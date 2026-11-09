# agent-long-term-memory

[![CI](https://github.com/aidless/agent-long-term-memory/actions/workflows/ci.yml/badge.svg)](https://github.com/aidless/agent-long-term-memory/actions/workflows/ci.yml)

**STATUS: WORK-IN-PROGRESS.** Honesty checklist for the prototype is in place. The three research judgments are not established by this clone, so this is not portfolio grade A. Gaps: [STATUS.md](STATUS.md). Failure modes: [FAILURE_MODES.md](FAILURE_MODES.md).

## Problem

This clone proves, offline, that `engineering/memory-system` installs from its pinned `requirements.txt` and its pytest suite passes (`pytest passed: 112`), and that `engineering/memory-system/forgetting-js` passes its Node assertions (`forgetting-js assertions: 103`).
It does not prove the three judgments — long-horizon failure as an agent result, retrieval ≠ memory, or recursive self-improvement unachieved. Those pages are essays plus synthetic simulators.
The P6 preregistration stays a draft: the transcribed N=36 synthetic pilot is inconclusive and its raw rows are not in this clone, and N=72 is a power calculation, not a run.

离线能证明的只有上述单元测试。三判断的文章与合成模拟、以及仓外的 P6 原文，都不是本克隆里的已完成实证。

## Fresh clone

Observed on CPython 3.12 after a cold `pip install` of the pinned file (seconds to a few minutes, wheel-dependent). The suites themselves finish in seconds. No network is required after the install. Nothing here is published to PyPI or npm (`not published`).

```bash
python3 -m pip install -r engineering/memory-system/requirements.txt
python3 scripts/check_claim_drift.py
```

The drift script re-runs pytest and the Node file and fails if `evidence/offline-claims.json` or the live docs disagree with that output. Equivalent pieces:

```bash
cd engineering/memory-system && python3 -m pytest tests/ -q
cd engineering/memory-system/forgetting-js && node test/forgetting.test.mjs
```

`forgetting-js` has no npm dependencies; `npm install` is optional. CI is only [`.github/workflows/ci.yml`](.github/workflows/ci.yml): pytest on Python 3.10 and 3.12, the Node 22 assertion script, and the drift script. A workflow file nested under `forgetting-js/.github/` would not run on GitHub; that file is not part of this repo.

## What a green suite is

`pytest passed: 112` means the prototype's unit tests passed: typed stores, TF-IDF-style search, conflict helpers, forgetting helpers, API shape. It does not mean an agent completed long-horizon tasks. `forgetting-js assertions: 103` means pure functions passed against a mock repository. See [FAILURE_MODES.md](FAILURE_MODES.md) for the two ways those greens get over-read.

## What is an essay or an external pointer

| Path | What it is here |
|---|---|
| `research/` | Essays and simulator scripts. JSON under `evidence/` is simulator output, not an agent study. |
| `refs/2026-11-01-prereg-link.md` | Pointer. The prereg file `agi-research-program/prereg/P6-memory.md` is **outside this clone**. |
| `refs/2026-11-01-p6-formal-prerequisites.md` | Transcription of a draft gate. N=36 synthetic, inconclusive. N=72 is a power calculation, not a run. Cited raw files are not in this clone. |
| `engineering/real-pipeline/real_task_harness.py` | Code that looks for an **external** DAG directory (the parent of this repo, not the repo). No run is committed. |
| `docs/2026-11-01-paper-integration.md` | Draft essay over the simulators. Not a paper. |
| Sister repos named in `research/*/README.md` | Not vendored. Not checked by cloning this repository. |

## Layout

```
engineering/memory-system/     # runnable prototype (pytest)
engineering/memory-system/forgetting-js/   # runnable Node assertions
research/                      # essays and simulators, not the offline proof
evidence/                      # simulator JSON plus the live count file
refs/                          # external-program notes
scripts/check_claim_drift.py
STATUS.md
FAILURE_MODES.md
```

## License

MIT
