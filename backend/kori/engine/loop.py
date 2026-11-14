"""The habit loop: look back at the last pay cycle, pick one thing for this one, track it.

Plain code on the same transactions and the same definitions as ``Money.safe``. No model, no HTTP.

- ``check_in``   how the last complete pay cycle went, and what did it (a habit or one big purchase)
- ``suggest``    exactly one reversible thing for this cycle, sized from the person's own numbers
- ``commit`` / ``change`` / ``drop``   keep it in the per-device state (and undo it)
- ``progress``   where it stands today, from the real transactions since it was set
"""
from __future__ import annotations

import time
from datetime import date, timedelta

from ..taxonomy import CATEGORIES, EVERYDAY, cat_label
from ..wording import is_pensioner
from .core import DAYS_PER_MONTH, Money, r2
from .insights import eur, whole
from .query import fmt_day

# everyday categories a person can put on hold for a couple of weeks without going hungry or missing work
PAUSABLE = ("Restaurants", "Lifestyle", "Entertainment", "Travel")
KINDS = ("cap_category", "pause_category", "daily_pace", "set_aside")
MONTHS = {"en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
          "fi": ["tammi", "helmi", "maalis", "huhti", "touko", "kesä", "heinä", "elo", "syys", "loka", "marras", "joulu"]}
# Finnish needs the category in the right case; a table is more honest than guessing endings
FI_SUBJECT = {"Groceries": "ruokaostokset", "Restaurants": "ravintolat", "Transportation": "liikkuminen", "Entertainment": "huvit",
              "Lifestyle": "ostokset", "Travel": "matkat"}
FI_ILLATIVE = {"Groceries": "ruokaostoksiin", "Restaurants": "ravintoloihin", "Transportation": "liikkumiseen",
               "Entertainment": "huveihin", "Lifestyle": "ostoksiin", "Travel": "matkoihin"}
# a purchase with no shop name, in words
ONE = {"Groceries": ("a grocery shop", "ruokaostos"), "Restaurants": ("a restaurant bill", "ravintolalasku"),
       "Transportation": ("a transport cost", "liikkumismeno"), "Entertainment": ("a ticket or outing", "huvimeno"),
       "Lifestyle": ("a purchase", "ostos"), "Travel": ("a trip", "matka")}
MIN_USUAL_FOR_CAP = 60.0      # a cap on something you barely spend on teaches nothing
FI_PAUSE = {"Restaurants": "ravintolat", "Lifestyle": "ostokset", "Entertainment": "huvit", "Travel": "matkat"}


class _W:
    """Words for this person in this language."""

    def __init__(self, m: Money):
        self.lang = m.prefs.lang
        self.pension = is_pensioner(m.customer.age)

    def L(self, en: str, fi: str) -> str:
        return en if self.lang == "en" else fi

    def E(self, v: float, cents: bool = False) -> str:
        return eur(v, self.lang, cents)

    def day(self, d: date) -> str:
        return fmt_day(d, self.lang)

    @property
    def cycle(self) -> str:
        return self.L("pension cycle" if self.pension else "pay cycle", "eläkejakso" if self.pension else "palkkajakso")

    @property
    def cycles(self) -> str:
        return self.L("pension cycles" if self.pension else "pay cycles", "eläkejaksosta" if self.pension else "palkkajaksosta")

    @property
    def cycle_on(self) -> str:       # "on the last cycle"
        return self.L(self.cycle, "eläkejaksolla" if self.pension else "palkkajaksolla")

    @property
    def pay(self) -> str:
        return self.L("pension" if self.pension else "pay", "eläke" if self.pension else "palkka")

    @property
    def from_pay(self) -> str:
        return self.L("your " + self.pay, "eläkkeestä" if self.pension else "palkasta")

    @property
    def payday(self) -> str:
        return self.L("pension day" if self.pension else "payday", "eläkepäivä" if self.pension else "palkkapäivä")

    @property
    def until_payday(self) -> str:
        return self.L("until " + self.payday, ("eläkepäivään" if self.pension else "palkkapäivään") + " asti")

    def cat(self, c: str) -> str:
        return cat_label(c, self.lang)

    def cat_low(self, c: str) -> str:
        return self.L(cat_label(c, "en").lower(), FI_SUBJECT.get(c, cat_label(c, "fi").lower()))


# ------------------------------------------------------------------ cycles
def _cycles(m: Money, n: int = 6) -> list[tuple[date, date]]:
    """The last n complete pay cycles as (payday, next payday). The running cycle is not one of them."""
    pays = sorted(set(m.salaries["date"].tolist()))
    out = [(pays[i], pays[i + 1]) for i in range(len(pays) - 1) if pays[i + 1] <= m.today and pays[i] < pays[i + 1]]
    return out[-n:]


def _purchase(r) -> dict:
    return {"date": r.date.isoformat(), "merchant": r.merchant if isinstance(r.merchant, str) else None,
            "amount": r2(r.spend), "category": r.category}


def _cycle_row(m: Money, start: date, end: date, detail: bool = True) -> dict:
    """One pay cycle: what the pay left for everyday, what everyday took, and what did most of it."""
    d = m.df[(m.df["date"] >= start) & (m.df["date"] < end)]
    days = max(1, (end - start).days)
    income = r2(d[d["category"].isin(["Salary", "Other Income"])]["amount"].sum())
    if not m.prefs.other_bank_linked:
        income = r2(income + d[d["category"] == "Salary Sweep"]["amount"].sum())     # sweeps are negative
    fixed = r2(d[d["basket"] == "fixed"]["spend"].sum())
    surprise = r2(m.usual["surprise"] * days / DAYS_PER_MONTH)
    saving = r2(m.savings_plan * days / DAYS_PER_MONTH)
    available = r2(max(0.0, income - fixed - surprise - saving))
    everyday = d[d["basket"] == EVERYDAY]
    spent = r2(everyday["spend"].sum())
    row = {"start": start.isoformat(), "end": end.isoformat(), "last_day": (end - timedelta(days=1)).isoformat(), "days": days,
           "income": income, "fixed": fixed, "surprise_reserve": surprise, "planned_saving": saving,
           "everyday_available": available, "everyday_spent": spent, "within": bool(spent <= available + 0.005),
           "difference": r2(abs(available - spent)), "over_by": r2(max(0.0, spent - available)),
           "days_below_zero": int(d[d["balance"] < 0]["date"].nunique())}
    if not detail:
        return row
    # what did it: the everyday category furthest above its own usual, scaled to the length of this cycle
    cats = []
    for c, meta in CATEGORIES.items():
        cd = everyday[everyday["category"] == c]
        if not len(cd):
            continue
        amount = r2(cd["spend"].sum())
        usual = r2(m.usual["categories"].get(c, 0.0) * days / DAYS_PER_MONTH)
        top = cd.sort_values(["spend", "date"], ascending=[False, True])
        biggest = _purchase(next(top.itertuples()))
        above = r2(max(0.0, amount - usual))
        # one big purchase is a different story from many small ones
        one_off = bool(above > 5 and biggest["amount"] >= 0.6 * above and biggest["amount"] >= 0.5 * amount and biggest["amount"] >= 150)
        cats.append({"category": c, "label": cat_label(c, m.prefs.lang), "spent": amount, "usual": usual, "above_usual": above,
                     "count": int(len(cd)), "kind": "one_off" if one_off else "habit", "biggest": biggest,
                     "purchases": [_purchase(r) for r in top.head(3).itertuples()]})
    cats.sort(key=lambda x: (-x["above_usual"], x["category"]))
    drivers = [c for c in cats if c["above_usual"] > 5]
    row["driver"] = drivers[0] if drivers else None
    row["drivers"] = drivers[:3]
    if row["driver"] and row["driver"]["kind"] == "one_off":
        rest = r2(spent - row["driver"]["biggest"]["amount"])
        row["without_one_off"] = {"everyday_spent": rest, "within": bool(rest <= available + 0.005),
                                  "difference": r2(abs(available - rest))}
    else:
        row["without_one_off"] = None
    return row


def _period(w: _W, row: dict) -> str:
    a, b = date.fromisoformat(row["start"]), date.fromisoformat(row["last_day"])
    return w.L(f"{w.day(a)} to {w.day(b)}", f"{w.day(a)}–{w.day(b)}")


def _what(w: _W, p: dict) -> str:
    """A purchase in words: the shop when we know it, else the kind of thing."""
    if p["merchant"]:
        return p["merchant"]
    en, fi = ONE.get(p["category"], ("a purchase", "ostos"))
    return w.L(en, fi)


def check_in(m: Money) -> dict:
    """How the last complete pay cycle went."""
    w = _W(m)
    L, E = w.L, w.E
    cycles = _cycles(m, 6)
    if not cycles:
        return {"available": False, "headline": L("I need one complete pay cycle before I can look back.",
                                                  "Tarvitsen yhden kokonaisen palkkajakson, ennen kuin voin katsoa taaksepäin."),
                "cycle": None, "history": {"cycles": [], "total": 0, "within": 0, "over": 0}, "partial_view": bool(m.partial_view)}
    row = _cycle_row(m, *cycles[-1])
    rows = [_cycle_row(m, *x, detail=False) for x in cycles]
    for r in rows:
        r["label"] = _period(w, r)
    history = {"cycles": rows, "total": len(rows), "within": sum(1 for x in rows if x["within"]),
               "over": sum(1 for x in rows if not x["within"])}
    row["label"] = _period(w, row)
    partial = bool(m.partial_view and not m.linked_view)
    drv, wo = row["driver"], row["without_one_off"]

    if partial:
        headline = L(f"On this account, everyday spending was {E(row['everyday_spent'])} last {w.cycle}. Without the account "
                     f"your salary goes to, I cannot say whether the cycle held.",
                     f"Tältä tililtä arkeen meni viime {w.cycle_on} {E(row['everyday_spent'])}. Ilman tiliä, jolle palkkasi "
                     f"menee, en voi sanoa, pitikö jakso.")
    elif row["within"]:
        headline = L(f"Last {w.cycle} held: {E(row['everyday_spent'])} went to everyday, {E(row['difference'])} less than {w.from_pay} "
                     f"left room for.",
                     f"Viime {w.cycle} piti: arkeen meni {E(row['everyday_spent'])}, eli {E(row['difference'])} vähemmän kuin "
                     f"{w.from_pay} jäi arkeen.")
    else:
        headline = L(f"Last {w.cycle} went {E(row['over_by'])} over: {E(row['everyday_spent'])} went to everyday, and {w.from_pay} left "
                     f"room for {E(row['everyday_available'])}.",
                     f"Viime {w.cycle} meni {E(row['over_by'])} yli: arkeen meni {E(row['everyday_spent'])}, ja {w.from_pay} jäi arkeen "
                     f"{E(row['everyday_available'])}.")

    driver_line = None
    if drv and not partial:
        if drv["kind"] == "one_off":
            b = drv["biggest"]
            what = _what(w, b)
            when = w.day(date.fromisoformat(b["date"]))
            if row["within"]:
                driver_line = L(f"The biggest single thing was {what}: {E(b['amount'])} on {when}.",
                                f"Suurin yksittäinen meno oli {what} {when}, {E(b['amount'])}.")
            elif wo["within"]:
                driver_line = L(f"One purchase did it: {what}, {E(b['amount'])} on {when}. Without it the cycle was {E(wo['difference'])} "
                                f"under.",
                                f"Syy oli yksi iso meno: {what} {when}, {E(b['amount'])}. Ilman sitä jakso olisi jäänyt "
                                f"{E(wo['difference'])} alle.")
            else:
                driver_line = L(f"The biggest piece was one purchase: {what}, {E(b['amount'])} on {when}. Without it the cycle was still "
                                f"{E(wo['difference'])} over.",
                                f"Suurin osa oli yksi iso meno: {what} {when}, {E(b['amount'])}. Ilman sitäkin jakso olisi mennyt "
                                f"{E(wo['difference'])} yli.")
        else:
            driver_line = L(f"{w.cat(drv['category'])} did most of it: {E(drv['spent'])} against your usual {E(drv['usual'])}.",
                            f"Eniten vaikuttivat {w.cat_low(drv['category'])}: {E(drv['spent'])}, kun tavallisesti {E(drv['usual'])}.")
            if row["within"]:
                driver_line = L(f"{w.cat(drv['category'])} ran above your usual: {E(drv['spent'])} against {E(drv['usual'])}.",
                                f"{w.cat(drv['category'])} ylittivät tavallisen: {E(drv['spent'])}, kun tavallisesti {E(drv['usual'])}.")
    history_line = None if partial else L(f"{history['within']} of your last {history['total']} {w.cycles} held.",
                                          f"Viimeisestä {history['total']} {w.cycles} {history['within']} piti.")
    note = (L("I can compare spending on this account, but not your whole month: your salary moves to another bank.",
              "Voin verrata tämän tilin menoja, mutta en koko kuukauttasi: palkkasi siirtyy toiseen pankkiin.") if partial else
            L("Counted from this account: the pay that came in, the bills that left, a share for surprises, and everyday spending.",
              "Laskettu tältä tililtä: tullut palkka, lähteneet laskut, osuus yllätyksiin ja arjen menot."))
    out = {"available": True, "cycle": row, "history": history, "headline": headline, "driver_line": driver_line,
           "history_line": history_line, "partial_view": partial, "note": note,
           "can_judge": {"everyday_spending": True, "full_income": not partial, "whole_financial_picture": not partial}}
    if m.linked_view:
        out["linked_view"] = m.linked_view
        out["note"] = L("An estimate from the simulated link to your other bank in this demo: the salary that moves out is counted as yours.",
                        "Arvio tämän demon simuloidusta linkistä toiseen pankkiisi: pois siirtyvä palkka lasketaan sinun rahaksesi.")
    return out


# -------------------------------------------------------------- one thing
def _say(v: float, lang: str) -> str:
    """An amount as it is said aloud."""
    n = whole(v)
    return f"{n:,} euros" if lang == "en" else f"{n} euroa"


def _round_down(v: float, step: float) -> float:
    return r2(max(step, (v // step) * step))


def title_of(m: Money, a: dict) -> str:
    """The thing in a few words: "Groceries under €530"."""
    w = _W(m)
    L, E = w.L, w.E
    k, t = a.get("kind"), a.get("target")
    if k == "cap_category":
        return L(f"{w.cat(t)} under {E(a.get('cap') or 0)}", f"{w.cat(t)} alle {E(a.get('cap') or 0)}")
    if k == "pause_category":
        return L(f"No {w.cat_low(t)} {w.until_payday}", f"{FI_PAUSE.get(t, w.cat(t)).capitalize()} tauolle {w.until_payday}")
    if k == "daily_pace":
        return L(f"{E(a.get('cap') or 0, True)} a day {w.until_payday}", f"{E(a.get('cap') or 0, True)} päivässä {w.until_payday}")
    if k == "set_aside":
        if t in CATEGORIES:
            return L(f"Set aside {E(a.get('amount') or 0)} a month for {w.cat_low(t)}",
                     f"Siirrä {E(a.get('amount') or 0)} kuussa sivuun: {w.cat_low(t)}")
        return L(f"Set aside {E(a.get('amount') or 0)} more a month", f"Siirrä {E(a.get('amount') or 0)} enemmän säästöön kuussa")
    return L("Nothing to set yet", "Ei vielä asetettavaa")


def _month_replay(m: Money, w: _W, category: str, cap: float) -> dict:
    """Would this cap have held in each of the last six complete calendar months? (Months, because pay cycles vary in length.)"""
    rows = []
    for k in m.last_full_months(6):
        total = r2(float(m.monthly.loc[k, "cat:" + category]))
        rows.append({"month": k, "label": MONTHS[w.lang][int(k[5:7]) - 1], "total": total, "held": bool(total <= cap + 0.005)})
    held = sum(1 for x in rows if x["held"])
    text = w.L(f"In {held} of the last {len(rows)} months {w.cat_low(category)} stayed under {w.E(cap)}.",
               f"Viimeisestä {len(rows)} kuukaudesta {held}:ssa {w.cat_low(category)} pysyivät alle {w.E(cap)}.") if rows else None
    return {"unit": "month", "held": held, "total": len(rows), "rows": rows, "text": text}


def _make(m: Money, kind: str, target: str | None, cap: float | None = None, amount: float | None = None, ci: dict | None = None) -> dict:
    """A thing with its reasons: why, what it is worth, and how realistic it is. Every figure from the transactions."""
    w = _W(m)
    L, E = w.L, w.E
    ci = ci or check_in(m)
    row = ci.get("cycle") or {}
    days = m.days_to_payday
    a = {"kind": kind, "target": target, "target_label": w.cat(target) if target in CATEGORIES else None,
         "cap": r2(cap) if cap is not None else None, "amount": r2(amount) if amount is not None else None,
         "until": m.next_payday.isoformat(), "until_label": w.day(m.next_payday), "days_left": days,
         "cycle": {"start": m.cycle_start.isoformat(), "end": m.next_payday.isoformat()},
         "why": None, "worth": None, "replay": None,
         "reversible": L("You can change it or drop it any time.", "Voit muuttaa sitä tai luopua siitä milloin vain.")}
    a["title"] = title_of(m, a)
    cat = next((c for c in (row.get("drivers") or []) if c["category"] == target), None)
    usual_month = r2(m.usual["categories"].get(target, 0.0)) if target in CATEGORIES else None

    if kind == "cap_category":
        if cat:
            a["why"] = L(f"Last {w.cycle} {w.cat_low(target)} came to {E(cat['spent'])}. Your usual is {E(cat['usual'])}.",
                         f"Viime {w.cycle_on} {FI_ILLATIVE.get(target, w.cat_low(target))} meni {E(cat['spent'])}. Tavallisesti "
                         f"{E(cat['usual'])}.")
            back = r2(max(0.0, cat["spent"] - float(cap or 0)))
            if back > 0:
                over = row.get("over_by") or 0.0
                a["worth"] = {"amount": back, "of_overshoot": over or None,
                              "text": (L(f"Had it held last cycle, {E(back)} of the {E(over)} would not have happened.",
                                         f"Jos raja olisi pitänyt viime jaksolla, {E(over)} ylityksestä {E(back)} olisi jäänyt pois.")
                                       if over > 0 else
                                       L(f"Had it held last cycle, {E(back)} more would have been left.",
                                         f"Jos raja olisi pitänyt viime jaksolla, {E(back)} enemmän olisi jäänyt."))}
        else:
            a["why"] = L(f"Your usual for {w.cat_low(target)} is {E(usual_month or 0)} a month.",
                         f"Tavallisesti {FI_ILLATIVE.get(target, w.cat_low(target))} menee {E(usual_month or 0)} kuussa.")
        a["replay"] = _month_replay(m, w, target, float(cap or 0))
    elif kind == "pause_category":
        at_usual = r2((usual_month or 0.0) * days / DAYS_PER_MONTH)
        spent_txt = (L(f" {w.cat(target)} took {E(cat['spent'])} last cycle, against a usual {E(cat['usual'])}.",
                       f" {FI_ILLATIVE.get(target, w.cat_low(target)).capitalize()} meni viime jaksolla {E(cat['spent'])}, kun tavallisesti "
                       f"{E(cat['usual'])}.") if cat else "")
        a["why"] = L(f"Your everyday money for this {w.cycle} is used up.{spent_txt}",
                     f"Tämän {'eläkejakson' if w.pension else 'palkkajakson'} arkiraha on käytetty.{spent_txt}")
        if at_usual > 0:
            a["worth"] = {"amount": at_usual, "of_overshoot": None,
                          "text": L(f"At your usual pace those {days} days would cost about {E(at_usual)}.",
                                    f"Tavallisella tahdillasi nämä {days} päivää maksaisivat noin {E(at_usual)}.")}
        a["cap"] = 0.0
    elif kind == "daily_pace":
        s = m.safe
        a["cap"] = r2(s["per_day"]) if cap is None else r2(cap)
        a["title"] = title_of(m, a)
        a["why"] = L(f"That is your safe pace: {E(s['amount'])} for {days} days. Your usual pace is {E(s['usual_per_day'], True)} a day.",
                     f"Se on turvallinen tahtisi: {E(s['amount'])} {days} päivälle. Tavallinen tahtisi on {E(s['usual_per_day'], True)} "
                     f"päivässä.")
        drv, wo = row.get("driver"), row.get("without_one_off")
        if drv and drv["kind"] == "one_off" and wo and wo["within"] and not row.get("within"):
            a["why"] += L(" Last cycle went over because of one purchase, not your everyday habits, so the pace is what matters now.",
                          " Viime jakso ylittyi yhden ison menon takia, ei arjen tapojen, joten nyt ratkaisee tahti.")
    elif kind == "set_aside" and target in CATEGORIES:
        b = (cat or {}).get("biggest")
        what = _what(w, b) if b else w.cat_low(target)
        a["why"] = (L(f"Last {w.cycle} {what} cost {E(b['amount'])} in one go. Spread over a year that is about {E(amount or 0)} a month, "
                      f"set aside before it comes.",
                      f"Viime {w.cycle_on} {what} maksoi kerralla {E(b['amount'])}. Vuodelle jaettuna se on noin {E(amount or 0)} kuussa, "
                      f"sivuun ennen kuin se tulee.") if b else
                    L(f"A reserve for {w.cat_low(target)}, set aside before the bill comes.",
                      f"Vara ({w.cat_low(target)}), sivuun ennen kuin lasku tulee."))
        a["worth"] = {"amount": r2(float(amount or 0) * 12), "of_overshoot": None,
                      "text": L(f"In a year that is {E(float(amount or 0) * 12)} waiting. The next one does not land on one {w.cycle}.",
                                f"Vuodessa sivussa on {E(float(amount or 0) * 12)}. Seuraava ei kaadu yhden jakson päälle.")}
        a["saving_now"] = r2(m.savings_plan)
        a["saving_after"] = r2(m.savings_plan + float(amount or 0))
    elif kind == "set_aside":
        rows = (ci.get("history") or {}).get("cycles") or []
        ok = sum(1 for r in rows if r["within"] and r["difference"] >= float(amount or 0) - 0.005)
        # the look back already says what last cycle left: the reason to believe the amount is how often it was there
        a["why"] = (L(f"In {ok} of your last {len(rows)} {w.cycles} at least {E(amount or 0)} was left over.",
                      f"Viimeisestä {len(rows)} {w.cycles} {ok}:ssa jäi vähintään {E(amount or 0)} yli.") if ok else
                    L(f"Last {w.cycle} left {E(row.get('difference') or 0)} of your everyday money unspent.",
                      f"Viime {w.cycle_on} arkirahasta jäi käyttämättä {E(row.get('difference') or 0)}."))
        a["worth"] = {"amount": r2(float(amount or 0) * 12), "of_overshoot": None,
                      "text": L(f"That is {E(float(amount or 0) * 12)} in a year. It is a plan for your own money, not investment advice.",
                                f"Se on {E(float(amount or 0) * 12)} vuodessa. Tämä on suunnitelma omille rahoillesi, ei sijoitusneuvo.")}
        a["replay"] = {"unit": "cycle", "held": ok, "total": len(rows),
                       "rows": [{"label": r["label"], "total": r["difference"] if r["within"] else r2(-r["over_by"]),
                                 "held": bool(r["within"] and r["difference"] >= float(amount or 0) - 0.005)} for r in rows],
                       "text": L(f"In {ok} of your last {len(rows)} {w.cycles} at least {E(amount or 0)} was left over.",
                                 f"Viimeisestä {len(rows)} {w.cycles} {ok}:ssa jäi vähintään {E(amount or 0)} yli.")}
        a["saving_now"] = r2(m.savings_plan)
        a["saving_after"] = r2(m.savings_plan + float(amount or 0))
    return a


def suggest(m: Money) -> dict:
    """Exactly one thing for this cycle, picked by rule from this person's own data, with one or two other ways to do it."""
    w = _W(m)
    L, E = w.L, w.E
    ci = check_in(m)
    row = ci.get("cycle")
    none = {"kind": "none", "target": None, "target_label": None, "cap": None, "amount": None, "title": title_of(m, {}),
            "worth": None, "replay": None, "alternatives": [], "question": None, "next": None}
    if not row:
        return {**none, "why": ci["headline"]}
    if ci["partial_view"]:
        return {**none, "next": "link_other_bank",
                "why": L("Your salary moves to another bank, so any limit I set would be a guess. Link the other account first.",
                         "Palkkasi siirtyy toiseen pankkiin, joten mikä tahansa raja olisi arvaus. Yhdistä ensin toinen tili.")}
    s = m.safe
    status = s["status"]
    drivers = row.get("drivers") or []
    usual = m.usual["categories"]
    habits = [c for c in drivers if c["kind"] == "habit" and usual.get(c["category"], 0.0) >= MIN_USUAL_FOR_CAP]
    biggest_usual = max((c for c in CATEGORIES if CATEGORIES[c]["basket"] == EVERYDAY), key=lambda c: usual.get(c, 0.0))
    question = None

    def cap_for(c: dict, gentle: bool = False) -> dict:
        base = r2(usual.get(c["category"], 0.0))                # the usual month, which is also what the replay is measured on
        cap = _round_down(base if not gentle else (base + c["spent"]) / 2, 10.0)
        return _make(m, "cap_category", c["category"], cap=cap, ci=ci)

    pace = _make(m, "daily_pace", "everyday", ci=ci)
    options: list[dict] = []

    if status == "empty" or s["amount"] <= 0:
        # nothing safe left: a limit on the total is beside the point, so put one want on hold until the money comes
        pausable = [c for c in drivers if c["category"] in PAUSABLE] or \
                   [{"category": c} for c in sorted(PAUSABLE, key=lambda x: -usual.get(x, 0.0)) if usual.get(c, 0.0) > 0]
        options = [_make(m, "pause_category", c["category"], ci=ci) for c in pausable[:2]]
    elif not row["within"]:
        wo = row["without_one_off"]
        drv = row["driver"]
        if habits and not (wo and wo["within"]):
            h = habits[0]
            options = [cap_for(h), cap_for(h, gentle=True), pace]
            question = {"text": L(f"{w.cat(h['category'])} came to {E(h['spent'])} against your usual {E(h['usual'])}. Was last "
                                  f"{w.cycle} unusual, or is this the new normal?",
                                  f"{FI_ILLATIVE.get(h['category'], w.cat_low(h['category'])).capitalize()} meni {E(h['spent'])}, kun "
                                  f"tavallisesti {E(h['usual'])}. Oliko viime jakso poikkeus vai uusi tavallinen?"),
                        "short": L(f"Was last {w.cycle} unusual, or is this the new normal?",
                                   "Oliko viime jakso poikkeus vai uusi tavallinen?"),
                        "spoken": L(f"Last {w.cycle} went {_say(row['over_by'], 'en')} over, mostly on {w.cat_low(h['category'])}. "
                                    f"Was that unusual, or is this the new normal?",
                                    f"Viime {w.cycle} meni {_say(row['over_by'], 'fi')} yli, eniten "
                                    f"{FI_ILLATIVE.get(h['category'], w.cat_low(h['category']))}. Oliko se poikkeus vai uusi tavallinen?"),
                        "answers": [{"key": "unusual", "label": L("It was unusual", "Se oli poikkeus"), "pick": 0},
                                    {"key": "new_normal", "label": L("It is the new normal", "Se on uusi tavallinen"), "pick": 1}]}
        else:
            # one big purchase did it: the habits are fine. The pace is what matters now; a reserve is what stops the next one
            b = drv["biggest"]
            reserve = _make(m, "set_aside", drv["category"], amount=max(10.0, round(b["amount"] / 120) * 10.0), ci=ci)
            options = [pace, reserve]
            what = _what(w, b)
            question = {"text": L(f"{what[:1].upper() + what[1:]} for {E(b['amount'])} did it. Will something like it come again "
                                  f"within a year?",
                                  f"Syy oli {what}, {E(b['amount'])}. Tuleeko samanlainen meno uudestaan vuoden sisällä?"),
                        "short": L("Will something like it come again within a year?",
                                   "Tuleeko samanlainen meno uudestaan vuoden sisällä?"),
                        "spoken": L(f"Last {w.cycle} went {_say(row['over_by'], 'en')} over because of one purchase: {what}, "
                                    f"{_say(b['amount'], 'en')}. Will something like it come again within a year?",
                                    f"Viime {w.cycle} meni {_say(row['over_by'], 'fi')} yli yhden menon takia: {what}, "
                                    f"{_say(b['amount'], 'fi')}. Tuleeko samanlainen meno uudestaan vuoden sisällä?"),
                        "answers": [{"key": "one_off", "label": L("No, it was a one-off", "Ei, se oli kertameno"), "pick": 0},
                                    {"key": "again", "label": L("Yes, probably", "Kyllä, luultavasti"), "pick": 1}]}
    else:
        spare = [r["difference"] for r in ci["history"]["cycles"] if r["within"]]
        if status == "comfortable" and m.usual["left_over"] >= 50 and len(spare) >= 3:
            amount = _round_down(min(0.5 * min(spare), 0.5 * m.usual["left_over"], 500.0), 10.0 if min(spare) < 400 else 50.0)
            options = [_make(m, "set_aside", "saving", amount=amount, ci=ci),
                       _make(m, "set_aside", "saving", amount=_round_down(amount / 2, 10.0), ci=ci)]
            options += [cap_for(c) for c in habits[:1]]
        elif habits:
            options = [cap_for(habits[0]), pace]
        else:
            options = [pace, cap_for({"category": biggest_usual, "spent": usual.get(biggest_usual, 0.0)})]
    if not options:
        options = [pace]
    seen, uniq = set(), []
    for o in options:
        key = (o["kind"], o["target"], o["cap"], o["amount"])
        if key not in seen:
            seen.add(key)
            uniq.append(o)
    first, rest = uniq[0], uniq[1:3]
    first["alternatives"] = [{k: o[k] for k in ("kind", "target", "target_label", "cap", "amount", "title", "why", "worth", "replay")}
                             for o in rest]
    if question:      # each answer points at one of the things: 0 is the suggestion, 1 the first alternative
        question["answers"] = [x for x in question["answers"] if x["pick"] <= len(rest)]
        for x in question["answers"]:
            x["title"] = ([first] + rest)[x["pick"]]["title"]
    first["question"] = question if question and len(question["answers"]) == 2 else None
    first["next"] = None
    return first


# ------------------------------------------------------- commit and undo
def build(m: Money, kind: str | None = None, target: str | None = None, cap: float | None = None, amount: float | None = None) -> dict:
    """The thing the user asked for (or the suggestion when nothing is named), checked against what exists."""
    if not kind or kind == "suggestion":
        return suggest(m)
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    if kind in ("cap_category", "pause_category"):
        by_label = {v[lang].lower(): k for k, v in CATEGORIES.items() for lang in ("en", "fi")}
        target = target if target in CATEGORIES else by_label.get(str(target or "").strip().lower())
        if target not in CATEGORIES or CATEGORIES[target]["basket"] != EVERYDAY:
            raise ValueError("target must be one of the everyday categories: " +
                             ", ".join(k for k, v in CATEGORIES.items() if v["basket"] == EVERYDAY))
        if kind == "cap_category" and (cap is None or float(cap) < 0):
            raise ValueError("cap_category needs a cap in euros")
    if kind == "set_aside" and (amount is None or float(amount) <= 0):
        raise ValueError("set_aside needs an amount in euros a month")
    if kind == "set_aside":
        target = target if target in CATEGORIES else "saving"
    return _make(m, kind, target or "everyday", cap=cap, amount=amount)


def commit(state: dict, m: Money, action: dict) -> dict:
    """Keep the thing. Setting money aside goes through the plan, so safe to spend counts it from today."""
    drop(state)
    a = {k: action.get(k) for k in ("kind", "target", "target_label", "cap", "amount", "title", "why", "until", "until_label")}
    a.update({"cycle_start": m.cycle_start.isoformat(), "cycle_end": m.next_payday.isoformat(), "set_on": m.today.isoformat(),
              "set_at": time.time()})
    if a["kind"] == "set_aside":
        prefs = state.setdefault("prefs", {})
        a["saving_before"] = prefs.get("savings_goal_monthly")          # None means "follow my habit"
        a["saving_was"] = r2(m.savings_plan)
        prefs["savings_goal_monthly"] = r2(m.savings_plan + float(a["amount"] or 0))
    state["action"] = a
    return a


def change(state: dict, m: Money, cap: float | None = None, amount: float | None = None) -> dict | None:
    a = state.get("action")
    if not a:
        return None
    if a["kind"] == "set_aside" and amount is not None:
        a["amount"] = r2(float(amount))
        state.setdefault("prefs", {})["savings_goal_monthly"] = r2(float(a.get("saving_was") or 0) + a["amount"])
    elif a["kind"] in ("cap_category", "daily_pace") and (cap if cap is not None else amount) is not None:
        a["cap"] = r2(float(cap if cap is not None else amount))
    a["title"] = title_of(m, a)
    a["changed_at"] = time.time()
    return a


def drop(state: dict) -> dict | None:
    old = state.pop("action", None)
    if old:
        if old.get("kind") == "set_aside":
            state.setdefault("prefs", {})["savings_goal_monthly"] = old.get("saving_before")
        state["last_action"] = old
    return old


# ---------------------------------------------------------------- progress
def _total(m: Money, a: dict, start: date, end_incl: date):
    d = m.df[(m.df["date"] >= start) & (m.df["date"] <= end_incl)]
    if a["kind"] in ("cap_category", "pause_category"):
        return d[(d["category"] == a["target"]) & (d["spend"] > 0)]
    return d[(d["basket"] == EVERYDAY) & (d["spend"] > 0)]


def progress(m: Money, action: dict) -> dict:
    """Where the thing stands today, from the real transactions of this cycle."""
    w = _W(m)
    L, E = w.L, w.E
    a = dict(action)
    kind = a.get("kind")
    start = date.fromisoformat(a.get("cycle_start") or m.cycle_start.isoformat())
    days_in = max(1, (m.today - start).days + 1)
    days_left = max(0, (m.next_payday - m.today).days)
    base = {"kind": kind, "target": a.get("target"), "target_label": w.cat(a["target"]) if a.get("target") in CATEGORIES else None,
            "cap": a.get("cap"), "amount": a.get("amount"), "title": title_of(m, a), "days_in": days_in, "days_left": days_left,
            "until": m.next_payday.isoformat(), "until_label": w.day(m.next_payday), "set_on": a.get("set_on")}
    if kind == "set_aside":
        s = m.safe
        return {**base, "verdict": "on_track" if s["amount"] > 0 else "at_risk", "limit": None, "spent": None, "left": None,
                "saving_monthly": r2(m.savings_plan), "purchases": [],
                "line": L(f"Planned saving is now {E(m.savings_plan)} a month. Safe to spend already counts it: {E(s['per_day'], True)} a day "
                          f"{w.until_payday}.",
                          f"Suunniteltu säästö on nyt {E(m.savings_plan)} kuussa. Turvallinen käyttövara huomioi sen jo: "
                          f"{E(s['per_day'], True)} päivässä {w.until_payday}."),
                "follow_up_preview": None}
    rows = _total(m, a, start, m.today)
    spent = r2(rows["spend"].sum())
    purchases = [_purchase(r) for r in rows.sort_values(["date", "spend"], ascending=[False, False]).itertuples()]
    if kind == "daily_pace":
        # the pace is a promise for the days that are left: what matters is today's safe number against the one it was set at
        s = m.safe
        per_day = r2(float(a.get("cap") or 0))
        now = r2(s["per_day"])
        today_spent = r2(rows[rows["date"] == m.today]["spend"].sum())
        set_today = (a.get("set_on") or m.today.isoformat()) == m.today.isoformat()
        verdict = "over" if s["amount"] <= 0 else "at_risk" if now < per_day * 0.9 else "on_track"
        if set_today or abs(now - per_day) < 0.01:
            line = L(f"{E(per_day, True)} a day for the {days_left} days {w.until_payday}. Spend less on a day and the next day's number "
                     f"goes up.",
                     f"{E(per_day, True)} päivässä, {days_left} päivää {w.until_payday}. Kun käytät jonain päivänä vähemmän, seuraavan "
                     f"päivän luku nousee.")
        elif now > per_day:
            line = L(f"Your safe pace is now {E(now, True)} a day, up from the {E(per_day, True)} you set. It is holding.",
                     f"Turvallinen tahtisi on nyt {E(now, True)} päivässä, kun asetit {E(per_day, True)}. Se pitää.")
        else:
            line = L(f"Your safe pace is now {E(now, True)} a day, down from the {E(per_day, True)} you set, with {days_left} days to go.",
                     f"Turvallinen tahtisi on nyt {E(now, True)} päivässä, kun asetit {E(per_day, True)}. {days_left} päivää jäljellä.")
        return {**base, "verdict": verdict, "limit": per_day, "spent": None, "left": None, "unit": "day", "pace_now": now,
                "today_spent": today_spent, "cycle_spent": spent, "purchases": purchases[:5], "line": line, "follow_up_preview": None}
    limit = r2(float(a.get("cap") or 0))
    left = r2(max(0.0, limit - spent))
    pace = spent / days_in
    lands = r2(spent + pace * days_left)
    if kind == "pause_category":
        since = date.fromisoformat(a.get("set_on") or m.today.isoformat())
        after = rows[rows["date"] > since]
        slipped = r2(after["spend"].sum())
        verdict = "over" if slipped > 0.005 else "done" if days_left == 0 else "on_track"
        line = (L(f"Nothing on {w.cat_low(a['target'])} since you set it. {days_left} days to go.",
                  f"{FI_ILLATIVE.get(a['target'], w.cat_low(a['target'])).capitalize()} ei ole mennyt mitään sen jälkeen, kun asetit "
                  f"tämän. {days_left} päivää jäljellä.") if slipped <= 0.005 else
                L(f"{E(slipped)} went to {w.cat_low(a['target'])} since you set it.",
                  f"{FI_ILLATIVE.get(a['target'], w.cat_low(a['target'])).capitalize()} on mennyt {E(slipped)} sen jälkeen, kun asetit tämän."))
        return {**base, "verdict": verdict, "limit": 0.0, "spent": slipped, "left": 0.0, "unit": "cycle", "cycle_spent": spent,
                "purchases": [_purchase(r) for r in after.itertuples()], "line": line, "follow_up_preview": None}
    if spent > limit + 0.005:
        verdict = "over"
        line = L(f"{E(spent)} of {E(limit)} used: {E(spent - limit)} over, with {days_left} days to go.",
                 f"{E(spent)} / {E(limit)} käytetty: {E(spent - limit)} yli, ja {days_left} päivää jäljellä.")
    elif days_left == 0:
        verdict = "done"
        line = L(f"It held: {E(spent)} of {E(limit)}.", f"Raja piti: {E(spent)} / {E(limit)}.")
    else:
        verdict = "at_risk" if lands > limit + 0.005 else "on_track"
        per_week = r2(left / days_left * 7)
        line = (L(f"{E(spent)} of {E(limit)} used after {days_in} days. At this pace it lands at {E(lands)}. To hold, that is {E(per_week)} "
                  f"a week from here.",
                  f"{E(spent)} / {E(limit)} käytetty {days_in} päivässä. Tällä tahdilla päädyt {E(lands)}:oon. Raja pitää, jos käytät tästä "
                  f"eteenpäin {E(per_week)} viikossa.") if verdict == "at_risk" else
                L(f"{E(spent)} of {E(limit)} used after {days_in} days. {E(left)} left for {days_left} days, about {E(per_week)} a week.",
                  f"{E(spent)} / {E(limit)} käytetty {days_in} päivässä. Jäljellä {E(left)} {days_left} päivälle, noin {E(per_week)} "
                  f"viikossa."))
    return {**base, "verdict": verdict, "limit": limit, "spent": spent, "left": left, "unit": "cycle",
            "left_per_week": r2(left / days_left * 7) if days_left else 0.0, "lands_at_current_pace": lands,
            "purchases": purchases[:6], "line": line, "follow_up_preview": follow_up_preview(m, a)}


def follow_up_preview(m: Money, action: dict) -> dict | None:
    """What the check-in at the end of the cycle will look like, shown as a replay of the last complete cycle.
    The dataset has no future, so this is the honest way to show the loop closing. It is labelled as a replay."""
    w = _W(m)
    L, E = w.L, w.E
    cycles = _cycles(m, 1)
    kind = action.get("kind")
    if not cycles or kind != "cap_category":
        return None
    start, end = cycles[-1]
    rows = _total(m, action, start, end - timedelta(days=1))
    total = r2(rows["spend"].sum())
    limit = r2(float(action.get("cap") or 0))
    held = bool(total <= limit + 0.005)
    top = [_purchase(r) for r in rows.sort_values("spend", ascending=False).head(2).itertuples()]
    did = ""
    if not held and top:
        names = [f"{_what(w, p)} {E(p['amount'])}" for p in top]
        did = L(" The biggest: " + " and ".join(names) + ".", " Suurimmat: " + " ja ".join(names) + ".")
    text = (L(f"Held: {E(total)} of {E(limit)}, {E(limit - total)} to spare.", f"Piti: {E(total)} / {E(limit)}, {E(limit - total)} jäi.") if held else
            L(f"{E(total)} of {E(limit)}: over by {E(total - limit)}.{did}", f"{E(total)} / {E(limit)}: {E(total - limit)} yli.{did}"))
    return {"label": L(f"Replay: had you set this on {w.day(start)}", f"Toisto: jos olisit asettanut tämän {w.day(start)}"),
            "replay": True, "held": held, "total": total, "limit": limit, "text": text, "purchases": top}


def purchase_effect(m: Money, action: dict, afford: dict) -> dict:
    """What a purchase the user is weighing does to the thing they set. Honest about what we cannot know (its category)."""
    w = _W(m)
    L, E = w.L, w.E
    p = progress(m, action)
    kind = action.get("kind")
    out = {"title": p["title"], "kind": kind, "verdict": p["verdict"], "touches": None}
    if kind == "daily_pace":
        after = afford["per_day"]["after"]
        out["touches"] = True
        out["line"] = L(f"Your one thing is {p['title']}. This would take the pace to {E(after, True)} a day.",
                        f"Yksi asiasi on {p['title']}. Tämä veisi tahdin {E(after, True)}:oon päivässä.")
    elif kind in ("cap_category", "pause_category"):
        left = p.get("left") or 0.0
        out["line"] = (L(f"Your one thing, {p['title']}, only moves if this is {w.cat_low(action['target'])}: {E(left)} is left on it.",
                         f"Yksi asiasi, {p['title']}, muuttuu vain jos tämä on {w.cat_low(action['target'])}: siitä on jäljellä {E(left)}.")
                       if kind == "cap_category" else
                       L(f"Your one thing, {p['title']}, only breaks if this is {w.cat_low(action['target'])}.",
                         f"Yksi asiasi, {p['title']}, rikkoutuu vain jos tämä on {w.cat_low(action['target'])}."))
    else:
        out["touches"] = False
        out["line"] = L(f"The {E(action.get('amount') or 0)} a month you set aside is already counted in this answer.",
                        f"Sivuun siirtämäsi {E(action.get('amount') or 0)} kuussa on jo mukana tässä vastauksessa.")
    return out


def slim(ci: dict) -> dict:
    """The look-back without the long lists: what the coach needs to talk about it."""
    if not ci.get("cycle"):
        return {k: ci[k] for k in ("available", "headline", "partial_view")}
    c = ci["cycle"]
    keep = ("label", "start", "end", "days", "income", "fixed", "surprise_reserve", "planned_saving", "everyday_available",
            "everyday_spent", "within", "difference", "over_by", "days_below_zero", "without_one_off")
    drv = c.get("driver")
    return {"headline": ci["headline"], "what_did_it": ci.get("driver_line"), "history_line": ci.get("history_line"),
            "note": ci["note"], "partial_view": ci["partial_view"], "can_judge": ci["can_judge"],
            "cycle": {**{k: c[k] for k in keep},
                      "driver": {k: drv[k] for k in ("label", "spent", "usual", "above_usual", "kind", "biggest")} if drv else None},
            "history": {k: ci["history"][k] for k in ("total", "within", "over")}}
