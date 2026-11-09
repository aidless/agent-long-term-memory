# Failure modes

Two ways this repository has been, or can be, read as stronger than the offline commands. The commands that are allowed to go green are `pytest passed: 112` and `forgetting-js assertions: 103`. Those phrases mean the unit suites passed. They do not mean the failure modes below are closed.

## 1. Retrieval reported as memory (false green)

A green test can mean "a query string overlapped a stored string." That is retrieval. Calling it memory, or calling it support for long-horizon autonomy, is a false green.

In this clone:

- `engineering/memory-system/tests/test_long_horizon.py` `test_cross_step_retrieval_hit_rate` stores ten sentences and searches a query that shares tokens (`field_0`, `field_1`). The assertion is `len(results) > 0` and that some hit contains `field_`. Passing shows the searcher returned a row.
- The same file's `test_long_horizon_memory_benefit` draws independent Bernoulli trials and checks the no-memory rate sits near `0.98 ** 20` (tolerance 0.05). It then stores `state_{step}` strings and asserts `search("关键状态 state_5")` returns something. `memory_rate_estimate` is set to `0.0` and never compared. The test name says "memory benefit"; the assertions do not measure one.
- `research/02-memory-vs-retrieval/experiments/r2_1_retrieval_vs_memory.py` builds the memory arm by adding `association_bonus` (default 0.2) to the best score when `use_memory_system` is true, then applies the same threshold. The arm wins because the script adds a constant. It does not call `MemoryManager`.
- `r2_2_memory_benchmark.py` reports a gap M between those two arms. M=1.000 in the committed JSON is that construction, not a measurement that a system remembered.

`r2_e2e_long_horizon.py` does import `MemoryManager`. The task is still a script: each step needs a `fact_{j}` key, the no-memory arm keeps a window of size C, and a coin flip (`step_success_rate`) fails the step. A higher scripted success rate is not a field result about retrieval versus memory.

How to avoid the false green: cite the assertion or the script branch. Do not translate a hit, or a bonus added before the threshold, into "the judgment is confirmed."

## 2. Synthetic pilot overclaim

A simulator, a power calculation, and a transcribed pilot are three different objects. Reporting any of them as a finished study is the overclaim.

In this clone:

- `research/01-long-horizon-autonomy/experiments/r1_1_reliability_curve.py` states it is a mechanical simulation with no LLM. Independent per-step failures produce completion rate `p^k` by construction. R² near 1 in `evidence/2026-11-01-r1_1-reliability-curve.json` is the generator matching its own formula.
- `refs/2026-11-01-p6-formal-prerequisites.md` records a pilot: N=36, `synthetic=true`, H1 inconclusive (the note's achieved power is 0.617). The same file's N=72 section is an extrapolation from the pilot effect size ("功效推算"). It is not a run. The preregistration is a draft. Raw per-seed files named in that note are not in this clone, so the pilot numbers are not recomputable here.
- `engineering/real-pipeline/real_task_harness.py` would write `synthetic: false` and a note that sounds like a real DAG run, if an external directory is supplied. No such output is in the tree. See the path label in that file: the default directory is outside the clone.
- `docs/2026-11-01-paper-integration.md` is a draft essay that narrates the simulator JSON in the voice of a study ("we conduct", "findings"). It is not a venue paper and not additional evidence. The limitations section inside it already says the simulations are synthetic; the abstract's voice is the overclaim.

How to avoid the overclaim: say "simulator output" or "power calculation" or "transcribed pilot, rows absent." Do not say the three judgments have been experimentally verified. Do not say N=72 was run.

## Related: external corpora cited as if they were here

forgetting-js docs describe a "真实库" (44 active, 19 archived) and plugin files (`patrol.js`, `evolve-memory.js`) that are not in this clone. A reader who treats those paragraphs as a replication of the 103 assertions is mixing a unit test with an absent database. The Node script uses an in-memory mock.

Counts in `forgetting-js/docs/v4` through `v7`, and in `evidence/baseline-memory-system-tests.md`, are point-in-time notes. They are marked `COUNT-HISTORICAL`. The live counts are only the two phrases above.
