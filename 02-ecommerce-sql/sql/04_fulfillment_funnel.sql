-- 04_fulfillment_funnel.sql
-- 履约漏斗与支付确认
--
-- 口径：订单状态 delivered 且送达时间非空；窗口 2017-01-01 ~ 2018-09-01（左闭右开）。
-- 每个 -- @query: 标记开始一段独立查询，run_queries.py 会逐段执行并落 results/<name>.csv。

-- ========================================================================
-- 履约漏斗（Q5）
-- @query: q5_funnel
-- ========================================================================
WITH base AS (
    SELECT o.order_id, o.order_status,
           o.order_approved_at,
           o.order_delivered_carrier_date,
           o.order_delivered_customer_date,
           p.paid
    FROM orders o
    LEFT JOIN (SELECT order_id, SUM(payment_value) AS paid FROM payments GROUP BY 1) p
           ON p.order_id = o.order_id
    WHERE o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
      AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
),
steps AS (
    SELECT
        COUNT(*)                                                                   AS s1_placed,
        SUM(CASE WHEN order_approved_at IS NOT NULL THEN 1 ELSE 0 END)             AS s2_approved,
        SUM(CASE WHEN order_delivered_carrier_date IS NOT NULL THEN 1 ELSE 0 END)  AS s3_shipped,
        SUM(CASE WHEN order_status = 'delivered'
                  AND order_delivered_customer_date IS NOT NULL THEN 1 ELSE 0 END) AS s4_delivered,
        SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END)                 AS canceled,
        SUM(CASE WHEN order_status = 'unavailable' THEN 1 ELSE 0 END)              AS unavailable,
        SUM(CASE WHEN order_status NOT IN ('delivered','canceled','unavailable')
                 THEN 1 ELSE 0 END)                                                AS in_flight
    FROM base
)
SELECT '下单'  AS step, s1_placed AS orders, 100.0 AS step_pct, 100.0 AS total_pct FROM steps
UNION ALL SELECT '支付确认', s2_approved,
       100.0 * s2_approved / s1_placed, 100.0 * s2_approved / s1_placed FROM steps
UNION ALL SELECT '交承运商', s3_shipped,
       100.0 * s3_shipped / s2_approved, 100.0 * s3_shipped / s1_placed FROM steps
UNION ALL SELECT '送达客户', s4_delivered,
       100.0 * s4_delivered / s3_shipped, 100.0 * s4_delivered / s1_placed FROM steps

-- ========================================================================
-- 各支付方式的支付确认时长（Q5B）
-- @query: q5b_approve
-- ========================================================================
WITH base AS (
    SELECT o.order_id, o.order_status, o.order_approved_at, o.order_purchase_timestamp,
           p.payment_type_first
    FROM orders o
    LEFT JOIN (
        SELECT order_id,
               STRING_AGG(DISTINCT payment_type, '/') AS payment_type_first
        FROM payments GROUP BY 1
    ) p ON p.order_id = o.order_id
    WHERE o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
      AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
)
SELECT
    COALESCE(payment_type_first, '(无支付记录)')                    AS payment_type,
    COUNT(*)                                                        AS orders,
    ROUND(AVG(DATEDIFF('hour', order_purchase_timestamp, order_approved_at)), 1) AS avg_hours_to_approve,
    ROUND(MEDIAN(DATEDIFF('hour', order_purchase_timestamp, order_approved_at)), 1) AS median_hours
FROM base
GROUP BY 1
HAVING COUNT(*) >= 100
ORDER BY orders DESC
