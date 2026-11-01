#!/usr/bin/env python3
"""
R1.2 错误复合模型 v2 - 公平对照版。

背景（判断①补充）：错误不只降低单步成功率，还**污染后续步骤的上下文/记忆**，
使错误计数呈「传染」分布——这是比简单二项分布更坏的情况。

实验目的：
    分离「独立失败」vs「复合失败」，用**公平对照**（相同完成判据）定量刻画
    错误复合比 p^k 更坏。核心假设：错误复合使错误计数**过度分散**
    （over-dispersion），即更可能 0 错误但也更可能大量错误（传染/级联），
    导致在相同错误阈值 θ 下，复合完成率 **低于** 独立完成率。

公平对照设计（关键修正）：
    两种模式使用**相同完成判据**：任务完成 = 错误计数 ≤ θ（阈值）。
    - independent：每步 p=p_step，错误相互独立，无传播。错误计数 ~ Binomial(k, 1-p)。
    - compound：每步 p=p_step，但错误发生后 p 下降（p_eff=p-contamination*errors），
      错误传播（正反馈）。错误计数过度分散。
    比较两种模式在相同 θ 下的 P(错误数 ≤ θ)。

    为什么这是公平的：之前版本复合允许「错误仍成功」而独立不允许，不公平。
    现在两者都用「错误数 ≤ θ」判完成，只改变「错误是否传播」这一维度。
    预期：θ≥1 时 compound P(≤θ) < independent P(≤θ)（传播使错误级联）。
    θ=0 时两者应相同 = p^k（公平性对照，验证对照有效）。

复现：
    python3 research/01-long-horizon-autonomy/experiments/r1_2_error_compound.py
"""

import json
import os
import random
from dataclasses import dataclass
from typing import Optional


# ==================== 模拟器 ====================

@dataclass
class ErrorContagionSimulator:
    """错误复合（传染）模拟器。

    两种模式（公平对照，相同完成判据「错误数 ≤ theta」）：
    - independent（error_contamination=0）：错误相互独立，无传播。
      错误计数 ~ Binomial(k, 1-p_step)。
    - compound（error_contamination>0）：错误传播——每发生一个错误，
      后续步骤成功率下降 p_eff = p_step - contamination * errors。
      这产生正反馈，错误计数过度分散（更可能 0 或大量错误）。
    """

    p_step: float = 0.98
    n_steps: int = 20
    error_contamination: float = 0.0  # >0 表示复合（传染）模式
    theta: int = 1  # 完成阈值：错误数 ≤ theta 即成功
    seed: Optional[int] = None

    def __post_init__(self):
        self.rng = random.Random(self.seed)

    def execute(self) -> int:
        """执行 k 步任务，返回错误计数。"""
        errors = 0
        for _ in range(self.n_steps):
            # 复合模式：错误传播，降低后续成功率
            if self.error_contamination > 0 and errors > 0:
                p_eff = max(0.0, self.p_step - self.error_contamination * errors)
            else:
                p_eff = self.p_step

            if self.rng.random() > p_eff:
                errors += 1

        return errors


# ==================== 实验 ====================

def run_compare(
    p_step: float = 0.98,
    steps_list: list[int] = [10, 20, 50],
    n_trials: int = 10000,
    contamination: float = 0.05,
    theta: int = 1,
    seed: int = 42,
) -> dict:
    """运行独立失败 vs 复合失败对比实验（公平对照）。"""
    results = []
    for k in steps_list:
        # 独立失败
        sim_ind = ErrorContagionSimulator(
            p_step=p_step, n_steps=k, error_contamination=0.0, theta=theta, seed=seed,
        )
        ind_errors = [sim_ind.execute() for _ in range(n_trials)]
        ind_rate = sum(1 for e in ind_errors if e <= theta) / n_trials

        # 复合失败（错误传播）
        sim_comp = ErrorContagionSimulator(
            p_step=p_step, n_steps=k, error_contamination=contamination, theta=theta, seed=seed,
        )
        comp_errors = [sim_comp.execute() for _ in range(n_trials)]
        comp_rate = sum(1 for e in comp_errors if e <= theta) / n_trials

        # 过度分散度量：错误数方差 / 均值（泊松=1，>1 过度分散）
        ind_mean = sum(ind_errors) / n_trials
        ind_var = sum((e - ind_mean) ** 2 for e in ind_errors) / n_trials
        comp_mean = sum(comp_errors) / n_trials
        comp_var = sum((e - comp_mean) ** 2 for e in comp_errors) / n_trials
        ind_dispersion = ind_var / ind_mean if ind_mean > 0 else 0
        comp_dispersion = comp_var / comp_mean if comp_mean > 0 else 0

        theoretical_pk = p_step ** k
        results.append({
            "steps": k,
            "theta": theta,
            "independent_rate": ind_rate,
            "compound_rate": comp_rate,
            "theoretical_pk": theoretical_pk,
            "compound_penalty": ind_rate - comp_rate,  # 复合比独立差多少（>0 表示复合更坏）
            "independent_dispersion": ind_dispersion,
            "compound_dispersion": comp_dispersion,
            "n_trials": n_trials,
        })

    return {
        "p_step": p_step,
        "contamination": contamination,
        "theta": theta,
        "results": results,
    }


def run_sensitivity(
    p_step: float = 0.98,
    k: int = 50,
    n_trials: int = 10000,
    seed: int = 42,
) -> dict:
    """参数敏感性：不同 contamination 对复合完成率的影响。"""
    sensitivity = []
    for contamination in [0.01, 0.02, 0.05, 0.10, 0.20]:
        e = run_compare(
            p_step=p_step, steps_list=[k], n_trials=n_trials,
            contamination=contamination, seed=seed,
        )
        r = e["results"][0]
        sensitivity.append({
            "contamination": contamination,
            "independent_rate": r["independent_rate"],
            "compound_rate": r["compound_rate"],
            "compound_penalty": r["compound_penalty"],
            "compound_dispersion": r["compound_dispersion"],
        })
    return {"k": k, "p_step": p_step, "sensitivity": sensitivity}


def main():
    """运行 R1.2 实验并落盘证据。"""
    print("=" * 70)
    print("R1.2 错误复合模型 v2 - 公平对照版")
    print("=" * 70)

    # 主对比实验（θ=1：允许 1 个错误，但传播使级联）
    print("\n[实验 1] 独立失败 vs 复合失败（公平对照 θ=1, contamination=0.05）")
    exp1 = run_compare(p_step=0.98, steps_list=[10, 20, 50], contamination=0.05, theta=1, n_trials=10000)
    for r in exp1["results"]:
        print(f"  k={r['steps']:3d}  独立={r['independent_rate']:.6f}  "
              f"复合={r['compound_rate']:.6f}  理论p^k={r['theoretical_pk']:.6f}  "
              f"惩罚={r['compound_penalty']:.6f}  "
              f"分散(独/复)={r['independent_dispersion']:.3f}/{r['compound_dispersion']:.3f}")

    # θ=0 对照（无容错，两者应相同 = p^k）
    print("\n[实验 2] 公平对照 θ=0（无容错，两者应相同 = p^k）")
    exp0 = run_compare(p_step=0.98, steps_list=[10, 20, 50], contamination=0.05, theta=0, n_trials=10000)
    for r in exp0["results"]:
        print(f"  k={r['steps']:3d}  独立={r['independent_rate']:.6f}  "
              f"复合={r['compound_rate']:.6f}  理论p^k={r['theoretical_pk']:.6f}")

    # 敏感性分析
    print("\n[实验 3] 敏感性：contamination 对复合完成率的影响 (k=50, θ=1)")
    exp2 = run_sensitivity(p_step=0.98, k=50, n_trials=10000)
    for s in exp2["sensitivity"]:
        print(f"  contamination={s['contamination']:.2f}  独立={s['independent_rate']:.6f}  "
              f"复合={s['compound_rate']:.6f}  惩罚={s['compound_penalty']:.6f}  "
              f"分散={s['compound_dispersion']:.3f}")

    # 落盘证据
    evidence = {
        "experiment": "R1.2 错误复合模型（公平对照版）",
        "description": "分离「独立失败」vs「复合失败」，用相同完成判据公平对照，验证错误复合比 p^k 更坏",
        "method": (
            "两种模式用相同完成判据「错误数 ≤ theta」。independent：错误独立无传播（Binomial）。"
            "compound：错误传播（p_eff=p-contamination*errors，正反馈），错误计数过度分散。"
            "比较两种模式 P(错误数≤theta)。θ=0 应相同=p^k（验证公平）；θ≥1 复合应更低（传播使级联）。"
        ),
        "main_comparison_theta1": exp1,
        "fairness_control_theta0": exp0,
        "sensitivity": exp2,
        "conclusion": (
            "若 θ=0 时独立=复合=p^k（公平性验证通过），且 θ≥1 时 compound_rate < independent_rate，"
            "则验证：错误复合比简单连乘更坏（错误传播导致错误级联，过度分散）。"
        ),
        "reproduce": "python3 research/01-long-horizon-autonomy/experiments/r1_2_error_compound.py",
    }

    evidence_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence")
    os.makedirs(evidence_dir, exist_ok=True)
    evidence_path = os.path.join(evidence_dir, "2026-11-01-r1_2-error-compound.json")
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 证据已落盘: {evidence_path}")


if __name__ == "__main__":
    main()
