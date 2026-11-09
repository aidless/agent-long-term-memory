<!-- COUNT-HISTORICAL: suite counts below are a point-in-time note, not the live count. Live count: evidence/offline-claims.json -->

# v7 增强报告：语义冗余 gating + 层级概率遗忘

> **Version snapshot.** Counts here belong to this version note. Live count: `evidence/offline-claims.json`.

> 日期：2026-11-02
> 版本：1.5.0
> 上游理论：《Strategic Forgetting for Structured Memory》(arXiv:2607.22562)

## 1. 动机

v6 落地了生存势能 Φ(t) 动态后，两个缺口仍然存在：

1. **Ψ_div 从未真正接线**：v6 定义了 `diversityModulation(similarity)` 函数，
   patrol 的势能更新却硬编码 `diversity=1`（中性）——语义冗余维度存在但从未
   被实际计算。这是「定义了但未应用」的结构性缺陷，类似 v3 的
   `REFERENCE_RELEVANCE=0.7` 问题。
2. **层级遗忘是确定性的**：v6 的 `tieredForgetRate` 只用于划分遗忘层级，
   软遗忘候选在单次 patrol 里**全部**被降级——一次扫描就能清空整个
   irrelevant tier，违背「层级非均匀遗忘」的连续性意图。

v7 把这两个缺口补上：Ψ_div 从真实语义相似度计算，软遗忘按 tier 概率准入。

## 2. 方向①：Ψ_div 从真实语义相似度接线

### 2.1 问题

`diversityModulation(similarity)` 在 v6 已定义（tanh gating：

```
Ψ_div = 1 + α·tanh(β·(τ − sim))
```

但 patrol.js 的势能更新循环写死 `diversity=1`。结果：所有记忆的 Ψ_div 恒为 1.0，
语义冗余从不抑制（也不奖励）任何记忆——第 6 维度的语义分量是**装饰**。

### 2.2 实现

- **embedding 侧车**（`embedding.js` + `embed_server.py`）：Node 侧
  `child_process.spawn` 起 Python 子进程跑 `sentence-transformers/all-MiniLM-L6-v2`
  （88M，本地 /tmp/embed-model），stdio JSON-RPC 逐行协议。模型懒加载缓存，
  持久进程（加载 2.1s 一次，服务多次）。
- **语义相似度**：对每个工作区的 active 非 soft-forgotten 记忆，取
  `maxSimilarities(texts)`（每行对其它行的最大余弦相似度）。
- **patrol 接线**：势能更新传 `diversity = diversityModulation(sim, params)`。
  相似记忆（sim→1）Ψ_div < 1 抑制冗余；独立记忆（sim→0）Ψ_div > 1 奖励新颖。

### 2.3 设计约束：runPatrol 是同步函数

调用方 `store.js` 做 `const patrol = store.patrol(); void patrol;`——**不 await**。
因此势能块不能用 `await`。解决方案：

```
runPatrol 同步
  ├─ fire-and-forget 预取：embedding.maxSimilarities(texts).then(set simCache)
  ├─ 本轮用 simCache 旧值（无缓存 → 中性）
  └─ close 挂在 Promise.allSettled(prefetches).then(() => embedding.close())
```

模块级 `simCache` 跨 patrol 轮次共享，预取从第 N 轮喂第 N+1 轮。这与 Φ(t) 的
**状态量演化语义一致**（Φ 本身也是逐轮累积）。

### 2.4 中性定义修正

`diversityModulation` 的「中性」是 sim=τ=0.7 时 Ψ_div=1.0，**不是** sim=1.0。
初版接线误把中性写成 sim=1.0（Ψ_div=0.547，低于中性），修正为
`sim = sims ? sims[i] : DIVERSITY_TAU`。

### 2.5 E2E 收敛验证

3 轮 E2E：R1/R2 中性（预取未完成），R3 收敛到真实值——
相似记忆（m1/m2，sim=0.802）Ψ_div=0.764 抑制，独立记忆（m3，sim=0.133）
Ψ_div=1.497 奖励。`enabled=false` 时降级中性（sim=0.700、Ψ_div=1.000）。

## 3. 方向②：层级概率遗忘

### 3.1 问题

`tieredForgetRate` 已把遗忘率分层（tier2=14.85%、tier3=39.83%、tier4=64.74%），
但 `scanForgetting` 只要候选过线就**全部**放进 softForgetCandidates——单次
patrol 清空整个低分人群，违背连续性。

### 3.2 实现

`FORGETTING_DEFAULTS` 加 `TIER_DRIVES_SOFT_FORGET: false`（默认关，向后兼容）。
开启时：

```
admitted = Math.random() < tieredForgetRate(score).forgetRate
```

候选带 `tier`/`forgetRate` 字段。这样降级率在 score 上连续：score=0.55 → ~40%/pass，
score=0.10 → ~65%/pass，irrelevant tier 不会被单次清空。

### 3.3 概率采样验证

30 条 tier-4 候选 × 60 轮：admitted 64.3%（理论 64.74%）；tier-2（score 0.745）
60 轮仅 0 次准入（理论 14.85%）。默认关闭时 30/30 全准入。

## 4. 测试

V16 新增 4 断言（默认全准入 / 候选带 tier / 概率准入近 tier-4 率 / tier-2 少准入）。
全套 **103 PASS / 0 FAIL**（v6 的 99 + V16 的 4）。

## 5. 插件集成

- `patrol.js`（插件 `dsh-continual-evolve/lib/data/`）：势能块接入
  `embedding.maxSimilarities` + `diversityModulation`，输出
  `potential.applied[].sim/.diversity`。
- `forgetting.js`（插件）：`TIER_DRIVES_SOFT_FORGET` 概率准入。
- `embedding.js` + `embed_server.py`（插件）：语义侧车。
- `migrate.js` + `records.js`（插件）：`potential` 列迁移（默认 0.5）。

## 6. 诚实边界

- **语义相似度只在 embedding 可用时生效**：模型/解释器不可用时降级中性
  （sim=τ、Ψ_div=1.0），patrol 照常完成，不因侧车故障阻塞。
- **收敛需要一轮**：runPatrol 同步导致预取喂下一轮，第一轮永远中性。
  这是设计选择（与 Φ(t) 状态演化一致），不是 bug。
- **侧车进程生命周期**：close 挂在预取 settle 后，避免 kill 与预取竞态。
- **Ψ_div 只影响势能增量，不影响评分**：语义冗余不改变 scoreMemory 的分数，
  只改变 Φ(t) 的累积方向——这是 SF-AMS Eq.3 的语义边界。
