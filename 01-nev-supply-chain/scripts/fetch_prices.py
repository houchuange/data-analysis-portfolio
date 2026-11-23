# -*- coding: utf-8 -*-
"""
fetch_prices.py — 数据采集
项目：中国新能源车产业链景气传导诊断
数据源：腾讯行情（经 akshare stock_zh_a_hist_tx），前复权日线
说明：东方财富接口存在 IP 级限流，因此主源选用腾讯，间隔 1.2s 以规避风控。
"""
import os
import time
import pandas as pd
import akshare as ak

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)

START, END = "20200101", "20261120"

UNIVERSE = {
    "上游资源": {
        "002460": "赣锋锂业", "002466": "天齐锂业", "603799": "华友钴业",
        "000792": "盐湖股份", "002738": "中矿资源", "300618": "寒锐钴业",
        "002176": "江特电机",
    },
    "中游材料": {
        "300073": "当升科技", "300769": "德方纳米", "002812": "恩捷股份",
        "603659": "璞泰来", "002709": "天赐材料", "600884": "杉杉股份",
        "002497": "雅化集团", "300037": "新宙邦", "002080": "中材科技",
    },
    "中游电池": {
        "300750": "宁德时代", "300014": "亿纬锂能", "002074": "国轩高科",
        "300207": "欣旺达", "688567": "孚能科技",
    },
    "下游整车": {
        "002594": "比亚迪", "601127": "赛力斯", "600104": "上汽集团",
        "601238": "广汽集团", "601633": "长城汽车", "000625": "长安汽车",
        "600418": "江淮汽车", "601777": "力帆科技",
    },
    "传统车对照": {
        "600006": "东风汽车", "000800": "一汽解放",
    },
}


def to_symbol(code: str) -> str:
    """A 股代码转腾讯行情 symbol 前缀"""
    if code.startswith(("60", "68", "11", "51")):
        return "sh" + code
    return "sz" + code


records, failures = [], []

for layer, stocks in UNIVERSE.items():
    for code, name in stocks.items():
        sym = to_symbol(code)
        for attempt in range(3):
            try:
                df = ak.stock_zh_a_hist_tx(symbol=sym, start_date=START,
                                           end_date=END, adjust="qfq")
                if df is None or df.empty:
                    raise ValueError("empty frame")
                df = df.rename(columns={"turnover": "turnover"})
                df["code"] = code
                df["name"] = name
                df["layer"] = layer
                records.append(df)
                print(f"  OK   {layer} {code} {name} rows={len(df)}")
                break
            except Exception as exc:
                if attempt == 2:
                    failures.append((code, name, repr(exc)[:80]))
                    print(f"  FAIL {code} {name}: {repr(exc)[:70]}")
                time.sleep(3.0)
        time.sleep(1.2)

# 基准：沪深300 指数
try:
    idx = ak.stock_zh_a_hist_tx(symbol="sh000300", start_date=START,
                                end_date=END, adjust="qfq")
    idx["code"], idx["name"], idx["layer"] = "000300", "沪深300", "基准"
    records.append(idx)
    print(f"  OK   benchmark 000300 rows={len(idx)}")
except Exception as exc:
    print("  FAIL benchmark:", repr(exc)[:90])

panel = pd.concat(records, ignore_index=True)
panel["date"] = pd.to_datetime(panel["date"])
panel = panel.sort_values(["date", "code"]).reset_index(drop=True)

out = os.path.join(DATA_DIR, "raw_panel.csv")
panel.to_csv(out, index=False, encoding="utf-8-sig")

print("\n--- summary ---")
print(f"rows={len(panel)}  stocks={panel['code'].nunique()}  "
      f"dates={panel['date'].nunique()}  span={panel['date'].min().date()}~{panel['date'].max().date()}")
print(panel.groupby("layer")["code"].nunique().to_string())
print(f"failures={len(failures)}")
for f in failures:
    print("  ", f)
print("saved ->", out)
