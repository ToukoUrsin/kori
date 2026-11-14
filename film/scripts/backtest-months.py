"""The backtest of docs/backtest.json, month by month, for the film's proof scene.

Runs the app's own replay (backend/scripts/backtest.py: one_customer, summarise) over every customer and keeps,
for each of the eleven replayed months, how many replays and customers it added and the running share of cases
where "safe to spend" held and where "balance as budget" held. The last month's running totals must equal
docs/backtest.json, or the script fails.

    cd backend && PYTHONPATH=.:scripts .venv/bin/python ../film/scripts/backtest-months.py --workers 16
"""
from __future__ import annotations

import argparse
import json
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from backtest import MONTHS, one_customer, summarise, pct  # backend/scripts/backtest.py

FILM = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    from kori import data
    ids = list(data.all_customers()["customer_id"])
    random.Random(a.seed).shuffle(ids)
    rows: list[dict] = []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(one_customer, ids, chunksize=8)):
            rows.extend(r)
            if i and i % 500 == 0:
                print(f"{i}/{len(ids)} customers, {len(rows)} cases", flush=True)
    total = summarise(rows)
    want = json.loads((FILM.parent / "docs/backtest.json").read_text())
    for k in ("cases", "customers"):
        assert total[k] == want[k], (k, total[k], want[k])
    for k in ("cases", "safe_held_pct", "balance_as_budget_held_pct"):
        assert total["promise"][k] == want["promise"][k], (k, total["promise"][k], want["promise"][k])
    months = []
    seen: set[str] = set()
    cum: list[dict] = []
    for y, mo in MONTHS:
        key = f"{y}-{mo:02d}"
        mine = [r for r in rows if r["t"].startswith(key)]
        cum += mine
        seen |= {r["c"] for r in mine}
        pos = [r for r in cum if r["start_ok"] and r["safe"] > 0]
        pos_m = [r for r in mine if r["start_ok"] and r["safe"] > 0]
        months.append({
            "month": key, "cases": len(mine), "cases_total": len(cum), "customers_total": len(seen),
            "promise_cases_total": len(pos),
            "safe_held_pct_month": pct(sum(r["held"] for r in pos_m), len(pos_m)),
            "balance_held_pct_month": pct(sum(r["naive_held"] for r in pos_m), len(pos_m)),
            "safe_held_pct_total": pct(sum(r["held"] for r in pos), len(pos)),
            "balance_held_pct_total": pct(sum(r["naive_held"] for r in pos), len(pos)),
        })
        print(months[-1], flush=True)
    out = {"source": "backend/scripts/backtest.py (one_customer, summarise), every customer, per as-of month",
           "matches": "docs/backtest.json", "cases": total["cases"], "customers": total["customers"],
           "promise": total["promise"], "months": months}
    (FILM / "src/data/backtest-months.json").write_text(json.dumps(out, indent=1))
    print("written", FILM / "src/data/backtest-months.json")


if __name__ == "__main__":
    main()
