"""The sandbox, seen from the host: one jailed Python process per chat session.

The process is started with bubblewrap in its own mount, PID, IPC, UTS, user and network namespace. It sees a
read-only system and Python, an empty environment, a scratch tmpfs, and `/data` with exactly one customer's
transactions. No other customer's data, none of the app's code and none of its keys are mounted, and there is no
network device to reach anything with. The only way out is the door: a JSON line on the pipe that names an
allow-listed host function (kori.lab.door).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import resource
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from .. import config, data

log = logging.getLogger("kori.lab.kernel")

PRELUDE = Path(__file__).with_name("prelude.py")
RUN_TIMEOUT = 25.0          # seconds one cell may take, door calls included
START_TIMEOUT = 20.0
MEMORY_BYTES = int(os.environ.get("KORI_LAB_MEMORY_GB", "8")) * 1024 ** 3
COLUMNS = ["ts", "month", "amount", "balance", "type", "category", "kind", "merchant", "basket", "is_spend", "spend"]

DoorFn = Callable[[str, list, dict], Awaitable[Any]]
OnCall = Callable[[str, list, dict], Awaitable[None]]

_bwrap_ok: bool | None = None


def _limits() -> None:
    # Two processors and a cap on the memory the code can ask for. (Not RLIMIT_AS: numpy, Arrow and DuckDB reserve far
    # more address space than they use, per thread.)
    cpus = sorted(os.sched_getaffinity(0))
    if len(cpus) > 2:
        at = os.getpid() % (len(cpus) - 1)
        os.sched_setaffinity(0, {cpus[at], cpus[at + 1]})
    resource.setrlimit(resource.RLIMIT_DATA, (MEMORY_BYTES, MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 ** 2, 64 * 1024 ** 2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:                                   # if the machine runs short of memory, the sandbox goes first, not the app
        with open("/proc/self/oom_score_adj", "w") as f:
            f.write("1000")
    except OSError:
        pass
    os.setsid()


def _limits_unjailed() -> None:
    """Where bubblewrap cannot run: the same limits, and if the app runs as root the code runs as nobody, so it cannot
    read the app's environment or write anywhere that matters."""
    _limits()
    if os.geteuid() == 0:
        os.setgroups([])
        os.setgid(65534)
        os.setuid(65534)


def _jail(session_dir: Path) -> list[str]:
    """The bubblewrap command line. Everything the process can see is listed here."""
    a = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL", "--ro-bind", "/usr", "/usr"]
    for p in ("/lib", "/lib64", "/bin", "/sbin"):
        if os.path.islink(p):
            a += ["--symlink", os.readlink(p), p]
        elif os.path.isdir(p):
            a += ["--ro-bind", p, p]
    for p in _python_dirs():                           # the Python install and the packages (pandas, numpy, duckdb)
        if not p.startswith("/usr/"):
            a += ["--ro-bind", p, p]
    a += ["--ro-bind", str(session_dir), "/data", "--ro-bind", str(PRELUDE), "/kernel/prelude.py",
          "--tmpfs", "/tmp", "--tmpfs", "/work", "--proc", "/proc", "--dev", "/dev", "--chdir", "/work",
          "--clearenv", "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/work", "--setenv", "LANG", "C.UTF-8",
          "--setenv", "PYTHONDONTWRITEBYTECODE", "1", "--setenv", "OMP_NUM_THREADS", "2", "--setenv", "OPENBLAS_NUM_THREADS", "2",
          "--setenv", "KORI_LAB_DATA", "/data", *_python(), "/kernel/prelude.py"]
    return a


def _python() -> list[str]:
    """The real interpreter (symlinks resolved), isolated mode, with the package folders handed over explicitly."""
    return [os.path.realpath(sys.executable), "-I", "-u", "-X", "kori_site=" + os.pathsep.join(_site())]


def _site() -> list[str]:
    return [p for p in sys.path if p.rstrip("/").endswith(("site-packages", "dist-packages")) and os.path.isdir(p)]


def _python_dirs() -> list[str]:
    exe = os.path.realpath(sys.executable)
    return sorted({os.path.dirname(os.path.dirname(exe)), *(_site())})


def jail_works() -> bool:
    """True when this machine can start the jail. Checked once."""
    global _bwrap_ok
    if _bwrap_ok is None:
        _bwrap_ok = False
        if shutil.which("bwrap") and os.environ.get("KORI_LAB_JAIL", "1") != "0":
            import subprocess
            try:
                d = tempfile.mkdtemp(prefix="kori-lab-probe-")
                cmd = _jail(Path(d))
                cmd = cmd[: cmd.index(_python()[0])] + [_python()[0], "-I", "-c", "print('ok')"]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
                _bwrap_ok = r.returncode == 0 and "ok" in r.stdout
                if not _bwrap_ok:
                    log.warning("bubblewrap jail unavailable: %s", (r.stderr or r.stdout)[-300:])
                shutil.rmtree(d, ignore_errors=True)
            except Exception as e:   # noqa: BLE001
                log.warning("bubblewrap jail unavailable: %s", e)
    return _bwrap_ok


def isolation() -> str:
    return "bubblewrap" if jail_works() else "process"


class Kernel:
    """One customer's sandbox. `run` executes a cell and answers door calls while it runs."""

    def __init__(self, customer_id: str, lang: str = "en"):
        self.customer_id = customer_id
        self.lang = lang
        self.proc: asyncio.subprocess.Process | None = None
        self.dir: Path | None = None
        self.used = time.time()
        self.rows = 0
        self._lock = asyncio.Lock()
        self._starting = asyncio.Lock()

    def _write_data(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="kori-lab-"))
        df = data.transactions(self.customer_id)
        df[COLUMNS].to_parquet(self.dir / "tx.parquet", index=False)
        c = data.get_customer(self.customer_id)
        from ..state import PERSONAS
        name = next((p["name"] for p in PERSONAS if p["id"] == self.customer_id), None)
        (self.dir / "me.json").write_text(json.dumps({"name": name, "age": c.age, "area": c.area, "lang": self.lang,
                                                       "today": config.DEMO_TODAY.isoformat()}))
        os.chmod(self.dir, 0o755)
        for f in self.dir.iterdir():
            os.chmod(f, 0o644)

    async def start(self) -> None:
        async with self._starting:          # the chat opening and the first question may both ask for it: one start, the other waits
            await self._start()

    async def _start(self) -> None:
        if self.proc and self.proc.returncode is None:
            return
        await asyncio.to_thread(self._write_data)
        pre = _limits
        if jail_works():
            cmd = _jail(self.dir)
            env = None
        else:
            pre = _limits_unjailed   # a developer machine without bubblewrap: a plain child process with an empty environment
            cmd = [*_python(), str(PRELUDE)]
            env = {"PATH": "/usr/bin:/bin", "KORI_LAB_DATA": str(self.dir), "HOME": str(self.dir), "PYTHONDONTWRITEBYTECODE": "1",
                   "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"}
        self.proc = await asyncio.create_subprocess_exec(
            *cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            env=env, preexec_fn=pre, limit=32 * 1024 * 1024)
        msg = await asyncio.wait_for(self._read(), START_TIMEOUT)
        if not msg or msg.get("t") != "ready":
            await self.close()
            raise RuntimeError(f"sandbox did not start: {msg}")
        self.rows = msg.get("rows", 0)

    async def _read(self) -> dict | None:
        line = await self.proc.stdout.readline()
        if not line:
            return None
        try:
            return json.loads(line)
        except ValueError:
            return {"t": "noise"}

    async def _write(self, obj: dict) -> None:
        self.proc.stdin.write((json.dumps(obj, ensure_ascii=False, default=str) + "\n").encode())
        await self.proc.stdin.drain()

    async def run(self, run_id: str, code: str, door: DoorFn, on_call: OnCall | None = None, timeout: float = RUN_TIMEOUT) -> dict:
        """Execute one cell. Returns {ok, out, err, facts, tables, products, ms, calls}."""
        async with self._lock:
            self.used = time.time()
            await self.start()
            t0 = time.time()
            calls: list[dict] = []
            try:
                await self._write({"op": "run", "id": run_id, "code": code})

                async def loop() -> dict:
                    while True:
                        msg = await self._read()
                        if msg is None:
                            return {"ok": False, "out": "", "err": "the sandbox stopped (out of memory or killed)", "facts": [], "tables": [], "products": []}
                        if msg.get("t") == "call":
                            name, args, kwargs = msg.get("name", ""), msg.get("args") or [], msg.get("kwargs") or {}
                            calls.append({"name": name, "args": args, "kwargs": kwargs})
                            if on_call:
                                await on_call(name, args, kwargs)
                            try:
                                value = await door(name, args, kwargs)
                                await self._write({"ok": True, "value": value})
                            except Exception as e:   # noqa: BLE001 - the cell sees the error and can react
                                await self._write({"ok": False, "error": f"{type(e).__name__}: {e}"[:300]})
                        elif msg.get("t") == "done" and msg.get("id") == run_id:
                            return msg

                res = await asyncio.wait_for(loop(), timeout)
            except asyncio.TimeoutError:
                await self.close()
                res = {"ok": False, "out": "", "err": f"the cell ran longer than {int(timeout)} s and was stopped; the sandbox was restarted, "
                                                      "so variables from earlier cells are gone", "facts": [], "tables": [], "products": []}
            except (BrokenPipeError, ConnectionResetError):
                await self.close()
                res = {"ok": False, "out": "", "err": "the sandbox stopped; it was restarted, so variables from earlier cells are gone",
                       "facts": [], "tables": [], "products": []}
            if self.proc and self.proc.returncode is not None:
                await self.close()
            return {"ok": bool(res.get("ok")), "out": res.get("out") or "", "err": res.get("err"), "facts": res.get("facts") or [],
                    "tables": res.get("tables") or [], "products": res.get("products") or [], "say": res.get("say"),
                    "ms": int((time.time() - t0) * 1000), "calls": calls}

    async def close(self) -> None:
        p, self.proc = self.proc, None
        if p and p.returncode is None:
            try:
                os.killpg(p.pid, 9)
            except (ProcessLookupError, PermissionError):
                try:
                    p.kill()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(p.wait(), 3)
            except asyncio.TimeoutError:
                pass
        if self.dir:
            shutil.rmtree(self.dir, ignore_errors=True)
            self.dir = None


# ------------------------------------------------------------- one per session
_kernels: dict[str, Kernel] = {}
MAX_KERNELS = int(os.environ.get("KORI_LAB_MAX_KERNELS", "8"))
IDLE_SECONDS = 15 * 60


async def kernel_for(session_id: str, customer_id: str, lang: str = "en") -> Kernel:
    k = _kernels.get(session_id)
    if k and k.customer_id != customer_id:
        await k.close()
        k = None
    if not k:
        now = time.time()
        for sid in [s for s, x in _kernels.items() if now - x.used > IDLE_SECONDS]:
            await _kernels.pop(sid).close()
        while len(_kernels) >= MAX_KERNELS:
            oldest = min(_kernels, key=lambda s: _kernels[s].used)
            await _kernels.pop(oldest).close()
        k = _kernels[session_id] = Kernel(customer_id, lang)
    k.lang = lang
    return k


async def drop(session_id: str) -> None:
    k = _kernels.pop(session_id, None)
    if k:
        await k.close()


async def close_all() -> None:
    for sid in list(_kernels):
        await drop(sid)
