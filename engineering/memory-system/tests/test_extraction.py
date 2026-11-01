"""
测试记忆提取 - 规则提取和 LLM mock 提取。
"""

import pytest

from manager.extractor import MemoryExtractor, MockLLMExtractor


class TestMemoryExtractor:
    """记忆提取器测试。"""

    def test_extract_facts(self):
        """测试事实断言提取。"""
        extractor = MemoryExtractor()
        result = extractor.extract("我是张三，我叫张三丰。")
        # 应该提取出关于身份的事实
        fact_memories = [m for m in result.memories if m.metadata.get("extraction_type") == "fact"]
        assert len(fact_memories) >= 1

    def test_extract_preferences(self):
        """测试偏好提取。"""
        extractor = MemoryExtractor()
        result = extractor.extract("我喜欢编程，我不喜欢早起。")
        pref_memories = [m for m in result.memories if m.metadata.get("extraction_type") == "preference"]
        assert len(pref_memories) >= 2

    def test_extract_emotions(self):
        """测试情感提取。"""
        extractor = MemoryExtractor()
        result = extractor.extract("今天真开心，一切都很顺利！")
        assert len(result.emotions) >= 1
        assert result.emotions[0]["type"] == "happy"

    def test_extract_entities(self):
        """测试实体提取。"""
        extractor = MemoryExtractor()
        result = extractor.extract("张三和李四一起去了北京。")
        assert len(result.entities) >= 1

    def test_extract_episodic(self):
        """测试情景记忆自动提取。"""
        extractor = MemoryExtractor()
        result = extractor.extract("这是一段对话内容")
        epi_memories = [m for m in result.memories if m.memory_type == "episodic"]
        assert len(epi_memories) >= 1

    def test_extract_empty_text(self):
        """测试空文本提取。"""
        extractor = MemoryExtractor()
        result = extractor.extract("")
        # 空文本不应产生情景记忆
        epi_memories = [m for m in result.memories if m.memory_type == "episodic"]
        assert len(epi_memories) == 0


class TestMockLLMExtractor:
    """Mock LLM 提取器测试。"""

    def test_llm_mock_extract(self):
        """测试 Mock LLM 提取。"""
        extractor = MockLLMExtractor()
        result = extractor.extract("我叫王小明，我喜欢打篮球。")
        # 应该包含规则提取结果
        assert len(result.memories) >= 1

    def test_llm_mock_long_text(self):
        """测试长文本的 LLM 额外提取。"""
        extractor = MockLLMExtractor()
        long_text = "这是一段很长很长的对话内容" * 5
        result = extractor.extract(long_text)
        # 长文本应触发 LLM mock 额外提取
        llm_memories = [m for m in result.memories if m.metadata.get("extraction_method") == "llm_mock"]
        assert len(llm_memories) >= 1

    def test_extract_with_speaker(self):
        """测试带说话人的提取。"""
        extractor = MemoryExtractor()
        result = extractor.extract("我喜欢Python。", speaker="assistant")
        assert all(
            m.metadata.get("speaker") == "assistant"
            for m in result.memories
        )