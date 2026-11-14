"""People like you: anonymous comparison with other customers, plus Statistics Finland.

Groups are never smaller than MIN_GROUP people; when a group is too small it widens.
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from .. import config
from ..taxonomy import BASKETS, CATEGORIES, cat_label
from .core import Money, r2

MIN_GROUP = 30

METRICS = {**{f"cat_{c}": c for c in CATEGORIES}, "fixed": "fixed", "surprise": "surprise", "everyday": "everyday",
           "spend": "spend", "invested": "invested", "salary": "salary"}


@lru_cache(maxsize=1)
def table() -> pd.DataFrame:
    return pd.read_parquet(config.BUILD_DIR / "peers.parquet").set_index("customer_id")


@lru_cache(maxsize=1)
def statfin() -> dict | None:
    p = config.BENCH_DIR / "statfin.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


@lru_cache(maxsize=4)
def usual_table(today=None) -> pd.DataFrame:
    """A usual month for every customer, measured exactly as `Money.usual` measures it for one:
    the middle (median) of the last 6 full months for fixed musts and everyday, the average of the last 12 for
    surprise musts, the average of the last 6 for each category, and the middle one of the last 6 pay amounts.
    So "you" and "people like you" are always compared on the same definition."""
    from datetime import date
    from ..data import _lock, con
    from ..taxonomy import EVERYDAY, FIXED, SURPRISE
    from .core import add_months, month_bounds, month_key
    today = today or config.DEMO_TODAY
    this = month_key(today)
    m6 = [add_months(this, -i) for i in range(6, 0, -1)]
    m12 = [add_months(this, -i) for i in range(12, 0, -1)]
    start = month_bounds(m12[0])[0]
    end = date(today.year, today.month, 1)
    with _lock:
        agg = con().execute(
            "select customer_id, strftime(tx_date, '%Y-%m') as ym, category, sum(amount) as amt from tx "
            "where tx_date >= ? and tx_date < ? group by 1, 2, 3", [start, end]).df()
        sal = con().execute(
            "select customer_id, median(amount) as salary from (select customer_id, amount, row_number() over "
            "(partition by customer_id order by ts desc) as rn from tx where category = 'Salary' and tx_date <= ?) "
            "where rn <= 6 group by 1", [today]).df().set_index("customer_id")["salary"]
    ids = pd.Index(sorted(agg["customer_id"].unique()), name="customer_id")
    wide = agg.pivot_table(index=["customer_id", "ym"], columns="category", values="amt", aggfunc="sum").fillna(0.0)
    full = pd.MultiIndex.from_product([ids, m12], names=["customer_id", "ym"])
    wide = wide.reindex(full).fillna(0.0)
    spend = lambda c: -wide[c] if c in wide.columns else pd.Series(0.0, index=wide.index)
    basket = lambda b: sum((spend(c) for c, v in CATEGORIES.items() if v["basket"] == b), pd.Series(0.0, index=wide.index))
    last6 = wide.index.get_level_values("ym").isin(m6)
    out = pd.DataFrame(index=ids)
    for c in CATEGORIES:
        out[f"cat_{c}"] = spend(c)[last6].groupby(level=0).mean()
    out["fixed"] = basket(FIXED)[last6].groupby(level=0).median()
    out["everyday"] = basket(EVERYDAY)[last6].groupby(level=0).median()
    out["surprise"] = basket(SURPRISE).groupby(level=0).mean()
    inv = spend("Invest Deposit")[last6]
    habit = (inv > 0).groupby(level=0).sum() >= 4
    out["invested"] = inv.groupby(level=0).median().where(habit, 0.0)
    out["salary"] = sal.reindex(ids).fillna(0.0)
    out["swept"] = spend("Salary Sweep")[last6].groupby(level=0).median()
    out["income"] = out["salary"] - out["swept"]
    out["spend"] = out["fixed"] + out["surprise"] + out["everyday"]
    return out.round(2)


def usual_window(lang: str = "en") -> str:
    return {"en": "A usual month: the middle of your last 6 full months (surprise musts: the average of the last 12)",
            "fi": "Tavallinen kuukausi: viimeisten 6 täyden kuukauden keskimmäinen (yllättävät pakolliset: 12 kuukauden keskiarvo)"}[lang]


def row(customer_id: str) -> pd.Series:
    return table().loc[customer_id]


def group_of(customer_id: str, by: str = "age") -> tuple[pd.DataFrame, str, str]:
    """Peer group for a customer -> (rows, key, human label)."""
    t = table()
    me = t.loc[customer_id]
    full = t[t["sweep_share"] < 0.5]          # leave out people whose money mostly lives elsewhere
    if by == "age_income":
        g = full[(full["age_band"] == me["age_band"]) & (full["income_band"] == me["income_band"])]
        if len(g) >= MIN_GROUP:
            return g, by, f"aged {me['age_band']} with a similar income"
        by = "age"
    if by == "income":
        g = full[full["income_band"] == me["income_band"]]
        if len(g) >= MIN_GROUP:
            return g, by, "with a similar income"
        by = "everyone"
    if by == "area":
        g = full[full["area"] == me["area"]]
        if len(g) >= MIN_GROUP:
            return g, by, f"in {me['area']}"
        by = "everyone"
    if by == "age":
        g = full[full["age_band"] == me["age_band"]]
        if len(g) >= MIN_GROUP:
            return g, by, f"aged {me['age_band']}"
    return full, "everyone", "of all ages"


def _statfin_age_key(age: int) -> str:
    for hi, k in ((25, "17-24"), (35, "25-34"), (45, "35-44"), (55, "45-54"), (65, "55-64"), (75, "65-74"), (85, "75-84")):
        if age < hi:
            return k
    return "85-"


def national(age: int, category: str) -> dict | None:
    """Statistics Finland Household Budget Survey 2022, per consumption unit, in 2026 euros."""
    s = statfin()
    if not s:
        return None
    try:
        k = _statfin_age_key(age)
        g = s["by_age_group"][k]
        v = g["per_consumption_unit"]["app_categories"][category]
        eur = v.get("eur_month_2026_category_cpi") or v.get("eur_month_2026")
        if eur is None:
            return None
        return {"eur_month": r2(eur), "group": g.get("label", k).replace(" ", ""), "survey_year": s["meta"].get("survey_year", 2022),
                "source": "Statistics Finland, Household Budget Survey", "basis": "per consumption unit, 2026 prices"}
    except (KeyError, TypeError):
        return None


def compare(m: Money, by: str = "age", categories: list[str] | None = None) -> dict:
    """You vs people like you, using the same usual-month window as the personal engine."""
    lang = m.prefs.lang
    g, key, label = group_of(m.customer_id, by)
    me = row(m.customer_id)
    # Compare the customer and peers on the same window used by Money.usual.
    # The peer cohort selection still comes from the stable peer table, while
    # each amount comes from the deterministic six-month usual-month table.
    usual = usual_table()
    group_usual = usual.reindex(g.index).dropna(how="all")
    me_usual = usual.loc[m.customer_id]
    cats = categories or list(CATEGORIES)
    items = []

    def one(col: str, name: str, lab: str, icon: str | None = None, cat: str | None = None):
        source = group_usual[col] if col in group_usual else g[col]
        vals = source.dropna().to_numpy(dtype=float)
        you = float(me_usual[col] if col in me_usual.index else me[col])
        med = float(np.median(vals))
        item = {"key": name, "label": lab, "you": r2(you), "median": r2(med),
                "p25": r2(np.percentile(vals, 25)), "p75": r2(np.percentile(vals, 75)),
                "percentile": int(round(100 * float((vals < you).mean()))),
                "diff": r2(you - med), "diff_pct": round(100 * (you - med) / med) if med > 0 else None}
        if icon:
            item["icon"] = icon
        if cat:
            nat = national(m.customer.age, cat)
            if nat:
                item["finland"] = nat
        return item

    for c in cats:
        if c in CATEGORIES:
            items.append(one(f"cat_{c}", c, cat_label(c, lang), CATEGORIES[c]["icon"], c))
    baskets = [one(b, b, BASKETS[b][lang]) for b in BASKETS]
    extra = {"saving": one("invested", "invested", {"en": "Moved to savings", "fi": "Säästöön siirretty"}[lang]),
             "income": one("income", "income", {"en": "Monthly income", "fi": "Kuukausitulot"}[lang])}
    items.sort(key=lambda x: -(x["diff"]))
    return {"group": {"by": key, "label": label, "size": int(len(g)), "min_group_size": MIN_GROUP},
            "window": usual_window(lang),
            "categories": items, "baskets": baskets, **extra,
            "note": {"en": "Peers are other customers in this dataset; nobody is identifiable and groups are never smaller than 30 people.",
                     "fi": "Vertailuryhmä on muita asiakkaita; ketään ei voi tunnistaa eikä ryhmä ole koskaan alle 30 henkeä."}[lang]}


def percentile_of(customer_id: str, col: str, group: pd.DataFrame | None = None) -> int:
    t = group if group is not None else table()
    vals = t[col].dropna().to_numpy(dtype=float)
    you = float(table().loc[customer_id, col]) if pd.notna(table().loc[customer_id, col]) else 0.0
    return int(round(100 * float((vals < you).mean())))
