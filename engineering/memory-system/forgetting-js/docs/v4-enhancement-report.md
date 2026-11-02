# v4 增强报告 — 选择性遗忘机制

日期：2026-11-01 · 版本：1.1.0 → 1.2.0（待发布）· 测试：70 PASS / 0 FAIL

## 概述

v4 在 v3（REFERENCE_RELEVANCE 修复 + restore 路径 + scoreBreakdown/scoreBand）基础上，完成五项增强：插件集成、权重经验校准、归档再评估（un-archive）、对抗鲁棒性、npm 发布准备。核心目标：让「选择性遗忘」在真实记忆库上不仅正确（v1-v3），而且**可调、可恢复、可解释、抗病态输入**。

## 1. 插件集成测试（方向1）

**问题**：v3 的 `scanForgetting` 已正确识别 `restoreCandidates`（score 回升的软遗忘记忆），但插件 `patrol.js` 只应用 `softForgetCandidates` + `overflowBackfill`，**从不调用 `restoreSoftForgetRow`**——恢复路径在插件层完全未落地。

**修复**：`patrol.js` 在 workspace 循环中插入 `restoreCandidates` 应用循环（调用 `memories.restoreSoftForgetRow`），输出 `appliedRestore`。端到端验证：`restore-me` 被恢复、`still-old` 不恢复、`appliedRestore=['restore-me']`。

**commit**：3a7bc7c

## 2. 权重经验校准（方向2）

**问题**：v2 的五维权重（W_TIME=0.35/W_USAGE=0.25/W_REDUNDANCY=0.15/W_REUSE=0.15/W_DRIFT=0.10）是手工设定，未用真实数据校准。

**数据**：真实库 44 条 active 中**无 age>30d 且零使用的样本**（v1 已清），archived 19 条多为很新的旧版副本——真实库样本不足以做监督校准，改用**合成数据网格搜索**。

**校准过程**：
- 纯合成最优：W_TIME=0.40/W_USAGE=0.30/W_REDUNDANCY=0.15/W_REUSE=0.05/W_DRIFT=0.10（F1=1.00）
- 噪声注入最优：W_TIME=0.55/W_USAGE=0.25/W_REDUNDANCY=0.05/W_REUSE=0.05/W_DRIFT=0.10（F1=0.93）
- 共同趋势：**W_TIME 应升高、W_REUSE 应降低**
- 约束验证：W_REDUNDANCY=0.20 会破坏 v3 地板修复（6mo 零使用 reference raw=(0.2+0.02)×0.7=0.154>0.15，重新引入 v3 问题）→ 必须回 0.15

**最终校准（和=1）**：W_TIME=0.45 / W_USAGE=0.25 / W_REDUNDANCY=0.15 / W_REUSE=0.05 / W_DRIFT=0.10

**验证**：6mo 零使用 reference score=0.119<0.15 仍可遗忘；24.6d 零使用 reference 0.211>0.15 仍保留。46 PASS。

**commit**：1120806

## 3. 归档再评估路径（方向3）

**问题**：archived 记忆**永不恢复**（`archiveEligible` 单向）。被归档的记忆如果后来重新被检索/使用，或 score 显著回升，应该能回到 active。

**实现**：
- `FORGETTING_DEFAULTS` 加 `UNARCHIVE_SCORE: 0.5`
- `unarchiveEligible(row, usage, nowIso, params)`：archived 且 `useCount>0` → `{eligible:true, reason:'reused-since-archive'}`；score≥UNARCHIVE_SCORE → `{eligible:true, reason:'score-recovered'}`；否则 score-low
- `scanUnarchive(repo, workspaceId, nowIso, params)`：读 `listArchivedRows`（默认 limit=500），逐条评估
- 插件 `repository.js` 加 `unarchiveRow(workspaceId, id, ts)`（status→active，清 archive_reason/merged_into）
- 插件 `patrol.js` 加 unarchive 应用循环，输出 `unarchive.appliedUnarchive`

**关键缺陷修复**：`unarchiveEligible` 最初对 `merged_into` 非空的旧版副本也判应恢复（`type=user` relevance=1.0 + archived 行 updated_at 被归档刷新→score 虚高>0.5），导致真实库 17/19 条应恢复。**修复：merged_into 非空 → {eligible:false, reason:'merged-superseded'}**（被合并替代的副本永不恢复，避免新旧版同时 active 破坏合并语义）。

**真实库验证**：19 条 archived 全部扫描，**0 候选**（全为 merged 副本，永不恢复——正确）。

**commit**：c300c3e（+2bb03d4 limit 修复）

## 4. 对抗鲁棒性测试（方向4）

**问题**：病态输入（NaN/Infinity/负 useCount、极端权重、缺失字段）可能使 score=NaN，导致 `NaN>0.15` 为 false 误判可遗忘。

**修复**：`scoreMemory` 与 `unarchiveEligible` 对非有限 useCount 清理为 0（`Number.isFinite`），负值 clamp 0。

**验证**：9 病态输入 + 3 极端权重 + 3 unarchive 病态全部 PASS（NaN use 现在 score=0.434 不再 NaN）。固化为 V12 测试（14 项）→ 总测试 70 PASS。

**commit**：e5b1918

## 5. npm 发布准备（方向5）

- 包名 `selective-forgetting` 在 npm 未占用（404 = 可用）
- 需用户提供 npm 登录凭据（当前未登录，无 token）——**待凭据后一键发布**
- package.json 已就绪（main/exports/type=module/files/engines>=22）

## 测试与工程质量

- **70 PASS / 0 FAIL**（V1-V12：评分/保护/软遗忘恢复/两段式/传播/溢出/多维上下文/restore/breakdown/sensitivity/unarchive/adversarial）
- CI：`.github/workflows/test.yml`（push/PR 触发，node-version 22）
- 所有变更已 push origin/main（f00e12e..2bb03d4）

## 关键文件

- 开源仓库：`agent-long-term-memory/engineering/memory-system/forgetting-js/`
  - `src/forgetting/forgetting.js`（核心，无外部依赖，纯模块）
  - `test/forgetting.test.mjs`（70 断言）
  - `README.md` / `docs/v4-enhancement-report.md`
- 插件：`dsh-continual-evolve/lib/data/`（patrol.js/forgetting.js/repository.js 已同步）
