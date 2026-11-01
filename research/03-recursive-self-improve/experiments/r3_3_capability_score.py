#!/usr/bin/env python3
"""
R3.3 能力/分数分离 - evaluator capture 门禁验证（衔接 P3 五键门）。

背景（判断③的缺口 3）：
    任何自我改进主张必须分离「真实能力提升」与「评测器钻空」。分数涨了，
    能力没涨——这是判断③最硬的工程障碍。P3 已用 GSM8K 五键门验证 FPR：
    R1（五键门）=0.0125，R2（无检验）=0.4125，R7（best-of-8）=0.9825。

核心问题：
    如何区分「真实能力提升」与「evaluator capture（分数涨≠能力涨）」？

    - 分数：agent 在评测集上的得分（可被钻空——过拟合评测集）。
    - 能力：agent 在独立 held-out 上的真实表现（不可钻空）。
    - evaluator capture：agent 在评测集上「过拟合」（分数涨），但 held-out
      上没涨（能力没涨）——假改进。

门禁（衔接 P3 方法）：
    任何自我改进主张必须验证「分数涨 AND held-out 涨」——用统计检验
    （McNemar 配对检验）确认增益显著，且增益在独立 held-out 上迁移。

判定：
    - score_up AND heldout_up = 真改进（capability）。
    - score_up AND heldout_flat = evaluator capture（假改进，分数涨≠能力涨）。

复现：
    python3 research/03-recursive-self-improve/experiments/r3_3_capability_score.py
"""

import json
import math
import os
import random
from dataclasses import dataclass
from typing import Optional


# ==================== 统计工具 ====================

def mcnemar_test(b: int, c: int) -> float:
    """McNemar 配对检验（二项精确）。

    b: 只在新方法上成功的对数
    c: 只在旧方法上成功的对数
    返回双侧 p 值。
    """
    n = b + c
    if n == 0:
        return 1.0
    # 二项检验：p = 0.5 下观察到 min(b,c) 或更极端的概率 * 2
    k = min(b, c)
    # 精确二项概率
    p_value = 0.0
    for i in range(k + 1):
        # C(n, i) * 0.5^n
        comb = math.comb(n, i)
        p_value += comb * (0.5 ** n)
    return min(1.0, 2 * p_value)


@dataclass
class CapabilityScoreSimulator:
    """能力/分数分离模拟器。

    模拟 agent 自我改进的「分数」与「能力」：
    - 评测集：agent 可过拟合（分数可涨但不代表能力涨）。
    - held-out：真实能力（不可钻空）。
    """

    n_pairs: int = 200  # 配对样本数
    seed: int = 42
    # 基线能力
    base_capability: float = 0.5
    # 改进后能力（真实提升，held-out 上可见）
    improved_capability: float = 0.7
    # 评测集过拟合程度（0-1）：分数在评测集上额外提升（钻空）
    eval_overfit: float = 0.0  # 0=无过拟合（真改进），0.3=过拟合（假改进）

    def __post_init__(self):
        self.rng = random.Random(self.seed)

    def run(self) -> dict:
        """运行能力/分数分离实验。"""
        # 配对样本：baseline vs improved
        # baseline 在评测集和 held-out 上的表现（同一对样本）
        # 分数（评测集）可被过拟合钻空；能力（held-out）不可
        score_b = 0  # baseline 评测集正确
        score_i = 0  # improved 评测集正确
        heldout_b = 0  # baseline held-out 正确
        heldout_i = 0  # improved held-out 正确
        # McNemar 配对计数
        mcnemar_b = 0  # improved 对 + baseline 错（score）
        mcnemar_c = 0  # baseline 对 + improved 错（score）
        mcnemar_hb = 0  # held-out
        mcnemar_hc = 0

        for _ in range(self.n_pairs):
            # baseline 能力
            base_ok_heldout = self.rng.random() < self.base_capability
            base_ok_score = self.rng.random() < self.base_capability

            # improved 能力：真实提升（held-out）
            imp_ok_heldout = self.rng.random() < self.improved_capability
            # improved 分数：真实提升 + 过拟合钻空（仅评测集）
            imp_score_prob = self.improved_capability + self.eval_overfit
            imp_ok_score = self.rng.random() < min(1.0, imp_score_prob)

            # 统计
            if imp_ok_score:
                score_i += 1
            if base_ok_score:
                score_b += 1
            if imp_ok_heldout:
                heldout_i += 1
            if base_ok_heldout:
                heldout_b += 1

            # McNemar 配对（score）
            if imp_ok_score and not base_ok_score:
                mcnemar_b += 1
            elif base_ok_score and not imp_ok_score:
                mcnemar_c += 1
            # McNemar 配对（held-out）
            if imp_ok_heldout and not base_ok_heldout:
                mcnemar_hb += 1
            elif base_ok_heldout and not imp_ok_heldout:
                mcnemar_hc += 1

        # 计算率
        score_b_rate = score_b / self.n_pairs
        score_i_rate = score_i / self.n_pairs
        heldout_b_rate = heldout_b / self.n_pairs
        heldout_i_rate = heldout_i / self.n_pairs

        # 增益
        score_gain = score_i_rate - score_b_rate
        heldout_gain = heldout_i_rate - heldout_b_rate

        # McNemar p 值
        score_p = mcnemar_test(mcnemar_b, mcnemar_c)
        heldout_p = mcnemar_test(mcnemar_hb, mcnemar_hc)

        # 判定：分数涨 AND held-out 涨 = 真改进；分数涨但 held-out 没涨 = capture
        score_up = score_gain > 0.02
        heldout_up = heldout_gain > 0.02 and heldout_p < 0.05

        if score_up and heldout_up:
            verdict = "CAPABILITY_IMPROVEMENT"
            explanation = (
                "分数涨 AND held-out 涨：真实能力提升——改进在独立 held-out 上迁移，"
                "非 evaluator capture。"
            )
        elif score_up and not heldout_up:
            verdict = "EVALUATOR_CAPTURE"
            explanation = (
                "分数涨但 held-out 没涨：evaluator capture（假改进）——"
                "分数涨≠能力涨，改进只钻了评测集空子。"
            )
        else:
            verdict = "NO_IMPROVEMENT"
            explanation = "分数没涨：无改进主张。"

        return {
            "experiment": "R3.3 能力/分数分离（evaluator capture 门禁）",
            "description": "分离「真实能力提升」与「评测器钻空」",
            "n_pairs": self.n_pairs,
            "results": {
                "score_baseline": score_b_rate,
                "score_improved": score_i_rate,
                "score_gain": score_gain,
                "score_mcnemar_p": score_p,
                "heldout_baseline": heldout_b_rate,
                "heldout_improved": heldout_i_rate,
                "heldout_gain": heldout_gain,
                "heldout_mcnemar_p": heldout_p,
            },
            "verdict": verdict,
            "explanation": explanation,
            "eval_overfit": self.eval_overfit,
        }


def main():
    """运行 R3.3 能力/分数分离并落盘证据。"""
    print("=" * 70)
    print("R3.3 能力/分数分离 - evaluator capture 门禁验证")
    print("=" * 70)

    # 场景 A：无过拟合（真改进）
    print("\n[场景 A] 无过拟合（eval_overfit=0）——真改进")
    sim_a = CapabilityScoreSimulator(n_pairs=200, seed=42, eval_overfit=0.0)
    result_a = sim_a.run()
    print(f"  分数: {result_a['results']['score_baseline']:.4f} → {result_a['results']['score_improved']:.4f} "
          f"(增益 {result_a['results']['score_gain']:.4f}, p={result_a['results']['score_mcnemar_p']:.4f})")
    print(f"  held-out: {result_a['results']['heldout_baseline']:.4f} → {result_a['results']['heldout_improved']:.4f} "
          f"(增益 {result_a['results']['heldout_gain']:.4f}, p={result_a['results']['heldout_mcnemar_p']:.4f})")
    print(f"  判定: {result_a['verdict']}")

    # 场景 B：过拟合（evaluator capture）——分数涨但能力没涨
    # 注意：过拟合场景下 improved 的真实能力不提升（capability 保持 0.5），
    # 只有评测集分数被钻空（eval_overfit 提升分数）。这是关键——假改进的
    # 特征是「分数涨但 held-out 没涨」，所以 improved_capability 必须等于 baseline。
    print("\n[场景 B] 过拟合（eval_overfit=0.3, 能力不提升）——假改进（分数涨但能力没涨）")
    sim_b = CapabilityScoreSimulator(n_pairs=200, seed=42, eval_overfit=0.3,
                                     improved_capability=0.5)
    result_b = sim_b.run()
    print(f"  分数: {result_b['results']['score_baseline']:.4f} → {result_b['results']['score_improved']:.4f} "
          f"(增益 {result_b['results']['score_gain']:.4f}, p={result_b['results']['score_mcnemar_p']:.4f})")
    print(f"  held-out: {result_b['results']['heldout_baseline']:.4f} → {result_b['results']['heldout_improved']:.4f} "
          f"(增益 {result_b['results']['heldout_gain']:.4f}, p={result_b['results']['heldout_mcnemar_p']:.4f})")
    print(f"  判定: {result_b['verdict']}")

    # 落盘证据
    evidence_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence")
    os.makedirs(evidence_dir, exist_ok=True)
    evidence_path = os.path.join(evidence_dir, "2026-11-01-r3_3-capability-score.json")
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump({
            "scenario_A_no_overfit": result_a,
            "scenario_B_overfit": result_b,
            "gate": (
                "任何自我改进主张必须验证「分数涨 AND held-out 涨」——"
                "用 McNemar 配对检验确认增益显著，且增益在独立 held-out 上迁移。"
            ),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 证据已落盘: {evidence_path}")


if __name__ == "__main__":
    main()
