"""把 results/ 下的聚合结果拼成看板用的「月 × 州 × 品类」立方体。

只读 results/（不碰 data/ 里的原始 CSV），输出 docs/data.json 供 docs/index.html 内嵌。

思路
----
results/ 里的每条查询都是一维聚合，彼此不能直接相乘。看板要的是「任意筛选组合」，
所以这里做一次**带边际约束的插值**：

1. 用 q1 的 2,000 单随机样本给出跨维度的初始形状（哪个州偏哪个品类、哪个月偏什么）；
2. 用 q7/q8/q9 的全量边际做 IPF 迭代校准，使任何一个「单维切片」都和已发表的
   聚合结果一致——只看月份、只看州、只看品类，数字都是精确值，
   只有「跨维度组合」才是模型插值的结果；
3. 晚到量按 q6 的 8 个延误档形状摊开，保证 8 档之和 = 订单量。

用法：python scripts/build_dashboard_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
OUT = ROOT / "docs" / "data.json"

BUCKETS = ["早 15+", "早 7–14", "早 1–6", "准时", "晚 1–3", "晚 4–7", "晚 8–15", "晚 15+"]
BUCKET_X = [-22, -10.5, -3.5, 0, 2, 5.5, 11.5, 22]          # 承诺偏差代表值（天）
BUCKET_SCORE = [4.32, 4.31, 4.18, 4.04, 3.29, 2.11, 1.68, 1.73]  # q6 的全局均值
BUCKET_SHARE = [0.3613, 0.4286, 0.1299, 0.0134, 0.0194, 0.0183, 0.0168, 0.0123]

STATE_CN = {
    "SP": "圣保罗", "RJ": "里约热内卢", "MG": "米纳斯吉拉斯", "RS": "南里奥格兰德",
    "PR": "巴拉那", "SC": "圣卡塔琳娜", "BA": "巴伊亚", "DF": "联邦区",
    "ES": "圣埃斯皮里图", "GO": "戈亚斯", "PE": "伯南布哥", "CE": "塞阿拉",
    "PA": "帕拉", "MA": "马拉尼昂", "PB": "帕拉伊巴", "PI": "皮奥伊",
    "RN": "北里奥格兰德", "AL": "阿拉戈斯", "SE": "塞尔希培", "MT": "马托格罗索",
    "MS": "南马托格罗索",
}
CAT_CN = {
    "health_beauty": "健康美容", "watches_gifts": "手表礼品", "bed_bath_table": "床品家纺",
    "sports_leisure": "运动休闲", "computers_accessories": "电脑配件",
    "furniture_decor": "家具装饰", "housewares": "家居用品", "cool_stuff": "潮玩礼品",
    "auto": "汽车用品", "garden_tools": "园艺工具", "toys": "玩具", "baby": "母婴",
    "perfumery": "香水", "telephony": "手机通讯", "office_furniture": "办公家具",
    "stationery": "文具", "computers": "电脑", "pet_shop": "宠物用品",
}
N_CAT = 18  # 前 18 个品类覆盖 81% 营收，其余归入「长尾品类」


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(RES / name, encoding="utf-8-sig")


def ipf(seed: np.ndarray, margins: list[tuple[int, np.ndarray]], iters: int = 300) -> np.ndarray:
    """iterative proportional fitting：反复按各维边际缩放，直到同时逼近所有约束。"""
    t = np.asarray(seed, float).copy()
    t[t <= 0] = 1e-9
    for _ in range(iters):
        for axis, target in margins:
            shape = [1] * t.ndim
            shape[axis] = len(target)
            others = tuple(i for i in range(t.ndim) if i != axis)
            cur = np.maximum(t.sum(axis=others, keepdims=True), 1e-12)
            t *= np.asarray(target, float).reshape(shape) / cur
    return t


def largest_remainder(values: np.ndarray, total: int) -> list[int]:
    """把一组浮点数凑成整数，保证和恰好等于 total，且按比例分配。"""
    total = max(int(total), 0)
    s = float(values.sum())
    if s <= 0:
        out = [0] * len(values)
        out[3] = total
        return out
    scaled = values / s * total
    base = np.floor(scaled).astype(int)
    rest = total - int(base.sum())
    if rest > 0:
        for i in np.argsort(-(scaled - base))[:rest]:
            base[i] += 1
    return base.tolist()


def main() -> None:
    monthly = read("q9_monthly.csv").sort_values("month").reset_index(drop=True)
    state = read("q8_state.csv").sort_values("late_pct", ascending=False).reset_index(drop=True)
    pareto = read("q7_pareto.csv").sort_values("rank").reset_index(drop=True)
    sample = read("q1_order_wide_sample.csv")

    months = list(monthly["month"])
    states = list(state["state"]) + ["OT"]
    cats = list(pareto["category"].head(N_CAT)) + ["other"]
    M, S, C = len(months), len(states), len(cats)
    midx = {v: i for i, v in enumerate(months)}
    sidx = {v: i for i, v in enumerate(states)}
    cidx = {v: i for i, v in enumerate(cats)}

    total_orders = float(monthly["orders"].sum())
    total_gmv = float(monthly["gmv"].sum())

    # ---------- 1. 订单量：三维 IPF ----------
    n_m = monthly["orders"].to_numpy(float)
    n_s = np.append(state["orders"].to_numpy(float), total_orders - state["orders"].sum())
    cat_orders = pareto["orders"].to_numpy(float)[:N_CAT] * total_orders / pareto["orders"].sum()
    n_c = np.append(cat_orders, max(total_orders - cat_orders.sum(), 1.0))

    seed = np.full((M, S, C), 0.35)
    d = sample[sample["order_status"] == "delivered"]
    for (pm, st, ct), cnt in d.groupby(["purchase_month", "customer_state", "main_category"]).size().items():
        m_i = midx.get(str(pm)[:7])
        if m_i is None:
            continue
        seed[m_i, sidx.get(st, sidx["OT"]), cidx.get(ct, cidx["other"])] += cnt
    n = ipf(seed, [(0, n_m), (1, n_s), (2, n_c)])
    n *= total_orders / n.sum()

    # ---------- 2. 逐格比率场：样本给形状，全量边际给水平 ----------
    sn = np.zeros((M, S, C))
    sg = np.zeros((M, S, C))
    sf = np.zeros((M, S, C))
    ss = np.zeros((M, S, C))
    sd = np.zeros((M, S, C))
    for (pm, st, ct), g in d.groupby(["purchase_month", "customer_state", "main_category"]):
        m_i = midx.get(str(pm)[:7])
        if m_i is None:
            continue
        m_, s_, c_ = m_i, sidx.get(st, sidx["OT"]), cidx.get(ct, cidx["other"])
        sn[m_, s_, c_] = len(g)
        sg[m_, s_, c_] = g["gmv"].sum()
        sf[m_, s_, c_] = g["freight"].sum()
        ss[m_, s_, c_] = g["review_score"].mean() * len(g)
        sd[m_, s_, c_] = g["delay_days"].fillna(0).sum()

    def rate(num: np.ndarray, den: np.ndarray, glob: float) -> np.ndarray:
        """逐格 num/den，样本没有覆盖到的格子退回全局值。"""
        with np.errstate(divide="ignore", invalid="ignore"):
            r = np.where(den > 0, num / np.maximum(den, 1e-9), glob)
        return np.where(np.isfinite(r) & (r > 0), r, glob)

    # 2.1 GMV：月份 / 州 / 品类 三重边际
    gmv_m = monthly["gmv"].to_numpy(float)
    gmv_s = (state["orders"] * state["avg_order_value"]).to_numpy(float)
    gmv_s = np.append(gmv_s, total_gmv - gmv_s.sum())
    gmv_c = pareto["gmv"].to_numpy(float)[:N_CAT]
    gmv_c = np.append(gmv_c, max(total_gmv - gmv_c.sum(), 1.0))
    gmv = ipf(rate(sg, sn, total_gmv / total_orders) * n,
              [(0, gmv_m), (1, gmv_s), (2, gmv_c)])

    # 2.2 运费：按品类运费占比校准（q7 的 freight_pct = 运费/GMV）
    fr_glob = float((pareto["gmv"] * pareto["freight_pct"] / 100).sum()) / total_gmv
    fr = gmv * rate(sf, sg, fr_glob)
    fr_c = np.append(pareto["freight_pct"].to_numpy(float)[:N_CAT] / 100, fr_glob)
    for _ in range(200):
        col = fr.sum(axis=(0, 1))
        target = fr_c * gmv.sum(axis=(0, 1))
        fr *= np.where(col > 0, target / np.maximum(col, 1e-9), 1.0).reshape(1, 1, C)

    # 2.3 评分：月份 / 州 双边际
    sc_glob = float((monthly["avg_score"] * monthly["orders"]).sum() / total_orders)
    sc_s = np.append(state["avg_score"].to_numpy(float), sc_glob)
    sc_m = monthly["avg_score"].to_numpy(float)
    sc = ipf(rate(ss, sn, sc_glob) * n, [(0, sc_m * n_m), (1, sc_s * n_s)]) / n
    # 评分必须落在 1–5：先线性压到区间内，再用加性偏移把月份、州两个边际校准回来
    sc = 1.04 + (np.clip(sc, 0.8, 5.7) - 0.8) * (4.96 - 1.04) / (5.7 - 0.8)

    def axis_mean(arr: np.ndarray, axis: int) -> np.ndarray:
        others = tuple(i for i in range(arr.ndim) if i != axis)
        return (arr * n).sum(axis=others) / np.maximum(n.sum(axis=others), 1e-9)

    for _ in range(200):
        sc += (sc_m - axis_mean(sc, 0)).reshape(M, 1, 1)
        sc += (sc_s - axis_mean(sc, 1)).reshape(1, S, 1)

    # 2.4 平均送达天数：只按州校准
    dn_glob = float((state["avg_days"] * state["orders"]).sum() / state["orders"].sum())
    dn_s = np.append(state["avg_days"].to_numpy(float), dn_glob)
    dn = ipf(rate(sd, sn, dn_glob) * n, [(1, dn_s * n_s)]) / n

    # 2.5 晚到量：月份（准时率）/ 州（晚到率）双边际
    late_m = n_m * (1 - monthly["on_time_pct"].to_numpy(float) / 100)
    late_s = np.append(state["orders"].to_numpy(float) * state["late_pct"].to_numpy(float) / 100, 0.0)
    late_s[-1] = max(late_m.sum() - late_s[:-1].sum(), 1.0)
    late = np.clip(ipf(n * 0.0667, [(0, late_m), (1, late_s)]), 0, n)

    # ---------- 3. 序列化（保留两位小数：格子很多且很小，取整会把长尾品类抹平） ----------
    cells = []
    for m_i in range(M):
        for s_i in range(S):
            for c_i in range(C):
                q = float(n[m_i, s_i, c_i])
                if q < 0.02:
                    continue
                cells.append([
                    m_i, s_i, c_i,
                    round(q, 2),
                    round(float(gmv[m_i, s_i, c_i])),
                    round(float(fr[m_i, s_i, c_i])),
                    round(float(sc[m_i, s_i, c_i]), 2),
                    round(float(dn[m_i, s_i, c_i]), 1),
                    round(float(min(late[m_i, s_i, c_i], q)), 2),
                ])

    payload = {
        "meta": {
            "months": months,
            "states": [{"code": s, "name": STATE_CN.get(s, "其余 6 州")} for s in states],
            "cats": [{"key": c, "name": CAT_CN.get(c, "长尾品类")} for c in cats],
            "buckets": BUCKETS,
            "bucketX": BUCKET_X,
            "bucketScore": BUCKET_SCORE,
            "bucketShare": BUCKET_SHARE,
            "globals": {
                "orders": int(total_orders),
                "gmv": int(total_gmv),
                "customers": 93096,
                "everRepeat": 2789,
                "realReturn": 1816,
                "repeatPct": 2.996,
                "realReturnPct": 1.95,
                "avgScore": round(float((monthly["avg_score"] * monthly["orders"]).sum() / total_orders), 2),
                "avgOrdersPerCustomer": round(96203 / 93096, 4),
                "extraOrdersPerRepeater": round((96203 - 90307) / 2789, 4),
            },
        },
        "cells": cells,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ---------- 5. 自检：单维切片必须和已发表的聚合结果对齐 ----------
    cm = np.array([c[0] for c in cells])
    cs = np.array([c[1] for c in cells])
    cc = np.array([c[2] for c in cells])
    q = np.array([c[3] for c in cells], float)
    g = np.array([c[4] for c in cells], float)
    sco = np.array([c[6] for c in cells], float)
    dys = np.array([c[7] for c in cells], float)
    lt = np.array([c[8] for c in cells], float)

    print(f"cells={len(cells)}  orders={q.sum():,.0f}  gmv={g.sum():,.0f}  "
          f"late={lt.sum():,.0f} ({lt.sum() / q.sum() * 100:.2f}%)  "
          f"score={np.average(sco, weights=q):.3f}  days={np.average(dys, weights=q):.2f}  "
          f"json={OUT.stat().st_size / 1024:.0f} KB")

    def wavg(v, w):
        return np.average(v, weights=w) if w.sum() > 0 else float("nan")

    def err(a, b):
        return float(np.max(np.abs(np.asarray(a, float) - np.asarray(b, float))))

    mo_q = [q[cm == i].sum() for i in range(M)]
    mo_g = [g[cm == i].sum() for i in range(M)]
    mo_s = [wavg(sco[cm == i], q[cm == i]) for i in range(M)]
    mo_l = [lt[cm == i].sum() / max(q[cm == i].sum(), 1e-9) * 100 for i in range(M)]
    print(f"月度 订单±{err(mo_q, n_m):.0f}  GMV±{err(mo_g, gmv_m) / 1e3:.1f}k  "
          f"评分±{err(mo_s, monthly['avg_score']):.3f}  准时率±{err(100 - np.array(mo_l), monthly['on_time_pct']):.2f}pt")

    st_l = [lt[cs == i].sum() / max(q[cs == i].sum(), 1e-9) * 100 for i in range(S)]
    st_s = [wavg(sco[cs == i], q[cs == i]) for i in range(S)]
    st_d = [wavg(dys[cs == i], q[cs == i]) for i in range(S)]
    print(f"州   晚到率±{err(st_l[:-1], state['late_pct']):.2f}pt  评分±{err(st_s[:-1], state['avg_score']):.3f}  "
          f"送达±{err(st_d[:-1], state['avg_days']):.2f}天")

    cat_share = np.array([g[cc == i].sum() for i in range(C)]) / g.sum() * 100
    print(f"品类 占比±{err(cat_share[:N_CAT], pareto['gmv_pct'][:N_CAT]):.2f}pt  "
          f"前{N_CAT}累计 {cat_share[:N_CAT].sum():.1f}% (源 {pareto['cum_gmv_pct'][N_CAT - 1]:.1f}%)")


if __name__ == "__main__":
    main()
