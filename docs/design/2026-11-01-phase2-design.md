# 阶段二实验设计细化 — 冲突场景 / 长程任务 / 检索 vs 记忆

> **STATUS: WORK-IN-PROGRESS.** The "阶段一已确认的结论" list is simulator output, not a confirmed finding. See `/STATUS.md` and `/FAILURE_MODES.md`.

> **目标**：在阶段一的模拟脚本和工程原型之上，细化三类实验设计，为仍是 draft 的 P6 预注册做准备。不把模拟输出当成已确认结论。
>
> **阶段一已确认的结论**（本设计的输入）：
> - R1.2：错误复合比简单连乘更坏（k=50 惩罚 -0.2423，复合分散 9.0 vs 0.98）——错误传播使计数过度分散。
> - R1.3/R2-E2E：记忆在上下文不足时帮助（+0.375 / +0.6925）但上下文足够时损害（-0.625 / -0.0145）。
> - R2.2：M=P(模糊,记忆)-P(模糊,纯检索)，M=1.000 真记忆（中文），M≈0 纯检索。
> - R2-INTEGRATION：强化路径不损害无冲突场景（差异全 0）。
> - R2-CONFLICT：冲突检测/解决在真实矛盾记忆上工作正常（4 场景）。
> - R3.3：evaluator capture 门禁（分数+0.345 但 held-out+0.01，p=0.918）——过拟合不可信。

## 1. 冲突场景变体（V2.1）

### 1.1 动机
阶段一 R2-CONFLICT 验证了**单个冲突对**（2 条记忆）。真实长程任务中，矛盾记忆可能：
- **多对冲突**（同一实体多次结论反转）；
- **级联冲突**（冲突解决触发新的冲突——丢弃一条后，保留者与第三方矛盾）；
- **重要性接近**（0.5 vs 0.5，判据临界）。

### 1.2 设计（可证伪）

| 变体 | 构造 | 预期（强化路径） | 判据 |
|------|------|-----------------|------|
| V2.1a 多对冲突 | 同一实体 3 次结论反转（提升→下降→提升） | 检测 ≥2 对，resolve 后保留最终高重要性者 | resolved_count ≥ 2 且 remaining 无冲突对 |
| V2.1b 级联冲突 | 冲突 A-B 解决后，保留者 B 与 C 矛盾 | resolve_conflicts 循环处理直到无冲突 | 最终无 conflict_candidate 残留 |
| V2.1c 重要性接近 | 0.51 vs 0.49（判据临界） | 保留 0.51（>0.49），确定性 | keep_importance == 0.51 |
| V2.1d 无冲突多事实 | 3 条不同实体唯一事实 | 0 冲突（不误伤） | resolved_count == 0 |

### 1.3 实现
- 扩展 `r2_conflict_integration.py`（新增 V2.1a-d 场景）或新建 `r2_conflict_variants.py`。
- 复用 `ConflictDetector` + `resolve_conflicts`（不修改生产代码，只加测试场景）。

## 2. 长程任务变体（V2.2）

### 2.1 动机
阶段一 R2-E2E 验证 k=10/20/50（C=5，无干扰）。真实长程任务有：
- **更长程**（k=100）；
- **干扰记忆**（无关记忆污染检索——记忆系统需选择性检索）；
- **混合上下文**（部分事实在上下文内、部分需检索）。

### 2.2 设计（可证伪）

| 变体 | 构造 | 预期 | 判据 |
|------|------|------|------|
| V2.2a 更长程 | k=100（C=5, p=0.98, 2000 trials） | 记忆收益保持 >0（有记忆 > 无记忆） | with_memory_rate > no_memory_rate |
| V2.2b 干扰记忆 | k=20，每步插入干扰记忆（无关事实），记忆组需选择性检索 | 记忆系统对干扰鲁棒（收益仍 >0） | 收益>0 且不显著低于无干扰 |
| V2.2c 混合上下文 | k=20，50% 事实在上下文（C=10），50% 需检索 | 记忆补充上下文不足部分 | 收益>0 |

### 2.3 实现
- 扩展 `r2_e2e_long_horizon.py` 或新建 `r2_long_horizon_variants.py`。
- 关键：干扰记忆通过 `add_semantic` 注入（不改变检索逻辑），验证真实系统选择性。

## 3. 检索 vs 记忆对照（V2.3）

### 3.1 动机
阶段一 R2.2 验证中文 M=1.000。需扩展：
- **英文**（improved/degraded 等英文反义——R2-CONFLICT 已修英文，但 R2.2 基准仍是中文）；
- **噪音水平**（不同 noise_ratio——记忆对噪音鲁棒是否一致）；
- **检索质量 vs 记忆**（不同 similarity_threshold——高检索质量是否降低记忆增益）。

### 3.2 设计（可证伪）

| 变体 | 构造 | 预期 | 判据 |
|------|------|------|------|
| V2.3a 英文基准 | 英文内容（improved/degraded） | M > 0.05（真记忆） | verdict == MEMORY_SYSTEM |
| V2.3b 噪音敏感性 | noise_ratio = [0.3, 0.5, 0.7] | M 保持 >0（记忆对噪音鲁棒） | 全档 M > 0.05 |
| V2.3c 检索质量 | similarity_threshold = [0.2, 0.3, 0.5] | 高阈值（检索质量高）时 M 仍 >0 | 全档 M > 0.05 |

### 3.3 实现
- 扩展 `r2_2_memory_benchmark.py`（加英文内容 + 噪音/阈值敏感性）。

## 4. 预注册链（P6 复用）

- P6 prereg text is the external path `agi-research-program/prereg/P6-memory.md` (not in this clone). The planned grid is 12 scenarios × 6 seeds = 72 pairs. N=60 power 0.70 and N=72 power ≈0.80 are power calculations, not a run.
- **本仓登记**：`refs/` 或 `docs/` 下登记 P6 引用（不重复启动——P6 是独立日程）。
- 阶段二实验（V2.1-V2.3）为**预实验（pilot）**：为 P6 正式实验提供参数估计（效应量、方差）。

## 5. 与 P6 的衔接

| 本阶段实验 | P6 假设 | 提供参数 |
|-----------|---------|---------|
| V2.1 冲突变体 | H6.2 memory hit（记忆命中率） | 冲突场景下的记忆命中/解决率 |
| V2.2 长程变体 | H6.1 primary（Full vs baselines 精确 McNemar） | 效应量估计（长程收益） |
| V2.3 检索 vs 记忆 | H6.3 cost+safety 非劣效 | 记忆系统 vs 检索的收益差 |

## 6. 复现

```bash
# V2.1 冲突变体
python3 research/02-memory-vs-retrieval/experiments/r2_conflict_variants.py
# V2.2 长程变体
python3 research/02-memory-vs-retrieval/experiments/r2_long_horizon_variants.py
# V2.3 检索 vs 记忆对照
python3 research/02-memory-vs-retrieval/experiments/r2_retrieval_memory_control.py
```

> 本文件是阶段二实验设计（预实验设计），不含新实验结论。所有组件引自己验证的 `engineering/memory-system/` 源码。
