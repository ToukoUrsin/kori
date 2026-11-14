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


# Where a figure came from, in words. Looked up by the end of its path in the tool result: two keys first, then one.
_FIELD_LABELS = {
    "amount": ("Safe to spend until payday", "Turvallista käyttää palkkapäivään asti"),
    "per_day": ("Safe pace a day", "Turvallinen päivätahti"),
    "this_week": ("Safe to spend this week", "Turvallista käyttää tällä viikolla"),
    "usual_per_day": ("Your usual everyday pace a day", "Tavallinen arjen päivätahtisi"),
    "days_to_payday": ("Days to payday", "Päiviä palkkapäivään"),
    "balance": ("Account balance", "Tilin saldo"),
    "cushion": ("Your cushion", "Puskurisi"),
    "per_day.before": ("Pace a day before the purchase", "Päivätahti ennen ostoa"),
    "per_day.after": ("Pace a day after the purchase", "Päivätahti oston jälkeen"),
    "safe.before": ("Safe to spend before the purchase", "Käyttövara ennen ostoa"),
    "safe.after": ("Safe to spend after the purchase", "Käyttövara oston jälkeen"),
    "short_by": ("Short by", "Jää vajaaksi"),
    "everyday_spent": ("Everyday spending in the last pay cycle", "Arjen menot viime palkkajaksolla"),
    "everyday_available": ("What the pay left for everyday", "Palkasta arkeen jäänyt raha"),
    "over_by": ("Over in the last pay cycle", "Ylitys viime palkkajaksolla"),
    "cycle.difference": ("Difference in the last pay cycle", "Ero viime palkkajaksolla"),
    "without_one_off.difference": ("The cycle without the one big purchase", "Jakso ilman yhtä isoa menoa"),
    "driver.spent": ("Spent on what did it", "Käytetty suurimpaan syyhyn"),
    "driver.usual": ("Your usual for it", "Tavallinen määräsi siihen"),
    "driver.above_usual": ("Above your usual", "Yli tavallisen"),
    "biggest.amount": ("The biggest single purchase", "Suurin yksittäinen meno"),
    "history.within": ("Pay cycles that held", "Pitäneet palkkajaksot"),
    "history.total": ("Pay cycles looked at", "Tarkastellut palkkajaksot"),
    "cap": ("The limit of your one thing", "Yhden asiasi raja"),
    "limit": ("The limit of your one thing", "Yhden asiasi raja"),
    "spent": ("Spent so far", "Käytetty tähän mennessä"),
    "left": ("Left on your limit", "Rajasta jäljellä"),
    "left_per_week": ("Left a week", "Jäljellä viikossa"),
    "lands_at_current_pace": ("Where it lands at this pace", "Mihin päädyt tällä tahdilla"),
    "pace_now": ("Your safe pace now", "Turvallinen tahtisi nyt"),
    "saving_monthly": ("Planned saving a month", "Suunniteltu säästö kuussa"),
    "days_left": ("Days left", "Päiviä jäljellä"),
    "days_in": ("Days into the pay cycle", "Päiviä palkkajaksoa kulunut"),
    "income": ("Income", "Tulot"),
    "fixed": ("Fixed musts", "Kiinteät pakolliset"),
    "surprise_reserve": ("Share for surprises", "Osuus yllätyksiin"),
    "planned_saving": ("Planned saving", "Suunniteltu säästö"),
    "total": ("Total of the matching transactions", "Osuvien tapahtumien summa"),
    "count": ("Number of transactions", "Tapahtumien määrä"),
    "average": ("Average per transaction", "Keskiarvo tapahtumaa kohden"),
    "per_year": ("In a year", "Vuodessa"),
    "monthly": ("A month", "Kuukaudessa"),
    "yearly": ("A year", "Vuodessa"),
    "result": ("Result of the calculation", "Laskun tulos"),
    "usual": ("Your usual", "Tavallinen määräsi"),
    "median": ("Typical for people like you", "Tyypillinen kaltaisillesi"),
    "percentile": ("Where you stand among people like you", "Sijoituksesi kaltaistesi joukossa"),
    "average_per_purchase": ("Average per purchase", "Keskiarvo ostosta kohden"),
    "held": ("Months the number held", "Kuukaudet, joina luku piti"),
    "missed": ("Months it missed", "Kuukaudet, joina se ei pitänyt"),
    "months_checked": ("Months checked", "Tarkastetut kuukaudet"),
    "months_number_would_have_held": ("Months the number would have held", "Kuukaudet, joina luku olisi pitänyt"),
    "months_stayed_within_number": ("Months you stayed within it", "Kuukaudet, joina pysyit siinä"),
    "share_held": ("Share of customers for whom the number held", "Osuus asiakkaista, joilla luku piti"),
}
_TOOL_NAMES = {
    "safe_to_spend": ("Safe to spend", "Turvallinen käyttövara"), "can_i_afford": ("Can I afford it", "Onko varaa"),
    "check_in": ("Your last pay cycle", "Viime palkkajaksosi"), "set_action": ("Your one thing", "Yksi asiasi"),
    "spending": ("Your transactions", "Tapahtumasi"), "small_purchases": ("Small purchases", "Pienet ostot"),
    "what_if": ("What-if on your usual month", "Entä jos tavallisessa kuussasi"), "track_record": ("Past months replayed", "Menneet kuukaudet uudelleen"),
    "balance_forecast": ("Balance until payday", "Saldo palkkapäivään asti"), "baskets": ("Your three baskets", "Kolme koriasi"),
    "compare_with_peers": ("People like you", "Kaltaisesi asiakkaat"), "calculate": ("A calculation on your numbers", "Lasku omilla luvuillasi"),
    "coach_notices": ("Worth knowing today", "Hyvä tietää tänään"), "safe_to_save": ("Safe to save", "Turvallista säästää"),
    "spender_profile": ("Your spending patterns", "Kulutustapasi"), "update_plan": ("Your plan", "Suunnitelmasi"),
    "explain": ("Your own numbers", "Omat lukusi"),
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


_DATE_AFTER = re.compile(r"\s*(?:st|nd|rd|th)?\s*(?:of\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", re.I)
_DATE_FI = re.compile(r"\.\d{1,2}\.")


def _label(path: str, lang: str) -> tuple[str, bool]:
    """Words for a field, and whether we really know it (so a known field wins when two fields hold the same value)."""
    keys = [k.split("[")[0] for k in path.split(".")]
    i = 1 if lang == "fi" else 0
    for cand in (".".join(keys[-2:]), keys[-1]):
        if cand in _FIELD_LABELS:
            return _FIELD_LABELS[cand][i], True
    words = keys[-1].replace("_", " ").strip() or ("figure" if lang == "en" else "luku")
    return words[:1].upper() + words[1:], False


def figures(text: str, results: list, lang: str = "en") -> list[dict]:
    """Where each number in an answer came from: the tool that computed it and the field, in words.

    ``results`` accepts either plain result dicts or ``{tool, result}`` records.
    A rounded figure keeps its source and is marked as rounded.
    """
    i = 1 if lang == "fi" else 0
    paths = []
    for item in results:
        if isinstance(item, dict) and "result" in item:
            tool, obj = item.get("tool", "tool"), item.get("result")
        else:
            tool, obj = "tool", item
        for pth, v in _paths(obj):
            label, known = _label(pth, lang)
            paths.append((tool, pth, abs(v), label, known))
    paths.sort(key=lambda x: not x[4])                 # stable: named fields first
    out, seen, pos = [], set(), 0
    for written, value in numbers_in_text(text, lang):
        at = text.find(written, pos)
        if at >= 0:
            pos = at + len(written)
        if at >= 0 and (_DATE_AFTER.match(text[pos:pos + 12]) or _DATE_FI.match(text[pos:pos + 4]) or
                        (lang == "fi" and re.search(r"\d\.$", text[max(0, at - 3):at]))):
            continue                                   # a day of the month, not a figure
        match = (next((x for x in paths if abs(x[2] - value) < 1e-9), None)
                 or next((x for x in paths if abs(round(x[2]) - value) < 0.5), None))
        if not match:
            continue
        tool, pth, source, label, _ = match
        if (pth, value) in seen:
            continue
        seen.add((pth, value))
        shown = written
        if at >= 0:                                    # keep the unit the answer used
            before, after = text[max(0, at - 1):at], text[pos:pos + 2]
            if before == "€":
                shown = "€" + written
            elif after.strip().startswith("€"):
                shown = written + " €"
            elif after.strip().startswith("%"):
                shown = written + ("%" if lang == "en" else " %")
        out.append({"text": shown, "value": value, "tool": tool, "source": _TOOL_NAMES.get(tool, (tool.replace("_", " "),) * 2)[i],
                    "path": pth, "label": label, "rounded": abs(source - value) > 1e-9})
    return out
