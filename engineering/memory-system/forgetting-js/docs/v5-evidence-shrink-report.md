<!-- COUNT-HISTORICAL: suite counts below are a point-in-time note, not the live count. Live count: evidence/offline-claims.json -->

# v5 交付报告：证据加权收缩（evidence-weighted usage shrink）

> **Version snapshot.** "82 PASS" is this version's note, not the live suite. Live count: `evidence/offline-claims.json`. `evolve-memory.js` is not in this clone.

> 2026-11-01 · 开源仓库 `forgetting-js` · 82 PASS / 0 FAIL · commit `2e3ae9e`

## 1. 背景：Memory Worth 的「证据量」洞见

论文《When to Forget: A Memory Governance Primitive》(arXiv:2604.12007) 提出
**Memory Worth** 双计数器信号：

```
MW_T(m) = hits⁺ / (hits⁺ + hits⁻)
```

其中 hits⁺/hits⁻ 是按检索权重累积的**成功/失败次数**。论文证明 MW 几乎必然收敛到
`p⁺(m) = Pr[成功 | m 被检索]`，并强调**双计数必要**：单标量比值会混淆
「高证据可靠」(80/20) 与「低证据不确定」(8/2)。

## 2. 可行性边界（诚实声明）

探测 dsh 的检索/outcome 信号后，结论如下：

| 信号 | dsh 是否记录 | 说明 |
|---|---|---|
| 正信号 hits⁺ | ✅ `use_count` | `recordMemoryUse` 在按 id 读取时触发（`evolve-memory.js:87`），注释明确「Search/list hits are noise and stay uncounted」 |
| 负信号 hits⁻ | ❌ 无 | 检索失败（记忆被检索但没用上）不记录 |

**结论：Memory Worth 的「成功/失败比值」在 dsh 架构下不可落地**（无失败信号）。
本 v5 只落地「证据量」部分（`use_count → V_m`），**不伪造失败信号**（铁律：绝不编造）。

## 3. 实施：证据加权收缩

`usage_factor` 从线性饱和改为**证据加权收缩**：

```
usage_factor = useCount === 0 ? 0
             : 0.5 + (linearUsage - 0.5) * shrink
shrink       = useCount / (useCount + EVIDENCE_HALF)
linearUsage  = min(1, useCount / USAGE_SATURATION)
```

关键设计决策：

- **`use=0`（无证据）保持 0**：从未使用的记忆应继续可遗忘，不因「中性收缩」被抬高过
  阈值（否则违背 v3 核心修复——6 个月零使用的 reference 应 < 0.15 可遗忘）。
- **`use≥1`（有证据但不确定）向 0.5 收缩**：避免「用过 1 次」和「用过 20 次」被同样
  对待——这正是论文 2「高证据可靠 vs 低证据不确定」的洞见。
- **`use→∞` 趋近线性饱和值 1**：高证据记忆回到线性。

### 数值验证

| useCount | linearUsage | shrink | usageFactor | 语义 |
|---|---|---|---|---|
| 0 | 0 | 0 | **0** | 无证据，继续可遗忘 |
| 1 | 0.333 | 0.333 | 0.444 | 向中性收缩 |
| 2 | 0.667 | 0.500 | 0.583 | 向中性收缩 |
| 3 | 1.0 | 0.600 | 0.800 | 趋近线性 |
| 10 | 1.0 | 0.833 | 0.917 | 高证据 |
| 1000 | 1.0 | 0.998 | 0.999 | 趋近 1 |

### 公式修正过程（两版）

1. **第一版** `0.5 + (0.5 - |0.5 - linear|) * shrink`：`linear > 0.5` 时（use≥2）被错误
   压向 0.5，高使用记忆 use=3/10/100 全变 0.5（应趋近 1.0）。**缺陷**。
2. **修正** `0.5 + (linear - 0.5) * shrink`：方向正确，但 use=0 时变 0.5（中性）抬高
   score，违背 v3 核心修复。**二次修正**：`use=0` 保持 0。

## 4. 测试

- V13 新增 8 断言：use=0 保持 0 / use=1,2 收缩 / use=3 趋近 / 单调 / 有界 / use=1000 趋近 1。
- 总 **82 PASS / 0 FAIL**（V1-V13 全套）。

## 5. 交付物

| 文件 | 变更 |
|---|---|
| `src/forgetting/forgetting.js` | `FORGETTING_DEFAULTS` 加 `EVIDENCE_HALF=2`；`scoreMemory` usageFactor 改证据加权收缩 |
| `test/forgetting.test.mjs` | V13 8 断言 |
| `README.md` | v5 说明 + 参数表加 EVIDENCE_HALF + 测试数 82 |
| `package.json` | 1.2.0 → 1.3.0 |
| 插件 `forgetting.js` | 同步（md5 `865fb850a06e109508b6cc595a621efc`） |

## 6. 与论文的关系

- **Memory Worth（论文 2）**：只落地「证据量」维度，成功/失败比值不可落地（诚实边界）。
- **多因子价值模型（论文 1）**：v4 已落地多因子加权，与论文 1 同源。
- **MemGPT / MemoryBank**：v1 双段式（分层）与 exp(-0.05×days)（Ebbinghaus）同源。
