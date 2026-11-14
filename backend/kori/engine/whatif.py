"""What-if simulator. Everything is replayed on this person's own typical month."""
from __future__ import annotations

from ..taxonomy import BASKETS, CATEGORIES, EVERYDAY, FIXED, KINDS, SURPRISE, cat_label, kind_label
from .core import DAYS_PER_MONTH, Money, r2


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
    months = int(max(1, min(120, months)))
    lines, monthly_freed, one_off_total, extra_saving = [], 0.0, 0.0, 0.0
    everyday_change = 0.0
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
            lines.append({"type": t, "label": ch.get("label") or {"en": "New monthly cost", "fi": "Uusi kuukausimeno"}[lang],
                          "basket": ch.get("basket") or FIXED, "from_monthly": 0.0, "to_monthly": amt, "monthly_change": -amt})
            monthly_freed -= amt
        elif t == "income":
            amt = r2(float(ch["monthly"]))
            lines.append({"type": t, "label": {"en": "Income change", "fi": "Tulojen muutos"}[lang],
                          "from_monthly": m.income_typical, "to_monthly": r2(m.income_typical + amt), "monthly_change": amt})
            monthly_freed += amt
        elif t == "one_off":
            amt = r2(float(ch["amount"]))
            lines.append({"type": t, "label": ch.get("label") or {"en": "One-off cost", "fi": "Kertameno"}[lang], "amount": amt})
            one_off_total += amt
        elif t == "save":
            amt = r2(float(ch["monthly"]))
            lines.append({"type": t, "label": {"en": "Extra saving", "fi": "Lisäsäästö"}[lang], "monthly_change": -amt, "to_monthly": amt})
            extra_saving += amt
        else:
            raise ValueError(f"unknown change type '{t}'")

    base_left = m.usual["left_over"]
    new_left = r2(base_left + monthly_freed - extra_saving)
    base_day = r2((m.income_typical - m.usual[FIXED] - m.usual[SURPRISE] - m.savings_plan) / DAYS_PER_MONTH)
    non_everyday = monthly_freed - everyday_change
    new_day = r2(base_day + (non_everyday - extra_saving) / DAYS_PER_MONTH)

    # month by month: money set aside (or the hole) compared with changing nothing
    series, cum_base, cum_new = [], 0.0, -one_off_total
    for k in range(0, months + 1):
        if k:
            cum_base += base_left
            cum_new += base_left + monthly_freed
        series.append({"month": k, "baseline": r2(cum_base), "scenario": r2(cum_new)})
    total_effect = r2(monthly_freed * months - one_off_total)

    musts = r2(m.usual[FIXED] + m.usual[SURPRISE])
    out = {
        "changes": lines, "months": months,
        "monthly_effect": r2(monthly_freed), "yearly_effect": r2(monthly_freed * 12),
        "one_off_total": r2(one_off_total), "total_effect_over_period": total_effect,
        "left_over": {"now": base_left, "after": new_left},
        "everyday_per_day": {"now": base_day, "after": new_day},
        "series": series,
        "usual_month": {"income": m.income_typical, "fixed": m.usual[FIXED], "surprise": m.usual[SURPRISE],
                        "everyday": m.usual[EVERYDAY], "saving": m.usual["invested"]},
    }
    # one-off: can the buffer take it, and how long to rebuild
    if one_off_total > 0:
        after = r2(m.balance - one_off_total)
        monthly_room = base_left + monthly_freed
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
        room_now = max(0.0, base_left)
        room_new = max(0.0, base_left + monthly_freed)
        out["goal"] = {"name": goal_name or {"en": "your goal", "fi": "tavoitteesi"}[lang], "amount": r2(g),
                       "months_now": round((g + 0) / room_now, 1) if room_now > 0 else None,
                       "months_after": round((g + one_off_total) / room_new, 1) if room_new > 0 else None}
    return out
