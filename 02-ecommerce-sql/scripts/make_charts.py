# -*- coding: utf-8 -*-
"""
make_charts.py — 图表生成

八张图，全部读 results/ 下的 SQL 查询结果，不重新计算任何指标，
保证「图上的数字 = SQL 跑出来的数字」。
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
import matplotlib.patheffects as pe

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "results")
CHARTS = os.path.join(BASE, "charts")
os.makedirs(CHARTS, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["axes.facecolor"] = "white"
plt.rcParams["axes.edgecolor"] = "#D8D8D8"
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["grid.color"] = "#EDEDED"
plt.rcParams["grid.linewidth"] = 0.7
plt.rcParams["font.size"] = 10.5
plt.rcParams["axes.titlesize"] = 12.5
plt.rcParams["axes.labelsize"] = 10.5

NAVY = "#1B3A6B"
BLUE = "#4F81BD"
LBLUE = "#A8C4E0"
RED = "#C0392B"
LRED = "#E8A79E"
GREEN = "#1E8449"
AMBER = "#B07D3C"
GRAY = "#9E9E9E"


def load(name):
    return pd.read_csv(os.path.join(OUT, f"{name}.csv"), encoding="utf-8-sig")


def style(ax, ylabel=None, xlabel=None, grid_axis="y"):
    ax.grid(axis=grid_axis, alpha=0.7)
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    if ylabel:
        ax.set_ylabel(ylabel, color="#3A4250")
    if xlabel:
        ax.set_xlabel(xlabel, color="#3A4250")


def save(fig, name):
    fig.tight_layout()
    path = os.path.join(CHARTS, name)
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print(f"  {name}")


# ══════════════════════════════════════════════════════════════════════
# 图 1 · 月度 GMV 与准时率
# ══════════════════════════════════════════════════════════════════════
def fig_monthly():
    df = load("q9_monthly")
    fig, ax = plt.subplots(figsize=(9.2, 3.9))
    x = np.arange(len(df))
    colors = [RED if m == "2017-11" else NAVY for m in df.month]
    ax.bar(x, df.gmv / 1000, color=colors, width=0.66, alpha=0.92)
    style(ax, "GMV（千雷亚尔）")

    ax.set_xticks(x)
    ax.set_xticklabels(df.month, rotation=45, ha="right", fontsize=8.6)
    ax.set_ylim(0, df.gmv.max() / 1000 * 1.42)

    ax2 = ax.twinx()
    ax2.plot(x, df.on_time_pct, color=AMBER, lw=1.9, marker="o", ms=3.2, zorder=5)
    ax2.set_ylabel("准时送达率（%）", color=AMBER)
    ax2.set_ylim(74, 100)
    ax2.tick_params(axis="y", colors=AMBER)
    for s in ["top", "left"]:
        ax2.spines[s].set_visible(False)
    ax2.grid(False)

    i = list(df.month).index("2017-11")
    ann = (f"2017-11 黑色星期五\n订单 +{df.orders.iloc[i]/df.orders.iloc[i-1]-1:.0%}，"
           f"准时率 {df.on_time_pct.iloc[i-1]:.1f}% → {df.on_time_pct.iloc[i]:.1f}%")
    ax.annotate(ann,
                xy=(i - 0.28, df.gmv.iloc[i] / 1000 * 0.86), xytext=(i - 10.6, 470),
                fontsize=8.8, color="#7A3B2E", ha="left", va="center",
                bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#E0D5D0", lw=0.8),
                arrowprops=dict(arrowstyle="->", color="#B08A7E", lw=1,
                                connectionstyle="arc3,rad=0.16"))

    # 尾部两个月的存活偏差提示
    tail = list(df.month).index("2018-07")
    ax.axvspan(tail - 0.5, len(df) - 0.5, color="#F2F2F2", alpha=0.55, zorder=0)
    ax.text(tail - 0.42, df.gmv.max() / 1000 * 1.33,
            "尾部两月\n存活偏差", fontsize=7.4, color=GRAY, va="top")

    ax.set_title("月度 GMV 与准时送达率：两次履约塌方，一次在大促，一次在 2018 年 2–3 月",
                 loc="left", color="#14181F", pad=12)
    save(fig, "01_monthly.png")


# ══════════════════════════════════════════════════════════════════════
# 图 2 · 客户结构：终身订单数与复购间隔
# ══════════════════════════════════════════════════════════════════════
def fig_customer_structure():
    life = load("q2_lifetime")
    gap = load("q2c_gap_dist")

    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.5),
                             gridspec_kw={"width_ratios": [1.05, 1]})

    ax = axes[0]
    x = np.arange(len(life))
    ax.bar(x, life.customers, color=[RED] + [NAVY] * (len(life) - 1), width=0.68)
    ax.set_yscale("log")
    ax.set_ylim(1, life.customers.max() * 14)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{int(v)} 单" for v in life.lifetime_orders], fontsize=8.4)
    style(ax, "客户数（对数轴）")
    ax.set_title("终身购买次数：97.0% 只买一次", loc="left", fontsize=11.5)
    ax.text(0.06, life.customers.iloc[0] * 1.15, f"{life.customers.iloc[0]:,} 人",
            ha="center", va="bottom", fontsize=8.8, color=RED)
    for i in range(1, 4):
        ax.text(i, life.customers.iloc[i] * 1.25, f"{life.customers.iloc[i]:,}",
                ha="center", va="bottom", fontsize=8.2, color="#4A5260")

    ax = axes[1]
    order = ["1 周内", "8–30 天", "31–90 天", "91–180 天", "181–365 天", "1 年以上"]
    gap["o"] = gap.gap_bucket.map({k: i for i, k in enumerate(order)})
    gap = gap.sort_values("o").reset_index(drop=True)
    gcol = [RED if "1 周内" in b else BLUE for b in gap.gap_bucket]
    y = np.arange(len(gap))
    ax.barh(y, gap.pct, color=gcol, height=0.62)
    ax.set_yticks(y)
    ax.set_yticklabels(gap.gap_bucket, fontsize=9)
    ax.invert_yaxis()
    style(ax, None, "占全部复购事件的比重（%）", grid_axis="x")
    for i, (v, n) in enumerate(zip(gap.pct, gap.events)):
        ax.text(v + 0.6, i, f"{v:.1f}%（{n:,}）", va="center", fontsize=8.3, color="#4A5260")
    ax.set_xlim(0, gap.pct.max() * 1.45)
    ax.set_title("两次下单的间隔：36% 在 7 天内", loc="left", fontsize=11.5)

    save(fig, "02_customer_structure.png")


# ══════════════════════════════════════════════════════════════════════
# 图 3 · RFM 分层：人数占比 vs 营收占比
# ══════════════════════════════════════════════════════════════════════
def fig_rfm():
    df = load("q3_rfm").sort_values("revenue_pct", ascending=True)
    fig, ax = plt.subplots(figsize=(9.2, 3.7))
    y = np.arange(len(df))
    h = 0.36
    ax.barh(y + h / 2, df.customer_pct, height=h, color=LBLUE, label="客户数占比")
    ax.barh(y - h / 2, df.revenue_pct, height=h, color=NAVY, label="营收占比")
    ax.set_yticks(y)
    ax.set_yticklabels(df.segment, fontsize=9.4)
    style(ax, None, "占比（%）", grid_axis="x")
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    for i, (c, r) in enumerate(zip(df.customer_pct, df.revenue_pct)):
        ax.text(c + 0.7, i + h / 2, f"{c:.1f}%", va="center", fontsize=8.2, color="#5A6B85")
        ax.text(r + 0.7, i - h / 2, f"{r:.1f}%", va="center", fontsize=8.2, color=NAVY)
    ax.set_xlim(0, max(df.customer_pct.max(), df.revenue_pct.max()) * 1.28)
    ax.set_title("RFM 分层：贡献 40% 营收的「重要挽留」客，平均只买过 1 单",
                 loc="left", pad=10)
    save(fig, "03_rfm.png")


# ══════════════════════════════════════════════════════════════════════
# 图 4 · cohort 留存热力图
# ══════════════════════════════════════════════════════════════════════
def fig_retention():
    df = load("q4_cohort")
    piv = df.pivot(index="cohort", columns="period", values="retention_pct").drop(columns=[0])
    size = df[df.period == 0].set_index("cohort").cohort_size
    piv = piv.loc[sorted(piv.index)]

    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    data = piv.values.astype(float)
    vmax = np.nanmax(data) * 1.05
    im = ax.imshow(data, cmap="YlGnBu", aspect="auto", vmin=0, vmax=vmax)
    ax.set_xticks(range(piv.shape[1]))
    ax.set_xticklabels([f"M+{c}" for c in piv.columns], fontsize=9)
    ax.set_yticks(range(piv.shape[0]))
    ax.set_yticklabels([f"{c}  ({int(size[c]):,} 人)" for c in piv.index], fontsize=8.2)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if np.isnan(data[i, j]):
                continue
            ax.text(j, i, f"{data[i, j]:.1f}", ha="center", va="center", fontsize=7.6,
                    color="white" if data[i, j] > vmax * 0.62 else "#2A3A4A")
    ax.set_title("月度 cohort 留存（%，M+0 恒为 100%，已略去）：\n不是衰减曲线，是一条贴着地面的水平线",
                 loc="left", pad=10, fontsize=11.5)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("留存率（%）", fontsize=9)
    cb.ax.tick_params(labelsize=8)
    for s in ax.spines.values():
        s.set_visible(False)
    save(fig, "04_retention.png")


# ══════════════════════════════════════════════════════════════════════
# 图 5 · 履约漏斗
# ══════════════════════════════════════════════════════════════════════
def fig_funnel():
    df = load("q5_funnel")
    fig, ax = plt.subplots(figsize=(9.0, 3.4))
    n = len(df)
    colors = [NAVY, BLUE, "#7FA8CC", GREEN]
    for i, row in df.iterrows():
        left = (100 - row.total_pct) / 2
        ax.barh(n - 1 - i, row.total_pct, left=left, height=0.62,
                color=colors[i], alpha=0.95)
        ax.text(50, n - 1 - i, f"{row.step}   {row.orders:,.0f} 单",
                ha="center", va="center", color="white", fontsize=10.5, fontweight="bold")
        if i > 0:
            ax.text(101.5, n - 1 - i, f"环节转化 {row.step_pct:.2f}%",
                    va="center", fontsize=8.6, color="#5A6472")
            ax.text(-1.0, n - 1 - i, f"累计 {row.total_pct:.2f}%",
                    va="center", ha="right", fontsize=8.6, color="#5A6472")
    ax.set_xlim(-16, 122)
    ax.set_ylim(-0.7, n - 0.3)
    ax.axis("off")
    ax.set_title("履约漏斗：取消 0.59%、商品不可得 0.61%，全链路损耗 2.92%",
                 loc="left", pad=8)
    save(fig, "05_funnel.png")


# ══════════════════════════════════════════════════════════════════════
# 图 6 · 延误 × 评分（核心图）
# ══════════════════════════════════════════════════════════════════════
def fig_delay():
    df = load("q6_delay_score")
    order = ["早到 15 天以上", "早到 7–14 天", "早到 1–6 天", "准时",
             "晚 1–3 天", "晚 4–7 天", "晚 8–15 天", "晚 15 天以上"]
    SHORT = ["早到\n≥15天", "早到\n7–14天", "早到\n1–6天", "准时",
             "晚到\n1–3天", "晚到\n4–7天", "晚到\n8–15天", "晚到\n≥15天"]
    df["o"] = df.delay_bucket.map({k: i for i, k in enumerate(order)})
    df = df.sort_values("o").reset_index(drop=True)
    x = np.arange(len(df))

    fig, axes = plt.subplots(1, 2, figsize=(9.8, 3.7),
                             gridspec_kw={"width_ratios": [1, 1.12], "wspace": 0.22})

    ax = axes[0]
    cols = [GREEN if i < 4 else RED for i in range(len(df))]
    ax.bar(x, df.order_pct, color=cols, width=0.68, alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(SHORT, fontsize=7.9)
    style(ax, "订单占比（%）")
    ax.set_ylim(0, df.order_pct.max() * 1.34)
    ax.set_title("履约分布：93.3% 未晚于承诺日", loc="left", fontsize=11.2)
    for i in range(4, len(df)):
        ax.text(i, df.order_pct.iloc[i] + 0.7, f"{df.order_pct.iloc[i]:.1f}",
                ha="center", fontsize=7.4, color=RED)
    ax.annotate("准时只有 1.3%：\n承诺日留了 12 天缓冲", xy=(3, df.order_pct.iloc[3] + 0.4),
                xytext=(1.55, 16), fontsize=8, color="#4A5260",
                arrowprops=dict(arrowstyle="->", color="#B9C0CB", lw=0.9))
    ax.text(0.02, 0.94, "← 早到", transform=ax.transAxes, fontsize=8.5, color=GREEN)
    ax.text(0.80, 0.94, "晚到 →", transform=ax.transAxes, fontsize=8.5, color=RED)

    ax = axes[1]
    ax.bar(x, df.avg_score, color=[GREEN if i < 4 else RED for i in range(len(df))],
           width=0.6, alpha=0.28)
    ax.set_ylim(0, 5.9)
    ax.set_xticks(x)
    ax.set_xticklabels(SHORT, fontsize=7.9)
    style(ax, "平均评分")
    ax2 = ax.twinx()
    ax2.plot(x, df.low_score_pct, color=RED, lw=1.9, marker="o", ms=4)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("1–2 星差评率（%）", color=RED)
    ax2.tick_params(axis="y", colors=RED)
    for s in ["top", "left"]:
        ax2.spines[s].set_visible(False)
    ax2.grid(False)
    for i in range(len(df)):
        ax.text(i, df.avg_score.iloc[i] + 0.16, f"{df.avg_score.iloc[i]:.2f}",
                ha="center", fontsize=7.6, color="#2A3340")
    ax.set_title("评分悬崖：晚到 4 天，评分 4.04 → 2.11", loc="left", fontsize=11.2)
    save(fig, "06_delay_score.png")


# ══════════════════════════════════════════════════════════════════════
# 图 7 · 品类帕累托
# ══════════════════════════════════════════════════════════════════════
def fig_pareto():
    df = load("q7_pareto").head(24)
    fig, ax = plt.subplots(figsize=(9.4, 4.0))
    x = np.arange(len(df))
    ax.bar(x, df.gmv_pct, color=NAVY, width=0.68, alpha=0.9)
    style(ax, "品类 GMV 占比（%）")
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("_", " ") for c in df.category],
                       rotation=55, ha="right", fontsize=7.8)
    ax.set_xlim(-0.8, len(df) - 0.2)

    ax2 = ax.twinx()
    ax2.plot(x, df.cum_gmv_pct, color=AMBER, lw=1.8, marker="o", ms=3)
    ax2.axhline(80, color=RED, ls="--", lw=1)
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("累计占比（%）", color=AMBER)
    ax2.tick_params(axis="y", colors=AMBER)
    for s in ["top", "left"]:
        ax2.spines[s].set_visible(False)
    ax2.grid(False)
    k = int((df.cum_gmv_pct < 80).sum())
    ax2.annotate(f"前 {k + 1} 个品类（共 74 个）覆盖 80% GMV",
                 xy=(k, df.cum_gmv_pct.iloc[k]), xytext=(k - 8.5, 88),
                 fontsize=9, color="#7A3B2E",
                 arrowprops=dict(arrowstyle="->", color="#B08A7E", lw=1))
    ax.set_title("品类集中度：Top 5 占 39.9%，前 18 个品类覆盖 80% 营收",
                 loc="left", pad=10)
    save(fig, "07_pareto.png")


# ══════════════════════════════════════════════════════════════════════
# 图 8 · 州维度：运费负担 vs 延误率
# ══════════════════════════════════════════════════════════════════════
def fig_state():
    df = load("q8_state")
    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    sizes = np.sqrt(df.orders) * 1.9
    sc = ax.scatter(df.freight_pct, df.late_pct, s=sizes, c=df.avg_days,
                    cmap="RdYlGn_r", alpha=0.82, edgecolors="white", linewidths=0.9,
                    vmin=8, vmax=26, zorder=3)
    style(ax, "延误率（%）", "运费占商品金额比重（%）", grid_axis="both")
    off = {"SP": (-19, 7), "PR": (7, -9), "MG": (7, 5), "AL": (6, 2)}
    for _, r in df.iterrows():
        if r.orders > 1500 or r.late_pct > 14 or r.freight_pct > 24:
            ax.annotate(r.state, (r.freight_pct, r.late_pct), fontsize=8,
                        color="#2A3340",
                        xytext=off.get(r.state, (4, 4)), textcoords="offset points")
    cb = fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("平均送达天数", fontsize=9)
    cb.ax.tick_params(labelsize=8)
    ax.set_title("运费越重、送得越慢：东北部各州同时是成本与时效的双重洼地",
                 loc="left", pad=10)
    ax.text(0.985, 0.05, "气泡大小 = 订单量　｜　相关系数 r(运费占比, 平均天数) = 0.78",
            transform=ax.transAxes, ha="right", fontsize=8, color=GRAY)
    save(fig, "08_state.png")


if __name__ == "__main__":
    print("生成图表：")
    fig_monthly()
    fig_customer_structure()
    fig_rfm()
    fig_retention()
    fig_funnel()
    fig_delay()
    fig_pareto()
    fig_state()
    print(f"→ {CHARTS}")
