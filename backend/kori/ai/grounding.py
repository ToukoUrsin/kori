"""Number check: every figure the coach says must exist in a tool result of this turn.

The model explains; it does not calculate. After it writes an answer we pull out every number
and look for it among the numbers the engine returned (allowing ordinary rounding). Anything
that cannot be traced is sent back for one rewrite.
"""
from __future__ import annotations

import re
from datetime import date

NUM = re.compile(r"(?<![\w])[-−]?\d[\d   ,.]*\d|(?<![\w])\d")
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})(?:-(\d{2}))?\b")
ALWAYS = {float(i) for i in range(0, 13)} | {100.0, 15.0}       # small counts, "three baskets", the 15th


def _parse(tok: str, lang: str) -> float | None:
    t = tok.replace(" ", "").replace(" ", "").replace(" ", "").replace("−", "-").rstrip(".,")
    if not t or t == "-":
        return None
    if lang == "fi":
        # 1.094,50 or 1094,50 -> comma is the decimal mark; a dot before three digits is a thousands mark
        if "," in t:
            t = t.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", t):
            t = t.replace(".", "")
    else:
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", t):
            t = t.replace(",", "")
        elif "," in t and "." not in t and re.fullmatch(r"-?\d+,\d{1,2}", t):
            t = t.replace(",", ".")
        else:
            t = t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def numbers_in_text(text: str, lang: str = "en") -> list[tuple[str, float]]:
    text = ISO_DATE.sub(" ", text)
    out = []
    for mt in NUM.finditer(text):
        tok = mt.group(0)
        # "15.10." Finnish date or "21:30" time fragments: split on the separators and check each part
        if lang == "fi" and re.fullmatch(r"\d{1,2}\.\d{1,2}\.?", tok.strip()) and text[mt.end():mt.end() + 1] in (".", " ", ",", ")", ""):
            for part in tok.strip(".").split("."):
                out.append((part, float(part)))
            continue
        v = _parse(tok, lang)
        if v is not None:
            out.append((tok.strip(), abs(v)))
    return out


def collect(obj, acc: set[float] | None = None) -> set[float]:
    """Every number in a tool result, including digits inside strings and the parts of dates."""
    acc = acc if acc is not None else set()
    if isinstance(obj, bool) or obj is None:
        return acc
    if isinstance(obj, (int, float)):
        v = abs(float(obj))
        acc.add(v)
        if 0 < v <= 1.5:
            acc.add(round(v * 100, 1))        # shares are stored as 0.35, said as 35%
        return acc
    if isinstance(obj, str):
        for y, mo, d in ISO_DATE.findall(obj):
            acc.update({float(y), float(mo)})
            if d:
                acc.add(float(d))
                try:
                    acc.add(float(date(int(y), int(mo), int(d)).isocalendar()[1]))
                except ValueError:
                    pass
        for _, v in numbers_in_text(obj, "en"):
            acc.add(v)
        for _, v in numbers_in_text(obj, "fi"):
            acc.add(v)
        return acc
    if isinstance(obj, dict):
        for v in obj.values():
            collect(v, acc)
        return acc
    if isinstance(obj, (list, tuple, set)):
        for v in obj:
            collect(v, acc)
    return acc


def _ok(x: float, tok: str, allowed: set[float]) -> bool:
    if x in ALWAYS:
        return True
    decimals = len(tok.replace(",", ".").rsplit(".", 1)[1]) if re.search(r"[.,]\d{1,2}$", tok) else 0
    for a in allowed:
        if decimals:
            if abs(round(a, decimals) - x) < 1e-9:
                return True
        else:
            if abs(a - x) <= max(0.5, 0.012 * abs(a)) + 1e-9:
                return True
    return False


def check(text: str, allowed: set[float], lang: str = "en") -> list[str]:
    """Tokens in `text` that cannot be traced to a tool result."""
    bad = []
    for tok, v in numbers_in_text(text, lang):
        if not _ok(v, tok, allowed):
            bad.append(tok)
    return list(dict.fromkeys(bad))


def consistency_issues(results: list[dict]) -> list[dict]:
    """Find contradictory canonical quantities returned in one turn.

    Only fields with an explicit canonical name participate. Transaction totals,
    category totals and labelled windows are intentionally left alone.
    """
    found: dict[str, list[float]] = {}

    def walk(obj, parent: str = ""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in ("monthly_income", "income_typical") and isinstance(value, (int, float)):
                    found.setdefault("monthly_income", []).append(float(value))
                elif parent == "usual_month" and key == "income" and isinstance(value, (int, float)):
                    found.setdefault("monthly_income", []).append(float(value))
                walk(value, key)
        elif isinstance(obj, list):
            for value in obj:
                walk(value, parent)
    for result in results:
        walk(result)
    return [{"quantity": key, "values": sorted({round(v, 2) for v in vals})}
            for key, vals in found.items() if len({round(v, 2) for v in vals}) > 1]


_FIELD_LABELS = {
    "amount": ("Safe to spend until payday", "Turvallista käyttää palkkapäivään asti"),
    "per_day": ("Safe pace per day", "Turvallinen päivätahti"),
    "this_week": ("Safe to spend this week", "Turvallista käyttää tällä viikolla"),
    "usual_per_day": ("Your usual everyday pace per day", "Tavallinen arjen päivätahtisi"),
    "everyday_spent": ("Everyday spending in the pay cycle", "Palkkajakson arjen menot"),
    "everyday_available": ("Everyday money left by income", "Tuloista arkeen jäävä raha"),
    "total": ("Total in the tool result", "Työkalun tulos yhteensä"),
}


def _paths(obj, path=""):
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        yield path, float(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _paths(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _paths(v, f"{path}[{i}]")


def _fallback_label(tool: str, path: str, lang: str) -> str:
    key = path.rsplit(".", 1)[-1].split("[")[0]
    if key in _FIELD_LABELS:
        return _FIELD_LABELS[key][1 if lang == "fi" else 0]
    words = key.replace("_", " ").strip() or "figure"
    if lang == "fi":
        words = {"count": "määrä", "spent": "käytetty", "usual": "tavallinen", "total": "yhteensä",
                 "difference": "ero", "over_by": "ylitys", "days_left": "päiviä jäljellä"}.get(key, words)
        return f"{tool.replace('_', ' ')}: {words}"
    title = tool.replace("_", " ").title()
    return f"{title}: {words}" if lang == "en" else f"{title}: {words}"


def figures(text: str, results: list, lang: str = "en") -> list[dict]:
    """Map each number written in an answer to its first matching tool field.

    ``results`` accepts either plain result dicts or ``{tool, result}`` records.
    Rounded speech keeps the source field and is marked as rounded.
    """
    paths = []
    for item in results:
        if isinstance(item, dict) and "result" in item:
            tool, obj = item.get("tool", "tool"), item.get("result")
        else:
            tool, obj = "tool", item
        paths.extend((tool, p, abs(v)) for p, v in _paths(obj))
    out = []
    for written, value in numbers_in_text(text, lang):
        match = next(((tool, path, source) for tool, path, source in paths
                      if abs(source - value) < 1e-9 or abs(round(source) - value) < 0.5), None)
        if not match:
            continue
        tool, path, source = match
        key = path.rsplit(".", 1)[-1].split("[")[0]
        label = _fallback_label(tool, path, lang)
        out.append({"text": written, "value": value, "tool": tool, "path": path,
                    "label": label, "rounded": abs(source - value) > 1e-9})
    return out
