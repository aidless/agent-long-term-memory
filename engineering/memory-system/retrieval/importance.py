"""
重要性评分 - 基于访问频率、手动标记和新近度的重要性评分。
"""

import math
import time
from typing import Optional

from retrieval.semantic_search import SearchResult
from memory.base import MemoryItem


class ImportanceScorer:
    """
    重要性评分器。

    评分公式：
        importance = alpha * manual_importance
                    + beta * access_frequency_normalized
                    + gamma * recency_score

    默认权重：alpha=0.4, beta=0.3, gamma=0.3
    """

    def __init__(
        self,
        alpha: float = 0.4,
        beta: float = 0.3,
        gamma: float = 0.3,
    ):
        self.alpha = alpha  # 手动重要性权重
        self.beta = beta    # 访问频率权重
        self.gamma = gamma  # 新近度权重

    def score(self, memory: MemoryItem, current_time: Optional[float] = None) -> float:
        """
        计算记忆的重要性分数。

        Args:
            memory: 记忆条目
            current_time: 当前时间

        Returns:
            重要性分数 [0, 1]
        """
        if current_time is None:
            current_time = time.time()

        # 1. 手动标记的重要性
        manual_importance = memory.importance

        # 2. 访问频率（使用对数平滑）
        access_freq = math.log1p(memory.access_count) / 5.0  # 归一化
        access_freq = min(access_freq, 1.0)

        # 3. 新近度（最近更新的记忆更重要）
        age = current_time - memory.updated_at
        recency = math.exp(-age / 86400.0)  # 24小时半衰期

        # 加权求和
        total = (
            self.alpha * manual_importance
            + self.beta * access_freq
            + self.gamma * recency
        )

        return max(0.0, min(1.0, total))

    def apply_importance(
        self,
        results: list[SearchResult],
        current_time: Optional[float] = None,
        importance_weight: float = 1.0,
    ) -> list[SearchResult]:
        """
        对检索结果应用重要性加权。

        Args:
            results: 原始检索结果
            current_time: 当前时间
            importance_weight: 重要性权重

        Returns:
            应用重要性加权后的检索结果
        """
        weighted = []
        for result in results:
            imp_score = self.score(result.memory, current_time)
            original_score = result.score
            blended = (1 - importance_weight) * original_score + importance_weight * imp_score
            breakdown = dict(result.score_breakdown)
            breakdown["importance"] = imp_score

            weighted.append(SearchResult(
                memory=result.memory,
                score=blended,
                score_breakdown=breakdown,
            ))

        weighted.sort(key=lambda r: r.score, reverse=True)
        return weighted

    def rerank_by_importance(
        self,
        memories: list[MemoryItem],
        top_k: int = 10,
        current_time: Optional[float] = None,
    ) -> list[SearchResult]:
        """
        按重要性重新排序记忆。
        """
        if current_time is None:
            current_time = time.time()

        scored = []
        for memory in memories:
            imp_score = self.score(memory, current_time)
            scored.append(SearchResult(
                memory=memory,
                score=imp_score,
                score_breakdown={"importance": imp_score},
            ))

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]