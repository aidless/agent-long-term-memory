"""
记忆整合 - LLM 辅助的归纳总结，将多条相关记忆合并为更抽象的记忆。
"""

import time
from typing import Optional

from memory.base import MemoryItem


class MockLLMConsolidator:
    """
    Mock LLM 记忆整合器。

    模拟 LLM 对多条记忆进行归纳总结和合并。
    在实际项目中，这里会调用真实的 LLM API 进行整合。
    """

    def consolidate(
        self,
        memories: list[MemoryItem],
        topic: Optional[str] = None,
    ) -> Optional[MemoryItem]:
        """
        将多条记忆整合为一条总结性记忆。

        Args:
            memories: 待整合的记忆列表
            topic: 可选的主题描述

        Returns:
            整合后的新记忆，或 None（如果记忆太少）
        """
        if len(memories) < 2:
            return None

        # 收集所有内容
        contents = [m.content for m in memories]
        combined = "; ".join(contents)

        # Mock LLM 整合：取前 N 个字符 + 添加总结标记
        summary_prefix = f"[整合记忆-{len(memories)}条]"
        if topic:
            summary_prefix += f"[主题:{topic}]"

        # 简单的总结策略：
        # 1. 提取公共关键词
        # 2. 合并内容
        summary_content = self._simple_summarize(contents, topic)

        # 计算整合后的重要性（取平均值 + 数量奖励）
        avg_importance = sum(m.importance for m in memories) / len(memories)
        boosted_importance = min(1.0, avg_importance + 0.1 * (len(memories) - 1))

        # 合并元数据
        merged_metadata = {
            "consolidated_from": [m.id for m in memories],
            "consolidated_count": len(memories),
            "consolidation_method": "llm_mock",
            "consolidated_at": time.time(),
        }
        if topic:
            merged_metadata["topic"] = topic

        # 继承原始记忆的元数据
        for m in memories:
            for k, v in m.metadata.items():
                if k not in merged_metadata:
                    merged_metadata[k] = v

        return MemoryItem(
            id=f"consolidated_{int(time.time() * 1000)}",
            content=f"{summary_prefix} {summary_content}",
            memory_type="semantic",  # 整合后通常变成语义记忆
            metadata=merged_metadata,
            importance=boosted_importance,
            extra={"source_memories": [m.to_dict() for m in memories]},
        )

    def _simple_summarize(self, contents: list[str], topic: Optional[str] = None) -> str:
        """
        简单的文本总结（Mock）。

        在真实实现中，这里会调用 LLM 进行总结。
        """
        if not contents:
            return ""

        # 合并所有内容
        all_text = " ".join(contents)

        # 截取合理长度
        if len(all_text) > 200:
            return all_text[:200] + "..."

        return all_text

    def find_consolidatable(
        self,
        memories: list[MemoryItem],
        similarity_threshold: float = 0.5,
        min_group_size: int = 3,
    ) -> list[list[MemoryItem]]:
        """
        找出可以整合的记忆组。

        策略：按记忆类型分组，同组内基于内容相似度聚类。

        Args:
            memories: 记忆列表
            similarity_threshold: 相似度阈值
            min_group_size: 最小分组大小

        Returns:
            可整合的记忆组列表
        """
        from collections import defaultdict

        # 按类型分组
        type_groups = defaultdict(list)
        for m in memories:
            type_groups[m.memory_type].append(m)

        # 每组内找相似的
        consolidatable_groups = []
        for mem_type, group in type_groups.items():
            if len(group) < min_group_size:
                continue

            # 简单聚类：基于共同关键词
            clusters = self._simple_cluster(group, similarity_threshold)
            for cluster in clusters:
                if len(cluster) >= min_group_size:
                    consolidatable_groups.append(cluster)

        return consolidatable_groups

    def _simple_cluster(
        self,
        memories: list[MemoryItem],
        threshold: float,
    ) -> list[list[MemoryItem]]:
        """
        简单的文本聚类。

        基于关键词重叠进行聚类。
        """
        clusters: list[list[MemoryItem]] = []
        assigned: set[str] = set()

        for memory in memories:
            if memory.id in assigned:
                continue

            cluster = [memory]
            assigned.add(memory.id)

            memory_words = set(memory.content.lower().split())

            for other in memories:
                if other.id in assigned:
                    continue

                other_words = set(other.content.lower().split())
                if not memory_words or not other_words:
                    continue

                overlap = len(memory_words & other_words)
                union = len(memory_words | other_words)
                similarity = overlap / union if union > 0 else 0.0

                if similarity >= threshold:
                    cluster.append(other)
                    assigned.add(other.id)

            if len(cluster) >= 2:
                clusters.append(cluster)

        return clusters