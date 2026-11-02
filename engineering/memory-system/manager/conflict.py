"""
冲突检测 - 检测记忆系统中的矛盾记忆（R2.3 缺口补全）。

背景：
    现有系统静默积累矛盾记忆（文献[4] MOSAIC 明确指出现有系统局限之一）。
    矛盾记忆：两条记忆内容相矛盾（如「模型 A 效果好」vs「模型 A 效果差」），
    会污染检索结果（R2.1 显示噪音侵蚀检索）。

冲突检测策略：
    1. 关键词相似度检测：两条记忆共享足够关键词但内容相反 → 潜在冲突。
    2. 主题冲突检测：同主题下的矛盾表述。

判定冲突：
    两条记忆如果：
    - 共享 ≥ min_shared_keywords 个关键词（同一主题）
    - 但表述矛盾（关键词有正反表述，如「好」vs「差」）
    则为冲突。

复现：
    pytest engineering/memory-system/tests/test_conflict.py
"""

from __future__ import annotations

import time
import re
from dataclasses import dataclass
from typing import Optional

from memory.base import MemoryItem


# 常见反义词对（用于检测表述矛盾）
OPPOSITE_PAIRS = [
    ("好", "差"), ("好", "坏"), ("高", "低"), ("大", "小"),
    ("成功", "失败"), ("有效", "无效"), ("正确", "错误"),
    ("快", "慢"), ("优", "劣"), ("强", "弱"), ("增加", "减少"),
    ("支持", "反对"), ("通过", "拒绝"), ("positive", "negative"),
    ("good", "bad"), ("high", "low"), ("success", "failure"),
    ("effective", "ineffective"), ("correct", "wrong"),
    # 补充中文反义对（性能/表现相关）
    ("提升", "下降"), ("提升", "降低"), ("上升", "下降"), ("上升", "降低"),
    ("增长", "减少"), ("增长", "缩减"), ("改善", "恶化"), ("改善", "变差"),
    ("增强", "减弱"), ("提高", "降低"), ("提高", "下降"),
    ("更好", "更差"), ("更快", "更慢"), ("更稳", "更不稳定"), ("更稳", "不稳定"),
    ("优秀", "糟糕"), ("优秀", "拙劣"), ("先进", "落后"),
    ("可靠", "不可靠"), ("稳定", "不稳定"), ("有效", "失效"),
    ("活跃", "不活跃"), ("可用", "不可用"), ("存在", "缺失"),
    ("包含", "排除"), ("接受", "拒绝"), ("通过", "未通过"),
    ("成功", "不成功"), ("正确", "不正确"), ("一致", "不一致"),
    # 英文动词/形容词反义对（补充：improved/degraded 等）
    ("improved", "degraded"), ("improved", "worsened"),
    ("increased", "decreased"), ("increase", "decrease"),
    ("better", "worse"), ("improve", "degrade"), ("improve", "worsen"),
    ("succeeded", "failed"), ("succeed", "fail"),
    ("faster", "slower"), ("stronger", "weaker"),
    ("more", "less"), ("up", "down"),
    ("reliable", "unreliable"), ("stable", "unstable"),
    ("beneficial", "harmful"), ("gain", "loss"), ("gain", "lose"),
    ("advantage", "disadvantage"), ("support", "oppose"),
    ("approve", "reject"), ("accepted", "rejected"),
    ("win", "lose"), ("works", "fails"),
    ("true", "false"), ("yes", "no"),
    ("well", "poorly"), ("good", "poor"), ("good", "badly"),
    ("fast", "slow"), ("fast", "slowly"), ("early", "late"),
    ("strong", "weak"), ("strong", "weakly"), ("large", "small"),
    ("large", "small"), ("many", "few"), ("much", "little"),
    ("increase", "reduce"), ("increase", "decrease"),
    ("improve", "reduce"), ("improve", "decline"),
    ("rise", "fall"), ("rise", "drop"), ("grow", "shrink"),
    ("upgrade", "downgrade"), ("expand", "contract"),
    ("enable", "disable"), ("enable", "disenable"),
    ("active", "inactive"), ("available", "unavailable"),
    ("present", "absent"), ("include", "exclude"),
    ("positive", "negative"), ("profit", "loss"),
    ("advance", "retreat"), ("progress", "regress"),
]


# 常见通用词（不构成主题区分，排除出共享关键词计数）
GENERIC_WORDS = {
    "模型", "效果", "表现", "性能", "准确", "数据", "结果", "方法",
    "model", "effect", "performance", "accuracy", "result",
    "好", "差", "高", "低", "大", "小", "成功", "失败",
    "有效", "无效", "正确", "错误", "快", "慢", "优", "劣",
    "强", "弱", "增加", "减少", "支持", "反对", "通过", "拒绝",
    "是", "的", "和", "与", "在", "有", "为", "对",
    # 英文通用词（补充：不构成主题区分的词）
    "improved", "degraded", "worsened", "increased", "decreased",
    "better", "worse", "improve", "degrade", "worsen",
    "succeeded", "failed", "succeed", "fail",
    "faster", "slower", "stronger", "weaker", "reliable", "unreliable",
    "stable", "unstable", "beneficial", "harmful", "gain", "loss",
    "significantly", "very", "quite", "slightly", "extremely",
    "well", "poorly", "works", "fails", "true", "false",
    "the", "an", "of", "to", "in", "on", "for", "with",
    # 'a' 不在 GENERIC：单字母 'a' 常是变量/实体标识（模型 A、算法 a），
    # 且英文不定冠词 'a' 作 subject 时通常伴随 'model'/'algorithm' 等
    # 通用词已被排除，不会单独造成误判。
    "and", "or", "but", "is", "are", "was", "were", "be", "been",
    "it", "this", "that", "these", "those", "its", "their",
}


@dataclass
class ConflictConfig:
    """冲突检测配置。"""
    min_shared_keywords: int = 1  # 共享主题标识数阈值（同一实体即可判同主题）
    similarity_threshold: float = 0.3  # 关键词重叠比例阈值


class ConflictDetector:
    """
    冲突检测器。

    检测两条记忆是否矛盾：
    - 共享足够关键词（同一主题）
    - 但表述矛盾（反义词对）

    这是「记忆区别于检索」的关键组件之一——纯检索不会检测矛盾，
    记忆系统应主动维护一致性。
    """

    def __init__(self, config: Optional[ConflictConfig] = None):
        self.config = config or ConflictConfig()

    def _tokenize(self, text: str) -> set[str]:
        """分词（中英文兼容，中文按词/组块而非单字）。

        单字切分导致误报：'模型 A 效果好' vs '模型 B 效果差' 共享
        模/型/效/果 单字，被误判为同一主题。改用：
        - 英文单词
        - 中文连续字符块（整块作为一个 token，含主语）
        - 中文双字组（bigram，捕获 '模型' '效果' 等词）
        """
        words = re.findall(r'[a-zA-Z]+|[\u4e00-\u9fff]+', text.lower())
        tokens = set()
        for w in words:
            if w.isascii():
                tokens.add(w)
            else:
                # 中文整块 + 双字组（bigram）
                if len(w) >= 2:
                    tokens.add(w)  # 整块
                for i in range(len(w) - 1):
                    tokens.add(w[i:i + 2])  # bigram
                # 单字仅当整块只有一个字时
                if len(w) == 1:
                    tokens.add(w)
        return tokens

    def _subject_tokens(self, text: str) -> set[str]:
        """提取主题标识（非通用词、非判定词的特定实体 token）。

        主题标识 = 能区分「这是关于什么」的 token：
        - 排除通用词（模型/效果/性能...）
        - 排除判定词（好/差/高/低...）——中文判定词常嵌在 bigram 中
          （'效果好'含'好'），需按字符检测。
        留下的是特定实体（如 'a'、'模型a'、'数据集b'、'algo'）。
        """
        tokens = self._tokenize(text)
        verdict_words = set()
        for pos, neg in OPPOSITE_PAIRS:
            verdict_words.add(pos)
            verdict_words.add(neg)
        result = set()
        for tok in tokens:
            if tok in GENERIC_WORDS:
                continue
            # 中文判定词常嵌在 bigram（如 '效果好' 含 '好'）——按字符检测
            if any(v in tok for v in verdict_words if len(v) == 1):
                continue
            if tok in verdict_words:
                continue
            result.add(tok)
        return result

    def _shared_keywords(self, a: str, b: str) -> set[str]:
        """计算共享关键词。"""
        tokens_a = self._tokenize(a)
        tokens_b = self._tokenize(b)
        return tokens_a & tokens_b

    def _has_opposite(self, a: str, b: str) -> bool:
        """检测两条记忆是否含反义表述。

        支持词形变化：'stability'/'instability' 通过词干 'stable'/'unstable'
        匹配。用词干匹配而非精确子串——英文词形变化（-ity/-y/-ed/-ing）
        导致精确子串失败。
        """
        for pos, neg in OPPOSITE_PAIRS:
            if self._stem_match(pos, a) and self._stem_match(neg, b):
                return True
            if self._stem_match(neg, a) and self._stem_match(pos, b):
                return True
        return False

    def _stem_match(self, stem: str, text: str) -> bool:
        """词干匹配：检查 text 中是否含 stem 或其词形变化。

        处理英文词形变化（-ity/-ness/-ful/-ly/-ed/-ing/-ment 及 e 结尾变体、
        un/in/im/ir 否定前缀）。例：'stable' 匹配 'stability'，'unstable'
        匹配 'instability'。
        """
        if stem in text:
            return True
        # 否定前缀变体（unstable->stable 核心）
        for prefix in ("un", "in", "im", "ir", "dis", "non"):
            core = stem[len(prefix):] if stem.startswith(prefix) else stem
            # 核心词干 + 词形变化后缀
            core_base = core[:-1] if core.endswith("e") else core
            for candidate in (core, core_base, core[:4] if len(core) >= 4 else core):
                if candidate and candidate in text:
                    return True
            # 常见词形变化后缀
            for suffix in ("ful", "ness", "ly", "ing", "ed", "ment", "ity"):
                if (core + suffix) in text or (core_base + suffix) in text:
                    return True
        # 无否定前缀的常规词干 + 词形变化
        core_base = stem[:-1] if stem.endswith("e") else stem
        for candidate in (core_base, stem[:4] if len(stem) >= 4 else stem):
            if candidate and candidate in text:
                return True
        for suffix in ("ful", "ness", "ly", "ing", "ed", "ment", "ity"):
            if (stem + suffix) in text or (core_base + suffix) in text:
                return True
        return False

    def detect_conflict(self, m1: MemoryItem, m2: MemoryItem) -> bool:
        """检测两条记忆是否冲突。

        判据：
        1. **同一主题**：共享 ≥ min_shared_keywords 个**特定**主题 token
           （排除通用词与判定词——只计区分主题的实体 token）
        2. 含反义表述（矛盾）

        Args:
            m1: 第一条记忆
            m2: 第二条记忆

        Returns:
            True 表示冲突
        """
        # 主题 token 必须共享（同一实体，如都关于 '模型a'）
        subject_a = self._subject_tokens(m1.content)
        subject_b = self._subject_tokens(m2.content)
        shared_subject = subject_a & subject_b
        if len(shared_subject) < self.config.min_shared_keywords:
            return False
        return self._has_opposite(m1.content, m2.content)

    def find_conflicts(self, memories: list[MemoryItem]) -> list[tuple[MemoryItem, MemoryItem]]:
        """找出所有冲突记忆对。

        Args:
            memories: 候选记忆列表

        Returns:
            冲突记忆对列表
        """
        conflicts = []
        for i in range(len(memories)):
            for j in range(i + 1, len(memories)):
                if self.detect_conflict(memories[i], memories[j]):
                    conflicts.append((memories[i], memories[j]))
        return conflicts

    def resolve_conflict(self, m1: MemoryItem, m2: MemoryItem) -> MemoryItem:
        """解决冲突：保留重要性更高的记忆，返回应保留的记忆。

        冲突解决策略：
        - 保留重要性更高 / 更近期的记忆
        - 废弃重要性更低 / 更陈旧的记忆

        Args:
            m1: 第一条记忆
            m2: 第二条记忆

        Returns:
            应保留的记忆
        """
        # 保留重要性更高者；重要性相同保留更近期者
        if m1.importance > m2.importance:
            return m1
        elif m2.importance > m1.importance:
            return m2
        else:
            return m1 if m1.created_at >= m2.created_at else m2
