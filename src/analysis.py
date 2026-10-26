# -*- coding: utf-8 -*-
"""A/B 测试与因果推断实验室 — 基于可复现模拟的完整实验方法学流水线

九个模块：实验设计（样本量/功效）→ 单次实验与假设检验 → AA 检验 → 功效模拟验证
→ 偷看(peeking)问题 → 多重检验校正 → CUPED 方差缩减 → 辛普森悖论 → 业务收益估算

所有模拟固定随机种子，可复现。比例检验用二项近似（每组转化数 ~ Binomial），
连续指标用正态模拟；输出 output/ 图表与 metrics.json。
"""
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti TC", "Arial Unicode MS", "STHeiti"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130
C = {"main": "#2563EB", "warm": "#D97706", "bad": "#E5484D", "good": "#10B981", "grey": "#9AA5B1"}

RNG = np.random.default_rng(20261027)
ALPHA = 0.05
POWER_TARGET = 0.80
metrics = {"alpha": ALPHA}

z_a = stats.norm.ppf(1 - ALPHA / 2)      # 1.96
z_b = stats.norm.ppf(POWER_TARGET)       # 0.8416


def two_prop_z(x1, n1, x2, n2):
    """两比例合并 z 检验，返回 (z, p, diff, ci)"""
    p1, p2 = x1 / n1, x2 / n2
    p_bar = (x1 + x2) / (n1 + n2)
    se = np.sqrt(p_bar * (1 - p_bar) * (1 / n1 + 1 / n2))
    z = (p2 - p1) / se
    p = 2 * stats.norm.sf(abs(z))
    se0 = np.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    ci = (p2 - p1 - 1.96 * se0, p2 - p1 + 1.96 * se0)
    return z, p, p2 - p1, ci


# ========== 1. 实验设计：样本量计算 ==========
P1 = 0.05          # 基线转化率 5%
LIFT = 0.10        # 相对提升 10%
P2 = P1 * (1 + LIFT)
DELTA = P2 - P1

var_ = P1 * (1 - P1) + P2 * (1 - P2)
n_per_arm = int(np.ceil(((z_a + z_b) ** 2) * var_ / DELTA ** 2))
metrics.update({"p1": P1, "lift": LIFT, "p2": P2, "n_per_arm": n_per_arm,
                "n_total": 2 * n_per_arm})

mdes = np.linspace(0.002, 0.02, 60)
ns = ((z_a + z_b) ** 2) * (P1 * (1 - P1) + (P1 + mdes) * (1 - P1 - mdes)) / mdes ** 2
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.plot(mdes * 100, ns / 10000, color=C["main"], lw=2)
ax.axvline(DELTA * 100, ls="--", c=C["warm"], lw=1.2)
ax.annotate(f"本实验 MDE={DELTA * 100:.1f}pp\n每组 {n_per_arm:,} 人",
            xy=(DELTA * 100, n_per_arm / 10000), xytext=(DELTA * 100 + 0.25, n_per_arm / 10000 * 2.1),
            fontsize=9, arrowprops=dict(arrowstyle="->", color=C["warm"]))
ax.set_xlabel("最小可检测提升 MDE（百分点）")
ax.set_ylabel("每组所需样本量（万）")
ax.set_title(f"样本量计算：基线 {P1 * 100:.0f}%，α={ALPHA}（双侧），功效 {POWER_TARGET:.0%}")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "01_sample_size.png", bbox_inches="tight")
plt.close(fig)

# ========== 2. 单次实验：z 检验全流程 ==========
x1 = RNG.binomial(n_per_arm, P1)
x2 = RNG.binomial(n_per_arm, P2)
z, p, diff, ci = two_prop_z(x1, n_per_arm, x2, n_per_arm)
metrics["demo"] = {"x1": int(x1), "x2": int(x2), "z": round(float(z), 3),
                   "p": float(f"{p:.2e}"), "diff_pp": round(diff * 100, 3),
                   "ci_pp": [round(ci[0] * 100, 3), round(ci[1] * 100, 3)],
                   "significant": bool(p < ALPHA)}

fig, ax = plt.subplots(figsize=(8, 3.6))
ax.errorbar([1, 2], [x1 / n_per_arm, x2 / n_per_arm],
            yerr=1.96 * np.sqrt([x1 / n_per_arm * (1 - x1 / n_per_arm) / n_per_arm,
                                 x2 / n_per_arm * (1 - x2 / n_per_arm) / n_per_arm]),
            fmt="o", capsize=6, color=C["main"], lw=2)
ax.set_xticks([1, 2], ["对照组", "实验组"])
ax.set_ylabel("转化率（95% CI）")
ax.set_title(f"模拟实验结果：提升 {diff * 100:.2f}pp，95%CI [{ci[0] * 100:.2f}, {ci[1] * 100:.2f}]pp，"
             f"z={z:.2f}，p={p:.1e}")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "02_single_test.png", bbox_inches="tight")
plt.close(fig)

# ========== 3. AA 检验：平台无偏性验证 ==========
N_SIM = 100_000
x1_aa = RNG.binomial(n_per_arm, P1, N_SIM)
x2_aa = RNG.binomial(n_per_arm, P1, N_SIM)
p_bar_aa = (x1_aa + x2_aa) / (2 * n_per_arm)
se_aa = np.sqrt(p_bar_aa * (1 - p_bar_aa) * (2 / n_per_arm))
z_aa = (x2_aa - x1_aa) / n_per_arm / se_aa
fp_aa = float(np.mean(np.abs(z_aa) > z_a))
metrics["aa_false_positive"] = round(fp_aa * 100, 2)

fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
axes[0].hist(z_aa, bins=80, density=True, color=C["main"], alpha=0.8)
xs = np.linspace(-4.5, 4.5, 200)
axes[0].plot(xs, stats.norm.pdf(xs), color=C["bad"], lw=1.5, label="理论 N(0,1)")
axes[0].axvline(z_a, ls="--", c=C["warm"]); axes[0].axvline(-z_a, ls="--", c=C["warm"])
axes[0].set_title(f"AA 检验 z 分布（{N_SIM:,} 次）：拒绝率 {fp_aa * 100:.2f}% ≈ α")
axes[0].legend(fontsize=9)
axes[0].spines[["top", "right"]].set_visible(False)
axes[1].hist(np.clip(stats.norm.sf(np.abs(z_aa)) * 2, 1e-6, 1), bins=80, color=C["good"])
axes[1].set_yscale("log")
axes[1].axvline(ALPHA, ls="--", c=C["bad"])
axes[1].set_title("AA 检验 p 值分布（对数轴）：均匀分布是健康标志")
axes[1].set_xlabel("p 值")
axes[1].spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "03_aa_test.png", bbox_inches="tight")
plt.close(fig)

# ========== 4. 功效模拟验证 ==========
x1_pw = RNG.binomial(n_per_arm, P1, N_SIM)
x2_pw = RNG.binomial(n_per_arm, P2, N_SIM)
p_bar_pw = (x1_pw + x2_pw) / (2 * n_per_arm)
se_pw = np.sqrt(p_bar_pw * (1 - p_bar_pw) * (2 / n_per_arm))
z_pw = (x2_pw - x1_pw) / n_per_arm / se_pw
power_sim = float(np.mean(z_pw > z_a))
metrics["power_simulated"] = round(power_sim * 100, 2)

# ========== 5. 偷看（peeking）问题 ==========
DAYS = 30
per_day = n_per_arm // DAYS
n_peek_sims = 20_000
daily_ctrl = RNG.binomial(per_day, P1, (n_peek_sims, DAYS))
daily_treat = RNG.binomial(per_day, P2, (n_peek_sims, DAYS))
cum_c = np.cumsum(daily_ctrl, axis=1)
cum_t = np.cumsum(daily_treat, axis=1)
day_idx = np.arange(1, DAYS + 1) * per_day
p_bar_pk = (cum_c + cum_t) / (2 * day_idx)
se_pk = np.sqrt(p_bar_pk * (1 - p_bar_pk) * (2 / day_idx))
z_pk = (cum_t - cum_c) / day_idx / se_pk
# AA 场景下的假阳性率：任一天显著即宣布
daily_ctrl_aa = RNG.binomial(per_day, P1, (n_peek_sims, DAYS))
daily_treat_aa = RNG.binomial(per_day, P1, (n_peek_sims, DAYS))
cc = np.cumsum(daily_ctrl_aa, axis=1)
tt = np.cumsum(daily_treat_aa, axis=1)
pb = (cc + tt) / (2 * day_idx)
sep = np.sqrt(pb * (1 - pb) * (2 / day_idx))
z_aa_pk = (tt - cc) / day_idx / sep
fp_peek = float(np.mean(np.any(np.abs(z_aa_pk) > z_a, axis=1)))
fp_once = float(np.mean(np.abs(z_aa_pk[:, -1]) > z_a))
metrics["peeking"] = {"fp_once": round(fp_once * 100, 2),
                      "fp_daily_peek_30d": round(fp_peek * 100, 2),
                      "inflation": round(fp_peek / fp_once, 1)}

# 不同监看频率的假阳性率曲线
freq_days = [1, 2, 5, 10, 30]
fp_by_freq = []
for k in freq_days:
    idx = np.linspace(DAYS // k - 1, DAYS - 1, k).astype(int) if k <= DAYS else np.array([DAYS - 1])
    fp_by_freq.append(float(np.mean(np.any(np.abs(z_aa_pk[:, idx]) > z_a, axis=1)) * 100))
metrics["peeking"]["fp_by_check_freq"] = dict(zip([f"每{k}天看1次" if k > 1 else "只在结束看1次" for k in freq_days],
                                                  [round(v, 2) for v in fp_by_freq]))

fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
axes[0].bar(["结束看 1 次", "每天偷看\n(30天)"],
            [fp_once * 100, fp_peek * 100], color=[C["good"], C["bad"]])
for i, v in enumerate([fp_once * 100, fp_peek * 100]):
    axes[0].text(i, v + 0.3, f"{v:.1f}%", ha="center", fontweight="bold")
axes[0].set_ylabel("实际假阳性率 %")
axes[0].set_title(f"偷看使假阳性率膨胀 {fp_peek / fp_once:.1f} 倍（名义 α={ALPHA * 100:.0f}%）")
axes[0].spines[["top", "right"]].set_visible(False)
axes[1].plot(range(len(freq_days)), fp_by_freq, marker="o", color=C["main"])
axes[1].set_xticks(range(len(freq_days)), ["结束1次", "每10天", "每5天", "每2天", "每天"], fontsize=9)
axes[1].axhline(5, ls="--", c=C["good"], lw=1)
axes[1].text(0.05, 5.3, "名义 5%", fontsize=8, color=C["good"])
axes[1].set_ylabel("实际假阳性率 %")
axes[1].set_title("监看越频繁，假阳性率越高")
axes[1].spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "04_peeking.png", bbox_inches="tight")
plt.close(fig)

# ========== 6. 多重检验：Bonferroni 校正 ==========
M_METRICS = 5
N_M = 50_000
n_m = n_per_arm
x1_m = RNG.binomial(n_m, P1, (N_M, M_METRICS))
x2_m = RNG.binomial(n_m, P1, (N_M, M_METRICS))   # 全部指标真实无效
pb_m = (x1_m + x2_m) / (2 * n_m)
se_m = np.sqrt(pb_m * (1 - pb_m) * (2 / n_m))
z_m = (x2_m - x1_m) / n_m / se_m
sig_uncorr = np.abs(z_m) > z_a
sig_bonf = np.abs(z_m) > stats.norm.ppf(1 - ALPHA / 2 / M_METRICS)
fwer_uncorr = float(np.mean(sig_uncorr.any(axis=1)) * 100)
fwer_bonf = float(np.mean(sig_bonf.any(axis=1)) * 100)
metrics["multitest"] = {"m": M_METRICS, "fwer_uncorrected": round(fwer_uncorr, 2),
                        "fwer_bonferroni": round(fwer_bonf, 2),
                        "theory_uncorrected": round((1 - (1 - ALPHA) ** M_METRICS) * 100, 2)}

fig, ax = plt.subplots(figsize=(7, 3.6))
vals = [fwer_uncorr, metrics["multitest"]["theory_uncorrected"], fwer_bonf]
ax.bar(["模拟：不校正", f"理论：1−0.95⁵", "模拟：Bonferroni"], vals,
       color=[C["bad"], C["grey"], C["good"]])
for i, v in enumerate(vals):
    ax.text(i, v + 0.4, f"{v:.1f}%", ha="center", fontweight="bold")
ax.set_ylabel(f"至少 1 项指标误报的比例 %（{M_METRICS} 项均无效）")
ax.set_title(f"多重检验：看 {M_METRICS} 个指标时，族错误率从不校正的失控到 Bonferroni 拉回")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "05_multiplicity.png", bbox_inches="tight")
plt.close(fig)

# ========== 7. CUPED 方差缩减 ==========
RHO = 0.6                      # 指标与实验前协变量的相关系数（业务中常见 0.3~0.7）
N_CUPED = 10_000               # 每组样本量（故意设小，让原始功效不足以凸显 CUPED 价值）
N_SIM_CUPED = 2_000
EFFECT_SIGMA = 0.028           # 真实效应 0.028 个标准差（小效应场景）
# 关键：两组必须各自独立采样（协变量、噪声都是独立矩阵）。
# 若共享同一噪声矩阵（Y_treat = Y_ctrl + 效应），均值差恒等于效应、无抽样波动，
# 模拟的将不是独立两样本实验而是配对设计——这是本次开发中踩过并修复的真实错误。
Xc = RNG.standard_normal((N_SIM_CUPED, N_CUPED))
Xt = RNG.standard_normal((N_SIM_CUPED, N_CUPED))
Y_ctrl = RHO * Xc + np.sqrt(1 - RHO ** 2) * RNG.standard_normal((N_SIM_CUPED, N_CUPED))
Y_treat = RHO * Xt + np.sqrt(1 - RHO ** 2) * RNG.standard_normal((N_SIM_CUPED, N_CUPED)) + EFFECT_SIGMA
# CUPED 调整：Y_adj = Y − θ·(X − E[X])；模拟中 E[X]=0，直接减 θ·X。
# 注意必须用已知的总体期望（或历史数据均值）做中心化，
# 若用本次实验的样本均值做中心化会部分吸收处理效应，引入偏差。
Yc_adj = Y_ctrl - RHO * Xc
Yt_adj = Y_treat - RHO * Xt
var_ratio = float(Yc_adj.var() / Y_ctrl.var())
z_raw = (Y_treat.mean(1) - Y_ctrl.mean(1)) / (Y_ctrl.std(1) * np.sqrt(2 / N_CUPED))
z_cuped = (Yt_adj.mean(1) - Yc_adj.mean(1)) / (Yc_adj.std(1) * np.sqrt(2 / N_CUPED))
power_raw = float(np.mean(z_raw > z_a) * 100)
power_cuped = float(np.mean(z_cuped > z_a) * 100)
n_ratio = 1 - RHO ** 2   # 达到同样功效所需样本量比例 = 1 − ρ²
metrics["cuped"] = {"rho": RHO, "n_per_arm": N_CUPED, "effect_sigma": EFFECT_SIGMA,
                    "var_reduction": round((1 - var_ratio) * 100, 1),
                    "power_raw_same_n": round(power_raw, 1),
                    "power_cuped_same_n": round(power_cuped, 1),
                    "n_needed_ratio": round(n_ratio * 100, 1)}

fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
axes[0].hist(Y_ctrl.mean(1), bins=60, alpha=0.65, label="原始指标均值（方差 1.00）", color=C["grey"])
axes[0].hist(Yc_adj.mean(1), bins=60, alpha=0.65,
             label=f"CUPED 调整后（方差降至 {var_ratio:.2f}）", color=C["main"])
axes[0].set_title(f"CUPED：用实验前数据把方差缩减 {(1 - var_ratio) * 100:.0f}%")
axes[0].legend(fontsize=8)
axes[0].spines[["top", "right"]].set_visible(False)
axes[1].bar(["原始指标", "CUPED 调整"],
            [power_raw, power_cuped], color=[C["grey"], C["main"]])
for i, v in enumerate([power_raw, power_cuped]):
    axes[1].text(i, v + 1.5, f"{v:.0f}%", ha="center", fontweight="bold")
axes[1].set_ylabel("实际功效 %")
axes[1].set_title(f"同样 {N_CUPED:,} 人/组下功效大幅提升\n等效方案：所需样本量降至 {n_ratio * 100:.0f}%")
axes[1].spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "06_cuped.png", bbox_inches="tight")
plt.close(fig)

# ========== 8. 辛普森悖论复现 ==========
# 场景：新旧版落地页。实验组流量意外偏向低转化人群（新用户占比 90% vs 对照组 10%），
# 每个分层内新版都略好，但混合后人群结构差异把结论整体反转——经典辛普森悖论。
simp = {
    "新用户(基础转化率10%)": {"旧版": (900, 9000), "新版": (105, 1000)},   # (转化数, 曝光)
    "老用户(基础转化率2%)": {"旧版": (20, 1000), "新版": (195, 9000)},
}
r_new_layer1 = simp["新用户(基础转化率10%)"]["新版"][0] / simp["新用户(基础转化率10%)"]["新版"][1]
r_old_layer1 = simp["新用户(基础转化率10%)"]["旧版"][0] / simp["新用户(基础转化率10%)"]["旧版"][1]
r_new_layer2 = simp["老用户(基础转化率2%)"]["新版"][0] / simp["老用户(基础转化率2%)"]["新版"][1]
r_old_layer2 = simp["老用户(基础转化率2%)"]["旧版"][0] / simp["老用户(基础转化率2%)"]["旧版"][1]
agg_new = (simp["新用户(基础转化率10%)"]["新版"][0] + simp["老用户(基础转化率2%)"]["新版"][0]) / 10000
agg_old = (simp["新用户(基础转化率10%)"]["旧版"][0] + simp["老用户(基础转化率2%)"]["旧版"][0]) / 10000
metrics["simpson"] = {"new_user": [round(r_old_layer1 * 100, 2), round(r_new_layer1 * 100, 2)],
                      "old_user": [round(r_old_layer2 * 100, 2), round(r_new_layer2 * 100, 2)],
                      "aggregate": [round(agg_old * 100, 2), round(agg_new * 100, 2)]}

fig, ax = plt.subplots(figsize=(9, 3.8))
groups = ["新用户层", "老用户层", "总体（混合）"]
old_v = [r_old_layer1 * 100, r_old_layer2 * 100, agg_old * 100]
new_v = [r_new_layer1 * 100, r_new_layer2 * 100, agg_new * 100]
xx = np.arange(3)
ax.bar(xx - 0.18, old_v, 0.36, label="旧版", color=C["grey"])
ax.bar(xx + 0.18, new_v, 0.36, label="新版", color=C["main"])
for i in range(3):
    verdict = "新版更好 ↑" if new_v[i] > old_v[i] else "结论反转：旧版『更好』↓"
    ax.text(i, max(old_v[i], new_v[i]) + 0.3, verdict, ha="center", fontsize=9,
            color=C["good"] if new_v[i] > old_v[i] else C["bad"])
ax.set_xticks(xx, groups)
ax.set_ylabel("转化率 %")
ax.set_title("辛普森悖论：分层看新版全面更好，混合后结论整体反转（实验组流量偏向低转化人群）")
ax.legend()
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "07_simpson.png", bbox_inches="tight")
plt.close(fig)

# ========== 9. 业务收益估算 ==========
ARPU_MONTH = 40.0        # 每用户月均收入（元）
MAU_EXPOSED = 2_000_000  # 实验覆盖的月活
# 收益点估计用本次实验观测到的提升；区间直接由提升量的 95%CI 换算（诚实展示不确定性）
monthly_gain = diff * MAU_EXPOSED * ARPU_MONTH
monthly_gain_ci = [ci[0] * MAU_EXPOSED * ARPU_MONTH, ci[1] * MAU_EXPOSED * ARPU_MONTH]
metrics["business"] = {"lift_point": round(diff * 100, 3),
                       "monthly_gain": round(monthly_gain, 0),
                       "monthly_gain_ci": [round(monthly_gain_ci[0], 0), round(monthly_gain_ci[1], 0)],
                       "arpu": ARPU_MONTH, "mau": MAU_EXPOSED}

fig, ax = plt.subplots(figsize=(8, 3.2))
ax.barh(["月增收"], [monthly_gain / 10000], color=C["main"], height=0.4)
ax.errorbar([monthly_gain / 10000], [0],
            xerr=[[abs(monthly_gain - monthly_gain_ci[0]) / 10000],
                  [abs(monthly_gain_ci[1] - monthly_gain) / 10000]],
            fmt="none", ecolor=C["bad"], capsize=6, lw=2)
ax.set_xlim(max(0, monthly_gain_ci[0] / 10000 * 0.8), monthly_gain_ci[1] / 10000 * 1.1)
ax.text(monthly_gain / 10000 * 1.02, 0.05, f"¥{monthly_gain / 10000:.0f} 万/月", va="center")
ax.set_xlabel("万元 / 月")
ax.set_title(f"收益估算：提升 {diff * 100:.2f}pp × {MAU_EXPOSED / 10000:.0f}0万 MAU × ¥{ARPU_MONTH:.0f} ARPU"
             f"（红线为 95%CI，来自提升量的置信区间）")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(OUT / "08_business.png", bbox_inches="tight")
plt.close(fig)

# ========== 保存 ==========
(OUT / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: metrics[k] for k in
                  ["n_per_arm", "aa_false_positive", "power_simulated",
                   "peeking", "multitest", "cuped", "simpson", "business"]},
                 ensure_ascii=False, indent=2))
print("图表与 metrics.json 已输出到", OUT)
