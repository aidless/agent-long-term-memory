# agent-long-term-memory

[![CI](https://github.com/aidless/agent-long-term-memory/actions/workflows/ci.yml/badge.svg)](https://github.com/aidless/agent-long-term-memory/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

🌐 简体中文版：[README.zh-CN.md](README.zh-CN.md)（完整中文内容）

**A research-plus-engineering repository on agent long-term memory.** It starts from three
load-bearing judgments about where agent systems actually break, runs falsifiable experiments
for each, and builds the engineering system those experiments point at. Every research claim
must be re-derivable from the archived artifacts in `evidence/`.

## The three judgments

### Judgment ① — Long-horizon autonomy fails by multiplicative decay
Multi-step tool calls, day-spanning autonomy, error compounding: every step carries a failure
rate and the rates multiply. With a 0.98 single-step success rate, only ≈0.67 remains after 20
steps and ≈0.36 after 50. Research direction: reliability modeling for long-horizon tasks,
error-recovery strategies, and how memory supports autonomy.

### Judgment ② — Retrieval is not memory
The model itself has no persistent memory in the training sense; external stores (RAG/vector
DBs) provide *retrieval*, which fails exactly when lookup fails. Research direction: memory
architectures (hierarchical / episodic / semantic / procedural), forgetting and consolidation,
memory benchmarks.

### Judgment ③ — General recursive self-improvement remains unachieved
AlphaEvolve-style systems are self-improvement inside verifiable domains — not general
recursive self-improvement. Research direction: feasibility boundaries, evaluator capture,
verifiability.

## Research roadmap

```
Phase 1 (current): research framework + evidence pool
  ├── research/01-long-horizon-autonomy/    # judgment ①
  ├── research/02-memory-vs-retrieval/      # judgment ②
  └── research/03-recursive-self-improve/   # judgment ③
Phase 2: per-direction experiment design + preregistration (in progress)
Phase 3: engineering system (long-term memory supporting long-horizon tasks)
```

## Prior-work assets referenced by this repo

| Asset | What it is | Where |
|---|---|---|
| P6-long-horizon-memory | memory/forgetting project: **draft preregistration** + N=36 synthetic pilot (**inconclusive**); **N=72 is a power extrapolation, not a run experiment** | `refs/2026-11-01-prereg-link.md`, `refs/2026-11-01-p6-formal-prerequisites.md` (prereg text lives outside this repo in `agi-research-program/prereg/P6-memory.md`) |
| 18-agent-long-term-memory | runnable FastAPI memory-system prototype (4 memory types + hybrid retrieval + forgetting) | `engineering/memory-system/` (moved in) |
| PAPER5 (memory-architecture-bias) | memory-architecture contamination study + preregistration chain | **separate repository; not verifiable from here** (its script details are not in this repo, so they are not restated) |
| agent-verifiability / agent-loop-safety | agent reliability / auditability / loop safety | separate repositories, referenced |

> **Real status of P6** (fully registered under `refs/`): the preregistration is still a
> **draft** (to be frozen before any formal N=72 run); what has actually run is an
> **N=36, synthetic=true pilot** with an **inconclusive** outcome (H1 missed the McNemar
> N=60 requirement, achieved power=0.617); the N=72 figure is a power extrapolation from the
> pilot effect size. Formal-run preconditions C1–C4 (real-data substitution, sample size,
> H3 threshold preset, TODO-D1 closure) are not yet closed. See
> `refs/2026-11-01-p6-formal-prerequisites.md` and `refs/2026-11-01-prereg-link.md`.

## Results (research track, phase 1 completed 2026-11-01)

All numbers below are backed by the named JSON artifacts under `evidence/` and are re-derivable.

### Judgment ① — long-horizon autonomy (`research/01-long-horizon-autonomy/`)

| Experiment | Result | Evidence |
|---|---|---|
| R1.1 reliability curve | p^k exponential decay verified, R²=0.999976 (0.98 per step, 0.365 after 50 steps) | `evidence/2026-11-01-r1_1-reliability-curve.json` |
| R1.2 error compounding | compounding is worse than p^k: penalty −0.2423 at k=50; error spread 9.0 vs 0.98 | `evidence/2026-11-01-r1_2-error-compound.json` |
| R1.3 memory support | memory helps when context is insufficient (+0.375) but can hurt when context is sufficient (−0.625) | `evidence/2026-11-01-r1_3-memory-benefit.json` |
| Engineering hardening | conflict detection + associated forgetting added (112 tests passing) | `engineering/memory-system/manager/conflict.py`, `engineering/memory-system/manager/associated_forgetter.py` |

### Judgment ② — memory vs retrieval (`research/02-memory-vs-retrieval/`)

| Experiment | Result | Evidence |
|---|---|---|
| R2.1 retrieval vs memory | fuzzy queries: pure retrieval 0.000 / memory 1.000 (+1.000); memory robust to noise | `evidence/2026-11-01-r2_1-retrieval-vs-memory.json` |
| R2.2 memory benchmark | criterion M=P(success\|fuzzy,memory)−P(success\|fuzzy,retrieval): M=1.000 (true memory) | `evidence/2026-11-01-r2_2-memory-benchmark.json` |
| R2.3 architecture taxonomy | hierarchical × forgetting × consolidation design space; gap = conflict detection / associated forgetting | `research/02-memory-vs-retrieval/design-space.md` |
| R2-E2E long horizon | real MemoryManager supporting long horizons: k=20 without memory 0.000 / with memory 0.6925 (+0.6925); with sufficient context (C=20) memory no longer helps (−0.0145) | `evidence/2026-11-01-r2_e2e-long-horizon.json` |
| R2-INTEGRATION | hardening does not damage conflict-free scenarios: k=10/20/50 base vs hardened differences all 0 (0.8505/0.6925/0.3925) | `evidence/2026-11-01-r2-integration-check.json` |
| R2-CONFLICT | real contradictory memories end-to-end: detect→mark→resolve→keep-higher-importance; 0 collateral damage in conflict-free scenarios | `research/02-memory-vs-retrieval/evidence/2026-11-01-r2-conflict-integration.json` |

### Judgment ③ — recursive self-improvement (`research/03-recursive-self-improve/`)

| Experiment | Result | Evidence |
|---|---|---|
| R3.1 boundary taxonomy | AlphaEvolve ≠ general recursion; outer loop = bounded recursion; weight-level not achieved | `research/03-recursive-self-improve/boundary-classification.md` |
| R3.2 self-reference | agent improving via its own memory: +0.237 (above external injection +0.144) | `evidence/2026-11-01-r3_2-self-reference.json` |
| R3.3 capability/score separation | evaluator-capture gate: score +0.345 but held-out +0.01 (p=0.918) → fake improvement | `evidence/2026-11-01-r3_3-capability-score.json` |

## Quickstart (engineering baseline — verified 2026-11-10)

```bash
# Python memory system (FastAPI prototype, 4 memory types + hybrid retrieval + forgetting)
cd engineering/memory-system
pip install -r requirements.txt
python3 -m pytest tests/ -q        # re-run locally on 2026-11-10: 112 passed, 1 warning in 5.89s

# JavaScript selective-forgetting module (separate npm module, different runtime stack)
cd engineering/memory-system/forgetting-js
npm install
npm test                           # re-run locally on 2026-11-10: TOTAL: 103 PASS / 0 FAIL
```

The two forgetting implementations (`manager/forgetter.py` in Python and
`engineering/memory-system/forgetting-js` in JS) are deliberately parallel: they cover
different runtime stacks.

## Engineering hardening (closing the R2.3 gaps)

- **Conflict detection** (`engineering/memory-system/manager/conflict.py`): detects contradictory
  memories (same topic + antonym phrasing), resolves by keeping the higher-importance one.
  Responds to the MOSAIC limitation — silent contradiction accumulation.
- **Associated forgetting** (`engineering/memory-system/manager/associated_forgetter.py`):
  forgetting triggers associated handling (low importance cascades; high importance is
  unlinked but kept).
- **Conflict-scenario validation** (`research/02-memory-vs-retrieval/experiments/r2_conflict_integration.py`):
  real contradictory memories (Chinese/English antonym pairs) validated end-to-end through
  detect → mark → resolve → keep-higher-importance, with 0 collateral damage when there are
  no conflicts. Tests: 112 passed.
- **Calibration** (`engineering/memory-system/manager/calibration.py`): staleness detection +
  calibration; `add_*` auto-runs conflict checks, `consolidate_memories` re-checks after
  consolidation, `forget` triggers associated forgetting.

## Phase-2 experiment variants (designed and implemented, falsifiable)

| Variant | Outcome | Key finding |
|---|---|---|
| V2.1 conflict scenarios | multiple conflict pairs resolved_count=2; cascade resolved_count=2; near-equal importance keeps 0.51; 0 collateral when conflict-free | residual judgment must use `find_conflicts` (real criterion), not metadata flags |
| V2.2 long-horizon tasks | k=100 gain +0.146 (diminishing); interference +0.693 (robust); mixed context +0.677 | long-horizon gains diminish (echoes R1.1 p^k); memory robust to interference |
| V2.3 retrieval vs memory | English benchmark M=1.000; all noise levels M=1.000; high-quality retrieval M=0.000 | memory advantage disappears when retrieval is high-quality (echoes the R1.3 flip) |

Design doc: `docs/design/2026-11-01-phase2-design.md`. Preregistration chain: P6 (still
**draft**, see `refs/2026-11-01-prereg-link.md`) + PAPER5 evidence-chain reuse.

## Repository layout

```
agent-long-term-memory/
├── README.md                # this file (English, primary)
├── README.zh-CN.md          # full Chinese version
├── research/                # research track: the three judgments
│   ├── 01-long-horizon-autonomy/
│   ├── 02-memory-vs-retrieval/
│   └── 03-recursive-self-improve/
├── engineering/             # engineering track
│   ├── memory-system/       # FastAPI prototype (18-agent baseline upgraded)
│   │   ├── manager/         # Python memory management (forgetter.py, conflict.py, calibration.py …)
│   │   └── forgetting-js/   # selective forgetting, JS (independent npm module, 103 assertions)
│   └── real-pipeline/
├── evidence/                # archived, re-derivable evidence (JSON/MD)
├── docs/design/             # design documents
└── refs/                    # references + P6 preregistration registrations
```

## Limits

- The P6 preregistration is a **draft**; the only P6 experiment that has run is an
  inconclusive N=36 synthetic pilot. Nothing in this repo should be quoted as a confirmed
  P6 result.
- R1–R3 results are synthetic-harness measurements of the prototype, not production-agent
  measurements; they characterize mechanisms, not deployed systems.
- PAPER5 details live in a separate repository and are intentionally not restated here.
- The `real-pipeline/` engineering track is exploratory; the verified baseline is
  `engineering/memory-system/`.

## Reproduction & verification

Every research conclusion in this repository must be re-derivable from the archived evidence
under `evidence/`. Design documents: `docs/design/2026-11-01-design.md` and
`docs/design/2026-11-01-phase2-design.md`. Engineering verification is the two Quickstart
commands above (pytest + npm test), both re-run clean on 2026-11-10.

## License

MIT — Liu Zewen, 2026
