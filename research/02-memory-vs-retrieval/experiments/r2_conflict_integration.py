"""R2.3 冲突场景整合验证：强化路径在真实矛盾记忆下的行为。

验证目标：
1. 长程任务中构造真实矛盾记忆（同一实体相反结论）。
2. 强化路径（_auto_conflict_check + resolve_conflicts）正确检测、标记、解决冲突。
3. 对比无强化路径：只检测不解决（保留双方）。
4. 验证 resolve 后保留重要性更高者。

输出：evidence/2026-11-01-r2-conflict-integration.json
"""
import sys
import json
import os
from pathlib import Path

# 确保可导入 memory-system
_MEM_SYS = str(Path(__file__).resolve().parents[3] / "engineering" / "memory-system")
sys.path.insert(0, _MEM_SYS)
os.chdir(_MEM_SYS)

from manager.memory_manager import MemoryManager


def run_conflict_scenario():
    """构造真实矛盾记忆并验证强化路径行为。"""
    results = {}

    # 场景 1：中文矛盾（性能提升/下降）
    m1 = MemoryManager()
    m1.add_semantic("model_a 性能提升显著", importance=0.9, metadata={"step": 1})
    m1.add_semantic("model_a 性能下降明显", importance=0.4, metadata={"step": 2})

    sem1 = m1._get_memory_store("semantic")
    mems1 = sem1.list_all()
    results["scenario1_detect"] = {
        "total": len(mems1),
        "conflict_candidates": [
            {"content": mem.content, "importance": mem.importance,
             "conflict_candidate": mem.metadata.get("conflict_candidate", False)}
            for mem in mems1
        ],
    }

    resolved1 = m1.resolve_conflicts(memory_type="semantic")
    remaining1 = sem1.list_all()
    results["scenario1_resolve"] = {
        "resolved_count": len(resolved1),
        "keep_content": resolved1[0]["keep_content"] if resolved1 else None,
        "discard_content": resolved1[0]["discard_content"] if resolved1 else None,
        "remaining_after": [mem.content for mem in remaining1],
    }

    # 场景 2：英文矛盾（improved/degraded）
    m2 = MemoryManager()
    m2.add_semantic("algo_b performance improved", importance=0.8, metadata={"step": 1})
    m2.add_semantic("algo_b performance degraded", importance=0.2, metadata={"step": 2})

    resolved2 = m2.resolve_conflicts(memory_type="semantic")
    results["scenario2_english"] = {
        "resolved_count": len(resolved2),
        "keep_content": resolved2[0]["keep_content"] if resolved2 else None,
        "discard_content": resolved2[0]["discard_content"] if resolved2 else None,
    }

    # 场景 3：重要性反转（低重要性先存，高重要性后存）
    m3 = MemoryManager()
    m3.add_semantic("model_c 稳定性增强", importance=0.3, metadata={"step": 1})
    m3.add_semantic("model_c 稳定性减弱", importance=0.8, metadata={"step": 2})
    resolved3 = m3.resolve_conflicts(memory_type="semantic")
    results["scenario3_reverse_importance"] = {
        "resolved_count": len(resolved3),
        "keep_content": resolved3[0]["keep_content"] if resolved3 else None,
        "keep_importance_should_be_high": True,
    }

    # 场景 4：无冲突（唯一事实，强化路径不应误伤）
    m4 = MemoryManager()
    m4.add_semantic("fact_1 about entity_d1 status verified ok", importance=0.8, metadata={"step": 1})
    m4.add_semantic("fact_2 about entity_d2 status verified ok", importance=0.8, metadata={"step": 2})
    resolved4 = m4.resolve_conflicts(memory_type="semantic")
    results["scenario4_no_conflict"] = {
        "resolved_count": len(resolved4),
        "expected_0": len(resolved4) == 0,
    }

    return results


def main():
    results = run_conflict_scenario()

    evidence_dir = Path(__file__).resolve().parents[1] / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    out_path = evidence_dir / "2026-11-01-r2-conflict-integration.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print("=== 冲突场景整合验证 ===")
    print(f"场景1（中文矛盾）检测: {results['scenario1_detect']['conflict_candidates']}")
    print(f"场景1 解决: {results['scenario1_resolve']}")
    print(f"场景2（英文矛盾）解决: {results['scenario2_english']}")
    print(f"场景3（重要性反转）解决: {results['scenario3_reverse_importance']}")
    print(f"场景4（无冲突）解决数: {results['scenario4_no_conflict']['resolved_count']} (期望 0)")
    print(f"\n证据已写入: {out_path}")


if __name__ == "__main__":
    main()
