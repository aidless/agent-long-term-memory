"""
上下文窗口管理 - 管理 Agent 的上下文窗口，确保记忆注入不超出限制。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ContextWindowConfig:
    """上下文窗口配置。"""
    max_tokens: int = 4096
    system_prompt_tokens: int = 500
    user_message_tokens: int = 200
    response_reserve_tokens: int = 1024
    chars_per_token: float = 2.0


@dataclass
class Allocation:
    """Token 分配方案。"""
    system_prompt: int
    memory: int
    user_message: int
    response_reserve: int
    total: int

    def to_dict(self) -> dict:
        return {
            "system_prompt": self.system_prompt,
            "memory": self.memory,
            "user_message": self.user_message,
            "response_reserve": self.response_reserve,
            "total": self.total,
        }


class ContextWindowManager:
    """
    上下文窗口管理器。

    管理 Agent 可用的上下文窗口空间，确保各部分（系统提示、记忆、用户消息、预留响应）
    合理分配 Token 预算。
    """

    def __init__(self, config: Optional[ContextWindowConfig] = None):
        self.config = config or ContextWindowConfig()

    def allocate(self) -> Allocation:
        """
        计算 Token 分配方案。

        Returns:
            Allocation 对象
        """
        total = self.config.max_tokens
        system = min(self.config.system_prompt_tokens, total // 4)
        response = min(self.config.response_reserve_tokens, total // 4)
        user = min(self.config.user_message_tokens, total // 6)
        memory = total - system - response - user

        return Allocation(
            system_prompt=system,
            memory=max(memory, 0),
            user_message=user,
            response_reserve=response,
            total=total,
        )

    def estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数。"""
        return int(len(text) / self.config.chars_per_token)

    def fits_in_window(
        self,
        system_prompt: str,
        memory_text: str,
        user_message: str,
    ) -> tuple[bool, int]:
        """
        检查文本是否适合上下文窗口。

        Returns:
            (是否适合, 估算的 token 总数)
        """
        total_tokens = (
            self.estimate_tokens(system_prompt)
            + self.estimate_tokens(memory_text)
            + self.estimate_tokens(user_message)
            + self.config.response_reserve_tokens
        )
        return total_tokens <= self.config.max_tokens, total_tokens

    def truncate_to_fit(
        self,
        memory_text: str,
        system_prompt: str = "",
        user_message: str = "",
    ) -> str:
        """
        截断记忆文本以适应上下文窗口。

        优先保留前面的记忆（通常更重要）。
        """
        alloc = self.allocate()
        available_chars = int(alloc.memory * self.config.chars_per_token)

        if len(memory_text) <= available_chars:
            return memory_text

        # 按行截断
        lines = memory_text.split("\n")
        result_lines = []
        current_len = 0

        for line in lines:
            line_len = len(line) + 1  # +1 for newline
            if current_len + line_len > available_chars:
                break
            result_lines.append(line)
            current_len += line_len

        truncated = "\n".join(result_lines)
        if len(result_lines) < len(lines):
            truncated += "\n... [记忆已截断以适应上下文窗口]"
        return truncated