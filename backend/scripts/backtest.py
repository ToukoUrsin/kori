"""Was "safe to spend" actually safe? A backtest on history the coach was not allowed to see.

For many customers and many past dates we stand on that date, compute safe-to-spend with only the
transactions visible then, and check it against what really happened until the next salary arrived:

  held      the customer spends exactly the safe daily amount on everyday things, the real bills and the real
            surprise costs land when they really did, pay arrives when it really did. Did the balance stay at or above zero?
  naive     same, but the customer treats the balance as the budget (spends balance / days-to-payday per day).
  payday    did we predict the right salary date?
  bills     how far was the predicted fixed total from the real one?
  status    how often did people really dip below zero after each status word (comfortable .. empty)?

    PYTHONPATH=. python scripts/backtest.py --customers 1500 --workers 12 --out ../docs/backtest.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from concurrent.futures import ProcessPoolExecutor
from datetime import date

AS_OF_DAYS = (5, 21)
MONTHS = [(2025, m) for m in (10, 11, 12)] + [(2026, m) for m in range(1, 9)]   # needs ~12 months of history and a known future


def one_customer(cid: str) -> list[dict]:
    from kori import data
    from kori.engine.core import Money
    from kori.engine.trackrecord import replay

    out = []
    try:
        raw = data._raw(cid)
    except KeyError:
        return out
    for y, mo in MONTHS:
        for day in AS_OF_DAYS:
            today = date(y, mo, day)
            try:
                m = Money(cid, today)
                if m.partial_view or len(m.salaries) < 6:
                    continue
                r = replay(m, raw[raw["date"] > today])
            except Exception:   # noqa: BLE001
                continue
            if r:
                out.append({"c": cid, **r})
    return out


def pct(n: float, d: float) -> float:
    return round(100 * n / d, 1) if d else 0.0


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    ok = [r for r in rows if r["start_ok"]]
    on_time = [r for r in ok if r["pay_exact"]]
    bills = [abs(r["fixed_pred"] - r["fixed_real"]) for r in on_time]
    bills_rel = [abs(r["fixed_pred"] - r["fixed_real"]) / r["fixed_real"] for r in on_time if r["fixed_real"] > 50]
    by_status = {}
    for st in ("comfortable", "tight", "very_tight", "empty"):
        g = [r for r in ok if r["status"] == st]
        by_status[st] = {"cases": len(g), "really_went_below_zero_pct": pct(sum(r["real_negative"] for r in g), len(g))}
    within = [r for r in ok if r["within"]]
    over = [r for r in ok if not r["within"]]
    pos = [r for r in ok if r["safe"] > 0]
    return {
        "cases": n, "customers": len({r["c"] for r in rows}),
        "as_of": {"days_of_month": list(AS_OF_DAYS), "months": [f"{y}-{m:02d}" for y, m in MONTHS]},
        "payday": {"exact_pct": pct(sum(r["pay_exact"] for r in rows), n),
                   "late_pct": pct(sum(r["pay_diff"] > 0 for r in rows), n)},
        "bills": {"cases": len(on_time), "median_abs_error_eur": round(statistics.median(bills), 2) if bills else None,
                  "within_50_eur_pct": pct(sum(x <= 50 for x in bills), len(bills)),
                  "median_rel_error_pct": round(100 * statistics.median(bills_rel), 1) if bills_rel else None},
        "promise": {
            "cases": len(pos),
            "safe_held_pct": pct(sum(r["held"] for r in pos), len(pos)),
            "safe_held_when_pay_on_time_pct": pct(sum(r["held"] for r in pos if r["pay_exact"]), sum(r["pay_exact"] for r in pos)),
            "safe_held_when_pay_late_pct": pct(sum(r["held"] for r in pos if r["pay_diff"] > 0), sum(r["pay_diff"] > 0 for r in pos)),
            "balance_as_budget_held_pct": pct(sum(r["naive_held"] for r in pos), len(pos)),
        },
        "real_life": {
            "stayed_within_safe": {"cases": len(within), "went_below_zero_pct": pct(sum(r["real_negative"] for r in within), len(within))},
            "spent_more_than_safe": {"cases": len(over), "went_below_zero_pct": pct(sum(r["real_negative"] for r in over), len(over))},
        },
        "status_words": by_status,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--customers", type=int, default=1500)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None)
    ap.add_argument("--public", default=None, help="small summary for the app, e.g. ../data/benchmarks/backtest.json")
    a = ap.parse_args()
    from kori import data
    ids = list(data.all_customers()["customer_id"])
    random.Random(a.seed).shuffle(ids)
    ids = ids[: a.customers]
    rows: list[dict] = []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(one_customer, ids, chunksize=8)):
            rows.extend(r)
            if i and i % 250 == 0:
                print(f"{i}/{len(ids)} customers, {len(rows)} cases", flush=True)
    summary = summarise(rows)
    print(json.dumps(summary, indent=2))
    if a.out:
        with open(a.out, "w") as f:
            json.dump(summary, f, indent=2)
    if a.public:      # the few figures the app shows next to a personal track record
        p = summary["promise"]
        with open(a.public, "w") as f:
            json.dump({"cases": p["cases"], "customers": summary["customers"], "safe_held_pct": p["safe_held_pct"],
                       "balance_as_budget_held_pct": p["balance_as_budget_held_pct"],
                       "status_words": {k: v["really_went_below_zero_pct"] for k, v in summary["status_words"].items()}}, f, indent=2)


if __name__ == "__main__":
    main()
