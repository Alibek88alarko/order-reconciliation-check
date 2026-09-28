"""Run the reconciliation between two CSV exports and print every row that breaks the total.

    python -m reconcile.run data/shop_export.csv data/report_table.csv --out findings.csv

Exit code 0 when the two sources agree, 1 when there is at least one finding (so a scheduler can alert).
The same SQL runs on BigQuery: point it at the two tables instead of the CSVs.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent


def load(con: duckdb.DuckDBPyConnection, name: str, csv_path: str) -> None:
    con.execute(f"""
        CREATE OR REPLACE TABLE {name} AS
        SELECT CAST(order_id AS VARCHAR) AS order_id,
               CAST(order_date AS DATE) AS order_date,
               CAST(country AS VARCHAR) AS country,
               CAST(total AS DECIMAL(12,2)) AS total,
               CAST(currency AS VARCHAR) AS currency
        FROM read_csv_auto('{csv_path}', header=true)
    """)


def reconcile(shop_csv: str, report_csv: str):
    con = duckdb.connect()
    load(con, "shop", shop_csv)
    load(con, "report", report_csv)
    findings = con.execute((HERE / "checks.sql").read_text()).fetchall()
    days = con.execute((HERE / "daily_totals.sql").read_text()).fetchall()
    counts = {
        "shop_rows": con.execute("SELECT COUNT(*) FROM shop").fetchone()[0],
        "report_rows": con.execute("SELECT COUNT(*) FROM report").fetchone()[0],
        "shop_total": con.execute("SELECT ROUND(SUM(total), 2) FROM shop").fetchone()[0],
        "report_total": con.execute("SELECT ROUND(SUM(total), 2) FROM report").fetchone()[0],
    }
    return findings, days, counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("shop_csv")
    ap.add_argument("report_csv")
    ap.add_argument("--out", default=None, help="write findings to this CSV")
    a = ap.parse_args(argv)

    t0 = time.perf_counter()
    findings, days, c = reconcile(a.shop_csv, a.report_csv)
    ms = int((time.perf_counter() - t0) * 1000)

    print(f"shop: {c['shop_rows']} rows, total {c['shop_total']}    report: {c['report_rows']} rows, total {c['report_total']}"
          f"    difference {round(float(c['report_total']) - float(c['shop_total']), 2)}")
    by_check: dict[str, int] = {}
    for f in findings:
        by_check[f[0]] = by_check.get(f[0], 0) + 1
    print(f"findings: {len(findings)} in {ms} ms  " + ", ".join(f"{k}={v}" for k, v in sorted(by_check.items())))
    for check_name, order_id, order_date, detail in findings:
        print(f"  {order_date}  {check_name:<20} {order_id:<10} {detail}")
    if days:
        print(f"days where totals differ: {len(days)}")
        for d in days:
            print(f"  {d[0]}  shop {d[1]} orders / {d[3]}   report {d[2]} orders / {d[4]}   diff {d[5]}")
    if a.out:
        import csv
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(["check_name", "order_id", "order_date", "detail"]); w.writerows(findings)
        print(f"written: {a.out}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
