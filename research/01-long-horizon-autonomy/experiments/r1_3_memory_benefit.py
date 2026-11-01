#!/usr/bin/env python3
"""
R1.3 记忆支撑长程 - 机械对照实验（不依赖真实 LLM）。

背景（判断① + 文献[1] 发现 (5)）：
    - 长程任务完成率随步数指数衰减（R1.1 已证）。
    - 错误复合比 p^k 更坏（R1.2 已证，错误传播导致级联）。
    - 文献[1] 发现 (5)：记忆脚手架**普遍损害**长时程性能（全部 10 模型）。
      这提示：记忆系统本身可能引入错误（存错/检错/整合错），抵消其收益。

实验目的：
    机械对照「无记忆（仅上下文窗口）」vs「有记忆（长期记忆系统）」的
    长程任务完成率。核心问题：记忆到底**帮助**还是**损害**长程任务？

设计（可证伪对照）：
    长程任务 = k 步，每步需要「先前某一步建立的事实」。
    - no_memory（对照组）：事实仅存在于上下文窗口（容量 C）。上下文满后
      早期事实被逐出 → 需要早期事实的步骤失败。
    - with_memory（实验组）：事实存入长期记忆系统，跨步持久。检索命中率 r。
      但记忆系统可能引入「污染」：返回错误事实的概率 poison（呼应文献[1]）。

    关键参数：
        k      = 任务步数（10/20/50）
        C      = 上下文窗口容量（5/10）
        r      = 记忆检索命中率（0.90/0.95/0.98）
        poison = 记忆污染概率（0/0.01/0.02/0.05）— 返回错误事实导致步骤失败

    核心对比（同参数下）：
        no_memory 完成率 vs with_memory 完成率
        - 若 with_memory > no_memory：记忆**帮助**长程（检索收益 > 污染代价）
        - 若 with_memory < no_memory：记忆**损害**长程（污染代价 > 检索收益，呼应文献[1]）

复现：
    python3 research/01-long-horizon-autonomy/experiments/r1_3_memory_benefit.py
"""

import json
import os
import random
from dataclasses import dataclass
from typing import Optional


@dataclass
class LongHorizonAgent:
    """长程任务 agent 模拟器（机械对照）。"""

    n_steps: int = 20
    context_capacity: int = 5  # 上下文窗口容量
    memory_hit_rate: float = 0.95  # 记忆检索命中率（with_memory 模式）
    memory_poison: float = 0.0  # 记忆污染概率（返回错误事实导致步骤失败）
    use_memory: bool = False  # True=有记忆系统，False=仅上下文
    seed: Optional[int] = None

    def __post_init__(self):
        self.rng = random.Random(self.seed)

    def execute(self) -> bool:
        """执行 k 步任务，返回是否全部成功。

        每步需要「先前某一步建立的事实」。
        - no_memory：仅上下文窗口。事实在上下文 iff 距离 ≤ C 步。
        - with_memory：事实存入长期记忆，跨步持久。检索命中率 r，
          但有污染概率 poison（返回错误事实 → 步骤失败）。
        """
        # 事实建立时间表：fact[j] 在步骤 j 建立
        # 步骤 i 需要 fact[j]，其中 j 在 1..i-1 中随机选择（模拟「需要先前事实」）
        # 事实 j 在步骤 i 是否可得：
        #   no_memory: i - j <= context_capacity（在上下文窗口内）
        #   with_memory: 记忆命中（r），但有污染风险（poison）

        for i in range(1, self.n_steps + 1):
            # 需要先前某一步的事实（i>1 才有先前步骤）
            if i == 1:
                # 第一步无需先前事实（建立第一个事实）
                continue
            need_j = self.rng.randint(1, i - 1)  # 需要 fact[j]
            age = i - need_j  # 事实年龄（步数差）

            if self.use_memory:
                # 记忆模式：检索命中（r），但污染风险
                if self.rng.random() > self.memory_hit_rate:
                    # 检索失败 → 事实不可得 → 步骤失败
                    return False
                if self.rng.random() < self.memory_poison:
                    # 污染：返回错误事实 → 步骤失败
                    return False
                # 检索成功且未污染 → 步骤成功
            else:
                # 上下文模式：事实可得 iff 年龄 ≤ C
                if age > self.context_capacity:
                    # 事实被逐出上下文 → 步骤失败
                    return False

        return True


def run_compare(
    n_steps_list: list[int] = [10, 20, 50],
    context_capacity: int = 5,
    memory_hit_rate: float = 0.95,
    memory_poison: float = 0.0,
    n_trials: int = 10000,
    seed: int = 42,
) -> dict:
    """运行无记忆 vs 有记忆对照实验。"""
    results = []
    for k in n_steps_list:
        # 无记忆（仅上下文）
        sim_no = LongHorizonAgent(
            n_steps=k, context_capacity=context_capacity,
            memory_hit_rate=memory_hit_rate, memory_poison=memory_poison,
            use_memory=False, seed=seed,
        )
        no_success = sum(1 for _ in range(n_trials) if sim_no.execute())
        no_rate = no_success / n_trials

        # 有记忆
        sim_yes = LongHorizonAgent(
            n_steps=k, context_capacity=context_capacity,
            memory_hit_rate=memory_hit_rate, memory_poison=memory_poison,
            use_memory=True, seed=seed,
        )
        yes_success = sum(1 for _ in range(n_trials) if sim_yes.execute())
        yes_rate = yes_success / n_trials

        results.append({
            "steps": k,
            "no_memory_rate": no_rate,
            "with_memory_rate": yes_rate,
            "memory_benefit": yes_rate - no_rate,  # >0 记忆帮助，<0 记忆损害
            "n_trials": n_trials,
        })

    return {
        "context_capacity": context_capacity,
        "memory_hit_rate": memory_hit_rate,
        "memory_poison": memory_poison,
        "results": results,
    }


def run_poison_sensitivity(
    n_steps: int = 20,
    context_capacity: int = 5,
    memory_hit_rate: float = 0.95,
    n_trials: int = 10000,
    seed: int = 42,
) -> dict:
    """污染敏感性：不同 poison 值对记忆收益的影响。"""
    sensitivity = []
    for poison in [0.0, 0.01, 0.02, 0.05, 0.10]:
        e = run_compare(
            n_steps_list=[n_steps], context_capacity=context_capacity,
            memory_hit_rate=memory_hit_rate, memory_poison=poison,
            n_trials=n_trials, seed=seed,
        )
        r = e["results"][0]
        sensitivity.append({
            "poison": poison,
            "no_memory_rate": r["no_memory_rate"],
            "with_memory_rate": r["with_memory_rate"],
            "memory_benefit": r["memory_benefit"],
        })
    return {"n_steps": n_steps, "sensitivity": sensitivity}


def run_capacity_sensitivity(
    n_steps: int = 20,
    memory_hit_rate: float = 0.95,
    memory_poison: float = 0.0,
    n_trials: int = 10000,
    seed: int = 42,
) -> dict:
    """上下文容量敏感性：不同 C 值下记忆收益。"""
    sensitivity = []
    for C in [3, 5, 10, 20]:
        e = run_compare(
            n_steps_list=[n_steps], context_capacity=C,
            memory_hit_rate=memory_hit_rate, memory_poison=memory_poison,
            n_trials=n_trials, seed=seed,
        )
        r = e["results"][0]
        sensitivity.append({
            "context_capacity": C,
            "no_memory_rate": r["no_memory_rate"],
            "with_memory_rate": r["with_memory_rate"],
            "memory_benefit": r["memory_benefit"],
        })
    return {"n_steps": n_steps, "sensitivity": sensitivity}


def main():
    """运行 R1.3 实验并落盘证据。"""
    print("=" * 70)
    print("R1.3 记忆支撑长程 - 机械对照实验")
    print("=" * 70)

    # 主对照实验（C=5, r=0.95, poison=0）
    print("\n[实验 1] 无记忆 vs 有记忆（C=5, 检索命中率=0.95, 无污染）")
    exp1 = run_compare(
        n_steps_list=[10, 20, 50],
        context_capacity=5, memory_hit_rate=0.95, memory_poison=0.0, n_trials=10000,
    )
    for r in exp1["results"]:
        print(f"  k={r['steps']:3d}  无记忆={r['no_memory_rate']:.6f}  "
              f"有记忆={r['with_memory_rate']:.6f}  收益={r['memory_benefit']:.6f}")

    # 污染敏感性（记忆是否可能损害）
    print("\n[实验 2] 污染敏感性：记忆污染对收益的影响 (k=20, C=5, r=0.95)")
    exp2 = run_poison_sensitivity(n_steps=20, context_capacity=5, memory_hit_rate=0.95, n_trials=10000)
    for s in exp2["sensitivity"]:
        print(f"  poison={s['poison']:.2f}  无记忆={s['no_memory_rate']:.6f}  "
              f"有记忆={s['with_memory_rate']:.6f}  收益={s['memory_benefit']:.6f}")

    # 上下文容量敏感性
    print("\n[实验 3] 上下文容量敏感性：不同 C 下记忆收益 (k=20, r=0.95, 无污染)")
    exp3 = run_capacity_sensitivity(n_steps=20, memory_hit_rate=0.95, memory_poison=0.0, n_trials=10000)
    for s in exp3["sensitivity"]:
        print(f"  C={s['context_capacity']:3d}  无记忆={s['no_memory_rate']:.6f}  "
              f"有记忆={s['with_memory_rate']:.6f}  收益={s['memory_benefit']:.6f}")

    # 落盘证据
    evidence = {
        "experiment": "R1.3 记忆支撑长程（机械对照）",
        "description": "对照「无记忆（仅上下文窗口）」vs「有记忆（长期记忆系统）」的长程任务完成率",
        "method": (
            "长程任务=k 步，每步需要先前某一步建立的事实。no_memory：事实仅存在于上下文窗口（容量 C），"
            "早期事实被逐出导致失败。with_memory：事实存入长期记忆跨步持久，检索命中率 r，但有污染概率 poison"
            "（返回错误事实导致步骤失败）。比较两种完成率。核心问题：记忆帮助还是损害长程任务？"
        ),
        "main_comparison": exp1,
        "poison_sensitivity": exp2,
        "capacity_sensitivity": exp3,
        "conclusion": (
            "若 with_memory > no_memory：记忆帮助长程（检索收益 > 污染代价）。"
            "若 with_memory < no_memory：记忆损害长程（污染代价 > 检索收益，呼应文献[1] 发现 (5)）。"
        ),
        "reproduce": "python3 research/01-long-horizon-autonomy/experiments/r1_3_memory_benefit.py",
    }

    evidence_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence")
    os.makedirs(evidence_dir, exist_ok=True)
    evidence_path = os.path.join(evidence_dir, "2026-11-01-r1_3-memory-benefit.json")
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 证据已落盘: {evidence_path}")


if __name__ == "__main__":
    main()
