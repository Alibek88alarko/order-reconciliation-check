-- Daily totals side by side. A day appears only when the two sides differ.
WITH s AS (
  SELECT order_date, COUNT(*) AS orders, ROUND(SUM(total), 2) AS total FROM shop GROUP BY order_date
),
r AS (
  SELECT order_date, COUNT(*) AS orders, ROUND(SUM(total), 2) AS total FROM report GROUP BY order_date
)
SELECT COALESCE(s.order_date, r.order_date) AS order_date,
       s.orders AS shop_orders, r.orders AS report_orders,
       s.total AS shop_total, r.total AS report_total,
       ROUND(COALESCE(r.total, 0) - COALESCE(s.total, 0), 2) AS diff
FROM s
FULL OUTER JOIN r ON r.order_date = s.order_date
WHERE s.orders IS NULL OR r.orders IS NULL OR s.orders <> r.orders OR ABS(s.total - r.total) > 0.005
ORDER BY order_date
