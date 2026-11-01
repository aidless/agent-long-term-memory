"""
测试检索策略 - 语义检索、时间衰减、重要性评分、混合检索。
"""

import time
import pytest

from memory.base import MemoryItem
from retrieval.semantic_search import SemanticSearch
from retrieval.time_decay import TimeDecayScorer, TimeDecayConfig
from retrieval.importance import ImportanceScorer
from retrieval.hybrid import HybridRetriever, HybridConfig


def _make_memory(content: str, memory_type: str = "semantic", age: float = 0, importance: float = 0.5, access_count: int = 0, mid: str = None) -> MemoryItem:
    """创建测试用记忆。"""
    return MemoryItem(
        id=mid or f"test_{content[:5]}",
        content=content,
        memory_type=memory_type,
        created_at=time.time() - age,
        updated_at=time.time() - age * 0.5,
        importance=importance,
        access_count=access_count,
    )


class TestSemanticSearch:
    """语义检索测试。"""

    def test_exact_match(self):
        """测试精确匹配。"""
        searcher = SemanticSearch()
        memories = [_make_memory("Python programming language")]
        results = searcher.search(memories, "Python programming language", top_k=1)
        assert len(results) == 1
        assert results[0].score >= 0.9

    def test_partial_match(self):
        """测试部分匹配。"""
        searcher = SemanticSearch()
        memories = [
            _make_memory("Python is a great programming language"),
            _make_memory("The weather is nice today"),
        ]
        results = searcher.search(memories, "Python programming", top_k=2)
        assert len(results) >= 1
        assert "Python" in results[0].memory.content

    def test_threshold_filter(self):
        """测试阈值过滤。"""
        searcher = SemanticSearch()
        memories = [
            _make_memory("Python programming"),
            _make_memory("weather today"),
        ]
        results = searcher.search(memories, "Python", threshold=0.5)
        assert all(r.score >= 0.5 for r in results)

    def test_empty_query(self):
        """测试空查询。"""
        searcher = SemanticSearch()
        memories = [_make_memory("some content")]
        results = searcher.search(memories, "", top_k=5, threshold=0.01)
        # 空查询应返回空或低分结果
        if results:
            assert results[0].score < 0.01

    def test_top_k_limit(self):
        """测试 Top-K 限制。"""
        searcher = SemanticSearch()
        memories = [_make_memory(f"memory number {i} about programming") for i in range(10)]
        results = searcher.search(memories, "programming", top_k=3)
        assert len(results) <= 3


class TestTimeDecay:
    """时间衰减测试。"""

    def test_new_memory_high_score(self):
        """测试新记忆有高衰减分数。"""
        scorer = TimeDecayScorer()
        memory = _make_memory("新记忆", age=0)
        score = scorer.decay(memory)
        assert score > 0.99

    def test_old_memory_low_score(self):
        """测试旧记忆有低衰减分数。"""
        config = TimeDecayConfig(half_life=86400.0)  # 1天半衰期
        scorer = TimeDecayScorer(config)
        # 100天前的记忆
        memory = _make_memory("旧记忆", age=86400.0 * 100)
        score = scorer.decay(memory)
        assert score <= 0.01  # min_score boundary

    def test_decay_monotonic(self):
        """测试衰减单调递减。"""
        scorer = TimeDecayScorer(TimeDecayConfig(half_life=3600.0))
        scores = []
        for age_hours in [0, 1, 2, 5, 10, 24]:
            memory = _make_memory("test", age=age_hours * 3600)
            scores.append(scorer.decay(memory))

        for i in range(1, len(scores)):
            assert scores[i] <= scores[i - 1]

    def test_apply_decay_to_results(self):
        """测试对检索结果应用时间衰减。"""
        scorer = TimeDecayScorer(TimeDecayConfig(half_life=3600.0))
        searcher = SemanticSearch()

        memories = [
            _make_memory("old Python info", age=86400.0 * 10),
            _make_memory("new Python info", age=0),
        ]
        results = searcher.search(memories, "Python", top_k=10)
        decayed = scorer.apply_decay(results, time_weight=0.8)

        # 新记忆应该排在前面
        assert decayed[0].memory.created_at > decayed[1].memory.created_at


class TestImportanceScorer:
    """重要性评分测试。"""

    def test_high_importance_high_score(self):
        """测试高重要性得到高分。"""
        scorer = ImportanceScorer()
        memory = _make_memory("重要记忆", importance=1.0, access_count=10)
        score = scorer.score(memory)
        assert score > 0.7

    def test_low_importance_low_score(self):
        """测试低重要性得到低分。"""
        scorer = ImportanceScorer()
        memory = _make_memory("不重要记忆", importance=0.0, access_count=0, age=86400.0)
        score = scorer.score(memory)
        assert score < 0.5

    def test_access_count_boost(self):
        """测试访问频率加成。"""
        scorer = ImportanceScorer()
        mem_low = _make_memory("低访问", importance=0.5, access_count=0)
        mem_high = _make_memory("高访问", importance=0.5, access_count=100)
        score_low = scorer.score(mem_low)
        score_high = scorer.score(mem_high)
        assert score_high > score_low


class TestHybridRetriever:
    """混合检索测试。"""

    def test_hybrid_search(self):
        """测试混合检索。"""
        retriever = HybridRetriever()
        memories = [
            _make_memory("Python programming language is versatile", importance=0.8, access_count=5),
            _make_memory("Weather forecast for today", importance=0.3),
            _make_memory("Python web development with FastAPI", importance=0.7, access_count=3),
        ]
        results = retriever.search(memories, "Python programming", top_k=5)
        assert len(results) >= 1
        # 第一个结果应该与 Python 相关
        assert "Python" in results[0].memory.content

    def test_hybrid_search_with_threshold(self):
        """测试带阈值的混合检索。"""
        retriever = HybridRetriever()
        memories = [
            _make_memory("Python programming"),
            _make_memory("completely unrelated topic"),
        ]
        results = retriever.search(memories, "Python", threshold=0.1)
        assert len(results) >= 1

    def test_empty_memories(self):
        """测试空记忆列表。"""
        retriever = HybridRetriever()
        results = retriever.search([], "test query")
        assert results == []

    def test_custom_weights(self):
        """测试自定义权重。"""
        config = HybridConfig(
            semantic_weight=0.2,
            time_weight=0.3,
            importance_weight=0.5,
        )
        retriever = HybridRetriever(config=config)
        memories = [_make_memory("test content")]
        results = retriever.search(memories, "test")
        assert len(results) == 1
        assert "semantic" in results[0].score_breakdown
        assert "time_decay" in results[0].score_breakdown
        assert "importance" in results[0].score_breakdown

    def test_association_expansion(self):
        """测试关联记忆扩展。"""
        config = HybridConfig(enable_association=True, top_k=10)
        retriever = HybridRetriever(config=config)
        memories = [
            _make_memory("Python programming basics"),
            _make_memory("Python advanced programming"),
            _make_memory("Java programming basics"),
        ]
        results = retriever.search(memories, "Python programming", top_k=5)
        # 关联扩展应该能找到更多相关记忆
        assert len(results) >= 1