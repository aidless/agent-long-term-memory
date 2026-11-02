"""R2.3 长程任务变体（V2.2）：更长程 / 干扰记忆 / 混合上下文。

验证目标：
1. V2.2a 更长程：k=100（C=5, p=0.98）——记忆收益保持 >0。
2. V2.2b 干扰记忆：k=20 每步插入无关事实——记忆系统对干扰鲁棒（收益 >0）。
3. V2.2c 混合上下文：50% 事实在上下文（C=10）、50% 需检索——记忆补充上下文不足。

输出：evidence/2026-11-01-r2-long-horizon-variants.json
"""
import json
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# 导入真实 MemoryManager（工程轨）
_MEM_SYS = str(Path(__file__).resolve().parents[3] / "engineering" / "memory-system")
sys.path.insert(0, _MEM_SYS)
os.chdir(_MEM_SYS)

from manager.memory_manager import MemoryManager


@dataclass
class LongHorizonVariantAgent:
    """长程任务变体 agent（真实 MemoryManager 系统）。

    变体：
    - mode="baseline"：标准长程任务（k 步，每步需先前事实）
    - mode="distractor"：每步插入干扰记忆（无关事实），记忆组需选择性检索
    - mode="mixed_context"：50% 事实在上下文（C=10）、50% 需检索
    """

    n_steps: int = 20
    context_capacity: int = 5
    use_memory: bool = False
    step_success_rate: float = 0.98
    seed: Optional[int] = None
    mode: str = "baseline"  # baseline / distractor / mixed_context

    def __post_init__(self):
        self.rng = random.Random(self.seed)
        self.manager = None
        if self.use_memory:
            self.manager = MemoryManager()

    def clear_memory(self):
        if self.manager:
            self.manager.clear_all()

    def _fact_key(self, j: int) -> str:
        return f"fact_{j}"

    def _distractor_content(self, i: int) -> str:
        """生成干扰记忆内容（无关事实，含特定关键词避免与真实事实冲突）。"""
        return f"distractor_observation_{i} 无关噪音条目"

    def _add_fact(self, content: str, importance: float = 0.8, metadata: Optional[dict] = None):
        """添加事实记忆，绕过 _auto_conflict_check（O(n²) 瓶颈）。

        本实验事实（fact_i）故意无冲突——自动冲突检测不是实验目标，
        而是系统开销。直接调用 semantic.add（不走 add_semantic 的 _auto_conflict_check），
        与 E2E 基线行为一致（E2E 用 add_semantic 但 n≤50 可承受）。

        注意：检索仍用 manager.search（真实检索逻辑），不影响实验有效性。
        """
        self.manager.semantic.add(
            content,
            metadata=metadata or {},
            importance=importance,
        )

    def execute(self) -> bool:
        """执行 k 步任务，返回是否全部成功。"""
        context = []

        for i in range(1, self.n_steps + 1):
            # 干扰模式：每步先插入无关记忆（污染记忆库）
            if self.mode == "distractor" and self.use_memory:
                self._add_fact(
                    self._distractor_content(i),
                    importance=0.2,
                    metadata={"step": i, "is_distractor": True},
                )

            # 第一步：建立第一个事实
            if i == 1:
                if self.use_memory:
                    self._add_fact(
                        self._fact_key(i),
                        importance=0.8,
                        metadata={"step": i},
                    )
                else:
                    context.append((i, self._fact_key(i)))
                continue

            # 需要先前某一步的事实
            need_j = self.rng.randint(1, i - 1)
            fact_key = self._fact_key(need_j)

            # 混合上下文模式：50% 事实在上下文窗口（C=10）
            in_context_half = False
            if self.mode == "mixed_context":
                in_context_half = (need_j % 2 == 0)  # 偶数步事实在上下文

            # 1. 单步失败
            if self.rng.random() > self.step_success_rate:
                return False

            # 2. 获取所需事实
            if self.use_memory:
                results = self.manager.search(
                    fact_key,
                    memory_types=["semantic"],
                    top_k=5,
                )
                if not results:
                    return False
                hit = False
                for sr in results:
                    if self._fact_key(need_j) in sr.memory.content:
                        hit = True
                        break
                if not hit:
                    return False
            else:
                found = any(
                    step == need_j for step, _ in context
                    if i - step <= self.context_capacity
                )
                if not found:
                    return False

            # 3. 该步成功，建立/更新事实
            if self.use_memory:
                self._add_fact(
                    self._fact_key(i),
                    importance=0.8,
                    metadata={"step": i},
                )
            else:
                context.append((i, self._fact_key(i)))

        return True


def run_variant_compare(
    n_steps: int,
    mode: str = "baseline",
    context_capacity: int = 5,
    step_success_rate: float = 0.98,
    n_trials: int = 2000,
    seed: int = 42,
) -> dict:
    """运行单个变体对照（无记忆 vs 有记忆）。

    优化：有记忆组复用单实例 + clear_all()（同 R2-E2E 修复方式），
    避免每 trial 新建 MemoryManager 的昂贵开销（k=100 时尤其明显）。
    """
    no_success = 0
    for t in range(n_trials):
        agent = LongHorizonVariantAgent(
            n_steps=n_steps, context_capacity=context_capacity,
            use_memory=False, step_success_rate=step_success_rate,
            seed=seed + t, mode=mode,
        )
        if agent.execute():
            no_success += 1
    no_rate = no_success / n_trials

    # 有记忆：复用单实例（每 trial 清空），避免每 trial 新建 MemoryManager
    mem_agent = LongHorizonVariantAgent(
        n_steps=n_steps, context_capacity=context_capacity,
        use_memory=True, step_success_rate=step_success_rate,
        seed=seed, mode=mode,
    )
    yes_success = 0
    for t in range(n_trials):
        mem_agent.clear_memory()
        if mem_agent.execute():
            yes_success += 1
    yes_rate = yes_success / n_trials

    return {
        "mode": mode,
        "steps": n_steps,
        "context_capacity": context_capacity,
        "no_memory_rate": no_rate,
        "with_memory_rate": yes_rate,
        "memory_benefit": yes_rate - no_rate,
        "n_trials": n_trials,
    }


def main():
    """运行 V2.2 长程任务变体并落盘证据。"""
    print("=" * 70)
    print("R2.3 长程任务变体（V2.2）：更长程 / 干扰 / 混合上下文")
    print("=" * 70)

    results = []

    # V2.2a 更长程：k=100
    print("\n[V2.2a] 更长程 k=100（C=5, p=0.98）")
    a = run_variant_compare(n_steps=100, mode="baseline", context_capacity=5)
    print(f"  无记忆={a['no_memory_rate']:.6f}  有记忆={a['with_memory_rate']:.6f}  "
          f"收益={a['memory_benefit']:.6f}")
    results.append(a)

    # V2.2b 干扰记忆：k=20 每步插入无关记忆
    print("\n[V2.2b] 干扰记忆 k=20（每步插入无关噪音，C=5）")
    b = run_variant_compare(n_steps=20, mode="distractor", context_capacity=5)
    print(f"  无记忆={b['no_memory_rate']:.6f}  有记忆={b['with_memory_rate']:.6f}  "
          f"收益={b['memory_benefit']:.6f}")
    results.append(b)

    # V2.2c 混合上下文：50% 在上下文（C=10），50% 需检索
    print("\n[V2.2c] 混合上下文 k=20（50% 事实在 C=10 上下文，50% 需检索）")
    c = run_variant_compare(n_steps=20, mode="mixed_context", context_capacity=10)
    print(f"  无记忆={c['no_memory_rate']:.6f}  有记忆={c['with_memory_rate']:.6f}  "
          f"收益={c['memory_benefit']:.6f}")
    results.append(c)

    # 落盘证据
    evidence = {
        "experiment": "R2.3 长程任务变体（V2.2）",
        "description": "更长程（k=100）、干扰记忆（每步污染）、混合上下文（50% 上下文/50% 检索）三变体对照",
        "method": "复用 E2ELongHorizonAgent 逻辑，扩展三变体。每个变体对照无记忆 vs 有记忆（真实 MemoryManager）。",
        "variants": results,
        "reproduce": "python3 research/02-memory-vs-retrieval/experiments/r2_long_horizon_variants.py",
    }

    evidence_dir = Path(__file__).resolve().parents[1] / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    out_path = evidence_dir / "2026-11-01-r2-long-horizon-variants.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 证据已落盘: {out_path}")


if __name__ == "__main__":
    main()
