"""Build the peer table: one row per customer with monthly averages and behaviour features.

Window: the 12 complete calendar months before the demo day. Used for "people like you"
comparisons (never fewer than 30 people in a group) and for the spender profile.

    PYTHONPATH=. uv run python scripts/build_peers.py
"""
from __future__ import annotations

import sys
from datetime import date

import duckdb

sys.path.insert(0, ".")
from kori import config  # noqa: E402
from kori.data import age_band  # noqa: E402
from kori.taxonomy import CATEGORIES, EVERYDAY, FIXED, SURPRISE  # noqa: E402

today = config.DEMO_TODAY
win_end = date(today.year, today.month, 1)                      # exclusive
win_start = date(win_end.year - 1, win_end.month, 1)
B = config.BUILD_DIR

con = duckdb.connect()
con.execute(f"create view tx as select * from read_parquet('{B / 'tx.parquet'}') where tx_date <= date '{today}'")
con.execute(f"create view w as select * from tx where tx_date >= date '{win_start}' and tx_date < date '{win_end}'")
con.execute(f"create view cust as select * from read_parquet('{B / 'customers.parquet'}')")

cat_cols = ",\n".join(
    f"coalesce(sum(-amount) filter (where category = '{c}'), 0) / 12.0 as \"cat_{c}\"" for c in CATEGORIES)
basket_sql = {b: " or ".join(f"category = '{c}'" for c, v in CATEGORIES.items() if v["basket"] == b)
              for b in (FIXED, SURPRISE, EVERYDAY)}
spend_pred = " or ".join(f"category = '{c}'" for c in CATEGORIES)

con.execute(f"""
create table agg as
select customer_id,
  {cat_cols},
  coalesce(sum(-amount) filter (where {basket_sql[FIXED]}), 0) / 12.0 as fixed,
  coalesce(sum(-amount) filter (where {basket_sql[SURPRISE]}), 0) / 12.0 as surprise,
  coalesce(sum(-amount) filter (where {basket_sql[EVERYDAY]}), 0) / 12.0 as everyday,
  coalesce(sum(-amount) filter (where {spend_pred}), 0) / 12.0 as spend,
  coalesce(sum(amount) filter (where category = 'Salary'), 0) / 12.0 as salary,
  coalesce(sum(-amount) filter (where category = 'Salary Sweep'), 0) / 12.0 as swept,
  coalesce(sum(amount) filter (where category = 'Other Income'), 0) / 12.0 as other_income,
  (coalesce(sum(-amount) filter (where category = 'Invest Deposit'), 0)
     - coalesce(sum(amount) filter (where category = 'Invest Withdraw'), 0)) / 12.0 as invested,
  count(*) filter (where type = 'purchase') / 12.0 as tx_pm,
  count(*) filter (where type = 'purchase' and -amount < 10) / 12.0 as small_tx_pm,
  coalesce(sum(-amount) filter (where type = 'purchase' and -amount < 10), 0) / 12.0 as small_eur_pm,
  coalesce(sum(-amount) filter (where type = 'purchase' and -amount >= 200), 0) / 12.0 as big_eur_pm,
  coalesce(sum(-amount) filter (where ({basket_sql[EVERYDAY]}) and dayofweek(tx_date) in (0, 6)), 0) / 12.0 as weekend_eur_pm,
  coalesce(sum(-amount) filter (where ({basket_sql[EVERYDAY]}) and hour(ts) >= 21), 0) / 12.0 as late_eur_pm,
  coalesce(sum(-amount) filter (where mcc = 4121), 0) / 12.0 as taxi_pm,
  coalesce(sum(-amount) filter (where mcc = 5814), 0) / 12.0 as cafe_pm,
  count(distinct tx_date) filter (where balance < 0) as overdraft_days
from w group by 1
""")

# share of everyday spending that happens within 7 days after a payday
con.execute(f"""
create table payweek as
with sal as (select customer_id, tx_date as pay_date from tx where category = 'Salary'),
p as (select customer_id, tx_date, -amount as eur from w where {basket_sql[EVERYDAY]}),
j as (select p.customer_id, p.eur, date_diff('day', s.pay_date, p.tx_date) as since
      from p asof join sal s on p.customer_id = s.customer_id and p.tx_date >= s.pay_date)
select customer_id, sum(eur) filter (where since < 7) / nullif(sum(eur), 0) as payday_week_share from j group by 1
""")

# month-to-month swing of the everyday basket
con.execute(f"""
create table vol as
select customer_id, stddev_pop(m) / nullif(avg(m), 0) as everyday_cv from (
  select customer_id, strftime(tx_date, '%Y-%m') as ym, sum(-amount) as m from w where {basket_sql[EVERYDAY]} group by 1, 2)
group by 1
""")

con.execute("""
create table bal as
select customer_id, last(balance order by ts) as balance from tx group by 1
""")

df = con.execute("""
select c.customer_id, c.age, c.postal_code, a.*exclude(customer_id), p.payday_week_share, v.everyday_cv, b.balance
from cust c join agg a using (customer_id) left join payweek p using (customer_id)
left join vol v using (customer_id) left join bal b using (customer_id)
order by c.customer_id
""").df()

df["age_band"] = df["age"].map(age_band)
df["area"] = df["postal_code"].str[:2].map({"00": "Helsinki", "01": "Vantaa", "02": "Espoo"}).fillna("Uusimaa")
df["income"] = df["salary"] - df["swept"]
df["sweep_share"] = (df["swept"] / df["salary"]).fillna(0).clip(0, 1)
df["musts"] = df["fixed"] + df["surprise"]
df["buffer_months"] = (df["balance"].clip(lower=0) / df["musts"].where(df["musts"] > 0)).clip(upper=60)
df["savings_rate"] = (df["invested"] / df["income"].where(df["income"] > 0)).clip(-1, 1)
df["left_over_rate"] = ((df["income"] - df["spend"] - df["invested"]) / df["income"].where(df["income"] > 0)).clip(-2, 1)
df["fixed_share"] = (df["fixed"] / df["income"].where(df["income"] > 0)).clip(0, 3)
df["everyday_share"] = (df["everyday"] / df["income"].where(df["income"] > 0)).clip(0, 5)
df["weekend_share"] = df["weekend_eur_pm"] / df["everyday"].where(df["everyday"] > 0)
df["late_share"] = df["late_eur_pm"] / df["everyday"].where(df["everyday"] > 0)
df["small_share"] = df["small_eur_pm"] / df["everyday"].where(df["everyday"] > 0)
df["big_share"] = df["big_eur_pm"] / df["spend"].where(df["spend"] > 0)
df["dining_ratio"] = df["cat_Restaurants"] / (df["cat_Restaurants"] + df["cat_Groceries"]).where(
    (df["cat_Restaurants"] + df["cat_Groceries"]) > 0)
for c in ("Travel", "Entertainment", "Lifestyle", "Home & Tech"):
    df[f"share_{c}"] = df[f"cat_{c}"] / df["spend"].where(df["spend"] > 0)
# income fifths across everyone (salary, since that is what peers "earn")
df["income_band"] = (df["salary"].rank(pct=True) * 5).clip(upper=4.999).astype(int) + 1

out = B / "peers.parquet"
df.to_parquet(out, index=False)
print(f"{len(df)} customers -> {out}  window {win_start}..{win_end} (exclusive)")
print(df[["salary", "income", "fixed", "surprise", "everyday", "invested", "buffer_months", "payday_week_share",
          "weekend_share", "small_tx_pm", "everyday_cv", "overdraft_days", "dining_ratio"]].describe().round(2).to_string())
