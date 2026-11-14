"""Runs INSIDE the sandbox. One long-lived Python process per chat session.

It reads one JSON line per request on stdin and writes one JSON line per answer on a private pipe. The analyst's
code runs with `exec`; whatever it prints is captured. The process has no network: the names `kori`, `shop`,
`web` and `market` are the door. A call through the door writes a line to the host, which runs the allow-listed
function and writes the result back.

Stdlib, pandas, numpy and duckdb only. Nothing from the app is importable here.
"""
import ast
import contextlib
import datetime
import io
import json
import math
import os
import re
import sys
import traceback

# The host talks on a duplicate of stdout; fd 1 itself is pointed at stderr so a stray print cannot break the protocol.
_proto = os.fdopen(os.dup(1), "w", buffering=1)
os.dup2(2, 1)
_stdin = sys.stdin

for _p in reversed((sys._xoptions.get("kori_site") or "").split(os.pathsep)):     # where pandas, numpy and duckdb live
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

import duckdb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

DATA = os.environ.get("KORI_LAB_DATA", "/data")
MAX_ROWS = 400
MAX_OUT = 6000

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 60)


def _send(obj: dict) -> None:
    _proto.write(json.dumps(obj, ensure_ascii=False, default=_plain) + "\n")
    _proto.flush()


def _plain(v):
    """Anything the analyst computed, as JSON."""
    if v is None or isinstance(v, (bool, str, int)):
        return v
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else round(f, 4)
    if isinstance(v, (pd.Timestamp, datetime.datetime)):
        return v.isoformat()[:19] if (v.hour or v.minute or v.second) else v.date().isoformat()
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, pd.Period):
        return str(v)
    if v is pd.NaT or v is pd.NA:
        return None
    if isinstance(v, dict):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set, np.ndarray, pd.Index)):
        return [_plain(x) for x in v]
    if isinstance(v, pd.Series):
        return {str(k): _plain(x) for k, x in v.items()}
    if isinstance(v, pd.DataFrame):
        return [_plain(r) for r in v.to_dict("records")]
    return str(v)


# ------------------------------------------------------------------ the ledger
_facts: list[dict] = []
_tables: list[dict] = []
_products: list[dict] = []
_NAME = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
UNITS = {"eur", "eur_per_day", "eur_per_month", "pct", "count", "days", "months", "years", "date", "ratio", "text"}


def emit(name: str, value, unit: str = "eur", label: str = "") -> None:
    """Put one figure on the ledger. Only figures on the ledger may be shown to the customer."""
    if not _NAME.match(str(name)):
        raise ValueError(f"emit name must be snake_case letters, digits, underscores: {name!r}")
    if unit not in UNITS:
        raise ValueError(f"unit must be one of {sorted(UNITS)}")
    v = _plain(value)
    if isinstance(v, (dict, list)):
        raise ValueError("emit takes one value; use table() for rows")
    if v is None:
        raise ValueError(f"emit {name}: the value is empty (None or NaN)")
    _facts.append({"name": name, "value": v, "unit": unit, "label": str(label)[:120]})


def table(name: str, rows, label: str = "") -> None:
    """Put a small table on the ledger: a DataFrame or a list of dicts, at most 400 rows."""
    if not _NAME.match(str(name)):
        raise ValueError(f"table name must be snake_case: {name!r}")
    if isinstance(rows, pd.Series):
        rows = rows.reset_index()
    if isinstance(rows, pd.DataFrame):
        if not isinstance(rows.index, pd.RangeIndex):
            rows = rows.reset_index()
        rows.columns = [str(c) for c in rows.columns]
        recs = rows.head(MAX_ROWS + 1).to_dict("records")
    else:
        recs = list(rows)[: MAX_ROWS + 1]
    if len(recs) > MAX_ROWS:
        print(f"[table {name}: cut to the first {MAX_ROWS} rows]")
        recs = recs[:MAX_ROWS]
    recs = [_plain(r) for r in recs]
    if not recs or not isinstance(recs[0], dict):
        raise ValueError(f"table {name}: needs at least one row of named columns")
    _tables.append({"name": name, "columns": list(recs[0].keys()), "rows": recs, "label": str(label)[:120]})


def show(products) -> None:
    """Put real products (rows returned by shop.* or web.products) on the ledger so the view can picture them."""
    if isinstance(products, dict):
        products = [products]
    for p in products:
        if isinstance(p, dict) and p.get("name"):
            _products.append(_plain(p))


_said: list[str] = []


def eur(value, cents: bool = False) -> str:
    """Money the way this customer reads it: €1,357 or €56.54 in English, 1 357 € or 56,54 € in Finnish."""
    v = float(value)
    s = f"{v:,.2f}" if cents else f"{round(v):,}"
    if (G.get("me") or {}).get("lang") == "fi":
        return s.replace(",", "\u00a0").replace(".", ",") + "\u00a0€"
    return ("-€" + s[1:]) if s.startswith("-") else "€" + s


def say(text) -> None:
    """The written answer, when the cell can already give it: the customer reads it the moment the cell has run."""
    t = " ".join(str(text).split())
    if t:
        _said[:] = [t[:700]]


# -------------------------------------------------------------------- the door
_calls = 0


class _Door:
    def __init__(self, prefix: str):
        self._prefix = prefix

    def __getattr__(self, fn: str):
        if fn.startswith("_"):
            raise AttributeError(fn)

        def call(*args, **kwargs):
            global _calls
            _calls += 1
            _send({"t": "call", "id": _calls, "name": f"{self._prefix}.{fn}", "args": list(args), "kwargs": kwargs})
            line = _stdin.readline()
            if not line:
                raise RuntimeError("the host went away")
            rep = json.loads(line)
            if not rep.get("ok"):
                raise RuntimeError(f"{self._prefix}.{fn}: {rep.get('error')}")
            return rep.get("value")

        call.__name__ = fn
        return call

    def __repr__(self):
        return f"<{self._prefix}: calls go through the host>"


# ---------------------------------------------------------------------- data
def _load() -> dict:
    tx = pd.read_parquet(os.path.join(DATA, "tx.parquet"))
    tx["ts"] = pd.to_datetime(tx["ts"])
    tx["date"] = tx["ts"].dt.date
    with open(os.path.join(DATA, "me.json")) as f:
        me = json.load(f)
    today = datetime.date.fromisoformat(me.pop("today"))
    return {"tx": tx, "me": me, "today": today}


G: dict = {"__name__": "__kori__", "pd": pd, "np": np, "duckdb": duckdb, "math": math, "json": json, "datetime": datetime,
           "emit": emit, "table": table, "show": show, "say": say, "eur": eur,
           "kori": _Door("engine"), "shop": _Door("shop"), "web": _Door("web"), "market": _Door("market")}


def _run(code: str) -> tuple[bool, str, str | None]:
    """Execute one cell. Like a notebook, the value of a last bare expression is printed."""
    buf = io.StringIO()
    try:
        tree = ast.parse(code, "<cell>")
        last = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last = ast.Expression(tree.body.pop().value)
            ast.fix_missing_locations(last)
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(compile(tree, "<cell>", "exec"), G)
            if last is not None:
                v = eval(compile(last, "<cell>", "eval"), G)
                if v is not None:
                    print(v if isinstance(v, (str, pd.DataFrame, pd.Series)) else repr(v))
        return True, buf.getvalue(), None
    except BaseException as e:   # noqa: BLE001 - the analyst reads the error and fixes its code
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            return False, buf.getvalue(), type(e).__name__
        tb = traceback.extract_tb(e.__traceback__)
        where = next((f"line {f.lineno}" for f in reversed(tb) if f.filename == "<cell>"), "")
        return False, buf.getvalue(), f"{type(e).__name__}: {e}" + (f" ({where})" if where else "")


def main() -> None:
    try:
        G.update(_load())
    except Exception as e:   # noqa: BLE001
        _send({"t": "fatal", "error": f"{type(e).__name__}: {e}"})
        return
    _send({"t": "ready", "rows": int(len(G["tx"]))})
    for line in _stdin:
        try:
            req = json.loads(line)
        except ValueError:
            continue
        if req.get("op") != "run":
            continue
        _facts.clear(), _tables.clear(), _products.clear(), _said.clear()
        ok, out, err = _run(req.get("code") or "")
        if len(out) > MAX_OUT:
            out = out[:MAX_OUT] + f"\n[... {len(out) - MAX_OUT} more characters not shown]"
        _send({"t": "done", "id": req.get("id"), "ok": ok, "out": out, "err": err,
               "facts": list(_facts), "tables": list(_tables), "products": list(_products), "say": _said[0] if ok and _said else None})


if __name__ == "__main__":
    main()
