"""Free exploration of one's own transactions (the MyData part).

One flexible, deterministic query: filter by time, category, kind, basket, merchant, size,
weekday or hour; group by almost anything; compare with an earlier period.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

import pandas as pd

from ..taxonomy import BASKETS, CATEGORIES, KINDS, cat_label, kind_label
from .core import Money, add_months, month_bounds, month_key, r2

WEEKDAYS = {"en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "fi": ["ma", "ti", "ke", "to", "pe", "la", "su"]}
MONTHS = {"en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
          "fi": ["tammi", "helmi", "maalis", "huhti", "touko", "kesä", "heinä", "elo", "syys", "loka", "marras", "joulu"]}
MONTHS_LONG = {"en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                      "November", "December"],
               "fi": ["tammikuu", "helmikuu", "maaliskuu", "huhtikuu", "toukokuu", "kesäkuu", "heinäkuu", "elokuu",
                      "syyskuu", "lokakuu", "marraskuu", "joulukuu"]}
PERIODS = ["today", "yesterday", "this_week", "last_week", "this_month", "last_month", "last_30_days", "last_90_days",
           "last_3_months", "last_6_months", "last_12_months", "this_year", "last_year", "since_payday", "all"]
SIZE_BUCKETS = [(0, 10, "under €10"), (10, 25, "€10–25"), (25, 50, "€25–50"), (50, 100, "€50–100"),
                (100, 250, "€100–250"), (250, 1e12, "over €250")]


def fmt_day(d: date, lang: str = "en") -> str:
    return f"{d.day} {MONTHS[lang][d.month - 1]}" if lang == "en" else f"{d.day}.{d.month}."


def month_label(key: str, lang: str = "en", long: bool = True) -> str:
    y, m = int(key[:4]), int(key[5:7])
    name = (MONTHS_LONG if long else MONTHS)[lang][m - 1]
    return f"{name.capitalize() if lang == 'en' else name} {y}"


def resolve_period(m: Money, period: str | None, date_from: str | None = None, date_to: str | None = None) -> dict:
    """Turn a period name (or explicit dates) into a concrete range, never past today."""
    t, lang = m.today, m.prefs.lang
    first = m.df["date"].iloc[0]
    L = lambda en, fi: en if lang == "en" else fi
    if date_from or date_to:
        a = date.fromisoformat(date_from) if date_from else first
        b = date.fromisoformat(date_to) if date_to else t
        label = f"{fmt_day(a, lang)} – {fmt_day(b, lang)} {b.year}"
    else:
        p = (period or "this_month").strip().lower().replace(" ", "_")
        tm = m.this_month
        if p == "today":
            a = b = t; label = L("today", "tänään")
        elif p == "yesterday":
            a = b = t - timedelta(days=1); label = L("yesterday", "eilen")
        elif p == "this_week":
            a = t - timedelta(days=t.weekday()); b = t; label = L("this week", "tällä viikolla")
        elif p == "last_week":
            b = t - timedelta(days=t.weekday() + 1); a = b - timedelta(days=6); label = L("last week", "viime viikolla")
        elif p == "this_month":
            a = date(t.year, t.month, 1); b = t; label = L(f"{month_label(tm, lang)} so far", f"{month_label(tm, lang)} tähän asti")
        elif p == "last_month":
            k = add_months(tm, -1); a, b = month_bounds(k); label = month_label(k, lang)
        elif p == "last_30_days":
            a = t - timedelta(days=29); b = t; label = L("the last 30 days", "viimeiset 30 päivää")
        elif p == "last_90_days":
            a = t - timedelta(days=89); b = t; label = L("the last 90 days", "viimeiset 90 päivää")
        elif p in ("last_3_months", "last_6_months", "last_12_months"):
            n = int(p.split("_")[1])
            a = month_bounds(add_months(tm, -n))[0]; b = month_bounds(add_months(tm, -1))[1]
            label = L(f"the last {n} full months", f"viimeiset {n} täyttä kuukautta")
        elif p == "this_year":
            a = date(t.year, 1, 1); b = t; label = L(f"{t.year} so far", f"{t.year} tähän asti")
        elif p == "last_year":
            a = date(t.year - 1, 1, 1); b = date(t.year - 1, 12, 31); label = str(t.year - 1)
        elif p == "since_payday":
            a = m.cycle_start; b = t; label = L(f"since payday ({fmt_day(a, lang)})", f"palkkapäivästä ({fmt_day(a, lang)})")
        elif p == "all":
            a = first; b = t; label = L("all your history", "koko historia")
        elif len(p) == 7 and p[4] == "-":            # YYYY-MM
            a, b = month_bounds(p); label = month_label(p, lang)
        elif len(p) == 4 and p.isdigit():            # YYYY
            a = date(int(p), 1, 1); b = date(int(p), 12, 31); label = p
        else:
            raise ValueError(f"unknown period '{period}'. Use one of {PERIODS}, 'YYYY-MM', 'YYYY', or date_from/date_to.")
    a = max(a, first)
    b = min(b, t)
    if b < a:
        b = a
    return {"from": a, "to": b, "label": label, "days": (b - a).days + 1}


def _previous(m: Money, rng: dict, period: str | None, mode: str) -> dict | None:
    """The comparison range: the period right before, or the same dates a year earlier."""
    a, b = rng["from"], rng["to"]
    lang = m.prefs.lang
    first = m.df["date"].iloc[0]
    if mode == "same_period_last_year":
        try:
            pa, pb = a.replace(year=a.year - 1), b.replace(year=b.year - 1)
        except ValueError:
            pa, pb = a - timedelta(days=365), b - timedelta(days=365)
        label = f"{fmt_day(pa, lang)} – {fmt_day(pb, lang)} {pb.year}"
    else:
        whole_months = a.day == 1 and (b.day == calendar.monthrange(b.year, b.month)[1] or b == m.today)
        if whole_months:
            n = (b.year - a.year) * 12 + (b.month - a.month) + 1
            pk = add_months(month_key(a), -n)
            pa = month_bounds(pk)[0]
            if b == m.today and b.day != calendar.monthrange(b.year, b.month)[1]:
                # month to date -> same number of days in the month before
                last = month_bounds(add_months(month_key(b), -n))[1]
                pb = min(last, date(last.year, last.month, min(b.day, last.day)))
                label = {"en": f"same days in {month_label(month_key(pb), lang)}",
                         "fi": f"samat päivät: {month_label(month_key(pb), lang)}"}[lang]
            else:
                pb = month_bounds(add_months(month_key(b), -n))[1]
                label = month_label(pk, lang) if n == 1 else {"en": f"the {n} months before", "fi": f"edelliset {n} kk"}[lang]
        else:
            pb = a - timedelta(days=1)
            pa = pb - timedelta(days=rng["days"] - 1)
            label = {"en": f"the {rng['days']} days before", "fi": f"edelliset {rng['days']} päivää"}[lang]
    if pb < first:
        return None
    pa = max(pa, first)
    return {"from": pa, "to": pb, "label": label, "days": (pb - pa).days + 1}


def _apply(m: Money, df: pd.DataFrame, f: dict) -> pd.DataFrame:
    flow = f.get("flow") or "spend"
    if flow == "spend":
        df = df[df["is_spend"]]
    elif flow == "income":
        df = df[df["category"].isin(["Salary", "Other Income"])]
    elif flow == "saving":
        df = df[df["category"].isin(["Invest Deposit", "Invest Withdraw"])]
    if f.get("categories"):
        df = df[df["category"].isin(f["categories"])]
    if f.get("kinds"):
        df = df[df["kind"].isin(f["kinds"])]
    if f.get("baskets"):
        df = df[df["basket"].isin(f["baskets"])]
    if f.get("merchant"):
        q = str(f["merchant"]).lower()
        df = df[df["merchant"].fillna("").str.lower().str.contains(q, regex=False)
                | df["merchant_id"].fillna("").str.lower().str.contains(q, regex=False)]
    val = df["amount"].abs()
    if f.get("min_amount") is not None:
        df = df[val >= float(f["min_amount"])]; val = df["amount"].abs()
    if f.get("max_amount") is not None:
        df = df[val <= float(f["max_amount"])]
    if f.get("weekdays"):
        wd = {d[:3].lower(): i for i, d in enumerate(WEEKDAYS["en"])}
        idx = [wd[str(x)[:3].lower()] for x in f["weekdays"] if str(x)[:3].lower() in wd]
        df = df[df["ts"].dt.weekday.isin(idx)]
    if f.get("hour_from") is not None or f.get("hour_to") is not None:
        h0, h1 = int(f.get("hour_from") or 0), int(f.get("hour_to") or 24)
        hrs = df["ts"].dt.hour
        df = df[(hrs >= h0) & (hrs < h1)] if h0 <= h1 else df[(hrs >= h0) | (hrs < h1)]
    return df


def _value(df: pd.DataFrame, flow: str) -> pd.Series:
    """Positive euros for the flow being asked about."""
    return df["spend"] if flow == "spend" else df["amount"] if flow == "income" else -df["amount"]


def tx_row(r, lang: str) -> dict:
    return {"id": int(r.id), "date": r.date.isoformat(), "time": r.ts.strftime("%H:%M"),
            "amount": r2(r.amount), "category": r.category, "category_label": cat_label(r.category, lang),
            "kind": r.kind, "kind_label": kind_label(r.kind, lang),
            "merchant": r.merchant if isinstance(r.merchant, str) else None,
            "basket": r.basket if isinstance(r.basket, str) else None, "balance_after": r2(r.balance)}


def _groups(m: Money, df: pd.DataFrame, val: pd.Series, group_by: str, rng: dict, top_n: int) -> list[dict]:
    lang = m.prefs.lang
    total = float(val.sum())
    share = lambda v: round(float(v) / total, 3) if total else 0.0
    out: list[dict] = []
    if group_by in ("category", "kind", "merchant", "basket"):
        key = df[group_by] if group_by != "merchant" else df["merchant"].fillna({"en": "No merchant", "fi": "Ei kauppiasta"}[lang])
        g = pd.DataFrame({"k": key, "v": val}).groupby("k")["v"].agg(["sum", "count"]).sort_values("sum", ascending=False)
        lab = {"category": lambda k: cat_label(k, lang), "kind": lambda k: kind_label(k, lang),
               "basket": lambda k: BASKETS[k][lang] if k in BASKETS else str(k), "merchant": lambda k: k}[group_by]
        rows = [{"key": str(k), "label": lab(k), "total": r2(s), "count": int(c), "share": share(s)} for k, (s, c) in g.iterrows()]
        if len(rows) > top_n:
            rest = rows[top_n:]
            rows = rows[:top_n] + [{"key": "_other", "label": {"en": f"{len(rest)} others", "fi": f"{len(rest)} muuta"}[lang],
                                    "total": r2(sum(x["total"] for x in rest)), "count": sum(x["count"] for x in rest),
                                    "share": round(sum(x["share"] for x in rest), 3)}]
        return rows
    if group_by == "month":
        g = pd.DataFrame({"k": df["month"], "v": val}).groupby("k")["v"].agg(["sum", "count"])
        k = month_key(rng["from"])
        while k <= month_key(rng["to"]):
            s, c = (g.loc[k, "sum"], g.loc[k, "count"]) if k in g.index else (0.0, 0)
            partial = month_bounds(k)[1] > rng["to"] or month_bounds(k)[0] < rng["from"]
            out.append({"key": k, "label": f"{MONTHS[lang][int(k[5:7]) - 1]} {k[2:4]}", "total": r2(s), "count": int(c),
                        "share": share(s), "partial": bool(partial)})
            k = add_months(k, 1)
        return out
    if group_by == "week":
        wk = df["date"].map(lambda d: d - timedelta(days=d.weekday()))
        g = pd.DataFrame({"k": wk, "v": val}).groupby("k")["v"].agg(["sum", "count"])
        d = rng["from"] - timedelta(days=rng["from"].weekday())
        while d <= rng["to"]:
            s, c = (g.loc[d, "sum"], g.loc[d, "count"]) if d in g.index else (0.0, 0)
            out.append({"key": d.isoformat(), "label": fmt_day(d, lang), "total": r2(s), "count": int(c), "share": share(s)})
            d += timedelta(days=7)
        return out
    if group_by == "day":
        g = pd.DataFrame({"k": df["date"], "v": val}).groupby("k")["v"].agg(["sum", "count"])
        d = rng["from"]
        while d <= rng["to"]:
            s, c = (g.loc[d, "sum"], g.loc[d, "count"]) if d in g.index else (0.0, 0)
            out.append({"key": d.isoformat(), "label": fmt_day(d, lang), "total": r2(s), "count": int(c), "share": share(s)})
            d += timedelta(days=1)
        return out
    if group_by == "weekday":
        g = pd.DataFrame({"k": df["ts"].dt.weekday, "v": val}).groupby("k")["v"].agg(["sum", "count"])
        for i in range(7):
            s, c = (g.loc[i, "sum"], g.loc[i, "count"]) if i in g.index else (0.0, 0)
            out.append({"key": str(i), "label": WEEKDAYS[lang][i], "total": r2(s), "count": int(c), "share": share(s)})
        return out
    if group_by == "hour":
        g = pd.DataFrame({"k": df["ts"].dt.hour, "v": val}).groupby("k")["v"].agg(["sum", "count"])
        for i in range(5, 24):
            s, c = (g.loc[i, "sum"], g.loc[i, "count"]) if i in g.index else (0.0, 0)
            out.append({"key": str(i), "label": f"{i:02d}", "total": r2(s), "count": int(c), "share": share(s)})
        return out
    if group_by == "size":
        a = df["amount"].abs()
        for lo, hi, lab in SIZE_BUCKETS:
            mask = (a >= lo) & (a < hi)
            s = float(val[mask].sum())
            out.append({"key": lab, "label": lab, "total": r2(s), "count": int(mask.sum()), "share": share(s)})
        return out
    raise ValueError("group_by must be one of category, kind, merchant, basket, month, week, day, weekday, hour, size")


def query(m: Money, *, period: str | None = None, date_from: str | None = None, date_to: str | None = None,
          categories: list[str] | None = None, kinds: list[str] | None = None, baskets: list[str] | None = None,
          merchant: str | None = None, min_amount: float | None = None, max_amount: float | None = None,
          weekdays: list[str] | None = None, hour_from: int | None = None, hour_to: int | None = None,
          flow: str = "spend", group_by: str | None = None, compare: str | None = None, top_n: int = 8,
          list_limit: int = 5, sort: str = "largest") -> dict:
    lang = m.prefs.lang
    bad = [c for c in (categories or []) if c not in CATEGORIES and c not in ("Salary", "Other Income", "Invest Deposit", "Invest Withdraw", "Salary Sweep")]
    if bad:
        raise ValueError(f"unknown categories {bad}. Valid: {list(CATEGORIES)}")
    bad = [k for k in (kinds or []) if k not in KINDS and not k.startswith("other_")]
    if bad:
        raise ValueError(f"unknown kinds {bad}. Valid: {sorted(KINDS)}")
    filters = {"categories": categories, "kinds": kinds, "baskets": baskets, "merchant": merchant, "min_amount": min_amount,
               "max_amount": max_amount, "weekdays": weekdays, "hour_from": hour_from, "hour_to": hour_to, "flow": flow}
    rng = resolve_period(m, period, date_from, date_to)
    base = _apply(m, m.df, filters)
    df = base[(base["date"] >= rng["from"]) & (base["date"] <= rng["to"])]
    val = _value(df, flow)
    total = r2(val.sum())
    count = int(len(df))
    months_span = rng["days"] / 30.44
    out = {
        "period": {"label": rng["label"], "from": rng["from"].isoformat(), "to": rng["to"].isoformat(), "days": rng["days"]},
        "filters": {k: v for k, v in filters.items() if v not in (None, [], "")},
        "total": total, "count": count,
        "average_per_purchase": r2(total / count) if count else 0.0,
        "per_month": r2(total / months_span) if rng["days"] >= 45 else None,
        "per_day": r2(total / rng["days"]),
    }
    if group_by and group_by != "none":
        out["group_by"] = group_by
        out["groups"] = _groups(m, df, val, group_by, rng, top_n)
    if compare and compare != "none":
        prev = _previous(m, rng, period, compare)
        if prev:
            pdf = base[(base["date"] >= prev["from"]) & (base["date"] <= prev["to"])]
            ptotal = r2(_value(pdf, flow).sum())
            out["comparison"] = {"label": prev["label"], "from": prev["from"].isoformat(), "to": prev["to"].isoformat(),
                                 "total": ptotal, "count": int(len(pdf)), "delta": r2(total - ptotal),
                                 "pct": round(100 * (total - ptotal) / ptotal) if ptotal else None}
    if list_limit and count:
        s = df.assign(_v=val)
        s = s.sort_values("_v", ascending=False) if sort == "largest" else s.sort_values("ts", ascending=False)
        out["transactions"] = [tx_row(r, lang) for r in s.head(list_limit).itertuples()]
    return out
