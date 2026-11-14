"""The designer: one model call that writes the interface for one answer.

It gets the question, the analyst's brief and the ledger, and streams an HTML fragment for the locked frame
(`web/public/lab/`, contract in `docs/LAB.md`). It never sees or types a figure it could get wrong: single figures are
`{{name|format}}` placeholders and rows are read from the ledger by the frame's kit, so what reaches the screen is
what the sandbox computed. Claude writes it; if Claude does not start within a few seconds, Gemini does with the same prompt.
"""
from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

from .. import config

log = logging.getLogger("kori.lab.designer")

PROMPT_FILE = Path(__file__).with_name("ui_prompt.md")
FIRST_TEXT_S = float(os.environ.get("KORI_UI_FIRST_S", "14"))    # Claude must start writing within this, or Gemini takes over (it thinks 7 to 8 s on the largest ledgers)
HEDGE_S = float(os.environ.get("KORI_UI_HEDGE_S", "4"))          # silent this long: Gemini starts beside it, so a takeover is not from cold
EFFORT = os.environ.get("KORI_UI_EFFORT", "low")                  # thinking cannot be switched off on these models; low starts fastest
MAX_TOKENS = 12000
TABLE_HEAD = 6                                                    # rows of each table the model sees; the frame gets them all
_HTTP_TIMEOUT = httpx.Timeout(90, connect=4)
_CACHE = {"type": "ephemeral", "ttl": "1h"}                       # a cold prompt costs seconds before the first word: keep it an hour

_used: contextvars.ContextVar[str] = contextvars.ContextVar("kori_ui_model", default="")
_last = ""
_stats: contextvars.ContextVar[dict] = contextvars.ContextVar("kori_ui_stats", default={})
_prompt_cache: tuple[float, str] | None = None
_TRAILING_TICKS = re.compile(r"\s*`{1,3}\s*$")


def model_used() -> str:
    """The model that wrote the last view in this task (or anywhere, if this task wrote none)."""
    return _used.get() or _last


def stats() -> dict:
    """Timing of the last call in this task: {model, first_s, total_s, chars, fallback, usage}."""
    return dict(_stats.get())


def system_prompt() -> str:
    global _prompt_cache
    m = PROMPT_FILE.stat().st_mtime
    if not _prompt_cache or _prompt_cache[0] != m:
        _prompt_cache = (m, PROMPT_FILE.read_text())
    return _prompt_cache[1]


# ------------------------------------------------------------------ what the model is shown
_NOT_SHOWN = {"url", "ean", "unit_price", "unit", "kind", "own_brand", "by_weight", "category", "category_name", "fetched", "live", "run"}


def _short(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 2)
    if isinstance(v, str) and len(v) > 90:
        return v[:88] + "…"
    if isinstance(v, dict):             # a product inside a row: what it is, and that it has a picture
        return {k: ("(picture)" if k == "image" else _short(x)) for k, x in v.items() if k not in _NOT_SHOWN}
    return v


def _steps(ledger: dict) -> dict[str, int]:
    """The cells that put something on the ledger, numbered in order (empty when it was one cell)."""
    runs: list[str] = []
    for group in (ledger.get("facts") or {}, ledger.get("tables") or {}):
        for x in group.values():
            r = x.get("run") if isinstance(x, dict) else None
            if r and r not in runs:
                runs.append(r)
    runs.sort(key=lambda r: (int(r[1:]) if r[1:].isdigit() else 0, r))
    return {r: i + 1 for i, r in enumerate(runs)} if len(runs) > 1 else {}


def digest(ledger: dict) -> dict:
    """The ledger as the model sees it: every single figure, the shape and first rows of every table, products without
    their picture paths. Enough to design with, too little to copy figures from."""
    facts, steps = {}, _steps(ledger)
    for name, f in (ledger.get("facts") or {}).items():
        f = f if isinstance(f, dict) else {"v": f}
        facts[name] = {k: _short(f[k]) for k in ("v", "unit", "label") if f.get(k) not in (None, "")}
        if steps.get(f.get("run")):
            facts[name]["step"] = steps[f["run"]]
    tables = {}
    for name, t in (ledger.get("tables") or {}).items():
        rows = t.get("rows") if isinstance(t, dict) else t
        rows = rows or []
        cols = (t.get("columns") if isinstance(t, dict) else None) or (list(rows[0]) if rows and isinstance(rows[0], dict) else [])
        head = [{k: _short(v) for k, v in r.items()} if isinstance(r, dict) else r for r in rows[:TABLE_HEAD]]
        entry: dict[str, Any] = {"columns": cols, "rows": len(rows), "first_rows": head}
        if len(rows) > TABLE_HEAD and isinstance(rows[-1], dict):
            entry["last_row"] = {k: _short(v) for k, v in rows[-1].items()}
        if isinstance(t, dict) and t.get("label"):
            entry["label"] = t["label"]
        if isinstance(t, dict) and steps.get(t.get("run")):
            entry["step"] = steps[t["run"]]
        tables[name] = entry
    products = [{k: _short(p[k]) for k in ("id", "name", "brand", "price", "unit_price", "unit", "size", "store") if p.get(k) not in (None, "")}
                | {"has_image": bool(p.get("image"))} for p in ledger.get("products") or []]
    out: dict[str, Any] = {"today": ledger.get("today"), "customer": ledger.get("customer"), "facts": facts, "tables": tables}
    if products:
        out["products"] = products
    if ledger.get("sources"):
        out["sources"] = [{"title": s.get("title"), "host": s.get("host"), "url": s.get("url")} for s in ledger["sources"][:6]]
    return out


def user_message(payload: dict) -> str:
    lang = "Finnish" if payload.get("lang") == "fi" else "English"
    parts = [
        f"Language of every visible word: {lang}.",
        f"Width: {payload.get('width') or 390} px.",
        f"The customer asked: {payload.get('question') or ''}",
    ]
    if payload.get("title"):
        parts.append(f"Working title of the view: {payload['title']}")
    if payload.get("answer"):
        parts.append("The written answer shown above your view (do not repeat it word for word):\n" + str(payload["answer"]))
    parts.append("The analyst's brief:\n" + (str(payload.get("brief") or "").strip() or "(none: choose the form yourself from the ledger)"))
    parts.append("The ledger (tables are cut to their first rows; the frame holds all rows):\n"
                 + json.dumps(digest(payload.get("data") or {}), ensure_ascii=False, separators=(",", ":")))
    if _steps(payload.get("data") or {}):
        parts.append("The analysis took more than one step (`step` on each entry). Where two entries cover the same thing, the one from the "
                     "later step is the answer and the earlier one is working: leave the earlier one out.")
    parts.append("Write the fragment now, straight away and without planning it first: the customer is watching it appear. "
                 "HTML only, starting with the first tag.")
    return "\n\n".join(parts)


# ------------------------------------------------------------------ output hygiene
class _Fence:
    """Drops a ```html fence if the model wrapped its answer in one, while streaming."""

    def __init__(self) -> None:
        self.head = ""
        self.started = False
        self.tail = ""

    def feed(self, text: str) -> str:
        if not self.started:
            self.head += text
            s = self.head.lstrip()
            if not s or (s.startswith("`") and "\n" not in s) or (len(s) < 3 and "```".startswith(s)):
                return ""
            if s.startswith("```"):
                s = s.split("\n", 1)[1]
            self.started, text = True, s
        text = self.tail + text
        m = _TRAILING_TICKS.search(text)
        keep = m.start() if m and "`" in m.group(0) else len(text)
        self.tail, out = text[keep:], text[:keep]
        return out

    def end(self) -> str:
        t, self.tail = self.tail, ""
        return "" if t.strip() == "```" else t


# ------------------------------------------------------------------ Claude
async def _claude(payload: dict, model: str, effort: str | None, usage: dict) -> AsyncIterator[str]:
    key = config.anthropic_key()
    if not key:
        raise RuntimeError("no key for the designer model")
    body: dict[str, Any] = {
        "model": model, "max_tokens": MAX_TOKENS, "stream": True,
        # the design system is the same for every question: first, with a cache breakpoint
        "system": [{"type": "text", "text": system_prompt(), "cache_control": _CACHE}],
        "messages": [{"role": "user", "content": user_message(payload)}],
    }
    if effort:
        body["output_config"] = {"effort": effort}
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as c:
        async with c.stream("POST", config.ANTHROPIC_BASE_URL.rstrip("/") + "/v1/messages", json=body, headers=headers) as r:
            if r.status_code != 200:
                raise RuntimeError(f"designer model answered {r.status_code}: {(await r.aread())[:240]!r}")
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:])
                except ValueError:
                    continue
                kind = ev.get("type")
                if kind == "content_block_delta" and (ev.get("delta") or {}).get("type") == "text_delta":
                    yield ev["delta"].get("text") or ""
                elif kind == "message_start":
                    usage.update((ev.get("message") or {}).get("usage") or {})
                elif kind == "message_delta":
                    usage.update(ev.get("usage") or {})
                    if (ev.get("delta") or {}).get("stop_reason") == "refusal":
                        raise RuntimeError("the designer model declined")
                elif kind == "error":
                    raise RuntimeError(f"designer stream error: {str(ev.get('error'))[:240]}")


async def warm(model: str | None = None) -> float:
    """Put the design system in the model's cache, so the first real question starts as fast as the rest. Call at
    start-up and again within the hour. Returns the seconds it took; never raises."""
    t0 = time.monotonic()
    name = model or config.UI_MODEL
    key = config.anthropic_key()
    if name.startswith("gemini") or not key:
        return 0.0
    body = {"model": name, "max_tokens": 16, "output_config": {"effort": "low"},
            "system": [{"type": "text", "text": system_prompt(), "cache_control": _CACHE}],
            "messages": [{"role": "user", "content": "Reply with the single word: ready"}]}
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(40, connect=4)) as c:
            r = await c.post(config.ANTHROPIC_BASE_URL.rstrip("/") + "/v1/messages", json=body, headers=headers)
            if r.status_code != 200:
                log.warning("designer warm-up answered %s: %s", r.status_code, r.text[:160])
    except Exception as e:  # noqa: BLE001
        log.warning("designer warm-up failed: %s", str(e)[:160])
    return round(time.monotonic() - t0, 2)


# ------------------------------------------------------------------ Gemini (stand-in)
async def _gemini(payload: dict, model: str) -> AsyncIterator[str]:
    from google.genai import types

    from ..ai.agent import client
    cfg = types.GenerateContentConfig(system_instruction=system_prompt(), max_output_tokens=MAX_TOKENS,
                                      thinking_config=types.ThinkingConfig(thinking_level="low"))
    stream = await client().aio.models.generate_content_stream(model=model, contents=user_message(payload), config=cfg)
    async for ch in stream:
        if ch.text:
            yield ch.text


_DONE = object()


async def _pump(gen: AsyncIterator[str], q: asyncio.Queue) -> None:
    try:
        async for t in gen:
            if t:
                await q.put(t)
        await q.put(_DONE)
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 - handed to the reader
        await q.put(e)


async def write_ui(payload: dict, model: str | None = None, effort: str | None = None) -> AsyncIterator[str]:
    """Yield the fragment as it is written. `payload = {question, lang, answer, brief, data, width}`.

    Claude writes. If it is still silent after HEDGE_S the stand-in starts beside it, unseen; whichever the clock
    favours at FIRST_TEXT_S carries on alone. Claude's first piece before that cancels the stand-in."""
    global _last
    t0 = time.monotonic()
    st: dict[str, Any] = {"model": "", "first_s": None, "total_s": None, "chars": 0, "fallback": "", "usage": {}}
    _stats.set(st)
    name = model or config.UI_MODEL
    on_clock = not name.startswith("gemini")          # only Claude's first piece is timed; the stand-in is the last resort
    tasks: list[asyncio.Task] = []

    def launch(gen: AsyncIterator[str]) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        tasks.append(asyncio.create_task(_pump(gen, q)))
        return q

    q = launch(_claude(payload, name, effort or EFFORT, st["usage"]) if on_clock else _gemini(payload, name))
    spare: asyncio.Queue | None = None
    fence, wrote = _Fence(), False
    try:
        while True:
            if wrote or not on_clock:
                wait = 75.0
            else:
                wait = max(0.05, (HEDGE_S if spare is None else FIRST_TEXT_S) - (time.monotonic() - t0))
            try:
                item = await asyncio.wait_for(q.get(), wait)
            except asyncio.TimeoutError:
                if wrote or not on_clock:
                    raise RuntimeError(f"{name} stopped writing") from None
                if spare is None and HEDGE_S < FIRST_TEXT_S:
                    spare = launch(_gemini(payload, config.GEMINI_MODEL))
                    continue
                item = RuntimeError(f"{name} did not start writing within {FIRST_TEXT_S:.0f} s")
            if item is _DONE and not wrote:
                item = RuntimeError(f"{name} wrote nothing")
            if isinstance(item, Exception):
                if wrote or not on_clock:   # half a view cannot be restarted on another model: the frame already shows it
                    log.warning("designer %s failed%s: %s", name, " mid-view" if wrote else "", str(item)[:200])
                    raise item
                st["fallback"] = str(item)[:160]
                log.warning("designer %s failed before writing, the stand-in takes over: %s", name, str(item)[:200])
                tasks[0].cancel()
                q = spare if spare is not None else launch(_gemini(payload, config.GEMINI_MODEL))
                name, on_clock, fence = config.GEMINI_MODEL, False, _Fence()
                st["usage"] = {}
                continue
            if item is _DONE:
                break
            out = fence.feed(item)
            if not out:
                continue
            if not wrote:
                wrote = True
                st["model"], st["first_s"] = name, round(time.monotonic() - t0, 2)
                _used.set(name)
                _last = name
                if on_clock and len(tasks) > 1:      # Claude made it: the stand-in is not needed
                    tasks[1].cancel()
            st["chars"] += len(out)
            yield out
        tail = fence.end()
        if tail:
            st["chars"] += len(tail)
            yield tail
    finally:
        st["total_s"] = round(time.monotonic() - t0, 2)
        for t in tasks:
            if not t.done():
                t.cancel()
