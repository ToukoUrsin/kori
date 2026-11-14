"""What-if simulator. Everything is replayed on this person's own typical month."""
from __future__ import annotations

from ..taxonomy import BASKETS, CATEGORIES, EVERYDAY, FIXED, KINDS, SURPRISE, cat_label, kind_label
from datetime import date

from .core import DAYS_PER_MONTH, Money, r2
from .insights import eur, tidy
from .query import fmt_day


def _baseline(m: Money, target: str) -> tuple[float, str, str]:
    """Typical monthly euros for a category, kind or basket -> (amount, label, basket)."""
    lang = m.prefs.lang
    if target in CATEGORIES:
        return m.usual["categories"][target], cat_label(target, lang), m._basket_of(target)
    if target in KINDS:
        months = m.last_full_months(6)
        d = m.df[(m.df["kind"] == target) & (m.df["month"].isin(months))]
        base = r2(d["spend"].sum() / max(1, len(months)))
        return base, kind_label(target, lang), m._basket_of(KINDS[target]["category"])
    if target in BASKETS:
        return m.usual[target], BASKETS[target][lang], target
    raise ValueError(f"unknown target '{target}'. Use a category {list(CATEGORIES)}, a kind {sorted(KINDS)} or a basket {list(BASKETS)}.")


NEEDS = {"cut": ("target", "pct"), "set": ("target", "monthly"), "add_cost": ("monthly",), "income": ("monthly",),
         "one_off": ("amount",), "save": ("monthly",)}
ALIASES = {"category": "target", "kind": "target", "percent": "pct", "percentage": "pct", "name": "label",
           "amount_monthly": "monthly", "per_month": "monthly"}


def _norm(ch: dict) -> dict:
    """Accept the common spellings of a change and fail with a readable message, never a KeyError."""
    if not isinstance(ch, dict):
        raise ValueError("each change must be an object")
    out = {ALIASES.get(k, k): v for k, v in ch.items() if v is not None}
    t = out.get("type")
    if t not in NEEDS:
        raise ValueError(f"unknown change type '{t}'. Use one of {sorted(NEEDS)}.")
    missing = [k for k in NEEDS[t] if k not in out]
    if missing:
        raise ValueError(f"change '{t}' needs {', '.join(missing)}")
    for k in ("pct", "monthly", "amount"):
        if k in out:
            try:
                out[k] = float(out[k])
            except (TypeError, ValueError):
                raise ValueError(f"'{k}' must be a number") from None
    return out


def _safe_effect(m: Money, limit_change: float, everyday_change: float, one_off_total: float, one_off_basket: str | None) -> dict:
    """What the changes do to safe to spend.

    Safe to spend is a limit: what a pay cycle's income leaves for everyday after musts, the surprise reserve and saving.
    More income, a new fixed cost or a monthly saving move the limit. Spending less on an everyday category does not move
    it: it changes how fast the same limit is used. A one-off hits today's number.
    """
    from .afford import afford          # local import: afford imports this package's core
    lang = m.prefs.lang
    L = lambda en, fi: en if lang == "en" else fi
    E = lambda v, cents=False: eur(v, lang, cents)
    s = m.safe
    partial = m.partial_view
    pay = date.fromisoformat(s["next_payday"])
    cycle_days = s["budget"]["cycle_days"]
    cycle_now = s["budget"]["everyday_budget"]
    cycle_delta = r2(limit_change * cycle_days / DAYS_PER_MONTH)
    cycle_after = r2(cycle_now + cycle_delta)
    day_change = r2(limit_change / DAYS_PER_MONTH)
    budget_after = r2(s["budget"]["left"] + cycle_delta)
    safe_after = r2(max(0.0, min(s["cash"]["free"], budget_after))) if not partial else s["amount"]
    kind = ("limit_and_pace" if abs(limit_change) >= 0.005 and abs(everyday_change) >= 0.005 else
            "limit" if abs(limit_change) >= 0.005 else "pace" if abs(everyday_change) >= 0.005 else
            "one_off" if one_off_total > 0 else "none")
    out = {
        "kind": kind,
        "per_cycle": {"now": None if partial else cycle_now, "after": None if partial else cycle_after, "change": cycle_delta},
        "per_day": {"now": None if partial else r2(cycle_now / cycle_days),
                    "after": None if partial else r2(max(0.0, cycle_after) / cycle_days), "change": day_change},
        "safe_to_spend": {"before": s["amount"], "after": safe_after,
                          "change": r2(safe_after - s["amount"]),
                          "per_day_before": s["per_day"], "per_day_after": r2(safe_after / s["days_to_payday"])},
        "today": {"amount": s["amount"], "per_day": s["per_day"], "until": s["next_payday"], "changes_now": bool(one_off_total > 0)},
        "starts": s["next_payday"], "partial_view": partial,
    }
    texts = []
    if abs(limit_change) >= 0.005:
        more = limit_change > 0
        if partial:
            texts.append(L(f"On this account, a full pay cycle has {E(abs(limit_change))} {'more' if more else 'less'} for everyday, about "
                           f"{E(abs(day_change), True)} a day. I only see part of your money, so I cannot give the whole figure.",
                           f"Tällä tilillä koko palkkajaksossa on {E(abs(limit_change))} {'enemmän' if more else 'vähemmän'} arkeen, noin "
                           f"{E(abs(day_change), True)} päivässä. Näen vain osan rahoistasi, joten en voi antaa koko lukua."))
        elif cycle_after < 0:
            texts.append(L(f"Safe to spend for a full pay cycle would go from {E(cycle_now)} to nothing: the musts and the saving would be "
                           f"{E(-cycle_after)} more than your income.",
                           f"Koko palkkajakson turvallinen käyttövara putoaisi {E(cycle_now)}:sta nollaan: pakolliset menot ja säästö olisivat "
                           f"{E(-cycle_after)} enemmän kuin tulosi."))
        else:
            texts.append(L(f"Safe to spend for a full pay cycle goes from {E(cycle_now)} to {E(cycle_after)}: "
                           f"{E(abs(day_change), True)} {'more' if more else 'less'} a day.",
                           f"Koko palkkajakson turvallinen käyttövara muuttuu: nyt {E(cycle_now)}, sen jälkeen {E(cycle_after)}. Se on "
                           f"{E(abs(day_change), True)} {'enemmän' if more else 'vähemmän'} päivässä."))
        if not one_off_total:
            texts.append(L(f"Today's number, {E(s['amount'])} until {fmt_day(pay, lang)}, changes only when the change starts.",
                           f"Tämän päivän luku, {E(s['amount'])} {fmt_day(pay, lang)} asti, muuttuu vasta kun muutos alkaa."))
    if abs(everyday_change) >= 0.005:
        now, after = m.usual[EVERYDAY], r2(m.usual[EVERYDAY] - everyday_change)
        out["everyday_usual"] = {"monthly": {"now": now, "after": after}, "monthly_change": r2(-everyday_change),
                                 "per_day_change": r2(-everyday_change / DAYS_PER_MONTH)}
        less = everyday_change > 0
        texts.append(L(f"{'It does not change the safe to spend limit' if kind == 'pace' else 'On top of that'}: your usual everyday month goes "
                       f"from {E(now)} to {E(after)}, so about {E(abs(everyday_change) / DAYS_PER_MONTH, True)} a day "
                       f"{'stays unspent' if less else 'more is used'}.",
                       f"{'Se ei muuta turvallisen käyttövaran rajaa' if kind == 'pace' else 'Lisäksi'}: tavallinen arkikuukautesi muuttuu, nyt "
                       f"{E(now)} ja sen jälkeen {E(after)}, joten noin {E(abs(everyday_change) / DAYS_PER_MONTH, True)} päivässä "
                       f"{'jää käyttämättä' if less else 'kuluu enemmän'}."))
    if one_off_total > 0:
        a = afford(m, one_off_total, basket="everyday" if one_off_basket == EVERYDAY else "surprise")
        out["today"].update({"amount_after": a["safe"]["after"], "per_day_after": a["per_day"]["after"], "short_by": a["short_by"],
                             "verdict": a["verdict"], "reserve": a["reserve"], "usual_per_day": a["usual_per_day"]})
        texts.append(a["headline"])
    if not texts:
        texts.append(L("This does not change safe to spend.", "Tämä ei muuta turvallista käyttövaraa."))
    out["text"] = tidy(" ".join(texts))
    return out


def what_if(m: Money, changes: list[dict], months: int = 12, goal_amount: float | None = None,
            goal_name: str | None = None) -> dict:
    """Apply changes to the typical month and show what it does to money left over.

    change types:
      {"type": "cut", "target": "Restaurants", "pct": 20}          spend 20% less (negative pct = more)
      {"type": "set", "target": "taxi", "monthly": 30}             cap a category/kind at a monthly amount
      {"type": "add_cost", "label": "Car lease", "monthly": 350}   a new monthly cost
      {"type": "income", "monthly": 200}                           income goes up (or down) by this much
      {"type": "one_off", "label": "New washing machine", "amount": 600}   a single hit (a surprise or a purchase)
      {"type": "save", "monthly": 150}                             move this much to savings every month
    """
    lang = m.prefs.lang
    L = lambda en, fi: en if lang == "en" else fi
    E = lambda v, cents=False: eur(v, lang, cents)
    months = int(max(1, min(120, months)))
    lines, monthly_freed, one_off_total, extra_saving = [], 0.0, 0.0, 0.0
    everyday_change = 0.0
    one_off_basket = None
    partial = m.partial_view
    for ch in changes:
        ch = _norm(ch)
        t = ch["type"]
        if t in ("cut", "set"):
            base, label, basket = _baseline(m, ch["target"])
            new = r2(base * (1 - float(ch.get("pct", 0)) / 100)) if t == "cut" else r2(min(base, float(ch["monthly"])) if float(ch["monthly"]) >= 0 else base)
            if t == "set":
                new = r2(float(ch["monthly"]))
            new = max(0.0, new)
            freed = r2(base - new)
            lines.append({"type": t, "target": ch["target"], "label": label, "basket": basket,
                          "pct": ch.get("pct"), "from_monthly": base, "to_monthly": new, "monthly_change": freed})
            monthly_freed += freed
            if basket == EVERYDAY:
                everyday_change += freed
        elif t == "add_cost":
            amt = r2(float(ch["monthly"]))
            basket = ch.get("basket") if ch.get("basket") in BASKETS else FIXED
            lines.append({"type": t, "label": ch.get("label") or {"en": "New monthly cost", "fi": "Uusi kuukausimeno"}[lang],
                          "basket": basket, "from_monthly": 0.0, "to_monthly": amt, "monthly_change": -amt})
            monthly_freed -= amt
            if basket == EVERYDAY:
                everyday_change -= amt
        elif t == "income":
            amt = r2(float(ch["monthly"]))
            lines.append({"type": t, "label": {"en": "Income change", "fi": "Tulojen muutos"}[lang],
                          "from_monthly": m.income_typical, "to_monthly": r2(m.income_typical + amt), "monthly_change": amt})
            monthly_freed += amt
        elif t == "one_off":
            amt = r2(float(ch["amount"]))
            basket = EVERYDAY if ch.get("basket") == EVERYDAY else SURPRISE
            lines.append({"type": t, "label": ch.get("label") or {"en": "One-off cost", "fi": "Kertameno"}[lang], "amount": amt,
                          "basket": basket})
            one_off_total += amt
            one_off_basket = basket if one_off_basket in (None, basket) else EVERYDAY
        elif t == "save":
            amt = r2(float(ch["monthly"]))
            lines.append({"type": t, "label": {"en": "Extra saving", "fi": "Lisäsäästö"}[lang], "monthly_change": -amt, "to_monthly": amt})
            extra_saving += amt
        else:
            raise ValueError(f"unknown change type '{t}'")

    net_monthly = r2(monthly_freed - extra_saving)
    base_left = m.usual["left_over"]
    new_left = r2(base_left + net_monthly)
    base_day = r2((m.income_typical - m.usual[FIXED] - m.usual[SURPRISE] - m.savings_plan) / DAYS_PER_MONTH)
    non_everyday = monthly_freed - everyday_change
    new_day = r2(base_day + (non_everyday - extra_saving) / DAYS_PER_MONTH)

    # month by month: money set aside (or the hole) compared with changing nothing.
    # With a partial view the usual month is not this person's whole month, so only the change itself is drawn.
    step_base = 0.0 if partial else base_left
    series, cum_base, cum_new = [], 0.0, -one_off_total
    for k in range(0, months + 1):
        if k:
            cum_base += step_base
            cum_new += step_base + net_monthly
        series.append({"month": k, "baseline": r2(cum_base), "scenario": r2(cum_new)})
    total_effect = r2(net_monthly * months - one_off_total)

    musts = r2(m.usual[FIXED] + m.usual[SURPRISE])
    out = {
        "changes": lines, "months": months,
        "monthly_effect": net_monthly, "yearly_effect": r2(net_monthly * 12),
        "one_off_total": r2(one_off_total), "total_effect_over_period": total_effect,
        "left_over": {"now": None if partial else base_left, "after": None if partial else new_left},
        "everyday_per_day": {"now": None if partial else base_day, "after": None if partial else new_day},
        "series": [] if partial else series,
        "usual_month_window": m.usual.get("window", "last 6 complete months"),
        "usual_month": {"income": m.income_typical, "fixed": m.usual[FIXED], "surprise": m.usual[SURPRISE],
                        "everyday": m.usual[EVERYDAY], "saving": m.usual["invested"]},
        "partial_view": partial,
        "projection": {"meaningful": not partial,
                       "reason": None if not partial else L(
                           "Most of your salary moves to another bank, so I only see part of your month. The lines show what this "
                           "change alone adds up to, not where your money will be.",
                           "Suurin osa palkastasi siirtyy toiseen pankkiin, joten näen vain osan kuukaudestasi. Viivat näyttävät, "
                           "mitä tämä muutos yksin tekee, eivät sitä, missä rahasi ovat.")},
        "safe_effect": _safe_effect(m, r2(non_everyday - extra_saving), r2(everyday_change), one_off_total, one_off_basket),
    }
    if extra_saving > 0:
        room = max(0.0, base_left + monthly_freed)
        from_left = r2(min(extra_saving, room))
        trim = r2(extra_saving - from_left)
        out["saving"] = {"monthly": r2(extra_saving), "yearly": r2(extra_saving * 12),
                         "from_left_over": None if partial else from_left, "from_trim": None if partial else trim,
                         "fits": None if partial else bool(trim <= 0.005)}
    if new_left < -0.005 and not partial:
        # the month no longer adds up: say exactly how much is missing and what that is per day
        gap = r2(-new_left)
        every_now = r2(m.usual[EVERYDAY] - everyday_change)
        every_need = r2(max(0.0, every_now - gap))
        already = r2(max(0.0, -base_left))
        # the pace she really spends at, and the same pace less the trim, so the two figures differ by exactly the trim
        trim_day = r2(gap / DAYS_PER_MONTH)
        pace_now = r2(every_now / DAYS_PER_MONTH)
        pace_need = r2(max(0.0, pace_now - trim_day))
        out["gap"] = {
            "monthly": gap, "per_day": trim_day, "trim_per_day": trim_day,
            "everyday_per_day_before": pace_now, "everyday_per_day_after": pace_need,
            "already_short_monthly": already,
            "everyday_usual_monthly": every_now, "everyday_needed_monthly": every_need,
            "text": (L(f"A usual month leaves you {E(base_left)}, so this is {E(gap)} a month more than fits. To make it fit, everyday "
                       f"spending has to come down by {E(gap)} a month, about {E(gap / DAYS_PER_MONTH, True)} a day: your everyday pace goes "
                       f"from {E(pace_now, True)} to {E(pace_need, True)} a day.",
                       f"Tavallisesta kuukaudestasi jää {E(base_left)}, joten tämä on {E(gap)} kuussa enemmän kuin mahtuu. Jotta se mahtuisi, "
                       f"arjen menojen pitää pienentyä {E(gap)} kuussa eli noin {E(gap / DAYS_PER_MONTH, True)} päivässä: päivätahti muuttuu "
                       f"{E(pace_now, True)} eurosta {E(pace_need, True)} euroon.")
                     if already <= 0.005 else
                     L(f"Your usual month is already {E(already)} short. With this change it would be {E(gap)} a month short, "
                       f"about {E(gap / DAYS_PER_MONTH, True)} a day.",
                       f"Tavallinen kuukautesi on jo {E(already)} miinuksella. Tämän muutoksen kanssa vajaus olisi {E(gap)} kuussa "
                       f"eli noin {E(gap / DAYS_PER_MONTH, True)} päivässä.")),
        }
    # one-off: can the buffer take it, and how long to rebuild
    if one_off_total > 0:
        after = r2(m.balance - one_off_total)
        monthly_room = (base_left + net_monthly) if not partial else 0.0
        out["one_off"] = {
            "balance_now": m.balance, "balance_after": after, "covered_by_balance": bool(after >= m.cushion),
            "surprise_reserve_monthly": m.usual[SURPRISE],
            "months_of_reserve": round(one_off_total / m.usual[SURPRISE], 1) if m.usual[SURPRISE] > 0 else None,
            "months_to_rebuild": round(one_off_total / monthly_room, 1) if monthly_room > 0 else None,
            "musts_covered_after_months": round(max(0.0, after) / musts, 1) if musts > 0 else None,
        }
    # translate the monthly effect into things this person already pays for
    if abs(monthly_freed) >= 1:
        yearly = abs(monthly_freed) * 12
        eq = []
        housing = m.usual["categories"].get("Housing", 0)
        groc = m.usual["categories"].get("Groceries", 0)
        if housing > 0:
            eq.append({"what": {"en": "months of housing costs", "fi": "kuukauden asumiskulut"}[lang], "count": round(yearly / housing, 1)})
        if groc > 0:
            eq.append({"what": {"en": "weeks of groceries", "fi": "viikon ruokaostokset"}[lang], "count": round(yearly / (groc / 4.35), 1)})
        if m.usual[SURPRISE] > 0:
            eq.append({"what": {"en": "months of your surprise reserve", "fi": "kuukauden yllätysvara"}[lang],
                       "count": round(yearly / m.usual[SURPRISE], 1)})
        out["yearly_equals"] = eq
    saved_monthly = max(0.0, monthly_freed) + extra_saving
    if saved_monthly > 0:
        # plain arithmetic, no market promise: what the pile is with 0% and with an example 4% yearly return
        def fv(p, years, rate):
            n = years * 12
            if rate == 0:
                return r2(p * n)
            i = rate / 12
            return r2(p * ((1 + i) ** n - 1) / i)
        out["if_set_aside"] = {"monthly": r2(saved_monthly),
                               "years": [{"years": y, "no_return": fv(saved_monthly, y, 0), "example_4pct": fv(saved_monthly, y, 0.04)}
                                         for y in (1, 5, 10)],
                               "note": {"en": "The 4% line is an example for learning how compounding works, not a forecast or advice.",
                                        "fi": "4 %:n rivi on esimerkki korkoa korolle -ilmiöstä, ei ennuste eikä sijoitusneuvo."}[lang]}
    if goal_amount:
        g = float(goal_amount)
        room_now = max(0.0, base_left) if not partial else 0.0
        room_new = max(0.0, base_left + monthly_freed) if not partial else 0.0
        out["goal"] = {"name": goal_name or {"en": "your goal", "fi": "tavoitteesi"}[lang], "amount": r2(g),
                       "months_now": round((g + 0) / room_now, 1) if room_now > 0 else None,
                       "months_after": round((g + one_off_total) / room_new, 1) if room_new > 0 else None,
                       "months_at_saving": round(g / extra_saving, 1) if extra_saving > 0 else None}
    return out
