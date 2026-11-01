"""
测试记忆管理器 - 统一管理接口、遗忘和整合。
"""

import time
import pytest

from manager.memory_manager import MemoryManager
from manager.forgetter import MemoryForgetter, ForgetConfig
from manager.consolidator import MockLLMConsolidator
from memory.base import MemoryItem


class TestMemoryManager:
    """记忆管理器测试。"""

    def setup_method(self):
        self.manager = MemoryManager()

    def test_add_semantic(self):
        """测试添加语义记忆。"""
        item = self.manager.add_semantic("Python 是一种编程语言")
        assert item.memory_type == "semantic"
        assert "Python" in item.content

    def test_add_episodic(self):
        """测试添加情景记忆。"""
        item = self.manager.add_episodic("用户问了关于天气的问题")
        assert item.memory_type == "episodic"

    def test_add_procedural(self):
        """测试添加程序记忆。"""
        item = self.manager.add_procedural("发送邮件的步骤", skill_name="send_email")
        assert item.memory_type == "procedural"
        assert item.metadata["skill_name"] == "send_email"

    def test_add_working(self):
        """测试添加工作记忆。"""
        item = self.manager.add_working("临时上下文")
        assert item.memory_type == "working"

    def test_search(self):
        """测试混合检索。"""
        self.manager.add_semantic("Python 是一种编程语言")
        self.manager.add_episodic("讨论了 Python 的用法")
        results = self.manager.search("Python")
        assert len(results) >= 1

    def test_search_by_type(self):
        """测试按类型检索。"""
        self.manager.add_semantic("语义知识")
        self.manager.add_episodic("情景事件")
        self.manager.add_procedural("程序技能")

        sem_results = self.manager.search_semantic_only("知识")
        assert all(r.memory.memory_type == "semantic" for r in sem_results)

    def test_update_and_delete(self):
        """测试更新和删除记忆。"""
        item = self.manager.add_semantic("原始内容")
        updated = self.manager.update_memory("semantic", item.id, content="更新后的内容")
        assert updated is not None
        assert updated.content == "更新后的内容"

        deleted = self.manager.delete_memory("semantic", item.id)
        assert deleted is True
        assert self.manager.get_memory("semantic", item.id) is None

    def test_get_stats(self):
        """测试获取统计信息。"""
        self.manager.add_semantic("知识一")
        self.manager.add_episodic("事件一")
        self.manager.add_procedural("技能一")
        self.manager.add_working("上下文一")

        stats = self.manager.get_stats()
        assert stats["semantic_count"] == 1
        assert stats["episodic_count"] == 1
        assert stats["procedural_count"] == 1
        assert stats["working_count"] == 1
        assert stats["total_long_term"] == 3

    def test_clear_all(self):
        """测试清空所有记忆。"""
        self.manager.add_semantic("知识")
        self.manager.add_episodic("事件")
        self.manager.clear_all()
        stats = self.manager.get_stats()
        assert stats["total_long_term"] == 0
        assert stats["working_count"] == 0

    def test_extract_and_store(self):
        """测试自动提取和存储记忆。"""
        stored = self.manager.extract_and_store("我叫张三，我喜欢编程。")
        assert len(stored) >= 1

    def test_reference_tracking(self):
        """测试记忆引用追踪。"""
        item = self.manager.add_semantic("重要的知识")
        self.manager.search("重要的知识")
        history = self.manager.get_reference_history(item.id)
        assert len(history) >= 1


class TestMemoryForgetter:
    """记忆遗忘器测试。"""

    def test_retention_score_new_memory(self):
        """测试新记忆的保留分数。"""
        forgetter = MemoryForgetter()
        memory = MemoryItem(
            id="test_1",
            content="新记忆",
            memory_type="semantic",
            created_at=time.time(),
            importance=0.5,
        )
        score = forgetter.compute_retention_score(memory)
        assert score > 0.9  # 新记忆应该有很高的保留分数

    def test_retention_score_old_low_importance(self):
        """测试旧的低重要性记忆应该被遗忘。"""
        config = ForgetConfig(
            decay_half_life=1.0,  # 1秒半衰期
            forget_threshold=0.5,
        )
        forgetter = MemoryForgetter(config=config)

        memory = MemoryItem(
            id="old_1",
            content="旧记忆",
            memory_type="semantic",
            created_at=time.time() - 100,  # 100秒前
            importance=0.0,
        )
        score = forgetter.compute_retention_score(memory)
        assert score < 0.5

    def test_should_forget(self):
        """测试遗忘判断。"""
        config = ForgetConfig(
            decay_half_life=1.0,
            forget_threshold=0.5,
        )
        forgetter = MemoryForgetter(config=config)

        new_memory = MemoryItem(
            id="new", content="新", memory_type="semantic",
            created_at=time.time(), importance=1.0,
        )
        assert not forgetter.should_forget(new_memory)

        old_memory = MemoryItem(
            id="old", content="旧", memory_type="semantic",
            created_at=time.time() - 100, importance=0.0,
        )
        assert forgetter.should_forget(old_memory)

    def test_capacity_enforcement(self):
        """测试容量限制。"""
        config = ForgetConfig(max_capacity=2)
        forgetter = MemoryForgetter(config=config)

        memories = [
            MemoryItem(id=f"m_{i}", content=f"记忆{i}", memory_type="semantic",
                       created_at=time.time(), importance=0.5)
            for i in range(5)
        ]
        forgotten = forgetter.enforce_capacity(memories)
        assert len(forgotten) == 3  # 5 - 2 = 3

    def test_forget_flow(self):
        """测试完整遗忘流程。"""
        config = ForgetConfig(
            decay_half_life=1.0,
            forget_threshold=0.3,
            max_capacity=5,
        )
        forgetter = MemoryForgetter(config=config)

        # 创建混合记忆
        memories = [
            MemoryItem(id="new_high", content="新且重要", memory_type="semantic",
                       created_at=time.time(), importance=1.0),
            MemoryItem(id="old_low", content="旧且不重要", memory_type="semantic",
                       created_at=time.time() - 200, importance=0.0),
            MemoryItem(id="mid", content="中等记忆", memory_type="semantic",
                       created_at=time.time() - 50, importance=0.5),
        ]

        forgotten_ids, retained = forgetter.forget(memories)
        assert "old_low" in forgotten_ids
        assert "new_high" in {r.id for r in retained}


class TestConsolidator:
    """记忆整合器测试。"""

    def test_consolidate_memories(self):
        """测试记忆整合。"""
        consolidator = MockLLMConsolidator()
        memories = [
            MemoryItem(id="m1", content="Python 编程技巧第一条", memory_type="semantic"),
            MemoryItem(id="m2", content="Python 编程技巧第二条", memory_type="semantic"),
            MemoryItem(id="m3", content="Python 编程技巧第三条", memory_type="semantic"),
        ]
        result = consolidator.consolidate(memories, topic="Python")
        assert result is not None
        assert "整合记忆" in result.content
        assert result.importance > 0.5
        assert "consolidated_from" in result.metadata

    def test_consolidate_single_memory_returns_none(self):
        """测试单条记忆不能整合。"""
        consolidator = MockLLMConsolidator()
        result = consolidator.consolidate([
            MemoryItem(id="m1", content="单条记忆", memory_type="semantic"),
        ])
        assert result is None

    def test_find_consolidatable(self):
        """测试查找可整合的记忆组。"""
        consolidator = MockLLMConsolidator()
        memories = [
            MemoryItem(id="a1", content="Python 编程相关内容", memory_type="semantic"),
            MemoryItem(id="a2", content="Python 编程相关技巧", memory_type="semantic"),
            MemoryItem(id="a3", content="Python 编程相关方法", memory_type="semantic"),
            MemoryItem(id="b1", content="完全不同的内容", memory_type="semantic"),
        ]
        groups = consolidator.find_consolidatable(memories, similarity_threshold=0.2, min_group_size=3)
        assert len(groups) >= 1