-- 05_delivery_and_reviews.sql
-- 送达时效与评分：延误分箱、差评归因
--
-- 口径：订单状态 delivered 且送达时间非空；窗口 2017-01-01 ~ 2018-09-01（左闭右开）。
-- 每个 -- @query: 标记开始一段独立查询，run_queries.py 会逐段执行并落 results/<name>.csv。

-- ========================================================================
-- 延误天数 × 评分（Q6）
-- @query: q6_delay_score
-- ========================================================================
WITH d AS (
    SELECT o.order_id,
           r.review_score,
           DATEDIFF('day', o.order_estimated_delivery_date,
                          o.order_delivered_customer_date) AS delay_days,
           DATEDIFF('day', o.order_purchase_timestamp,
                          o.order_delivered_customer_date) AS total_days
    FROM orders o
    JOIN (SELECT order_id, AVG(review_score) AS review_score FROM reviews GROUP BY 1) r
      ON r.order_id = o.order_id
    WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
          AND o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
          AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
)
SELECT
    CASE WHEN delay_days <= -15 THEN '早到 15 天以上'
         WHEN delay_days <=  -7 THEN '早到 7–14 天'
         WHEN delay_days <=  -1 THEN '早到 1–6 天'
         WHEN delay_days  =   0 THEN '准时'
         WHEN delay_days <=   3 THEN '晚 1–3 天'
         WHEN delay_days <=   7 THEN '晚 4–7 天'
         WHEN delay_days <=  15 THEN '晚 8–15 天'
         ELSE '晚 15 天以上' END                                    AS delay_bucket,
    COUNT(*)                                                        AS orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)              AS order_pct,
    ROUND(AVG(review_score), 2)                                     AS avg_score,
    ROUND(100.0 * SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END) / COUNT(*), 1) AS low_score_pct,
    ROUND(100.0 * SUM(CASE WHEN review_score  = 5 THEN 1 ELSE 0 END) / COUNT(*), 1) AS five_star_pct
FROM d
GROUP BY 1
ORDER BY 1

-- ========================================================================
-- 差评归因（Q6B）
-- @query: q6b_attribution
-- ========================================================================
WITH d AS (
    SELECT o.order_id, r.review_score,
           DATEDIFF('day', o.order_estimated_delivery_date,
                          o.order_delivered_customer_date) AS delay_days
    FROM orders o
    JOIN (SELECT order_id, AVG(review_score) AS review_score FROM reviews GROUP BY 1) r
      ON r.order_id = o.order_id
    WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
          AND o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
          AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
)
SELECT
    COUNT(*)                                                             AS orders,
    ROUND(100.0 * SUM(CASE WHEN delay_days > 0 THEN 1 ELSE 0 END) / COUNT(*), 2)  AS late_order_share,
    SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END)                   AS low_reviews,
    ROUND(100.0 * SUM(CASE WHEN review_score <= 2 AND delay_days > 0 THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END), 0), 1)      AS low_review_from_late,
    SUM(CASE WHEN review_score = 5 THEN 1 ELSE 0 END)                    AS five_star,
    ROUND(100.0 * SUM(CASE WHEN review_score = 5 AND delay_days > 0 THEN 1 ELSE 0 END)
          / NULLIF(SUM(CASE WHEN review_score = 5 THEN 1 ELSE 0 END), 0), 1)       AS lost_five_star
FROM d
