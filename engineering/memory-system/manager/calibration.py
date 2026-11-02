"""
记忆校准 - 程序记忆陈化检测 + 重要性校准（R2.3 剩余缺口补全）。

背景：
    设计空间（design-space.md 缺口 3/4）指出：
    - 缺口 3 程序记忆陈化：技能随环境变化陈化，需要「技能失效」机制而非纯时间衰减。
    - 缺口 4 重要性校准：重要性评分的主观性，需要与遗忘策略联动校准。

本模块实现两个组件：
    1. ProceduralStalenessDetector：检测程序记忆（技能）是否陈化失效。
       - 陈化 = 技能失败过多（成功率低）OR 长期未用且低重要性。
       - 与纯时间衰减区分：陈化是「技能失效」（环境变了），不是「变旧」。
    2. ImportanceCalibrator：从使用反馈校准重要性。
       - importance = clip(manual_base + access_bonus + recency_bonus - penalty)
       - 校准后的重要性直接喂给遗忘器，实现「重要性 ↔ 遗忘」联动。

复现：
    pytest engineering/memory-system/tests/test_calibration.py
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

from memory.base import MemoryItem


@dataclass
class StalenessConfig:
    """程序记忆陈化检测配置。"""
    min_success_rate: float = 0.4  # 低于此成功率 → 技能失效（失败过多）
    min_usage_count: int = 5  # 至少需要这么多次使用才有统计意义
    stale_after_days: float = 90.0  # 未使用超过此天数 → 可能陈化
    stale_importance_threshold: float = 0.3  # 长期未用且重要性低于此 → 陈化
    recent_failure_window: float = 30.0  # 近期失败窗口（天）
    recent_failure_threshold: int = 3  # 近期失败次数阈值


@dataclass
class CalibrationConfig:
    """重要性校准配置。"""
    manual_base_weight: float = 0.5  # 手动设定基础重要性的权重
    access_bonus_weight: float = 0.3  # 访问频率奖励权重
    access_bonus_cap: float = 0.2  # 访问频率奖励上限
    recency_bonus_weight: float = 0.2  # 近期使用奖励权重
    recency_window_days: float = 30.0  # 近期窗口
    failure_penalty: float = 0.1  # 每次失败的惩罚
    stale_penalty: float = 0.2  # 陈化惩罚
    min_importance: float = 0.05  # 重要性下限
    max_importance: float = 1.0  # 重要性上限


class ProceduralStalenessDetector:
    """
    程序记忆陈化检测器。

    检测一条程序记忆（技能）是否陈化失效。陈化 ≠ 变旧：
    - 变旧：纯时间衰减（forgetter 处理）
    - 陈化：技能失效——失败过多 / 长期未用且低重要性 / 近期失败级联

    陈化的技能应被标记（stale），供上层决定降级或淘汰。
    """

    def __init__(self, config: Optional[StalenessConfig] = None):
        self.config = config or StalenessConfig()

    def is_stale(
        self,
        item: MemoryItem,
        current_time: Optional[float] = None,
    ) -> bool:
        """
        判断一条程序记忆是否陈化。

        判据（任一成立即陈化）：
        1. **失败过多**：成功率 < min_success_rate 且使用次数 ≥ min_usage_count
        2. **长期未用且低重要性**：未使用超 stale_after_days 且 importance < stale_importance_threshold
        3. **近期失败级联**：近期（recent_failure_window 内）失败 ≥ recent_failure_threshold 次

        Args:
            item: 程序记忆项
            current_time: 当前时间（默认 now）

        Returns:
            True 表示陈化
        """
        if current_time is None:
            current_time = time.time()

        meta = item.metadata or {}
        success_count = meta.get("success_count", 0)
        failure_count = meta.get("failure_count", 0)
        total_usage = success_count + failure_count

        # 判据 1：失败过多（成功率低）
        if total_usage >= self.config.min_usage_count:
            success_rate = success_count / total_usage
            if success_rate < self.config.min_success_rate:
                return True

        # 判据 2：长期未用且低重要性
        last_used_at = meta.get("last_used_at")
        if last_used_at is not None:
            days_since_use = (current_time - last_used_at) / 86400.0
            if (
                days_since_use > self.config.stale_after_days
                and item.importance < self.config.stale_importance_threshold
            ):
                return True

        # 判据 3：近期失败级联
        recent_failures = meta.get("recent_failures", [])
        if len(recent_failures) >= self.config.recent_failure_threshold:
            window_start = current_time - self.config.recent_failure_window * 86400.0
            recent_count = sum(
                1 for ts in recent_failures if ts >= window_start
            )
            if recent_count >= self.config.recent_failure_threshold:
                return True

        return False

    def find_stale(
        self,
        items: list[MemoryItem],
        current_time: Optional[float] = None,
    ) -> list[MemoryItem]:
        """找出所有陈化的程序记忆。"""
        return [
            m for m in items
            if self.is_stale(m, current_time)
        ]


class ImportanceCalibrator:
    """
    重要性校准器。

    从使用反馈动态校准重要性，解决主观静态赋值问题：
    - 手动基础重要性（用户/提取器设定）
    - 访问频率奖励（越常用越重要）
    - 近期使用奖励（越近使用越重要）
    - 失败惩罚（技能总失败 → 重要性降低）
    - 陈化惩罚（技能陈化 → 重要性降低）

    校准后的重要性直接喂给遗忘器（forgetter.compute_retention_score），
    实现「重要性 ↔ 遗忘」联动——高重要性记忆不易被遗忘，低重要性易被遗忘。
    """

    def __init__(self, config: Optional[CalibrationConfig] = None):
        self.config = config or CalibrationConfig()

    def calibrate(
        self,
        item: MemoryItem,
        current_time: Optional[float] = None,
    ) -> float:
        """
        计算校准后的重要性。

        Args:
            item: 记忆项
            current_time: 当前时间（默认 now）

        Returns:
            校准后的重要性 [min_importance, max_importance]
        """
        if current_time is None:
            current_time = time.time()

        cfg = self.config
        meta = item.metadata or {}

        # 1. 手动基础重要性（用户/提取器设定）
        base = item.importance * cfg.manual_base_weight

        # 2. 访问频率奖励（对数平滑）
        access_bonus = min(
            math.log1p(item.access_count) * cfg.access_bonus_weight,
            cfg.access_bonus_cap,
        )

        # 3. 近期使用奖励
        last_used_at = meta.get("last_used_at")
        recency_bonus = 0.0
        if last_used_at is not None:
            days_since = (current_time - last_used_at) / 86400.0
            if days_since < cfg.recency_window_days:
                recency_bonus = (
                    cfg.recency_bonus_weight
                    * (1.0 - days_since / cfg.recency_window_days)
                )

        # 4. 失败惩罚
        failure_count = meta.get("failure_count", 0)
        failure_penalty = failure_count * cfg.failure_penalty

        # 5. 陈化惩罚（对程序记忆）
        stale_penalty = 0.0
        if item.memory_type == "procedural":
            detector = ProceduralStalenessDetector()
            if detector.is_stale(item, current_time):
                stale_penalty = cfg.stale_penalty

        calibrated = base + access_bonus + recency_bonus - failure_penalty - stale_penalty
        return max(cfg.min_importance, min(cfg.max_importance, calibrated))
