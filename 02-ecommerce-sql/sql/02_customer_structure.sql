-- 02_customer_structure.sql
-- 客户结构：复购序列、复购间隔、真实回访率、RFM
--
-- 口径：订单状态 delivered 且送达时间非空；窗口 2017-01-01 ~ 2018-09-01（左闭右开）。
-- 每个 -- @query: 标记开始一段独立查询，run_queries.py 会逐段执行并落 results/<name>.csv。

-- ========================================================================
-- 客户终身购买次数分布（Q2）
-- @query: q2_lifetime
-- ========================================================================
WITH valid AS (
    SELECT DISTINCT c.customer_unique_id AS uid, o.order_id, o.order_purchase_timestamp AS ts
    FROM orders o JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
          AND o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
          AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
),
seq AS (
    SELECT uid, order_id, ts,
           ROW_NUMBER() OVER (PARTITION BY uid ORDER BY ts) AS order_no,
           LAG(ts)      OVER (PARTITION BY uid ORDER BY ts) AS prev_ts
    FROM valid
),
profile AS (
    SELECT uid,
           COUNT(*)                              AS orders,
           MIN(ts)                               AS first_ts,
           MAX(ts)                               AS last_ts,
           DATEDIFF('day', MIN(ts), MAX(ts))     AS lifespan_days
    FROM seq GROUP BY uid
)
SELECT
    orders AS lifetime_orders,
    COUNT(*)                                                  AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)        AS pct,
    ROUND(AVG(lifespan_days), 0)                              AS avg_lifespan_days
FROM profile
GROUP BY orders
ORDER BY orders

-- ========================================================================
-- 首购→N 购的间隔（Q2B）
-- @query: q2b_gap
-- ========================================================================
WITH valid AS (
    SELECT DISTINCT c.customer_unique_id AS uid, o.order_id, o.order_purchase_timestamp AS ts
    FROM orders o JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
          AND o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
          AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
),
seq AS (
    SELECT uid, order_id, ts,
           ROW_NUMBER() OVER (PARTITION BY uid ORDER BY ts) AS order_no,
           LAG(ts)      OVER (PARTITION BY uid ORDER BY ts) AS prev_ts
    FROM valid
)
SELECT
    order_no,
    COUNT(*)                                            AS repeat_events,
    ROUND(AVG(DATEDIFF('day', prev_ts, ts)), 1)         AS avg_gap_days,
    ROUND(MEDIAN(DATEDIFF('day', prev_ts, ts)), 0)      AS median_gap_days,
    MIN(DATEDIFF('day', prev_ts, ts))                   AS min_gap_days,
    MAX(DATEDIFF('day', prev_ts, ts))                   AS max_gap_days
FROM seq
WHERE prev_ts IS NOT NULL
GROUP BY order_no
ORDER BY order_no

-- ========================================================================
-- 复购间隔分布（Q2C）
-- @query: q2c_gap_dist
-- ========================================================================
WITH valid AS (
    SELECT DISTINCT c.customer_unique_id AS uid, o.order_id, o.order_purchase_timestamp AS ts
    FROM orders o JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
          AND o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
          AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
),
seq AS (
    SELECT uid, ts,
           ROW_NUMBER() OVER (PARTITION BY uid ORDER BY ts) AS order_no,
           LAG(ts)      OVER (PARTITION BY uid ORDER BY ts) AS prev_ts
    FROM valid
),
gap AS (SELECT DATEDIFF('day', prev_ts, ts) AS g FROM seq WHERE prev_ts IS NOT NULL)
SELECT
    CASE WHEN g <= 7   THEN '1 周内'
         WHEN g <= 30  THEN '8–30 天'
         WHEN g <= 90  THEN '31–90 天'
         WHEN g <= 180 THEN '91–180 天'
         WHEN g <= 365 THEN '181–365 天'
         ELSE '1 年以上' END AS gap_bucket,
    COUNT(*)                                        AS events,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM gap
GROUP BY 1
ORDER BY 1

-- ========================================================================
-- 剔除 7 天内的拆单后，真实回访率（Q2D）
-- @query: q2d_real_return
-- ========================================================================
WITH valid AS (
    SELECT DISTINCT c.customer_unique_id AS uid, o.order_id, o.order_purchase_timestamp AS ts
    FROM orders o JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
          AND o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
          AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
),
seq AS (
    SELECT uid, ts,
           ROW_NUMBER() OVER (PARTITION BY uid ORDER BY ts) AS order_no,
           LAG(ts)      OVER (PARTITION BY uid ORDER BY ts) AS prev_ts
    FROM valid
),
per AS (
    SELECT uid,
           COUNT(*)                                  AS orders,
           MAX(CASE WHEN DATEDIFF('day', prev_ts, ts) > 7 THEN 1 ELSE 0 END) AS has_real_return
    FROM seq GROUP BY uid
)
SELECT
    COUNT(*)                                                              AS customers,
    SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END)                           AS ever_repeat,
    SUM(CASE WHEN has_real_return = 1 THEN 1 ELSE 0 END)                  AS real_return,
    ROUND(100.0 * SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_pct,
    ROUND(100.0 * SUM(CASE WHEN has_real_return = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS real_return_pct
FROM per

-- ========================================================================
-- RFM 客户分层（Q3）
-- @query: q3_rfm
-- ========================================================================
WITH valid AS (
    SELECT c.customer_unique_id AS uid, o.order_id,
           o.order_purchase_timestamp AS ts, i.gmv
    FROM orders o
    JOIN customers c   ON c.customer_id = o.customer_id
    JOIN (SELECT order_id, SUM(price + freight_value) AS gmv FROM order_items GROUP BY 1) i
         ON i.order_id = o.order_id
    WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
          AND o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
          AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
),
base AS (
    SELECT uid,
           DATEDIFF('day', MAX(ts), DATE '2018-10-17')  AS recency_days,
           COUNT(DISTINCT order_id)                     AS frequency,
           SUM(gmv)                                     AS monetary
    FROM valid GROUP BY uid
),
scored AS (
    SELECT *,
           -- 加 uid 做 tiebreaker：只按 recency/monetary 排序时，分位边界上的并列行
           -- 会因为执行顺序不同落到不同档，重跑一次结果就变
           NTILE(5) OVER (ORDER BY recency_days DESC, uid) AS r_score,  -- 5 = 最近买过
           NTILE(5) OVER (ORDER BY monetary ASC, uid)      AS m_score,  -- 5 = 花得最多
           CASE WHEN frequency >= 3 THEN 5
                WHEN frequency  = 2 THEN 3
                ELSE 1 END                               AS f_score
    FROM base
),
seg AS (
    SELECT *,
           CASE WHEN r_score >= 4 AND f_score >= 3 AND m_score >= 4 THEN '重要价值'
                WHEN r_score <  4 AND f_score >= 3 AND m_score >= 4 THEN '重要保持'
                WHEN r_score >= 4 AND f_score <  3 AND m_score >= 4 THEN '重要发展'
                WHEN r_score <  4 AND f_score <  3 AND m_score >= 4 THEN '重要挽留'
                WHEN r_score >= 4 AND f_score >= 3 AND m_score <  4 THEN '一般价值'
                WHEN r_score <  4 AND f_score >= 3 AND m_score <  4 THEN '一般保持'
                WHEN r_score >= 4 AND f_score <  3 AND m_score <  4 THEN '一般发展'
                ELSE '一般挽留' END                       AS segment
    FROM scored
)
SELECT
    segment,
    COUNT(*)                                                AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)      AS customer_pct,
    ROUND(SUM(monetary), 0)                                 AS revenue,
    ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 2) AS revenue_pct,
    ROUND(AVG(monetary), 1)                                 AS arpu,
    ROUND(AVG(frequency), 2)                                AS avg_orders,
    ROUND(AVG(recency_days), 0)                             AS avg_recency
FROM seg
GROUP BY segment
ORDER BY revenue DESC

-- ========================================================================
-- 金额档 × 复购：RFM 的二维读法（Q3B）
-- @query: q3b_matrix
-- ========================================================================
WITH valid AS (
    SELECT c.customer_unique_id AS uid, o.order_id,
           o.order_purchase_timestamp AS ts, i.gmv
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    JOIN (SELECT order_id, SUM(price + freight_value) AS gmv FROM order_items GROUP BY 1) i
         ON i.order_id = o.order_id
    WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
          AND o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
          AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
),
base AS (
    SELECT uid, COUNT(DISTINCT order_id) AS frequency, SUM(gmv) AS monetary
    FROM valid GROUP BY uid
),
q AS (SELECT NTILE(4) OVER (ORDER BY monetary, uid) AS m_quartile, * FROM base)
SELECT
    CASE m_quartile WHEN 1 THEN 'Q1 低'
                    WHEN 2 THEN 'Q2'
                    WHEN 3 THEN 'Q3'
                    ELSE 'Q4 高' END                    AS monetary_tier,
    CASE WHEN frequency >= 2 THEN '复购客户' ELSE '一次性客户' END AS f_group,
    COUNT(*)                                             AS customers,
    ROUND(AVG(monetary), 0)                              AS avg_spend,
    ROUND(SUM(monetary), 0)                              AS revenue,
    ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 2) AS revenue_pct
FROM q
GROUP BY 1, 2
ORDER BY 1, 2
