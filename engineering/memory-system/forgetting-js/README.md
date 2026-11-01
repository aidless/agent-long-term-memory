# Selective Forgetting

A memory system that selectively forgets beats one that only accumulates.

**Selective forgetting** is not information loss — it is **budget reallocation**. A low-score memory is demoted out of the per-session injection list (soft forget) but stays searchable and recoverable; only after it remains unused for a long window does it archive (still recoverable via review). The per-session context budget goes to the memories that matter right now.

## 设计哲学：为什么主动遗忘优于被动记忆

### 概念区分

不是"记忆 vs 遗忘"的对立，而是**两种策略**：

| 策略 | 核心机制 | 代表系统 |
|------|---------|---------|
| **被动记忆**（accumulate-only） | 只写入不删除；靠**检索**决定什么被想起 | 纯 RAG、向量库 append-only |
| **主动遗忘**（selective forgetting） | 有写入也有淘汰；靠**评分**决定什么留在快路径 | 本模块 |

### 主动遗忘更优的四个论证

**1. 上下文预算是硬约束，不遗忘就必然挤占**
被动记忆的问题不是"记不住"，而是全部都要挤进上下文。每个记忆默认注入每个会话，注入预算有限。被动策略下无关记忆占预算 → 真正重要的被挤出。遗忘是**预算再分配**，不是信息损失。

**2. 检索 ≠ 记忆**
被动记忆的软肋：检索不到 = 记忆失效。向量检索有召回上限，语义漂移时旧记忆可能永远检索不到。主动遗忘至少保留了**降级但可恢复**的路径：软遗忘仍可检索（被检索时自动恢复），归档仍可 review 恢复。所以主动遗忘**不是丢弃，是分层**。

**3. 遗忘是适应性功能，不是缺陷**
认知科学（Bjork 的 desirable difficulties、Anderson 的 adaptive forgetting）指出：主动遗忘提升提取——让"记得"的东西更少而更准，降低干扰（proactive interference）；遗忘是元认知功能，系统判断"什么值得记"本身让记忆更可用。

**4. 保护规则 = 价值分层**
被动记忆做不到这一点。本模块有硬保护：user/feedback 永不遗忘、被 corrects 引用的承重记忆永不遗忘、匹配活跃主题的记忆受保护。系统不是一刀切淘汰，而是区分"必须保留的"与"可以降级的"。

### 主动遗忘的代价（诚实评估）

| 代价 | 说明 |
|------|------|
| 评分错误的代价 | 评分判错会把重要记忆降级，信息"沉没"——虽可恢复但可能检索不到 |
| 调参负担 | 阈值、权重、半衰期要调；被动记忆零配置 |
| 冷启动问题 | 新记忆还没积累使用数据，评分可能低估；probation 机制在缓解 |

### 结论

**主动遗忘更好，前提是"选择性"**——不是盲目淘汰。本模块抓住三点：①分层而非丢弃（软遗忘→归档→可恢复）；②价值分层（保护规则）；③预算感知（溢出兜底）。认知科学的"遗忘是适应性的"在此落地为工程机制。

> 一句话：不是"记忆 vs 遗忘"，而是"**无差别积累 vs 有差别的价值分层**"——后者赢得预算约束下的信息密度。

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
