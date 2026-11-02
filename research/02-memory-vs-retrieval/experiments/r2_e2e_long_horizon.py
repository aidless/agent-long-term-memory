#!/usr/bin/env python3
"""
R2-E2E 端到端长程记忆对照实验（真实 MemoryManager 系统）。

背景（目标核心要求）：
    第一阶段 R1.3 用抽象概率模型证明「记忆帮助长程（上下文不足时）但也可能损害
    （上下文足够时）」。本实验用**真实 MemoryManager 系统组件**做端到端对照，
    验证工程轨 `engineering/memory-system` 能否实际支撑长程任务。

实验目的：
    对照「有记忆（真实 MemoryManager 存储/检索）」vs「无记忆（仅上下文窗口）」
    的长程任务完成率。核心问题：真实记忆系统能否提升长程任务完成率？

设计（可证伪对照）：
    长程任务 = k 步，每步需要「先前某一步建立的事实」。
    - no_memory（对照组）：事实仅存在于上下文窗口（容量 C）。上下文满后
      早期事实被逐出 → 需要早期事实的步骤失败。
    - with_memory（实验组）：事实通过 MemoryManager.add_semantic() 存入，
      需要时 MemoryManager.search() 检索。真实检索命中率由系统决定。

    与 R1.3 的关键区别：
        R1.3 用抽象概率模型（memory_hit_rate/poison 参数）。
        本实验用**真实 MemoryManager 的存储/检索逻辑**（不注入人工参数），
        验证真实系统能否支撑长程任务。

    每步单步成功率 p（模拟 agent 单步失败）：无记忆组失败 → 该步失败；
    有记忆组失败 → 该步失败（但已存事实仍保留）。

复现：
    python3 research/02-memory-vs-retrieval/experiments/r2_e2e_long_horizon.py
"""

import json
import os
import random
import sys
from dataclasses import dataclass
from typing import Optional

# 导入真实 MemoryManager（工程轨）
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "engineering", "memory-system",
))
from manager.memory_manager import MemoryManager


@dataclass
class E2ELongHorizonAgent:
    """端到端长程任务 agent（真实 MemoryManager 系统）。"""

    n_steps: int = 20
    context_capacity: int = 5  # 无记忆组上下文窗口容量
    use_memory: bool = False  # True=真实 MemoryManager，False=仅上下文
    step_success_rate: float = 0.98  # 单步成功率 p
    seed: Optional[int] = None

    def __post_init__(self):
        self.rng = random.Random(self.seed)
        # use_memory 时创建真实 MemoryManager（内存模式，不落盘）
        self.manager = None
        if self.use_memory:
            self.manager = MemoryManager()

    def clear_memory(self):
        """清空记忆（实验隔离：每次 trial 独立）。"""
        if self.manager:
            self.manager.clear_all()

    def _fact_key(self, j: int) -> str:
        """生成第 j 步事实的唯一检索键。"""
        return f"fact_{j}"

    def execute(self) -> bool:
        """执行 k 步任务，返回是否全部成功。

        每步需要「先前某一步建立的事实」。
        - no_memory：仅上下文窗口。事实在上下文 iff 距离 ≤ C 步。
        - with_memory：事实通过真实 MemoryManager 存入并检索。
        """
        # 当前上下文窗口（无记忆组）：list of (step_index, fact_content)
        context = []

        for i in range(1, self.n_steps + 1):
            # 第一步：建立第一个事实（无需先前事实）
            if i == 1:
                if self.use_memory:
                    self.manager.add_semantic(
                        self._fact_key(i),
                        importance=0.8,
                        metadata={"step": i},
                    )
                else:
                    context.append((i, self._fact_key(i)))
                continue

            # 需要先前某一步的事实（模拟「需要先前知识」）
            need_j = self.rng.randint(1, i - 1)
            fact_key = self._fact_key(need_j)

            # 1. 单步失败（agent 能力限制）
            if self.rng.random() > self.step_success_rate:
                return False  # 该步失败 → 任务失败

            # 2. 获取所需事实
            if self.use_memory:
                # 真实 MemoryManager 检索（按事实键查询）
                results = self.manager.search(
                    fact_key,
                    memory_types=["semantic"],
                    top_k=5,
                )
                if not results:
                    return False  # 检索失败 → 事实不可得 → 步骤失败
                # 检索成功，但需确认返回的是正确事实（内容含 fact_{need_j}）
                hit = False
                for sr in results:
                    if self._fact_key(need_j) in sr.memory.content:
                        hit = True
                        break
                if not hit:
                    return False  # 返回错误事实
            else:
                # 无记忆：事实在上下文 iff 年龄 ≤ C
                # 从 context 找该事实
                found = any(
                    step == need_j for step, _ in context
                    if i - step <= self.context_capacity
                )
                if not found:
                    return False  # 事实被逐出上下文 → 步骤失败

            # 3. 该步成功，建立/更新事实
            if self.use_memory:
                self.manager.add_semantic(
                    self._fact_key(i),
                    importance=0.8,
                    metadata={"step": i},
                )
            else:
                context.append((i, self._fact_key(i)))

        return True


def run_compare(
    n_steps_list: list[int] = [10, 20, 50],
    context_capacity: int = 5,
    step_success_rate: float = 0.98,
    n_trials: int = 2000,
    seed: int = 42,
) -> dict:
    """运行无记忆 vs 有记忆（真实系统）端到端对照。"""
    results = []
    for k in n_steps_list:
        # 无记忆（仅上下文）
        no_success = 0
        for t in range(n_trials):
            agent = E2ELongHorizonAgent(
                n_steps=k, context_capacity=context_capacity,
                use_memory=False, step_success_rate=step_success_rate,
                seed=seed + t,
            )
            if agent.execute():
                no_success += 1
        no_rate = no_success / n_trials

        # 有记忆（真实 MemoryManager，复用单实例，每 trial 清空）
        mem_agent = E2ELongHorizonAgent(
            n_steps=k, context_capacity=context_capacity,
            use_memory=True, step_success_rate=step_success_rate,
            seed=seed,
        )
        yes_success = 0
        for t in range(n_trials):
            mem_agent.clear_memory()
            if mem_agent.execute():
                yes_success += 1
        yes_rate = yes_success / n_trials

        results.append({
            "steps": k,
            "no_memory_rate": no_rate,
            "with_memory_rate": yes_rate,
            "memory_benefit": yes_rate - no_rate,
            "n_trials": n_trials,
        })

    return {
        "context_capacity": context_capacity,
        "step_success_rate": step_success_rate,
        "results": results,
    }


def run_capacity_sensitivity(
    n_steps: int = 20,
    step_success_rate: float = 0.98,
    n_trials: int = 2000,
    seed: int = 42,
) -> dict:
    """上下文容量敏感性：不同 C 值下记忆收益（真实系统）。"""
    sensitivity = []
    for C in [3, 5, 10, 20]:
        e = run_compare(
            n_steps_list=[n_steps], context_capacity=C,
            step_success_rate=step_success_rate,
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
    """运行 R2-E2E 实验并落盘证据。"""
    print("=" * 70)
    print("R2-E2E 端到端长程记忆对照（真实 MemoryManager 系统）")
    print("=" * 70)

    # 主对照实验（C=5, p=0.98）
    print("\n[实验 1] 无记忆 vs 有记忆（真实系统，C=5, 单步成功率=0.98）")
    exp1 = run_compare(
        n_steps_list=[10, 20, 50],
        context_capacity=5, step_success_rate=0.98, n_trials=2000,
    )
    for r in exp1["results"]:
        print(f"  k={r['steps']:3d}  无记忆={r['no_memory_rate']:.6f}  "
              f"有记忆={r['with_memory_rate']:.6f}  收益={r['memory_benefit']:.6f}")

    # 上下文容量敏感性
    print("\n[实验 2] 上下文容量敏感性：不同 C 下记忆收益（真实系统, k=20）")
    exp2 = run_capacity_sensitivity(n_steps=20, step_success_rate=0.98, n_trials=2000)
    for s in exp2["sensitivity"]:
        print(f"  C={s['context_capacity']:3d}  无记忆={s['no_memory_rate']:.6f}  "
              f"有记忆={s['with_memory_rate']:.6f}  收益={s['memory_benefit']:.6f}")

    # 落盘证据
    evidence = {
        "experiment": "R2-E2E 端到端长程记忆对照（真实 MemoryManager 系统）",
        "description": (
            "对照「无记忆（仅上下文窗口）」vs「有记忆（真实 MemoryManager 存储/检索）」"
            "的长程任务完成率，验证工程轨记忆系统能否实际支撑长程任务"
        ),
        "method": (
            "长程任务=k 步，每步需要先前某一步建立的事实。no_memory：事实仅存在于上下文窗口（容量 C），"
            "超龄被逐出导致失败。with_memory：事实通过 MemoryManager.add_semantic() 存入，"
            "需要时 MemoryManager.search() 检索（真实检索逻辑，不注入人工参数）。"
            "每步单步成功率 p=0.98。比较两种完成率。"
        ),
        "key_difference_from_r1_3": (
            "R1.3 用抽象概率模型（memory_hit_rate/poison 参数）；本实验用真实 MemoryManager 的"
            "存储/检索逻辑，不注入人工检索参数——验证真实系统组件能否支撑长程任务。"
        ),
        "main_comparison": exp1,
        "capacity_sensitivity": exp2,
        "reproduce": "python3 research/02-memory-vs-retrieval/experiments/r2_e2e_long_horizon.py",
    }

    evidence_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence")
    os.makedirs(evidence_dir, exist_ok=True)
    evidence_path = os.path.join(evidence_dir, "2026-11-01-r2_e2e-long-horizon.json")
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 证据已落盘: {evidence_path}")


if __name__ == "__main__":
    main()
