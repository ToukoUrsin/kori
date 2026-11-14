"""Can I afford it? One purchase, measured against safe to spend and the pace it leaves until payday.

The balance is not the budget, so "yes, it is under your safe to spend" is not an answer either:
what matters is what is left per day afterwards, against what this person usually spends per day.
"""
from __future__ import annotations

import math
from datetime import date

from ..taxonomy import EVERYDAY, FIXED, SURPRISE
from .core import DAYS_PER_MONTH, Money, r2
from .insights import eur, tidy
from .query import fmt_day

BASKET_WORDS = {"surprise": SURPRISE, "surprise_must": SURPRISE, "surprise_musts": SURPRISE, "must": SURPRISE,
                "everyday": EVERYDAY, "want": EVERYDAY, "fixed": FIXED, "fixed_must": FIXED, "fixed_musts": FIXED}
MAX_SPREAD_MONTHS = 24


def _status(per_day: float, usual_day: float, amount: float) -> str:
    """The same words and thresholds as safe to spend itself."""
    if amount <= 0:
        return "empty"
    ratio = (per_day / usual_day) if usual_day > 0 else 9.0
    return "comfortable" if ratio >= 1.0 else "tight" if ratio >= 0.6 else "very_tight"


def afford(m: Money, amount: float, label: str | None = None, basket: str | None = None) -> dict:
    """What a purchase of `amount` euros today does to safe to spend.

    basket "everyday" (default): something the person chooses to buy. It comes out of safe to spend.
    basket "surprise": a must that just happened (a repair, a dentist bill). The surprise reserve pays
    first, then the buffer, and only the rest comes out of safe to spend.
    """
    try:
        amount = r2(float(amount))
    except (TypeError, ValueError):
        raise ValueError("amount must be a number of euros") from None
    if amount <= 0:
        raise ValueError("amount must be more than zero")
    lang = m.prefs.lang
    L = lambda en, fi: en if lang == "en" else fi
    E = lambda v, cents=False: eur(v, lang, cents)
    key = BASKET_WORDS.get(str(basket or "everyday").strip().lower().replace(" ", "_"))
    if key is None:
        raise ValueError("basket must be 'everyday' (something you choose to buy) or 'surprise' (a must that just happened)")
    if key == FIXED:
        raise ValueError("a new monthly cost is not a one-time purchase: use what_if with an add_cost change")
    label = (label or "").strip()[:60] or L("This purchase", "Tämä ostos")

    s = m.safe
    days, pay = s["days_to_payday"], date.fromisoformat(s["next_payday"])
    safe_before, per_day_before, usual_day = s["amount"], s["per_day"], s["usual_per_day"]
    free = s["cash"]["free"]
    buffer_before = r2(max(0.0, free - safe_before))

    reserve = None
    from_safe = amount
    if key == SURPRISE:
        available = s["cash"]["surprise_reserve"]
        from_reserve = r2(min(amount, available))
        from_buffer = r2(min(amount - from_reserve, buffer_before))
        from_safe = r2(amount - from_reserve - from_buffer)
        reserve = {"available": available, "used": from_reserve, "left_after": r2(available - from_reserve),
                   "covers_it": bool(from_reserve >= amount - 0.005), "beyond_reserve": r2(amount - from_reserve),
                   "from_buffer": from_buffer, "from_safe_to_spend": from_safe}

    left = r2(safe_before - from_safe)
    short_by = r2(max(0.0, -left))
    safe_after = r2(max(0.0, left))
    per_day_after = r2(safe_after / days)
    status_after = _status(per_day_after, usual_day, safe_after)
    if short_by > 0:
        verdict = "no"
    elif from_safe <= 0.005 or status_after == "comfortable":
        verdict = "yes"
    else:
        verdict = "tight"

    # the account itself: does the money exist without touching bills, reserve or cushion
    cash_after = r2(free - amount + (reserve["used"] if reserve else 0.0))
    account = {"balance_before": m.balance, "balance_after": r2(m.balance - amount),
               "can_take_it": bool(cash_after >= -0.005),
               "buffer_before": buffer_before, "buffer_after": r2(max(0.0, min(buffer_before, cash_after - safe_after)))}

    # options: wait for payday, or spread it over months (a must cannot wait: it can only be rebuilt)
    options = []
    room = m.usual["left_over"]
    cap = room if room >= 20 else max(20.0, 0.1 * m.usual[EVERYDAY])
    if verdict != "yes" and not m.partial_view and key == EVERYDAY:
        cycle_money = s["budget"]["everyday_monthly"]            # what a month's income leaves for everyday
        if cycle_money > 0 and amount <= 0.5 * cycle_money:
            day_then = r2((cycle_money - amount) / DAYS_PER_MONTH)
            until_then = (L(f"Until then your pace stays {E(per_day_before)} a day. ", f"Siihen asti tahtisi pysyy ennallaan: {E(per_day_before)} päivässä. ")
                          if per_day_before > 0 else "")
            options.append({
                "key": "wait", "date": pay.isoformat(), "days": days,
                "per_day_until_then": per_day_before, "per_day_after_buying_then": day_then,
                "text": tidy(L(f"Wait until payday on {fmt_day(pay, lang)}. {until_then}Bought from a full pay cycle, it leaves about {E(day_then)} a day.",
                               f"Odota palkkapäivään {fmt_day(pay, lang)}. {until_then}Koko palkkajaksosta ostettuna siitä jää noin {E(day_then)} päivässä."))})
        n = int(min(MAX_SPREAD_MONTHS, max(2, math.ceil(amount / cap))))
        monthly = r2(amount / n)
        fits = bool(room >= monthly)
        per_day_trim = r2(monthly / DAYS_PER_MONTH)
        options.append({
            "key": "spread", "months": n, "monthly": monthly, "fits_in_left_over": fits,
            "left_over_monthly": room, "per_day": per_day_trim,
            "text": (L(f"Set aside {E(monthly)} a month for {n} months, then buy it. A usual month leaves you {E(room)}, so it fits without changing anything else.",
                       f"Laita sivuun {E(monthly)} kuussa {n} kuukauden ajan ja osta se sitten. Tavallisesta kuukaudestasi jää {E(room)}, joten se mahtuu muuttamatta muuta.")
                     if fits else
                     L(f"Set aside {E(monthly)} a month for {n} months, then buy it. That is about {E(per_day_trim, True)} a day less on everyday spending.",
                       f"Laita sivuun {E(monthly)} kuussa {n} kuukauden ajan ja osta se sitten. Se on noin {E(per_day_trim, True)} päivässä vähemmän arjen menoihin."))})
    if reserve and reserve["beyond_reserve"] > 0.005 and not m.partial_view:
        back = reserve["beyond_reserve"]
        n = int(min(MAX_SPREAD_MONTHS, max(1, math.ceil(back / cap))))
        monthly = r2(back / n)
        options.append({
            "key": "rebuild", "amount": back, "months": n, "monthly": monthly, "fits_in_left_over": bool(room >= monthly),
            "left_over_monthly": room, "per_day": r2(monthly / DAYS_PER_MONTH),
            "text": L(f"A must cannot wait, so the plan is to put back the {E(back)} that the reserve did not cover: {E(monthly)} a month for {n} months.",
                      f"Pakollista menoa ei voi lykätä, joten suunnitelma on palauttaa se {E(back)}, jota vara ei kattanut: {E(monthly)} kuussa {n} kuukauden ajan.")})

    until = fmt_day(pay, lang)
    if m.partial_view:
        headline = (L(f"From what stays on this account, yes: {E(safe_after)} is still safe to spend here until {until}. I only see part of your money, so I cannot say what it does to your whole month.",
                      f"Siitä, mikä jää tälle tilille, kyllä: täällä on sen jälkeen {E(safe_after)} turvallista käyttää {until} asti. Näen vain osan rahoistasi, joten en voi sanoa, mitä se tekee koko kuukaudellesi.")
                    if verdict != "no" else
                    L(f"Not from what stays on this account: it is {E(short_by)} more than is safe to spend here until {until}. I only see part of your money.",
                      f"Ei siitä, mikä jää tälle tilille: se on {E(short_by)} enemmän kuin täällä on turvallista käyttää {until} asti. Näen vain osan rahoistasi."))
    elif reserve and reserve["covers_it"]:
        headline = L(f"Yes. Your surprise reserve of {E(reserve['available'])} covers it, and safe to spend stays at {E(safe_after)}.",
                     f"Kyllä. Yllätysvarasi, {E(reserve['available'])}, kattaa sen, ja turvallinen käyttövara pysyy ennallaan: {E(safe_after)}.")
    elif reserve and from_safe <= 0.005:
        headline = L(f"Yes. Your surprise reserve covers {E(reserve['used'])} and the other {E(reserve['from_buffer'])} comes from money this pay cycle does not need. Safe to spend stays at {E(safe_after)}.",
                     f"Kyllä. Yllätysvarasi kattaa {E(reserve['used'])} ja loput {E(reserve['from_buffer'])} tulee rahasta, jota tämä palkkajakso ei tarvitse. Turvallinen käyttövara pysyy ennallaan: {E(safe_after)}.")
    elif reserve and verdict == "no":
        headline = L(f"Not fully. Your surprise reserve covers {E(reserve['used'])} and money this pay cycle does not need covers {E(reserve['from_buffer'])}. Safe to spend covers part of the rest, and {E(short_by)} is still missing before payday on {until}.",
                     f"Ei kokonaan. Yllätysvarasi kattaa {E(reserve['used'])} ja raha, jota tämä palkkajakso ei tarvitse, {E(reserve['from_buffer'])}. Turvallinen käyttövara kattaa osan lopusta, ja {E(short_by)} jää puuttumaan ennen palkkapäivää {until}.")
    elif reserve:
        headline = L(f"Yes, but only {E(reserve['used'])} comes from your surprise reserve. The rest lowers your pace: now {E(per_day_before)} a day, after it {E(per_day_after)} a day until {until}.",
                     f"Kyllä, mutta yllätysvarastasi tulee vain {E(reserve['used'])}. Loppu pienentää päivätahtiasi: nyt {E(per_day_before)} päivässä, sen jälkeen {E(per_day_after)} päivässä {until} asti.")
    elif verdict == "no":
        headline = (L(f"Not from this pay cycle's everyday money: it is {E(short_by)} more than your safe to spend. The account can take it, but the money comes from what this pay cycle was not going to touch.",
                      f"Ei tämän palkkajakson arkirahasta: se on {E(short_by)} enemmän kuin turvallinen käyttövarasi. Tili kestää sen, mutta raha tulee siitä, mihin tällä palkkajaksolla ei ollut tarkoitus koskea.")
                    if account["can_take_it"] else
                    L(f"Not before payday on {until}: it is {E(short_by)} more than your safe to spend.",
                      f"Ei ennen palkkapäivää {until}: se on {E(short_by)} enemmän kuin turvallinen käyttövarasi."))
    elif verdict == "tight":
        headline = L(f"Yes, but your pace drops from {E(per_day_before)} to {E(per_day_after)} a day until {until}. Your usual is {E(usual_day)} a day.",
                     f"Kyllä, mutta päivätahtisi putoaa: nyt {E(per_day_before)} päivässä, oston jälkeen {E(per_day_after)} päivässä {until} asti. Tavallinen tahtisi on {E(usual_day)} päivässä.")
    else:
        headline = L(f"Yes. Your pace goes from {E(per_day_before)} to {E(per_day_after)} a day until {until}, and your usual is {E(usual_day)} a day.",
                     f"Kyllä. Päivätahtisi on nyt {E(per_day_before)} ja oston jälkeen {E(per_day_after)} päivässä {until} asti, ja tavallinen tahtisi on {E(usual_day)} päivässä.")
    headline = tidy(headline)

    return {
        "amount": amount, "label": label, "basket": key,
        "verdict": verdict, "headline": headline, "short_by": short_by,
        "safe": {"before": safe_before, "after": safe_after},
        "per_day": {"before": per_day_before, "after": per_day_after},
        "usual_per_day": usual_day, "days_to_payday": days, "next_payday": s["next_payday"],
        "status": {"before": s["status"], "after": status_after},
        "from_safe_to_spend": r2(min(from_safe, safe_before)) if short_by else from_safe,
        "reserve": reserve, "account": account, "options": options, "partial_view": m.partial_view,
    }
