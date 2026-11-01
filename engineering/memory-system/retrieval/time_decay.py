"""
时间衰减 - 基于时间衰减函数的记忆评分。
"""

import math
import time
from dataclasses import dataclass
from typing import Optional

from retrieval.semantic_search import SearchResult
from memory.base import MemoryItem


@dataclass
class TimeDecayConfig:
    """时间衰减配置。"""
    half_life: float = 86400.0  # 半衰期，默认 24 小时（秒）
    min_score: float = 0.01  # 最低衰减分数


class TimeDecayScorer:
    """
    时间衰减评分器。

    使用指数衰减函数：score = base_score * exp(-lambda * age)
    其中 lambda = ln(2) / half_life
    """

    def __init__(self, config: Optional[TimeDecayConfig] = None):
        self.config = config or TimeDecayConfig()

    def decay(self, memory: MemoryItem, current_time: Optional[float] = None) -> float:
        """
        计算时间衰减分数。

        Args:
            memory: 记忆条目
            current_time: 当前时间（默认为 time.time()）

        Returns:
            衰减分数 (0, 1]
        """
        if current_time is None:
            current_time = time.time()

        age = current_time - memory.created_at
        if age <= 0:
            return 1.0

        lambda_val = math.log(2) / self.config.half_life
        decay_score = math.exp(-lambda_val * age)
        return max(decay_score, self.config.min_score)

    def apply_decay(
        self,
        results: list[SearchResult],
        current_time: Optional[float] = None,
        time_weight: float = 1.0,
    ) -> list[SearchResult]:
        """
        对检索结果应用时间衰减。

        Args:
            results: 原始检索结果
            current_time: 当前时间
            time_weight: 时间衰减的权重

        Returns:
            应用时间衰减后的检索结果
        """
        decayed = []
        for result in results:
            time_score = self.decay(result.memory, current_time)
            original_score = result.score
            # 混合：保留部分原始分数，加入时间衰减
            blended = (1 - time_weight) * original_score + time_weight * (original_score * time_score)
            breakdown = dict(result.score_breakdown)
            breakdown["time_decay"] = time_score

            decayed.append(SearchResult(
                memory=result.memory,
                score=blended,
                score_breakdown=breakdown,
            ))

        decayed.sort(key=lambda r: r.score, reverse=True)
        return decayed

    def rerank_by_recency(
        self,
        memories: list[MemoryItem],
        query: str,
        top_k: int = 10,
        current_time: Optional[float] = None,
    ) -> list[SearchResult]:
        """
        按时间新近度重新排序记忆。

        纯时间排序，不考虑语义相似度。
        """
        if current_time is None:
            current_time = time.time()

        scored = []
        for memory in memories:
            time_score = self.decay(memory, current_time)
            scored.append(SearchResult(
                memory=memory,
                score=time_score,
                score_breakdown={"time_decay": time_score},
            ))

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]