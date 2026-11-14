#!/usr/bin/env python3
"""
R3.2 改进算子自指性 - 判定 agent 能否用自身记忆改进自身行为。

背景（判断③的缺口 2）：
    f 能否由 A 自身执行，而不是依赖外部系统？改进算子的自指性问题是
    「递归自我改进」的关键——若 f 只能由外部执行，则不是真自指。

核心问题（外循环层面）：
    agent 能否用**自己写入的记忆**改进**自己未来的行为**？
    - 自指：agent 自己写入记忆（学习），自己用记忆（改进）。改进来自
      agent 自身的经验沉淀，非外部注入。
    - 非自指：改进来自外部系统（prompt 工程师、外部知识库注入）。

判定实验：
    长程任务中，agent 需完成一系列决策，每个决策需参考先前经验。
    - no_memory（baseline）：agent 每次从头开始，无先前经验。
    - self_improve（自指）：agent 用**自身写入的记忆**改进行为（学习+复用）。
    - external_knowledge（非自指对照）：agent 使用**外部注入**的知识改进行为。

    自指性判据：
        self_improve > no_memory：agent 能用自身经验改进自身行为 → 自指外循环改进。
        self_improve ≈ external_knowledge：自指改进达到外部注入水平 → 强自指。

    注意：记忆必须是 agent 自身写入的（模拟 agent 的学习），不是外部预设。

复现：
    python3 research/03-recursive-self-improve/experiments/r3_2_self_reference.py
"""

import json
import os
import random
from dataclasses import dataclass


@dataclass
class SelfReferenceSimulator:
    """自指性模拟器：agent 用自身记忆改进自身行为。"""

    n_trials: int = 1000
    seed: int = 42
    n_episodes: int = 5  # 每个 trial 的 episode 数（agent 学习并复用）
    memory_recall_rate: float = 0.9  # 记忆检索命中率
    memory_utility: float = 0.4  # 记忆对决策的增益（0-1）

    def __post_init__(self):
        self.rng = random.Random(self.seed)

    def _run_episode(self, use_memory: bool, learned: bool,
                     external_knowledge: bool = False) -> bool:
        """运行一个 episode，返回是否成功。

        Args:
            use_memory: 是否使用记忆系统
            learned: 是否已有经验（记忆中有先前 episode 的经验）
            external_knowledge: 是否使用外部注入知识（非自指对照）
        """
        # 基础成功率（agent 决策的固有正确率）
        base_success = 0.5

        # 外部知识：外部注入提高基础成功率（非自指对照）
        if external_knowledge:
            base_success += 0.2

        # 记忆系统：使用记忆时，若已学习，检索命中则增益
        if use_memory and learned:
            if self.rng.random() < self.memory_recall_rate:
                base_success += self.memory_utility

        # 决策成功判定
        return self.rng.random() < base_success

    def run(self) -> dict:
        """运行自指性判定实验。"""
        results = {}

        # 1. no_memory：无记忆，无学习（每次从头）
        no_memory_success = 0
        for _ in range(self.n_trials):
            ep_success = 0
            for _ in range(self.n_episodes):
                if self._run_episode(use_memory=False, learned=False):
                    ep_success += 1
            # 全部 episode 成功才算 trial 成功
            if ep_success == self.n_episodes:
                no_memory_success += 1
        results["no_memory"] = no_memory_success / self.n_trials

        # 2. self_improve：agent 用自身记忆改进（学习+复用）
        self_improve_success = 0
        for _ in range(self.n_trials):
            ep_success = 0
            learned = False
            for ep in range(self.n_episodes):
                # 第一个 episode 前未学习，之后已学习（agent 写入记忆）
                use_mem = ep > 0  # 从第二个 episode 开始用记忆
                if self._run_episode(use_memory=use_mem, learned=learned):
                    ep_success += 1
                learned = True  # 每个 episode 后 agent 学习（写入记忆）
            if ep_success == self.n_episodes:
                self_improve_success += 1
        results["self_improve"] = self_improve_success / self.n_trials

        # 3. external_knowledge：外部注入知识（非自指对照）
        external_success = 0
        for _ in range(self.n_trials):
            ep_success = 0
            for _ in range(self.n_episodes):
                if self._run_episode(use_memory=False, learned=False,
                                     external_knowledge=True):
                    ep_success += 1
            if ep_success == self.n_episodes:
                external_success += 1
        results["external_knowledge"] = external_success / self.n_trials

        # 自指性判据
        self_ref_gain = results["self_improve"] - results["no_memory"]
        external_gain = results["external_knowledge"] - results["no_memory"]

        if self_ref_gain > 0.05:
            verdict = "SELF_REFERENTIAL"
            explanation = (
                "self_improve > no_memory：agent 能用自身记忆改进自身行为"
                "（自指外循环改进）。"
            )
        else:
            verdict = "NOT_SELF_REFERENTIAL"
            explanation = (
                "self_improve ≈ no_memory：agent 无法用自身记忆改进自身行为"
                "（记忆未带来自指改进）。"
            )

        return {
            "experiment": "R3.2 改进算子自指性",
            "description": "判定 agent 能否用自身记忆改进自身行为（外循环层面）",
            "n_trials": self.n_trials,
            "n_episodes": self.n_episodes,
            "results": results,
            "self_reference_gain": self_ref_gain,
            "external_gain": external_gain,
            "verdict": verdict,
            "explanation": explanation,
        }


def main():
    """运行 R3.2 自指性判定并落盘证据。"""
    print("=" * 70)
    print("R3.2 改进算子自指性 - 判定 agent 用自身记忆改进自身行为")
    print("=" * 70)

    sim = SelfReferenceSimulator(n_trials=1000, seed=42, n_episodes=5)
    result = sim.run()

    print(f"\n[长程任务 {result['n_episodes']} episode, {result['n_trials']} trials]")
    print(f"  no_memory（无记忆）       = {result['results']['no_memory']:.6f}")
    print(f"  self_improve（自指记忆）  = {result['results']['self_improve']:.6f}")
    print(f"  external（外部知识注入）  = {result['results']['external_knowledge']:.6f}")
    print(f"\n  自指增益 = {result['self_reference_gain']:.6f}")
    print(f"  外部增益 = {result['external_gain']:.6f}")
    print(f"\n  判据结论: {result['verdict']}")
    print(f"  {result['explanation']}")

    # 落盘证据
    evidence_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence")
    os.makedirs(evidence_dir, exist_ok=True)
    evidence_path = os.path.join(evidence_dir, "2026-11-01-r3_2-self-reference.json")
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 证据已落盘: {evidence_path}")


if __name__ == "__main__":
    main()
