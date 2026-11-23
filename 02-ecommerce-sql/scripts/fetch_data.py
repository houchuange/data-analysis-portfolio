# -*- coding: utf-8 -*-
"""
fetch_data.py — 数据获取

数据源：Kaggle「Brazilian E-Commerce Public Dataset by Olist」
        https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
        License: CC BY-NC-SA 4.0，可公开再分发（署名 + 非商用 + 相同方式共享）

该数据集由 Olist 官方发布，是巴西最大的百货电商平台在 2016-09 至 2018-10 的
真实交易记录，共 9 张关联表、约 10 万笔订单。

下载走 Kaggle 的 public API 端点，该端点对公开数据集免鉴权（无需 API token），
实测国内直连可用；若失败则回落到 kagglehub 或手动下载提示。
"""
import os
import sys
import urllib.request
import zipfile
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce"
ZIP_NAME = "olist_raw.zip"

EXPECTED = [
    "olist_orders_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "product_category_name_translation.csv",
]


def already_ok():
    return all(os.path.exists(os.path.join(DATA, f)) for f in EXPECTED)


def download():
    os.makedirs(DATA, exist_ok=True)
    dest = os.path.join(DATA, ZIP_NAME)
    print(f"下载中 … {URL}")
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            if total:
                sys.stdout.write(f"\r  {got/1e6:6.1f} / {total/1e6:.1f} MB")
                sys.stdout.flush()
    print(f"\n  完成 {got/1e6:.1f} MB")

    with zipfile.ZipFile(dest) as z:
        z.extractall(DATA)
    os.remove(dest)

    # Kaggle 压缩包可能带一层子目录，统一摊平到 data/
    for root, _, files in os.walk(DATA):
        for fn in files:
            src = os.path.join(root, fn)
            dst = os.path.join(DATA, fn)
            if os.path.abspath(src) != os.path.abspath(dst) and not os.path.exists(dst):
                shutil.move(src, dst)


def main():
    if already_ok():
        print("数据已存在，跳过下载。")
    else:
        try:
            download()
        except Exception as e:
            print(f"下载失败：{e}")
            print("备选方案：pip install kagglehub && python -c \"import kagglehub;"
                  "print(kagglehub.dataset_download('olistbr/brazilian-ecommerce'))\"")
            raise
    missing = [f for f in EXPECTED if not os.path.exists(os.path.join(DATA, f))]
    if missing:
        raise RuntimeError(f"解压后缺少文件：{missing}")
    print("数据就绪：")
    for f in EXPECTED:
        p = os.path.join(DATA, f)
        print(f"  {f:<45} {os.path.getsize(p)/1e6:7.1f} MB")


if __name__ == "__main__":
    main()
