-- 01_order_wide.sql
-- 订单级宽表：后面所有查询都建在它上面
--
-- 口径：订单状态 delivered 且送达时间非空；窗口 2017-01-01 ~ 2018-09-01（左闭右开）。
-- 每个 -- @query: 标记开始一段独立查询，run_queries.py 会逐段执行并落 results/<name>.csv。

-- ========================================================================
-- 订单级宽表（Q1）
-- @query: q1_order_wide_sample
-- ========================================================================
WITH item_agg AS (
    SELECT order_id,
           SUM(price)                     AS gmv,
           SUM(freight_value)             AS freight,
           COUNT(*)                       AS n_items,
           COUNT(DISTINCT product_id)     AS n_products,
           COUNT(DISTINCT seller_id)      AS n_sellers
    FROM order_items
    GROUP BY order_id
),
pay_agg AS (
    SELECT order_id,
           SUM(payment_value)             AS paid,
           MAX(payment_installments)      AS max_inst,
           STRING_AGG(DISTINCT payment_type, '/' ORDER BY payment_type) AS pay_types
    FROM payments
    GROUP BY order_id
),
rev AS (
    SELECT order_id,
           AVG(review_score)              AS review_score,
           COUNT(*)                       AS n_reviews
    FROM reviews
    GROUP BY order_id
),
cat AS (      -- 一单多品类时取金额最大的那个品类作为主品类
    SELECT order_id, product_category_name_english AS main_category
    FROM (
        SELECT i.order_id,
               COALESCE(t.product_category_name_english, 'unknown') AS product_category_name_english,
               ROW_NUMBER() OVER (
                   PARTITION BY i.order_id
                   ORDER BY SUM(i.price) DESC
               ) AS rk
        FROM order_items i
        JOIN products p  ON p.product_id = i.product_id
        LEFT JOIN cat_tr t ON t.product_category_name = p.product_category_name
        GROUP BY i.order_id, 2
    )
    WHERE rk = 1
)
SELECT
    o.order_id,
    c.customer_unique_id                                   AS customer_uid,
    c.customer_state,
    o.order_status,
    o.order_purchase_timestamp                             AS purchase_ts,
    DATE_TRUNC('month', o.order_purchase_timestamp)        AS purchase_month,
    COALESCE(i.gmv, 0)                                     AS gmv,
    COALESCE(i.freight, 0)                                 AS freight,
    COALESCE(i.n_items, 0)                                 AS n_items,
    COALESCE(i.n_sellers, 0)                               AS n_sellers,
    p.paid,
    p.pay_types,
    p.max_inst,
    r.review_score,
    k.main_category,
    DATEDIFF('day', o.order_purchase_timestamp, o.order_approved_at)             AS days_to_approve,
    DATEDIFF('day', o.order_approved_at, o.order_delivered_carrier_date)         AS days_to_carrier,
    DATEDIFF('day', o.order_delivered_carrier_date, o.order_delivered_customer_date) AS days_in_transit,
    DATEDIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date) AS days_total,
    DATEDIFF('day', o.order_purchase_timestamp, o.order_estimated_delivery_date) AS days_promised,
    DATEDIFF('day', o.order_estimated_delivery_date, o.order_delivered_customer_date) AS delay_days
FROM orders o
JOIN customers c        ON c.customer_id = o.customer_id
LEFT JOIN item_agg i    ON i.order_id = o.order_id
LEFT JOIN pay_agg  p    ON p.order_id = o.order_id
LEFT JOIN rev      r    ON r.order_id = o.order_id
LEFT JOIN cat      k    ON k.order_id = o.order_id
WHERE o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
  AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
