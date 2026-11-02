# Agent Long-Term Memory: Three Judgments on Autonomy, Retrieval, and Self-Improvement

> **Integration Draft** — consolidates Phase 1 (R1.1-R3.3) and Phase 2 (V2.1-V2.3) experimental findings.
> Status: **draft** (research conclusions verified, not yet submitted to a venue).
> All numbers traceable to evidence files in `evidence/` and `research/*/evidence/`.

## Abstract

Long-term memory is widely assumed to be a key enabler of agent autonomy, yet three judgments remain under-examined: (1) *long-horizon autonomy* — the failure-rate compounding that limits multi-step autonomy; (2) *memory vs. retrieval* — whether memory provides genuine benefits beyond retrieval; (3) *recursive self-improvement* — whether an agent can improve itself in a generalizable way. We conduct a systematic experimental study across these three judgments, with a purpose-built memory system as the engineering substrate. Our findings are: (1) task completion decays as $p^k$ (R²=0.999976), but error compounding makes it *worse* than independent multiplication (k=50 penalty -0.2423, dispersion 9.0 vs. 0.98); memory helps when context is insufficient (+0.375 at k=20) but *hurts* when context is sufficient (-0.625 at C=20). (2) Memory provides genuine, robust benefits over retrieval in fuzzy-query scenarios (M=1.000), and the benefit is entirely robust to noise (all 5 noise levels M=1.000) — but *vanishes* when retrieval quality is high (M=0.000). (3) Recursive self-improvement has not been achieved: evaluator capture is a hard barrier (score +0.345 but held-out +0.01, p=0.918), while outer-loop self-reference via memory does work (+0.237, exceeding external injection +0.144). We contribute a verified memory system (110 tests passing) that implements conflict detection, associative forgetting, and staleness calibration, plus a design-space taxonomy for memory architectures.

## 1. Introduction

Agentic systems increasingly rely on long-term memory to extend autonomy beyond a single context window. Yet three assumptions embedded in this reliance remain largely unexamined:

1. **Long-horizon autonomy** assumes task completion decays gracefully. We show it decays as $p^k$ but error compounding makes it strictly worse.
2. **Memory vs. retrieval** assumes memory provides benefits beyond retrieval-augmented generation. We show memory provides genuine, noise-robust benefits — but only when retrieval quality is insufficient.
3. **Recursive self-improvement** assumes agents can improve themselves. We show outer-loop self-reference via memory works, but evaluator capture makes score-based self-improvement untrustworthy.

These three judgments form the theoretical core of our study. We test them with a purpose-built memory system that implements the full engineering stack: semantic/episodic/procedural storage, conflict detection, associative forgetting, and staleness calibration.

## 2. Related Work

**Long-horizon autonomy.** Beyond pass@1 [1] shows that memory scaffolding *consistently* harms long-horizon performance across 10 models (23,392 tasks) — the first finding our R1.3 replicates in a controlled setting. The Horizon Gap [2] distinguishes long-horizon, long-context, and long-term memory as separate challenges.

**Memory vs. retrieval.** Human-inspired perspectives [3] propose SALM (selective associative memory). MOSAIC [4] achieves 89.35% on LoCoMo with memory consolidation but suffers from silent conflict accumulation — the gap our conflict detector addresses. REALM [5] studies retrieval feedback re-consolidation.

**Recursive self-improvement.** Self-Referential Introspection [6] gives a theoretical threshold for when LLM self-referential reasoning becomes possible. AlphaEvolve-style systems improve *solved problems* in verifiable domains, not the *solver* — a distinction our R3.1 makes explicit.

## 3. Methods

### 3.1 Memory System

Our memory system (`engineering/memory-system/`) implements:

- **Semantic/episodic/procedural** memory layers with typed storage.
- **Conflict detection** (`conflict.py`): detects contradictory memories (same topic + opposite assertion), resolves by keeping higher importance. English + Chinese antonym pairs (60+ pairs), stem matching.
- **Associative forgetting** (`associated_forgetter.py`): cascade forgetting for low-importance, disconnect-retain for high-importance.
- **Staleness calibration** (`calibration.py`): procedural staleness detection + importance calibration.
- **JavaScript implementation** (`forgetting-js/`): v1-v7, tiered forgetting, survival potential, evidence-weighted shrink, tier-driven soft-forget.

### 3.2 Experimental Protocol

All experiments use a deterministic simulation harness with configurable failure rates. Key parameters:

- **Single-step reliability** $p$: probability of a correct step.
- **Horizon** $k$: number of steps in the task.
- **Context window** $C$: number of steps visible in context.
- **Error compounding** $\theta$: 0 = independent, 1 = fully correlated.
- **Contamination** $c$: fraction of noise in queries.

For each setting, we run $N$ trials and record task completion rate. Theoretical prediction: $p^k$ for independent steps.

### 3.3 Verdict Protocol

For memory-vs-retrieval, we define the benchmark criterion:

$$M = P(\text{success} \mid \text{fuzzy query}, \text{memory}) - P(\text{success} \mid \text{fuzzy query}, \text{retrieval only})$$

$M=1.000$ indicates genuine memory; $M \approx 0$ indicates pure retrieval. For self-improvement, we define a capability gate: score gain AND held-out gain (McNemar $p<.05$).

## 4. Results

### 4.1 Long-Horizon Autonomy (Judgment 1)

**R1.1 — Reliability curve.** Task completion follows $p^k$: R²=0.999976 (p=0.98; k=50 measured 0.3653 vs. theory 0.3642, |Δ|=0.0011).

**R1.2 — Error compounding.** With correlated errors ($\theta=1$, contamination=0.05), compounding is *strictly worse* than independent multiplication: k=50 penalty -0.2423 (0.7426 → 0.5003), dispersion 9.00 vs. 0.98. Error correlation makes the failure tail heavier.

**R1.3 — Memory benefit flips with context.** Memory helps when context is insufficient: k=20, C=5 → +0.3750 (0.000 → 0.375). But when context is sufficient (C=20), memory *hurts*: -0.625. This replicates [1]'s finding (5) in a controlled setting.

### 4.2 Memory vs. Retrieval (Judgment 2)

**R2.1 — Retrieval is query-driven; memory is associative.** At fuzzy query f=0.25, pure retrieval succeeds 0.000 while memory succeeds 1.000 (+1.000). Memory works through association rather than exact match.

**R2.2 — Memory benchmark.** M(fuzzy)=1.000 (genuine memory); M(exact)=0.000 (no advantage when query is exact). Verdict: MEMORY_SYSTEM.

**R2-E2E — End-to-end.** With the real MemoryManager: k=20, no-memory 0.000 → with-memory 0.6925 (+0.6925). But when context is sufficient (C=20): -0.0145 (memory no longer helps).

**V2.3 — Retrieval quality.** High-quality retrieval (threshold 0.15): M=0.000 (memory advantage disappears). Medium/low quality: M=1.000. **Memory's advantage is conditional on retrieval insufficiency.**

### 4.3 Recursive Self-Improvement (Judgment 3)

**R3.1 — Boundary classification.** AlphaEvolve-style systems improve *solved problems* in verifiable domains, not the *solver*. Outer-loop self-reference (memory/prompt/tools) is a reachable finite recursion. Weight-level recursion is not implemented.

**R3.2 — Self-reference.** Agent improves itself using its own memory: no-memory 0.025 → self-improve 0.262 (**+0.237**), exceeding external knowledge injection (+0.144). Verdict: SELF_REFERENTIAL.

**R3.3 — Evaluator capture.** Score-based self-improvement is untrustworthy: scenario B score +0.345 (p=8.48e-12) but held-out +0.01 (p=0.918) → **EVALUATOR_CAPTURE**. The capability gate (score AND held-out) correctly discriminates real improvement from overfitting.

### 4.4 Engineering Contributions

- **Conflict detection**: 60+ English/Chinese antonym pairs, stem matching. Verified in multi-conflict (resolved=2), cascade (resolved=2), importance-close (keep 0.51), and no-conflict (0 false positives).
- **Associative forgetting**: cascade forgetting for low-importance, disconnect-retain for high-importance.
- **Staleness calibration**: procedural staleness + importance calibration.
- **Integration**: `add_*` auto-conflict-check, `consolidate_memories` post-consolidation check, `forget` triggers associative forgetting.
- **Tests**: 110 passed (Python) + 103 passed (JS).

## 5. Discussion

### 5.1 Memory helps — but conditionally

Our findings refine the naive "memory helps" narrative. Memory provides genuine, noise-robust benefits when retrieval is insufficient or context is limited. But when retrieval quality is high or context is sufficient, memory provides no advantage — and can even *hurt* (R1.3, -0.625). This is consistent with [1]'s finding (5) that memory scaffolding harms long-horizon performance when the context window is adequate.

### 5.2 Error compounding is the true bottleneck

Long-horizon autonomy fails faster than $p^k$ because errors correlate. The failure mode is not "each step has a failure rate" but "failures cluster." This motivates error-isolation strategies over naive step-count reduction.

### 5.3 Evaluator capture is the self-improvement barrier

Outer-loop self-reference works (+0.237), but score-based self-improvement is untrustworthy. Any self-improvement claim must pass the capability gate: score gain AND held-out gain. Weight-level recursion remains unimplemented.

## 6. Limitations

- All simulation experiments use deterministic synthetic data (synthetic=true); real-data validation is a prerequisite for P6 formal run.
- Memory system tests are unit/integration tests, not end-to-end agent evaluations.
- Retrieval quality threshold (0.15) is a simulation parameter, not measured on real embedding models.

## 7. Reproducibility

All experiments are runnable via `research/*/experiments/*.py`. Evidence files are in `evidence/` and `research/*/evidence/`. See `refs/2026-11-01-verified-literature.md` for literature verification.

## References

[1] Beyond pass@1: Memory Scaffolding for Long-Horizon Agents. arXiv:2603.29231. (10 models, 23,392 tasks)

[2] The Horizon Gap: Distinguishing Long-Horizon, Long-Context, and Long-Term Memory. arXiv:2608.06663. (1,547 papers)

[3] Human-Inspired Perspectives on LLM Memory: SALM. arXiv:2411.00489.

[4] MOSAIC: Memory Consolidation for Multi-Agent Systems. arXiv:2607.16211. (LoCoMo 89.35%)

[5] REALM: Retrieval Feedback Re-Consolidation. arXiv:2609.16053.

[6] Self-Referential Introspection in LLMs. Entropy 2026, doi:10.3390/e28090951.
