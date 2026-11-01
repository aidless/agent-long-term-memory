"""
程序记忆 - 存储学到的技能和模式。
"""

import uuid
from typing import Any, Optional

from memory.base import BaseMemory, MemoryItem


class ProceduralMemory(BaseMemory):
    """
    程序记忆：存储学到的技能、规则和操作模式。

    特点：
    - 存储可执行的技能描述
    - 支持技能分类
    - 支持成功/失败次数统计
    - 支持按技能名称检索
    """

    @property
    def memory_type(self) -> str:
        return "procedural"

    def add(
        self,
        content: str,
        metadata: Optional[dict] = None,
        importance: float = 0.5,
        **kwargs,
    ) -> MemoryItem:
        """添加一条程序记忆（技能/模式）。"""
        mem_id = kwargs.get("memory_id") or f"proc_{uuid.uuid4().hex[:12]}"
        meta = metadata or {}
        meta["memory_type"] = "procedural"

        # 技能相关元数据
        if "skill_name" not in meta:
            meta["skill_name"] = kwargs.get("skill_name", "")
        if "category" not in meta:
            meta["category"] = kwargs.get("category", "general")
        if "success_count" not in meta:
            meta["success_count"] = kwargs.get("success_count", 0)
        if "failure_count" not in meta:
            meta["failure_count"] = kwargs.get("failure_count", 0)
        if "trigger_conditions" not in meta:
            meta["trigger_conditions"] = kwargs.get("trigger_conditions", [])

        record = self.store.add(
            text=content,
            record_id=mem_id,
            metadata=meta,
            importance=importance,
        )

        return self._record_to_item(record)

    def record_success(self, memory_id: str) -> Optional[MemoryItem]:
        """记录技能使用成功。"""
        item = self.get(memory_id)
        if not item:
            return None
        success = item.metadata.get("success_count", 0) + 1
        return self.update(memory_id, metadata={"success_count": success})

    def record_failure(self, memory_id: str) -> Optional[MemoryItem]:
        """记录技能使用失败。"""
        item = self.get(memory_id)
        if not item:
            return None
        failure = item.metadata.get("failure_count", 0) + 1
        return self.update(memory_id, metadata={"failure_count": failure})

    def get_skill_success_rate(self, memory_id: str) -> Optional[float]:
        """获取技能成功率。"""
        item = self.get(memory_id)
        if not item:
            return None
        success = item.metadata.get("success_count", 0)
        failure = item.metadata.get("failure_count", 0)
        total = success + failure
        if total == 0:
            return None
        return success / total

    def search_by_skill_name(self, skill_name: str, top_k: int = 10) -> list[tuple[MemoryItem, float]]:
        """按技能名称搜索。"""
        results = self.store.search(
            query=skill_name,
            top_k=top_k,
            filter_metadata={"skill_name": skill_name},
        )
        return [(self._record_to_item(r), score) for r, score in results]