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


def whole(v: float) -> int:
    """Whole euros the way the screen rounds them: from the cents, halves up. (Python's round() sends 18.50 to 18 and the
    app's own formatter sends it to 19, and then a sentence and the card under it disagree.)"""
    a = abs(round(float(v), 2))
    n = int(a + 0.5 + 1e-9)
    return -n if v < 0 else n


def eur(v: float, lang: str, cents: bool = False) -> str:
    """€1,094 in English, 1 094 € in Finnish."""
    neg = v < 0
    v = abs(v)
    s = f"{v:,.2f}" if cents else f"{whole(v):,}"
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
    kinds = [{"kind": k, "label": kind_label(k, lang), "total": r2(s), "count": int(c)} for k, (s, c) in by_kind.head(3).iterrows()]
    rest_n = int(len(d)) - sum(k["count"] for k in kinds)
    if rest_n > 0:          # the rows add up to the total above them
        kinds.append({"kind": "other", "label": L("Everything else", "Kaikki muu"), "total": r2(total - sum(k["total"] for k in kinds)), "count": rest_n})
    return {"days": days, "under": under, "count": int(len(d)), "total": total,
            "per_year": r2(total * 365 / days), "per_month": r2(total * DAYS_PER_MONTH / days),
            "average": r2(total / len(d)) if len(d) else 0.0,
            "share_of_everyday": round(float(total / every), 3) if every > 0 else 0.0,
            "top_kinds": kinds,
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


def hero_line(m) -> str:
    """The one sentence under the number on the home screen: what the balance says against what comes first.
    With the other bank linked it also says that a simulated account is counted in."""
    line = _hero_line(m)
    if m.linked_view:
        lang = m.prefs.lang
        own = eur(float(m.df["balance"].iloc[-1]), lang)
        there = eur(m.linked_view["balance_today"], lang)
        line = line.replace("Your account shows", "Your accounts show", 1).replace("Tililläsi on", "Tileilläsi on", 1)
        line += {"en": f" That is {own} here plus {there} on the simulated account at your other bank.",
                 "fi": f" Siitä {own} on tällä tilillä ja {there} simuloidulla tilillä toisessa pankissasi."}[lang]
    return line


def _hero_line(m) -> str:
    from .query import fmt_day
    s, lang = m.safe, m.prefs.lang
    E = lambda v: eur(v, lang)
    L = lambda en, fi: en if lang == "en" else fi
    bal, due, res = s["balance"], s["cash"]["fixed_due"], s["cash"]["surprise_reserve"]
    until = fmt_day(date.fromisoformat(s["next_payday"]), lang)
    if m.partial_view:
        return L(f"This account shows {E(bal)}, but most of your salary moves to another bank, so I count only what stays here.",
                 f"Tällä tilillä on {E(bal)}, mutta suurin osa palkastasi siirtyy toiseen pankkiin, joten lasken vain sen, mikä jää tänne.")
    if s["amount"] <= 0.005 and s["limit"] == "budget" and s["cash"]["free"] > 0.5:
        # The balance is not all spoken for: the everyday money this pay cycle left is used up, and the rest is
        # held for bills, the reserve and the cushion, or is money Kori does not count as spending money.
        b = s["budget"]
        return L(f"Your account shows {E(bal)}, but this pay cycle's everyday money is used up: there was {E(b['everyday_budget'])} "
                 f"for it and {E(b['everyday_spent'])} is spent. The rest is held for bills and reserves, or kept as savings.",
                 f"Tililläsi on {E(bal)}, mutta tämän palkkajakson arkiraha on käytetty: siihen oli {E(b['everyday_budget'])}, "
                 f"ja arkeen on mennyt {E(b['everyday_spent'])}. Loput on varattu laskuihin ja varoihin tai jää säästöön.")
    if s["amount"] <= 0.005:
        return tidy(L(f"Your account shows {E(bal)}, and all of it is spoken for until payday on {until}.",
                      f"Tililläsi on {E(bal)}, ja se kaikki on jo varattu palkkapäivään {until} asti."))
    # Every euro between the balance and the number is named, so the sentence adds up to the number above it.
    c = s["cash"]
    parts = [(due, f"{E(due)} of bills", f"{E(due)} laskuihin"),
             (res, f"a {E(res)} surprise reserve", f"{E(res)} yllätysvaraan"),
             (c.get("saving_left", 0.0), f"{E(c.get('saving_left', 0.0))} of planned saving", f"{E(c.get('saving_left', 0.0))} säästöön"),
             (c.get("cushion", 0.0), f"a {E(c.get('cushion', 0.0))} cushion", f"{E(c.get('cushion', 0.0))} pohjavaraan")]
    parts = [p for p in parts if p[0] > 0.5]
    beyond = c["free"] - s["amount"] if s["limit"] == "budget" else 0.0
    if beyond > 0.5:
        # in whole euros the last part is what is left of the sum, so a reader who subtracts gets the number on screen
        left = whole(bal) - sum(whole(p[0]) for p in parts) - whole(s["amount"])
        beyond = float(left) if abs(left - beyond) <= 1.5 and left > 0 else beyond
    if parts:
        def join(items: list[str], last: str) -> str:
            return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" {last} " + items[-1]
        en = f"Your account shows {E(bal)}, but {join([p[1] for p in parts], 'and')} come first."
        fi = f"Tililläsi on {E(bal)}, mutta siitä menee ensin {join([p[2] for p in parts], 'ja')}."
        if beyond > 0.5:
            first = join([p[1] for p in parts], "and")
            # one breath on a phone: what comes first, and what stays put (the row below it says why it is not spending money)
            en = f"Your account shows {E(bal)}. {first[0].upper() + first[1:]} come first, and {E(beyond)} more stays as savings."
            fi = f"Tililläsi on {E(bal)}. Siitä menee ensin {join([p[2] for p in parts], 'ja')}, ja {E(beyond)} jää säästöön."
        return L(en, fi)
    return tidy(L(f"Your account shows {E(bal)}, and it has to last until payday on {until}.", f"Tililläsi on {E(bal)}, ja sen pitää riittää palkkapäivään {until} asti."))


def tidy(text: str) -> str:
    """Finnish dates end in a full stop; avoid '15.10..' at the end of a sentence."""
    return text.replace("..", ".").replace(".,", ".,").replace(". .", ".")


def notices(m: Money, limit: int = 6, action: dict | None = None) -> list[dict]:
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
              f"Noin {E(m.sweep_typical)} palkastasi siirtyy toiseen pankkiin heti palkkapäivän jälkeen. Lukuni koskevat sitä, mikä jää tänne. Kun yhdistät toisen tilin, näen koko kuvan."),
            L("What can you see about my money?", "Mitä näet rahoistani?"), metric=m.sweep_typical)
    elif m.linked_view:
        add("linked_view", "info", 95,
            L("Your numbers include a simulated account", "Luvuissasi on mukana simuloitu tili"),
            m.linked_view["note"],
            L("What did the other-bank link add?", "Mitä toisen pankin linkki lisäsi?"), metric=m.linked_view["amount_counted"])

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
            L(f"You're {E(-s['budget']['left'])} past what your income leaves for everyday. There is still {E(s['cash']['free'])} free on the account, but this pay cycle's plan does not use it: it is savings from before, not this pay cycle's pay.",
              f"Olet {E(-s['budget']['left'])} yli sen, mitä tuloistasi jää arkeen. Tilillä on vielä {E(s['cash']['free'])} vapaana, mutta tämän palkkajakson suunnitelma ei käytä sitä: se on aiemmin kertynyttä säästöä, ei tämän palkkajakson palkkaa."),
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
                L(f"At your usual pace you'd be down to {E(low)} when your pay lands",
                  f"Tavallisella tahdillasi tililläsi olisi {E(low)}, kun palkkasi tulee"),
                L(f"Payday is {fmt_day(pay, lang)}.{rent_txt} Your safe pace is {E(s['per_day'], True)} a day; your usual is {E(s['usual_per_day'], True)}.",
                  f"Palkkapäivä on {fmt_day(pay, lang)}.{rent_txt} Turvallinen tahtisi on {E(s['per_day'], True)} päivässä; tavallinen tahtisi on {E(s['usual_per_day'], True)}."),
                L("What is safe for me to spend this week?", "Paljonko voin turvallisesti käyttää tällä viikolla?"),
                card="forecast", metric=low)
        elif s["limit"] == "budget" and s["usual_per_day"] > s["per_day"] + 0.005:
            # The account lasts, but the usual pace is above what this pay cycle's plan leaves: the rest is savings.
            add("runway", "info", 40,
                L(f"At your usual pace the account has {E(low)} when your pay lands", f"Tavallisella tahdillasi tililläsi on {E(low)}, kun palkkasi tulee"),
                L(f"Your usual pace is {E(s['usual_per_day'], True)} a day and this pay cycle's plan leaves {E(s['per_day'], True)} a day, "
                  f"so the difference comes out of your savings.",
                  f"Tavallinen tahtisi on {E(s['usual_per_day'], True)} päivässä ja tämän palkkajakson suunnitelma jättää {E(s['per_day'], True)} päivässä, "
                  f"joten erotus otetaan säästöistäsi.") if s["amount"] > 0.005 else
                L(f"Your usual pace is {E(s['usual_per_day'], True)} a day and this pay cycle's everyday money is used up, "
                  f"so until payday it comes out of your savings.",
                  f"Tavallinen tahtisi on {E(s['usual_per_day'], True)} päivässä ja tämän palkkajakson arkiraha on käytetty, "
                  f"joten palkkapäivään asti se otetaan säästöistäsi."),
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
        add("late_pay", "info", 35,
            L(f"Your pay landed at the end of the month in {late_n} of the last {n} months", f"Palkkasi tuli vasta kuun lopussa {late_n} kertaa viimeisten {n} kuukauden aikana"),
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
            L(f"{cat_label(r['category'], lang)}. You can't skip these and you can't time them. Over the past year yours have averaged {E(m.usual[SURPRISE])} a month. "
              f"For the {s['days_to_payday']} {'day' if s['days_to_payday'] == 1 else 'days'} left before payday that is {E(s['cash']['surprise_reserve'])}, and I hold it back for you.",
              f"{cat_label(r['category'], lang)}. Näitä ei voi ohittaa eikä ajoittaa. Viimeisen vuoden aikana niitä on tullut keskimäärin {E(m.usual[SURPRISE])} kuussa. "
              f"Palkkapäivään on {s['days_to_payday']} päivää, ja niiden osuus on {E(s['cash']['surprise_reserve'])}. Sen pidän sinulle varalla."),
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

    if action:
        from .loop import progress as action_progress
        p = action_progress(m, action)
        if p["verdict"] in ("at_risk", "over"):
            add("action_" + p["verdict"], "warn", 110,
                L("Your one thing needs attention", "Yksi asiasi tarvitsee huomiota"),
                p["line"],
                L("How am I doing with it?", "Miten minulla menee sen kanssa?"), metric=p.get("spent"))
    out.sort(key=lambda x: -x["priority"])
    return out[:limit]
