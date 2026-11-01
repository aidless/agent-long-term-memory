"""
记忆提取 - 从对话中自动提取记忆，包括实体关系、情感偏好和事实断言。
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExtractedMemory:
    """提取出的记忆。"""
    content: str
    memory_type: str  # semantic, episodic, procedural
    importance: float = 0.5
    metadata: dict = field(default_factory=dict)
    confidence: float = 0.8


@dataclass
class ExtractionResult:
    """提取结果。"""
    memories: list[ExtractedMemory] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)
    emotions: list[dict] = field(default_factory=list)
    preferences: list[dict] = field(default_factory=list)


class MemoryExtractor:
    """
    记忆提取器。

    使用规则 + LLM mock 的方式从对话文本中提取记忆。
    支持：
    - 实体和关系提取
    - 情感和偏好记录
    - 事实断言提取
    """

    # 事实断言的模式
    FACT_PATTERNS = [
        r"我是(.+?)[。，,！!？?；;]",
        r"我叫(.+?)[。，,！!？?；;]",
        r"我喜欢(.+?)[。，,！!？?；;]",
        r"我不喜欢(.+?)[。，,！!？?；;]",
        r"我的(.+?)是(.+?)[。，,！!？?；;]",
        r"(.+?)是(.+?)的(.+?)[。，,！!？?；;]",
        r"(.+?)有(.+?)[。，,！!？?；;]",
        r"(.+?)在(.+?)[。，,！!？?；;]",
    ]

    # 情感关键词
    EMOTION_KEYWORDS = {
        "happy": ["开心", "高兴", "快乐", "喜欢", "满意", "棒", "太好了", "哈哈", "好的"],
        "sad": ["难过", "伤心", "不开心", "失望", "遗憾", "可惜"],
        "angry": ["生气", "愤怒", "讨厌", "烦", "恼火"],
        "surprised": ["惊讶", "意外", "没想到", "不敢相信"],
        "fearful": ["害怕", "担心", "焦虑", "紧张"],
    }

    # 偏好模式
    PREFERENCE_PATTERNS = [
        (r"我(?:更)?喜欢(.+?)[。，,！!？?；;]", "like", 0.7),
        (r"我(?:比较)?偏爱(.+?)[。，,！!？?；;]", "like", 0.8),
        (r"我讨厌(.+?)[。，,！!？?；;]", "dislike", 0.8),
        (r"我不(?:太)?喜欢(.+?)[。，,！!？?；;]", "dislike", 0.7),
        (r"我(?:通常)?习惯(.+?)[。，,！!？?；;]", "habit", 0.6),
    ]

    def extract(self, text: str, speaker: str = "user") -> ExtractionResult:
        """
        从文本中提取记忆。

        Args:
            text: 输入文本
            speaker: 说话人标识

        Returns:
            ExtractionResult 包含所有提取的记忆
        """
        result = ExtractionResult()

        # 1. 提取事实断言
        facts = self._extract_facts(text, speaker)
        result.memories.extend(facts)

        # 2. 提取实体和关系
        entities, relations = self._extract_entities_relations(text, speaker)
        result.entities = entities
        result.relations = relations

        # 3. 提取情感
        emotions = self._extract_emotions(text, speaker)
        result.emotions = emotions

        # 4. 提取偏好
        preferences = self._extract_preferences(text, speaker)
        result.preferences = preferences
        result.memories.extend(preferences)

        # 5. 提取情景记忆（将整段对话作为一个情景）
        if text.strip():
            result.memories.append(ExtractedMemory(
                content=f"[{speaker}] {text.strip()}",
                memory_type="episodic",
                importance=0.3,
                metadata={"speaker": speaker, "auto_extracted": True},
                confidence=0.9,
            ))

        return result

    def _extract_facts(self, text: str, speaker: str) -> list[ExtractedMemory]:
        """提取事实断言。"""
        facts = []
        for pattern in self.FACT_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                # 跳过太短的匹配
                if len(match.strip()) < 2:
                    continue
                facts.append(ExtractedMemory(
                    content=f"{speaker}的事实: {match.strip()}",
                    memory_type="semantic",
                    importance=0.7,
                    metadata={
                        "speaker": speaker,
                        "auto_extracted": True,
                        "extraction_type": "fact",
                    },
                    confidence=0.7,
                ))
        return facts

    def _extract_entities_relations(self, text: str, speaker: str) -> tuple[list[dict], list[dict]]:
        """
        简单的实体和关系提取（规则 + mock）。

        返回实体列表和关系列表。
        """
        entities = []
        relations = []

        # 简单的实体识别：中文名字（2-4个中文字）
        name_pattern = r"[\u4e00-\u9fff]{2,4}"
        names = set(re.findall(name_pattern, text))

        for name in names:
            entities.append({
                "name": name,
                "type": "person",  # mock: 都当作人名
                "source": speaker,
                "confidence": 0.5,
            })

        # 简单的关系提取
        relation_patterns = [
            (r"([\u4e00-\u9fff]{2,4})是([\u4e00-\u9fff]{2,4})的(朋友|同事|同学|家人|领导|下属)", "relationship"),
            (r"([\u4e00-\u9fff]{2,4})在([\u4e00-\u9fff]+?)(工作|学习|生活)", "location"),
        ]
        for pattern, rel_type in relation_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                relations.append({
                    "subject": match[0],
                    "predicate": rel_type,
                    "object": match[1],
                    "detail": match[2] if len(match) > 2 else "",
                    "source": speaker,
                    "confidence": 0.6,
                })

        return entities, relations

    def _extract_emotions(self, text: str, speaker: str) -> list[dict]:
        """提取情感。"""
        emotions = []
        for emotion_type, keywords in self.EMOTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    emotions.append({
                        "type": emotion_type,
                        "keyword": keyword,
                        "text": text[:100],  # 上下文截断
                        "speaker": speaker,
                        "intensity": 0.7,  # mock 简单赋值
                    })
                    break  # 每种情感只取第一个匹配
        return emotions

    def _extract_preferences(self, text: str, speaker: str) -> list[ExtractedMemory]:
        """提取偏好。"""
        preferences = []
        for pattern, pref_type, default_importance in self.PREFERENCE_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match.strip()) < 2:
                    continue
                preferences.append(ExtractedMemory(
                    content=f"{speaker}的偏好 [{pref_type}]: {match.strip()}",
                    memory_type="semantic",
                    importance=default_importance,
                    metadata={
                        "speaker": speaker,
                        "auto_extracted": True,
                        "extraction_type": "preference",
                        "preference_type": pref_type,
                    },
                    confidence=0.8,
                ))
        return preferences


class MockLLMExtractor:
    """
    Mock LLM 提取器 - 模拟 LLM 的记忆提取能力。

    在实际项目中，这里会调用真实的 LLM API。
    """

    def __init__(self):
        self.rule_extractor = MemoryExtractor()

    def extract(self, text: str, speaker: str = "user") -> ExtractionResult:
        """使用 mock LLM 提取记忆。"""
        # 先用规则提取
        result = self.rule_extractor.extract(text, speaker)

        # Mock: 模拟 LLM 额外提取一些信息
        if len(text) > 20:
            result.memories.append(ExtractedMemory(
                content=f"[LLM提取] 对话摘要: {text[:50]}...",
                memory_type="episodic",
                importance=0.4,
                metadata={
                    "speaker": speaker,
                    "extraction_method": "llm_mock",
                },
                confidence=0.6,
            ))

        return result