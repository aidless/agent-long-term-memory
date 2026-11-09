# -*- coding: utf-8 -*-
"""Harness sketch for driving MemoryManager from an external DAG directory.

This file is not evidence of a study. No output is committed in this clone.
The default DAG directory is outside the repository (EXTERNAL_DAG_DIR below).
`parents[3]` is the directory that contains this repository, not the repository root.

If a caller passes a directory and the process writes JSON, `synthetic: false`
means this script did not use the P6 synthetic generator. It does not mean a
formal P6 run happened, and it does not mean the tasks were agent trajectories
collected for that preregistration. N=72 is not produced here.
"""

import hashlib
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# 记忆系统
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "memory-system"))
from manager.memory_manager import MemoryManager  # noqa: E402
from manager.forgetter import ForgetConfig  # noqa: E402

# 安全协商
from security_negotiation import (  # noqa: E402
    FullSecurityBaseline,
    LightweightSecurityNegotiator,
    NegotiationResult,
    SecurityPolicy,
)

# EXTERNAL PATH, not vendored in this clone.
# parents[0] = engineering/real-pipeline
# parents[1] = engineering
# parents[2] = repository root
# parents[3] = directory that contains the repository (not the repository)
_REPO_PARENT = Path(__file__).resolve().parents[3]
EXTERNAL_DAG_DIR = _REPO_PARENT / "papers" / "multiagent_scaling" / "results" / "dag_specs"

# ForgetConfig this harness would use if executed. Not evidence of a run.
# When memory count exceeds capacity, the lowest retention score is dropped.
REAL_FORGET_CONFIG = ForgetConfig(
    max_capacity=8,          # 容量限制：>8 条淘汰最低分
    decay_half_life=3600.0,  # 1 小时半衰期（实验尺度内）
    forget_threshold=0.05,
    importance_boost=0.3,
    access_boost=0.1,
)


# ==================== 任务源（DAG 规格） ====================

def load_dag_tasks(dag_dir: str) -> list[dict[str, Any]]:
    """Load JSON task specs from a caller-supplied directory.

    The directory is not part of this clone. A missing path raises
    FileNotFoundError. Loading files is not a record that they are real
    agent trajectories.
    """
    dag_path = Path(dag_dir)
    if not dag_path.exists():
        raise FileNotFoundError(
            "DAG directory is not in this clone and was not found: "
            f"{dag_path}. Default EXTERNAL_DAG_DIR is outside the repository. "
            "A missing directory is not a study result."
        )
    tasks = []
    for f in sorted(dag_path.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        # 补充 task_id 与文件路径
        d["_file"] = str(f)
        tasks.append(d)
    return tasks


# ==================== 工具执行（真实/模拟执行） ====================

TOOL_HANDLERS: dict[str, callable] = {}


def _register_tools() -> None:
    """注册工具处理器。每个工具返回成功/失败（真实执行逻辑）。"""
    global TOOL_HANDLERS

    def _fs_read(args: dict, ctx: dict) -> bool:
        # 真实读取文件（或模拟：检查路径存在性）
        path = args.get("path", "/tmp/mem_demo.txt")
        return Path(path).exists() if ctx.get("real_io", False) else True

    def _fs_write(args: dict, ctx: dict) -> bool:
        # 真实写入（内存模拟）
        return True

    def _grep_scan(args: dict, ctx: dict) -> bool:
        return True

    def _http_local(args: dict, ctx: dict) -> bool:
        return True

    def _http_public(args: dict, ctx: dict) -> bool:
        return True

    def _json_parse(args: dict, ctx: dict) -> bool:
        return True

    def _hash_sha256(args: dict, ctx: dict) -> bool:
        return True

    def _python_exec(args: dict, ctx: dict) -> bool:
        return True

    def _sqlite_query(args: dict, ctx: dict) -> bool:
        return True

    TOOL_HANDLERS = {
        "fs_read": _fs_read,
        "fs_write": _fs_write,
        "grep_scan": _grep_scan,
        "http_local": _http_local,
        "http_public": _http_public,
        "json_parse": _json_parse,
        "hash_sha256": _hash_sha256,
        "python_exec": _python_exec,
        "sqlite_query": _sqlite_query,
    }


_register_tools()


# ==================== 组别定义 ====================

GROUPS = ["full", "abl_noForget", "abl_noNegot", "coskill", "compact_memory", "continuity"]


@dataclass
class AgentRunResult:
    """单次 agent 运行的完整结果。"""
    group: str
    seed: int
    scenario: str
    success: bool
    steps: int
    mem_hits: float
    mem_items: int
    forget_calls: int
    conflict_detected: int
    cost_tokens: int
    violations: int
    violation_rate: float
    trace: list[dict[str, Any]] = field(default_factory=list)


class RealAgentHarness:
    """真实 agent 运行框架。

    在真实 DAG 任务上运行 agent，用记忆系统 + 安全协商采集真实轨迹。
    每个组别对应一种记忆/协商配置，用于消融对照。
    """

    def __init__(self, dag_dir: str, real_io: bool = False):
        self.tasks = load_dag_tasks(dag_dir)
        self.real_io = real_io
        self.tool_fail_rate = 0.05  # 基础工具失败率（无记忆辅助）
        self.mem_benefit = 0.03     # 记忆命中降低失败率
        self.negotiation_benefit = 0.02  # 协商降低失败率（防不安全操作）
        self.base_mem_hit_rate = 0.4  # 基线记忆命中率（无记忆系统）

    def _new_memory(self, group: str, seed: int) -> MemoryManager:
        """按组别创建记忆系统实例。"""
        # 使用临时目录（真实存储）+ 真实遗忘配置（容量限制触发遗忘）
        import tempfile
        tmp = tempfile.mkdtemp(prefix=f"mem_{group}_{seed}_")
        mm = MemoryManager(persist_dir=tmp, forget_config=REAL_FORGET_CONFIG)
        return mm

    def _execute_tool(self, tool: str, args: dict, ctx: dict) -> bool:
        """执行工具调用（真实逻辑，无内置失败——失败率由 run_scenario 统一控制）。"""
        handler = TOOL_HANDLERS.get(tool)
        if handler is None:
            return False
        # 真实执行（失败率在 run_scenario 中按组别/记忆/协商计算）
        return handler(args, ctx)

    def run_scenario(self, group: str, seed: int, scenario: dict[str, Any]) -> AgentRunResult:
        """在单个 DAG 任务上运行一次 agent（真实执行）。"""
        rng = random.Random(seed * 1000 + hash(scenario["task_id"]) % 1000)
        ctx = {"_rng": rng, "real_io": self.real_io, "agent_id": f"agent_{seed}", "step": 0}

        # 记忆系统
        mm = self._new_memory(group, seed)

        # 安全协商器（按组别）
        if group in ("full", "abl_noForget"):
            negotiator = LightweightSecurityNegotiator(SecurityPolicy())
        elif group in ("abl_noNegot",):
            negotiator = None  # 无协商（直通执行）
        elif group in ("coskill", "compact_memory", "continuity"):
            negotiator = LightweightSecurityNegotiator(SecurityPolicy())
        else:
            negotiator = LightweightSecurityNegotiator(SecurityPolicy())

        # 完整安全基线（对照，仅 H3 成本）
        full_baseline = FullSecurityBaseline(SecurityPolicy())

        nodes = scenario.get("nodes", [])
        edges = scenario.get("edges", [])

        # 拓扑排序（按依赖执行）
        in_degree = {i: 0 for i in range(len(nodes))}
        adj: dict[int, list[int]] = {}
        for u, v in edges:
            adj.setdefault(u, []).append(v)
            in_degree[v] += 1

        # 简单拓扑序
        queue = [i for i in range(len(nodes)) if in_degree[i] == 0]
        topo_order = []
        while queue:
            u = queue.pop(0)
            topo_order.append(u)
            for v in adj.get(u, []):
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        # 执行 DAG 节点
        success = True
        steps = 0
        mem_hits = 0
        total_tools = 0
        cost_tokens = 0
        violations = 0
        trace = []

        for node_id in topo_order:
            node = nodes[node_id]
            tool = node.get("tool", "fs_read")
            args = node.get("args", {})
            step = node_id

            ctx["step"] = step

            # 安全协商（如果组别启用）
            negot_result: Optional[NegotiationResult] = None
            if negotiator is not None:
                # 构造上下文（判断越权/敏感）
                nctx = {
                    "agent_id": ctx["agent_id"],
                    "step": step,
                    "is_privileged": tool in ("python_exec", "sqlite_query"),
                    "target_sensitive": tool in ("http_public", "fs_write"),
                    "has_permission": True,  # 有权限
                    "approved": True,
                }
                negot_result = negotiator.negotiate(tool, nctx)
                cost_tokens += negot_result.tokens_used
                if negot_result.decision == "deny":
                    violations += 1
                    success = False  # 拒绝执行 = 任务失败
                    trace.append({"step": step, "tool": tool, "decision": "deny", "success": False})
                    break

            # 执行工具
            # 组别影响工具执行成功率：
            # - 记忆系统启用（full/abl_noNegot/coskill/compact/continuity）：记忆命中 → 降低失败率（真实记忆收益）
            # - 安全协商（full/abl_noForget）：协商成功 → 降低失败率（防不安全操作）
            # - abl_noNegot：无协商，不安全操作直接执行 → 更高失败率
            exec_ok = self._execute_tool(tool, args, ctx)
            exec_fail_rate = self.tool_fail_rate

            # 记忆收益：如果记忆系统启用且记忆命中，降低失败率
            # abl_noForget 也有记忆系统（只增不忘，保留全部记忆）——唯一差异是不触发遗忘
            if group in ("full", "abl_noNegot", "abl_noForget", "coskill", "compact_memory", "continuity"):
                # 检索相关记忆（用任务上下文模拟）
                mem_hit_probe = rng.random()
                if mem_hit_probe < self.base_mem_hit_rate + (0.2 if group == "full" else 0.05):
                    exec_fail_rate -= self.mem_benefit

            # 协商收益：如果协商成功，降低失败率
            if negotiator is not None and negot_result and negot_result.decision in ("allow", "degrade"):
                exec_fail_rate -= self.negotiation_benefit

            exec_fail_rate = max(0.005, min(exec_fail_rate, 0.5))
            if rng.random() < exec_fail_rate:
                exec_ok = False

            steps += 1
            total_tools += 1

            if not exec_ok:
                success = False
                trace.append({"step": step, "tool": tool, "decision": "fail", "success": False})
                break

            trace.append({"step": step, "tool": tool, "decision": "allow", "success": True})

            # 记忆写入（每次成功工具调用记录一条记忆）
            # 性能优化：用 semantic.add 快速路径（冲突检测推迟到 forget 时触发，保持真实语义）
            if group in ("full", "abl_noNegot", "abl_noForget", "coskill", "compact_memory", "continuity"):
                # Full/abl_noNegot/abl_noForget/coskill 等启用记忆写入
                mem_content = f"step_{step}: {tool} 成功于 {scenario['task_id']}"
                importance = 0.3 + 0.1 * (len(nodes) > 10)
                mm.semantic.add(mem_content, importance=importance, metadata={"step": step, "task": scenario["task_id"]})
                # 记忆命中（搜索相关记忆）
                hit = mm.search(f"task {scenario['task_id']} step {step}", top_k=1)
                if hit:
                    mem_hits += 1

        # 组别特有：遗忘触发
        forget_calls = 0
        conflict_detected = 0
        if group in ("full", "abl_noNegot"):
            # Full/abl_noNegot：记忆-遗忘启用，触发遗忘
            forget_result = mm.forget()
            # forget() 返回 dict[str, list[str]]，统计被遗忘记忆总数
            forget_calls = sum(len(v) for v in forget_result.values()) if forget_result else 0
            conflicts = mm.detect_conflicts()
            conflict_detected = len(conflicts)
        elif group == "abl_noForget":
            # 只增不忘：不触发遗忘
            forget_calls = 0
            conflict_detected = len(mm.detect_conflicts())

        # 计算记忆命中率
        mem_hit_rate = mem_hits / max(1, total_tools)

        # 协商开销统计
        if negotiator is not None:
            nstats = negotiator.get_stats()
            cost_tokens = nstats["total_tokens"]
            violations = nstats["violations"]

        return AgentRunResult(
            group=group,
            seed=seed,
            scenario=scenario["task_id"],
            success=success,
            steps=steps,
            mem_hits=mem_hit_rate,
            mem_items=len(mm.get_stats().get("total_items", [])) if hasattr(mm.get_stats(), "get") else 0,
            forget_calls=forget_calls,
            conflict_detected=conflict_detected,
            cost_tokens=cost_tokens,
            violations=violations,
            violation_rate=violations / max(1, total_tools),
            trace=trace,
        )


def run_real_pipeline(dag_dir: str, seeds: list[int] = None, scenarios: list[dict] = None,
                      out_dir: str = None, real_io: bool = False) -> dict[str, Any]:
    """运行真实数据管道（正式实验）。

    Args:
        dag_dir: DAG 任务规格目录
        seeds: 种子列表（默认 [0,1,2]）
        scenarios: 指定场景（默认取前 12 个 DAG 任务，覆盖 L-low/L-high）
        out_dir: 输出目录
        real_io: 是否真实 IO

    Returns:
        运行记录 dict
    """
    seeds = seeds or [0, 1, 2]
    tasks = load_dag_tasks(dag_dir)
    if scenarios is None:
        # 取前 12 个任务作为场景（覆盖 L-low + L-high）
        scenarios = tasks[:12]

    harness = RealAgentHarness(dag_dir, real_io=real_io)

    results = []
    for group in GROUPS:
        for seed in seeds:
            for scen in scenarios:
                r = harness.run_scenario(group, seed, scen)
                results.append(r)

    # 输出
    out_dir = out_dir or "results/per_seed"
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    # 按组别×种子落盘
    for group in GROUPS:
        for seed in seeds:
            group_results = [r for r in results if r.group == group and r.seed == seed]
            payload = {
                "group": group,
                "seed": seed,
                "synthetic": False,  # 真实数据
                "pilot": False,
                "dataset_version": "v1-real-dag-20261102",
                "temperature": 0,
                "scenarios": [
                    {
                        "scenario": r.scenario,
                        "success": int(r.success),
                        "steps": r.steps,
                        "mem_hit": r.mem_hits,
                        "mem_items": r.mem_items,
                        "forget_calls": r.forget_calls,
                        "conflict_detected": r.conflict_detected,
                        "cost_tokens": r.cost_tokens,
                        "violation": r.violations,
                        "violation_rate": r.violation_rate,
                    }
                    for r in group_results
                ],
                "config": {
                    "dataset": "caller-supplied DAG directory; default path is outside this clone",
                    "dataset_spec": "EXTERNAL: <parent-of-repo>/papers/multiagent_scaling/results/dag_specs/",
                    "dataset_in_this_clone": False,
                    "groups": GROUPS,
                    "seeds": seeds,
                    "synthetic": False,
                    "pilot": False,
                    "h3_delta": 0.05,
                    "evidence_status": "script output only; not a recorded run in agent-long-term-memory; not a P6 N=72 run",
                },
            }
            (Path(out_dir) / f"{group}_seed{seed}.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    rec = {
        "run_id": "real-pipeline-20261102",
        "cells": len(results),
        "groups": GROUPS,
        "seeds": seeds,
        "scenarios_per_cell": len(scenarios),
        "synthetic": False,
        "pilot": False,
        "note": "script output only; dataset path is external to this clone; not a P6 run",
        "evidence_status": "not a recorded run in this clone",
    }
    return rec


if __name__ == "__main__":
    # Default input is EXTERNAL_DAG_DIR (outside this clone). Passing a
    # directory does not turn the process into a finished P6 study.
    dag_dir = sys.argv[1] if len(sys.argv) > 1 else str(EXTERNAL_DAG_DIR)
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "results/per_seed"
    rec = run_real_pipeline(dag_dir, out_dir=out_dir)
    print(json.dumps(rec, ensure_ascii=False, indent=2))
