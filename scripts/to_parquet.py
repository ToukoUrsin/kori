import duckdb, sys
src, out = sys.argv[1], sys.argv[2]
con = duckdb.connect()
con.execute(f"""
copy (
  select customer_id, bank_account_id, tx_date,
         strptime(tx_timestamp, '%d%b%y:%H:%M:%S') as ts,
         category, tx_amount_eur as amount, balance_after_eur as balance,
         transaction_type as type, merchant_id, cast(mcc_code as integer) as mcc
  from read_csv('{src}/tx_junction_transactions.csv', header=true, types={{'mcc_code':'VARCHAR'}})
  order by customer_id, ts
) to '{out}/tx.parquet' (format parquet, compression zstd, row_group_size 60000)
""")
con.execute(f"copy (select customer_id, customer_postal_code as postal_code, customer_age as age from read_csv('{src}/tx_customers_junction.csv', header=true, types={{'customer_postal_code':'VARCHAR'}})) to '{out}/customers.parquet' (format parquet)")
print(con.execute(f"select count(*), min(ts), max(ts) from '{out}/tx.parquet'").fetchall())
print(con.execute(f"select * from '{out}/customers.parquet' limit 3").fetchall())
