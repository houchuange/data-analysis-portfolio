-- 03_cohort_retention.sql
-- 月度 cohort 留存
--
-- 口径：订单状态 delivered 且送达时间非空；窗口 2017-01-01 ~ 2018-09-01（左闭右开）。
-- 每个 -- @query: 标记开始一段独立查询，run_queries.py 会逐段执行并落 results/<name>.csv。

-- ========================================================================
-- 月度 cohort 留存（Q4）
-- @query: q4_cohort
-- ========================================================================
WITH valid AS (
    SELECT c.customer_unique_id AS uid,
           DATE_TRUNC('month', o.order_purchase_timestamp) AS m
    FROM orders o JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL
          AND o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
          AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
    GROUP BY 1, 2
),
cohort AS (
    SELECT uid, MIN(m) AS cohort_month FROM valid GROUP BY uid
),
act AS (
    SELECT c.cohort_month,
           DATEDIFF('month', c.cohort_month, v.m) AS period,
           COUNT(DISTINCT v.uid)                  AS users
    FROM cohort c JOIN valid v USING(uid)
    GROUP BY 1, 2
),
size AS (SELECT cohort_month, COUNT(*) AS cohort_size FROM cohort GROUP BY 1)
SELECT
    STRFTIME(a.cohort_month, '%Y-%m')                       AS cohort,
    s.cohort_size,
    a.period,
    a.users,
    ROUND(100.0 * a.users / s.cohort_size, 2)               AS retention_pct
FROM act a JOIN size s USING(cohort_month)
WHERE a.period BETWEEN 0 AND 6
ORDER BY a.cohort_month, a.period
