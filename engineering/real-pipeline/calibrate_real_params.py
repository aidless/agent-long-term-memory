# -*- coding: utf-8 -*-
"""Real-parameter calibration from real agent traces.

Estimates tool_fail_rate / mem_benefit / negotiation_benefit /
base_mem_hit_rate from REAL LLM-agent trajectory evidence (synthetic=false).

Usage:
    python3 calibrate_real_params.py --evidence <dir> --config <json>
    python3 calibrate_real_params.py --selftest

The script MUST re-derive every constant from the traces (not hand-typed),
and MUST pass RED/GREEN self-test (AGENTS.md rule 21).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any


# ===================== Estimation from traces =====================

def estimate_from_traces(traces: list[dict[str, Any]]) -> dict[str, float]:
    """Re-derive calibration constants from a list of real-agent run traces.

    Each trace is a per-run dict with keys:
        success (bool), steps (int), mem_hits (int), tools (int),
        neg_decision (str), has_memory (bool), has_negotiation (bool)

    Returns estimated constants (mean over runs).
    """
    if not traces:
        raise ValueError("no traces to estimate from")

    tool_fails = 0
    tool_totals = 0
    mem_hits = 0
    mem_totals = 0
    mem_success = []
    no_mem_success = []
    neg_success = []
    no_neg_success = []

    for t in traces:
        # 必须字段校验：缺失即拒绝（避免静默用 0 造成假估计）
        required = ("tools", "tool_fails", "mem_hits", "success",
                    "has_memory", "has_negotiation")
        for key in required:
            if key not in t:
                raise KeyError(f"trace missing required key: {key}")
        tools = t.get("tools", 0)
        fails = t.get("tool_fails", 0)
        tool_totals += tools
        tool_fails += fails
        mem_hits += t.get("mem_hits", 0)
        mem_totals += tools
        # 组别成功
        if t.get("has_memory"):
            mem_success.append(1.0 if t.get("success") else 0.0)
        else:
            no_mem_success.append(1.0 if t.get("success") else 0.0)
        if t.get("has_negotiation"):
            neg_success.append(1.0 if t.get("success") else 0.0)
        else:
            no_neg_success.append(1.0 if t.get("success") else 0.0)

    tool_fail_rate = tool_fails / max(1, tool_totals)
    base_mem_hit_rate = mem_hits / max(1, mem_totals)

    def _mean(xs: list[float]) -> float:
        return statistics.mean(xs) if xs else 0.0

    mem_benefit = _mean(mem_success) - _mean(no_mem_success)
    neg_benefit = _mean(neg_success) - _mean(no_neg_success)

    return {
        "tool_fail_rate": round(tool_fail_rate, 6),
        "mem_benefit": round(mem_benefit, 6),
        "negotiation_benefit": round(neg_benefit, 6),
        "base_mem_hit_rate": round(base_mem_hit_rate, 6),
        "n_traces": len(traces),
        "n_tools": tool_totals,
    }


# ===================== RED/GREEN self-test =====================

def _selftest() -> int:
    """RED/GREEN self-test: inject violation -> reject; valid -> accept."""
    # GREEN: valid traces with clear direction
    valid_traces = [
        {"success": True, "tools": 10, "tool_fails": 1, "mem_hits": 8,
         "has_memory": True, "has_negotiation": True},
        {"success": False, "tools": 10, "tool_fails": 3, "mem_hits": 5,
         "has_memory": True, "has_negotiation": True},
        {"success": False, "tools": 10, "tool_fails": 4, "mem_hits": 0,
         "has_memory": False, "has_negotiation": False},
    ]
    est = estimate_from_traces(valid_traces)
    # GREEN assertions: estimates are in valid range and re-derivable
    assert 0 <= est["tool_fail_rate"] <= 1, "tool_fail_rate out of range"
    assert -1 <= est["mem_benefit"] <= 1, "mem_benefit out of range"
    assert 0 <= est["base_mem_hit_rate"] <= 1, "base_mem_hit_rate out of range"
    # re-derive manually to prove not hand-typed
    manual_fail = (1 + 3 + 4) / (10 + 10 + 10)
    assert abs(est["tool_fail_rate"] - round(manual_fail, 6)) < 1e-9, \
        "tool_fail_rate not re-derived"
    print("  GREEN: valid traces -> estimates accepted (re-derived)")

    # RED: empty traces must raise
    try:
        estimate_from_traces([])
        print("  RED FAIL: empty traces did not raise")
        return 1
    except ValueError:
        print("  RED: empty traces rejected (ValueError)")

    # RED: missing key must raise (malformed trace)
    try:
        estimate_from_traces([{"success": True}])
        print("  RED FAIL: malformed trace did not raise")
        return 1
    except (KeyError, TypeError):
        print("  RED: malformed trace rejected")

    print("  ✓ selftest RED+GREEN passed")
    return 0


# ===================== CLI =====================

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--evidence", help="dir with per-run trace JSON files")
    ap.add_argument("--config", help="run config JSON (frozen before run)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    if not args.evidence:
        print("error: --evidence required (or --selftest)")
        return 2

    traces = []
    for f in sorted(Path(args.evidence).glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(d, list):
            traces.extend(d)
        elif isinstance(d, dict):
            traces.append(d)
    if not traces:
        print(f"error: no traces found in {args.evidence}")
        return 2

    est = estimate_from_traces(traces)
    print(json.dumps(est, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
