"""The figure check for the chat.

The analyst's code puts figures on a ledger. The written answer and the generated view may show only those.
In a view, figures are placeholders (`{{name|eur}}`) and table reads (`K.table("name")`) filled from the ledger, so
they cannot be wrong. What is left to check is what a model typed by hand: every literal number in the answer and
in the view's visible text is looked up on the ledger, and anything that is not there is flagged.
"""
from __future__ import annotations

import re

from ..ai import grounding

# the same reading as the runtime (web/public/lab/runtime.js): any name, an optional format, and one closing brace is enough
PLACEHOLDER = re.compile(r"\{\{\s*([^{}|]+?)\s*(?:\|\s*(\w+)\s*)?(?:\|[^{}]*)?\}\}?")
CELL = re.compile(r"^([\w-]+)\.(\d+|first|last)\.(.+)$")
EACH = re.compile(r"<k-each\b[^>]*?\btable\s*=\s*['\"]([\w]+)['\"][^>]*>(.*?)</k-each\s*>", re.S | re.I)
ROWCELL = re.compile(r"(?<!\{)\{\s*([^{}|<>\"'=;:\n]{1,60}?)\s*(?:\|\s*\w+\s*)?\}(?!\})")
_HOLE = re.compile(r"(?<![A-Za-z])(?:nan|NaN|NaT|undefined)(?![A-Za-z])|<NA>|[{}]")
REF = re.compile(r"K\.(table|fact)\(\s*['\"]([\w]+)['\"]")
KIT_TABLE = re.compile(r"<k-[\w-]+\b[^>]*?\btable\s*=\s*['\"]([\w]+)['\"]")       # <k-each table="swaps">, <k-chart table="…">
KIT_PRODUCTS = re.compile(r"<k-product\b|<k-each\b[^>]*\bproducts\b|K\.data\.products|K\.products")
_BLOCKS = re.compile(r"<(style|script|template)\b[^>]*>.*?</\1\s*>", re.S | re.I)
_TAGS = re.compile(r"<[^>]+>")
_DIGITS = re.compile(r"\d+(?:[.,]\d+)?")


def _no_links(v):
    """A product without its addresses and codes: the digits in a picture path or an EAN are not figures anyone computed."""
    if isinstance(v, dict):
        return {k: _no_links(x) for k, x in v.items() if k not in ("image", "url", "id", "ean")}
    if isinstance(v, list):
        return [_no_links(x) for x in v]
    return v


def allowed(ledger: dict, *more) -> set[float]:
    """Every number that is on the ledger (figures, table cells, product prices), plus numbers the customer typed."""
    acc: set[float] = set()
    facts = ledger.get("facts") or {}
    grounding.collect([f.get("v") for f in facts.values()], acc)
    for t in (ledger.get("tables") or {}).values():
        grounding.collect(_no_links(t.get("rows")), acc)
        for c in t.get("columns") or []:                      # "p10", "year_5": a column name may carry a figure
            acc.update(float(x.replace(",", ".")) for x in _DIGITS.findall(str(c)))
    for p in ledger.get("products") or []:
        grounding.collect(_no_links(p), acc)
    for x in more:
        grounding.collect(x, acc)
    return acc


def _cells(v) -> int:
    """How many figures a row holds, counting the products inside it."""
    if isinstance(v, bool):
        return 0
    if isinstance(v, (int, float)):
        return 1
    if isinstance(v, dict):
        return sum(_cells(x) for k, x in v.items() if k not in ("ean", "id"))
    if isinstance(v, list):
        return sum(_cells(x) for x in v)
    return 0


def answer(text: str, ok: set[float], lang: str) -> list[str]:
    """Figures in the written answer that are not on the ledger."""
    return grounding.check(text or "", ok, lang)


def fragment(html: str, ledger: dict, ok: set[float], lang: str) -> dict:
    """{figures, traced, flagged}: how many figures the view shows, how many come from the ledger, and what does not."""
    facts, tables = ledger.get("facts") or {}, ledger.get("tables") or {}
    flagged: list[str] = []
    figures = traced = 0
    def column(t: dict, path: str) -> bool:                           # a column of this table, or a field inside one ("have.name")
        cols = [str(c) for c in t.get("columns") or []]
        return path in cols or path.split(".")[0] in cols

    for name, _fmt in PLACEHOLDER.findall(html):
        figures += 1
        cell = CELL.match(name)
        if name in facts:                                            # {{saving}}
            traced += 1
        elif cell and cell.group(1) in tables:                       # a table cell, {{months.5.month}}: the row and the column must exist
            t = tables[cell.group(1)]
            n = len(t.get("rows") or [])
            if column(t, cell.group(3)) and n and (cell.group(2) in ("first", "last") or int(cell.group(2)) < n):
                traced += 1
            else:
                flagged.append("{{" + name + "}}")
        else:
            flagged.append("{{" + name + "}}")
    for tname, body in EACH.findall(html):                           # a row template may name only columns that table has
        if tname in tables:
            for path in ROWCELL.findall(PLACEHOLDER.sub(" ", body)):
                if path != "$i" and not column(tables[tname], path):
                    flagged.append("{" + path + "}")
    for kind, name in REF.findall(html):
        if name not in (tables if kind == "table" else facts):
            flagged.append(f"K.{kind}({name})")
    for name in KIT_TABLE.findall(html):
        if name not in tables:
            flagged.append(f'table="{name}"')
    used = {n for k, n in REF.findall(html) if k == "table" and n in tables} | {n for n in KIT_TABLE.findall(html) if n in tables}
    for n in used:                                             # every cell of a table the view reads is a ledger figure
        cells = sum(_cells(r) for r in tables[n].get("rows") or [])
        figures += cells
        traced += cells
    if KIT_PRODUCTS.search(html):
        n = sum(1 for p in ledger.get("products") or [] if isinstance(p.get("price"), (int, float)))
        figures += n
        traced += n
    text = PLACEHOLDER.sub(" ", _TAGS.sub(" ", _BLOCKS.sub(" ", html)))
    for hole in _HOLE.findall(text):                                 # a brace or "nan" a customer would read as it stands
        flagged.append(hole)
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
