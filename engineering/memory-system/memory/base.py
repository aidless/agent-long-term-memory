"""
记忆基类 - 定义所有记忆类型的通用接口和数据结构。
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from vector_store.simple_vector import SimpleVectorStore


@dataclass
class MemoryItem:
    """记忆条目的基础数据结构。"""

    id: str
    content: str
    memory_type: str  # semantic, episodic, procedural, working
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    importance: float = 0.5
    embedding: list[float] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
            "importance": self.importance,
            "embedding": self.embedding,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryItem":
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=data["memory_type"],
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            access_count=data.get("access_count", 0),
            importance=data.get("importance", 0.5),
            embedding=data.get("embedding", []),
            extra=data.get("extra", {}),
        )


class BaseMemory(ABC):
    """所有记忆类型的抽象基类。"""

    def __init__(self, persist_path: Optional[str] = None):
        self.persist_path = persist_path
        self.store = SimpleVectorStore(persist_path=persist_path)

    @property
    @abstractmethod
    def memory_type(self) -> str:
        """返回记忆类型名称。"""
        ...

    @abstractmethod
    def add(self, content: str, metadata: Optional[dict] = None, importance: float = 0.5, **kwargs) -> MemoryItem:
        """添加一条记忆。"""
        ...

    def get(self, memory_id: str) -> Optional[MemoryItem]:
        """根据 ID 获取记忆。"""
        record = self.store.get(memory_id)
        if record:
            return self._record_to_item(record)
        return None

    def update(self, memory_id: str, content: Optional[str] = None, metadata: Optional[dict] = None, importance: Optional[float] = None) -> Optional[MemoryItem]:
        """更新记忆。"""
        record = self.store.update(memory_id, text=content, metadata=metadata, importance=importance)
        if record:
            return self._record_to_item(record)
        return None

    def delete(self, memory_id: str) -> bool:
        """删除记忆。"""
        return self.store.delete(memory_id)

    def search(self, query: str, top_k: int = 10, threshold: float = 0.0) -> list[tuple[MemoryItem, float]]:
        """搜索记忆。"""
        results = self.store.search(query, top_k=top_k, threshold=threshold)
        return [(self._record_to_item(r), score) for r, score in results]

    def list_all(self) -> list[MemoryItem]:
        """列出所有记忆。"""
        return [self._record_to_item(r) for r in self.store.list_all()]

    def count(self) -> int:
        """返回记忆数量。"""
        return self.store.count()

    def clear(self) -> None:
        """清空所有记忆。"""
        self.store.clear()

    def _record_to_item(self, record) -> MemoryItem:
        """将 VectorRecord 转换为 MemoryItem。"""
        return MemoryItem(
            id=record.id,
            content=record.text,
            memory_type=self.memory_type,
            metadata=record.metadata,
            created_at=record.created_at,
            updated_at=record.updated_at,
            access_count=record.access_count,
            importance=record.importance,
            embedding=record.vector,
        )