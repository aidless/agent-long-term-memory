# Real-Data Calibration Protocol (P6 C1 closure plan)

> Status: **protocol draft** (not yet executed). Author: local agent, 2026-11-02.
> Purpose: define how to close C1 (real data replacement) for the P6 formal run
> by calibrating the real-pipeline's simulation constants from REAL LLM-agent
> trajectories. This is the plan document; execution requires cloud compute
> and explicit user authorization (see AGENTS.md rule 17).

## 0. Why this protocol exists

The existing `engineering/real-pipeline/` uses hard-coded simulation constants
(`tool_fail_rate=0.05`, `mem_benefit=0.03`, `negotiation_benefit=0.02`,
`base_mem_hit_rate=0.4`) with `rng.random()` to decide tool success. This is
NOT a real agent trajectory — it is a deterministic random simulation on real
DAG task specs. C1 requires REAL agent trajectories to replace these constants.

## 1. Calibration target (what real trajectories must measure)

On the 144 real DAG tasks (`papers/multiagent_scaling/results/dag_specs/`),
run a REAL LLM agent that actually calls tools and records traces. From those
traces, estimate:

| Constant | Current (simulated) | Must be replaced by |
|----------|--------------------|--------------------|
| `tool_fail_rate` | 0.05 | observed tool failure rate from real agent traces |
| `mem_benefit` | 0.03 | observed success-rate gain from memory hit (real agent) |
| `negotiation_benefit` | 0.02 | observed success-rate gain from negotiation (real agent) |
| `base_mem_hit_rate` | 0.4 | observed baseline memory-hit rate without memory system |

## 2. Real agent specification

- **Model**: small instruction-tuned LLM usable on cloud GPU. Candidate:
  `Qwen/Qwen3-1.7B-Instruct` (multiagent_scaling used `qwen3_1p7b` in
  `e2_mini_twolevel_qwen3_1p7b`). Model choice is a calibration parameter, to be
  frozen in the run config before execution.
- **Agent loop**: at each DAG node, the agent is prompted with the current
  task context + available tool, decides to call the tool or stop, and the
  harness executes the real tool (or a deterministic mock for non-filesystem
  tools). The agent's choice is a REAL LLM generation; tool outcome is the
  real result where available.
- **Traces recorded per run**: step index, tool, prompt, chosen action,
  tool success, memory hit, negotiation decision, token cost, final success.

## 3. Calibration procedure (per seed)

For each of `S` seeds (default S=3, matching pilot):
1. Sample `K` of the 144 DAG tasks (default K=24, stratified L-low/L-high).
2. Run the real agent on each sampled task WITHOUT memory system
   (baseline arm) → estimate `tool_fail_rate`, `base_mem_hit_rate`.
3. Run the real agent WITH memory system (Full arm) → estimate `mem_benefit`
   = (success rate with memory) − (success rate without memory), and
   `negotiation_benefit` from the negotiation arm contrast.
4. Aggregate across seeds: report mean ± CI for each constant.

## 4. Statistical analysis (post-calibration)

- **Point estimates**: mean, 95% bootstrap CI for each calibrated constant.
- **Validation gate**: calibrated constants must be consistent with the
  real-agent traces (re-derivable from the saved per-seed JSON). A constant
  that is not re-derivable is a gate failure.
- **RED/GREEN**: the calibration script must include a RED injection test
  (feed a deliberately wrong constant → gate must reject) and a GREEN test
  (feed a valid estimate → gate accepts). Follow AGENTS.md rule 21.

## 5. Cloud compute requirement

- This is a real LLM inference sweep (K tasks × S seeds × arms). Per AGENTS.md
  rule 17, it MUST run on a cloud GPU host, not this workstation.
- Candidate cloud paths: AMD T4 (`36.150.116.206:34677`, ssh), `ecs-hz`/`ecs-us`
  (Aliyun), SeetaCloud GPU, Kaggle GPU, Magpie gateway (`127.0.0.1:3425`).
- **No GPU host is started without explicit user authorization.**

## 6. Preregistration linkage

- This calibration feeds the P6 formal run (see
  `refs/2026-11-01-prereg-link.md` and
  `agi-research-program/prereg/P6-memory.md`).
- P6 formal run stays at N=72 pairs (12 scenarios × 6 seeds) per the
  preregistration; calibration does NOT change the formal design.
- If the formal run remains inconclusive at 72 pairs, report "not observed"
  with achieved power; do not claim "no effect" (P6 stopping rule).

## 7. Evidence & reproducibility

- All calibration results land in `engineering/real-pipeline/evidence/`
  as per-seed JSON with `synthetic=false`, `calibration=true`.
- The run config (model, seeds, K, arms, thresholds) is frozen in a
  `calibration_config.json` committed before the run.
- Claim ledger updated per number; every number must be re-derivable.

## 8. Gate (do not skip)

1. Calibration config frozen + committed.
2. Calibration script passes RED/GREEN self-test.
3. Real agent traces saved as evidence with `synthetic=false`.
4. Calibrated constants re-derived from traces (not hand-typed).
5. P6 C1 marked closed only after steps 1-4 + explicit user confirmation.

## 9. Out of scope (blocked, not silently deferred)

- C2 (N=72) — requires the full 12×6 formal run AFTER C1 closes.
- C3 (H3 formal margin) — must be frozen in P6 preregistration, not in this
  repo.
- C4 (dataset version/split/license operationalization) — requires the DAG
  dataset to be versioned + licensed; a separate work item.
- Any submission while C1-C4 are open — blocked by the P6 preregistration
  and by AGENTS.md research-integrity rules.
