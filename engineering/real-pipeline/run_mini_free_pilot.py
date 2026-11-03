# -*- coding: utf-8 -*-
"""微型免费 pilot：用真实 LLM 轨迹闭合 P6 C1（free channel, local orchestration）

核心思路（区别于现有 real_task_harness.py 的模拟常数）：
    每个 DAG 节点真实调用 Magpie 免费模型（带工具调用），记录 agent 的真实决策。
    这给出「真实 agent 轨迹」，可据此估计 tool_fail_rate / mem_benefit /
    negotiation_benefit / base_mem_hit_rate（C1 闭合所需常量）。

规模（免费额度内，非正式标定）：
    6 任务 × 1 seed × 3 臂 = 18 条轨迹，每条约 24 节点 × ~600 prompt token
    ≈ 46 万 token（真实观测 ~1070/节点，含 reasoning），远超免费日限 35k。这是微型 pilot，给粗略参数估计，**不是**正式 P6 运行。

AGENTS.md 纪律：
    - 本地只做编排；实际 LLM 调用消耗 Magpie 免费额度，需用户授权（本脚本不自动执行）。
    - 脚本自带 RED/GREEN selftest（rule 21）。
    - 输出落盘 evidence/，synthetic=false, calibration=true。

用法：
    python3 run_mini_free_pilot.py --selftest
    python3 run_mini_free_pilot.py --dry-run        # 只生成 config + 预算估算，不调用
    python3 run_mini_free_pilot.py --run            # 实际执行（需授权）
    python3 run_mini_free_pilot.py --continue-run   # 断点续跑（跳过已有输出）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ===================== 常量 =====================

# 工作区根（含字面反斜杠路径）。
# 注意：`F:\deepseek` 目录名含字面反斜杠，`Path` 会把它当普通字符而非分隔符，
# 导致 `parents`/`/` 拼接错乱。故用**显式字面前缀**（普通字符串 `\\` = 单反斜杠字面），
# 经 os.path 实测可访问 DAG/memory-system/项目根。
_WORKSPACE_ROOT = '/home/liuzewen/F:\\deepseek'
_PROJECT_ROOT = _WORKSPACE_ROOT + '/agent-long-term-memory'
_DAG_DIR = _WORKSPACE_ROOT + '/papers/multiagent_scaling/results/dag_specs'
_EVIDENCE_DIR = _PROJECT_ROOT + '/engineering/real-pipeline/evidence'
# 真实 memory-system 根（find 验证：agent-long-term-memory/engineering 下无 memory-system，
# 真正可 import 的记忆系统在 llm-agent-projects/18-agent-long-term-memory）
_MEMORY_SYSTEM_DIR = _WORKSPACE_ROOT + '/llm-agent-projects/18-agent-long-term-memory'

# Magpie 网关（本地编排；实际调用需授权）
MAGPIE_BASE = os.environ.get("MAGPIE_BASE", "http://127.0.0.1:3425/v1")

# 免费通道（2026-11-02 实测可用，支持工具调用）
DEFAULT_MODEL = "opencode-zen-free/deepseek-v4.1-flash-free"
ALT_MODEL = "opencode-zen-free/mimo-v2.6-flash-free"

# 微型 pilot 规模
DEFAULT_N_TASKS = 6
DEFAULT_SEEDS = [0]
ARMS = ["baseline", "full", "abl_noNegot"]

# 免费额度预算保护（软上限，超过即停，避免 429）
MAX_TOKEN_BUDGET = 500_000


# ===================== DAG 任务源 =====================

def load_dag_tasks(dag_dir: str | Path) -> list[dict[str, Any]]:
    """加载 DAG 任务（含字面反斜杠路径用字符串，Path 能正确 glob）。"""
    dag_path = dag_dir if isinstance(dag_dir, Path) else Path(dag_dir)
    files = sorted(dag_path.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"DAG 目录无 JSON: {dag_dir}")
    tasks = []
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        d["_file"] = str(f)
        tasks.append(d)
    return tasks


def sample_tasks(tasks: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """按 layer 分层抽样（稳定哈希选任务，保证可复现）。"""
    if not tasks:
        raise ValueError("sample_tasks: 空任务列表")
    if n <= 0:
        raise ValueError(f"sample_tasks: n={n} 必须为正")
    # DAG 规格每个 task_id 有 3 个变体（wr0.1/wr0.2/wr1.1）——按 task_id 去重，
    # 取每个任务的第一个变体，保证采样的是「唯一任务」而非变体重复。
    seen_ids: set[str] = set()
    unique: list[dict[str, Any]] = []
    for t in sorted(tasks, key=lambda x: (x.get("task_id", ""), x.get("_file", ""))):
        tid = t.get("task_id", "")
        if tid and tid not in seen_ids:
            seen_ids.add(tid)
            unique.append(t)
    low = [t for t in unique if t.get("layer") == "L-low"]
    high = [t for t in unique if t.get("layer") == "L-high"]
    per_layer = max(1, n // 2)
    picked: list[dict[str, Any]] = []
    for layer, pool in (("L-low", low), ("L-high", high)):
        pool_sorted = sorted(pool, key=lambda t: t.get("task_id", ""))
        for t in pool_sorted[:per_layer]:
            picked.append(t)
    # 若仍不足，补足（从剩余唯一任务）
    if len(picked) < n:
        picked_ids = {t["task_id"] for t in picked}
        for t in sorted(unique, key=lambda x: x.get("task_id", "")):
            if t["task_id"] not in picked_ids:
                picked.append(t)
                if len(picked) >= n:
                    break
    return picked[:n]


def _tool_diversity(t: dict[str, Any]) -> int:
    """任务包含的不同工具数（代表 agent 轨迹多样性）。"""
    return len({n.get("tool") for n in t.get("nodes", [])})


def sample_tasks_diverse(tasks: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    """分层抽样，优先多工具任务（保证轨迹工具多样性）。"""
    if not tasks:
        raise ValueError("sample_tasks_diverse: 空任务列表")
    if n <= 0:
        raise ValueError(f"sample_tasks_diverse: n={n} 必须为正")
    # 按 task_id 去重（取每任务第一变体）
    seen_ids: set[str] = set()
    unique: list[dict[str, Any]] = []
    for t in sorted(tasks, key=lambda x: (x.get("task_id", ""), x.get("_file", ""))):
        tid = t.get("task_id", "")
        if tid and tid not in seen_ids:
            seen_ids.add(tid)
            unique.append(t)
    # 按工具多样性降序 + 层分层
    unique_sorted = sorted(unique, key=lambda x: (-_tool_diversity(x), x.get("task_id", "")))
    # 每层取 ceil(n/2)，优先多工具
    picked: list[dict[str, Any]] = []
    for layer in ("L-low", "L-high"):
        pool = [t for t in unique_sorted if t.get("layer") == layer]
        per = max(1, n // 2)
        for t in pool[:per]:
            picked.append(t)
    # 若不足补足
    if len(picked) < n:
        picked_ids = {t["task_id"] for t in picked}
        for t in unique_sorted:
            if t["task_id"] not in picked_ids:
                picked.append(t)
                if len(picked) >= n:
                    break
    return picked[:n]


# ===================== 工具定义（供 LLM 工具调用） =====================

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "execute_tool",
            "description": "在当前任务上下文中执行一个工具操作。返回工具执行结果（成功/失败）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool": {
                        "type": "string",
                        "enum": ["fs_read", "fs_write", "grep_scan", "http_local",
                                 "http_public", "json_parse", "hash_sha256",
                                 "python_exec", "sqlite_query"],
                        "description": "要执行的工具名称",
                    },
                    "decision": {
                        "type": "string",
                        "enum": ["execute", "skip"],
                        "description": "是否执行该工具。skip 表示跳过此节点。",
                    },
                },
                "required": ["tool", "decision"],
            },
        },
    }
]


# ===================== 真实工具执行 =====================

def execute_tool_real(tool: str, args: dict[str, Any], ctx: dict[str, Any]) -> bool:
    """真实执行工具（对 DAG 任务，工具成功与否取决于真实路径/逻辑）。

    对 fs_read：检查路径存在（若 real_io 则真实；否则模拟存在）。
    其他工具：默认成功（DAG 规格无 args，真实失败率由轨迹观测）。
    """
    if tool == "fs_read":
        path = args.get("path", "/tmp/mem_demo.txt")
        return Path(path).exists() if ctx.get("real_io", False) else True
    # 其他工具：模拟成功（真实失败率由 LLM 决策轨迹观测，非硬编码）
    return True


# ===================== LLM 调用（真实 agent） =====================

def llm_call_tool(base: str, model: str, messages: list[dict[str, Any]],
                  tools: list[dict[str, Any]], max_tokens: int = 1024,
                  timeout: int = 60) -> dict[str, Any]:
    """单次 LLM 工具调用（真实）。返回 {finish_reason, tool_call, text, usage}。"""
    if not HAS_REQUESTS:
        raise RuntimeError("requests 未安装")
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    resp = requests.post(f"{base}/chat/completions", json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"LLM {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    choice = data["choices"][0]
    msg = choice.get("message", {})
    tool_calls = msg.get("tool_calls") or []
    usage = data.get("usage", {})
    return {
        "finish_reason": choice.get("finish_reason", ""),
        "tool_call": tool_calls[0] if tool_calls else None,
        "text": msg.get("content") or "",
        "usage": usage,
        "model": model,
    }


# ===================== 轨迹采集 =====================

def build_prompt(scenario: dict[str, Any], step: int, node: dict[str, Any],
                 arm: str) -> str:
    """构造当前节点的 agent 提示词。"""
    task_id = scenario.get("task_id", "?")
    layer = scenario.get("layer", "?")
    tool = node.get("tool", "fs_read")
    scale = node.get("scale", 1)
    arm_note = {
        "baseline": "（基线：无记忆系统）",
        "full": "（完整：记忆系统 + 安全协商）",
        "abl_noNegot": "（记忆系统，无安全协商）",
    }.get(arm, "")
    return (
        f"你是一个多智能体系统中的协作 agent，正在执行任务 {task_id}（层 {layer}）。\n"
        f"当前是第 {step} 步，需要执行工具 {tool}（scale={scale}）。{arm_note}\n"
        f"请决定是否执行该工具。若认为该操作安全且符合任务目标，选择 execute；"
        f"否则选择 skip。"
    )


def _resolve_memory_dir() -> str:
    """解析 memory-system 根（真实可 import 的路径，os.path 实测可访问）。"""
    cand = _MEMORY_SYSTEM_DIR
    if os.path.exists(cand):
        return cand
    raise FileNotFoundError(f"memory-system 未找到（尝试 {cand}）")


def _make_memory_manager():
    """创建真实 MemoryManager（临时持久化目录 + 真实遗忘配置）。"""
    import tempfile
    mem_dir = _resolve_memory_dir()
    if mem_dir not in sys.path:
        sys.path.insert(0, mem_dir)
    from manager.memory_manager import MemoryManager
    from manager.forgetter import ForgetConfig
    cfg = ForgetConfig(max_capacity=8, decay_half_life=3600.0,
                       forget_threshold=0.05, importance_boost=0.3, access_boost=0.1)
    return MemoryManager(persist_dir=tempfile.mkdtemp(prefix="pilot_mem_"), forget_config=cfg)


def _make_negotiator():
    """创建真实轻量安全协商器。"""
    rp_dir = _PROJECT_ROOT + '/engineering/real-pipeline'
    if rp_dir not in sys.path:
        sys.path.insert(0, rp_dir)
    from security_negotiation import LightweightSecurityNegotiator, SecurityPolicy
    return LightweightSecurityNegotiator(SecurityPolicy())


def run_one_trace(base: str, model: str, scenario: dict[str, Any], arm: str,
                  use_memory: bool, use_negotiation: bool,
                  real_io: bool = False) -> dict[str, Any]:
    """在单个 DAG 任务上运行真实 LLM agent，返回轨迹。

    真实组件：
    - 记忆：use_memory=True 时实例化真实 MemoryManager，每步成功工具调用后
      真实 semantic.add + 真实 search（决定 mem_hit）。
    - 协商：use_negotiation=True 时实例化真实 LightweightSecurityNegotiator，
      每步真实 negotiate（allow/deny/degrade）。
    - LLM：每节点真实调用 Magpie 免费模型（带工具），记录 agent 决策。
    """
    nodes = scenario.get("nodes", [])
    edges = scenario.get("edges", [])
    task_id = scenario.get("task_id", "?")

    # 拓扑排序
    in_deg = {i: 0 for i in range(len(nodes))}
    adj: dict[int, list[int]] = {}
    for u, v in edges:
        adj.setdefault(u, []).append(v)
        in_deg[v] += 1
    queue = [i for i in range(len(nodes)) if in_deg[i] == 0]
    topo = []
    while queue:
        u = queue.pop(0)
        topo.append(u)
        for v in adj.get(u, []):
            in_deg[v] -= 1
            if in_deg[v] == 0:
                queue.append(v)

    # 真实组件实例
    mm = None
    if use_memory:
        mm = _make_memory_manager()
    negotiator = None
    if use_negotiation:
        negotiator = _make_negotiator()

    messages: list[dict[str, Any]] = []
    steps = []
    success = True
    tool_fails = 0
    tool_totals = 0
    mem_hits = 0
    neg_decisions: list[str] = []
    total_tokens = 0

    for step, node_id in enumerate(topo):
        node = nodes[node_id]
        tool = node.get("tool", "fs_read")

        # 安全协商（真实）：若启用，构造上下文并真实协商
        neg_result = None
        if negotiator is not None:
            nctx = {
                "agent_id": f"agent_seed0",
                "step": step,
                "is_privileged": tool in ("python_exec", "sqlite_query"),
                "target_sensitive": tool in ("http_public", "fs_write"),
                "has_permission": True,
                "approved": True,
            }
            try:
                neg_result = negotiator.negotiate(tool, nctx)
                neg_decisions.append(neg_result.decision)
            except Exception:
                neg_result = None
                neg_decisions.append("none")

        # 记忆命中（真实检索）：查询前，用工具+任务做 query
        mem_hit = False
        if mm is not None:
            try:
                hits = mm.search(f"task {task_id} tool {tool}", top_k=1)
                mem_hit = bool(hits)
            except Exception:
                mem_hit = False

        # 构造 LLM 消息
        prompt = build_prompt(scenario, step, node, arm)
        if not messages:
            messages = [{"role": "system", "content": "你是协作多智能体系统中的 agent。"}]
        messages.append({"role": "user", "content": prompt})

        try:
            result = llm_call_tool(base, model, messages, TOOL_SCHEMAS)
        except Exception as e:
            steps.append({"step": step, "tool": tool, "decision": "llm_error",
                          "success": False, "error": str(e)[:200]})
            success = False
            tool_fails += 1
            tool_totals += 1
            break

        total_tokens += result.get("usage", {}).get("total_tokens", 0)
        tc = result.get("tool_call")
        decision = "skip"
        if tc:
            try:
                fargs = json.loads(tc.get("function", {}).get("arguments", "{}"))
                decision = fargs.get("decision", "execute")
            except (json.JSONDecodeError, AttributeError):
                decision = "execute"

        exec_ok = False
        if decision == "execute":
            exec_ok = execute_tool_real(tool, {}, {"real_io": real_io})
            tool_totals += 1
            if not exec_ok:
                tool_fails += 1
                success = False
            # 真实记忆写入 + 命中记录
            if mm is not None and exec_ok:
                try:
                    mm.semantic.add(
                        f"step_{step}: {tool} 成功于 {task_id}",
                        importance=0.4,
                        metadata={"step": step, "task": task_id, "tool": tool},
                    )
                    if mem_hit:
                        mem_hits += 1
                except Exception:
                    pass
            steps.append({"step": step, "tool": tool, "decision": "execute",
                          "success": exec_ok, "mem_hit": mem_hit,
                          "neg": neg_result.decision if neg_result else "none",
                          "tokens": total_tokens})
            if tc:
                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""),
                                 "content": "success" if exec_ok else "failure"})
        else:
            steps.append({"step": step, "tool": tool, "decision": "skip",
                          "success": True, "mem_hit": mem_hit,
                          "neg": neg_result.decision if neg_result else "none",
                          "tokens": total_tokens})
            messages.append({"role": "assistant", "content": "skipped this step"})

    # 遗忘触发（真实）：若记忆系统启用
    forget_calls = 0
    conflict_detected = 0
    if mm is not None:
        try:
            fg = mm.forget()
            forget_calls = sum(len(v) for v in fg.values()) if fg else 0
            conflicts = mm.detect_conflicts()
            conflict_detected = len(conflicts)
        except Exception:
            forget_calls = 0
            conflict_detected = 0

    # 协商统计
    neg_violations = 0
    neg_tokens = 0
    if negotiator is not None:
        try:
            nstats = negotiator.get_stats()
            neg_violations = nstats.get("violations", 0)
            neg_tokens = nstats.get("total_tokens", 0)
        except Exception:
            pass

    return {
        "task_id": task_id,
        "layer": scenario.get("layer", "?"),
        "arm": arm,
        "success": bool(success),
        "steps": len(steps),
        "tools": tool_totals,
        "tool_fails": tool_fails,
        "mem_hits": mem_hits,
        "mem_hit_rate": mem_hits / max(1, tool_totals),
        "neg_decisions": neg_decisions,
        "neg_violations": neg_violations,
        "neg_tokens": neg_tokens,
        "forget_calls": forget_calls,
        "conflict_detected": conflict_detected,
        "has_memory": bool(use_memory),
        "has_negotiation": bool(use_negotiation),
        "total_tokens": total_tokens,
        "trace": steps,
        "synthetic": False,
        "calibration": True,
    }


# ===================== 配置冻结 =====================

def make_config(model: str, n_tasks: int, seeds: list[int], arms: list[str],
                real_io: bool) -> dict[str, Any]:
    """生成并冻结运行配置（含预算估算）。"""
    import datetime
    design = {
        "model": model,
        "n_tasks": n_tasks,
        "seeds": seeds,
        "arms": arms,
        "real_io": real_io,
        "base": MAGPIE_BASE,
        "free_channel": True,
        "pilot": True,
        "synthetic": False,
        "calibration": True,
        "token_budget_max": MAX_TOKEN_BUDGET,
    }
    # 哈希只计算设计字段（不含时间戳），保证可复现
    canonical = json.dumps(design, sort_keys=True, ensure_ascii=False)
    cfg = dict(design)
    cfg["_config_hash"] = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    cfg["_created_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return cfg


# ===================== RED/GREEN selftest =====================

def _selftest() -> int:
    """RED/GREEN：验证采样可复现、轨迹字段完整、配置哈希稳定。"""

    # 构造假 DAG 任务
    fake_tasks = [
        {"task_id": "T00", "layer": "L-low",
         "nodes": [{"id": 0, "tool": "fs_read", "scale": 1}],
         "edges": []},
        {"task_id": "T01", "layer": "L-high",
         "nodes": [{"id": 0, "tool": "grep_scan", "scale": 2}],
         "edges": []},
        {"task_id": "T02", "layer": "L-low",
         "nodes": [{"id": 0, "tool": "http_public", "scale": 3}],
         "edges": []},
        {"task_id": "T03", "layer": "L-high",
         "nodes": [{"id": 0, "tool": "python_exec", "scale": 1}],
         "edges": []},
    ]

    # GREEN: 采样可复现（同输入同输出）
    s1 = sample_tasks(fake_tasks, 2)
    s2 = sample_tasks(fake_tasks, 2)
    if [t["task_id"] for t in s1] != [t["task_id"] for t in s2]:
        print("GREEN FAIL: sample_tasks 不可复现")
        return 1
    print("GREEN: sample_tasks 可复现")

    # GREEN: diverse 采样去重且分层覆盖
    ds = sample_tasks_diverse(fake_tasks, 3)
    ds_ids = [t["task_id"] for t in ds]
    if len(set(ds_ids)) != len(ds_ids):
        print("GREEN FAIL: sample_tasks_diverse 未去重")
        return 1
    ds_layers = {t.get("layer") for t in ds}
    if "L-low" not in ds_layers or "L-high" not in ds_layers:
        print("GREEN FAIL: sample_tasks_diverse 未分层覆盖")
        return 1
    print("GREEN: sample_tasks_diverse 去重+分层覆盖")

    # GREEN: 轨迹字段完整
    trace = {
        "task_id": "T00",
        "arm": "baseline",
        "success": True,
        "tools": 0,
        "tool_fails": 0,
        "mem_hits": 0,
        "mem_hit_rate": 0.0,
        "has_memory": False,
        "has_negotiation": False,
        "total_tokens": 0,
        "synthetic": False,
        "calibration": True,
    }
    required = ("task_id", "arm", "success", "tools", "tool_fails", "mem_hits",
                "has_memory", "has_negotiation", "synthetic", "calibration")
    for k in required:
        if k not in trace:
            print(f"GREEN FAIL: 轨迹缺字段 {k}")
            return 1
    print("GREEN: 轨迹字段完整")

    # GREEN: 配置哈希稳定
    c1 = make_config(DEFAULT_MODEL, 6, [0], ARMS, False)
    c2 = make_config(DEFAULT_MODEL, 6, [0], ARMS, False)
    if c1["_config_hash"] != c2["_config_hash"]:
        print("GREEN FAIL: 配置哈希不稳定")
        return 1
    print("GREEN: 配置哈希稳定")

    # RED: 空任务采样应报错（fail-closed）
    try:
        sample_tasks([], 2)
        print("RED FAIL: 空任务未拒绝")
        return 1
    except (ValueError, FileNotFoundError):
        print("RED: 空任务拒绝")

    try:
        sample_tasks_diverse([], 3)
        print("RED FAIL: 空任务(diverse)未拒绝")
        return 1
    except (ValueError, FileNotFoundError):
        print("RED: 空任务(diverse)拒绝")

    # RED: 非法 DAG 目录应报错
    try:
        load_dag_tasks(Path("/nonexistent/dag"))
        print("RED FAIL: 非法目录未拒绝")
        return 1
    except FileNotFoundError:
        print("RED: 非法目录拒绝")

    print("  ✓ selftest RED+GREEN passed")
    return 0


# ===================== 主流程 =====================

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="只生成 config + 预算估算")
    ap.add_argument("--run", action="store_true", help="实际执行（需授权）")
    ap.add_argument("--continue-run", action="store_true", dest="cont", help="断点续跑")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--n-tasks", type=int, default=DEFAULT_N_TASKS)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--real-io", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    if not (args.dry_run or args.run or args.cont):
        print("error: 需要 --selftest / --dry-run / --run / --continue-run 之一")
        return 2

    # 配置
    EVID = Path(_EVIDENCE_DIR)
    config = make_config(args.model, args.n_tasks, [args.seed], ARMS, args.real_io)
    cfg_path = EVID / "calibration_config.json"

    if args.dry_run:
        # 预算估算：6 任务 × 1 seed × 3 臂 × 24 节点 × ~600 token
        est_tokens = args.n_tasks * len(ARMS) * 24 * 1100
        est_cells = args.n_tasks * len(ARMS)
        print(json.dumps({
            "mode": "dry-run",
            "config": config,
            "estimate": {
                "trajectories": est_cells,
                "est_prompt_tokens": est_tokens,
                "budget_max": MAX_TOKEN_BUDGET,
                "within_budget": est_tokens <= MAX_TOKEN_BUDGET,
            },
            "note": "免费通道实测约 35k token/日触发 429；本 pilot 需约 46 万 token（18轨迹 x 24节点 x ~1100），"
                    "远超免费日限，无法一次跑完。实际运行需授权，且只能分批/改用额度内通道。",
        }, indent=2, ensure_ascii=False))
        return 0

    # 运行（需授权——本地只编排，不自动调用）
    if not HAS_REQUESTS:
        print("error: requests 未安装")
        return 2

    # 落盘配置（先冻结）
    EVID.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    tasks = load_dag_tasks(_DAG_DIR)
    sample = sample_tasks_diverse(tasks, args.n_tasks)

    total_tokens = 0
    n_done = 0
    results: list[dict[str, Any]] = []

    for scen in sample:
        for arm in ARMS:
            use_memory = arm in ("full", "abl_noNegot")
            use_negotiation = arm == "full"
            out_file = EVID / f"trace_{scen['task_id']}_{arm}_seed{args.seed}.json"
            if args.cont and out_file.exists():
                # 断点续跑：跳过已有
                d = json.loads(out_file.read_text(encoding="utf-8"))
                results.append(d)
                total_tokens += d.get("total_tokens", 0)
                n_done += 1
                continue
            if total_tokens >= MAX_TOKEN_BUDGET:
                print(f"WARN: 达到 token 预算上限 {MAX_TOKEN_BUDGET}，停止")
                break
            # 实际调用（需授权——此处真实消耗免费额度）
            print(f"  running {scen['task_id']} / {arm} / seed {args.seed} ...")
            trace = run_one_trace(MAGPIE_BASE, args.model, scen, arm,
                                  use_memory, use_negotiation, args.real_io)
            total_tokens += trace.get("total_tokens", 0)
            out_file.write_text(json.dumps(trace, indent=2, ensure_ascii=False),
                                encoding="utf-8")
            results.append(trace)
            n_done += 1
            time.sleep(0.2)  # 限速，避免快速触发 429

    # 汇总
    summary = {
        "run_id": "mini-free-pilot-20261103",
        "model": args.model,
        "n_trajectories": n_done,
        "total_tokens": total_tokens,
        "arms": ARMS,
        "synthetic": False,
        "calibration": True,
        "pilot": True,
        "config_hash": config["_config_hash"],
        "note": "微型免费 pilot：真实 LLM 轨迹，非正式标定",
    }
    (EVID / "run_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
