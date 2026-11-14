#!/usr/bin/env python3
"""
R2.3 检索 vs 记忆变体（V2.3）——补充对照实验，扩展 R2.1/R2.2 的边界。

设计（docs/design/2026-11-01-phase2-design.md V2.3）：
    V2.3a 英文基准：英文场景下验证 M 判据（区分记忆与检索）。
    V2.3b 噪音敏感性：不同噪音比例下 M 值变化（记忆系统应保持优势）。
    V2.3c 检索质量：不同检索质量（阈值/关联提升）下 M 值变化——高检索质量下
            纯检索接近记忆，低质量下记忆优势扩大。

判据（R2.2 基准协议）：
    M = P(成功|模糊查询,记忆) - P(成功|模糊查询,纯检索)
    M > 0.05：MEMORY_SYSTEM（真记忆，模糊查询仍帮助）
    |M| ≤ 0.05：RETRIEVAL_SYSTEM（仅检索，查询驱动）
    M < -0.05：DEGRADED_SYSTEM（记忆引入噪音，损害）

复现：
    python3 research/02-memory-vs-retrieval/experiments/r2_3_retrieval_vs_memory_variants.py
"""

import json
import os
import random
from dataclasses import dataclass


# ==================== 相似度机制 ====================

def jaccard_similarity(query: str, content: str) -> float:
    """Jaccard 相似度（与 semantic_search.py 一致）。"""
    query_words = set(query.lower().split())
    content_words = set(content.lower().split())
    if not query_words or not content_words:
        return 0.0
    intersection = len(query_words & content_words)
    union = len(query_words | content_words)
    if union == 0:
        return 0.0
    jaccard = intersection / union
    # 精确包含奖励
    if query.lower() in content.lower():
        jaccard = max(jaccard, 0.9)
    return jaccard


# ==================== 基准协议 ====================

@dataclass
class VariantBenchmark:
    """R2.3 变体基准：区分记忆能力与检索质量的扩展协议。

    支持语言（英文/中文）与检索质量参数调节。
    """

    n_trials: int = 1000
    seed: int = 42
    similarity_threshold: float = 0.3
    association_bonus: float = 0.2
    noise_ratio: float = 0.5
    n_items: int = 20
    language: str = "en"  # en / zh

    def __post_init__(self):
        self.rng = random.Random(self.seed)

    def _target(self) -> str:
        if self.language == "zh":
            return "正确的目标信息关键词事实"
        return "correct target information keyword fact"

    def _fuzzy_query(self) -> str:
        """模糊查询：只匹配部分目标信息（模拟 agent 无法精确表达）。"""
        if self.language == "zh":
            # 2 个目标词 + 模糊词
            return "正确的目标 模糊1 模糊2 模糊3"
        return "correct target fuzzy1 fuzzy2 fuzzy3"

    def _exact_query(self) -> str:
        """精确查询：完全匹配目标信息。"""
        return self._target()

    def _noise_items(self) -> list[str]:
        """生成噪音信息列表。"""
        n_noise = int(self.n_items * self.noise_ratio)
        noise_items = []
        for _ in range(n_noise):
            overlap = self.rng.randint(0, 3)
            if self.language == "zh":
                words = ["噪音", "无关", "干扰"] + [f"w{i}" for i in range(overlap)]
            else:
                words = ["noise", "irrelevant", "distractor"] + \
                        [f"w{i}" for i in range(overlap)]
            noise_items.append(" ".join(words))
        return noise_items

    def _run_trial(self, query: str, use_memory: bool) -> bool:
        """运行一次检索试验，返回是否命中目标信息。"""
        target = self._target()
        items = [target] + self._noise_items()

        scores = [(item, jaccard_similarity(query, item)) for item in items]
        best_item, best_score = max(scores, key=lambda x: x[1])

        if use_memory:
            # 记忆系统：关联记忆提升（模糊查询时通过关联命中）
            target_sim = jaccard_similarity(query, target)
            if target_sim > 0:
                best_score += self.association_bonus

        # 命中判定：分数超阈值且命中 target
        return best_score >= self.similarity_threshold and target in best_item

    def measure(self, query_kind: str, use_memory: bool) -> float:
        """测量指定查询类型与系统类型的成功率。"""
        success = 0
        for _ in range(self.n_trials):
            query = self._exact_query() if query_kind == "exact" else self._fuzzy_query()
            if self._run_trial(query, use_memory):
                success += 1
        return success / self.n_trials

    def run(self) -> dict:
        """运行基准协议，计算记忆帮助度 M。"""
        exact_pure = self.measure("exact", use_memory=False)
        fuzzy_pure = self.measure("fuzzy", use_memory=False)
        exact_mem = self.measure("exact", use_memory=True)
        fuzzy_mem = self.measure("fuzzy", use_memory=True)

        m_fuzzy = fuzzy_mem - fuzzy_pure
        m_exact = exact_mem - exact_pure

        # 判据分类
        if m_fuzzy > 0.05:
            verdict = "MEMORY_SYSTEM"
            explanation = "M(模糊)>0：记忆在模糊查询时仍帮助（自主）——真记忆。"
        elif abs(m_fuzzy) <= 0.05:
            verdict = "RETRIEVAL_SYSTEM"
            explanation = "M(模糊)≈0：仅对精确查询有效——检索系统（查询驱动）。"
        else:
            verdict = "DEGRADED_SYSTEM"
            explanation = "M(模糊)<0：记忆引入噪音，损害而非帮助。"

        return {
            "language": self.language,
            "n_trials": self.n_trials,
            "similarity_threshold": self.similarity_threshold,
            "association_bonus": self.association_bonus,
            "noise_ratio": self.noise_ratio,
            "n_items": self.n_items,
            "results": {
                "exact_query_pure": round(exact_pure, 6),
                "fuzzy_query_pure": round(fuzzy_pure, 6),
                "exact_query_memory": round(exact_mem, 6),
                "fuzzy_query_memory": round(fuzzy_mem, 6),
            },
            "memory_advantage": {
                "fuzzy_query_M": round(m_fuzzy, 6),
                "exact_query_M": round(m_exact, 6),
            },
            "verdict": verdict,
            "explanation": explanation,
        }


# ==================== V2.3 变体实验 ====================

def run_v2_3a_english_baseline(n_trials: int = 1000, seed: int = 42) -> dict:
    """V2.3a 英文基准：英文场景验证 M 判据。"""
    bench = VariantBenchmark(n_trials=n_trials, seed=seed, language="en")
    return bench.run()


def run_v2_3b_noise_sensitivity(n_trials: int = 1000, seed: int = 42) -> dict:
    """V2.3b 噪音敏感性：不同噪音比例下 M 值。"""
    sensitivity = []
    for noise_ratio in [0.1, 0.3, 0.5, 0.7, 0.9]:
        bench = VariantBenchmark(
            n_trials=n_trials, seed=seed, language="en",
            noise_ratio=noise_ratio,
        )
        r = bench.run()
        sensitivity.append({
            "noise_ratio": noise_ratio,
            "fuzzy_query_pure": r["results"]["fuzzy_query_pure"],
            "fuzzy_query_memory": r["results"]["fuzzy_query_memory"],
            "M_fuzzy": r["memory_advantage"]["fuzzy_query_M"],
            "verdict": r["verdict"],
        })
    return {"n_trials": n_trials, "sensitivity": sensitivity}


def run_v2_3c_retrieval_quality(n_trials: int = 1000, seed: int = 42) -> dict:
    """V2.3c 检索质量：不同检索质量（阈值/关联提升）下 M 值。

    高质量检索（阈值低/关联提升高）→ 纯检索接近记忆，M 缩小；
    低质量检索（阈值高/关联提升低）→ 记忆优势扩大，M 增大。
    """
    quality_results = []
    configs = [
        # (label, similarity_threshold, association_bonus)
        ("high_quality", 0.15, 0.05),   # 高质量检索：阈值低、提升小
        ("medium_quality", 0.30, 0.20),  # 中等（R2.2 基准）
        ("low_quality", 0.45, 0.35),    # 低质量检索：阈值高、提升大
    ]
    for label, threshold, bonus in configs:
        bench = VariantBenchmark(
            n_trials=n_trials, seed=seed, language="en",
            similarity_threshold=threshold, association_bonus=bonus,
        )
        r = bench.run()
        quality_results.append({
            "quality_level": label,
            "similarity_threshold": threshold,
            "association_bonus": bonus,
            "fuzzy_query_pure": r["results"]["fuzzy_query_pure"],
            "fuzzy_query_memory": r["results"]["fuzzy_query_memory"],
            "M_fuzzy": r["memory_advantage"]["fuzzy_query_M"],
            "verdict": r["verdict"],
        })
    return {"n_trials": n_trials, "quality_results": quality_results}


def main():
    """运行 R2.3 变体实验并落盘证据。"""
    print("=" * 70)
    print("R2.3 检索 vs 记忆变体（V2.3）——扩展 R2.1/R2.2 边界")
    print("=" * 70)

    # V2.3a 英文基准
    print("\n[V2.3a] 英文基准（M 判据验证）")
    v23a = run_v2_3a_english_baseline()
    print(f"  精确+纯检索={v23a['results']['exact_query_pure']:.6f}")
    print(f"  模糊+纯检索={v23a['results']['fuzzy_query_pure']:.6f}")
    print(f"  精确+记忆  ={v23a['results']['exact_query_memory']:.6f}")
    print(f"  模糊+记忆  ={v23a['results']['fuzzy_query_memory']:.6f}")
    print(f"  M(模糊)={v23a['memory_advantage']['fuzzy_query_M']:.6f}  "
          f"M(精确)={v23a['memory_advantage']['exact_query_M']:.6f}")
    print(f"  判据: {v23a['verdict']}")

    # V2.3b 噪音敏感性
    print("\n[V2.3b] 噪音敏感性（M 随噪音比例变化）")
    v23b = run_v2_3b_noise_sensitivity()
    for s in v23b["sensitivity"]:
        print(f"  噪音={s['noise_ratio']:.1f}  "
              f"纯检索={s['fuzzy_query_pure']:.6f}  "
              f"记忆={s['fuzzy_query_memory']:.6f}  "
              f"M={s['M_fuzzy']:.6f}  {s['verdict']}")

    # V2.3c 检索质量
    print("\n[V2.3c] 检索质量（M 随检索质量变化）")
    v23c = run_v2_3c_retrieval_quality()
    for q in v23c["quality_results"]:
        print(f"  {q['quality_level']:14s} 阈值={q['similarity_threshold']:.2f}  "
              f"提升={q['association_bonus']:.2f}  "
              f"纯检索={q['fuzzy_query_pure']:.6f}  "
              f"记忆={q['fuzzy_query_memory']:.6f}  "
              f"M={q['M_fuzzy']:.6f}  {q['verdict']}")

    # 落盘证据
    evidence = {
        "experiment": "R2.3 检索 vs 记忆变体（V2.3）",
        "description": "扩展 R2.1/R2.2 边界：英文基准 / 噪音敏感性 / 检索质量",
        "variants": {
            "v2_3a_english_baseline": v23a,
            "v2_3b_noise_sensitivity": v23b,
            "v2_3c_retrieval_quality": v23c,
        },
        "criterion": "M = P(成功|模糊查询,记忆) - P(成功|模糊查询,纯检索)",
        "reproduce": "python3 research/02-memory-vs-retrieval/experiments/r2_3_retrieval_vs_memory_variants.py",
    }

    evidence_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "evidence")
    os.makedirs(evidence_dir, exist_ok=True)
    evidence_path = os.path.join(evidence_dir, "2026-11-01-r2_3-retrieval-vs-memory-variants.json")
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 证据已落盘: {evidence_path}")


if __name__ == "__main__":
    main()
