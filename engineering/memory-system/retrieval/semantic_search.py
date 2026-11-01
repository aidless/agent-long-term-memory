"""
语义检索 - 基于向量相似度的记忆检索。
"""

from dataclasses import dataclass
from typing import Optional

from memory.base import MemoryItem


@dataclass
class SearchResult:
    """检索结果。"""
    memory: MemoryItem
    score: float
    score_breakdown: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "memory": self.memory.to_dict(),
            "score": self.score,
            "score_breakdown": self.score_breakdown,
        }


class SemanticSearch:
    """
    语义检索策略。

    直接基于向量存储的语义相似度进行检索。
    """

    def __init__(self):
        pass

    def search(
        self,
        memories: list[MemoryItem],
        query: str,
        top_k: int = 10,
        threshold: float = 0.0,
    ) -> list[SearchResult]:
        """
        执行语义检索。

        由于真正的语义检索在向量存储层完成，
        这里直接对已给定的记忆列表按内容相似度排序。
        """
        scored = self._score_all(memories, query)
        results = [
            SearchResult(memory=m, score=s, score_breakdown={"semantic": s})
            for m, s in scored
            if s >= threshold
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def _score_all(self, memories: list[MemoryItem], query: str) -> list[tuple[MemoryItem, float]]:
        """对记忆列表进行评分。"""
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for memory in memories:
            content_lower = memory.content.lower()
            content_words = set(content_lower.split())

            if not query_words or not content_words:
                scored.append((memory, 0.0))
                continue

            # Jaccard 相似度
            intersection = len(query_words & content_words)
            union = len(query_words | content_words)
            jaccard = intersection / union if union > 0 else 0.0

            # 精确包含奖励
            if query_lower in content_lower:
                jaccard = max(jaccard, 0.9)

            scored.append((memory, jaccard))

        return scored