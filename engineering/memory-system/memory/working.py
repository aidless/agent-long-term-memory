"""
工作记忆 - 短期上下文窗口，用于当前对话的临时记忆。
"""

import time
import uuid
from collections import OrderedDict
from typing import Any, Optional

from memory.base import BaseMemory, MemoryItem


class WorkingMemory(BaseMemory):
    """
    工作记忆：短期上下文窗口。

    特点：
    - 容量有限（默认 20 条）
    - FIFO 淘汰策略
    - 不持久化到磁盘
    - 自动过期机制
    """

    def __init__(self, capacity: int = 20, ttl_seconds: float = 3600.0, persist_path: Optional[str] = None):
        # 工作记忆不使用持久化
        super().__init__(persist_path=None)
        self.capacity = capacity
        self.ttl_seconds = ttl_seconds
        self._items: OrderedDict[str, MemoryItem] = OrderedDict()

    @property
    def memory_type(self) -> str:
        return "working"

    def add(
        self,
        content: str,
        metadata: Optional[dict] = None,
        importance: float = 0.5,
        **kwargs,
    ) -> MemoryItem:
        """添加一条工作记忆，超出容量时淘汰最早的。"""
        mem_id = kwargs.get("memory_id") or f"work_{uuid.uuid4().hex[:12]}"
        meta = metadata or {}
        meta["memory_type"] = "working"

        item = MemoryItem(
            id=mem_id,
            content=content,
            memory_type="working",
            metadata=meta,
            importance=importance,
        )

        # 超出容量时淘汰
        while len(self._items) >= self.capacity:
            self._items.popitem(last=False)

        self._items[mem_id] = item
        return item

    def get(self, memory_id: str) -> Optional[MemoryItem]:
        """获取工作记忆。"""
        item = self._items.get(memory_id)
        if item and not self._is_expired(item):
            item.access_count += 1
            return item
        if item and self._is_expired(item):
            del self._items[memory_id]
        return None

    def update(self, memory_id: str, content: Optional[str] = None, metadata: Optional[dict] = None, importance: Optional[float] = None) -> Optional[MemoryItem]:
        """更新工作记忆。"""
        item = self._items.get(memory_id)
        if not item or self._is_expired(item):
            return None

        if content is not None:
            item.content = content
        if metadata is not None:
            item.metadata.update(metadata)
        if importance is not None:
            item.importance = importance
        item.updated_at = time.time()
        return item

    def delete(self, memory_id: str) -> bool:
        """删除工作记忆。"""
        if memory_id in self._items:
            del self._items[memory_id]
            return True
        return False

    def search(self, query: str, top_k: int = 10, threshold: float = 0.0) -> list[tuple[MemoryItem, float]]:
        """
        工作记忆搜索 - 使用简单的关键词匹配。
        由于工作记忆不使用向量存储，这里用文本包含判断。
        """
        self._cleanup_expired()
        query_lower = query.lower()
        results: list[tuple[MemoryItem, float]] = []

        for item in self._items.values():
            # 简单的关键词匹配评分
            content_lower = item.content.lower()
            if query_lower in content_lower:
                score = 1.0
            else:
                # 计算重叠词的比例
                query_words = set(query_lower.split())
                content_words = set(content_lower.split())
                if query_words:
                    overlap = len(query_words & content_words)
                    score = overlap / len(query_words)
                else:
                    score = 0.0

            if score >= threshold:
                item.access_count += 1
                results.append((item, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def list_all(self) -> list[MemoryItem]:
        """列出所有未过期的工作记忆。"""
        self._cleanup_expired()
        return list(self._items.values())

    def count(self) -> int:
        """返回未过期的工作记忆数量。"""
        self._cleanup_expired()
        return len(self._items)

    def clear(self) -> None:
        """清空所有工作记忆。"""
        self._items.clear()

    def _is_expired(self, item: MemoryItem) -> bool:
        """判断记忆是否过期。"""
        return (time.time() - item.created_at) > self.ttl_seconds

    def _cleanup_expired(self) -> None:
        """清理所有过期记忆。"""
        expired_ids = [
            mid for mid, item in self._items.items()
            if self._is_expired(item)
        ]
        for mid in expired_ids:
            del self._items[mid]

    def get_context_window(self) -> str:
        """获取当前工作记忆的上下文文本。"""
        self._cleanup_expired()
        items = list(self._items.values())
        items.sort(key=lambda m: m.created_at)
        return "\n".join(f"- {item.content}" for item in items)