"""
混合检索 - 多因子加权的综合检索策略。

默认权重：语义*0.5 + 时间*0.2 + 重要性*0.3
"""

import time
from dataclasses import dataclass
from typing import Optional

from retrieval.semantic_search import SemanticSearch, SearchResult
from retrieval.time_decay import TimeDecayScorer
from retrieval.importance import ImportanceScorer
from memory.base import MemoryItem


@dataclass
class HybridConfig:
    """混合检索配置。"""
    semantic_weight: float = 0.5
    time_weight: float = 0.2
    importance_weight: float = 0.3
    top_k: int = 10
    threshold: float = 0.0
    enable_association: bool = True  # 是否启用关联记忆


class HybridRetriever:
    """
    混合检索器。

    综合语义相似度、时间衰减和重要性评分进行多因子加权检索。
    支持关联记忆：一次检索触发相关记忆的二次检索。
    """

    def __init__(self, config: Optional[HybridConfig] = None):
        self.config = config or HybridConfig()
        self.semantic_search = SemanticSearch()
        self.time_scorer = TimeDecayScorer()
        self.importance_scorer = ImportanceScorer()

    def search(
        self,
        memories: list[MemoryItem],
        query: str,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
        current_time: Optional[float] = None,
    ) -> list[SearchResult]:
        """
        执行混合检索。

        Args:
            memories: 候选记忆列表
            query: 查询文本
            top_k: 返回数量
            threshold: 最低分数阈值
            current_time: 当前时间

        Returns:
            混合评分后的检索结果
        """
        k = top_k or self.config.top_k
        thresh = threshold or self.config.threshold
        now = current_time or time.time()

        if not memories:
            return []

        # 1. 语义检索评分
        semantic_results = self.semantic_search.search(memories, query, top_k=len(memories), threshold=0.0)

        # 2. 为每条结果计算混合分数
        hybrid_results = []
        for result in semantic_results:
            mem = result.memory
            semantic_score = result.score
            time_score = self.time_scorer.decay(mem, now)
            importance_score = self.importance_scorer.score(mem, now)

            hybrid_score = (
                self.config.semantic_weight * semantic_score
                + self.config.time_weight * time_score
                + self.config.importance_weight * importance_score
            )

            hybrid_results.append(SearchResult(
                memory=mem,
                score=hybrid_score,
                score_breakdown={
                    "semantic": semantic_score,
                    "time_decay": time_score,
                    "importance": importance_score,
                    "hybrid": hybrid_score,
                },
            ))

        # 3. 过滤和排序
        filtered = [r for r in hybrid_results if r.score >= thresh]
        filtered.sort(key=lambda r: r.score, reverse=True)
        results = filtered[:k]

        # 4. 关联记忆扩展
        if self.config.enable_association and results:
            results = self._expand_associations(results, memories, now, k)

        return results

    def _expand_associations(
        self,
        results: list[SearchResult],
        all_memories: list[MemoryItem],
        current_time: float,
        max_results: int,
    ) -> list[SearchResult]:
        """
        关联记忆扩展：基于已检索到的记忆内容，触发相关记忆的二次检索。

        策略：提取已检索记忆中的关键词，用这些关键词进行二次检索，
        将相关但不重叠的记忆补充到结果中。
        """
        # 收集已有记忆的 ID
        existing_ids = {r.memory.id for r in results}

        # 提取关键词作为二次查询
        seen_results = set()
        expanded_results = list(results)

        for result in results[:3]:  # 只从前3条结果提取关键词
            # 用记忆内容作为查询进行关联检索
            associated = self.semantic_search.search(
                all_memories,
                result.memory.content,
                top_k=5,
                threshold=0.1,
            )
            for assoc in associated:
                if assoc.memory.id not in existing_ids and assoc.memory.id not in seen_results:
                    seen_results.add(assoc.memory.id)
                    # 关联记忆分数降低
                    assoc_score = assoc.score * 0.5
                    time_score = self.time_scorer.decay(assoc.memory, current_time)
                    importance_score = self.importance_scorer.score(assoc.memory, current_time)
                    hybrid_score = (
                        self.config.semantic_weight * assoc_score
                        + self.config.time_weight * time_score
                        + self.config.importance_weight * importance_score
                    )
                    expanded_results.append(SearchResult(
                        memory=assoc.memory,
                        score=hybrid_score * 0.7,  # 关联记忆进一步降权
                        score_breakdown={
                            "semantic": assoc_score,
                            "time_decay": time_score,
                            "importance": importance_score,
                            "hybrid": hybrid_score,
                            "association": True,
                        },
                    ))

        # 重新排序
        expanded_results.sort(key=lambda r: r.score, reverse=True)
        return expanded_results[:max_results]