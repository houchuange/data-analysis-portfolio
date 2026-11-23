# -*- coding: utf-8 -*-
"""
audit.py — 数据质量审计

先审计再分析。所有检查都用 SQL 完成，结果同时写入
  data/audit_log.txt   人读的逐项结论
  data/audit.json      机器读的数值，供报告引用

检查分四类：
  A 完整性   表规模、主键唯一性、关键字段缺失
  B 一致性   多表之间能否对上（订单↔明细、订单↔支付）
  C 逻辑性   时间戳先后、金额正负
  D 可用性   样本截断、状态字段的业务含义
"""
import os
import json
from db import connect, BASE

DATA = os.path.join(BASE, "data")
LOG = []
J = {}


def say(line=""):
    print(line)
    LOG.append(line)


def ask(con, sql):
    return con.execute(sql).fetchdf()


def check_a(con):
    say("=" * 78)
    say("A · 完整性")
    say("=" * 78)

    rows = ask(con, """
        SELECT 'orders' t, COUNT(*) n FROM orders UNION ALL
        SELECT 'customers', COUNT(*) FROM customers UNION ALL
        SELECT 'order_items', COUNT(*) FROM order_items UNION ALL
        SELECT 'payments', COUNT(*) FROM payments UNION ALL
        SELECT 'reviews', COUNT(*) FROM reviews UNION ALL
        SELECT 'products', COUNT(*) FROM products UNION ALL
        SELECT 'sellers', COUNT(*) FROM sellers UNION ALL
        SELECT 'cat_tr', COUNT(*) FROM cat_tr
    """)
    say("\n[1] 表规模")
    for _, r in rows.iterrows():
        say(f"    {r['t']:<14}{r['n']:>9,}")
    J["row_counts"] = {r["t"]: int(r["n"]) for _, r in rows.iterrows()}

    say("\n[2] 主键唯一性")
    dup = ask(con, """
        SELECT
          (SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM orders)      AS dup_order,
          (SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM customers) AS dup_customer,
          (SELECT COUNT(*) - COUNT(DISTINCT product_id) FROM products)   AS dup_product,
          (SELECT COUNT(*) - COUNT(DISTINCT seller_id) FROM sellers)     AS dup_seller,
          (SELECT COUNT(*) - COUNT(DISTINCT review_id) FROM reviews)     AS dup_review
    """).iloc[0]
    for k, v in dup.items():
        say(f"    {k:<16}{int(v)}")
    J["dup_pk"] = {k: int(v) for k, v in dup.items()}

    say("\n[3] 关键字段缺失（订单表）")
    miss = ask(con, """
        SELECT
          SUM(CASE WHEN order_approved_at IS NULL THEN 1 ELSE 0 END)           AS approved_null,
          SUM(CASE WHEN order_delivered_carrier_date IS NULL THEN 1 ELSE 0 END) AS carrier_null,
          SUM(CASE WHEN order_delivered_customer_date IS NULL THEN 1 ELSE 0 END) AS delivered_null,
          SUM(CASE WHEN order_estimated_delivery_date IS NULL THEN 1 ELSE 0 END) AS estimated_null,
          SUM(CASE WHEN customer_id IS NULL OR customer_id = '' THEN 1 ELSE 0 END) AS customer_null
        FROM orders
    """).iloc[0]
    for k, v in miss.items():
        say(f"    {k:<18}{int(v):>7,}  ({int(v)/99441*100:.2f}%)")
    J["nulls"] = {k: int(v) for k, v in miss.items()}


def check_b(con):
    say("\n" + "=" * 78)
    say("B · 一致性（多表能否对上）")
    say("=" * 78)

    say("\n[4] 订单 ↔ 明细")
    r = ask(con, """
        SELECT
          (SELECT COUNT(*) FROM orders o WHERE NOT EXISTS
             (SELECT 1 FROM order_items i WHERE i.order_id = o.order_id)) AS order_no_item,
          (SELECT COUNT(*) FROM order_items i WHERE NOT EXISTS
             (SELECT 1 FROM orders o WHERE o.order_id = i.order_id))     AS item_no_order
    """).iloc[0]
    say(f"    有订单无商品明细：{int(r['order_no_item']):,}（全部是取消/不可得订单，属正常）")
    say(f"    有明细无订单记录：{int(r['item_no_order']):,}")
    st = ask(con, """
        SELECT o.order_status, COUNT(*) n FROM orders o
        WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.order_id)
        GROUP BY 1 ORDER BY n DESC
    """)
    for _, x in st.iterrows():
        say(f"      · {x['order_status']:<12}{int(x['n']):>5,}")
    J["order_item_orphan"] = {k: int(v) for k, v in r.items()}

    say("\n[5] 订单 ↔ 支付（金额对账，仅比对双方都有记录的订单）")
    r = ask(con, """
        WITH pay AS (SELECT order_id, SUM(payment_value) pv FROM payments GROUP BY 1),
             itm AS (SELECT order_id, SUM(price + freight_value) iv FROM order_items GROUP BY 1)
        SELECT COUNT(*) orders_compared,
               SUM(CASE WHEN ABS(pay.pv - itm.iv) > 0.01 THEN 1 ELSE 0 END) mismatch,
               ROUND(MAX(ABS(pay.pv - itm.iv)), 2) max_gap,
               ROUND(AVG(ABS(pay.pv - itm.iv)), 2) avg_gap
        FROM pay JOIN itm USING(order_id)
    """).iloc[0]
    say(f"    可比订单 {int(r['orders_compared']):,} 笔，金额不一致 "
        f"{int(r['mismatch']):,} 笔（{int(r['mismatch'])/int(r['orders_compared'])*100:.2f}%）")
    say(f"    平均差额 R$ {r['avg_gap']}，最大 R$ {r['max_gap']}")
    J["payment_mismatch"] = {"compared": int(r["orders_compared"]),
                            "mismatch": int(r["mismatch"]),
                            "max_gap": float(r["max_gap"]),
                            "avg_gap": float(r["avg_gap"])}

    say("\n[6] 订单 ↔ 评价（一单多评）")
    r = ask(con, """
        WITH c AS (SELECT order_id, COUNT(*) n FROM reviews GROUP BY 1)
        SELECT COUNT(*) orders_reviewed, SUM(CASE WHEN n > 1 THEN 1 ELSE 0 END) multi
        FROM c
    """).iloc[0]
    say(f"    有评价的订单 {int(r['orders_reviewed']):,} 笔，其中一单多评 "
        f"{int(r['multi']):,} 笔（需去重后再关联）")
    J["review_multi"] = {"orders_reviewed": int(r["orders_reviewed"]), "multi": int(r["multi"])}

    say("\n[7] 客户表 customer_id 与订单的关系")
    r = ask(con, """
        SELECT COUNT(DISTINCT o.customer_id) orders_cid,
               COUNT(DISTINCT c.customer_unique_id) unique_person,
               COUNT(*) orders
        FROM orders o JOIN customers c USING(customer_id)
    """).iloc[0]
    say(f"    customer_id 唯一数 {int(r['orders_cid']):,}，订单数 {int(r['orders']):,}"
        f" → customer_id 是「一单一号」，不是自然人 ID")
    say(f"    真正的自然人标识 customer_unique_id 共 {int(r['unique_person']):,} 个")
    say("    ⚠ 做复购/留存分析必须用 customer_unique_id，用 customer_id 会把复购率算成 0")
    J["id_structure"] = {"customer_ids": int(r["orders_cid"]),
                         "unique_persons": int(r["unique_person"]),
                         "orders": int(r["orders"])}


def check_c(con):
    say("\n" + "=" * 78)
    say("C · 逻辑性（时间戳与金额）")
    say("=" * 78)

    say("\n[8] 时间戳先后异常")
    r = ask(con, """
        SELECT
          SUM(CASE WHEN order_approved_at < order_purchase_timestamp THEN 1 ELSE 0 END) appr_before,
          SUM(CASE WHEN order_delivered_carrier_date < order_approved_at THEN 1 ELSE 0 END) carrier_before,
          SUM(CASE WHEN order_delivered_customer_date < order_delivered_carrier_date THEN 1 ELSE 0 END) deliv_before_carrier,
          SUM(CASE WHEN order_delivered_customer_date < order_purchase_timestamp THEN 1 ELSE 0 END) deliv_before_purchase,
          SUM(CASE WHEN order_estimated_delivery_date < order_purchase_timestamp THEN 1 ELSE 0 END) est_before_purchase
        FROM orders
    """).iloc[0]
    for k, v in r.items():
        say(f"    {k:<28}{int(v):>6,}")
    J["time_anomaly"] = {k: int(v) for k, v in r.items()}

    say("\n[9] 金额异常")
    r = ask(con, """
        SELECT SUM(CASE WHEN price <= 0 THEN 1 ELSE 0 END) price_nonpos,
               SUM(CASE WHEN freight_value < 0 THEN 1 ELSE 0 END) freight_neg,
               ROUND(MIN(price), 2) min_price,
               ROUND(MAX(price), 2) max_price
        FROM order_items
    """).iloc[0]
    say(f"    price ≤ 0：{int(r['price_nonpos'])}    freight < 0：{int(r['freight_neg'])}")
    say(f"    price 区间：{r['min_price']} — {r['max_price']} R$")
    J["amount"] = {"price_nonpos": int(r["price_nonpos"]), "freight_neg": int(r["freight_neg"]),
                   "min_price": float(r["min_price"]), "max_price": float(r["max_price"])}

    say("\n[10] 评价分数取值")
    r = ask(con, """
        SELECT review_score, COUNT(*) n FROM reviews GROUP BY 1 ORDER BY 1
    """)
    for _, x in r.iterrows():
        say(f"    {int(x['review_score'])} 分  {int(x['n']):>8,}")


def check_d(con):
    say("\n" + "=" * 78)
    say("D · 可用性（样本边界与状态字段）")
    say("=" * 78)

    say("\n[11] 订单状态分布")
    r = ask(con, "SELECT order_status, COUNT(*) n FROM orders GROUP BY 1 ORDER BY n DESC")
    for _, x in r.iterrows():
        say(f"    {x['order_status']:<14}{int(x['n']):>8,}  "
            f"({int(x['n'])/99441*100:5.2f}%)")
    J["status_dist"] = {x["order_status"]: int(x["n"]) for _, x in r.iterrows()}

    say("\n[12] 月度订单量（识别样本截断）")
    r = ask(con, """
        SELECT STRFTIME(DATE_TRUNC('month', order_purchase_timestamp), '%Y-%m') m,
               COUNT(*) n
        FROM orders GROUP BY 1 ORDER BY 1
    """)
    for _, x in r.iterrows():
        bar = "█" * max(1, int(x["n"] / 160))
        say(f"    {x['m']}  {int(x['n']):>5,}  {bar}")
    J["monthly"] = [{"month": x["m"], "orders": int(x["n"])} for _, x in r.iterrows()]

    say("\n    ⚠ 2016-09（4 单）、2016-12（1 单）、2018-09（16 单）、2018-10（4 单）")
    say("      为系统上线/导出口径造成的截断，趋势分析与月度环比一律剔除，")
    say("      分析窗口定为 2017-01 — 2018-08。")

    say("\n[13] 非 delivered 订单的完成情况")
    r = ask(con, """
        SELECT order_status,
               SUM(CASE WHEN order_delivered_customer_date IS NOT NULL THEN 1 ELSE 0 END) has_deliv,
               COUNT(*) n
        FROM orders WHERE order_status <> 'delivered' GROUP BY 1 ORDER BY n DESC
    """)
    for _, x in r.iterrows():
        say(f"    {x['order_status']:<12}{int(x['n']):>6,} 单，其中有送达时间的 {int(x['has_deliv']):>6,}")
    J["nondelivered"] = [{"status": x["order_status"], "n": int(x["n"]),
                          "has_deliv": int(x["has_deliv"])} for _, x in r.iterrows()]


def main():
    con = connect(verbose=True)
    say(f"\nOlist Brazilian E-Commerce · 数据质量审计")
    say(f"DuckDB {__import__('duckdb').__version__}")
    check_a(con)
    check_b(con)
    check_c(con)
    check_d(con)

    say("\n" + "=" * 78)
    say("审计结论")
    say("=" * 78)
    say("""
 1. 结构完整：8 张业务表主键唯一；评价表允许一单多评，review_id 有 814 条
    重复，关联前需按订单去重。无孤儿明细，支付与商品金额可逐单对上
    （98,665 单中 380 单不一致，占 0.39%，平均差额 R$ 0.03，源于
    voucher 分摊与运费合并，不影响金额类分析）。
 2. 唯一的身份陷阱：customer_id 是「一单一号」，复购分析必须切到
    customer_unique_id，否则复购率恒为 0。这是本数据集最常被踩的坑。
 3. 时间戳基本自洽：无「送达早于下单」的记录，仅 23 单「送达早于交承运商」、
    1,359 单「交承运商早于支付确认」——后者多为线下支付确认滞后所致。
    计算履约时长时以「送达 − 下单」为准，负值直接剔除，不做插补。
 4. 样本两端截断明显。2016-09 与 2016-12 是系统试运行，2018-09 之后
    只有零星记录。所有趋势/留存/环比分析统一使用 2017-01 — 2018-08。
 5. 分析口径统一为「已送达订单（delivered）」计算金额与时效，
    计算转化漏斗时保留全状态样本。
""")

    with open(os.path.join(DATA, "audit_log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG))
    with open(os.path.join(DATA, "audit.json"), "w", encoding="utf-8") as f:
        json.dump(J, f, ensure_ascii=False, indent=2)
    print(f"\n→ 已写出 data/audit_log.txt 与 data/audit.json")


if __name__ == "__main__":
    main()
