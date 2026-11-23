# -*- coding: utf-8 -*-
"""
charts.py — 图表生成
项目：Cookie Cats 新手引导门槛 A/B 实验评估
配色：A 组（对照，gate_30）深海军蓝，B 组（实验，gate_40）赭黄；显著负向效应用红。
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch
from scipy import stats

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "charts")
os.makedirs(OUT, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.facecolor"] = "white"
plt.rcParams["axes.facecolor"] = "white"
plt.rcParams["axes.edgecolor"] = "#D8D8D8"
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["grid.color"] = "#EDEDED"
plt.rcParams["grid.linewidth"] = 0.7
plt.rcParams["font.size"] = 11
plt.rcParams["axes.titlesize"] = 13
plt.rcParams["axes.labelsize"] = 11

NAVY = "#1B3A6B"      # A 组 / 主色
AMBER = "#B07D3C"     # B 组
RED = "#C0392B"       # 显著变差
GREY = "#8A93A2"
INK = "#14181F"
INK2 = "#4A5260"

M = json.load(open(os.path.join(DATA, "metrics.json"), encoding="utf-8"))
K = 1.959963984540054


def style(ax, ylabel=None, xlabel=None, title=None, grid_axis="y"):
    ax.grid(axis=grid_axis, alpha=0.75)
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    if ylabel:
        ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)
    if title:
        ax.set_title(title, loc="left", pad=12, fontweight="bold", fontsize=12.5)


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"[chart] {name}")


# ------------------------------------------------ 图 1 三指标相对效应森林图
def fig_effect():
    m7, m1, mr = M["metrics"]["retention_7"], M["metrics"]["retention_1"], M["metrics"]["rounds"]
    rows = [
        ("7 日留存（北极星）", m7["rel"] * 100, (m7["ci_rel"][0] - 1) * 100, (m7["ci_rel"][1] - 1) * 100,
         m7["p"], m7["diff_pp"]),
        ("1 日留存（护栏）", m1["rel"] * 100, (m1["ci_rel"][0] - 1) * 100, (m1["ci_rel"][1] - 1) * 100,
         m1["p"], m1["diff_pp"]),
        ("首日游戏轮次（均值）", mr["mean_rel"] * 100, mr["ci_boot_rel"][0] * 100, mr["ci_boot_rel"][1] * 100,
         mr["p_welch"], None),
    ]
    fig, ax = plt.subplots(figsize=(10, 3.45))
    ys = np.arange(len(rows))[::-1]
    ax.axvline(0, color="#5A5A5A", lw=1.1, zorder=1)
    for y, (label, est, lo, hi, p, pp) in zip(ys, rows):
        sig = lo > 0 or hi < 0
        col = RED if (sig and est < 0) else GREY
        ax.plot([lo, hi], [y, y], color=col, lw=2.2, solid_capstyle="round", zorder=2)
        ax.plot([lo, lo], [y - .09, y + .09], color=col, lw=1.4)
        ax.plot([hi, hi], [y - .09, y + .09], color=col, lw=1.4)
        ax.scatter([est], [y], s=95, color=col, edgecolor="white", linewidth=1.6, zorder=3)
        note = f"{est:+.2f}%"
        if pp is not None:
            note += f"（{pp:+.3f} pp）"
        note += f"   p={p:.4f}" if p >= 0.001 else f"   p<0.001"
        ax.annotate(note, xy=(hi, y), xytext=(10, 0), textcoords="offset points",
                    va="center", fontsize=10, color=INK2)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], fontsize=11)
    ax.axvspan(-0.0, 0.02, color="#F2F4F7", zorder=0)
    ax.set_xlim(-9.5, 4.2)
    ax.set_xlabel("B 组（gate_40）相对 A 组（gate_30）的变化（%）")
    style(ax, grid_axis="x", title="三个指标的相对效应与 95% 置信区间")
    save(fig, "01_effect_forest.png")


# ------------------------------------------------ 图 2 轮次分布与均值的脆弱性
def fig_rounds():
    df = pd.read_csv(os.path.join(DATA, "cookie_cats.csv"))
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.1), gridspec_kw={"width_ratios": [1.08, 1]})

    ax = axes[0]
    for v, col, lab in [("gate_30", NAVY, "A 组 gate_30"), ("gate_40", AMBER, "B 组 gate_40")]:
        s = np.sort(df.loc[df.version == v, "sum_gamerounds"].to_numpy())[::-1]
        x = np.maximum(s, 1)
        y = np.arange(1, len(s) + 1) / len(s)
        ax.plot(x, y, color=col, lw=1.8, label=lab)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(1, 8e4)
    ax.set_ylim(1e-5, 1.2)
    ax.set_xlabel("首日游戏轮次（对数轴）")
    ax.set_ylabel("P(轮次 > x)")
    ax.legend(frameon=False, fontsize=9.5, loc="lower left")
    ax.annotate("99 分位 493", xy=(493, 0.01), xytext=(-52, -52), textcoords="offset points",
                fontsize=9, color=GREY, arrowprops=dict(arrowstyle="-", color=GREY, lw=.8))
    ax.annotate("单个用户 49,854", xy=(49854, 1 / 90189), xytext=(-72, 26), textcoords="offset points",
                fontsize=9, color=RED, arrowprops=dict(arrowstyle="-", color=RED, lw=.8))
    style(ax, title="两组首日轮次分布几乎重合", grid_axis="both")

    ax = axes[1]
    srt = {v: np.sort(df.loc[df.version == v, "sum_gamerounds"].to_numpy())[::-1]
           for v in ["gate_30", "gate_40"]}
    ks = np.arange(0, 51)
    diffs = []
    for k in ks:
        a, b = srt["gate_30"], srt["gate_40"]
        ma = a[k:].mean() if k else a.mean()
        mb = b[k:].mean() if k else b.mean()
        diffs.append(mb - ma)
    ax.plot(ks, diffs, color=NAVY, lw=2)
    ax.axhline(0, color="#5A5A5A", lw=1)
    ax.scatter([0], [diffs[0]], s=60, color=RED, zorder=4, edgecolor="white", linewidth=1.3)
    ax.annotate(f"原始差 {diffs[0]:+.2f} 轮", xy=(0, diffs[0]), xytext=(20, -8),
                textcoords="offset points", fontsize=9.5, color=RED,
                arrowprops=dict(arrowstyle="-", color=RED, lw=.9))
    ax.annotate(f"同时剔除各组最大 1 个观测：{diffs[1]:+.2f} 轮", xy=(1, diffs[1]), xytext=(30, 26),
                textcoords="offset points", fontsize=9.5, color=INK2,
                arrowprops=dict(arrowstyle="-", color=GREY, lw=.9))
    ax.set_xlabel("从每组中剔除的前 k 个最大值")
    ax.set_ylabel("B 组均值 − A 组均值（轮）")
    ax.set_xlim(-1, 50)
    ax.set_ylim(-1.55, 0.42)
    style(ax, title="均值差被一个用户绑架")
    fig.tight_layout()
    save(fig, "02_rounds_tail.png")


# ------------------------------------------------ 图 3 功效曲线
def fig_power():
    n_obs = M["meta"]["n_a"]
    obs = abs(M["metrics"]["retention_7"]["diff_pp"])
    xs = np.geomspace(3000, 260000, 220)
    ys = []
    for n in xs:
        xs_ = float(n)
        # 近似：z 检验的双侧 MDE（与 analysis.py 的数值解一致到 0.01pp）
        se = np.sqrt(2 * 0.190201 * (1 - 0.190201) / xs_)
        ys.append((1.959963984540054 + 0.8416212335729143) * se * 100)
    fig, ax = plt.subplots(figsize=(9.4, 4.2))
    ax.plot(xs / 1000, ys, color=NAVY, lw=2.2)
    ax.axhline(obs, color=RED, lw=1.2, ls=(0, (5, 3)))
    ax.annotate(f"本次实测差异 {obs:.2f} pp", xy=(250, obs), xytext=(0, 7),
                textcoords="offset points", fontsize=9.5, color=RED, ha="right")
    ax.scatter([n_obs / 1000], [0.730], s=90, color=AMBER, zorder=4, edgecolor="white", linewidth=1.5)
    ax.annotate(f"本次实验\n每组 {n_obs:,} 人\n可检出 0.73 pp",
                xy=(n_obs / 1000, 0.730), xytext=(16, 26), textcoords="offset points",
                fontsize=9.5, color=INK2,
                arrowprops=dict(arrowstyle="-", color=GREY, lw=.9))
    ax.set_xscale("log")
    ax.set_xlim(3, 260)
    ax.set_ylim(0, 2.4)
    ax.set_xticks([5, 10, 20, 45, 100, 200])
    ax.set_xticklabels(["5k", "10k", "20k", "45k", "100k", "200k"])
    ax.set_xlabel("每组样本量（对数轴）")
    ax.set_ylabel("可检出的最小绝对差异（pp）")
    style(ax, title="样本量决定能看到多小的差异（7 日留存，基线 19.0%）")
    save(fig, "03_power_curve.png")


# ------------------------------------------------ 图 4 分层效应
def fig_segments():
    rows = M["segments"]["rows"]
    p_inter = M["segments"]["p_interaction"]
    fig, ax = plt.subplots(figsize=(9.6, 4.3))
    ys = np.arange(len(rows))[::-1]
    ax.axvline(0, color="#5A5A5A", lw=1.1)
    for y, r in zip(ys, rows):
        lo, hi = r["ci_diff_pp"]
        col = RED if (lo > 0 or hi < 0) else GREY
        ax.plot([lo, hi], [y, y], color=col, lw=2.2, solid_capstyle="round")
        for e in (lo, hi):
            ax.plot([e, e], [y - .08, y + .08], color=col, lw=1.4)
        ax.scatter([r["diff_pp"]], [y], s=80, color=col, edgecolor="white", linewidth=1.5, zorder=3)
        ax.annotate(f"{r['diff_pp']:+.2f} pp   n={r['n_a']+r['n_b']:,}",
                    xy=(max(hi, 0), y), xytext=(10, 0), textcoords="offset points",
                    va="center", fontsize=9.5, color=INK2)
    ax.set_yticks(ys)
    ax.set_yticklabels([f"{r['tier']}\n{r['rate_a']*100:.1f}% → {r['rate_b']*100:.1f}%" for r in rows],
                       fontsize=9.5)
    ax.set_xlim(-3.6, 2.2)
    ax.set_xlabel("B 组 − A 组的 7 日留存差（pp）")
    style(ax, grid_axis="x", title=f"分段后差异方向不一致，但交互项不显著（p={p_inter:.2f}）")
    save(fig, "04_segments.png")


# ------------------------------------------------ 图 5 peeking
def fig_peeking():
    curve = M["peeking"]["fpr_curve"]
    looks = np.arange(1, len(curve) + 1)
    fig, ax = plt.subplots(figsize=(8.6, 3.9))
    ax.plot(looks, np.array(curve) * 100, color=RED, lw=2.4, marker="o", ms=5,
            markerfacecolor="white", markeredgewidth=1.6)
    ax.axhline(5, color=NAVY, lw=1.2, ls=(0, (5, 3)))
    ax.annotate("名义显著性水平 5%", xy=(9.9, 5.35), fontsize=9.5, color=NAVY, ha="right")
    ax.annotate(f"看满 10 次：{curve[-1]*100:.1f}%", xy=(10, curve[-1] * 100), xytext=(-8, 12),
                textcoords="offset points", fontsize=10, color=RED, ha="right",
                fontweight="bold")
    ax.set_ylim(0, 25)
    ax.set_xlim(0.6, 10.4)
    ax.set_xticks(range(1, 11))
    ax.set_xlabel("累计查看结果的次数")
    ax.set_ylabel("假阳性率（%）")
    style(ax, title="每多看一次结果，误判风险就往上走一层")
    save(fig, "05_peeking.png")


# ------------------------------------------------ 图 6 贝叶斯后验
def fig_bayes():
    m7 = M["metrics"]["retention_7"]
    ka, na = m7["k_a"], M["meta"]["n_a"]
    kb, nb = m7["k_b"], M["meta"]["n_b"]
    xs = np.linspace(0.175, 0.198, 800)
    pdf_a = stats.beta.pdf(xs, 1 + ka, 1 + na - ka)
    pdf_b = stats.beta.pdf(xs, 1 + kb, 1 + nb - kb)
    fig, ax = plt.subplots(figsize=(9.2, 4.0))
    ax.fill_between(xs, 0, np.minimum(pdf_a, pdf_b), color="#D9DEE7", zorder=1)
    ax.plot(xs, pdf_a, color=NAVY, lw=2.2, label="A 组 gate_30 的后验")
    ax.plot(xs, pdf_b, color=AMBER, lw=2.2, label="B 组 gate_40 的后验")
    ax.axvline(m7["rate_a"], color=NAVY, lw=1, ls=":")
    ax.axvline(m7["rate_b"], color=AMBER, lw=1, ls=":")
    prob = M["bayes"]["prob_b_worse"]
    top = max(pdf_a.max(), pdf_b.max())
    ax.set_ylim(0, top * 1.55)
    ax.text(0.5, 0.95, f"P(B 低于 A) = {prob*100:.2f}%", transform=ax.transAxes,
            fontsize=12, color=INK, fontweight="bold", ha="center", va="top")
    ax.text(0.5, 0.855, "两组后验几乎不重叠：B 组几乎不可能优于 A 组", transform=ax.transAxes,
            fontsize=9.5, color=INK2, ha="center", va="top")
    ax.set_xlabel("7 日留存率")
    ax.set_ylabel("后验密度")
    ax.set_yticks([])
    ax.legend(frameon=False, fontsize=9.5, loc="upper left")
    style(ax, title="换个学派看同一组数据：结论一致", grid_axis="x")
    save(fig, "06_bayes.png")


if __name__ == "__main__":
    fig_effect()
    fig_rounds()
    fig_power()
    fig_segments()
    fig_peeking()
    fig_bayes()
