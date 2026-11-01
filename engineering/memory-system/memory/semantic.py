"""
语义记忆 - 存储事实和知识，基于向量存储的语义检索。
"""

import time
import uuid
from typing import Any, Optional

from memory.base import BaseMemory, MemoryItem


class SemanticMemory(BaseMemory):
    """
    语义记忆：存储事实、知识和概念。

    特点：
    - 基于向量相似度检索
    - 支持知识分类和标签
    - 支持知识来源追溯
    """

    @property
    def memory_type(self) -> str:
        return "semantic"

    def add(
        self,
        content: str,
        metadata: Optional[dict] = None,
        importance: float = 0.5,
        **kwargs,
    ) -> MemoryItem:
        """添加一条语义记忆（事实/知识）。"""
        mem_id = kwargs.get("memory_id") or f"sem_{uuid.uuid4().hex[:12]}"
        meta = metadata or {}
        meta["memory_type"] = "semantic"

        # 知识相关元数据
        if "category" not in meta:
            meta["category"] = kwargs.get("category", "general")
        if "source" not in meta:
            meta["source"] = kwargs.get("source", "manual")
        if "confidence" not in meta:
            meta["confidence"] = kwargs.get("confidence", 1.0)

        record = self.store.add(
            text=content,
            record_id=mem_id,
            metadata=meta,
            importance=importance,
        )

        return self._record_to_item(record)

    def search_by_category(self, category: str, top_k: int = 10) -> list[tuple[MemoryItem, float]]:
        """按类别搜索语义记忆。"""
        results = self.store.search(
            query=category,
            top_k=top_k,
            filter_metadata={"category": category},
        )
        return [(self._record_to_item(r), score) for r, score in results]

    def update_confidence(self, memory_id: str, confidence: float) -> Optional[MemoryItem]:
        """更新知识的置信度。"""
        return self.update(memory_id, metadata={"confidence": confidence})