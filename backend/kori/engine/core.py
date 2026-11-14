"""The deterministic money engine.

Every number the coach says comes from here. The language model never does arithmetic:
it picks a tool, the tool computes, the model explains.

`Money` is a snapshot of one customer on one day. Nothing after `today` is visible to it.
"""
from __future__ import annotations

import calendar
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import cached_property

import numpy as np
import pandas as pd

from .. import config
from ..data import Customer, get_customer, transactions
from ..taxonomy import (BASKET_ORDER, BASKETS, CATEGORIES, EVERYDAY, FIXED, SURPRISE, cat_label, kind_label)

DAYS_PER_MONTH = 30.44


def r2(x) -> float:
    """Round to cents, as a plain float (no numpy types, no -0.0)."""
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return 0.0
    v = round(float(x), 2)
    return 0.0 if v == 0 else v


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_bounds(key: str) -> tuple[date, date]:
    y, m = int(key[:4]), int(key[5:7])
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def add_months(key: str, n: int) -> str:
    y, m = int(key[:4]), int(key[5:7])
    idx = y * 12 + (m - 1) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


@dataclass
class Prefs:
    """What the user has told the coach. Stored per customer, editable by voice or tap."""
    lang: str = "en"
    cushion: float | None = None            # never let the balance go below this
    savings_goal_monthly: float | None = None
    basket_overrides: dict[str, str] = field(default_factory=dict)   # category -> basket
    goal: dict | None = None                # {"name": str, "amount": float, "saved": float}
    other_bank_linked: bool = False         # simulated PSD2 view for the demo


class Money:
    def __init__(self, customer_id: str, today: date | None = None, prefs: Prefs | None = None):
        self.customer: Customer = get_customer(customer_id)
        self.customer_id = customer_id
        self.today = today or config.DEMO_TODAY
        self.prefs = prefs or Prefs()
        self.df = transactions(customer_id, self.today, self.prefs.basket_overrides)
        if self.df.empty:
            raise KeyError(f"no transactions for {customer_id} on or before {self.today}")

    # ------------------------------------------------------------ basics
    @cached_property
    def balance(self) -> float:
        base = float(self.df["balance"].iloc[-1])
        # A linked view treats salary sweeps as transfers between the user's
        # own accounts. The real account balance is unchanged; the linked
        # picture adds the swept amount back to the household total.
        if self.prefs.other_bank_linked and not self.sweeps.empty:
            base += float(self.sweep_typical)
        return r2(base)

    @cached_property
    def this_month(self) -> str:
        return month_key(self.today)

    @cached_property
    def full_months(self) -> list[str]:
        """Complete calendar months in the data before the current month, oldest first."""
        first = month_key(self.df["date"].iloc[0])
        out, k = [], first
        while k < self.this_month:
            out.append(k)
            k = add_months(k, 1)
        # the first month may be partial only if data starts mid-month; the dataset starts on the 1st
        return out

    def last_full_months(self, n: int) -> list[str]:
        return self.full_months[-n:]

    # ------------------------------------------------------------ income
    @cached_property
    def salaries(self) -> pd.DataFrame:
        return self.df[self.df["category"] == "Salary"]

    @cached_property
    def sweeps(self) -> pd.DataFrame:
        return self.df[self.df["category"] == "Salary Sweep"]

    @cached_property
    def salary_typical(self) -> float:
        s = self.salaries["amount"].tail(6)
        return r2(s.median()) if len(s) else 0.0

    @cached_property
    def sweep_typical(self) -> float:
        """Money that leaves for another bank right after payday (median of last 6 months)."""
        if self.sweeps.empty:
            return 0.0
        months = self.last_full_months(6)
        by_m = self.sweeps.groupby("month")["amount"].sum().reindex(months).fillna(0.0)
        return r2(-by_m.median())

    @cached_property
    def sweep_share(self) -> float:
        return round(self.sweep_typical / self.salary_typical, 3) if self.salary_typical else 0.0

    @cached_property
    def partial_view(self) -> bool:
        """Most of the salary moves to another bank: we only see a slice of this person's money."""
        return self.sweep_share >= 0.5 and not self.prefs.other_bank_linked

    @cached_property
    def linked_view(self) -> dict | None:
        if not self.prefs.other_bank_linked or self.sweeps.empty:
            return None
        amount = self.sweep_typical
        return {"simulated": True, "amount_counted": amount,
                "note": {"en": "Estimate from a simulated link to the other bank. Salary moved out is counted as your money.",
                         "fi": "Arvio tämän demon simuloidusta toisen pankin linkistä. Siirtynyt palkka lasketaan omaksi rahaksesi."}}

    @cached_property
    def income_typical(self) -> float:
        """Salary that stays on this account each month."""
        return r2(self.salary_typical if self.prefs.other_bank_linked else self.salary_typical - self.sweep_typical)

    @cached_property
    def late_pay_rate(self) -> float:
        """Share of months where pay came at month end instead of mid-month."""
        s = self.salaries
        if s.empty:
            return 0.0
        late = sum(1 for d in s["date"] if d.day >= 26)
        return round(late / len(s), 3)

    @cached_property
    def last_payday(self) -> date | None:
        return self.salaries["date"].iloc[-1] if len(self.salaries) else None

    @cached_property
    def paid_this_month(self) -> bool:
        return bool(len(self.salaries)) and month_key(self.salaries["date"].iloc[-1]) == self.this_month

    @cached_property
    def next_payday(self) -> date:
        """Best guess of the next salary date. Pay usually lands on the 15th; when it has not
        arrived by then, it has always come in the last three days of the month."""
        t = self.today
        if not self.paid_this_month:
            if t.day < 15:
                return date(t.year, t.month, 15)
            late = month_end(t) - timedelta(days=1)
            return late if late > t else t + timedelta(days=1)
        nk = add_months(self.this_month, 1)
        return date(int(nk[:4]), int(nk[5:7]), 15)

    @cached_property
    def late_payday(self) -> date:
        """If the next pay is late, it comes around this day."""
        np_ = self.next_payday
        return month_end(np_) - timedelta(days=1) if np_.day == 15 else np_

    @cached_property
    def days_to_payday(self) -> int:
        return max(1, (self.next_payday - self.today).days)

    @cached_property
    def cycle_start(self) -> date:
        """Start of the current pay cycle (the last payday, or 30 days back if none)."""
        if self.last_payday and (self.today - self.last_payday).days <= 50:
            return self.last_payday
        return self.today - timedelta(days=30)

    # ------------------------------------------------------- monthly table
    @cached_property
    def monthly(self) -> pd.DataFrame:
        """One row per calendar month: income, baskets, categories, saving, net."""
        df = self.df
        months = sorted(set(df["month"]))
        out = pd.DataFrame(index=months)
        g = df.groupby("month")
        amt = lambda mask: df[mask].groupby("month")["amount"].sum().reindex(months).fillna(0.0)
        out["salary"] = amt(df["category"] == "Salary")
        out["other_income"] = amt(df["category"] == "Other Income")
        out["swept"] = -amt(df["category"] == "Salary Sweep")
        out["invested"] = -amt(df["category"] == "Invest Deposit")
        out["withdrawn"] = amt(df["category"] == "Invest Withdraw")
        for b in BASKET_ORDER:
            out[b] = df[df["basket"] == b].groupby("month")["spend"].sum().reindex(months).fillna(0.0)
        for c in CATEGORIES:
            out["cat:" + c] = df[df["category"] == c].groupby("month")["spend"].sum().reindex(months).fillna(0.0)
        out["spend"] = out[BASKET_ORDER].sum(axis=1)
        out["income"] = out["salary"] + out["other_income"] - (0 if self.prefs.other_bank_linked else out["swept"])
        out["net"] = out["income"] - out["spend"] - out["invested"] + out["withdrawn"]
        out["end_balance"] = g["balance"].last().reindex(months)
        out["min_balance"] = g["balance"].min().reindex(months)
        return out.round(2)

    def _typ(self, col: str, n: int = 6, how: str = "median") -> float:
        months = self.last_full_months(n)
        if not months:
            return 0.0
        s = self.monthly[col].reindex(months).fillna(0.0)
        return r2(s.median() if how == "median" else s.mean())

    @cached_property
    def usual(self) -> dict:
        """A typical month, from the last 6 complete months (12 for the lumpy surprise basket)."""
        cats = {c: self._typ("cat:" + c, 6, "mean") for c in CATEGORIES}
        u = {
            "income": self.income_typical,
            FIXED: self._typ(FIXED, 6, "median"),
            SURPRISE: self._typ(SURPRISE, 12, "mean"),
            EVERYDAY: self._typ(EVERYDAY, 6, "median"),
            "invested": self.invest_typical,
            "categories": cats,
            "window": {"en": "last 6 complete months, median for baskets and mean for categories",
                       "fi": "viimeiset 6 täyttä kuukautta, koreissa mediaani ja kategorioissa keskiarvo"}[self.prefs.lang],
        }
        u["spend"] = r2(u[FIXED] + u[SURPRISE] + u[EVERYDAY])
        u["left_over"] = r2(u["income"] - u["spend"] - u["invested"])
        return u

    @cached_property
    def invest_typical(self) -> float:
        """Monthly amount this person usually moves to investments (0 unless it is a habit)."""
        months = self.last_full_months(6)
        if not months:
            return 0.0
        s = self.monthly["invested"].reindex(months).fillna(0.0)
        if (s > 0).sum() < 4:
            return 0.0
        return r2(s.median())

    @cached_property
    def savings_plan(self) -> float:
        g = self.prefs.savings_goal_monthly
        return r2(g) if g is not None else self.invest_typical

    @cached_property
    def cushion(self) -> float:
        if self.prefs.cushion is not None:
            return r2(max(0.0, self.prefs.cushion))
        base = min(100.0, 0.05 * max(self.salary_typical, 0.0))
        return float(int(base // 10) * 10)

    # ------------------------------------------------------ upcoming musts
    def _housing_forecast(self, until: date) -> list[dict]:
        h = self.df[self.df["category"] == "Housing"]
        if h.empty or (self.today - h["date"].iloc[-1]).days > 75:
            return []
        amount = r2(-h["amount"].tail(3).median())
        items = []
        paid_this_month = month_key(h["date"].iloc[-1]) == self.this_month
        # Housing leaves between the 1st and the 8th. If it has not left by then, this month's is not coming
        # (about one month in 28 is skipped in the data), but next month's still is.
        skipped = not paid_this_month and self.today.day > 8
        k = add_months(self.this_month, 1) if (paid_this_month or skipped) else self.this_month
        while True:
            y, m = int(k[:4]), int(k[5:7])
            due = date(y, m, 8)                       # always paid between the 1st and the 8th
            if k == self.this_month and due <= self.today:
                due = self.today + timedelta(days=1)  # running late: expect it any day
            if due > until:
                break
            items.append({"date": due, "category": "Housing", "amount": amount,
                          "window": [date(y, m, 1).isoformat(), date(y, m, 8).isoformat()]})
            k = add_months(k, 1)
        return items

    def _utilities_forecast(self, until: date) -> list[dict]:
        u = self.df[self.df["category"] == "Utilities"]
        if u.empty or (self.today - u["date"].iloc[-1]).days > 60:
            return []
        amount = r2(-u["amount"].tail(9).median())
        months = self.last_full_months(6)
        per_month = int(round(u.groupby("month").size().reindex(months).fillna(0).mean())) if months else 3
        if per_month <= 0:
            return []
        items = []
        done = int((u["month"] == self.this_month).sum())
        remaining = max(0, per_month - done)
        end = month_end(self.today)
        span = (end - self.today).days
        for i in range(remaining):
            d = self.today + timedelta(days=max(1, round((i + 1) * span / (remaining + 1))))
            if d <= until and d <= end:
                items.append({"date": d, "category": "Utilities", "amount": amount})
        k = add_months(self.this_month, 1)
        while True:
            y, m = int(k[:4]), int(k[5:7])
            last = calendar.monthrange(y, m)[1]
            added = False
            for i in range(per_month):
                day = min(last, 3 + round((i + 0.5) * (last - 3) / per_month))
                d = date(y, m, day)
                if d <= until:
                    items.append({"date": d, "category": "Utilities", "amount": amount})
                    added = True
            if not added or date(y, m, last) >= until:
                break
            k = add_months(k, 1)
        return items

    def upcoming_fixed(self, until: date | None = None) -> list[dict]:
        """Fixed musts expected between tomorrow and `until` (default: next payday)."""
        until = until or self.next_payday
        items = self._housing_forecast(until) + self._utilities_forecast(until)
        for it in items:
            it["label"] = cat_label(it["category"], self.prefs.lang)
        items.sort(key=lambda x: x["date"])
        return [{**it, "date": it["date"].isoformat()} for it in items]

    # ----------------------------------------------------------- baskets
    def baskets(self, month: str | None = None) -> dict:
        """The three baskets for one month, against this person's usual month."""
        lang = self.prefs.lang
        month = month or self.this_month
        mt = self.monthly
        row = mt.loc[month] if month in mt.index else None
        is_current = month == self.this_month
        start, end = month_bounds(month)
        days_in = (end - start).days + 1
        elapsed = min(days_in, (self.today - start).days + 1) if is_current else days_in
        d = self.df[self.df["month"] == month]
        out = {"month": month, "is_current": is_current, "days_elapsed": elapsed, "days_in_month": days_in,
               "income": r2(row["income"]) if row is not None else 0.0, "baskets": []}
        total = 0.0
        for b in BASKET_ORDER:
            amount = r2(row[b]) if row is not None else 0.0
            usual = self.usual[b]
            cats = []
            for c, meta in CATEGORIES.items():
                if self._basket_of(c) != b:
                    continue
                cd = d[d["category"] == c]
                cats.append({"category": c, "label": cat_label(c, lang), "icon": meta["icon"],
                             "amount": r2(cd["spend"].sum()), "count": int(len(cd)),
                             "usual": self.usual["categories"][c]})
            cats.sort(key=lambda x: -x["amount"])
            out["baskets"].append({
                "key": b, "label": BASKETS[b][lang], "short": BASKETS[b]["short_" + lang],
                "desc": BASKETS[b]["desc_" + lang], "amount": amount, "usual": usual,
                "vs_usual_pct": round(100 * (amount - usual) / usual) if usual else None,
                "categories": cats,
            })
            total += amount
        out["spend"] = r2(total)
        for b in out["baskets"]:
            b["share"] = round(b["amount"] / total, 3) if total else 0.0
        out["usual_spend"] = self.usual["spend"]
        out["usual_window"] = self.usual["window"]
        out["saved"] = r2(row["invested"] - row["withdrawn"]) if row is not None else 0.0
        out["left_over"] = r2(out["income"] - out["spend"] - out["saved"])
        return out

    def _basket_of(self, category: str) -> str:
        return self.prefs.basket_overrides.get(category, CATEGORIES[category]["basket"])

    # ------------------------------------------------------ everyday pace
    @cached_property
    def everyday_daily(self) -> dict:
        """How much the everyday basket usually costs per weekday (last 90 days, zero days included)."""
        start = self.today - timedelta(days=90)
        d = self.df[(self.df["date"] > start) & (self.df["basket"] == EVERYDAY)]
        by_day = d.groupby("date")["spend"].sum()
        days = [start + timedelta(days=i) for i in range(1, 91)]
        s = pd.Series([float(by_day.get(x, 0.0)) for x in days], index=days)
        wd = pd.Series([x.weekday() for x in days], index=days)
        per_wd = {int(k): r2(v) for k, v in s.groupby(wd).mean().items()}
        return {"mean": r2(s.mean()), "p75": r2(s.rolling(7).sum().dropna().quantile(0.75) / 7 if len(s) >= 7 else s.mean()),
                "per_weekday": per_wd}

    # -------------------------------------------------------- safe to spend
    @cached_property
    def safe(self) -> dict:
        """Safe to spend until payday, and the reasoning behind it.

        Two limits, the lower one wins:
          budget = what this pay cycle's income leaves for everyday after musts, surprises and saving
          cash   = what is on the account minus everything already spoken for before payday
        """
        lang = self.prefs.lang
        upcoming = self.upcoming_fixed(self.next_payday)
        fixed_due = r2(sum(i["amount"] for i in upcoming))
        days = self.days_to_payday
        surprise_monthly = self.usual[SURPRISE]
        surprise_reserve = r2(surprise_monthly * days / DAYS_PER_MONTH)

        cyc = self.df[self.df["date"] >= self.cycle_start]
        everyday_spent = r2(cyc[cyc["basket"] == EVERYDAY]["spend"].sum())
        invested_cycle = r2(-cyc[cyc["category"] == "Invest Deposit"]["amount"].sum())
        savings_left = r2(max(0.0, self.savings_plan - invested_cycle))

        # a month's income leaves this much for everyday; scale it to the real length of this pay cycle
        everyday_monthly = r2(self.income_typical - self.usual[FIXED] - surprise_monthly - self.savings_plan)
        cycle_days = max(1, (self.next_payday - self.cycle_start).days)
        everyday_budget = r2(everyday_monthly * cycle_days / DAYS_PER_MONTH)
        budget_left = r2(everyday_budget - everyday_spent)
        free_cash = r2(self.balance - fixed_due - surprise_reserve - savings_left - self.cushion)

        # The lower limit wins, with a partial view too: what stays on this account each month is then the income,
        # so the balance of an account the salary only passes through is never read as a budget.
        if budget_left <= free_cash:
            amount, limit = max(0.0, budget_left), "budget"
        else:
            amount, limit = max(0.0, free_cash), "cash"
        amount = r2(amount)
        per_day = r2(amount / days)
        week_days = min(7, days)
        usual_day = self.everyday_daily["mean"]
        ratio = (per_day / usual_day) if usual_day > 0 else 9.0
        status = "comfortable" if ratio >= 1.0 else "tight" if ratio >= 0.6 else "very_tight"
        if amount <= 0:
            status = "empty"

        # what the balance is already spoken for
        free_total = max(0.0, free_cash)
        spoken = [
            {"key": "fixed", "label": BASKETS[FIXED][lang], "amount": fixed_due},
            {"key": "surprise", "label": {"en": "Surprise reserve", "fi": "Yllätysvara"}[lang], "amount": surprise_reserve},
            {"key": "saving", "label": {"en": "Planned saving", "fi": "Suunniteltu säästö"}[lang], "amount": savings_left},
            {"key": "cushion", "label": {"en": "Cushion", "fi": "Pohjavara"}[lang], "amount": self.cushion},
            {"key": "safe", "label": {"en": "Safe to spend", "fi": "Turvallista käyttää"}[lang], "amount": r2(min(amount, free_total))},
            {"key": "buffer", "label": {"en": "Not needed before payday", "fi": "Ei tarvita ennen palkkapäivää"}[lang], "amount": r2(max(0.0, free_total - amount))},
        ]
        # stress test: pay comes late (end of month instead of the 15th)
        late = None
        if self.next_payday.day == 15 and self.late_pay_rate > 0 and not self.partial_view:
            extra_days = (self.late_payday - self.next_payday).days
            extra_fixed = r2(sum(i["amount"] for i in self.upcoming_fixed(self.late_payday)) - fixed_due)
            need = r2(extra_fixed + extra_days * usual_day)
            late = {"date": self.late_payday.isoformat(), "extra_days": extra_days, "rate": self.late_pay_rate,
                    "extra_needed": need, "covered": bool(free_total - amount >= need)}
        label, line = self._status_words(status, per_day, usual_day, free_cash)
        return {
            "amount": amount, "per_day": per_day, "this_week": r2(per_day * week_days), "week_days": week_days,
            "days_to_payday": days, "next_payday": self.next_payday.isoformat(), "status": status,
            "status_label": label, "status_line": line,
            "limit": limit, "balance": self.balance,
            "usual_per_day": usual_day, "pace_ratio": round(ratio, 2) if usual_day > 0 else None,
            "budget": {"income": self.income_typical, "fixed": self.usual[FIXED], "surprise": surprise_monthly,
                       "saving": self.savings_plan, "everyday_monthly": everyday_monthly,
                       "cycle_days": cycle_days, "everyday_budget": everyday_budget,
                       "everyday_spent": everyday_spent, "left": budget_left,
                       "cycle_start": self.cycle_start.isoformat()},
            "cash": {"balance": self.balance, "fixed_due": fixed_due, "surprise_reserve": surprise_reserve,
                     "saving_left": savings_left, "cushion": self.cushion, "free": free_cash},
            "upcoming": upcoming, "spoken_for": spoken, "late_pay": late, "partial_view": self.partial_view,
            "linked_view": self.linked_view,
        }

    def _status_words(self, status: str, per_day: float, usual_day: float, free_cash: float) -> tuple[str, str]:
        """The status in plain words: a short label and one sentence that says what is meant."""
        from .insights import eur          # local import: insights imports this module
        lang = self.prefs.lang
        L = lambda en, fi: en if lang == "en" else fi
        pd_, us = eur(per_day, lang, True), eur(usual_day, lang, True)
        if self.partial_view:
            return (L("This account only", "Vain tämä tili"),
                    L("Your salary moves to another bank, so this is not your whole month.",
                      "Palkkasi siirtyy toiseen pankkiin, joten tämä ei ole koko kuukautesi."))
        if status == "comfortable":
            return (L("On track", "Hyvässä tahdissa"),
                    L(f"Your usual pace is {us} a day, so your usual days fit.",
                      f"Tavallinen tahtisi on {us} päivässä, joten tavalliset päiväsi mahtuvat tähän."))
        if status == "tight":
            return (L("Tight", "Tiukkaa"),
                    L(f"Your usual pace is {us} a day, so it takes some care.",
                      f"Tavallinen tahtisi on {us} päivässä, joten nyt kannattaa olla tarkkana."))
        if status == "very_tight":
            return (L("Very tight", "Hyvin tiukkaa"),
                    L(f"Far under your usual {us} a day. The bills due before payday are already set aside.",
                      f"Selvästi alle tavallisen tahtisi, joka on {us} päivässä. Ennen palkkapäivää erääntyvät laskut on jo varattu."))
        if free_cash < 0:
            return (L("Short", "Vajaa"),
                    L(f"The account is {eur(-free_cash, lang)} short of the bills and reserves due before payday.",
                      f"Tililtä puuttuu {eur(-free_cash, lang)} ennen palkkapäivää erääntyvistä laskuista ja varauksista."))
        return (L("Used up", "Käytetty"),
                L("This pay cycle's everyday money is used up. The bills due before payday are already set aside.",
                  "Tämän palkkajakson arkiraha on käytetty. Ennen palkkapäivää erääntyvät laskut on jo varattu."))

    # ------------------------------------------------------------ forecast
    def forecast(self, pace: str = "usual") -> dict:
        """Projected balance day by day until pay lands.

        pace: "usual" = this person's usual daily pace, shaped by their own weekday pattern from the last 90 days,
              "safe"  = spending exactly the safe-to-spend amount per day.

        Each point is the balance at the start of that day, so the last one is what is on the account when pay
        lands: today's balance, minus the bills on the way, minus the everyday spending of every day until then
        (today included, as in "a day" of safe to spend), minus the surprise reserve and any saving still planned.
        `adds_up` is that sum, to the cent, and at the safe pace it leaves exactly the cushion and the buffer.
        """
        upcoming = {}
        for it in self.upcoming_fixed(self.next_payday):
            upcoming.setdefault(it["date"], []).append(it)
        s = self.safe
        days = self.days_to_payday
        spend_days = [self.today + timedelta(days=i) for i in range(days)]
        if pace == "safe":
            everyday_total = s["amount"]
            share = {d: 1.0 / days for d in spend_days}
        else:
            everyday_total = r2(s["usual_per_day"] * days)
            per_wd = self.everyday_daily["per_weekday"]
            w = {d: max(0.0, per_wd.get(d.weekday(), s["usual_per_day"])) for d in spend_days}
            tot = sum(w.values())
            share = {d: (w[d] / tot if tot > 0 else 1.0 / days) for d in spend_days}
        reserve = s["cash"]["surprise_reserve"]
        saving = s["cash"]["saving_left"]
        fixed_due = s["cash"]["fixed_due"]
        bal = self.balance
        series = [{"date": self.today.isoformat(), "balance": r2(bal), "events": []}]
        low, low_date = bal, self.today
        for i, spent_on in enumerate(spend_days):
            d = spent_on + timedelta(days=1)
            bal -= everyday_total * share[spent_on] + reserve / days
            events = []
            if i == 0 and saving > 0:
                bal -= saving
                events.append({"type": "saving", "amount": saving})
            for it in upcoming.get(d.isoformat(), []):
                bal -= it["amount"]
                events.append({"type": "bill", "category": it["category"], "label": it["label"], "amount": it["amount"]})
            if bal < low:
                # the start of a day is the end of the one before: that is the day people know it by
                low, low_date = bal, spent_on if d == self.next_payday else d
            point = {"date": d.isoformat(), "balance": r2(bal), "events": events}
            if d == self.next_payday:
                events.append({"type": "payday", "amount": self.salary_typical})
                point["balance_after_pay"] = r2(bal + self.salary_typical)
            series.append(point)
        left = r2(self.balance - fixed_due - everyday_total - reserve - saving)
        series[-1]["balance"] = left
        if series[-1].get("balance_after_pay") is not None:
            series[-1]["balance_after_pay"] = r2(left + self.salary_typical)
        if low_date == spend_days[-1] or left < low:
            low = left
        buffer = r2(max(0.0, s["cash"]["free"] - s["amount"]))
        adds_up = {"balance_today": self.balance, "bills_before_payday": fixed_due, "everyday_spending": everyday_total,
                   "per_day": s["per_day"] if pace == "safe" else s["usual_per_day"], "days": days,
                   "surprise_reserve": reserve, "planned_saving": saving, "left_when_pay_lands": left,
                   "left_if_no_surprise_comes": r2(left + reserve)}
        from .insights import eur          # local import: insights imports this module
        lang = self.prefs.lang
        E = lambda v: eur(v, lang, True)
        L = lambda en, fi: en if lang == "en" else fi
        if pace == "safe":
            adds_up |= {"cushion": self.cushion, "buffer": buffer}
            made_of = (L(f"your cushion of {E(self.cushion)} plus {E(buffer)} that this pay cycle does not need",
                         f"pohjavarasi {E(self.cushion)} ja {E(buffer)}, jota tämä palkkajakso ei tarvitse") if buffer > 0.005 and left > 0.005 else
                       L(f"your cushion of {E(self.cushion)}", f"pohjavarasi {E(self.cushion)}") if left > 0.005 else "")
            adds_up["in_words"] = L(
                f"At the safe pace of {E(adds_up['per_day'])} a day, {E(left)} is on the account when pay lands" + (f": {made_of}." if made_of else ".") +
                (f" That already counts the surprise reserve of {E(reserve)} as used. If no surprise comes, {E(left + reserve)} is left." if reserve > 0.005 else ""),
                f"Turvallisella tahdilla, {E(adds_up['per_day'])} päivässä, tilillä on {E(left)}, kun palkka tulee" + (f": {made_of}." if made_of else ".") +
                (f" Siinä yllätysvara {E(reserve)} on jo laskettu käytetyksi. Jos yllätystä ei tule, jäljelle jää {E(left + reserve)}." if reserve > 0.005 else ""))
        else:
            adds_up["in_words"] = L(
                f"At your usual pace of {E(adds_up['per_day'])} a day, {E(left)} is on the account when pay lands, after the same bills and with the surprise reserve of {E(reserve)} counted as used.",
                f"Tavallisella tahdillasi, {E(adds_up['per_day'])} päivässä, tilillä on {E(left)}, kun palkka tulee. Samat laskut on maksettu ja yllätysvara {E(reserve)} on laskettu käytetyksi.")
        return {"pace": pace, "series": series, "bills": self.bills_on_the_way(),
                "lowest": {"balance": r2(low), "date": low_date.isoformat()},
                "before_payday": left, "next_payday": self.next_payday.isoformat(), "adds_up": adds_up,
                "goes_negative": bool(low < 0), "below_cushion": bool(low < self.cushion)}

    def bills_on_the_way(self) -> dict:
        """Every fixed must expected before payday, with one total. The total is the same figure as
        `safe.cash.fixed_due`; `largest_day` is the single day with the most leaving (what a chart marks)."""
        from .query import fmt_day          # local import: query imports this module
        lang = self.prefs.lang
        items = self.upcoming_fixed(self.next_payday)
        by_day: dict[str, list[dict]] = {}
        for it in items:
            by_day.setdefault(it["date"], []).append(it)
        largest = None
        if by_day:
            d, its = max(by_day.items(), key=lambda kv: sum(i["amount"] for i in kv[1]))
            day = fmt_day(date.fromisoformat(d), lang)
            largest = {"date": d, "total": r2(sum(i["amount"] for i in its)), "count": len(its),
                       "label": {"en": f"Bills on {day}", "fi": f"Laskut {day}"}[lang] if len(its) > 1
                       else {"en": f"{its[0]['label']} on {day}", "fi": f"{its[0]['label']} {day}"}[lang]}
        return {"total": r2(sum(i["amount"] for i in items)), "count": len(items),
                "label": {"en": "Bills before payday", "fi": "Laskut ennen palkkapäivää"}[lang],
                "items": [{"date": i["date"], "category": i["category"], "label": i["label"], "amount": i["amount"]} for i in items],
                "largest_day": largest}

    # --------------------------------------------------------- safe to save
    @cached_property
    def safe_to_save(self) -> dict:
        """How much could move to savings today, and how much per month, without touching normal life."""
        s = self.safe
        days = self.days_to_payday
        need_everyday = r2(self.everyday_daily["p75"] * days)       # a slightly expensive stretch
        musts_monthly = r2(self.usual[FIXED] + self.usual[SURPRISE])
        buffer_target = r2(3 * musts_monthly)
        free = s["cash"]["free"]
        after_life = r2(free - need_everyday)                         # cash left on payday eve
        now = r2(max(0.0, after_life - buffer_target)) if not self.partial_view else 0.0
        monthly_capacity = r2(max(0.0, self.income_typical - self.usual[FIXED] - self.usual[SURPRISE] - self.usual[EVERYDAY]))
        buffer_now = r2(max(0.0, self.balance))
        months_covered = round(buffer_now / musts_monthly, 1) if musts_monthly > 0 else None
        return {
            "now": now, "monthly_capacity": monthly_capacity,
            "already_saving_monthly": self.invest_typical,
            "extra_monthly": r2(max(0.0, monthly_capacity - self.invest_typical)),
            "buffer": {"balance": buffer_now, "musts_monthly": musts_monthly, "months_covered": months_covered,
                       "target_months": 3, "target": buffer_target,
                       "gap": r2(max(0.0, buffer_target - buffer_now))},
            "needed_until_payday": {"everyday": need_everyday, "fixed": s["cash"]["fixed_due"],
                                    "surprise_reserve": s["cash"]["surprise_reserve"], "cushion": self.cushion},
            "partial_view": self.partial_view,
        }

    # ------------------------------------------------------------ overview
    def overview(self) -> dict:
        lang = self.prefs.lang
        c = self.customer
        return {
            "customer_id": self.customer_id, "age": c.age, "area": c.area, "postal_code": c.postal_code,
            "today": self.today.isoformat(), "balance": self.balance,
            "income_typical": self.income_typical, "salary_typical": self.salary_typical,
            "sweep_typical": self.sweep_typical, "partial_view": self.partial_view,
            "next_payday": self.next_payday.isoformat(), "days_to_payday": self.days_to_payday,
            "last_payday": self.last_payday.isoformat() if self.last_payday else None,
            "late_pay_rate": self.late_pay_rate,
            "usual_month": {"income": self.usual["income"], "fixed": self.usual[FIXED], "surprise": self.usual[SURPRISE],
                            "everyday": self.usual[EVERYDAY], "saving": self.usual["invested"],
                            "left_over": self.usual["left_over"],
                            "categories": {cat_label(k, lang): v for k, v in self.usual["categories"].items() if v > 0},
                            "window": self.usual["window"]},
            "months_of_history": len(self.full_months),
        }
