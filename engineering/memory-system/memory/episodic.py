"""
情景记忆 - 存储过去的交互和经历。
"""

import time
import uuid
from typing import Any, Optional

from memory.base import BaseMemory, MemoryItem


class EpisodicMemory(BaseMemory):
    """
    情景记忆：存储过去的交互、事件和经历。

    特点：
    - 带时间戳的事件记录
    - 支持情感标注
    - 支持场景和参与者记录
    - 按时间线检索
    """

    @property
    def memory_type(self) -> str:
        return "episodic"

    def add(
        self,
        content: str,
        metadata: Optional[dict] = None,
        importance: float = 0.5,
        **kwargs,
    ) -> MemoryItem:
        """添加一条情景记忆（交互/经历）。"""
        mem_id = kwargs.get("memory_id") or f"epi_{uuid.uuid4().hex[:12]}"
        meta = metadata or {}
        meta["memory_type"] = "episodic"

        # 情景相关元数据
        if "timestamp" not in meta:
            meta["timestamp"] = kwargs.get("timestamp", time.time())
        if "emotion" not in meta:
            meta["emotion"] = kwargs.get("emotion", "neutral")
        if "participants" not in meta:
            meta["participants"] = kwargs.get("participants", [])
        if "context" not in meta:
            meta["context"] = kwargs.get("context", "")

        record = self.store.add(
            text=content,
            record_id=mem_id,
            metadata=meta,
            importance=importance,
        )

        return self._record_to_item(record)

    def get_timeline(self, start_time: Optional[float] = None, end_time: Optional[float] = None) -> list[MemoryItem]:
        """获取时间线上的情景记忆。"""
        all_memories = self.list_all()
        if start_time is not None:
            all_memories = [m for m in all_memories if m.created_at >= start_time]
        if end_time is not None:
            all_memories = [m for m in all_memories if m.created_at <= end_time]
        all_memories.sort(key=lambda m: m.created_at)
        return all_memories

    def search_by_emotion(self, emotion: str, top_k: int = 10) -> list[tuple[MemoryItem, float]]:
        """按情感搜索情景记忆。"""
        results = self.store.search(
            query=emotion,
            top_k=top_k,
            filter_metadata={"emotion": emotion},
        )
        return [(self._record_to_item(r), score) for r, score in results]

    def get_recent(self, n: int = 5) -> list[MemoryItem]:
        """获取最近的 n 条情景记忆。"""
        all_memories = self.list_all()
        all_memories.sort(key=lambda m: m.created_at, reverse=True)
        return all_memories[:n]