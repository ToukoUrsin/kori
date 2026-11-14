"""Kept views: the questions the chat suggests itself open the same approved screen every time.

For each one, the code and the screen were written once with the models, then edited and approved by a person
(`kept/*.json`; scripts/keep_view.py saves one from a real turn). Asking one runs that code again on this customer's
own data, so every figure is computed now and goes through the same check; only the writing is skipped, and the work
view names it a kept view, not a model. Anything typed in other words is built fresh, and `fresh` on the request
builds a suggested one fresh too.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

log = logging.getLogger("kori.lab")
DIR = Path(__file__).parent / "kept"
_DEV = os.environ.get("KORI_LAB_DEV") == "1"
_loaded: dict[tuple[str, str], dict] | None = None


def norm(q: str) -> str:
    """The same question however it is typed: case, punctuation and spacing do not count."""
    return re.sub(r"[^\w€]+", " ", (q or "").lower()).strip()


def records() -> dict[tuple[str, str], dict]:
    global _loaded
    if _loaded is None or _DEV:                       # a developer edits these while the server runs
        out: dict[tuple[str, str], dict] = {}
        for f in sorted(DIR.glob("*.json")):
            try:
                rec = json.loads(f.read_text())
                if not (rec.get("cells") and rec.get("html") and rec.get("question")):
                    raise ValueError("needs question, cells and html")
                rec["file"] = f.name
                for q in [rec["question"], *(rec.get("also") or [])]:
                    out[(rec.get("lang") or "en", norm(q))] = rec
            except Exception as e:   # noqa: BLE001 - a broken file only means that question is built fresh
                log.warning("kept view %s not loaded: %s", f.name, e)
        _loaded = out
    return _loaded


def find(message: str, lang: str, customer: str | None = None) -> dict | None:
    """The kept view for this question, or None. A record with `param` answers a family of questions that differ by one
    number ("What if I save €99 a month for ten years?"): the number goes into the code, nothing else changes."""
    q = norm(message)
    rec = records().get((lang, q))
    if rec is None:
        rec = next((r for (lg, _), r in records().items() if lg == lang and r.get("param") and re.match(r["param"]["pattern"], q)), None)
    if rec is None or (rec.get("only") and customer not in rec["only"]):
        return None
    par = rec.get("param")
    if par:
        m = re.match(par["pattern"], q)
        value = m.group(1) if m else str(par["default"])
        if not (par.get("min", 0) <= float(value) <= par.get("max", 1e9)):
            return None
        rec = {**rec, "cells": [{**c, "code": c["code"].replace(par["token"], value)} for c in rec["cells"]]}
    return rec


def questions(lang: str, customer: str | None = None) -> list[str]:
    """The questions that have a kept view in this language, as the customer would ask them."""
    return [r["question"] for (lg, _), r in records().items() if lg == lang and not (r.get("only") and customer not in r["only"])]
