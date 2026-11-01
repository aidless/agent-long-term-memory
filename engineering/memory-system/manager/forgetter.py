"""
记忆遗忘 - 基于衰减和容量限制的记忆遗忘机制。
"""

import math
import time
from dataclasses import dataclass
from typing import Optional

from memory.base import MemoryItem


@dataclass
class ForgetConfig:
    """遗忘配置。"""
    max_capacity: int = 1000  # 最大记忆容量
    decay_half_life: float = 86400.0 * 30  # 半衰期 30 天
    forget_threshold: float = 0.05  # 低于此阈值的记忆被遗忘
    importance_boost: float = 0.3  # 重要性对遗忘的缓冲系数
    access_boost: float = 0.1  # 访问频率对遗忘的缓冲系数


class MemoryForgetter:
    """
    记忆遗忘器。

    基于指数衰减函数和容量限制实现记忆遗忘：
    1. 时间衰减：使用指数衰减函数计算记忆的保留分数
    2. 容量限制：当记忆超过最大容量时，淘汰分数最低的记忆
    3. 重要性保护：高重要性的记忆不容易被遗忘
    4. 访问保护：频繁访问的记忆不容易被遗忘
    """

    def __init__(self, config: Optional[ForgetConfig] = None):
        self.config = config or ForgetConfig()

    def compute_retention_score(self, memory: MemoryItem, current_time: Optional[float] = None) -> float:
        """
        计算记忆的保留分数。

        保留分数 = 时间衰减分数 + 重要性加成 + 访问频率加成

        Args:
            memory: 记忆条目
            current_time: 当前时间

        Returns:
            保留分数 [0, 1]
        """
        if current_time is None:
            current_time = time.time()

        # 1. 时间衰减
        age = current_time - memory.created_at
        if age <= 0:
            time_score = 1.0
        else:
            lambda_val = math.log(2) / self.config.decay_half_life
            time_score = math.exp(-lambda_val * age)

        # 2. 重要性加成
        importance_bonus = memory.importance * self.config.importance_boost

        # 3. 访问频率加成（对数平滑）
        access_bonus = min(math.log1p(memory.access_count) * self.config.access_boost, 0.3)

        retention = time_score + importance_bonus + access_bonus
        return max(0.0, min(1.0, retention))

    def should_forget(self, memory: MemoryItem, current_time: Optional[float] = None) -> bool:
        """
        判断一条记忆是否应该被遗忘。

        Args:
            memory: 记忆条目
            current_time: 当前时间

        Returns:
            True 表示应该遗忘
        """
        score = self.compute_retention_score(memory, current_time)
        return score < self.config.forget_threshold

    def get_forgettable(
        self,
        memories: list[MemoryItem],
        current_time: Optional[float] = None,
    ) -> list[MemoryItem]:
        """
        获取应该被遗忘的记忆列表。

        Args:
            memories: 所有记忆
            current_time: 当前时间

        Returns:
            应该被遗忘的记忆列表
        """
        return [
            m for m in memories
            if self.should_forget(m, current_time)
        ]

    def enforce_capacity(
        self,
        memories: list[MemoryItem],
        current_time: Optional[float] = None,
    ) -> list[str]:
        """
        执行容量限制。

        当记忆数量超过最大容量时，淘汰保留分数最低的记忆。

        Args:
            memories: 所有记忆
            current_time: 当前时间

        Returns:
            被淘汰的记忆 ID 列表
        """
        if len(memories) <= self.config.max_capacity:
            return []

        # 计算所有记忆的保留分数
        scored = [
            (m, self.compute_retention_score(m, current_time))
            for m in memories
        ]
        scored.sort(key=lambda x: x[1])

        # 淘汰超出容量的部分
        excess = len(memories) - self.config.max_capacity
        to_forget = [m.id for m, _ in scored[:excess]]

        return to_forget

    def forget(
        self,
        memories: list[MemoryItem],
        current_time: Optional[float] = None,
    ) -> tuple[list[str], list[MemoryItem]]:
        """
        执行完整的遗忘流程。

        1. 基于衰减淘汰
        2. 基于容量淘汰

        Args:
            memories: 所有记忆
            current_time: 当前时间

        Returns:
            (被遗忘的记忆 ID 列表, 保留的记忆列表)
        """
        now = current_time or time.time()

        # 1. 基于衰减淘汰
        retained = [m for m in memories if not self.should_forget(m, now)]
        forgotten_ids = [m.id for m in memories if m.id not in {r.id for r in retained}]

        # 2. 基于容量淘汰
        capacity_forgotten = self.enforce_capacity(retained, now)
        forgotten_ids.extend(capacity_forgotten)
        retained = [m for m in retained if m.id not in set(capacity_forgotten)]

        return forgotten_ids, retained