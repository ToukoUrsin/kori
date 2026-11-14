"""The figure check for the chat.

The analyst's code puts figures on a ledger. The written answer and the generated view may show only those.
In a view, figures are placeholders (`{{name|eur}}`) and table reads (`K.table("name")`) filled from the ledger, so
they cannot be wrong. What is left to check is what a model typed by hand: every literal number in the answer and
in the view's visible text is looked up on the ledger, and anything that is not there is flagged.
"""
from __future__ import annotations

import re

from ..ai import grounding

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][\w.]*)\s*(?:\|\s*(\w+))?\s*\}\}")
REF = re.compile(r"K\.(table|fact)\(\s*['\"]([\w]+)['\"]")
_BLOCKS = re.compile(r"<(style|script|template)\b[^>]*>.*?</\1\s*>", re.S | re.I)
_TAGS = re.compile(r"<[^>]+>")
_DIGITS = re.compile(r"\d+(?:[.,]\d+)?")


def allowed(ledger: dict, *more) -> set[float]:
    """Every number that is on the ledger (figures, table cells, product prices), plus numbers the customer typed."""
    acc: set[float] = set()
    facts = ledger.get("facts") or {}
    grounding.collect([f.get("v") for f in facts.values()], acc)
    for t in (ledger.get("tables") or {}).values():
        grounding.collect(t.get("rows"), acc)
        for c in t.get("columns") or []:                      # "p10", "year_5": a column name may carry a figure
            acc.update(float(x.replace(",", ".")) for x in _DIGITS.findall(str(c)))
    for p in ledger.get("products") or []:
        grounding.collect({k: v for k, v in p.items() if k not in ("image", "url", "id", "ean")}, acc)
    for x in more:
        grounding.collect(x, acc)
    return acc


def answer(text: str, ok: set[float], lang: str) -> list[str]:
    """Figures in the written answer that are not on the ledger."""
    return grounding.check(text or "", ok, lang)


def fragment(html: str, ledger: dict, ok: set[float], lang: str) -> dict:
    """{figures, traced, flagged}: how many figures the view shows, how many come from the ledger, and what does not."""
    facts, tables = ledger.get("facts") or {}, ledger.get("tables") or {}
    flagged: list[str] = []
    figures = traced = 0
    for name, _fmt in PLACEHOLDER.findall(html):
        figures += 1
        if name.split(".")[0] in facts:
            traced += 1
        else:
            flagged.append("{{" + name + "}}")
    for kind, name in REF.findall(html):
        if name not in (tables if kind == "table" else facts):
            flagged.append(f"K.{kind}({name})")
    used = {n for k, n in REF.findall(html) if k == "table" and n in tables}
    for n in used:                                             # every cell of a table the view reads is a ledger figure
        cells = sum(1 for r in tables[n].get("rows") or [] for v in r.values() if isinstance(v, (int, float)) and not isinstance(v, bool))
        figures += cells
        traced += cells
    if "K.data.products" in html or "K.products" in html:
        n = sum(1 for p in ledger.get("products") or [] if isinstance(p.get("price"), (int, float)))
        figures += n
        traced += n
    text = PLACEHOLDER.sub(" ", _TAGS.sub(" ", _BLOCKS.sub(" ", html)))
    for tok, v in grounding.numbers_in_text(text, lang):
        if grounding._ok(v, tok, ok):
            continue
        after = text[text.find(tok) + len(tok): text.find(tok) + len(tok) + 3]
        before = text[max(0, text.find(tok) - 2): text.find(tok)]
        moneyish = "€" in after or "€" in before or "%" in after or re.search(r"[.,]\d", tok) or v >= 100
        if moneyish:
            figures += 1
            flagged.append(tok)
    return {"figures": figures, "traced": traced, "flagged": list(dict.fromkeys(flagged))[:12]}
