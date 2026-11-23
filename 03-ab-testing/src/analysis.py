# -*- coding: utf-8 -*-
"""
analysis.py — A/B 实验的完整统计评估
项目：Cookie Cats 新手引导门槛 A/B 实验评估

流程：数据审计 → 分流均衡(SRM) → 功效与 MDE 复盘 → 三指标假设检验
      → 多重比较校正 → 分段异质性 → 贝叶斯复核 → 连续监测(peeking)风险
输出：data/metrics.json（全部数字的唯一来源）、data/analysis_log.txt（可读日志）
"""
import json
import math
import os
import sys
from datetime import date

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
CSV = os.path.join(DATA_DIR, "cookie_cats.csv")

ALPHA = 0.05
POWER = 0.80
Z_95 = stats.norm.ppf(1 - ALPHA / 2)
A, B = "gate_30", "gate_40"
SEED = 20261123

LOG: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    LOG.append(msg)


# ---------------------------------------------------------------- 统计工具


def wilson_ci(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score 区间：低发生率时显著优于 Wald 区间，且不会越界。"""
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - half, center + half


def newcombe_diff_ci(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    """Newcombe (1998) 混合评分法，构造两比例之差的置信区间（B − A）。"""
    l1, u1 = wilson_ci(k1, n1)
    l2, u2 = wilson_ci(k2, n2)
    p1, p2 = k1 / n1, k2 / n2
    d = p2 - p1
    lower = d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    upper = d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)
    return lower, upper


def two_prop_z(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    """两比例 z 检验（合并方差，等价于无连续性校正的卡方）。"""
    p1, p2 = k1 / n1, k2 / n2
    p_pool = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    z = (p2 - p1) / se
    p_val = 2 * (1 - stats.norm.cdf(abs(z)))
    return z, p_val


def relative_ci(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    """相对提升的 delta 法区间（对数尺度）。"""
    p1, p2 = k1 / n1, k2 / n2
    se = math.sqrt((1 - p1) / (n1 * p1) + (1 - p2) / (n2 * p2))
    center = math.log(p2 / p1)
    return math.exp(center - Z_95 * se), math.exp(center + Z_95 * se)


def cohen_h(p1: float, p2: float) -> float:
    return 2 * math.asin(math.sqrt(p2)) - 2 * math.asin(math.sqrt(p1))


def mde_abs(p_base: float, n: int, alpha: float = ALPHA, power: float = POWER) -> float:
    """给定每组样本量与基线率，反解可检出的最小绝对差异（双侧）。"""
    solver = NormalIndPower()

    def gap(delta: float) -> float:
        p_alt = p_base - delta  # 只考虑下降方向，与本次实验一致
        if p_alt <= 0:
            return -1
        h = abs(proportion_effectsize(p_alt, p_base))
        return solver.power(effect_size=h, nobs1=n, alpha=alpha, ratio=1.0) - power

    lo, hi = 1e-6, p_base * 0.9
    if gap(lo) > 0:  # 连极小效应都能检出
        return 0.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if gap(mid) > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def required_n(p_base: float, p_alt: float, alpha: float = ALPHA, power: float = POWER) -> int:
    h = abs(proportion_effectsize(p_alt, p_base))
    n = NormalIndPower().solve_power(effect_size=h, alpha=alpha, power=power, ratio=1.0)
    return int(math.ceil(n))


def holm(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[idx]))
        adj[idx] = running
    return adj.tolist()


# ---------------------------------------------------------------- 主流程


def main() -> None:
    rng = np.random.default_rng(SEED)
    df = pd.read_csv(CSV)
    log("=" * 78)
    log("Cookie Cats A/B 实验评估 · 分析日志")
    log(f"生成时间：{date.today().isoformat()}   随机种子：{SEED}")
    log("=" * 78)

    # ---------------- 1. 数据审计
    log("\n[1] 数据审计")
    n_total = len(df)
    log(f"  行数 {n_total:,} ｜ 列 {list(df.columns)}")
    missing = int(df.isna().sum().sum())
    dup_uid = int(df.userid.duplicated().sum())
    dup_full = int(df.duplicated().sum())
    log(f"  缺失值 {missing} ｜ 重复 userid {dup_uid} ｜ 完全重复行 {dup_full}")
    log(f"  version 取值 {df.version.value_counts().to_dict()}")

    n_a = int((df.version == A).sum())
    n_b = int((df.version == B).sum())
    log(f"  A 组 {A}: {n_a:,} ｜ B 组 {B}: {n_b:,}")

    # 异常值：首日轮次的长尾
    rounds_max = int(df.sum_gamerounds.max())
    top1 = df.loc[df.sum_gamerounds.idxmax()]
    log(f"  首日轮次最大值 {rounds_max:,}（userid={int(top1.userid)}，{top1.version}）")
    zero_rounds = {v: float((g.sum_gamerounds == 0).mean() * 100)
                   for v, g in df.groupby("version", observed=True)}
    log(f"  零轮次用户占比：" + " ｜ ".join(f"{k} {v:.2f}%" for k, v in zero_rounds.items()))

    # ---------------- 2. SRM：样本比例失衡检验
    log("\n[2] SRM 检查（样本比例失衡）")
    expected = n_total / 2
    chi2_srm = float(((n_a - expected) ** 2 + (n_b - expected) ** 2) / expected)
    p_srm = float(stats.chi2.sf(chi2_srm, df=1))
    dev_pct = (n_b - n_a) / n_total * 100
    share_a = n_a / n_total
    share_b = n_b / n_total
    log(f"  实测 A {share_a*100:.3f}% / B {share_b*100:.3f}%，B 比 A 多 {n_b-n_a:,} 人（{dev_pct:+.2f} 个百分点）")
    log(f"  χ² = {chi2_srm:.4f}，p = {p_srm:.4f} → "
        + ("检出失衡，需做敏感性分析" if p_srm < ALPHA else "未见失衡"))

    # SRM 的影响评估：组内均值不受两组人数比例影响，风险在于分流机制本身
    r7_a = df.loc[df.version == A, "retention_7"].mean()
    r7_b = df.loc[df.version == B, "retention_7"].mean()
    log(f"  说明：两组留存率均为组内均值，人数比例不机械地改变点估计（当前差 {(r7_b-r7_a)*100:+.3f} pp）。")
    log("  风险在于分流机制本身：若失衡与结果相关（例如高活跃用户更易落入某一组），")
    log("  组间比较即存在选择偏倚，且仅凭本数据无法检验——这是需要外部复现验证的一项。")

    # ---------------- 3. 功效复盘与 MDE
    log("\n[3] 功效复盘（alpha=0.05，power=0.80，双侧）")
    p_base_r7 = float(r7_a)
    p_base_r1 = float(df.loc[df.version == A, "retention_1"].mean())
    mde_r7 = mde_abs(p_base_r7, n_a)
    mde_r1 = mde_abs(p_base_r1, n_a)
    log(f"  7 日留存：每组 {n_a:,} 人 → 可检出最小绝对差异 {mde_r7*100:.3f} pp（相对 {mde_r7/p_base_r7*100:.2f}%）")
    log(f"  1 日留存：每组 {n_a:,} 人 → 可检出最小绝对差异 {mde_r1*100:.3f} pp（相对 {mde_r1/p_base_r1*100:.2f}%）")

    design = {
        "2.0pp": required_n(p_base_r7, p_base_r7 - 0.02),
        "1.0pp": required_n(p_base_r7, p_base_r7 - 0.01),
        "0.8pp": required_n(p_base_r7, p_base_r7 - 0.008),
        "0.5pp": required_n(p_base_r7, p_base_r7 - 0.005),
    }
    for k, v in design.items():
        log(f"  预实验设计｜若目标是检出 {k} 的 7 日留存差异，每组需 {v:,} 人（总 {2*v:,}）")

    curve_n = [5000, 10000, 15000, 20000, 30000, 45000, 60000, 90000, 120000, 180000, 250000]
    curve = [[int(n), float(mde_abs(p_base_r7, int(n)))] for n in curve_n]
    log("  功效曲线（R7）：" + " ｜ ".join(f"n={n//1000}k→{m*100:.2f}pp" for n, m in curve))

    # ---------------- 4. 三指标检验
    log("\n[4] 指标检验")

    def prop_metric(name: str, col: str) -> dict:
        k_a = int(df.loc[df.version == A, col].sum())
        k_b = int(df.loc[df.version == B, col].sum())
        p_a, p_b = k_a / n_a, k_b / n_b
        z, p_val = two_prop_z(k_a, n_a, k_b, n_b)
        chi2 = z * z
        p_chi = float(stats.chi2.sf(chi2, df=1))
        ci_a = wilson_ci(k_a, n_a)
        ci_b = wilson_ci(k_b, n_b)
        ci_d = newcombe_diff_ci(k_a, n_a, k_b, n_b)
        ci_rel = relative_ci(k_a, n_a, k_b, n_b)
        h = cohen_h(p_a, p_b)
        out = {
            "name": name,
            "k_a": k_a, "k_b": k_b,
            "rate_a": p_a, "rate_b": p_b,
            "ci_a": ci_a, "ci_b": ci_b,
            "diff_pp": (p_b - p_a) * 100,
            "ci_diff_pp": (ci_d[0] * 100, ci_d[1] * 100),
            "rel": (p_b - p_a) / p_a,
            "ci_rel": ci_rel,
            "z": z, "p": p_val, "chi2": chi2, "p_chi": p_chi,
            "cohen_h": h,
            "test": "两比例 z 检验（合并方差）",
        }
        log(f"  {name}: A {p_a*100:.3f}% [{ci_a[0]*100:.2f},{ci_a[1]*100:.2f}] ｜ "
            f"B {p_b*100:.3f}% [{ci_b[0]*100:.2f},{ci_b[1]*100:.2f}]")
        log(f"    差 {(p_b-p_a)*100:+.3f} pp [{ci_d[0]*100:+.3f},{ci_d[1]*100:+.3f}] ｜ "
            f"相对 {(p_b-p_a)/p_a*100:+.2f}% [{ci_rel[0]*100-100:+.2f}%,{ci_rel[1]*100-100:+.2f}%] ｜ "
            f"z={z:.3f} p={p_val:.4f} h={h:+.4f}")
        return out

    m_r1 = prop_metric("1 日留存", "retention_1")
    m_r7 = prop_metric("7 日留存", "retention_7")

    # 连续型指标：首日游戏轮次
    s_a = df.loc[df.version == A, "sum_gamerounds"].to_numpy()
    s_b = df.loc[df.version == B, "sum_gamerounds"].to_numpy()
    t_stat, p_welch = stats.ttest_ind(s_b, s_a, equal_var=False)
    u_stat, p_mwu = stats.mannwhitneyu(s_b, s_a, alternative="two-sided")
    # bootstrap 均值差
    boot = np.empty(4000)
    boot_rel = np.empty(4000)
    for i in range(4000):
        mb = rng.choice(s_b, n_b, replace=True).mean()
        ma = rng.choice(s_a, n_a, replace=True).mean()
        boot[i] = mb - ma
        boot_rel[i] = (mb - ma) / ma
    ci_boot = (float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)))
    ci_boot_rel = (float(np.percentile(boot_rel, 2.5)), float(np.percentile(boot_rel, 97.5)))
    # 缩尾 / 截尾
    trim_a, trim_b = stats.trim_mean(s_a, 0.01), stats.trim_mean(s_b, 0.01)
    trim5_a, trim5_b = stats.trim_mean(s_a, 0.05), stats.trim_mean(s_b, 0.05)
    mean_a, mean_b = float(s_a.mean()), float(s_b.mean())
    med_a, med_b = float(np.median(s_a)), float(np.median(s_b))
    # 剔除单个极端值后的均值
    drop_a = float(np.sort(s_a)[:-1].mean())
    drop_both = float(np.sort(s_b)[:-1].mean() - np.sort(s_a)[:-1].mean())
    rank_biserial = 2 * float(u_stat) / (n_a * n_b) - 1
    m_rounds = {
        "name": "首日游戏轮次",
        "mean_a": mean_a, "mean_b": mean_b,
        "mean_diff": mean_b - mean_a,
        "mean_rel": (mean_b - mean_a) / mean_a,
        "ci_boot": ci_boot,
        "ci_boot_rel": ci_boot_rel,
        "median_a": med_a, "median_b": med_b,
        "median_diff": med_b - med_a,
        "trim_a": float(trim_a), "trim_b": float(trim_b),
        "trim_diff": float(trim_b - trim_a),
        "trim5_a": float(trim5_a), "trim5_b": float(trim5_b),
        "trim5_diff": float(trim5_b - trim5_a),
        "drop_top_a": drop_a,
        "drop_top_diff": float(mean_b - drop_a),
        "drop_both_diff": drop_both,
        "t": float(t_stat), "p_welch": float(p_welch),
        "u": float(u_stat), "p_mwu": float(p_mwu),
        "rank_biserial": rank_biserial,
        "p90_a": float(np.percentile(s_a, 90)), "p90_b": float(np.percentile(s_b, 90)),
        "sd_a": float(s_a.std(ddof=1)), "sd_b": float(s_b.std(ddof=1)),
        "test": "Welch t 检验 + Mann-Whitney U + bootstrap",
    }
    log(f"  首日轮次: 均值 A {mean_a:.3f} / B {mean_b:.3f}（差 {mean_b-mean_a:+.3f}，"
        f"bootstrap 95%CI [{ci_boot[0]:+.3f},{ci_boot[1]:+.3f}]）")
    log(f"    Welch t={t_stat:.3f} p={p_welch:.4f} ｜ Mann-Whitney p={p_mwu:.4f}，"
        f"秩二列相关 r={rank_biserial:+.4f}")
    log(f"    中位数 A {med_a:.0f} / B {med_b:.0f}（差 {med_b-med_a:+.0f}）｜ "
        f"1% 截尾均值 A {trim_a:.3f} / B {trim_b:.3f}（差 {trim_b-trim_a:+.3f}）")
    log(f"    剔除最大单点后 A 均值 {drop_a:.3f}，与 B 的差变为 {mean_b-drop_a:+.3f}")
    log(f"    各组同时剔除最大 1 个观测后，均值差为 {drop_both:+.3f} 轮")

    # ---------------- 5. 多重比较
    log("\n[5] 多重比较校正（3 个指标同时检验）")
    raw_p = [m_r1["p"], m_r7["p"], m_rounds["p_welch"]]
    names = [m_r1["name"], m_r7["name"], m_rounds["name"]]
    holm_p = holm(raw_p)
    bh = multipletests(raw_p, method="fdr_bh")[1].tolist()
    multi = []
    for nm, pr, ph, pb in zip(names, raw_p, holm_p, bh):
        log(f"  {nm}: p={pr:.4f} → Holm {ph:.4f} ｜ BH {pb:.4f} "
            + ("（仍显著）" if ph < ALPHA else "（不再显著）"))
        multi.append({"name": nm, "p_raw": pr, "p_holm": ph, "p_bh": pb})

    # 若把 5 个活跃层级分段也计入，族错误率
    n_tests_family = 3 + 10
    log(f"  提示：若把 3 个整体指标 + 5 个层级 × 2 个留存指标全部检验（共 {n_tests_family} 次），"
        f"α=0.05 下的期望假阳性个数为 {n_tests_family*ALPHA:.2f}")

    # ---------------- 6. 分段异质性（事后分层，仅作诊断）
    log("\n[6] 分段异质性（按首日活跃层级，事后变量）")
    bins = [-1, 0, 5, 20, 50, 10 ** 9]
    labels = ["0 局", "1–5 局", "6–20 局", "21–50 局", "50 局以上"]
    df["tier"] = pd.cut(df.sum_gamerounds, bins=bins, labels=labels)
    seg = []
    for tier in labels:
        sub = df[df.tier == tier]
        ka = int(sub.loc[sub.version == A, "retention_7"].sum())
        na_ = int((sub.version == A).sum())
        kb = int(sub.loc[sub.version == B, "retention_7"].sum())
        nb_ = int((sub.version == B).sum())
        pa, pb = ka / na_, kb / nb_
        _, pv = two_prop_z(ka, na_, kb, nb_)
        ci_d = newcombe_diff_ci(ka, na_, kb, nb_)
        seg.append({
            "tier": tier, "n_a": na_, "n_b": nb_,
            "rate_a": pa, "rate_b": pb, "diff_pp": (pb - pa) * 100, "p": pv,
            "ci_diff_pp": [ci_d[0] * 100, ci_d[1] * 100],
        })
        log(f"  {tier:<10} n={na_+nb_:>6,}  A {pa*100:6.2f}%  B {pb*100:6.2f}%  差 {(pb-pa)*100:+6.2f} pp  p={pv:.3f}")

    # 交互项检验：版本 × 活跃层级
    p_inter = None
    try:
        import statsmodels.formula.api as smf
        d = df.copy()
        d["y"] = d.retention_7.astype(int)
        full = smf.logit("y ~ C(version) * C(tier)", data=d).fit(disp=0)
        main = smf.logit("y ~ C(version) + C(tier)", data=d).fit(disp=0)
        lr = 2 * (full.llf - main.llf)
        p_inter = float(stats.chi2.sf(lr, df=4))
        log(f"  交互项似然比检验：LR={lr:.3f}，df=4，p={p_inter:.4f}")
    except Exception as e:  # noqa: BLE001
        log(f"  交互项检验跳过：{e}")

    # ---------------- 7. 贝叶斯复核
    log("\n[7] 贝叶斯复核（Beta(1,1) 无信息先验）")
    ka7 = int(df.loc[df.version == A, "retention_7"].sum())
    kb7 = int(df.loc[df.version == B, "retention_7"].sum())
    draws_a = rng.beta(1 + ka7, 1 + n_a - ka7, 200000)
    draws_b = rng.beta(1 + kb7, 1 + n_b - kb7, 200000)
    prob_b_worse = float((draws_b < draws_a).mean())
    prob_b_better5 = float(((draws_b - draws_a) > 0.005).mean())
    loss = float(np.mean(np.maximum(draws_a - draws_b, 0)) * 100)
    log(f"  P(B 的 7 日留存低于 A) = {prob_b_worse*100:.2f}%")
    log(f"  P(B 高出 A 至少 0.5 pp) = {prob_b_better5*100:.3f}%")
    log(f"  若上线 B，留存损失的期望值 = {loss:.3f} pp")

    # ---------------- 8. 连续监测（peeking）风险
    log("\n[8] 连续监测（peeking）下的假阳性率")
    y = df.retention_7.to_numpy().astype(int)
    lab = (df.version == B).to_numpy().astype(int)
    n = len(df)
    looks = 10
    pos = np.linspace(n // looks, n, looks).astype(int) - 1
    B_SIM = 2000
    first_exceed = np.full(B_SIM, looks + 1, dtype=int)
    for i in range(B_SIM):
        # 零假设：打乱结果与分组的对应关系，得到"实验无差异"下的一次虚拟实验
        lp = lab
        yp = rng.permutation(y)
        c_lab = np.cumsum(lp)
        c_yb = np.cumsum(yp * lp)
        c_y = np.cumsum(yp)
        for j, k in enumerate(pos):
            n1 = c_lab[k]
            n0 = (k + 1) - n1
            s1 = c_yb[k]
            s0 = c_y[k] - s1
            p1, p0 = s1 / n1, s0 / n0
            pp = (s1 + s0) / (k + 1)
            se = math.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n0))
            if abs((p1 - p0) / se) > Z_95:
                first_exceed[i] = j + 1
                break
    fpr_curve = [float((first_exceed <= j).mean()) for j in range(1, looks + 1)]
    fpr_peek = fpr_curve[-1]
    log(f"  零假设下重复 {B_SIM} 次，看 {looks} 次就喊停（|z|>1.96）的假阳性率 = {fpr_peek*100:.1f}%")
    log("  逐步累积：" + " ｜ ".join(f"{j}次 {v*100:.1f}%" for j, v in enumerate(fpr_curve, 1)))
    log(f"  单次检验的理论假阳性率 = 5.0%")

    # ---------------- 9. 结论判定
    log("\n[9] 判定")
    significant_r7 = m_r7["p"] < ALPHA
    log(f"  主指标 7 日留存 p={m_r7['p']:.4f}，"
        + ("显著下降 → 不建议上线" if significant_r7 and m_r7["diff_pp"] < 0 else "未见显著变化"))
    log(f"  1 日留存 p={m_r1['p']:.4f}，观测差异 {m_r1['diff_pp']:+.3f} pp，"
        f"小于本实验检出下限 {mde_r1*100:.3f} pp → 不能解读为“无差异”")

    # ---------------- 汇总输出
    metrics = {
        "meta": {
            "title": "Cookie Cats 新手引导门槛 A/B 实验评估",
            "n_total": n_total, "n_a": n_a, "n_b": n_b,
            "group_a": A, "group_b": B,
            "alpha": ALPHA, "power": POWER, "seed": SEED,
            "analysis_date": date.today().isoformat(),
            "data_sha256": "5ab54d761fbddcd50de7b88e4eaf7837cba4569474f50c043a4d17ee342c46bd",
        },
        "data_check": {
            "missing": missing, "dup_userid": dup_uid, "dup_rows": dup_full,
            "rounds_max": rounds_max, "rounds_max_user": int(top1.userid),
            "rounds_max_group": str(top1.version),
            "zero_rounds_pct": zero_rounds,
            "rounds_sd": {"a": float(s_a.std(ddof=1)), "b": float(s_b.std(ddof=1))},
            "rounds_p90": {"a": float(np.percentile(s_a, 90)), "b": float(np.percentile(s_b, 90))},
        },
        "srm": {
            "chi2": chi2_srm, "p": p_srm, "share_a": share_a, "share_b": share_b,
            "dev_pp": dev_pct, "significant": bool(p_srm < ALPHA),
        },
        "power": {
            "p_base_r7": p_base_r7, "p_base_r1": p_base_r1,
            "mde_r7_pp": mde_r7 * 100, "mde_r1_pp": mde_r1 * 100,
            "mde_r7_rel": mde_r7 / p_base_r7 * 100, "mde_r1_rel": mde_r1 / p_base_r1 * 100,
            "design_n": design, "curve": curve,
        },
        "metrics": {"retention_1": m_r1, "retention_7": m_r7, "rounds": m_rounds},
        "multi": multi,
        "segments": {"rows": seg, "p_interaction": p_inter},
        "bayes": {"prob_b_worse": prob_b_worse, "prob_b_better_5pp": prob_b_better5, "expected_loss_pp": loss},
        "peeking": {"looks": looks, "sims": B_SIM, "fpr": fpr_peek,
                    "fpr_curve": fpr_curve, "nominal": ALPHA},
    }

    with open(os.path.join(DATA_DIR, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2, default=float)
    log(f"\n[输出] data/metrics.json 已写入")

    with open(os.path.join(DATA_DIR, "analysis_log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")
    print(f"[输出] data/analysis_log.txt 已写入（{len(LOG)} 行）")


if __name__ == "__main__":
    main()
