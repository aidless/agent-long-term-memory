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
    # v8: tier 概率遗忘（从 forgetting-js v7 direction ② 移植）
    tier_probabilistic: bool = False  # 开启后按 tier forgetRate 概率准入（非一次全部淘汰）
    tier_seed: Optional[int] = None   # 随机种子（None = 系统随机，测试用固定种子）


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
        # v8: tier 概率遗忘需要随机源（固定种子可复现）
        import random
        self._rng = random.Random(self.config.tier_seed) if self.config.tier_seed is not None else random.Random()

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

    def tiered_forget_rate(self, score: float) -> tuple[int, float]:
        """
        按保留分数计算 tier 与 forgetRate（从 forgetting-js v7 direction ② 移植）。

        语义：分数越低，tier 越低，forgetRate 越高（更可能被遗忘）。
        - tier 4: score >= 0.8, rate=0.0（核心，永不遗忘）
        - tier 3: score >= 0.55, rate=0.15（重要，低遗忘率）
        - tier 2: score >= 0.3, rate=0.40（次要，中遗忘率）
        - tier 1: score < 0.3, rate=0.65（不重要，高遗忘率）
        """
        if score >= 0.8:
            return (4, 0.0)
        elif score >= 0.55:
            return (3, 0.15)
        elif score >= 0.3:
            return (2, 0.40)
        else:
            return (1, 0.65)

    def enforce_capacity(
        self,
        memories: list[MemoryItem],
        current_time: Optional[float] = None,
    ) -> list[str]:
        """
        执行容量限制。

        当记忆数量超过最大容量时，淘汰保留分数最低的记忆。
        若 tier_probabilistic 开启，按 tier forgetRate 概率准入淘汰候选
        （避免一次清空低分群体，与 v7 direction ② 语义一致）。

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

        if self.config.tier_probabilistic:
            # v8: tier 概率淘汰——每个候选按对应 tier 的 forgetRate 概率准入
            # 避免一次清空低分群体（连续分数：0.55→~15%/pass，0.10→~65%/pass）
            to_forget = []
            for m, score in scored[:excess]:
                _, rate = self.tiered_forget_rate(score)
                if self._rng.random() < rate:
                    to_forget.append(m.id)
            return to_forget

        # 确定性淘汰（默认）
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