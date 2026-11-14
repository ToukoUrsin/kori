"""Coach notices: the few things worth saying today, found by rules on the customer's own data.

Each notice has a tone (warn / info / good), the numbers behind it and a question to ask the coach next.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..taxonomy import CATEGORIES, EVERYDAY, FIXED, SURPRISE, cat_label, kind_label
from .core import DAYS_PER_MONTH, Money, month_bounds, r2
from .query import fmt_day
from . import peers

SMALL = 15.0
PURCHASES, OSTOKSET = ("purchase", "purchases"), ("ostos", "ostosta")


def eur(v: float, lang: str, cents: bool = False) -> str:
    """€1,094 in English, 1 094 € in Finnish."""
    neg = v < 0
    v = abs(v)
    s = f"{v:,.2f}" if cents else f"{round(v):,}"
    if lang == "fi":
        s = s.replace(",", " ").replace(".", ",")
        return f"{'−' if neg else ''}{s} €"
    return f"{'−' if neg else ''}€{s}"


def slips(m: Money, days: int = 90, under: float = SMALL) -> dict:
    """Small everyday purchases that are easy to forget: how many, what they add up to, and where they go."""
    lang = m.prefs.lang
    days = int(max(7, min(365, days or 90)))
    under = float(under or SMALL)
    start = m.today - timedelta(days=days - 1)
    start = max(start, m.df["date"].iloc[0])
    days = (m.today - start).days + 1
    d = m.df[(m.df["date"] >= start) & (m.df["basket"] == EVERYDAY) & (m.df["spend"] > 0) & (m.df["spend"] < under)]
    every = m.df[(m.df["date"] >= start) & (m.df["basket"] == EVERYDAY)]["spend"].sum()
    total = r2(d["spend"].sum())
    by_kind = d.groupby("kind")["spend"].agg(["sum", "count"]).sort_values("sum", ascending=False)
    by_place = d[d["merchant"].notna()].groupby("merchant")["spend"].agg(["sum", "count"]).sort_values(["count", "sum"], ascending=False)
    E = lambda v, cents=False: eur(v, lang, cents)
    L = lambda en, fi: en if lang == "en" else fi
    return {"days": days, "under": under, "count": int(len(d)), "total": total,
            "per_year": r2(total * 365 / days), "per_month": r2(total * DAYS_PER_MONTH / days),
            "average": r2(total / len(d)) if len(d) else 0.0,
            "share_of_everyday": round(float(total / every), 3) if every > 0 else 0.0,
            "top_kinds": [{"kind": k, "label": kind_label(k, lang), "total": r2(s), "count": int(c)} for k, (s, c) in by_kind.head(3).iterrows()],
            "top_places": [{"merchant": k, "total": r2(s), "count": int(c)} for k, (s, c) in by_place.head(3).iterrows()],
            "window_label": L(f"Purchases under {E(under)}, the last {days} days", f"Alle {E(under)} ostokset, viimeiset {days} päivää"),
            "headline": (L(f"{len(d)} purchases under {E(under)} in the last {days} days came to {E(total)}. At this rate that is {E(total * 365 / days)} a year.",
                           f"{len(d)} alle {E(under)} ostosta viimeisten {days} päivän aikana teki yhteensä {E(total)}. Tällä tahdilla se on {E(total * 365 / days)} vuodessa.")
                         if len(d) != 1 else
                         L(f"1 purchase under {E(under)} in the last {days} days: {E(total, True)}.",
                           f"1 alle {E(under)} ostos viimeisten {days} päivän aikana: {E(total, True)}."))}


def plural(n: int, lang: str, en: tuple[str, str], fi: tuple[str, str]) -> str:
    """'1 purchase' / '3 purchases'; '1 ostos' / '3 ostosta'."""
    one, many = en if lang == "en" else fi
    return f"{n} {one if n == 1 else many}"


def negative_days(m: Money, months: int = 12) -> dict:
    """Days on which the balance was below zero, over the last complete months."""
    keys = m.last_full_months(months)
    d = m.df[m.df["month"].isin(keys)]
    neg = d[d["balance"] < 0]
    return {"months": len(keys), "days": int(neg["date"].nunique()), "lowest": r2(d["balance"].min()) if len(d) else 0.0,
            "months_touched": int(neg["month"].nunique())}


def num(v: float, lang: str, digits: int = 1) -> str:
    s = f"{v:.{digits}f}"
    return s.replace(".", ",") if lang == "fi" else s


def tidy(text: str) -> str:
    """Finnish dates end in a full stop; avoid '15.10..' at the end of a sentence."""
    return text.replace("..", ".").replace(".,", ".,").replace(". .", ".")


def notices(m: Money, limit: int = 6) -> list[dict]:
    lang = m.prefs.lang
    L = lambda en, fi: en if lang == "en" else fi
    E = lambda v, cents=False: eur(v, lang, cents)
    out: list[dict] = []
    s = m.safe
    pay = date.fromisoformat(s["next_payday"])

    def add(id_, tone, prio, title, body, ask, card=None, metric=None):
        out.append({"id": id_, "tone": tone, "priority": prio, "title": tidy(title), "body": tidy(body), "ask": ask,
                    "card": card, "metric": metric})

    # 0. partial view (salary moves to another bank)
    if m.partial_view:
        add("partial_view", "info", 95,
            L("I only see part of your money", "Näen vain osan rahoistasi"),
            L(f"About {E(m.sweep_typical)} of your salary moves to another bank the day after payday. My numbers cover what stays here. Linking the other account would give you the full picture.",
              f"Noin {E(m.sweep_typical)} palkastasi siirtyy toiseen pankkiin palkkapäivän jälkeen. Lukuni kattavat sen, mikä jää tänne. Toisen tilin liittäminen näyttäisi koko kuvan."),
            L("What can you see about my money?", "Mitä näet rahoistani?"), metric=m.sweep_typical)

    # 0b. pay has not arrived on the 15th this month
    if not m.paid_this_month and m.today.day >= 15 and not m.partial_view and len(m.salaries):
        add("pay_pending", "info", 93,
            L("Your pay didn't arrive on the 15th this month", "Palkkasi ei tullut tässä kuussa 15. päivä"),
            L(f"In months like this it has always landed in the last days of the month, so I'm planning for {fmt_day(pay, lang)}.",
              f"Tällaisina kuukausina se on aina tullut kuun viimeisinä päivinä, joten suunnittelen päivän {fmt_day(pay, lang)} mukaan."),
            L("What is safe for me to spend until my pay arrives?", "Paljonko voin käyttää ennen kuin palkka tulee?"), metric=s["days_to_payday"])

    # 0c. this pay cycle's everyday money is used up, but there is still cash
    if not m.partial_view and s["budget"]["left"] < 0 and s["cash"]["free"] > 0:
        add("over_budget", "warn", 92,
            L("This pay cycle's everyday money is used up", "Tämän palkkajakson arkiraha on käytetty"),
            L(f"You're {E(-s['budget']['left'])} past what your income leaves for everyday. There is still {E(s['cash']['free'])} free on the account, but spending it shrinks your buffer instead of using this month's income.",
              f"Olet {E(-s['budget']['left'])} yli sen, mitä tuloistasi jää arkeen. Tilillä on vielä {E(s['cash']['free'])} vapaana, mutta sen käyttäminen pienentää puskuriasi eikä tule tämän kuun tuloista."),
            L("Where did my everyday money go this pay cycle?", "Mihin arkirahani meni tällä palkkajaksolla?"), metric=s["budget"]["left"])

    # 1. runway to payday
    f = m.forecast("usual")
    low, low_d = f["lowest"]["balance"], date.fromisoformat(f["lowest"]["date"])
    rent = next((u for u in s["upcoming"] if u["category"] == "Housing"), None)
    rent_txt = L(f" {E(rent['amount'])} of housing leaves around {fmt_day(date.fromisoformat(rent['date']), lang)}, before payday.",
                 f" Asumiseen lähtee {E(rent['amount'])} noin {fmt_day(date.fromisoformat(rent['date']), lang)}, ennen palkkapäivää.") if rent else ""
    if not m.partial_view:
        if low < 0:
            add("runway", "warn", 100,
                L(f"At your usual pace you'd be {E(-low)} short on {fmt_day(low_d, lang)}",
                  f"Tavallisella tahdillasi olisit {E(-low)} miinuksella {fmt_day(low_d, lang)}"),
                L(f"Payday is {fmt_day(pay, lang)}.{rent_txt} Keeping to {E(s['per_day'], True)} a day gets you there without going below zero.",
                  f"Palkkapäivä on {fmt_day(pay, lang)}.{rent_txt} Kun pysyt {E(s['per_day'], True)}:ssa päivässä, pääset perille menemättä miinukselle."),
                L("What is safe for me to spend this week?", "Paljonko voin turvallisesti käyttää tällä viikolla?"),
                card="forecast", metric=low)
        elif low < max(m.cushion * 2.5, 0.08 * m.salary_typical):
            add("runway", "warn", 90,
                L(f"At your usual pace you'd be down to {E(low)} the day before payday",
                  f"Tavallisella tahdillasi sinulla olisi {E(low)} palkkapäivän aattona"),
                L(f"Payday is {fmt_day(pay, lang)}.{rent_txt} Your safe pace is {E(s['per_day'], True)} a day; your usual is {E(s['usual_per_day'], True)}.",
                  f"Palkkapäivä on {fmt_day(pay, lang)}.{rent_txt} Turvallinen tahtisi on {E(s['per_day'], True)} päivässä; tavallinen tahtisi on {E(s['usual_per_day'], True)}."),
                L("What is safe for me to spend this week?", "Paljonko voin turvallisesti käyttää tällä viikolla?"),
                card="forecast", metric=low)
        else:
            add("runway", "good", 40,
                L(f"You're on course to reach payday with {E(low)} to spare", f"Olet menossa palkkapäivään {E(low)} ylimääräisenä"),
                L(f"That's at your usual pace of {E(s['usual_per_day'], True)} a day, with housing and bills already counted.",
                  f"Tämä tavallisella tahdillasi, {E(s['usual_per_day'], True)} päivässä, asuminen ja laskut jo huomioituna."),
                L("How much could I safely save right now?", "Paljonko voisin turvallisesti säästää juuri nyt?"),
                card="forecast", metric=low)

    # 2. late pay stress test
    lp = s.get("late_pay")
    if lp and not lp["covered"] and lp["rate"] >= 0.1:
        n = len(m.salaries)
        late_n = round(lp["rate"] * n)
        add("late_pay", "info", 70,
            L(f"Your pay came late in {late_n} of the last {n} months", f"Palkkasi tuli myöhässä {late_n} kertaa viimeisten {n} kuukauden aikana"),
            L(f"If it lands on {fmt_day(date.fromisoformat(lp['date']), lang)} instead of the 15th, you'd need about {E(lp['extra_needed'])} more to cover those {lp['extra_days']} days.",
              f"Jos se tulee {fmt_day(date.fromisoformat(lp['date']), lang)} eikä 15. päivä, tarvitsisit noin {E(lp['extra_needed'])} lisää niiden {lp['extra_days']} päivän ajaksi."),
            L("What happens if my pay is late this month?", "Mitä tapahtuu, jos palkkani myöhästyy tässä kuussa?"), metric=lp["extra_needed"])

    # 3. a category running hot this month
    b = m.baskets()
    hot = []
    for bk in b["baskets"]:
        if bk["key"] != EVERYDAY:
            continue
        for c in bk["categories"]:
            if c["usual"] > 0 and c["amount"] - c["usual"] >= 60 and c["amount"] >= 1.3 * c["usual"]:
                hot.append(c)
    if hot:
        c = max(hot, key=lambda x: x["amount"] - x["usual"])
        left_days = b["days_in_month"] - b["days_elapsed"]
        add("hot_" + c["category"], "warn", 80,
            L(f"{c['label']} is at {E(c['amount'])} this month. Your usual whole month is {E(c['usual'])}",
              f"{c['label']}: {E(c['amount'])} tässä kuussa. Tavallinen koko kuukautesi on {E(c['usual'])}"),
            L(f"{plural(c['count'], lang, PURCHASES, OSTOKSET)} so far, with {left_days} {'day' if left_days == 1 else 'days'} of the month left.",
              f"{plural(c['count'], lang, PURCHASES, OSTOKSET)} tähän mennessä, kuukautta jäljellä {left_days} {'päivä' if left_days == 1 else 'päivää'}."),
            L(f"Show me my {c['label'].lower()} spending this month", f"Näytä {c['label'].lower()} tässä kuussa"),
            metric=r2(c["amount"] - c["usual"]))

    # 4. small purchases that slip through
    sl = slips(m)
    if sl["count"] >= 8:
        add("slips", "info", 60,
            L(f"{sl['count']} small purchases added up to {E(sl['total'])}", f"{sl['count']} pientä ostosta teki yhteensä {E(sl['total'])}"),
            L(f"All under {E(SMALL)} each, over the last {sl['days']} days. At this rate that's {E(sl['per_year'])} a year from the basket that slips through your fingers.",
              f"Kaikki alle {E(SMALL)}, viimeisten {sl['days']} päivän aikana. Tällä tahdilla se on {E(sl['per_year'])} vuodessa siitä korista, joka valuu sormien läpi."),
            L("Show me my small purchases from the last 90 days", "Näytä pienet ostokseni viimeisten 90 päivän ajalta"), metric=sl["total"])

    # 5. a surprise just happened
    recent = m.df[(m.df["date"] >= m.today - timedelta(days=30)) & (m.df["basket"] == SURPRISE) & (m.df["spend"] >= 150)]
    if len(recent):
        r = recent.sort_values("spend").iloc[-1]
        add("surprise", "info", 55,
            L(f"A {E(r['spend'])} surprise landed on {fmt_day(r['date'], lang)}", f"{E(r['spend'])} yllätys osui {fmt_day(r['date'], lang)}"),
            L(f"{cat_label(r['category'], lang)}. You can't skip these and you can't time them. Over the past year yours have averaged {E(m.usual[SURPRISE])} a month, so that is what I hold back for you.",
              f"{cat_label(r['category'], lang)}. Näitä ei voi ohittaa eikä ajoittaa. Viimeisen vuoden aikana niitä on tullut keskimäärin {E(m.usual[SURPRISE])} kuussa, joten sen verran pidän sinulle varalla."),
            L("How big should my surprise reserve be?", "Kuinka iso yllätysvarani pitäisi olla?"), metric=r2(r["spend"]))

    # 6. below zero in the past year
    nd = negative_days(m)
    if nd["days"] >= 5 and not m.partial_view:
        add("below_zero", "warn" if nd["days"] >= 20 else "info", 65,
            L(f"Your balance was below zero on {nd['days']} days in the past year", f"Saldosi oli miinuksella {nd['days']} päivänä viimeisen vuoden aikana"),
            L(f"It touched {nd['months_touched']} different months, lowest {E(nd['lowest'])}. The pattern: housing leaves early in the month, pay arrives on the 15th.",
              f"Se osui {nd['months_touched']} eri kuukaudelle, alimmillaan {E(nd['lowest'])}. Kaava: asuminen lähtee alkukuusta, palkka tulee 15. päivä."),
            L("Why does my balance go below zero before payday?", "Miksi saldoni menee miinukselle ennen palkkapäivää?"), metric=nd["days"])

    # 7. buffer
    sv = m.safe_to_save
    mc = sv["buffer"]["months_covered"]
    if mc is not None and not m.partial_view:
        if mc >= 3:
            add("buffer", "good", 35,
                L(f"Your buffer covers {num(mc, lang)} months of musts", f"Puskurisi kattaa {num(mc, lang)} kuukauden pakolliset menot"),
                L(f"That is {E(sv['buffer']['balance'])} against musts of {E(sv['buffer']['musts_monthly'])} a month. Three months is the usual target, so you're past it.",
                  f"Se on {E(sv['buffer']['balance'])}, kun pakolliset menosi ovat {E(sv['buffer']['musts_monthly'])} kuussa. Tavallinen tavoite on kolme kuukautta, joten olet sen yli."),
                L("How much could I safely save right now?", "Paljonko voisin turvallisesti säästää juuri nyt?"), metric=mc)
        elif mc < 1:
            add("buffer", "info", 50,
                L(f"Your buffer covers {num(mc, lang)} months of musts", f"Puskurisi kattaa {num(mc, lang)} kuukauden pakolliset menot"),
                L(f"Musts (fixed plus surprises) are {E(sv['buffer']['musts_monthly'])} a month. A first goal of one full month would be {E(sv['buffer']['musts_monthly'])}.",
                  f"Pakolliset menosi (kiinteät ja yllätykset) ovat {E(sv['buffer']['musts_monthly'])} kuussa. Ensimmäinen tavoite, yksi täysi kuukausi, olisi {E(sv['buffer']['musts_monthly'])}."),
                L("How do I build a buffer?", "Miten rakennan puskurin?"), metric=mc)

    # 8. could save now
    if sv["now"] >= 100:
        add("save_now", "good", 58,
            L(f"You could move {E(sv['now'])} to savings today", f"Voisit siirtää {E(sv['now'])} säästöön tänään"),
            L("That is what's left after housing, bills, a surprise reserve, a slightly expensive stretch of everyday life and a three-month buffer.",
              "Sen verran jää asumisen, laskujen, yllätysvaran, hieman tavallista kalliimman arjen ja kolmen kuukauden puskurin jälkeen."),
            L("How much could I safely save right now?", "Paljonko voisin turvallisesti säästää juuri nyt?"), metric=sv["now"])

    # 9. a win: an everyday category clearly under its usual pace late in the month
    if b["days_elapsed"] >= 18:
        frac = b["days_elapsed"] / b["days_in_month"]
        wins = [c for bk in b["baskets"] if bk["key"] == EVERYDAY for c in bk["categories"]
                if c["usual"] >= 80 and 0 < c["amount"] <= 0.6 * c["usual"] * frac]
        if wins:
            c = max(wins, key=lambda x: x["usual"] * frac - x["amount"])
            add("win_" + c["category"], "good", 45,
                L(f"{c['label']} is well under your usual this month", f"{c['label']} on selvästi alle tavallisen tässä kuussa"),
                L(f"{E(c['amount'])} so far, against a usual whole month of {E(c['usual'])}.",
                  f"{E(c['amount'])} tähän mennessä, kun tavallinen koko kuukautesi on {E(c['usual'])}."),
                L(f"How does my {c['label'].lower()} compare with earlier months?", f"Miten {c['label'].lower()} vertautuu aiempiin kuukausiin?"),
                metric=r2(c["usual"] - c["amount"]))

    # 10. standing out from people the same age
    try:
        cmp_ = peers.compare(m, "age")
        cand = [c for c in cmp_["categories"] if c["percentile"] >= 90 and c["diff"] >= 60 and c["key"] not in ("Housing", "Utilities")]
        if cand and not m.partial_view:
            c = cand[0]
            add("peer_" + c["key"], "info", 48,
                L(f"{c['label']}: you spend more than {c['percentile']}% of people your age",
                  f"{c['label']}: käytät enemmän kuin {c['percentile']} % ikäisistäsi"),
                L(f"{E(c['you'])} a month against a typical {E(c['median'])} for customers {cmp_['group']['label']} ({cmp_['group']['size']} people).",
                  f"{E(c['you'])} kuussa, kun tyypillinen on {E(c['median'])} ({cmp_['group']['size']} henkeä vertailuryhmässä)."),
                L("How do I compare with people my age?", "Miten vertaudun ikäisiini?"), card="peers", metric=c["diff"])
    except KeyError:
        pass

    out.sort(key=lambda x: -x["priority"])
    return out[:limit]
