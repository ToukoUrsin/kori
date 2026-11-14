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
    "cycle.difference": ("Over or under in the last pay cycle", "Yli tai alle viime palkkajaksolla"),
    "without_one_off.difference": ("The cycle without the one big purchase", "Jakso ilman yhtä isoa menoa"),
    "driver.spent": ("The biggest cause, last pay cycle", "Suurin syy viime palkkajaksolla"),
    "driver.usual": ("The same thing in a usual month", "Sama asia tavallisena kuukautena"),
    "driver.above_usual": ("How far above your usual", "Kuinka paljon yli tavallisen"),
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
    # what-if
    "monthly_effect": ("Effect a month", "Vaikutus kuussa"),
    "yearly_effect": ("Effect over a year", "Vaikutus vuodessa"),
    "monthly_change": ("Change a month", "Muutos kuussa"),
    "from_monthly": ("What it is in your usual month", "Määrä tavallisena kuukautena"),
    "to_monthly": ("What it would be a month", "Määrä muutoksen jälkeen"),
    "total_effect_over_period": ("Effect over the whole period", "Vaikutus koko jaksolla"),
    "one_off_total": ("The one-off cost", "Kertameno"),
    "left_over.now": ("Left over in your usual month now", "Tavallisesta kuusta jää nyt"),
    "left_over.after": ("Left over after the change", "Jää muutoksen jälkeen"),
    "everyday_per_day.now": ("Everyday pace a day now", "Arjen päivätahti nyt"),
    "everyday_per_day.after": ("Everyday pace a day after the change", "Arjen päivätahti muutoksen jälkeen"),
    "per_day_change": ("Change in pace a day", "Päivätahdin muutos"),
    "per_day_before": ("Safe pace a day now", "Turvallinen päivätahti nyt"),
    "per_day_after": ("Safe pace a day after it", "Turvallinen päivätahti sen jälkeen"),
    "safe_to_spend.before": ("Safe to spend now", "Käyttövara nyt"),
    "safe_to_spend.after": ("Safe to spend after the change", "Käyttövara muutoksen jälkeen"),
    "safe_to_spend.change": ("Change in safe to spend", "Käyttövaran muutos"),
    "amount_after": ("Safe to spend after it", "Käyttövara sen jälkeen"),
    "reserve.available": ("Your surprise reserve", "Yllätysvarasi"),
    "reserve.used": ("Taken from the surprise reserve", "Yllätysvarasta käytetty"),
    "no_return": ("Set aside, with no return", "Sivuun laitettuna ilman tuottoa"),
    "example_4pct": ("Example at 4% a year", "Esimerkki 4 %:n vuosituotolla"),
    "pct": ("Percent of the change", "Muutoksen prosentti"),
    "per_cycle.now": ("Everyday money a pay cycle now", "Arjen raha palkkajaksossa nyt"),
    "per_cycle.after": ("Everyday money a pay cycle after the change", "Arjen raha palkkajaksossa muutoksen jälkeen"),
    "per_cycle.change": ("Change in everyday money a pay cycle", "Arjen rahan muutos palkkajaksossa"),
    "per_day.now": ("Pace a day now", "Päivätahti nyt"),
    "per_day.change": ("Change in pace a day", "Päivätahdin muutos"),
    "monthly.now": ("Everyday spending a month now", "Arjen menot kuussa nyt"),
    "monthly.after": ("Everyday spending a month after the change", "Arjen menot kuussa muutoksen jälkeen"),
    # affordability
    "from_safe_to_spend": ("Taken from safe to spend", "Käyttövarasta otettu"),
    "balance_before": ("Account balance before the purchase", "Tilin saldo ennen ostoa"),
    "balance_after": ("Account balance after the purchase", "Tilin saldo oston jälkeen"),
    "buffer_before": ("Buffer before the purchase", "Puskuri ennen ostoa"),
    "buffer_after": ("Buffer after the purchase", "Puskuri oston jälkeen"),
    "options.days": ("Days until payday", "Päiviä palkkapäivään"),
    "per_day_until_then": ("Pace a day until then", "Päivätahti siihen asti"),
    "per_day_after_buying_then": ("Pace a day if you buy it after payday", "Päivätahti, jos ostat palkkapäivän jälkeen"),
    "options.months": ("Months to set aside for it", "Kuukausia säästämiseen"),
    "options.monthly": ("To set aside a month for it", "Sivuun kuussa sitä varten"),
    "left_over_monthly": ("Left over in your usual month", "Tavallisesta kuusta jää yli"),
    # safe to spend, in detail
    "fixed_due": ("Bills still due before payday", "Ennen palkkapäivää erääntyvät laskut"),
    "cash.free": ("Free after bills still due", "Vapaana laskujen jälkeen"),
    "extra_days": ("Days pay has come late", "Päiviä, jotka palkka on myöhästynyt"),
    "late_pay.rate": ("How often pay came late", "Kuinka usein palkka myöhästyi"),
    "extra_needed": ("Kept back in case pay is late", "Varattu palkan myöhästymisen varalle"),
    "everyday_budget": ("Everyday money for this pay cycle", "Arjen raha tälle palkkajaksolle"),
    "everyday_monthly": ("Everyday spending in your usual month", "Arjen menot tavallisena kuukautena"),
    "budget.surprise": ("Share for surprises a month", "Osuus yllätyksiin kuussa"),
    "cycle_days": ("Days in the pay cycle", "Päiviä palkkajaksossa"),
    # the replay of past months
    "stayed_within": ("Months you stayed within the number", "Kuukaudet, joina pysyit luvussa"),
    "went_over": ("Months you went over it", "Kuukaudet, joina ylitit sen"),
    "customers": ("Customers in the replay", "Asiakkaita uudelleenlaskennassa"),
    "cases": ("Customer-months replayed", "Uudelleen lasketut asiakaskuukaudet"),
    "safe_held_pct": ("Share where the safe number held", "Osuus, jossa turvallinen luku piti"),
    "held_pct": ("Share where the safe number held", "Osuus, jossa turvallinen luku piti"),
    "balance_as_budget_held_pct": ("Share where the balance held as a budget", "Osuus, jossa saldo piti budjettina"),
    "balance_as_budget_pct": ("Share where the balance held as a budget", "Osuus, jossa saldo piti budjettina"),
    "months.safe": ("The safe number that month", "Sen kuun turvallinen luku"),
    "months.spent": ("Spent that month", "Sinä kuussa käytetty"),
    # people like you
    "group.size": ("People in your comparison group", "Vertailuryhmäsi koko"),
    "you": ("You", "Sinä"),
    "p25": ("Lower quarter of people like you", "Kaltaistesi alin neljännes"),
    "p75": ("Upper quarter of people like you", "Kaltaistesi ylin neljännes"),
    "diff": ("Difference from the typical", "Ero tyypilliseen"),
    "diff_pct": ("Difference from the typical, percent", "Ero tyypilliseen prosentteina"),
    "eur_month": ("Finnish households a month (Statistics Finland)", "Suomalaiset kotitaloudet kuussa (Tilastokeskus)"),
    # small purchases, forecast, baskets, saving
    "per_month": ("A month", "Kuukaudessa"),
    "share_of_everyday": ("Share of your everyday spending", "Osuus arjen menoistasi"),
    "under": ("Counted as small when under", "Pieneksi lasketaan alle"),
    "balance_today": ("Account balance today", "Tilin saldo tänään"),
    "at_usual_pace.before_payday": ("Balance the day before payday at your usual pace", "Saldo palkkapäivän aattona tavallisella tahdilla"),
    "at_safe_pace.before_payday": ("Balance the day before payday at the safe pace", "Saldo palkkapäivän aattona turvallisella tahdilla"),
    "per_day.safe": ("Safe pace a day", "Turvallinen päivätahti"),
    "expected_salary": ("Expected pay", "Odotettu palkka"),
    "vs_usual_pct": ("Compared with your usual, percent", "Verrattuna tavalliseen, prosenttia"),
    "share": ("Share of the total", "Osuus kokonaisuudesta"),
    "spend": ("Spent this month", "Käytetty tässä kuussa"),
    "usual_spend": ("Your usual month's spending", "Tavallisen kuusi menot"),
    "left_over": ("Left over", "Jää yli"),
    "saved": ("Saved", "Säästetty"),
    "monthly_capacity": ("What your usual month leaves to save", "Tavallisesta kuusta jää säästöön"),
    "extra_monthly": ("More you could set aside a month", "Lisää sivuun kuussa"),
    "months_covered": ("Months your buffer covers", "Kuukaudet, jotka puskurisi kattaa"),
    "target_months": ("Months a full buffer covers", "Täyden puskurin kuukaudet"),
    "buffer.target": ("A full buffer", "Täysi puskuri"),
    "buffer.gap": ("Missing from a full buffer", "Täydestä puskurista puuttuu"),
    "musts_monthly": ("Your musts a month", "Pakolliset menosi kuussa"),
    "period.days": ("Days in the period", "Päiviä jaksossa"),
    "score": ("Score out of 100", "Pisteet sadasta"),
    "fitness": ("Money fitness out of 100", "Rahakunto sadasta"),
}
# Numbers the engine wrote inside a sentence: named by the field that holds the sentence.
_SENTENCE_LABELS = {
    "why": ("The reason behind the one thing", "Yhden asian perustelu"),
    "worth": ("What the one thing is worth", "Mitä yksi asia tuo"),
    "would_have_held": ("How often it would have held", "Kuinka usein se olisi pitänyt"),
    "headline": ("Your last pay cycle, in words", "Viime palkkajaksosi sanoin"),
    "what_did_it": ("What did it last pay cycle", "Mikä sen aiheutti viime jaksolla"),
    "line": ("How the one thing is going", "Miten yksi asiasi etenee"),
    "text": ("In the calculation's own words", "Laskelman omin sanoin"),
    "body": ("Worth knowing today", "Hyvä tietää tänään"),
    "notices.title": ("Worth knowing today", "Hyvä tietää tänään"),
    "then_the_thing_is": ("What the other answer would set", "Mitä toinen vastaus asettaisi"),
    "other_ways.title": ("Another way to do it", "Toinen tapa"),
    "other_ways.why": ("Another way to do it", "Toinen tapa"),
    "thing.title": ("Your one thing", "Yksi asiasi"),
    "note": ("In the calculation's own words", "Laskelman omin sanoin"),
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


def _strings(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _strings(v, f"{path}[{i}]")


_IN_WORDS = ("In the calculation's own words", "Laskelman omin sanoin")
_ASKED = (("The amount you asked about", "Kysymäsi summa"), ("Your question", "Kysymyksesi"))


_COUNT_KEYS = {"days", "days_left", "days_in", "days_to_payday", "count", "held", "missed", "months", "months_checked",
               "months_number_would_have_held", "months_stayed_within_number", "stayed_within", "went_over", "customers", "cases",
               "size", "extra_days", "week_days", "cycle_days", "years", "target_months", "months_covered",
               "below_zero_when_within", "below_zero_when_over", "pay_late_months", "score", "fitness"}
_COUNT_KEYS2 = {"history.total", "history.within", "history.over", "replay.held", "replay.total"}


def _kind(path: str) -> str:
    """What a field holds: a share ("pct"), a count of days or months ("count"), or money."""
    keys = [k.split("[")[0] for k in path.split(".")]
    last = keys[-1]
    if "pct" in last or "share" in last or last in ("rate", "percentile", "pace_ratio"):
        return "pct"
    if last in _COUNT_KEYS or ".".join(keys[-2:]) in _COUNT_KEYS2:
        return "count"
    return "money"


def figures(text: str, results: list, lang: str = "en", question: str = "") -> list[dict]:
    """Where each number in an answer came from: the tool that computed it and the field, in words.

    ``results`` accepts either plain result dicts or ``{tool, result}`` records. An amount is matched to a money
    field, a percentage to a share, a bare number to a count of days or months, so a figure is never explained by
    a field of another kind that happens to hold the same value. A rounded figure keeps its source and is marked as
    rounded. An amount the engine gave inside a sentence, or one the user said in the question, is listed as that.
    """
    i = 1 if lang == "fi" else 0
    paths = []
    worded = []                                        # amounts the engine wrote inside its own sentences
    for item in results:
        if isinstance(item, dict) and "result" in item:
            tool, obj = item.get("tool", "tool"), item.get("result")
        else:
            tool, obj = "tool", item
        for pth, v in _paths(obj):
            label, known = _label(pth, lang)
            kind = _kind(pth)
            paths.append((tool, pth, abs(v), label, known, kind))
            if kind == "pct" and 0 < abs(v) <= 1.5:      # a share stored as 0.35 is said as 35%
                paths.append((tool, pth, round(abs(v) * 100, 1), label, known, kind))
        for pth, sentence in _strings(obj):
            for l in ("en", "fi"):
                for _, v in numbers_in_text(sentence, l):
                    worded.append((tool, pth, v))
    paths.sort(key=lambda x: not x[4])                 # stable: named fields first
    asked = {v for l in ("en", "fi") for _, v in numbers_in_text(question or "", l)}
    src_name = lambda tool: _TOOL_NAMES.get(tool, (tool.replace("_", " "),) * 2)[i]
    out, seen, pos = [], set(), 0
    for written, value in numbers_in_text(text, lang):
        at = text.find(written, pos)
        if at >= 0:
            pos = at + len(written)
        if at >= 0 and (_DATE_AFTER.match(text[pos:pos + 12]) or _DATE_FI.match(text[pos:pos + 4]) or
                        (lang == "fi" and re.search(r"\d\.$", text[max(0, at - 3):at]))):
            continue                                   # a day of the month, not a figure
        unit, shown = "count", written                 # the unit the answer used, also when it was spoken ("520 euros")
        if at >= 0:
            before, after = text[max(0, at - 1):at], text[pos:pos + 10].lstrip("* ").lower()
            if before == "€" or (lang == "en" and after.startswith("euro")):
                unit, shown = "money", "€" + written
            elif after.startswith("€") or (lang == "fi" and after.startswith("euro")):
                unit, shown = "money", written + " €"
            elif after.startswith("%") or after.startswith(("percent", "prosent")):
                unit, shown = "pct", written + ("%" if lang == "en" else " %")
        mine = [x for x in paths if x[5] == unit]
        match = (next((x for x in mine if abs(x[2] - value) < 1e-9), None)
                 or next((x for x in mine if abs(round(x[2]) - value) < 0.5), None))
        if unit == "money" and value in asked and not (match and abs(match[2] - value) < 1e-9 and match[4] and "amount" not in match[1]):
            row = {"tool": "question", "source": _ASKED[1][i], "path": "question", "label": _ASKED[0][i], "rounded": False}
        elif match:
            tool, pth, source, label, _, _ = match
            row = {"tool": tool, "source": src_name(tool), "path": pth, "label": label, "rounded": abs(source - value) > 1e-9}
        elif unit == "count":
            continue                                   # a bare number with no count behind it: not listed
        else:
            w = (next((x for x in worded if abs(x[2] - value) < 1e-9), None)
                 or next((x for x in worded if abs(round(x[2]) - value) < 0.5), None))
            if not w:
                continue
            ks = [k.split("[")[0] for k in w[1].split(".")]
            words = _SENTENCE_LABELS.get(".".join(ks[-2:])) or _SENTENCE_LABELS.get(ks[-1]) or _IN_WORDS
            row = {"tool": w[0], "source": src_name(w[0]), "path": w[1], "label": words[i],
                   "rounded": abs(w[2] - value) > 1e-9}
        if (row["path"], value) in seen:
            continue
        seen.add((row["path"], value))
        out.append({"text": shown, "value": value, **row})
    return out
