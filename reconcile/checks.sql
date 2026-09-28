-- Reconciliation checks. Standard SQL that runs unchanged on BigQuery and on DuckDB (used for the tests).
-- Two tables: shop (the source of truth: the web shop / marketplace export) and report (what the reporting layer holds).
-- Columns in both: order_id STRING, order_date DATE, country STRING, total NUMERIC, currency STRING.
-- Every finding has: check_name, order_id, order_date, detail. One row per problem, nothing else.

WITH
report_counts AS (
  SELECT order_id, COUNT(*) AS n
  FROM report
  GROUP BY order_id
),
report_dedup AS (
  -- one representative row per order_id for the value comparison; duplicates are reported separately
  SELECT order_id, MIN(order_date) AS order_date, MIN(country) AS country, MIN(total) AS total, MIN(currency) AS currency
  FROM report
  GROUP BY order_id
),
missing_in_report AS (
  SELECT 'missing_in_report' AS check_name, s.order_id, s.order_date,
         CONCAT('shop total ', CAST(s.total AS STRING), ' ', s.currency, ', no row in report') AS detail
  FROM shop s
  LEFT JOIN report_dedup r ON r.order_id = s.order_id
  WHERE r.order_id IS NULL
),
extra_in_report AS (
  SELECT 'extra_in_report' AS check_name, r.order_id, r.order_date,
         CONCAT('report total ', CAST(r.total AS STRING), ' ', r.currency, ', no such order in shop') AS detail
  FROM report_dedup r
  LEFT JOIN shop s ON s.order_id = r.order_id
  WHERE s.order_id IS NULL
),
duplicate_in_report AS (
  SELECT 'duplicate_in_report' AS check_name, r.order_id, r.order_date,
         CONCAT('order appears ', CAST(c.n AS STRING), ' times in report; total counted ', CAST(c.n AS STRING), 'x') AS detail
  FROM report_counts c
  JOIN report_dedup r ON r.order_id = c.order_id
  WHERE c.n > 1
),
amount_mismatch AS (
  SELECT 'amount_mismatch' AS check_name, s.order_id, s.order_date,
         CONCAT('shop ', CAST(s.total AS STRING), ' vs report ', CAST(r.total AS STRING),
                ', diff ', CAST(ROUND(r.total - s.total, 2) AS STRING)) AS detail
  FROM shop s
  JOIN report_dedup r ON r.order_id = s.order_id
  WHERE ABS(r.total - s.total) > 0.005
),
currency_mismatch AS (
  SELECT 'currency_mismatch' AS check_name, s.order_id, s.order_date,
         CONCAT('shop ', s.currency, ' vs report ', r.currency) AS detail
  FROM shop s
  JOIN report_dedup r ON r.order_id = s.order_id
  WHERE s.currency <> r.currency
)
SELECT * FROM missing_in_report
UNION ALL SELECT * FROM extra_in_report
UNION ALL SELECT * FROM duplicate_in_report
UNION ALL SELECT * FROM amount_mismatch
UNION ALL SELECT * FROM currency_mismatch
ORDER BY order_date, check_name, order_id
