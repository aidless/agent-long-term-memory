<!-- COUNT-HISTORICAL: suite counts below are a point-in-time note, not the live count. Live count: evidence/offline-claims.json -->

# v6 增强报告：生存势能动态 + 层级非均匀遗忘

> **Version snapshot.** "99 PASS" in this file is this version's note. Live count: `evidence/offline-claims.json`. The "真实库" section describes a database that is not in this clone.

> 日期：2026-11-01
> 版本：1.4.0
> 上游理论：《Strategic Forgetting for Structured Memory》(arXiv:2607.22562)

## 1. 动机

v5 落地了「证据量」维度后，评分器仍是**静态重算**——每次调用根据当前状态
重新打分，不携带历史累积信息。SF-AMS 的两个洞见指明进化方向：

1. **生存势能动态**：记忆价值应该是一个**状态量** Φ(t)，随使用累积、随时间衰减，
   而不是每次从零重算。这样「反复有用」的记忆会积累势能，长期被检索的记忆
   即使单次价值不高也能被保护。
2. **层级非均匀遗忘**：不同价值的记忆遗忘速率不同（核心记忆几乎不遗忘、
   无关记忆快速遗忘），而不是单一阈值二值化。

## 2. 生存势能动态（第 6 维度）

### 2.1 公式（SF-AMS Eq.3）

```
Φ(t+1) = max(0, Φ(t) + I·Γ_usage·Ψ_div − λ)
```

| 符号 | 含义 | 本实现 |
|------|------|--------|
| Φ(t) | 生存势能 | `ctx.potential`（DB 列，默认 0.5） |
| I | 记忆重要性 | scoreMemory 的 score（0-1） |
| Γ_usage | 使用信号 | used=1 / unused=0 |
| Ψ_div | 多样性调制 | `diversityModulation(sim)` |
| λ | 衰减率 | `POTENTIAL_DECAY=0.02` |
| 下限 | — | `POTENTIAL_FLOOR=0` |

### 2.2 多样性调制

```
Ψ_div = 1 + α·tanh(β·(τ − Sim))
```

- `sim=τ` 时 Ψ_div=1（中性）；
- 新颖记忆（sim<τ）Ψ_div>1（增强）；
- 冗余记忆（sim>τ）Ψ_div<1（抑制）。

本实现因 dsh 无 embedding，`sim` 退化为同主题计数（`listMemoryTopics`），
默认传入 1（中性）。

### 2.3 语义

- **被使用**（Γ=1）且重要性高（I 大）→ 势能上升，记忆被强化；
- **长期未被使用** → 势能按 λ 衰减，即使历史上有价值也会逐渐失去保护；
- **势能**作为评分第 6 维 `W_POTENTIAL=0.10`，把「历史累积价值」并入单次评分。

## 3. 层级非均匀遗忘（SF-AMS Table 4）

```
tieredForgetRate(score) → {tier(1-4), label, forgetRate}
```

| tier | label | score 范围 | forgetRate | 语义 |
|------|-------|-----------|------------|------|
| 1 | core | ≥ 0.80 | 0 | 核心记忆，永不遗忘 |
| 2 | important | [0.60, 0.80) | 0.1485 | 重要，慢遗忘 |
| 3 | secondary | [0.15, 0.60) | 0.3983 | 次要，中遗忘 |
| 4 | irrelevant | < 0.15 | 0.6474 | 无关，快遗忘 |

遗忘率单调递增（0 → 0.1485 → 0.3983 → 0.6474），符合「越无价值越快遗忘」。

## 4. 权重重平衡

引入第 6 维后重新平衡（和=1）：

| 维度 | v5 | v6 |
|------|----|----|
| W_TIME | 0.45 | 0.40 |
| W_USAGE | 0.25 | 0.23 |
| W_REDUNDANCY | 0.15 | 0.14 |
| W_REUSE | 0.05 | 0.05 |
| W_DRIFT | 0.10 | 0.08 |
| W_POTENTIAL | — | 0.10 |

W_POTENTIAL=0.10 保持第 6 维对总分有实质影响，同时不喧宾夺主
（W_TIME 仍最大，符合「时间是最强遗忘信号」的认知科学结论）。

## 5. 插件集成

- `migrate.js`：`ensureMemoriesPotentialColumn` 加 `potential REAL NOT NULL DEFAULT 0.5`；
- `records.js`：MEMORIES_COLUMNS + DDL + rowToRecord 映射；
- `repository.js`：`updatePotential` 方法 + `updatePotentialStmt`；
- `resource-kinds.js`：`updatePotentialSql`；
- `patrol.js`：workspace 循环加势能更新块（used=useCount>0，importance=score，
  tier=tieredForgetRate，nextPhi=updatePotential，差值>1e-12 时更新）。

## 6. 测试

- V14（生存势能 10 断言）：衰减/累积/下限/多样性/NaN 鲁棒/单调/有界；
- V15（层级遗忘 8 断言）：四层边界/遗忘率/单调/NaN 安全/势能维度影响；
- 全套 **99 PASS / 0 FAIL**（V1-V15）。

## 7. 真实库验证

- `migrateDatabase` 在真实库副本：potential 列存在，默认 0.5，44 active + 19 archived 不变；
- runPatrol 端到端（完整 mock）：used+high-score 记忆势能上升（0.5→1.08）、
  unused 记忆衰减（0.5→0.48）、soft-forgotten 跳过；restore 路径正常（score-recovered）。

## 8. 可行性边界（诚实声明）

- **多样性调制退化**：dsh 无 embedding，`sim` 退化为同主题计数。当未来接入
  embedding 后，Ψ_div 才能发挥语义冗余 gating 的完整作用。
- **势能字段新增**：`potential` 是新 DB 列，旧库迁移时默认 0.5（中性），
  不会因迁移误杀或误保任何记忆。
- **层级遗忘率不直接驱动 soft-forget**：`tieredForgetRate` 当前是**分析/诊断**工具
  （patrol 输出 tier），soft-forget 决策仍由 `softForgetEligible` 的阈值判定。
  若未来想让 tier 直接驱动遗忘概率，需要显式配置。

## 9. 文件变更

| 文件 | 变更 |
|------|------|
| `src/forgetting/forgetting.js` | +`updatePotential`/`diversityModulation`/`tieredForgetRate`；权重 6 维；scoreMemory 第 6 维 |
| `test/forgetting.test.mjs` | +V14/V15；旧断言 5→6 维 |
| `README.md` | +v6 说明 |
| `package.json` | 1.3.0 → 1.4.0 |
