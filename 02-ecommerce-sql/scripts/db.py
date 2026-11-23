# -*- coding: utf-8 -*-
"""
db.py — DuckDB 连接与视图定义

Olist 的 9 张 CSV 原样入仓，不落数据库文件：DuckDB 直接以视图方式读取 CSV，
省掉建库与导入步骤，脚本可从零跑通。

所有字段在这里显式转型，避免下游 SQL 里出现满屏 CAST。
"""
import os
import duckdb

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

TABLES = {
    "orders": ("olist_orders_dataset.csv", """
        order_id VARCHAR, customer_id VARCHAR, order_status VARCHAR,
        order_purchase_timestamp TIMESTAMP, order_approved_at TIMESTAMP,
        order_delivered_carrier_date TIMESTAMP, order_delivered_customer_date TIMESTAMP,
        order_estimated_delivery_date TIMESTAMP
    """),
    "customers": ("olist_customers_dataset.csv", """
        customer_id VARCHAR, customer_unique_id VARCHAR,
        customer_zip_code_prefix VARCHAR, customer_city VARCHAR, customer_state VARCHAR
    """),
    "order_items": ("olist_order_items_dataset.csv", """
        order_id VARCHAR, order_item_id INTEGER, product_id VARCHAR, seller_id VARCHAR,
        shipping_limit_date TIMESTAMP, price DOUBLE, freight_value DOUBLE
    """),
    "payments": ("olist_order_payments_dataset.csv", """
        order_id VARCHAR, payment_sequential INTEGER, payment_type VARCHAR,
        payment_installments INTEGER, payment_value DOUBLE
    """),
    "reviews": ("olist_order_reviews_dataset.csv", """
        review_id VARCHAR, order_id VARCHAR, review_score INTEGER,
        review_comment_title VARCHAR, review_comment_message VARCHAR,
        review_creation_date TIMESTAMP, review_answer_timestamp TIMESTAMP
    """),
    "products": ("olist_products_dataset.csv", """
        product_id VARCHAR, product_category_name VARCHAR,
        product_name_lenght INTEGER, product_description_lenght INTEGER,
        product_photos_qty INTEGER, product_weight_g DOUBLE,
        product_length_cm DOUBLE, product_height_cm DOUBLE, product_width_cm DOUBLE
    """),
    "sellers": ("olist_sellers_dataset.csv", """
        seller_id VARCHAR, seller_zip_code_prefix VARCHAR,
        seller_city VARCHAR, seller_state VARCHAR
    """),
    "cat_tr": ("product_category_name_translation.csv", """
        product_category_name VARCHAR, product_category_name_english VARCHAR
    """),
}


def _col_struct(ddl):
    """把 'a VARCHAR, b INTEGER' 转成 read_csv 需要的 {'a': 'VARCHAR', 'b': 'INTEGER'}"""
    pairs = []
    for part in ddl.replace("\n", " ").split(","):
        part = part.strip()
        if not part:
            continue
        name, typ = part.split(None, 1)
        pairs.append(f"'{name}': '{typ.strip()}'")
    return "{" + ", ".join(pairs) + "}"


def connect(verbose=False):
    con = duckdb.connect()
    con.execute("SET threads=4")
    for view, (fname, cols) in TABLES.items():
        path = os.path.join(DATA, fname).replace("\\", "/")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"缺少数据文件 {fname}，请先运行 fetch_data.py 下载 Olist 数据集"
            )
        con.execute(f"""
            CREATE OR REPLACE VIEW {view} AS
            SELECT * FROM read_csv('{path}', header=true, columns={_col_struct(cols)},
                                   nullstr=['', 'NA', 'NULL'])
        """)
        if verbose:
            n = con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]
            print(f"  view {view:<12} {n:>9,} rows")
    return con


if __name__ == "__main__":
    connect(verbose=True)
