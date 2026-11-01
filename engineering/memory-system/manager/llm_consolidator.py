"""
LLM 记忆整合器 - 使用 OpenAI API 进行真正的归纳总结和语义聚类。

替代 MockLLMConsolidator 的真实实现，通过 httpx 直接调用 OpenAI API。
"""

import logging
import math
import os
import time
from collections import defaultdict
from typing import Optional

import httpx

from memory.base import MemoryItem

logger = logging.getLogger(__name__)


class LLMConsolidator:
    """
    LLM 记忆整合器。

    使用 OpenAI API 对多条记忆进行归纳总结，
    并使用 TF-IDF 进行语义聚类（而非关键词重叠）。
    """

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self._http_client: Optional[httpx.AsyncClient] = None
        self._sync_client: Optional[httpx.Client] = None

        if not self.api_key:
            logger.warning("OPENAI_API_KEY 未设置，LLM 整合将回退到简单模式")

    def _get_sync_client(self) -> httpx.Client:
        if self._sync_client is None or self._sync_client.is_closed:
            self._sync_client = httpx.Client(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30.0,
            )
        return self._sync_client

    async def _get_async_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30.0,
            )
        return self._http_client

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
            整合后的新记忆，或 None（如果记忆太少或 API 不可用）
        """
        if len(memories) < 2:
            return None

        contents = [m.content for m in memories]

        # 尝试调用 LLM 进行总结
        summary_content = self._llm_summarize(contents, topic)

        # 如果 LLM 不可用，回退到简单模式
        if summary_content is None:
            logger.info("LLM 不可用，回退到简单总结模式")
            summary_content = self._fallback_summarize(contents, topic)

        # 计算整合后的重要性
        avg_importance = sum(m.importance for m in memories) / len(memories)
        boosted_importance = min(1.0, avg_importance + 0.1 * (len(memories) - 1))

        # 合并元数据
        merged_metadata = {
            "consolidated_from": [m.id for m in memories],
            "consolidated_count": len(memories),
            "consolidation_method": "llm",
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
            content=summary_content,
            memory_type="semantic",
            metadata=merged_metadata,
            importance=boosted_importance,
            extra={"source_memories": [m.to_dict() for m in memories]},
        )

    def _llm_summarize(self, contents: list[str], topic: Optional[str] = None) -> Optional[str]:
        """调用 OpenAI API 进行真正的归纳总结。"""
        if not self.api_key:
            return None

        # 构造提示
        memory_texts = "\n".join(f"- {c}" for c in contents)
        topic_hint = f"，主题为「{topic}」" if topic else ""

        prompt = (
            f"请将以下多条记忆整合为一条简洁、连贯的总结性记忆{topic_hint}。\n"
            f"要求：\n"
            f"1. 保留关键信息和重要细节\n"
            f"2. 去除重复内容\n"
            f"3. 用概括性的语言表达\n"
            f"4. 输出纯文本，不要加前缀标记\n\n"
            f"原始记忆：\n{memory_texts}"
        )

        try:
            client = self._get_sync_client()
            response = client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "你是一个记忆整合助手，擅长将多条相关记忆归纳为简洁的总结。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 512,
                },
            )
            response.raise_for_status()
            data = response.json()
            summary = data["choices"][0]["message"]["content"].strip()
            if summary:
                logger.info(f"LLM 整合成功：{len(contents)} 条记忆 -> 1 条总结")
                return summary
            return None
        except httpx.HTTPError as e:
            logger.warning(f"LLM API 调用失败: {e}")
            return None
        except Exception as e:
            logger.warning(f"LLM 整合异常: {e}")
            return None

    def _fallback_summarize(self, contents: list[str], topic: Optional[str] = None) -> str:
        """简单回退总结：合并内容并截断（当 API 不可用时）。"""
        summary_prefix = f"[整合记忆-{len(contents)}条]"
        if topic:
            summary_prefix += f"[主题:{topic}]"

        all_text = " ".join(contents)
        if len(all_text) > 500:
            # 截取前500字符
            return f"{summary_prefix} {all_text[:500]}..."
        return f"{summary_prefix} {all_text}"

    def find_consolidatable(
        self,
        memories: list[MemoryItem],
        similarity_threshold: float = 0.5,
        min_group_size: int = 3,
    ) -> list[list[MemoryItem]]:
        """
        找出可以整合的记忆组。

        使用 TF-IDF 向量计算语义相似度，而非简单的关键词重叠。
        按 memory_type 分组后，在组内使用 TF-IDF + cosine similarity 聚类。

        Args:
            memories: 记忆列表
            similarity_threshold: 相似度阈值 (cosine similarity)
            min_group_size: 最小分组大小

        Returns:
            可整合的记忆组列表
        """
        # 按类型分组
        type_groups = defaultdict(list)
        for m in memories:
            type_groups[m.memory_type].append(m)

        consolidatable_groups = []
        for mem_type, group in type_groups.items():
            if len(group) < min_group_size:
                continue

            clusters = self._tfidf_cluster(group, similarity_threshold)
            for cluster in clusters:
                if len(cluster) >= min_group_size:
                    consolidatable_groups.append(cluster)

        return consolidatable_groups

    def _tfidf_cluster(
        self,
        memories: list[MemoryItem],
        threshold: float,
    ) -> list[list[MemoryItem]]:
        """
        基于 TF-IDF 的语义聚类。

        使用 TF-IDF 将记忆内容转换为向量，
        然后用 cosine similarity 进行贪心聚类。
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            contents = [m.content for m in memories]
            vectorizer = TfidfVectorizer(
                max_features=1000,
                # 支持中文：使用字符级 n-gram
                analyzer="char",
                ngram_range=(1, 3),
            )
            tfidf_matrix = vectorizer.fit_transform(contents)
            sim_matrix = cosine_similarity(tfidf_matrix)

            return self._greedy_cluster_from_sim(memories, sim_matrix, threshold)

        except ImportError:
            logger.warning("sklearn 未安装，回退到关键词重叠聚类")
            return self._keyword_cluster(memories, threshold)

    def _greedy_cluster_from_sim(
        self,
        memories: list[MemoryItem],
        sim_matrix,
        threshold: float,
    ) -> list[list[MemoryItem]]:
        """基于相似度矩阵进行贪心聚类。"""
        clusters: list[list[MemoryItem]] = []
        assigned: set[int] = set()

        for i in range(len(memories)):
            if i in assigned:
                continue

            cluster_indices = [i]
            assigned.add(i)

            for j in range(i + 1, len(memories)):
                if j in assigned:
                    continue
                if sim_matrix[i][j] >= threshold:
                    cluster_indices.append(j)
                    assigned.add(j)

            if len(cluster_indices) >= 2:
                clusters.append([memories[idx] for idx in cluster_indices])

        return clusters

    def _keyword_cluster(
        self,
        memories: list[MemoryItem],
        threshold: float,
    ) -> list[list[MemoryItem]]:
        """回退的关键词重叠聚类（当 sklearn 不可用时）。"""
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
