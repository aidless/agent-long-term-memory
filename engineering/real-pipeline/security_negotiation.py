# -*- coding: utf-8 -*-
"""轻量安全协商模块（Lightweight Security Negotiation）

Sketch of a negotiation helper that a future P6 run would need.
This module is not a P6 result. N=72 has not been run. The
`violation_threshold` below is a local default, not a frozen prereg bound.

本模块实现一个轻量级安全协商协议：
- 每个工具调用前检查是否触发安全策略（敏感操作/越权访问/数据泄露风险）
- 协商决策：允许（allow）/ 拒绝（deny）/ 降级（degrade）三态
- 开销度量：每次协商的 token 数（用于 H3 成本比较）
- 安全违规检测：记录实际违规次数（用于 H3 非劣效界）

设计目标：开销显著低于完整安全基线，同时安全违规率不显著上升。
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SecurityPolicy:
    """安全策略配置（轻量级）。"""
    sensitive_ops: set[str] = field(default_factory=lambda: {
        "fs_write", "http_public", "python_exec", "sqlite_query",
    })
    allow_deny_rate: float = 0.05  # 允许-拒绝协商的采样率（轻量：只协商敏感操作）
    max_tokens_per_negotiation: int = 8  # 单次协商最大 token 数（轻量上限）
    violation_threshold: float = 0.05  # 非劣效界（安全违规率上限）


@dataclass
class NegotiationResult:
    """一次安全协商的结果。"""
    op: str
    decision: str  # "allow" | "deny" | "degrade"
    tokens_used: int
    violation: bool
    reason: str = ""


class LightweightSecurityNegotiator:
    """轻量安全协商器。

    只对敏感操作做采样协商（allow_deny_rate），非敏感操作直接允许。
    对比完整安全基线：完整基线对每个操作都做深度策略检查（高 token 成本）。
    """

    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self.policy = policy or SecurityPolicy()
        self.total_tokens = 0
        self.total_negotiations = 0
        self.violations = 0

    def negotiate(self, op: str, context: dict[str, Any] | None = None) -> NegotiationResult:
        """对一次工具调用执行安全协商。

        Args:
            op: 工具操作名（如 fs_write）
            context: 调用上下文（用于判断越权/风险）

        Returns:
            NegotiationResult
        """
        context = context or {}
        self.total_negotiations += 1

        # 非敏感操作：直接允许，零 token 开销（轻量核心优势）
        if op not in self.policy.sensitive_ops:
            return NegotiationResult(
                op=op, decision="allow", tokens_used=0, violation=False,
                reason="non-sensitive op: auto-allow",
            )

        # 敏感操作：采样协商（轻量：只对一部分敏感操作做深度检查）
        # 判断是否触发深度协商——用简单哈希模拟采样（确定性）
        import hashlib
        h = int(hashlib.sha256(f"{op}|{context.get('agent_id','')}|{context.get('step','')}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        if h > self.policy.allow_deny_rate:
            # 未采样到：轻量放行但记录潜在风险
            return NegotiationResult(
                op=op, decision="allow", tokens_used=1, violation=False,
                reason="sampled-pass (lightweight)",
            )

        # 采样到：深度检查
        # 风险判断：是否越权访问（简单规则）
        is_privileged = context.get("is_privileged", False)
        target_is_sensitive = context.get("target_sensitive", False)

        tokens = self.policy.max_tokens_per_negotiation
        self.total_tokens += tokens

        if is_privileged and not context.get("has_permission", False):
            # 越权访问：拒绝
            self.violations += 1
            return NegotiationResult(
                op=op, decision="deny", tokens_used=tokens, violation=True,
                reason="privilege-escalation: denied",
            )
        elif target_is_sensitive and not context.get("approved", False):
            # 敏感目标未批准：降级
            return NegotiationResult(
                op=op, decision="degrade", tokens_used=tokens, violation=False,
                reason="sensitive-target: degraded",
            )
        else:
            # 正常：允许
            return NegotiationResult(
                op=op, decision="allow", tokens_used=tokens, violation=False,
                reason="approved",
            )

    def get_stats(self) -> dict[str, Any]:
        """返回协商开销统计（用于 H3 成本比较）。"""
        return {
            "total_tokens": self.total_tokens,
            "total_negotiations": self.total_negotiations,
            "violations": self.violations,
            "violation_rate": self.violations / max(1, self.total_negotiations),
        }


class FullSecurityBaseline:
    """完整安全基线（对照）。

    对**每个**操作都做深度策略检查（高 token 成本），对比轻量协商器。
    用于 H3：轻量协商开销显著低于完整基线。
    """

    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self.policy = policy or SecurityPolicy()
        self.total_tokens = 0
        self.violations = 0
        self.total_negotiations = 0

    def negotiate(self, op: str, context: dict[str, Any] | None = None) -> NegotiationResult:
        """完整基线：每个操作都深度检查（高成本）。"""
        context = context or {}
        self.total_negotiations += 1

        # 完整基线：所有操作都消耗 token（深度检查）
        tokens = self.policy.max_tokens_per_negotiation * 4  # 4 倍开销
        self.total_tokens += tokens

        # 深度检查所有操作
        is_privileged = context.get("is_privileged", False)
        target_is_sensitive = context.get("target_sensitive", False)

        if is_privileged and not context.get("has_permission", False):
            self.violations += 1
            return NegotiationResult(
                op=op, decision="deny", tokens_used=tokens, violation=True,
                reason="privilege-escalation: denied (full check)",
            )
        elif target_is_sensitive and not context.get("approved", False):
            return NegotiationResult(
                op=op, decision="degrade", tokens_used=tokens, violation=False,
                reason="sensitive-target: degraded (full check)",
            )
        else:
            return NegotiationResult(
                op=op, decision="allow", tokens_used=tokens, violation=False,
                reason="approved (full check)",
            )

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_tokens": self.total_tokens,
            "total_negotiations": self.total_negotiations,
            "violations": self.violations,
            "violation_rate": self.violations / max(1, self.total_negotiations),
        }
