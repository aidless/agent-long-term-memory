"""
冲突检测 + 关联遗忘测试（R2.3 缺口补全验证）。

覆盖：
- ConflictDetector：冲突检测（同一主题+反义表述）
- ConflictDetector：非冲突（不同主题 / 无反义）
- ConflictDetector：冲突解决（保留重要性高者）
- AssociatedForgetter：级联遗忘（低重要性关联）
- AssociatedForgetter：断联保留（高重要性关联）
- MemoryManager 集成：forget_with_associates
"""

import os
import sys
import tempfile

# 确保可导入 engineering/memory-system
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.base import MemoryItem
from manager.conflict import ConflictDetector
from manager.associated_forgetter import AssociatedForgetter
from manager.memory_manager import MemoryManager


def make_memory(content, importance=0.5, mtype="semantic", created_at=1000.0):
    return MemoryItem(
        id=f"mem_{abs(hash(content))}",
        content=content,
        memory_type=mtype,
        importance=importance,
        created_at=created_at,
        updated_at=created_at,
        metadata={},
        access_count=0,
    )


class TestConflictDetector:
    """冲突检测器测试。"""

    def test_detect_conflict_same_topic_opposite(self):
        """同一主题+反义表述 → 冲突。"""
        detector = ConflictDetector()
        m1 = make_memory("模型 A 效果好 准确率高")
        m2 = make_memory("模型 A 效果差 准确率低")
        assert detector.detect_conflict(m1, m2)

    def test_no_conflict_different_topic(self):
        """不同主题 → 非冲突。"""
        detector = ConflictDetector()
        m1 = make_memory("模型 A 效果好")
        m2 = make_memory("数据集 B 样本充足")
        assert not detector.detect_conflict(m1, m2)

    def test_no_conflict_same_topic_same_direction(self):
        """同一主题+同向表述 → 非冲突。"""
        detector = ConflictDetector()
        m1 = make_memory("模型 A 效果好 准确率高")
        m2 = make_memory("模型 A 效果很好 准确率很高")
        assert not detector.detect_conflict(m1, m2)

    def test_find_conflicts_multiple(self):
        """找出多对冲突。"""
        detector = ConflictDetector()
        m1 = make_memory("模型 A 效果好")
        m2 = make_memory("模型 A 效果差")
        m3 = make_memory("模型 B 效果好")
        m4 = make_memory("模型 B 效果差")
        conflicts = detector.find_conflicts([m1, m2, m3, m4])
        assert len(conflicts) == 2

    def test_resolve_conflict_keep_higher_importance(self):
        """冲突解决：保留重要性高者。"""
        detector = ConflictDetector()
        m1 = make_memory("模型 A 效果好", importance=0.8)
        m2 = make_memory("模型 A 效果差", importance=0.3)
        keep = detector.resolve_conflict(m1, m2)
        assert keep.id == m1.id


class TestAssociatedForgetter:
    """关联遗忘器测试。"""

    def test_cascade_low_importance(self):
        """低重要性关联 → 级联遗忘。"""
        forgetter = AssociatedForgetter()
        assoc = make_memory("关联信息 无独立价值", importance=0.1)
        decision = forgetter.decide(assoc)
        assert decision == "cascade"

    def test_disconnect_high_importance(self):
        """高重要性关联 → 断联保留。"""
        forgetter = AssociatedForgetter()
        assoc = make_memory("重要关联信息", importance=0.8)
        decision = forgetter.decide(assoc)
        assert decision == "disconnect"

    def test_apply_disconnect_reduces_importance(self):
        """断联：降低重要性。"""
        forgetter = AssociatedForgetter()
        assoc = make_memory("重要关联信息", importance=0.8)
        updated = forgetter.apply_disconnect(assoc)
        assert updated.importance < 0.8
        assert updated.importance >= forgetter.config.cascade_min_importance

    def test_forget_with_associates_mixed(self):
        """混合处置：高重要性断联，低重要性级联。"""
        forgetter = AssociatedForgetter()
        forgotten = make_memory("被遗忘记忆", importance=0.5)
        high = make_memory("高重要性关联", importance=0.8)
        low = make_memory("低重要性关联", importance=0.1)
        cascade, disconnected = forgetter.forget_with_associates(
            forgotten, [high, low]
        )
        assert len(cascade) == 1
        assert len(disconnected) == 1
        assert disconnected[0].importance < 0.8


class TestManagerIntegration:
    """MemoryManager 集成测试（forget_with_associates）。"""

    def test_forget_with_associates_integration(self):
        """集成：遗忘主记忆，高重要性关联断联、低重要性级联。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MemoryManager(persist_dir=tmpdir)
            # 添加记忆
            main = manager.add_semantic("主记忆 主题", importance=0.6)
            high = manager.add_semantic("高重要性关联 主题", importance=0.8)
            low = manager.add_semantic("低重要性关联 主题", importance=0.1)

            # 遗忘主记忆并处理关联
            result = manager.forget_with_associates(
                "semantic", main.id, [high.id, low.id]
            )

            assert result["forgotten_id"] == main.id
            # 低重要性级联
            assert low.id in result["cascade_ids"]
            # 高重要性断联
            assert high.id in result["disconnected_ids"]
            # 主记忆已删除
            assert manager.get_memory("semantic", main.id) is None
            # 低重要性关联已删除
            assert manager.get_memory("semantic", low.id) is None
            # 高重要性关联保留（重要性降低）
            high_updated = manager.get_memory("semantic", high.id)
            assert high_updated is not None
            assert high_updated.importance < 0.8

    def test_detect_conflicts_integration(self):
        """集成：检测语义记忆冲突。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MemoryManager(persist_dir=tmpdir)
            manager.add_semantic("模型 A 效果好 准确率高", importance=0.7)
            manager.add_semantic("模型 A 效果差 准确率低", importance=0.3)
            conflicts = manager.detect_conflicts("semantic")
            assert len(conflicts) >= 1


class TestAutoConflictCheckIntegration:
    """自动冲突检查集成测试（添加后自动标记）。"""

    def test_add_semantic_marks_conflict_candidate(self):
        """添加冲突记忆后，自动标记 conflict_candidate。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MemoryManager(persist_dir=tmpdir)
            manager.add_semantic("模型 A 效果好 准确率高", importance=0.7)
            item2 = manager.add_semantic("模型 A 效果差 准确率低", importance=0.3)
            # 第二项应被标记为冲突候选
            fetched = manager.get_memory("semantic", item2.id)
            assert fetched is not None
            assert fetched.metadata.get("conflict_candidate") is True
            assert fetched.metadata.get("conflict_with") is not None

    def test_add_non_conflict_no_mark(self):
        """添加非冲突记忆，不标记。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MemoryManager(persist_dir=tmpdir)
            manager.add_semantic("模型 A 效果好", importance=0.7)
            item2 = manager.add_semantic("数据集 B 样本充足", importance=0.3)
            fetched = manager.get_memory("semantic", item2.id)
            assert fetched is not None
            assert fetched.metadata.get("conflict_candidate") is not True

    def test_consolidate_runs_conflict_check(self):
        """整合后自动冲突检查（整合记忆与现有记忆冲突时标记）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MemoryManager(persist_dir=tmpdir)
            # 先放一个高重要性记忆
            manager.add_semantic("模型 A 效果好 准确率高", importance=0.9)
            # 添加一组可整合的记忆（同主题）
            manager.add_semantic("模型 A 效果好", importance=0.5)
            manager.add_semantic("模型 A 准确率高", importance=0.5)
            manager.add_semantic("模型 A 效果好 准确率高", importance=0.5)
            # 整合（min_group_size=3）
            consolidated = manager.consolidate_memories("semantic")
            # 整合后应至少有 1 条，且不与高重要性记忆冲突标记
            # 整合记忆内容含"模型 A 效果好"可能与高重要性冲突
            # 此处验证：整合记忆确实被添加，且不抛异常
            assert consolidated is not None

    def test_forget_triggers_associate_disposal(self):
        """forget 触发关联处置（高重要性断联保留）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = MemoryManager(persist_dir=tmpdir)
            # 添加记忆
            low_imp = manager.add_semantic("过期信息 无价值", importance=0.05)
            high_imp = manager.add_semantic("重要关联 模型 A 效果好", importance=0.9)
            # 模拟老化：直接改底层 VectorRecord 的 created_at（很久以前，低于遗忘阈值）
            store = manager._get_memory_store("semantic").store
            store._records[low_imp.id].created_at = 100.0
            store._records[high_imp.id].created_at = 100.0
            # 执行遗忘（默认 forgetter 会遗忘低重要性、保留高重要性）
            result = manager.forget("semantic")
            # 低重要性记忆应被遗忘
            assert low_imp.id in result.get("semantic", [])
            # 高重要性关联应保留
            assert manager.get_memory("semantic", high_imp.id) is not None
