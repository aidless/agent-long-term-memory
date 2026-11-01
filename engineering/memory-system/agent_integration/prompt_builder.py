"""
Prompt 构建 - 记忆增强的 Prompt 构建器。

支持 Token 预算控制和多种注入策略。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from retrieval.semantic_search import SearchResult


class InjectionStrategy(str, Enum):
    """记忆注入策略。"""
    TOP_K = "top_k"              # 取 Top-K 条
    THRESHOLD = "threshold"       # 阈值过滤
    RELEVANCE = "relevance"       # 相关性排序


@dataclass
class PromptConfig:
    """Prompt 构建配置。"""
    token_budget: int = 2000          # Token 预算（字符数近似）
    injection_strategy: InjectionStrategy = InjectionStrategy.TOP_K
    top_k: int = 5                    # Top-K 策略的 K 值
    score_threshold: float = 0.1      # 阈值策略的最低分数
    max_memory_chars: int = 200       # 单条记忆最大字符数
    include_score: bool = False       # 是否在 prompt 中包含分数
    memory_section_header: str = "## 相关记忆"
    working_memory_header: str = "## 当前上下文"


class PromptBuilder:
    """
    记忆增强的 Prompt 构建器。

    功能：
    - 将检索到的记忆注入到 system prompt 或 user prompt 中
    - Token 预算控制
    - 多种注入策略（Top-K / 阈值 / 相关性）
    - 记忆引用追踪
    """

    # 近似 token 估算：中文 ~1.5 字符/token，英文 ~4 字符/token
    CHARS_PER_TOKEN = 2.0

    def __init__(self, config: Optional[PromptConfig] = None):
        self.config = config or PromptConfig()

    def build_memory_prompt(
        self,
        search_results: list[SearchResult],
        working_context: str = "",
    ) -> str:
        """
        构建包含记忆的 prompt 片段。

        Args:
            search_results: 检索到的记忆结果
            working_context: 工作记忆上下文

        Returns:
            可插入到 prompt 中的记忆文本
        """
        sections = []

        # 1. 长期记忆部分
        filtered = self._apply_strategy(search_results)
        memory_texts = self._format_memories(filtered)
        budget_used = sum(len(t) for t in memory_texts)

        if memory_texts:
            header = self.config.memory_section_header
            header_cost = len(header) + 10
            available = (self.config.token_budget * self.CHARS_PER_TOKEN) - header_cost

            selected = []
            for text in memory_texts:
                if budget_used <= available:
                    selected.append(text)
                    available -= len(text)

            if selected:
                sections.append(header)
                sections.extend(selected)

        # 2. 工作记忆部分
        if working_context:
            sections.append(self.config.working_memory_header)
            sections.append(working_context)

        return "\n\n".join(sections)

    def build_full_prompt(
        self,
        system_prompt: str,
        user_message: str,
        search_results: list[SearchResult],
        working_context: str = "",
    ) -> str:
        """
        构建完整的 prompt。

        将记忆注入到 system prompt 和 user message 之间。

        Args:
            system_prompt: 系统 prompt
            user_message: 用户消息
            search_results: 检索结果
            working_context: 工作记忆上下文

        Returns:
            完整的 prompt 文本
        """
        memory_section = self.build_memory_prompt(search_results, working_context)

        parts = [system_prompt]
        if memory_section:
            parts.append(memory_section)
        parts.append(f"用户: {user_message}")

        return "\n\n".join(parts)

    def estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数。"""
        return int(len(text) / self.CHARS_PER_TOKEN)

    def _apply_strategy(self, results: list[SearchResult]) -> list[SearchResult]:
        """根据注入策略过滤结果。"""
        strategy = self.config.injection_strategy

        if strategy == InjectionStrategy.TOP_K:
            return results[:self.config.top_k]

        elif strategy == InjectionStrategy.THRESHOLD:
            return [r for r in results if r.score >= self.config.score_threshold]

        elif strategy == InjectionStrategy.RELEVANCE:
            # 相关性：取分数 > 0 的结果
            return [r for r in results if r.score > 0]

        return results

    def _format_memories(self, results: list[SearchResult]) -> list[str]:
        """格式化记忆为文本。"""
        texts = []
        for result in results:
            memory = result.memory
            content = memory.content

            # 截断过长的记忆
            if len(content) > self.config.max_memory_chars:
                content = content[:self.config.max_memory_chars] + "..."

            if self.config.include_score:
                line = f"- [{memory.memory_type}] (score={result.score:.2f}) {content}"
            else:
                line = f"- [{memory.memory_type}] {content}"

            texts.append(line)

        return texts