# STATUS: WORK-IN-PROGRESS

Not portfolio grade A. The honesty checklist below is the satellite this clone can support. Closing the research gaps needs new evidence that is not invented here.

## Offline proof (this clone)

Live phrases, checked by `scripts/check_claim_drift.py` against a re-run:

- `pytest passed: 112` — `engineering/memory-system`, `python3 -m pytest tests/ -q`
- `forgetting-js assertions: 103` — `node test/forgetting.test.mjs`, 0 FAIL

Observed while preparing this note, CPython 3.12.3, pytest 7.4.3, Node v22.23.4: pytest `112 passed in 3.74s`; JS `TOTAL: 103 PASS / 0 FAIL`. A later clone should trust the drift script's output, not this sentence, if the two ever diverge — the script fails the build until the integers and the docs move together.

`engineering/memory-system/requirements.txt` installed from PyPI in this environment in about 11 seconds, then the suites ran in seconds. That is the fresh-clone path. It does not download models or call an API.

CI that actually runs is `.github/workflows/ci.yml` (pytest on Python 3.10 and 3.12, the Node 22 job, and the drift script on 3.12). Local verification for the count was Python 3.12.3 only.

This package is not published. `selective-forgetting` is a directory in the tree.

## Honesty checklist

1. README problem statement is three lines: what the clone runs offline, versus essays and the P6 draft.
2. Pytest is runnable from `engineering/memory-system`. CI names that job and the Node job.
3. P6 stays a draft. N=36 synthetic pilot stays inconclusive. N=72 stays a power calculation, not a run. No PyPI/npm release is claimed. Sister-repo names are labeled not-in-clone.
4. `FAILURE_MODES.md` records retrieval-as-memory false greens and synthetic-pilot overclaim.
5. `scripts/check_claim_drift.py` re-runs both suites and scans docs for a different suite count. External paths are labeled in the files that cite them.
6. Fresh clone is pip install plus the drift script. No step needs a long job.

## Gaps (why this is still not A)

1. **The three judgments are not results of this clone.** `research/01-long-horizon-autonomy/experiments/r1_1_reliability_curve.py` is a Bernoulli simulator. An R² near 1 against `p^k` restates the generator. It is not a measured agent reliability curve. `research/02-memory-vs-retrieval/experiments/r2_1_retrieval_vs_memory.py` adds `association_bonus` on the "memory" branch before the hit threshold. `r2_e2e_long_horizon.py` calls `MemoryManager` inside a scripted fact-key task with a scripted step-success coin flip. `research/03-recursive-self-improve/experiments/` does the same kind of scripted comparison. Numbers in `evidence/*.json` are those scripts' outputs.
2. **P6 cannot be recomputed here.** The prereg text is the external path `agi-research-program/prereg/P6-memory.md`. `refs/2026-11-01-p6-formal-prerequisites.md` transcribes an N=36 synthetic pilot (H1 inconclusive, achieved power 0.617 in that note) and a power extrapolation to N=72. The per-seed JSON, `dataset_spec.md`, `analysis_plan.md`, `protocol.md`, and `analysis_p3.py` cited there are not in this clone. C1–C4 are recorded as open. Do not cite N=72 as a run.
3. **Sister repositories are not checkable from this clone.** `agent-loop-safety`, `agent-verifiability`, `memory-architecture-bias` / PAPER5, `evo_agent`, and `agi-research-program` P3/P4/P6 are names in the essays. This change did not open them.
4. **`engineering/real-pipeline/real_task_harness.py` is not a run.** Its default DAG directory is external: `Path(__file__).resolve().parents[3] / "papers/multiagent_scaling/results/dag_specs"`. `parents[3]` is the directory that contains this repository, not the repository root. No output is committed. If the script is pointed at a directory and exits 0, the JSON field `synthetic: false` means the script did not use the P6 synthetic generator. It does not mean a formal study happened.
5. **forgetting-js "真实库" notes are external.** Counts such as 44 active and 19 archived, and files such as `patrol.js` and `evolve-memory.js`, are not in this clone. The offline statement is the 103 mock-repo assertions.
6. **Literature notes are not re-audited as findings.** `refs/2026-11-01-verified-literature.md` is a dated bibliography note. On 2026-11-09 the abs pages for `2603.29231` and `2411.00489` resolved and the titles matched that note. The other four entries were not re-fetched. None of those papers were re-run. Do not treat their metrics as results of this repository.
7. **The JS suite contains a probabilistic band** (tier-4 admission rate between 0.55 and 0.75 over a fixed number of draws). It passed in the run above (observed rate 64.1%). It is a unit check with a wide band, not an estimate to cite.

## What would close the research gaps

A run whose rows, task definitions, and analysis script all live in this clone (or are pinned by a hash the clone checks), with `synthetic` and the sample size written by that script, and with N=72 — if it is ever executed — present as that command's output rather than as a power formula. Until such a run exists, the status line stays **STATUS: WORK-IN-PROGRESS**.
