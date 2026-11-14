"""Answers that are about one thing in the person's situation: a payment already made, money that arrives once,
a goal with a date, the pay itself.

Each returns the numbers and a `brief`: a headline, a few rows and notes the app draws as they are. Nothing is
simulated on a typical month here; these read the real account as it stands today.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from ..taxonomy import BASKETS, EVERYDAY, FIXED, KINDS, SURPRISE, cat_label, kind_label
from .core import DAYS_PER_MONTH, Money, add_months, month_key, r2
from .insights import eur, num, tidy
from ..wording import is_pensioner
from .query import MONTHS_LONG, fmt_day, tx_row


def _words(m: Money):
    lang = m.prefs.lang
    L = lambda en, fi: en if lang == "en" else fi
    E = lambda v, cents=False: eur(v, lang, cents)
    return lang, L, E


def _month_year(d: date, lang: str, case: str = "") -> str:
    """June 2027 / kesäkuu 2027. Finnish takes a case ending: 'by' kesäkuuhun, 'in' kesäkuussa."""
    name = MONTHS_LONG[lang][d.month - 1]
    if lang == "en":
        return f"{name.capitalize()} {d.year}"
    return f"{name}{ {'by': 'hun', 'in': 'ssa'}.get(case, '') } {d.year}"


# --------------------------------------------------------------- a payment already made

def _find(m: Money, amount: float | None, merchant: str | None, on: str | None):
    """The payment the person means. Each hint narrows the search; a hint that matches nothing is dropped.
    Hints that all match nothing find nothing: better to say so than to explain some other payment."""
    df = m.df
    hints = bool(amount or merchant or on)
    when = None
    if on:
        try:
            when = date.fromisoformat(str(on)[:10])
        except ValueError:
            when = None
    if when is not None:
        hit = df[df["date"] == when]
        if hit.empty:
            hit = df[(df["date"] >= when - timedelta(days=3)) & (df["date"] <= when + timedelta(days=3))]
        if not hit.empty:
            df = hit
    if amount is not None:
        try:
            a = abs(float(amount))
        except (TypeError, ValueError):
            a = None
        if a:
            hit = df[(df["amount"].abs() - a).abs() <= 0.011]
            if hit.empty:
                hit = df[(df["amount"].abs() - a).abs() <= max(1.0, 0.03 * a)]
            if not hit.empty:
                df = hit
    if merchant:
        q = str(merchant).strip().lower()
        hit = df[df["merchant"].fillna("").str.lower().str.contains(q, regex=False)]
        if hit.empty and q:
            lang = m.prefs.lang
            lab = df["kind"].map(lambda k: kind_label(k, lang).lower()) + " " + df["category"].map(lambda c: cat_label(c, lang).lower())
            hit = df[lab.str.contains(q, regex=False)]
        if not hit.empty:
            df = hit
    if df is m.df:
        if hints:
            return None
        df = df[df["is_spend"]]
    if df.empty:
        return None
    return df.sort_values("ts").iloc[-1]


def payment(m: Money, amount: float | None = None, merchant: str | None = None, on: str | None = None) -> dict:
    """One payment that has already happened: which basket it is in, whether it is already counted, and how
    that kind of spending is running against the usual month. Never a new purchase."""
    lang, L, E = _words(m)
    r = _find(m, amount, merchant, on)
    if r is None:
        return {"found": False, "note": L("No payment like that in the account history.", "Tilihistoriasta ei löytynyt sellaista maksua.")}
    s = m.safe
    amt = r2(abs(r["amount"]))
    when: date = r["date"]
    cat, kind = r["category"], r["kind"]
    name = r["merchant"] if isinstance(r["merchant"], str) else kind_label(kind, lang) if kind in KINDS else cat_label(cat, lang)
    row = tx_row(r, lang)
    in_cycle = when >= m.cycle_start
    start = fmt_day(m.cycle_start, lang)
    pay = fmt_day(date.fromisoformat(s["next_payday"]), lang)
    base = {"found": True, "payment": {"date": when.isoformat(), "amount": amt, "merchant": row["merchant"], "category": row["category_label"],
                                       "kind": row["kind_label"], "time": row["time"]},
            "already_happened": True}

    if cat in ("Salary", "Other Income"):
        head = L(f"Money in: {E(amt, True)} on {fmt_day(when, lang)}. It is part of your income, not spending.",
                 f"Rahaa sisään: {E(amt, True)} {fmt_day(when, lang)}. Se on tuloasi, ei kulutusta.")
        return base | {"flow": "income", "headline": tidy(head),
                       "brief": {"headline": tidy(head), "figure": {"value": amt, "label": f"{name} · {fmt_day(when, lang)}", "cents": True}, "rows": [], "notes": []}}
    if cat == "Salary Sweep":
        head = L(f"Your salary moving on: {E(amt, True)} left for your account at another bank on {fmt_day(when, lang)}. It is your own money, and I count what stays here.",
                 f"Palkkasi siirtyi eteenpäin: {E(amt, True)} lähti toisen pankin tilillesi {fmt_day(when, lang)}. Se on omaa rahaasi, ja minä lasken sen, mikä jää tänne.")
        return base | {"flow": "transfer", "headline": tidy(head),
                       "brief": {"headline": tidy(head), "figure": {"value": amt, "label": f"{cat_label(cat, lang)} · {fmt_day(when, lang)}", "cents": True}, "rows": [], "notes": []}}
    if cat in ("Invest Deposit", "Invest Withdraw"):
        head = L(f"Saving, not spending: {E(amt, True)} moved on {fmt_day(when, lang)}.", f"Säästöä, ei kulutusta: {E(amt, True)} siirtyi {fmt_day(when, lang)}.")
        return base | {"flow": "saving", "headline": tidy(head),
                       "brief": {"headline": tidy(head), "figure": {"value": amt, "label": f"{cat_label(cat, lang)} · {fmt_day(when, lang)}", "cents": True}, "rows": [], "notes": []}}

    basket = r["basket"] if isinstance(r["basket"], str) else m._basket_of(cat)
    b_label = BASKETS[basket][lang]

    # how this kind of spending is running: this pay cycle against a usual whole month
    by_kind = kind in KINDS
    like = m.df[(m.df["kind"] == kind) if by_kind else (m.df["category"] == cat)]
    like_label = kind_label(kind, lang) if by_kind else cat_label(cat, lang)
    cyc = like[like["date"] >= m.cycle_start]
    months = m.last_full_months(6)
    per_month = like[like["month"].isin(months)].groupby("month")["spend"].sum().reindex(months).fillna(0.0)
    usual = r2(per_month.mean()) if len(months) else 0.0
    cyc_total, cyc_count = r2(cyc["spend"].sum()), int(len(cyc))
    days_in = (m.today - m.cycle_start).days + 1
    cycle_days = max(1, s["budget"]["cycle_days"])

    spent = s["budget"]["everyday_spent"]
    if basket == EVERYDAY and in_cycle and s["amount"] <= 0.005:
        head = L(f"Already counted. This {E(amt, True)} is everyday spending from this pay cycle: it is inside the {E(spent, True)} you have spent since {start}, "
                 f"which is more than this cycle's income leaves for everyday. That is why nothing is safe to spend before {pay}.",
                 f"Jo laskettu mukaan. Tämä {E(amt, True)} on tämän palkkajakson arkimenoa: se sisältyy {E(spent, True)} menoihin, jotka olet käyttänyt {start} jälkeen, "
                 f"ja se on enemmän kuin tämän jakson tuloista jää arkeen. Siksi turvallista käyttövaraa ei ole ennen {pay}.")
        counted = {"counted_in": "everyday_spent_this_pay_cycle", "everyday_spent_this_pay_cycle": spent, "safe_to_spend_now": s["amount"],
                   "changes_safe_to_spend_again": False}
    elif basket == EVERYDAY and in_cycle:
        head = L(f"Already counted. This {E(amt, True)} is everyday spending from this pay cycle: it is inside the {E(spent, True)} you have spent since {start}, "
                 f"so the {E(s['amount'], True)} that is safe to spend already takes it into account.",
                 f"Jo laskettu mukaan. Tämä {E(amt, True)} on tämän palkkajakson arkimenoa: se sisältyy {E(spent, True)} menoihin, jotka olet käyttänyt {start} jälkeen, "
                 f"joten turvallinen käyttövara, {E(s['amount'], True)}, ottaa sen jo huomioon.")
        counted = {"counted_in": "everyday_spent_this_pay_cycle", "everyday_spent_this_pay_cycle": spent, "safe_to_spend_now": s["amount"],
                   "changes_safe_to_spend_again": False}
    elif basket == EVERYDAY:
        head = L(f"Everyday spending from an earlier pay cycle. It does not touch the {E(s['amount'], True)} that is safe to spend now.",
                 f"Aiemman palkkajakson arkimenoa. Se ei vaikuta siihen, mitä voit nyt käyttää: {E(s['amount'], True)}.")
        counted = {"counted_in": "an_earlier_pay_cycle", "safe_to_spend_now": s["amount"], "changes_safe_to_spend_again": False}
    elif basket == FIXED:
        head = (L(f"A fixed must that has already left the account. It is no longer among the {E(s['cash']['fixed_due'], True)} of bills I hold back before {pay}, "
                  f"and it never came out of your everyday money.",
                  f"Kiinteä pakollinen meno, joka on jo lähtenyt tililtä. Se ei ole enää niiden laskujen joukossa, joita varten pidän {E(s['cash']['fixed_due'], True)} "
                  f"varalla ennen {pay}, eikä se tullut arkirahastasi.")
                if in_cycle else
                L("A fixed must from an earlier pay cycle. Fixed musts are set aside before safe to spend is worked out, so they never come out of everyday money.",
                  "Aiemman palkkajakson kiinteä pakollinen meno. Kiinteät menot varataan ennen kuin turvallinen käyttövara lasketaan, joten ne eivät tule arkirahasta."))
        counted = {"counted_in": "fixed_musts", "bills_still_due_before_payday": s["cash"]["fixed_due"], "changes_safe_to_spend_again": False}
    else:
        head = (L(f"A surprise must: you needed it, but you could not pick the day. It has already left the account, and the {E(s['cash']['surprise_reserve'], True)} "
                  f"I hold back until {pay} is for the next one.",
                  f"Yllättävä pakollinen meno: tarvitsit sen, mutta et voinut valita päivää. Se on jo lähtenyt tililtä, ja {E(s['cash']['surprise_reserve'], True)}, "
                  f"jota pidän varalla {pay} asti, on seuraavaa varten.")
                if in_cycle else
                L(f"A surprise must from an earlier pay cycle. Yours average {E(m.usual[SURPRISE])} a month over the past year, and that is what the reserve is sized for.",
                  f"Aiemman palkkajakson yllättävä pakollinen meno. Niitä on tullut sinulle keskimäärin {E(m.usual[SURPRISE])} kuussa viimeisen vuoden aikana, ja vara on mitoitettu sen mukaan."))
        counted = {"counted_in": "surprise_musts", "surprise_reserve_until_payday": s["cash"]["surprise_reserve"],
                   "surprise_monthly_average": m.usual[SURPRISE], "changes_safe_to_spend_again": False}

    rows = [{"label": L("Basket", "Kori"), "text": b_label, "dot": basket}]
    notes = []
    running = None
    if in_cycle and cyc_count:
        rows.append({"label": L(f"{like_label} since {start}", f"{like_label} {start} alkaen"), "value": cyc_total, "cents": True,
                     "sub": L(f"{cyc_count} {'payment' if cyc_count == 1 else 'payments'}", f"{cyc_count} {'maksu' if cyc_count == 1 else 'maksua'}")})
        if usual > 0:
            rows.append({"label": L("Your usual whole month", "Tavallinen koko kuukautesi"), "value": usual, "cents": True})
            expected = usual * days_in / DAYS_PER_MONTH
            if cyc_total > usual:
                running = "past_usual_month"
                notes.append(L(f"{like_label}: already past your usual whole month, {days_in} days into a {cycle_days}-day pay cycle.",
                               f"{like_label}: olet jo yli tavallisen koko kuukautesi, kun palkkajaksoa on kulunut {days_in} päivää {cycle_days} päivästä."))
            elif cyc_total > 1.25 * expected and cyc_total - expected >= 15:
                running = "ahead_of_usual"
                notes.append(L(f"{like_label}: running ahead of your usual pace, {days_in} days into a {cycle_days}-day pay cycle.",
                               f"{like_label} kulkee tavallista tahtiasi edellä: palkkajaksoa on kulunut {days_in} päivää {cycle_days} päivästä."))
            else:
                running = "within_usual"
                notes.append(L(f"{like_label}: within your usual pace so far.", f"{like_label}: toistaiseksi tavallisessa tahdissasi."))
    elif usual > 0:
        rows.append({"label": L(f"{like_label}, your usual month", f"{like_label}, tavallinen kuukautesi"), "value": usual, "cents": True})
    if basket == EVERYDAY and s["per_day"] > 0:
        d = round(amt / s["per_day"], 1)
        if d >= 0.3:
            notes.append(L(f"One payment this size is {num(d, lang)} {'day' if d == 1 else 'days'} of your safe pace of {E(s['per_day'], True)} a day.",
                           f"Yksi tämän kokoinen maksu on {num(d, lang)} päivän verran turvallista tahtiasi, joka on {E(s['per_day'], True)} päivässä."))
    brief = {"headline": tidy(head),
             "figure": {"value": amt, "cents": True,
                        "label": f"{name} · {fmt_day(when, lang)}"},
             "rows": rows, "notes": [tidy(n) for n in notes]}
    return base | {"flow": "spend", "basket": {"key": basket, "label": b_label}, "in_this_pay_cycle": in_cycle, "counted": counted,
                   "like_it": {"label": like_label, "this_pay_cycle": {"total": cyc_total, "count": cyc_count}, "usual_whole_month": usual,
                               "days_into_cycle": days_in, "cycle_days": cycle_days, "running": running},
                   "headline": tidy(head), "brief": brief}


# ------------------------------------------------------------------- money that arrives once

def windfall(m: Money, amount: float, label: str | None = None) -> dict:
    """A bonus, a refund, a gift: money that lands once. It changes this pay cycle and nothing after it."""
    lang, L, E = _words(m)
    try:
        amount = r2(float(amount))
    except (TypeError, ValueError):
        raise ValueError("amount must be a number of euros") from None
    if amount <= 0:
        raise ValueError("amount must be more than zero")
    label = (label or "").strip()[:40] or L("One-off money", "Kertaluonteinen raha")
    s = m.safe
    days, pay = s["days_to_payday"], fmt_day(date.fromisoformat(s["next_payday"]), lang)
    before = s["amount"]
    after = r2(max(0.0, min(s["budget"]["left"] + amount, s["cash"]["free"] + amount)))
    per_before, per_after = s["per_day"], r2(after / days)
    over = r2(max(0.0, -min(s["budget"]["left"], s["cash"]["free"])))
    musts = r2(m.usual[FIXED] + m.usual[SURPRISE])
    surprise = m.usual[SURPRISE]
    head = (L(f"With {E(amount)} more, safe to spend until {pay} goes from {E(before)} to {E(after)}: {E(per_after, True)} a day. "
              f"It comes once, so your next {'pension' if is_pensioner(m.customer.age) else 'pay'} cycle starts from the usual number again.",
              f"Kun tilille tulee {E(amount)} lisää, turvallinen käyttövara {pay} asti muuttuu: nyt {E(before)}, sen jälkeen {E(after)} eli {E(per_after, True)} päivässä. "
              f"Raha tulee vain kerran, joten seuraava {'eläkejakso' if is_pensioner(m.customer.age) else 'palkkajakso'} alkaa taas tavallisesta luvusta."))
    choices = []
    if over > 0.005:
        choices.append({"title": L("This pay cycle first", "Ensin tämä palkkajakso"),
                        "text": L(f"This cycle is already {E(over, True)} over what your income leaves for everyday. The money fills that first; {E(after)} is left for the {days} days to {pay}.",
                                  f"Tämä jakso on jo {E(over, True)} yli sen, mitä tuloistasi jää arkeen. Raha täyttää ensin sen; {E(after)} jää {days} päivälle {pay} asti.")})
    else:
        choices.append({"title": L("Spread it over this pay cycle", "Jaa se tälle palkkajaksolle"),
                        "text": L(f"{E(amount / days, True)} more a day for the {days} days to {pay}: {E(per_before, True)} becomes {E(per_after, True)}.",
                                  f"{E(amount / days, True)} enemmän päivässä {days} päivän ajan {pay} asti: nyt {E(per_before, True)}, sen jälkeen {E(per_after, True)}.")})
    if surprise > 0:
        n = round(amount / surprise, 1)
        choices.append({"title": L("Keep it for a surprise", "Pidä se yllätyksen varalle"),
                        "text": L(f"Your surprise musts average {E(surprise)} a month. This is {num(n, lang)} {'month' if n == 1 else 'months'} of them, ready before they come.",
                                  f"Yllättävät pakolliset menosi ovat keskimäärin {E(surprise)} kuussa. Tämä vastaa {num(n, lang)} kuukauden yllätyksiä, valmiina ennen kuin ne tulevat.")})
    if musts > 0:
        d = int(round(amount / musts * DAYS_PER_MONTH))
        choices.append({"title": L("Leave it untouched", "Jätä se koskematta"),
                        "text": L(f"Your musts are {E(musts)} a month, so {E(amount)} keeps rent, bills and surprises paid for {d} more {'day' if d == 1 else 'days'} if income stopped.",
                                  f"Pakolliset menosi ovat {E(musts)} kuussa, joten {E(amount)} maksaa vuokran, laskut ja yllätykset {d} päivää pidempään, jos tulot loppuisivat.")})
    brief = {"headline": tidy(head),
             "rows": [{"label": L(f"Safe to spend until {pay}", f"Turvallista käyttää {pay} asti"), "from": before, "to": after},
                      {"label": L("A day", "Päivässä"), "from": per_before, "to": per_after, "cents": True},
                      {"label": L(f"Next {'pension' if is_pensioner(m.customer.age) else 'pay'} cycle", f"Seuraava {'eläkejakso' if is_pensioner(m.customer.age) else 'palkkajakso'}"),
                       "text": L("No change", "Ei muutosta")}],
             "choices_title": L("Three places it can go", "Kolme paikkaa, joihin se voi mennä") if len(choices) == 3 else L("Where it can go", "Mihin se voi mennä"),
             "choices": [{"title": c["title"], "text": tidy(c["text"])} for c in choices], "notes": []}
    return {"amount": amount, "label": label, "comes_once": True,
            "safe_to_spend": {"before": before, "after": after, "per_day_before": per_before, "per_day_after": per_after},
            "days_to_payday": days, "next_payday": s["next_payday"], "already_over_this_cycle": over,
            "next_pay_cycle_changes": False, "musts_monthly": musts, "surprise_monthly_average": surprise,
            "choices": [{"title": c["title"], "text": tidy(c["text"])} for c in choices],
            "headline": tidy(head), "brief": brief, "partial_view": m.partial_view}


# ----------------------------------------------------------------------- a goal with a date

def _months_until(m: Money, by: str | None, months: float | None) -> tuple[int | None, date | None]:
    if months:
        try:
            n = int(max(1, min(240, math.ceil(float(months)))))
        except (TypeError, ValueError):
            n = None
        if n:
            k = add_months(m.this_month, n)
            return n, date(int(k[:4]), int(k[5:7]), 1)
    if by:
        txt = str(by).strip()
        try:
            target = date.fromisoformat(txt[:10]) if len(txt) >= 10 else date(int(txt[:4]), int(txt[5:7]), 1)
        except (ValueError, IndexError):
            return None, None
        n = (target.year - m.today.year) * 12 + (target.month - m.today.month)
        return (max(1, n), target) if n >= 0 else (None, None)
    return None, None


MAX_GOAL = 1_000_000.0


def goal_amount(amount, lang: str = "en") -> float:
    """A goal amount as euros, or a plain sentence saying why it is refused (more than a million, or not an amount)."""
    L = lambda en, fi: en if lang == "en" else fi
    try:
        v = float(amount)
    except (TypeError, ValueError):
        v = float("nan")
    if math.isnan(v) or math.isinf(v) or v <= 0:
        raise ValueError(L("A goal needs an amount in euros that is more than zero.",
                           "Tavoitteelle tarvitaan euromäärä, joka on suurempi kuin nolla."))
    if v > MAX_GOAL:
        raise ValueError(L("A goal can be at most €1,000,000. Choose a smaller amount.",
                           "Tavoite voi olla enintään 1 000 000 €. Valitse pienempi summa."))
    return r2(v)


def goal(m: Money, amount: float, name: str | None = None, months: float | None = None, by: str | None = None) -> dict:
    """Is this goal reachable by that date, from what a usual month really leaves? If not: when, or what it takes."""
    lang, L, E = _words(m)
    amount = goal_amount(amount, lang)
    name = (name or "").strip()[:40] or L("Your goal", "Tavoitteesi")
    n, target = _months_until(m, by, months)
    room = r2(max(0.0, m.usual["left_over"]))
    short = r2(max(0.0, -m.usual["left_over"]))
    when = lambda k, case="": _month_year(date(int(k[:4]), int(k[5:7]), 1), lang, case)
    out = {"goal": {"name": name, "amount": amount, "months": n, "by": target.isoformat()[:7] if target else None},
           "usual_month_leaves": room, "usual_month_short_by": short, "partial_view": m.partial_view}
    if m.partial_view:
        head = L("I only see part of your month: most of your salary moves to another bank. Link the other account and I can tell you whether this fits.",
                 "Näen vain osan kuukaudestasi: suurin osa palkastasi siirtyy toiseen pankkiin. Yhdistä toinen tili, niin voin kertoa, mahtuuko tämä.")
        need = r2(amount / n) if n else None
        rows = [{"label": L("Needed each month", "Tarvitaan kuukaudessa"), "value": need}] if need else []
        return out | {"verdict": "cannot_judge", "needed_monthly": need, "headline": head,
                      "brief": {"headline": head, "figure": {"value": amount, "label": name}, "rows": rows, "notes": [], "link": True}}

    at_room = math.ceil(amount / room) if room >= 1 else None
    at_room_key = add_months(m.this_month, at_room) if at_room and at_room <= 240 else None
    at_room_when = when(at_room_key) if at_room_key else None
    at_room_in = when(at_room_key, "in") if at_room_key else None
    day_now = r2(m.safe["budget"]["everyday_monthly"] / DAYS_PER_MONTH)
    top = sorted(((c, v) for c, v in m.usual["categories"].items() if m._basket_of(c) == EVERYDAY and v > 0), key=lambda x: -x[1])[:2]
    top_txt = L(" and ", " ja ").join(f"{cat_label(c, lang).lower()} ({E(v)})" for c, v in top)
    rows, choices, notes = [], [], []
    if not n:
        # no date given: how long at the pace a usual month allows
        if at_room:
            head = L(f"A usual month leaves you {E(room)} after everything. At that pace {E(amount)} takes {at_room} months: around {at_room_when}.",
                     f"Tavallisesta kuukaudestasi jää {E(room)} kaiken jälkeen. Sillä tahdilla {E(amount)} vie {at_room} kuukautta: koossa noin {at_room_in}.")
            verdict = "no_date"
        else:
            head = L(f"A usual month leaves nothing over right now{f' (it is {E(short)} short)' if short else ''}, so this goal needs a trim first.",
                     f"Tavallisesta kuukaudestasi ei juuri nyt jää mitään yli{f' (se on {E(short)} miinuksella)' if short else ''}, joten tavoite vaatii ensin karsimista.")
            verdict = "no_room"
        rows = [{"label": L("A usual month leaves", "Tavallisesta kuukaudesta jää"), "value": room}]
        if at_room:
            rows.append({"label": L("Months at that pace", "Kuukausia sillä tahdilla"), "text": str(at_room)})
        return out | {"verdict": verdict, "needed_monthly": None, "months_at_usual_room": at_room, "reached_at_usual_room": at_room_when,
                      "headline": tidy(head),
                      "brief": {"headline": tidy(head), "figure": {"value": amount, "label": name}, "rows": rows, "notes": [], "choices": []}}

    need = r2(amount / n)
    gap = r2(max(0.0, need - room))
    by_txt, by_fi = when(month_key(target)), when(month_key(target), "by")
    day_after = r2(max(0.0, m.safe["budget"]["everyday_monthly"] - need) / DAYS_PER_MONTH)
    rows = [{"label": L("Needed each month", "Tarvitaan kuukaudessa"), "value": need, "strong": True},
            {"label": L("A usual month leaves", "Tavallisesta kuukaudesta jää"), "value": room}]
    if gap <= 0.005:
        verdict = "fits"
        spare = r2(room - need)
        head = L(f"Yes, it fits. {E(amount)} by {by_txt} is {E(need)} a month for {n} months, and a usual month leaves you {E(room)}.",
                 f"Kyllä, se mahtuu. {E(amount)} {by_fi} mennessä on {E(need)} kuussa {n} kuukauden ajan, ja tavallisesta kuukaudestasi jää {E(room)}.")
        rows.append({"label": L("Still left over", "Jää vielä yli"), "value": spare, "tone": "good"})
        notes.append(L(f"Move the {E(need)} on payday, before spending starts. Your everyday money for a full pay cycle then goes from {E(day_now, True)} a day to {E(day_after, True)}.",
                       f"Siirrä {E(need)} palkkapäivänä, ennen kuin kulutus alkaa. Koko palkkajakson arkiraha on silloin {E(day_after, True)} päivässä, kun se nyt on {E(day_now, True)}."))
    else:
        verdict = "not_at_this_pace" if at_room else "no_room"
        gap_day = r2(gap / DAYS_PER_MONTH)
        rows.append({"label": L("Missing each month", "Puuttuu kuukaudessa"), "value": gap, "tone": "warn"})
        head = (L(f"Not at your current pace. {E(amount)} by {by_txt} needs {E(need)} a month, and a usual month leaves you {E(room)}. At {E(room)} a month it is there in {at_room} months, around {at_room_when}.",
                  f"Ei nykyisellä tahdillasi. {E(amount)} {by_fi} mennessä vaatii {E(need)} kuussa, ja tavallisesta kuukaudestasi jää {E(room)}. Kun säästät {E(room)} kuussa, se on koossa {at_room} kuukaudessa, noin {at_room_in}.")
                if at_room else
                L(f"Not yet. {E(amount)} by {by_txt} needs {E(need)} a month, and a usual month leaves nothing over right now.",
                  f"Ei vielä. {E(amount)} {by_fi} mennessä vaatii {E(need)} kuussa, eikä tavallisesta kuukaudestasi jää juuri nyt mitään yli."))
        choices.append({"title": L(f"Keep the date: {by_txt}", f"Pidä päivä: {by_txt}"),
                        "text": L(f"Find {E(gap)} a month, about {E(gap_day, True)} a day less on everyday spending. Your largest everyday spending is {top_txt} a month.",
                                  f"Etsi {E(gap)} kuussa eli noin {E(gap_day, True)} päivässä vähemmän arjen menoihin. Suurimmat arkimenosi ovat {top_txt} kuussa.")})
        if not at_room and top:
            # nothing is left over: show what one modest trim of the largest everyday category would do
            c0, v0 = top[0]
            trim = r2(0.1 * v0)
            net = r2(trim - short)
            if net >= 1:
                mm = math.ceil(amount / net)
                choices.append({"title": L("Start with one trim", "Aloita yhdestä karsinnasta"),
                                "text": L(f"10% less on {cat_label(c0, lang).lower()} is {E(trim)} a month. " +
                                          (f"After the {E(short)} your usual month is short, {E(net)} is left for the goal: " if short else f"Set that aside: ") +
                                          f"{E(amount)} in {mm} months, around {when(add_months(m.this_month, mm))}.",
                                          f"10 % vähemmän kategoriaan {cat_label(c0, lang).lower()} on {E(trim)} kuussa. " +
                                          (f"Kun siitä katetaan ensin tavallisen kuukautesi {E(short)} vajaus, tavoitteelle jää {E(net)}: " if short else "Laita se sivuun: ") +
                                          f"{E(amount)} on koossa {mm} kuukaudessa, noin {when(add_months(m.this_month, mm), 'in')}.")})
            elif short:
                notes.append(L(f"Your usual month is {E(short)} short, so the first {E(short)} you trim closes that before anything goes to the goal.",
                               f"Tavallinen kuukautesi on {E(short)} miinuksella, joten ensimmäiset {E(short)} karsinnasta menevät sen kattamiseen ennen kuin mitään jää tavoitteelle."))
        if at_room:
            choices.append({"title": L("Keep your month as it is", "Pidä kuukautesi ennallaan"),
                            "text": L(f"Set aside the {E(room)} a usual month leaves. The goal moves to {at_room_when}.",
                                      f"Laita sivuun se {E(room)}, joka tavallisesta kuukaudesta jää. Tavoite on silloin koossa {at_room_in}.")})
            half = r2(room + gap / 2)
            mid = math.ceil(amount / half)
            if n < mid < at_room:
                choices.append({"title": L("Meet in the middle", "Puolivälin ratkaisu"),
                                "text": L(f"Trim {E(gap / 2)} a month and set aside {E(half)}. It is there in {mid} months, around {when(add_months(m.this_month, mid))}.",
                                          f"Karsi {E(gap / 2)} kuussa ja laita sivuun {E(half)}. Se on koossa {mid} kuukaudessa, noin {when(add_months(m.this_month, mid), 'in')}.")})
    brief = {"headline": tidy(head), "figure": {"value": need, "label": L(f"a month for {n} months · {name}, {E(amount)}", f"kuussa {n} kuukauden ajan · {name}, {E(amount)}")},
             "rows": rows, "notes": [tidy(x) for x in notes],
             "choices_title": L("Ways to get there", "Tapoja päästä perille") if choices else None,
             "choices": [{"title": c["title"], "text": tidy(c["text"])} for c in choices]}
    return out | {"verdict": verdict, "needed_monthly": need, "missing_monthly": gap, "missing_per_day": r2(gap / DAYS_PER_MONTH) if gap else 0.0,
                  "months_at_usual_room": at_room, "reached_at_usual_room": at_room_when,
                  "everyday_per_day": {"now": day_now, "if_set_aside_on_payday": day_after},
                  "largest_everyday_spending": [{"label": cat_label(c, lang), "usual_monthly": v} for c, v in top],
                  "choices": [{"title": c["title"], "text": tidy(c["text"])} for c in choices],
                  "headline": tidy(head), "brief": brief}


# ------------------------------------------------------------------------------- the pay itself

def income(m: Money, period_total: float | None = None, period_label: str | None = None, period_count: int | None = None) -> dict:
    """What comes in each month, when it lands, and (when the salary moves on) what stays on this account."""
    lang, L, E = _words(m)
    pension = is_pensioner(m.customer.age)
    word = L("pension" if pension else "pay", "eläke" if pension else "palkka")
    sal = m.salaries
    last = [{"date": r.date.isoformat(), "amount": r2(r.amount), "late": bool(r.date.day >= 26)} for r in sal.tail(4).itertuples()][::-1]
    late_n, total_n = int(sum(1 for d in sal["date"] if d.day >= 26)), int(len(sal))
    swept = m.sweep_typical if (m.partial_view or m.linked_view) else 0.0
    s = m.safe
    rows = [{"label": fmt_day(date.fromisoformat(x["date"]), lang) + (L(" · late", " · myöhässä") if x["late"] else ""), "value": x["amount"], "cents": True}
            for x in last[:3]]
    notes = []
    if m.partial_view:
        head = L(f"About {E(m.salary_typical)} lands here each month, and about {E(swept)} of it moves to another bank the next day. {E(m.income_typical, True)} stays, "
                 f"and that is the income I build safe to spend from.",
                 f"Tälle tilille tulee noin {E(m.salary_typical)} kuussa, ja siitä noin {E(swept)} siirtyy toiseen pankkiin seuraavana päivänä. Tänne jää {E(m.income_typical, True)}, "
                 f"ja siitä lasken turvallisen käyttövaran.")
        rows += [{"label": L("Moves to another bank, typical month", "Siirtyy toiseen pankkiin, tavallinen kuukausi"), "value": -swept, "cents": True},
                 {"label": L("Stays on this account", "Jää tälle tilille"), "value": m.income_typical, "cents": True, "strong": True}]
    else:
        head = L(f"Your typical monthly {word} is {E(m.salary_typical, True)}: the middle of your last six. Safe to spend starts from it, "
                 f"before fixed musts, the surprise reserve and saving come off.",
                 f"Tyypillinen kuukausittainen {word}si on {E(m.salary_typical, True)}: kuuden viimeisimmän keskimmäinen. Turvallinen käyttövara lähtee siitä, "
                 f"ennen kuin kiinteät menot, yllätysvara ja säästö vähennetään.")
        if m.linked_view:
            notes.append(m.linked_view["note"])
    if late_n and total_n:
        notes.append(L(f"It usually lands on the 15th. In {late_n} of your last {total_n} months it came at the end of the month instead.",
                       f"Se tulee yleensä 15. päivä. {late_n} kertaa viimeisten {total_n} kuukauden aikana se tuli vasta kuun lopussa."))
    brief = {"headline": tidy(head),
             "figure": {"value": m.salary_typical, "cents": True, "label": L(f"Typical monthly {word} · last 6 months", f"Tyypillinen {word} kuussa · viimeiset 6 kk")},
             "rows_title": L(f"Latest {word}", f"Viimeisimmät: {word}"), "rows": rows, "notes": [tidy(n) for n in notes]}
    out = {"monthly_income": m.salary_typical,
           "monthly_income_label": L(f"typical monthly {word} landing on this account, median of the last 6", f"tyypillinen tälle tilille tuleva {word} kuussa, kuuden viimeisimmän mediaani"),
           "latest_payments": last, "usual_day": 15, "came_at_month_end": {"months": late_n, "of_months": total_n},
           "next_expected": s["next_payday"], "partial_view": m.partial_view, "headline": tidy(head), "brief": brief}
    if m.partial_view:
        out |= {"moves_to_another_bank_monthly": swept, "stays_on_this_account_monthly": m.income_typical,
                "safe_to_spend_is_built_on": "stays_on_this_account_monthly"}
    if period_total is not None and period_label:
        out["in_the_period_asked"] = {"label": period_label, "total": r2(period_total), "payments": period_count}
    return out
