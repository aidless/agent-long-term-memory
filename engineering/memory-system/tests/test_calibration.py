"""
程序记忆陈化检测 + 重要性校准测试（R2.3 剩余缺口补全验证）。

覆盖：
- ProceduralStalenessDetector：失败过多 → 陈化
- ProceduralStalenessDetector：长期未用且低重要性 → 陈化
- ProceduralStalenessDetector：近期失败级联 → 陈化
- ProceduralStalenessDetector：健康技能 → 不陈化
- ImportanceCalibrator：访问频率奖励
- ImportanceCalibrator：失败惩罚
- ImportanceCalibrator：陈化惩罚（程序记忆）
- ImportanceCalibrator：校准后重要性限制在 [min, max]
"""

import os
import sys
import time
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.base import MemoryItem
from manager.calibration import (
    ProceduralStalenessDetector,
    ImportanceCalibrator,
)
from manager.memory_manager import MemoryManager


def make_procedural(
    content,
    importance=0.5,
    success_count=0,
    failure_count=0,
    last_used_at=None,
    recent_failures=None,
    created_at=1000.0,
):
    return MemoryItem(
        id=f"proc_{abs(hash(content))}",
        content=content,
        memory_type="procedural",
        importance=importance,
        created_at=created_at,
        updated_at=created_at,
        metadata={
            "success_count": success_count,
            "failure_count": failure_count,
            "last_used_at": last_used_at,
            "recent_failures": recent_failures or [],
        },
        access_count=0,
    )


class TestProceduralStalenessDetector:
    """程序记忆陈化检测测试。"""

    def test_stale_too_many_failures(self):
        """失败过多 → 陈化。"""
        detector = ProceduralStalenessDetector()
        # 成功率 20% < 40% 阈值，使用次数 10 ≥ 5
        item = make_procedural(
            "技能 A", success_count=2, failure_count=8
        )
        assert detector.is_stale(item)

    def test_not_stale_healthy_skill(self):
        """健康技能（成功率 90%）→ 不陈化。"""
        detector = ProceduralStalenessDetector()
        item = make_procedural(
            "技能 A", success_count=9, failure_count=1
        )
        assert not detector.is_stale(item)

    def test_stale_long_unused_low_importance(self):
        """长期未用且低重要性 → 陈化。"""
        detector = ProceduralStalenessDetector()
        now = time.time()
        # 未使用 120 天（>90 天），重要性 0.2（<0.3）
        item = make_procedural(
            "技能 A",
            importance=0.2,
            last_used_at=now - 120 * 86400.0,
        )
        assert detector.is_stale(item)

    def test_not_stale_long_unused_high_importance(self):
        """长期未用但高重要性 → 不陈化（重要技能保留）。"""
        detector = ProceduralStalenessDetector()
        now = time.time()
        item = make_procedural(
            "技能 A",
            importance=0.8,
            last_used_at=now - 120 * 86400.0,
        )
        assert not detector.is_stale(item)

    def test_stale_recent_failure_cascade(self):
        """近期失败级联 → 陈化。"""
        detector = ProceduralStalenessDetector()
        now = time.time()
        # 近期（30 天内）失败 4 次（≥3 阈值）
        item = make_procedural(
            "技能 A",
            success_count=10,
            failure_count=4,
            last_used_at=now - 86400.0,
            recent_failures=[
                now - 1 * 86400.0,
                now - 2 * 86400.0,
                now - 3 * 86400.0,
                now - 4 * 86400.0,
            ],
        )
        assert detector.is_stale(item)

    def test_find_stale_multiple(self):
        """找出所有陈化的程序记忆。"""
        detector = ProceduralStalenessDetector()
        now = time.time()
        stale = make_procedural("技能 A", success_count=1, failure_count=9)
        healthy = make_procedural("技能 B", success_count=9, failure_count=1)
        stale_items = detector.find_stale([stale, healthy])
        assert len(stale_items) == 1
        assert stale_items[0].content == "技能 A"


class TestImportanceCalibrator:
    """重要性校准测试。"""

    def test_calibrate_access_bonus(self):
        """访问频率奖励：高访问 → 重要性提升。"""
        calibrator = ImportanceCalibrator()
        now = time.time()
        low_access = make_procedural("技能 A", importance=0.5, last_used_at=now - 86400.0)
        low_access.access_count = 0
        high_access = make_procedural("技能 A", importance=0.5, last_used_at=now - 86400.0)
        high_access.access_count = 50
        low_cal = calibrator.calibrate(low_access, now)
        high_cal = calibrator.calibrate(high_access, now)
        assert high_cal > low_cal

    def test_calibrate_failure_penalty(self):
        """失败惩罚：失败多 → 重要性降低。"""
        calibrator = ImportanceCalibrator()
        now = time.time()
        no_fail = make_procedural("技能 A", importance=0.5, failure_count=0, last_used_at=now - 86400.0)
        many_fail = make_procedural("技能 A", importance=0.5, failure_count=5, last_used_at=now - 86400.0)
        no_fail_cal = calibrator.calibrate(no_fail, now)
        many_fail_cal = calibrator.calibrate(many_fail, now)
        assert many_fail_cal < no_fail_cal

    def test_calibrate_bounds(self):
        """校准后重要性限制在 [min, max]。"""
        calibrator = ImportanceCalibrator()
        now = time.time()
        # 极低重要性 + 大量失败 → 应达到下限
        item = make_procedural(
            "技能 A", importance=0.01, failure_count=100, last_used_at=now
        )
        cal = calibrator.calibrate(item, now)
        assert cal >= calibrator.config.min_importance

    def test_calibrate_recency_bonus(self):
        """近期使用奖励：最近使用 → 重要性略高。"""
        calibrator = ImportanceCalibrator()
        now = time.time()
        recent = make_procedural("技能 A", importance=0.5, last_used_at=now - 86400.0)
        old = make_procedural("技能 A", importance=0.5, last_used_at=now - 60 * 86400.0)
        recent_cal = calibrator.calibrate(recent, now)
        old_cal = calibrator.calibrate(old, now)
        assert recent_cal > old_cal


class TestCalibrationIntegration:
    """MemoryManager 集成测试（陈化检测 + 重要性校准）。"""

    def test_manager_detect_stale_procedural(self):
        """集成：MemoryManager 检测陈化的程序记忆。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MemoryManager(persist_dir=tmpdir)
            # 添加一个失败过多的程序记忆
            item = manager.add_procedural(
                "技能 A 失败过多", importance=0.5, success_count=1, failure_count=9
            )
            # 陈化检测
            stale = manager.detect_stale_procedural()
            assert item.id in [m.id for m in stale]

    def test_manager_calibrate_importance(self):
        """集成：MemoryManager 校准重要性。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MemoryManager(persist_dir=tmpdir)
            # 添加程序记忆（失败多）
            item = manager.add_procedural(
                "技能 A", importance=0.5, success_count=1, failure_count=9
            )
            calibrated = manager.calibrate_importance("procedural", item.id)
            assert calibrated is not None
            assert calibrated < 0.5  # 失败惩罚 → 重要性降低
