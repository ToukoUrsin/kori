"""Track record: was "safe to spend" actually safe?

We stand on a past day, compute safe-to-spend from only what was visible then, and replay what really
happened until the next pay arrived. The same check runs over the whole customer base (scripts/backtest.py)
and for one person over their own past months (track_record), so the coach can show its own history
instead of asking to be trusted.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd

from .. import config, data
from ..taxonomy import CATEGORIES, EVERYDAY, FIXED, SURPRISE
from .core import Money, Prefs, add_months, month_key, r2
from .insights import eur
from .query import fmt_day, month_label

_BASKET = {c: v["basket"] for c, v in CATEGORIES.items()}


def replay(m: Money, later: pd.DataFrame) -> dict | None:
    """m = the view on a past day. later = this customer's transactions after that day (hidden from m)."""
    sal = later[later["category"] == "Salary"]
    if sal.empty:
        return None
    s = m.safe
    today = m.today
    actual_pay = sal["date"].iloc[0]
    pred_pay = date.fromisoformat(s["next_payday"])
    win = later[later["date"] < actual_pay]
    b = win["category"].map(_BASKET)
    everyday_real = float(win.loc[b == EVERYDAY, "spend"].sum())
    days_real = max(1, (actual_pay - today).days)
    musts = win.loc[b.isin([FIXED, SURPRISE])].groupby("date")["spend"].sum().to_dict()

    def lowest(per_day: float) -> float:
        bal, low, d = s["balance"], s["balance"], today
        while d < actual_pay - timedelta(days=1):
            d += timedelta(days=1)
            bal -= per_day + musts.get(d, 0.0)
            low = min(low, bal)
        return low

    naive_day = max(0.0, s["balance"]) / s["days_to_payday"]
    return {
        "t": today.isoformat(), "status": s["status"], "limit": s["limit"],
        "safe": s["amount"], "per_day": s["per_day"], "balance": s["balance"],
        "pay_predicted": pred_pay.isoformat(), "pay_actual": actual_pay.isoformat(),
        "pay_exact": pred_pay == actual_pay, "pay_diff": (actual_pay - pred_pay).days,
        "fixed_pred": s["cash"]["fixed_due"], "fixed_real": r2(win.loc[b == FIXED, "spend"].sum()),
        "surprise_pred": s["cash"]["surprise_reserve"], "surprise_real": r2(win.loc[b == SURPRISE, "spend"].sum()),
        "everyday_real": r2(everyday_real), "days_real": days_real,
        "lowest_if_followed": r2(lowest(s["per_day"])),
        "held": lowest(s["per_day"]) >= 0, "naive_held": lowest(naive_day) >= 0,
        "start_ok": s["balance"] >= 0,
        "real_lowest": r2(win["balance"].min()) if len(win) else s["balance"],
        "real_negative": bool(len(win) and float(win["balance"].min()) < 0),
        "within": everyday_real <= s["per_day"] * days_real + 0.005,
    }


@lru_cache(maxsize=512)
def _rows(customer_id: str, today: date, months: int) -> tuple:
    raw = data._raw(customer_id)
    raw = raw[raw["date"] <= today]            # the coach still never sees past its own today
    out = []
    k = month_key(today)
    for i in range(1, months + 1):
        mk = add_months(k, -i)
        y, mo = int(mk[:4]), int(mk[5:7])
        d = date(y, mo, min(today.day, calendar.monthrange(y, mo)[1]))
        try:
            m = Money(customer_id, d)
            if len(m.salaries) < 3 or len(m.full_months) < 3:
                continue
            r = replay(m, raw[raw["date"] > d])
        except Exception:   # noqa: BLE001
            continue
        if r and date.fromisoformat(r["pay_actual"]) <= today:
            out.append({"month": mk, **r})
    return tuple(out)


@lru_cache(maxsize=1)
def population() -> dict | None:
    """The same check over the whole customer base (written by scripts/backtest.py)."""
    import json
    f = config.BENCH_DIR / "backtest.json"
    return json.loads(f.read_text()) if f.exists() else None


def _why(r: dict, lang: str) -> dict | None:
    """The one thing that broke a month the number did not hold."""
    if r["held"]:
        return None
    E = lambda v: eur(v, lang)
    L = lambda en, fi: en if lang == "en" else fi
    late = r["pay_diff"]
    sur, fix = r["surprise_real"] - r["surprise_pred"], r["fixed_real"] - r["fixed_pred"]
    if late > 0:
        return {"cause": "late_pay", "text": L(f"Pay came {late} days late.", f"Palkka tuli {late} päivää myöhässä.")}
    if sur >= fix:
        return {"cause": "surprise", "text": L(f"Surprises came to {E(r['surprise_real'])}; the reserve was {E(r['surprise_pred'])}.",
                                               f"Yllätyksiä tuli {E(r['surprise_real'])}; varaus oli {E(r['surprise_pred'])}.")}
    return {"cause": "bills", "text": L(f"Bills came to {E(r['fixed_real'])}; I expected {E(r['fixed_pred'])}.",
                                        f"Laskuja tuli {E(r['fixed_real'])}; odotin {E(r['fixed_pred'])}.")}


def track_record(m: Money, months: int = 11) -> dict:
    """This person's own history of the number: the same day of the month, each of the last months."""
    lang = m.prefs.lang
    rows = [dict(r) for r in _rows(m.customer_id, m.today, months)]
    rows.reverse()
    usable = [r for r in rows if r["start_ok"] and r["safe"] > 0]
    held = sum(r["held"] for r in usable)
    within = [r for r in usable if r["within"]]
    over = [r for r in usable if not r["within"]]
    items = []
    for r in rows:
        counted = bool(r["start_ok"] and r["safe"] > 0)
        why = _why(r, lang) if counted else None
        items.append({"month": r["month"], "label": month_label(r["month"], lang, long=False), "as_of": r["t"],
                      "safe": r["safe"], "per_day": r["per_day"], "days": r["days_real"],
                      "spent": r["everyday_real"], "within": r["within"], "held": r["held"],
                      "lowest_if_followed": r["lowest_if_followed"], "went_below_zero": r["real_negative"],
                      "real_lowest": r["real_lowest"], "pay_late": r["pay_diff"] > 0, "counted": counted,
                      "why": why["text"] if why else None, "cause": why["cause"] if why else None})
    causes: dict[str, int] = {}
    for it in items:
        if it["cause"]:
            causes[it["cause"]] = causes.get(it["cause"], 0) + 1
    pop = population()
    population_view = None
    if pop:
        promise = pop.get("promise", {})
        population_view = {"customers": pop.get("customers"), "cases": pop.get("cases"),
                           "held_pct": pop.get("safe_held_pct", promise.get("safe_held_pct")),
                           "balance_as_budget_pct": pop.get("balance_as_budget_held_pct", promise.get("balance_as_budget_held_pct")),
                           "labels": {"en": {"held_pct": "safe-to-spend held", "balance_as_budget_pct": "balance as budget held"},
                                      "fi": {"held_pct": "turvallinen käyttövara piti", "balance_as_budget_pct": "saldo budjettina piti"}}}
    return {
        "day_of_month": m.today.day, "months_checked": len(usable), "held": held, "missed": len(usable) - held,
        "months_number_would_have_held": held,
        "missed_because": causes,
        "stayed_within": len(within), "went_over": len(over),
        "months_stayed_within_number": len(within),
        "count_labels": {"en": {"held": "months the safe number would have held", "stayed_within": "months you actually stayed within it"},
                         "fi": {"held": "kuukaudet, jolloin turvallinen luku olisi pitänyt", "stayed_within": "kuukaudet, jolloin pysyit luvussa"}},
        "below_zero_when_within": sum(r["real_negative"] for r in within),
        "below_zero_when_over": sum(r["real_negative"] for r in over),
        "pay_late_months": sum(r["pay_diff"] > 0 for r in usable),
        "items": items, "partial_view": m.partial_view, "everyone": pop, "population": population_view,
        "method": {"en": "For each past month I stood on the same day, used only what I could see then, and replayed your "
                         "real bills, your real surprises and your real payday.",
                   "fi": "Jokaisen menneen kuukauden kohdalla seisoin samassa päivässä, käytin vain silloin näkyvissä ollutta "
                         "tietoa ja toistin todelliset laskusi, todelliset yllätyksesi ja todellisen palkkapäiväsi."}[lang],
    }
