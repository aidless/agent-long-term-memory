# Selective Forgetting

A memory system that selectively forgets beats one that only accumulates.

**Selective forgetting** is not information loss — it is **budget reallocation**. A low-score memory is demoted out of the per-session injection list (soft forget) but stays searchable and recoverable; only after it remains unused for a long window does it archive (still recoverable via review). The per-session context budget goes to the memories that matter right now.

## Why

Agent memory stores grow unbounded. Every memory is injected into every session's context, so the context budget is consumed by stale, unrelated, and low-value memories while genuinely important ones get squeezed out. Forgetting is the **deliberate** mechanism that decides what stays in the fast path and what gets demoted.

## How it works

### Two-stage forgetting

1. **Soft forget** — demote a memory out of the injection list. It stays in the DB, searchable, and is automatically restored if later retrieved (`scoreMemory` recovers it via `useCount`).
2. **Archive** — after a long unused window, move it to a deeper tier. Still recoverable via review.

### Multi-dimensional scoring (v2)

```
score = W_TIME·time_factor + W_USAGE·usage_factor
      + W_REDUNDANCY·redundancy_factor + W_REUSE·reuse_factor
      + W_DRIFT·drift_factor
```

| Dimension | Weight | Meaning |
|-----------|--------|---------|
| Temporal decay | 0.35 | Ebbinghaus decay: recently used → high |
| Usage frequency | 0.25 | Saturating: used often → high |
| Content redundancy | 0.15 | Few same-topic siblings → high (unique content is valuable) |
| Cross-project reuse | 0.15 | Referenced elsewhere / global scope → high |
| Topic drift | 0.10 | Matches an active work topic → high (0.2 baseline when drifted) |

### Protection rules (never forgotten)

- `type='user'` (identity / profile / preference)
- `type='feedback'` (correction history)
- `probation_until` non-null (trial memory)
- Referenced by another memory's `corrects`
- Matches an active topic (context-dependent importance)
- Active count at `MIN_ACTIVE` floor

### Forgetting criteria (all optional, pluggable)

1. **Unused-time decay** — score falls below `SOFT_FORGET_SCORE` after `SOFT_FORGET_DAYS`
2. **Low usage frequency** — score falls below threshold with zero use
3. **Superseded by a new version** — auto-archived via merge (`landMerge`)
4. **Injection budget overflow** — `overflowBackfill` demotes lowest-score rows when projected cost exceeds budget by `OVERFLOW_EVICTION_FRACTION`

## API

```js
import {
  scoreMemory,        // multi-dimensional score
  softForgetEligible, // should this row be soft-forgotten?
  archiveEligible,    // should a soft-forgotten row be archived?
  isProtected,        // hard-coded protection rules
  scanForgetting,     // find candidates (uses a repo)
  overflowBackfill,   // budget-pressure escape hatch
  propagationRisk,    // is this row load-bearing?
  FORGETTING_DEFAULTS // tunable parameters
} from 'selective-forgetting';
```

### Minimal repo interface

`scanForgetting` and `overflowBackfill` need a small repository object:

```js
const repo = {
  listRows: () => rows,                    // active rows for the workspace
  listInjectedRows: () => rows,            // rows currently in the injection list
  getUsage: (ws, ids) => [{ use_count, last_used_at }],
  listWorkspaces: () => [{ workspace_id, updated_at }],
};
```

### Parameters

| Name | Default | Description |
|------|---------|-------------|
| `SOFT_FORGET_DAYS` | 45 | Days without use before a memory is a soft-forget candidate |
| `SOFT_FORGET_SCORE` | 0.15 | Score below which a memory is forgettable |
| `ARCHIVE_DAYS` | 90 | Days soft-forgotten before archive eligibility |
| `MIN_ACTIVE` | 12 | Never forget below this many active memories |
| `DECAY_RATE` | 0.05 | Ebbinghaus decay rate (half-life ≈ 14 days) |
| `USAGE_SATURATION` | 3 | Use count at which usage factor saturates |
| `REDUNDANCY_SATURATION` | 3 | Same-topic siblings at which redundancy saturates |
| `REUSE_BOOST` | 1.0 | Cross-workspace reference count at which reuse saturates |
| `TOPIC_MATCH_BONUS` | 1.0 | Drift factor when a memory matches an active topic |
| `OVERFLOW_EVICTION_FRACTION` | 1.15 | Budget pressure threshold for overflow eviction |
| `W_TIME` | 0.35 | Weight: temporal decay |
| `W_USAGE` | 0.25 | Weight: usage frequency |
| `W_REDUNDANCY` | 0.15 | Weight: content redundancy |
| `W_REUSE` | 0.15 | Weight: cross-project reuse |
| `W_DRIFT` | 0.10 | Weight: topic drift |

## Install & test

```bash
npm install
npm test   # 25 assertions, pure-function + minimal-repo-mock
```

## License

MIT. See [LICENSE](./LICENSE).
