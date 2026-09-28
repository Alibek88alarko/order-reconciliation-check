# Order reconciliation check: find the row that breaks the total

Two sources hold the same orders: the shop export (source of truth) and the reporting table. The totals differ by
105.99 and nobody knows why. This tool lists every row responsible, classified, with the day it belongs to, and
nothing else.

Stack: standard SQL that runs unchanged on BigQuery and on DuckDB (used for tests and for CSV files), Python 3.11,
pytest. Plus an Apps Script that pulls a BigQuery query into a Google Sheet with a "Last refreshed" cell.

## Measured result

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -q
```

```
.....                                                                    [100%]
5 passed in 1.14s
```

Then on generated data: 10,000 orders in the shop export, a report copy with 7 planted errors
(2 orders missing, 2 duplicated, 2 amounts changed, 1 phantom order that the shop never had):

```
$ python -m reconcile.generate 10000 data
wrote 10000 shop orders, 10001 report rows, 7 planted errors -> data/

$ python -m reconcile.run data/shop_export.csv data/report_table.csv --out findings.csv
shop: 10000 rows, total 1289456.32    report: 10001 rows, total 1289562.31    difference 105.99
findings: 7 in 100 ms  amount_mismatch=2, duplicate_in_report=2, extra_in_report=1, missing_in_report=2
  2026-08-02  missing_in_report    O107411    shop total 221.22 EUR, no row in report
  2026-08-10  amount_mismatch      O109623    shop 76.31 vs report 88.81, diff 12.50
  2026-08-23  duplicate_in_report  O107629    order appears 2 times in report; total counted 2x
  2026-08-27  extra_in_report      O999999    report total 49.90 EUR, no such order in shop
  2026-09-02  amount_mismatch      O108320    shop 98.74 vs report 98.75, diff 0.01
  2026-09-02  missing_in_report    O109171    shop total 108.35 EUR, no row in report
  2026-09-12  duplicate_in_report  O107402    order appears 2 times in report; total counted 2x
days where totals differ: 6
  2026-08-02  shop 225 orders / 28849.24   report 224 orders / 28628.02   diff -221.22
  ...
written: findings.csv
```

Seven planted, seven found, zero false positives, and the six days whose totals moved are exactly the days those
seven rows belong to. Exit code is 1 when there is any finding, so a scheduler can alert on it.

What the 5 tests check:

| Test | What is measured |
|---|---|
| `test_finds_exactly_the_planted_errors` | The set of (check, order_id) returned equals the planted set. Not "at least", equals. Row counts 10,000 vs 10,001 are asserted too. |
| `test_every_finding_explains_itself` | Every row carries the order id, the date and a sentence a non-SQL reader understands ("shop 76.31 vs report 88.81, diff 12.50"). |
| `test_one_cent_is_a_finding_not_noise` | A 0.01 rounding drift is reported next to the 12.50 error. A total that is off by a cent is still wrong. |
| `test_daily_totals_flag_only_affected_days` | The daily comparison flags exactly the days touched by the findings and no other day. |
| `test_identical_sources_produce_nothing` | Two identical sources give an empty report. |

## How it works

- `reconcile/checks.sql`: five checks as one query, plain joins and group-bys, no dialect tricks, so the same file runs
  in the BigQuery console against `shop` and `report` tables. Duplicates are counted once in `report_counts`, then a
  deduplicated view is used for the value comparison, so a duplicated order is not also reported as an amount mismatch.
- `reconcile/daily_totals.sql`: totals per day from both sides, `FULL OUTER JOIN`, only differing days returned.
- `reconcile/run.py`: loads two CSVs into DuckDB with explicit types (`DECIMAL(12,2)` for money, never float), runs
  both queries, prints the report, writes `findings.csv`.
- `reconcile/generate.py`: deterministic synthetic data with a known answer, so the tests assert equality, not
  plausibility.
- `sheets/bigquery_to_sheet.gs`: Apps Script that runs a BigQuery query and writes it to a tab with a "Last refreshed"
  cell, a bold header, frozen rows and a formula-based TOTAL row, so the number people quote is the one on the sheet.

## Honest scope note

Built in one evening as a work sample. BigQuery-specific pieces (scheduled queries, partitioning, the Sheets
connector) are not exercised here because the repository has no GCP project attached; the SQL is written to the
BigQuery standard dialect and tested on DuckDB. On a real setup the first step is to run it read-only against the
documented tables and compare with the existing report before changing anything.
