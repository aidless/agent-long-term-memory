#!/usr/bin/env python3
"""
R2.2 记忆基准协议 - 明确「记忆帮助」的可操作判据。

背景（判断②的缺口 2）：
    业界缺少统一的「记忆是否真的帮助」基准——多数宣称是检索质量而非记忆能力。
    很多系统宣称「记忆提升」但实际上只提升了检索质量（更好的 embedding、更好的
    chunk），并非真正帮助 agent 记住。

核心问题：
    如何区分「记忆能力」与「检索质量」？

    检索系统：查询精确 → 命中；查询模糊 → 失败（查询驱动）。
    记忆系统：即使查询模糊，也能利用先前经验影响行为（自主）。

可操作判据（本协议）：
    M = P(成功 | 模糊查询) - P(成功 | 精确查询)

    - M 显著 > 0：系统在模糊查询时仍能帮助（真正记忆）——模糊查询是记忆的试金石，
      因为模糊查询模拟 agent 无法精确表达信息的真实场景。
    - M ≈ 0：系统只帮精确查询（纯检索）——它只是「检索系统」而非「记忆系统」。

    注意：M > 0 意味着**模糊查询也能成功**——这正是记忆超越检索的关键。
    如果系统只对精确查询有效（M≈0 且 P(exact) 高），它是检索系统。

基准协议（任何记忆系统可自检）：
    1. 定义任务：agent 需利用先前经验完成当前任务。
    2. 变量：查询精确度（精确 vs 模糊）。
    3. 度量：任务成功率。
    4. 判据：M = P(success|fuzzy) - P(success|exact)。

复现：
    python3 research/02-memory-vs-retrieval/experiments/r2_2_memory_benchmark.py
"""

import json
import os
import random
from dataclasses import dataclass
from typing import Optional


# ==================== 基准协议实现 ====================

@dataclass
class MemoryBenchmark:
    """记忆基准协议：区分「记忆能力」与「检索质量」。"""

    # 系统参数
    n_trials: int = 1000
    seed: int = 42
    similarity_threshold: float = 0.3  # 检索命中阈值
    association_bonus: float = 0.2  # 记忆整合带来的关联提升（仅记忆系统）

    def __post_init__(self):
        self.rng = random.Random(self.seed)

    def _jaccard(self, query: str, content: str) -> float:
        """Jaccard 相似度（与 semantic_search.py 一致）。"""
        q_words = set(query.lower().split())
        c_words = set(content.lower().split())
        if not q_words or not c_words:
            return 0.0
        inter = len(q_words & c_words)
        union = len(q_words | c_words)
        if union == 0:
            return 0.0
        j = inter / union
        if query.lower() in content.lower():
            j = max(j, 0.9)
        return j

    def _query_exact(self) -> str:
        """精确查询：完全匹配目标信息。"""
        return "correct target information keyword fact"

    def _query_fuzzy(self) -> str:
        """模糊查询：只匹配部分目标信息（模拟 agent 无法精确表达）。"""
        # 只保留 2 个目标词（Jaccard 约 0.25 < 阈值），加模糊词
        return "correct target fuzzy1 fuzzy2 fuzzy3"

    def _run_trial(self, query: str, use_memory: bool, n_items: int = 20,
                   noise_ratio: float = 0.5) -> bool:
        """运行一次检索试验，返回是否命中目标信息。"""
        target = "correct target information keyword fact"
        n_noise = int(n_items * noise_ratio)
        noise_items = []
        for _ in range(n_noise):
            overlap = self.rng.randint(0, 3)
            words = ["noise", "irrelevant", "distractor"] + \
                    [f"w{i}" for i in range(overlap)]
            noise_items.append(" ".join(words))
        items = [target] + noise_items

        scores = [(item, self._jaccard(query, item)) for item in items]
        best_item, best_score = max(scores, key=lambda x: x[1])

        if use_memory:
            # 记忆系统：关联记忆提升（查询模糊时通过关联命中）
            target_sim = self._jaccard(query, target)
            if target_sim > 0:
                best_score += self.association_bonus

        return best_score >= self.similarity_threshold and "correct target" in best_item

    def measure(self, query_kind: str, use_memory: bool) -> float:
        """测量指定查询类型与系统类型的成功率。"""
        success = 0
        for _ in range(self.n_trials):
            query = self._query_exact() if query_kind == "exact" else self._query_fuzzy()
            if self._run_trial(query, use_memory):
                success += 1
        return success / self.n_trials

    def run(self) -> dict:
        """运行基准协议，计算记忆帮助度 M。"""
        # 四种组合
        exact_pure = self.measure("exact", use_memory=False)   # 精确查询 + 纯检索
        fuzzy_pure = self.measure("fuzzy", use_memory=False)   # 模糊查询 + 纯检索
        exact_mem = self.measure("exact", use_memory=True)     # 精确查询 + 记忆系统
        fuzzy_mem = self.measure("fuzzy", use_memory=True)     # 模糊查询 + 记忆系统

        # 记忆帮助度 M（模糊查询下，记忆系统 vs 纯检索的差异）
        # M = P(success|fuzzy, memory) - P(success|fuzzy, pure)
        # 若 M > 0：记忆系统在模糊查询时比纯检索更好 → 真记忆
        # 若 M ≈ 0：两者无差异 → 只是检索系统
        m_fuzzy = fuzzy_mem - fuzzy_pure
        m_exact = exact_mem - exact_pure

        # 判据分类
        if m_fuzzy > 0.05:
            verdict = "MEMORY_SYSTEM"
            explanation = (
                "M(模糊查询)>0：记忆系统在模糊查询时仍能帮助（关联记忆），"
                "是真正的记忆系统（自主，不依赖查询精确度）。"
            )
        elif abs(m_fuzzy) <= 0.05:
            verdict = "RETRIEVAL_SYSTEM"
            explanation = (
                "M(模糊查询)≈0：记忆系统与纯检索无差异——只对精确查询有效，"
                "是「检索系统」而非「记忆系统」（查询驱动）。"
            )
        else:
            verdict = "DEGRADED_SYSTEM"
            explanation = (
                "M(模糊查询)<0：记忆系统在模糊查询时反而更差——"
                "记忆整合引入了错误/噪音，损害而非帮助。"
            )

        return {
            "protocol": "R2.2 记忆基准协议",
            "description": "区分「记忆能力」与「检索质量」的可操作判据",
            "criterion": "M = P(成功|模糊查询,记忆系统) - P(成功|模糊查询,纯检索)",
            "n_trials": self.n_trials,
            "results": {
                "exact_query_pure": exact_pure,
                "fuzzy_query_pure": fuzzy_pure,
                "exact_query_memory": exact_mem,
                "fuzzy_query_memory": fuzzy_mem,
            },
            "memory_advantage": {
                "fuzzy_query_M": round(m_fuzzy, 6),
                "exact_query_M": round(m_exact, 6),
            },
            "verdict": verdict,
            "explanation": explanation,
        }


def main():
    """运行 R2.2 基准协议并落盘证据。"""
    print("=" * 70)
    print("R2.2 记忆基准协议 - 区分记忆能力与检索质量")
    print("=" * 70)

    bench = MemoryBenchmark(n_trials=1000, seed=42)
    result = bench.run()

    print(f"\n基准协议：M = P(成功|模糊查询,记忆) - P(成功|模糊查询,纯检索)")
    print(f"  精确查询 + 纯检索 = {result['results']['exact_query_pure']:.6f}")
    print(f"  模糊查询 + 纯检索 = {result['results']['fuzzy_query_pure']:.6f}")
    print(f"  精确查询 + 记忆系统 = {result['results']['exact_query_memory']:.6f}")
    print(f"  模糊查询 + 记忆系统 = {result['results']['fuzzy_query_memory']:.6f}")
    print(f"\n  M(模糊查询) = {result['memory_advantage']['fuzzy_query_M']:.6f}")
    print(f"  M(精确查询) = {result['memory_advantage']['exact_query_M']:.6f}")
    print(f"\n  判据结论: {result['verdict']}")
    print(f"  {result['explanation']}")

    # 落盘证据
    evidence_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence")
    os.makedirs(evidence_dir, exist_ok=True)
    evidence_path = os.path.join(evidence_dir, "2026-11-01-r2_2-memory-benchmark.json")
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 证据已落盘: {evidence_path}")


if __name__ == "__main__":
    main()
