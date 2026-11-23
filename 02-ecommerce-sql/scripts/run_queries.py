# -*- coding: utf-8 -*-
"""
run_queries.py — 把 sql/ 下的查询全部跑一遍

sql/ 里每个文件是「一个主题 + 若干条查询」，用 -- @query: <name> 分隔。
本脚本只负责切段、执行、落盘，不写任何分析逻辑——分析全在 SQL 里。

用法：
    python scripts/run_queries.py              # 跑全部
    python scripts/run_queries.py 03           # 只跑文件名含 03 的
"""
import os
import sys
import re
import glob
import pandas as pd
from db import connect, BASE

SQL_DIR = os.path.join(BASE, "sql")
OUT_DIR = os.path.join(BASE, "results")
os.makedirs(OUT_DIR, exist_ok=True)

SPLIT = re.compile(r"^--\s*@query:\s*(\w+)\s*$", re.M)


def split_queries(text):
    """按 -- @query: name 切段，返回 [(name, sql), ...]"""
    marks = list(SPLIT.finditer(text))
    out = []
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[start:end]
        # 去掉段末尾的分隔注释和空行
        body = "\n".join(l for l in body.split("\n") if not l.startswith("-- ====")).strip()
        out.append((m.group(1), body.rstrip(";")))
    return out


def main():
    keyword = sys.argv[1] if len(sys.argv) > 1 else ""
    files = sorted(glob.glob(os.path.join(SQL_DIR, "*.sql")))
    files = [f for f in files if keyword in os.path.basename(f)]
    if not files:
        print("没有匹配的 sql 文件")
        return

    con = connect()
    total = 0
    for f in files:
        text = open(f, encoding="utf-8").read()
        qs = split_queries(text)
        print(f"\n{os.path.basename(f)}  ({len(qs)} queries)")
        for name, sql in qs:
            df = con.execute(sql).fetchdf()
            path = os.path.join(OUT_DIR, f"{name}.csv")
            # 宽表只留前 2000 行做结构示意，全量 99,092 行没必要入仓
            df.head(2000).to_csv(path, index=False, encoding="utf-8-sig")
            print(f"  {name:<22} {len(df):>7,} 行  {len(df.columns):>2} 列")
            total += 1
    print(f"\n完成，共 {total} 条查询，结果在 results/")


if __name__ == "__main__":
    main()
