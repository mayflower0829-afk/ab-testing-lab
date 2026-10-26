# -*- coding: utf-8 -*-
"""把 output/ 下的 metrics.json 与图表组装为可部署的单页 HTML 报告。

用法：python3 src/build_report.py
产物：ab-testing-lab/public/（index.html + charts/*.png）
"""
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
PUB = ROOT / "public"
(CHARTS := PUB / "charts").mkdir(parents=True, exist_ok=True)

M = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))

for png in OUT.glob("*.png"):
    shutil.copy(png, CHARTS / png.name)


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def metric_card(v, label, note=""):
    return f'<div class="kpi"><b>{v}</b><span>{label}</span><em>{note}</em></div>'


d = M["demo"]
verdict = (
    f"本次模拟 <b>p = {d['p']:.2e} &lt; 0.05，检出显著</b>。"
    if d["significant"]
    else f"本次模拟 <b>p = {d['p']:.3f} &gt; 0.05，未检出显著</b>——注意：真实提升是 10%，"
    f"但单次实验仍可能不显著。功效 {M['power_simulated']:.0f}% 的含义正是："
    f"约 {M['power_simulated']:.0f}% 的此类实验能检出显著，约 {100 - M['power_simulated']:.0f}% 会漏检。"
    "「实验不显著」≠「没有效果」，这一区分是 A/B 测试最常见的误读。"
)

kpi = (
    metric_card(f"{M['aa_false_positive']:.2f}%", "AA 假阳性率", f"理论 α = {M['alpha'] * 100:.0f}%")
    + metric_card(f"{M['power_simulated']:.1f}%", "模拟功效", "理论目标 80%")
    + metric_card(f"{M['peeking']['fp_daily_peek_30d']:.1f}%", "每天偷看的假阳性", f"膨胀 {M['peeking']['inflation']} 倍")
    + metric_card(f"{M['multitest']['fwer_bonferroni']:.1f}%", "校正后族错误率", f"不校正为 {M['multitest']['fwer_uncorrected']:.1f}%")
)

pf = M["peeking"]["fp_by_check_freq"]

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A/B 测试与因果推断实验室 · 方法学报告</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='22' fill='%232563EB'/><text x='50' y='70' font-size='44' text-anchor='middle' fill='white' font-family='sans-serif' font-weight='bold'>A/B</text></svg>">
<style>
:root {{ --bg:#F5F7FB; --card:#fff; --text:#1C2333; --muted:#7C879C; --border:#E3E8F2; --accent:#2563EB; --bad:#E5484D; --good:#10B981; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); line-height:1.75; }}
header {{ background:linear-gradient(135deg,#1E4FCC,#2563EB); color:#fff; padding:26px 22px 20px; border-radius:0 0 22px 22px; }}
header h1 {{ font-size:22px; }} header p {{ font-size:13px; opacity:.9; }}
main {{ max-width:900px; margin:0 auto; padding:18px 16px 50px; }}
.kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-top:-6px; }}
@media (max-width:640px) {{ .kpis {{ grid-template-columns:repeat(2,1fr); }} }}
.kpi {{ background:var(--card); border-radius:14px; box-shadow:0 2px 10px rgba(28,35,51,.07); padding:14px 10px; text-align:center; margin-top:14px; }}
.kpi b {{ display:block; font-size:22px; color:var(--accent); }}
.kpi span {{ font-size:12px; font-weight:700; }} .kpi em {{ display:block; font-size:11px; font-style:normal; color:var(--muted); }}
section {{ margin-top:22px; }}
.card {{ background:var(--card); border-radius:14px; box-shadow:0 2px 10px rgba(28,35,51,.07); padding:18px 20px; margin-top:12px; }}
h2 {{ font-size:17px; border-left:4px solid var(--accent); padding-left:10px; }}
h3 {{ font-size:15px; margin:14px 0 6px; }}
p {{ font-size:14px; margin-top:8px; }}
ul {{ font-size:14px; padding-left:20px; }} li {{ margin-top:4px; }}
img {{ max-width:100%; border-radius:10px; border:1px solid var(--border); margin-top:10px; }}
.figcap {{ font-size:12px; color:var(--muted); margin-top:4px; }}
table.tbl {{ width:100%; border-collapse:collapse; font-size:13px; margin-top:8px; }}
.tbl th, .tbl td {{ border-bottom:1px solid var(--border); padding:7px 10px; text-align:left; }}
.tbl th {{ color:var(--muted); font-weight:600; }}
.note {{ background:#EDF2FE; border:1px solid #D3DEFB; border-radius:10px; padding:10px 14px; font-size:13px; margin-top:10px; }}
.warn {{ background:#FEF2F2; border:1px solid #FBD5D5; border-radius:10px; padding:10px 14px; font-size:13px; margin-top:10px; }}
.steps {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; }}
.step {{ background:#E8EFFE; color:var(--accent); border-radius:999px; padding:5px 13px; font-size:12.5px; font-weight:600; }}
footer {{ text-align:center; font-size:12px; color:var(--muted); padding:26px 0 34px; }}
</style>
</head>
<body>
<header>
  <h1>A/B 测试与因果推断实验室</h1>
  <p>基于 10 万次级可复现模拟（随机种子固定）· 覆盖实验设计到收益估算的九个关键环节 · Python/SciPy</p>
</header>
<main>

<div class="kpis">{kpi}</div>

<section>
  <h2>1 · 实验设计：样本量与功效</h2>
  <div class="card">
    <p>业务场景：基线转化率 {M['p1'] * 100:.0f}%，希望检测 {M['lift'] * 100:.0f}% 相对提升（MDE = {M['p2'] * 100:.1f}% − {M['p1'] * 100:.0f}% = {(M['p2'] - M['p1']) * 100:.1f}pp），双侧 α = {M['alpha']}，目标功效 {80}%。</p>
    <img src="charts/01_sample_size.png" alt="样本量">
    <p><b>结论：</b>每组需要 <b>{M['n_per_arm']:,}</b> 个样本（合计 {M['n_total']:,}）。MDE 越小所需样本量呈平方级增长——把"想检测的提升"从 2pp 缩到 0.5pp，样本量不是 ×4 而是 ×16。实验设计的第一课：先算清楚你到底要检测多大的提升。</p>
  </div>
</section>

<section>
  <h2>2 · 单次实验与假设检验</h2>
  <div class="card">
    <img src="charts/02_single_test.png" alt="单次实验">
    <p>对照组 {d['x1']:,}/{M['n_per_arm']:,} 转化，实验组 {d['x2']:,}/{M['n_per_arm']:,}，两比例合并 z 检验：z = {d['z']:.2f}，提升 {d['diff_pp']:.2f}pp，95%CI [{d['ci_pp'][0]:.2f}, {d['ci_pp'][1]:.2f}]pp。</p>
    <div class="note">{verdict}</div>
  </div>
</section>

<section>
  <h2>3 · AA 检验：先证明你的实验平台是干净的</h2>
  <div class="card">
    <img src="charts/03_aa_test.png" alt="AA检验">
    <p><b>方法：</b>对<b>完全相同</b>的两个组做 {100000:,} 次模拟检验——AA 实验理应"不显著"。模拟结果：假阳性率 <b>{M['aa_false_positive']:.2f}%</b>，与理论 α = {M['alpha'] * 100:.0f}% 吻合；p 值分布均匀。</p>
    <p><b>业务含义：</b>AA 检验是实验平台健康检查的标准动作——分流是否随机、埋点是否对齐、是否有新鲜感效应，AA 显著就说明系统有偏差，此时一切 AB 结论都不可信。</p>
  </div>
</section>

<section>
  <h2>4 · 功效的模拟验证</h2>
  <div class="card">
    <p>同一场景 {100000:,} 次模拟（真实存在 {M['lift'] * 100:.0f}% 提升），实际检出显著的比例 = <b>{M['power_simulated']:.2f}%</b>，与样本量公式承诺的 80% 一致。功效不是理论空谈，它是可被模拟直接验证的频率性质。</p>
  </div>
</section>

<section>
  <h2>5 · 偷看（Peeking）：最常见的致命错误</h2>
  <div class="card">
    <img src="charts/04_peeking.png" alt="偷看">
    <p><b>方法：</b>AA 场景（两组无差异）下模拟 30 天实验：只在结束时检验 vs 每天看一次、任一天显著就宣布。</p>
    <table class="tbl">
      <thead><tr><th>监看频率</th><th>实际假阳性率</th></tr></thead>
      <tbody>{''.join(f'<tr><td>{esc(k)}</td><td>{v}%</td></tr>' for k, v in pf.items())}</tbody>
    </table>
    <div class="warn"><b>每天偷看让假阳性率从 5% 膨胀到 {M['peeking']['fp_daily_peek_30d']:.1f}%（{M['peeking']['inflation']} 倍）。</b>
    原因：多次检验取最小 p 值，等于变相放宽了显著性门槛。工业界的对策是固定样本量后一次性检验、使用序贯检验（如 SPRT/mSPRT）、或基于 CUPED 缩短实验周期。</div>
  </div>
</section>

<section>
  <h2>6 · 多重检验与 Bonferroni 校正</h2>
  <div class="card">
    <img src="charts/05_multiplicity.png" alt="多重检验">
    <p>一个实验看 {M['multitest']['m']} 个指标（全部真实无效）：至少一项误报的概率 = <b>{M['multitest']['fwer_uncorrected']:.1f}%</b>（理论 1−0.95⁵ = {M['multitest']['theory_uncorrected']:.1f}%）；Bonferroni 校正（α/m）后回落到 <b>{M['multitest']['fwer_bonferroni']:.1f}%</b>。看板上的"数字都在涨"很多时候只是多重检验的幻觉。</p>
  </div>
</section>

<section>
  <h2>7 · CUPED：用实验前数据给实验"降噪"</h2>
  <div class="card">
    <img src="charts/06_cuped.png" alt="CUPED">
    <p><b>方法：</b>调整后的指标 Y<sub>adj</sub> = Y − θ(X − E[X])，其中 X 为实验前同用户的行为数据，θ = cov(Y,X)/var(X)。当相关系数 ρ = {M['cuped']['rho']} 时，方差缩减 <b>{M['cuped']['var_reduction']}%</b>（方差降至原来的 {100 - M['cuped']['var_reduction']:.0f}%）。</p>
    <p><b>结果：</b>同样 {M['cuped']['n_per_arm']:,} 人/组，功效从 {M['cuped']['power_raw_same_n']:.0f}% 提升到 <b>{M['cuped']['power_cuped_same_n']:.0f}%</b>；等效方案是所需样本量降至 <b>{M['cuped']['n_needed_ratio']:.0f}%</b>——实验周期缩短 1/3 以上，这是大厂实验平台的标准配置（Microsoft/字节/美团均在用）。</p>
    <p class="figcap">实现细节：中心化必须用已知的总体期望（或历史均值），用本次实验样本均值做中心化会吸收处理效应引入偏差；两组必须独立采样——本次开发中这两个错误都真实踩过并在代码注释中记录。</p>
  </div>
</section>

<section>
  <h2>8 · 辛普森悖论：为什么必须看分层</h2>
  <div class="card">
    <img src="charts/07_simpson.png" alt="辛普森悖论">
    <p>构造场景：实验组流量意外偏向低转化人群（新用户占比 90% vs 对照组 10%）。结果：<b>新用户层</b> {M['simpson']['new_user'][0]}% → {M['simpson']['new_user'][1]}%（新版更好）、<b>老用户层</b> {M['simpson']['old_user'][0]}% → {M['simpson']['old_user'][1]}%（新版更好），但<b>混合后</b> {M['simpson']['aggregate'][0]}% → {M['simpson']['aggregate'][1]}%，结论整体反转。</p>
    <p><b>业务含义：</b>只看大盘会做出完全错误的上线路径决策；分流均衡性检查与分层分析是实验分析的必备动作。</p>
  </div>
</section>

<section>
  <h2>9 · 业务收益估算</h2>
  <div class="card">
    <img src="charts/08_business.png" alt="收益估算">
    <p>把统计结论翻译成业务语言：提升 {M['business']['lift_point']:.2f}pp × {M['business']['mau'] / 10000:.0f}0万 覆盖用户 × ¥{M['business']['arpu']:.0f} 月ARPU ≈ <b>¥{M['business']['monthly_gain'] / 10000:.0f} 万/月</b>；其 95% 区间由提升量的置信区间直接换算（¥{M['business']['monthly_gain_ci'][0] / 10000:.0f} ~ ¥{M['business']['monthly_gain_ci'][1] / 10000:.0f} 万）。<b>收益估算必须带区间</b>——点估计只是故事，区间才是决策依据。</p>
  </div>
</section>

<section>
  <h2>方法局限与改进方向</h2>
  <div class="card">
    <ul>
      <li>比例检验采用二项近似的解析 z 检验；真实平台常用基于 Delta method 的 t 检验处理比率指标。</li>
      <li>多重检验只演示了 Bonferroni；更优选择是 Holm 逐步校正或控制 FDR（Benjamini-Hochberg）。</li>
      <li>偷看问题的工业级解法是序贯检验（SPRT / mSPRT）与贝叶斯实验平台，本实验只量化了问题本身。</li>
      <li>CUPED 假设协变量在实验期间不受处理影响（pre-experiment data）；若用实验期协变量需谨慎（可能引入 post-treatment bias）。</li>
      <li>可扩展方向：非线性收益的弹性估算、实验溢出效应（network interference）、长期效应（novelty effect）检验。</li>
    </ul>
  </div>
</section>

<footer>全部结论基于固定随机种子的可复现模拟 · 代码见项目仓库 · Python/NumPy/SciPy/Matplotlib</footer>
</main>
</body>
</html>"""

(PUB / "index.html").write_text(html, encoding="utf-8")
print(f"报告已生成: {PUB / 'index.html'}")
