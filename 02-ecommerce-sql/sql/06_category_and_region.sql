-- 06_category_and_region.sql
-- 品类集中度、州维度时效、月度趋势
--
-- 口径：订单状态 delivered 且送达时间非空；窗口 2017-01-01 ~ 2018-09-01（左闭右开）。
-- 每个 -- @query: 标记开始一段独立查询，run_queries.py 会逐段执行并落 results/<name>.csv。

-- ========================================================================
-- 品类帕累托（Q7）
-- @query: q7_pareto
-- ========================================================================
WITH cat AS (
    SELECT COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
           SUM(i.price)          AS gmv,
           SUM(i.freight_value)  AS freight,
           COUNT(DISTINCT i.order_id) AS orders
    FROM order_items i
    JOIN orders o    ON o.order_id = i.order_id
    JOIN products p  ON p.product_id = i.product_id
    LEFT JOIN cat_tr t ON t.product_category_name = p.product_category_name
    WHERE o.order_status = 'delivered'
      AND o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
      AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
    GROUP BY 1
),
ranked AS (
    SELECT category, gmv, freight, orders,
           ROW_NUMBER()                         OVER (ORDER BY gmv DESC)          AS rank,
           SUM(gmv)                             OVER ()                           AS total_gmv,
           SUM(gmv)                             OVER (ORDER BY gmv DESC
                                                       ROWS BETWEEN UNBOUNDED PRECEDING
                                                       AND CURRENT ROW)            AS cum_gmv
    FROM cat
)
SELECT rank, category, orders,
       ROUND(gmv, 0)                                        AS gmv,
       ROUND(100.0 * gmv / total_gmv, 2)                    AS gmv_pct,
       ROUND(100.0 * cum_gmv / total_gmv, 2)                AS cum_gmv_pct,
       ROUND(100.0 * freight / gmv, 1)                      AS freight_pct
FROM ranked
ORDER BY rank

-- ========================================================================
-- 州维度时效与运费（Q8）
-- @query: q8_state
-- ========================================================================
SELECT
    c.customer_state                                         AS state,
    COUNT(*)                                                 AS orders,
    ROUND(AVG(DATEDIFF('day', o.order_purchase_timestamp,
                            o.order_delivered_customer_date)), 1) AS avg_days,
    ROUND(AVG(DATEDIFF('day', o.order_purchase_timestamp,
                            o.order_estimated_delivery_date)), 1) AS avg_promised,
    ROUND(100.0 * SUM(CASE WHEN DATEDIFF('day', o.order_estimated_delivery_date,
                                              o.order_delivered_customer_date) > 0
                       THEN 1 ELSE 0 END) / COUNT(*), 1)     AS late_pct,
    ROUND(SUM(i.freight) / SUM(i.gmv) * 100, 1)               AS freight_pct,
    ROUND(AVG(i.gmv), 0)                                     AS avg_order_value,
    ROUND(AVG(r.review_score), 2)                            AS avg_score
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN (SELECT order_id, SUM(price) gmv, SUM(freight_value) freight
      FROM order_items GROUP BY 1) i ON i.order_id = o.order_id
LEFT JOIN (SELECT order_id, AVG(review_score) review_score FROM reviews GROUP BY 1) r
       ON r.order_id = o.order_id
WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
          AND o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
          AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
GROUP BY 1
HAVING COUNT(*) >= 300
ORDER BY late_pct DESC

-- ========================================================================
-- 月度经营趋势（Q9）
-- @query: q9_monthly
-- ========================================================================
SELECT
    STRFTIME(DATE_TRUNC('month', o.order_purchase_timestamp), '%Y-%m') AS month,
    COUNT(DISTINCT o.order_id)                                        AS orders,
    ROUND(SUM(i.gmv), 0)                                              AS gmv,
    ROUND(SUM(i.gmv) / COUNT(DISTINCT o.order_id), 1)                 AS aov,
    ROUND(100.0 * SUM(CASE WHEN DATEDIFF('day', o.order_estimated_delivery_date,
                                              o.order_delivered_customer_date) <= 0
                       THEN 1 ELSE 0 END) / COUNT(*), 1)          AS on_time_pct,
    ROUND(AVG(r.review_score), 2)                                     AS avg_score
FROM orders o
JOIN (SELECT order_id, SUM(price) gmv FROM order_items GROUP BY 1) i
  ON i.order_id = o.order_id
LEFT JOIN (SELECT order_id, AVG(review_score) review_score FROM reviews GROUP BY 1) r
       ON r.order_id = o.order_id
WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
          AND o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
          AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
GROUP BY 1
ORDER BY 1
