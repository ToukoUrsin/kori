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


def _hit(term: str, q: str, words: list[str]) -> bool:
    """A stem matches the start of a word ("grocer" in "groceries"); a phrase matches where a word starts."""
    return (" " + term) in (" " + q) if " " in term else any(w.startswith(term) for w in words)


# Words no English or Finnish question has. A question in another language is never one of the approved ones.
_ELSEWHERE = {"jag", "hur", "mycket", "och", "är", "inte", "vad", "förra", "månad", "månaden", "pengar", "mina", "mitt", "ska",
              "wie", "viel", "ich", "habe", "und", "nicht", "mein", "meine", "combien", "cuánto", "cuanto", "dinero"}
# Two questions in one ("... and what would I save if I halved it?") is not the approved question either.
_AND = ("and what", "and how", "and if", "and can", "and would", "and should", "and where", "and when", "and why",
        "ja mitä", "ja paljonko", "ja paljon", "ja miten", "ja jos", "ja voinko", "ja kuinka", "ja missä", "ja milloin", "ja miksi")


def _subject(rec: dict, q: str) -> bool:
    """The question holds this view's own words, whatever else it says."""
    words = q.split()
    return bool(rec.get("match")) and all(any(_hit(t, q, words) for t in g) for g in rec["match"])


def _means(rec: dict, q: str, loose: bool) -> bool:
    """The same question in other words. `match` is a list of groups of stems: every group needs one hit, and no
    `unless` stem may appear. No model reads the question, so the bank's approved-only mode can use it too.
    Outside that mode it is stricter: a long question, or one with a number this view has no place for, is built fresh."""
    groups = rec.get("match")
    if not groups:
        return False
    words = q.split()
    if _ELSEWHERE & {w.strip("?!.,") for w in words}:
        return False
    if not rec.get("first"):                          # money that will not stretch is heard however long or tangled the message is
        if any((" " + t + " ") in (" " + q + " ") for t in _AND):
            return False
        if not loose and (len(words) > 14 or (re.search(r"\d", q) and not (rec.get("param") or rec.get("params")))):
            return False
    if any(_hit(t, q, words) for t in rec.get("unless") or []):
        return False
    return all(any(_hit(t, q, words) for t in g) for g in groups)


def _fill(rec: dict, q: str, own: dict | None = None) -> dict | None:
    """Put the question's own number or thing into the reviewed code. A number is digits within the view's limits, a
    thing is one of the view's own listed values, and a name is one of this customer's own (`own`: the merchants on their
    account, matched by the whole name and never by a part of it), so nothing the customer typed is ever run as code."""
    pars = ([rec["param"]] if rec.get("param") else []) + list(rec.get("params") or [])
    if not pars:
        return rec
    cells = rec["cells"]
    for par in pars:
        if "own" in par:                                # the longest of their own names that the question holds whole
            names = sorted((own or {}).get(par["own"]) or [], key=lambda n: -len(norm(n)))
            name = next((n for n in names if norm(n) and (" " + norm(n) + " ") in (" " + q + " ")), None)
            value = None if name is None else json.dumps(name, ensure_ascii=False)
        elif "choices" in par:
            value = next((v for k, v in par["choices"].items() if _hit(k, q, q.split())), par.get("default"))
        else:
            qn = re.sub(r"(?<!\d)(\d{1,3}) (\d{3})(?!\d)", r"\1\2", q)          # "€3,000" and "3 000 €" are 3000
            m = re.match(par["pattern"], q) if par.get("pattern") else None
            m = m or (re.search(par["find"], qn) if par.get("find") else None)
            value = m.group(1) if m else par.get("default")
            if m and par.get("cents"):                  # "€1,042.04" and "1 042,04 €": euros, then two digits of cents
                value = m.group(1).replace(" ", "") + "." + m.group(2)
            if value is not None and not (par.get("min", 0) <= float(value) <= par.get("max", 1e9)):
                return None
        if value is None:
            return None
        cells = [{**c, "code": c["code"].replace(par["token"], str(value))} for c in cells]
    return {**rec, "cells": cells}


def find(message: str, lang: str, customer: str | None = None, loose: bool = False, own: dict | None = None) -> dict | None:
    """The kept view for this question, or None.

    Three ways in, most exact first: the question as written (or one of its `also` wordings); a `param` pattern, for a
    family of questions that differ by one number ("What if I save €99 a month for ten years?"); and `match`, the same
    question in the customer's own words. `loose` is the bank's approved-only mode, where a kept view is the only answer.
    `own` holds this customer's own names (their merchants), for a view about one payment they tapped."""
    q = norm(message)
    mine = [r for (lg, _), r in records().items() if lg == lang and not (r.get("only") and customer not in r["only"])]
    rec = records().get((lang, q))
    if rec is not None and rec.get("only") and customer not in rec["only"]:
        rec = None
    if rec is None:
        rec = next((r for r in mine if r.get("param") and r["param"].get("pattern") and re.match(r["param"]["pattern"], q)), None)
    if rec is None:
        rec = next((r for r in mine if _means(r, q, loose)), None)
    urgent = [r for r in mine if r.get("first")]         # "I can't pay my bills" is never the plain bills answer, in any wording
    if rec is not None and not rec.get("first") and any(_subject(r, q) for r in urgent):
        rec = next((r for r in urgent if _means(r, q, loose)), None)
    return _fill(rec, q, own) if rec else None


def questions(lang: str, customer: str | None = None) -> list[str]:
    """The questions that have a kept view in this language, as the customer would ask them."""
    seen: dict[str, None] = {}
    for (lg, _), r in records().items():
        if lg == lang and not (r.get("tap") or r.get("quiet")) and not (r.get("only") and customer not in r["only"]):   # a tapped payment and a cry for help are not questions to suggest
            seen.setdefault(r["question"])
    return list(seen)


def nearest(message: str, lang: str, customer: str | None = None, n: int = 3) -> list[str]:
    """The approved questions closest to this one, for the "not on the approved list" reply: the ones that share its
    subject come first, so "how much do I blow on restaurants" is offered the eating-out answer and not the first three."""
    q = norm(message)
    words = q.split()
    scored: dict[str, int] = {}
    for (lg, _), r in records().items():
        if lg != lang or r.get("tap") or r.get("quiet") or (r.get("only") and customer not in r["only"]):
            continue
        hits = sum((2 if i == 0 else 1) for i, g in enumerate(r.get("match") or []) if any(_hit(t, q, words) for t in g))   # the first group is the subject
        scored[r["question"]] = max(scored.get(r["question"], 0), hits)
    order = list(scored)
    close = sorted((k for k in order if scored[k] > 0), key=lambda k: (-scored[k], order.index(k)))
    return (close + [k for k in order if scored[k] == 0])[:n]


def approved(lang: str) -> list[dict]:
    """What the bank has reviewed, for its own list: the question, when it was approved and which file holds the code."""
    out: dict[str, dict] = {}
    for (lg, _), r in records().items():
        if lg == lang:
            out.setdefault(r["file"], {"question": r["question"], "title": r.get("title", ""), "approved": r.get("kept", ""),
                                       "version": r.get("version", 1), "file": r["file"], "wordings": bool(r.get("match"))})
    return sorted(out.values(), key=lambda x: x["file"])
