"""R2.3 冲突场景变体（V2.1）：多对冲突 / 级联冲突 / 重要性接近 / 无冲突多事实。

验证目标：
1. V2.1a 多对冲突：同一实体 3 次结论反转，resolve 后保留最终高重要性者。
2. V2.1b 级联冲突：冲突 A-B 解决后保留者与第三方矛盾，循环处理直到无冲突。
3. V2.1c 重要性接近：0.51 vs 0.49（判据临界），保留 0.51。
4. V2.1d 无冲突多事实：3 条不同实体唯一事实，0 冲突（不误伤）。

输出：evidence/2026-11-01-r2-conflict-variants.json
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


def _count_conflicts(mgr: MemoryManager, memory_type: str = "semantic") -> int:
    """统计当前仍有冲突候选标记的记忆数。"""
    store = mgr._get_memory_store(memory_type)
    return sum(
        1 for mem in store.list_all()
        if mem.metadata.get("conflict_candidate", False)
    )


def _has_conflict_pair(mgr: MemoryManager, memory_type: str = "semantic") -> bool:
    """检查是否仍存在冲突对（用 ConflictDetector 重新检测，不看 metadata 残留标记）。"""
    store = mgr._get_memory_store(memory_type)
    memories = store.list_all()
    # 用冲突检测器重新检测真实冲突（metadata 的 conflict_candidate 是检测时的残留标记，
    # 不会在 resolve 后自动清除——真实判据是 find_conflicts 的结果）
    from manager.conflict import ConflictDetector
    cd = ConflictDetector()
    return len(cd.find_conflicts(memories)) > 0


def run_conflict_variants():
    """运行 4 个冲突场景变体。"""
    results = {}

    # === V2.1a 多对冲突：同一实体 3 次结论反转 ===
    m1 = MemoryManager()
    m1.add_semantic("model_a 性能提升", importance=0.9, metadata={"step": 1})
    m1.add_semantic("model_a 性能下降", importance=0.3, metadata={"step": 2})
    m1.add_semantic("model_a 性能提升显著", importance=0.8, metadata={"step": 3})

    store1 = m1._get_memory_store("semantic")
    mems1 = store1.list_all()
    candidate_count1 = sum(
        1 for mem in mems1 if mem.metadata.get("conflict_candidate", False)
    )
    resolved1 = m1.resolve_conflicts(memory_type="semantic")
    remaining1 = store1.list_all()
    results["V2_1a_multi_conflict"] = {
        "total_stored": len(mems1),
        "conflict_candidates": candidate_count1,
        "resolved_count": len(resolved1),
        "keep_content": resolved1[0]["keep_content"] if resolved1 else None,
        "remaining_count": len(remaining1),
        "remaining_contents": [mem.content for mem in remaining1],
        "no_residual_conflict": not _has_conflict_pair(m1),
    }

    # === V2.1b 级联冲突：A-B 解决后保留者 B 与 C 矛盾 ===
    m2 = MemoryManager()
    m2.add_semantic("model_b 稳定性增强", importance=0.4, metadata={"step": 1})
    m2.add_semantic("model_b 稳定性减弱", importance=0.6, metadata={"step": 2})
    m2.add_semantic("model_b 稳定性显著减弱", importance=0.7, metadata={"step": 3})

    resolved2 = m2.resolve_conflicts(memory_type="semantic")
    # 级联：第一次 resolve 后可能仍有冲突，应循环处理
    # 当前 resolve_conflicts 一次性处理全部冲突对，检查是否残留
    store2 = m2._get_memory_store("semantic")
    remaining2 = store2.list_all()
    results["V2_1b_cascade_conflict"] = {
        "initial_stored": 3,
        "resolved_count": len(resolved2),
        "keep_content": resolved2[0]["keep_content"] if resolved2 else None,
        "remaining_count": len(remaining2),
        "remaining_contents": [mem.content for mem in remaining2],
        "no_residual_conflict": not _has_conflict_pair(m2),
    }

    # === V2.1c 重要性接近：0.51 vs 0.49（判据临界） ===
    m3 = MemoryManager()
    m3.add_semantic("model_c 效率提高", importance=0.51, metadata={"step": 1})
    m3.add_semantic("model_c 效率降低", importance=0.49, metadata={"step": 2})

    resolved3 = m3.resolve_conflicts(memory_type="semantic")
    results["V2_1c_importance_close"] = {
        "resolved_count": len(resolved3),
        "keep_content": resolved3[0]["keep_content"] if resolved3 else None,
        "keep_importance": resolved3[0].get("keep_importance") if resolved3 else None,
        "keep_should_be_051": resolved3[0]["keep_content"] == "model_c 效率提高" if resolved3 else False,
    }

    # === V2.1d 无冲突多事实：3 条不同实体唯一事实 ===
    m4 = MemoryManager()
    m4.add_semantic("entity_d1 status verified ok", importance=0.8, metadata={"step": 1})
    m4.add_semantic("entity_d2 status verified ok", importance=0.8, metadata={"step": 2})
    m4.add_semantic("entity_d3 status verified ok", importance=0.8, metadata={"step": 3})

    resolved4 = m4.resolve_conflicts(memory_type="semantic")
    results["V2_1d_no_conflict_multi"] = {
        "total_stored": 3,
        "resolved_count": len(resolved4),
        "expected_0": len(resolved4) == 0,
    }

    return results


def main():
    results = run_conflict_variants()

    evidence_dir = Path(__file__).resolve().parents[1] / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    out_path = evidence_dir / "2026-11-01-r2-conflict-variants.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("=== 冲突场景变体（V2.1）===")
    print(f"V2.1a 多对冲突: {results['V2_1a_multi_conflict']}")
    print(f"V2.1b 级联冲突: {results['V2_1b_cascade_conflict']}")
    print(f"V2.1c 重要性接近: {results['V2_1c_importance_close']}")
    print(f"V2.1d 无冲突多事实: {results['V2_1d_no_conflict_multi']}")
    print(f"\n证据已写入: {out_path}")


if __name__ == "__main__":
    main()
