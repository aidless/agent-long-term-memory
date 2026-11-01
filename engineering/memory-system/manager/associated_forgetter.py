"""
关联遗忘 - 遗忘触发关联记忆处置（R2.3 缺口补全）。

背景：
    R2.3 指出「关联遗忘」是设计空间缺口——遗忘一条记忆时，关联记忆的处置
    未定义。R2.1 显示关联是记忆系统的核心优势（记忆通过关联更自主），但
    关联的**生命周期**（何时断联、何时一起遗忘）是缺口。

关联遗忘策略：
    当一条记忆被遗忘（删除）时：
    1. **级联遗忘**：若关联记忆依赖被遗忘记忆（无独立价值），一起遗忘。
    2. **断联**：若关联记忆有独立价值，仅断开关联（保留记忆本身）。
    3. **降级**：关联记忆的重要性降低（失去关联源，重要性下降）。

复现：
    pytest engineering/memory-system/tests/test_conflict.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from memory.base import MemoryItem


@dataclass
class AssociationConfig:
    """关联遗忘配置。"""
    cascade_threshold: float = 0.2  # 关联记忆重要性低于此阈值 → 级联遗忘
    cascade_min_importance: float = 0.3  # 关联记忆的独立价值阈值
    importance_decay: float = 0.1  # 断联时的重要性衰减系数


class AssociatedForgetter:
    """
    关联遗忘器。

    管理记忆的关联生命周期：
    - 关联记忆有独立价值（importance ≥ 阈值）：仅断联，保留记忆。
    - 关联记忆无独立价值（importance < 阈值）：级联遗忘（一起删除）。
    - 断联时降低重要性（失去关联源）。
    """

    def __init__(self, config: Optional[AssociationConfig] = None):
        self.config = config or AssociationConfig()

    def decide(self, associated: MemoryItem) -> str:
        """决定关联记忆的处置。

        Args:
            associated: 被遗忘记忆的关联记忆

        Returns:
            "cascade"（级联遗忘）| "disconnect"（断联保留）
        """
        if associated.importance < self.config.cascade_threshold:
            return "cascade"
        return "disconnect"

    def apply_disconnect(self, associated: MemoryItem) -> MemoryItem:
        """断联：降低关联记忆的重要性（失去关联源）。

        Args:
            associated: 关联记忆

        Returns:
            更新后的记忆（重要性降低）
        """
        # 降低重要性（但不低于最小阈值）
        new_importance = max(
            self.config.cascade_min_importance,
            associated.importance - self.config.importance_decay,
        )
        # 返回更新后的记忆（副本）
        updated = MemoryItem(
            id=associated.id,
            content=associated.content,
            memory_type=associated.memory_type,
            importance=new_importance,
            created_at=associated.created_at,
            updated_at=associated.updated_at,
            metadata=dict(associated.metadata or {}),
            access_count=associated.access_count,
        )
        return updated

    def forget_with_associates(
        self,
        forgotten: MemoryItem,
        associates: list[MemoryItem],
    ) -> tuple[list[MemoryItem], list[MemoryItem]]:
        """处理被遗忘记忆的关联记忆。

        Args:
            forgotten: 被遗忘的记忆
            associates: 关联记忆列表

        Returns:
            (级联遗忘的关联记忆列表, 断联保留的关联记忆列表)
        """
        cascade = []
        disconnected = []
        for assoc in associates:
            decision = self.decide(assoc)
            if decision == "cascade":
                cascade.append(assoc)
            else:
                disconnected.append(self.apply_disconnect(assoc))
        return cascade, disconnected
