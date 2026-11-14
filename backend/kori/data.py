"""Data access: one customer's transactions as a pandas frame, cached.

The parquet file is sorted by customer, so DuckDB reads one row group per lookup.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import duckdb
import pandas as pd

from . import config
from .taxonomy import CATEGORIES, FIXED, SURPRISE, EVERYDAY, kind_of, merchant_name

_lock = threading.Lock()
_con: duckdb.DuckDBPyConnection | None = None


def con() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        _con = duckdb.connect()
        _con.execute(f"create view tx as select * from read_parquet('{config.BUILD_DIR / 'tx.parquet'}')")
        _con.execute(f"create view customers as select * from read_parquet('{config.BUILD_DIR / 'customers.parquet'}')")
    return _con


@dataclass(frozen=True)
class Customer:
    customer_id: str
    age: int
    postal_code: str

    @property
    def area(self) -> str:
        p = self.postal_code[:2]
        return {"00": "Helsinki", "01": "Vantaa", "02": "Espoo"}.get(p, "Uusimaa")

    @property
    def age_band(self) -> str:
        return age_band(self.age)


def age_band(age: int) -> str:
    if age < 25:
        return "18-24"
    if age < 35:
        return "25-34"
    if age < 45:
        return "35-44"
    if age < 55:
        return "45-54"
    if age < 65:
        return "55-64"
    return "65+"


@lru_cache(maxsize=1)
def all_customers() -> pd.DataFrame:
    with _lock:
        return con().execute("select customer_id, age, postal_code from customers order by customer_id").df()


@lru_cache(maxsize=8192)
def get_customer(customer_id: str) -> Customer:
    df = all_customers()
    row = df[df.customer_id == customer_id]
    if row.empty:
        raise KeyError(customer_id)
    r = row.iloc[0]
    return Customer(customer_id, int(r.age), str(r.postal_code))


@lru_cache(maxsize=512)
def _raw(customer_id: str) -> pd.DataFrame:
    with _lock:
        df = con().execute(
            "select tx_date, ts, category, amount, balance, type, merchant_id, mcc from tx where customer_id = ? order by ts",
            [customer_id],
        ).df()
    if df.empty:
        raise KeyError(customer_id)
    df["date"] = pd.to_datetime(df["tx_date"]).dt.date
    df["ts"] = pd.to_datetime(df["ts"])
    df["month"] = df["ts"].dt.strftime("%Y-%m")
    df["mcc"] = df["mcc"].astype("Int64")
    df["kind"] = [kind_of(m if pd.notna(m) else None, c, t) for m, c, t in zip(df["mcc"], df["category"], df["type"])]
    df["merchant"] = [merchant_name(m, c if pd.notna(c) else None) if isinstance(m, str) else None
                      for m, c in zip(df["merchant_id"], df["mcc"])]
    df["is_spend"] = df["category"].isin(CATEGORIES.keys())
    df["spend"] = (-df["amount"]).where(df["is_spend"], 0.0)
    df = df.drop(columns=["tx_date"]).reset_index(drop=True)
    df["id"] = df.index.astype(int)
    return df


def transactions(customer_id: str, today: date | None = None, basket_overrides: dict[str, str] | None = None) -> pd.DataFrame:
    """Transactions visible on `today` (inclusive), with basket assigned."""
    today = today or config.DEMO_TODAY
    df = _raw(customer_id)
    df = df[df["date"] <= today].copy()
    mapping = {c: v["basket"] for c, v in CATEGORIES.items()}
    if basket_overrides:
        mapping.update({k: v for k, v in basket_overrides.items() if k in CATEGORIES and v in (FIXED, SURPRISE, EVERYDAY)})
    df["basket"] = df["category"].map(mapping)
    return df


def future_transactions(customer_id: str, today: date | None = None) -> pd.DataFrame:
    """What actually happened after `today` — only for backtests, never shown to the coach."""
    today = today or config.DEMO_TODAY
    df = _raw(customer_id)
    return df[df["date"] > today].copy()
