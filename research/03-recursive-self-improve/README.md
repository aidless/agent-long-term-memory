# 判断③：递归自我改进没有实现

> **STATUS: WORK-IN-PROGRESS.** `experiments/` holds scripted comparisons, not a demonstration that recursive self-improvement is achieved or refuted on real agents. P6 is a draft; N=72 is a power calculation, not a run. Sister-repo rows are not in this clone and were not checked from here. See `/STATUS.md` and `/FAILURE_MODES.md`.

> **核心判断**：很多人以为快到了，实际远没到。

## 定义

**递归自我改进（recursive self-improvement）**：一个 agent 能**改进自身**（修改自己的权重/架构/工具），且改进后的 agent 又能继续改进自身——形成递归提升循环。

形式化：设 agent 为 $A$，改进算子为 $f$，则递归自我改进要求 $A_{t+1} = f(A_t)$，且 $A_{t+1}$ 的能力严格优于 $A_t$，且 $f$ 本身可由 $A$ 执行。

## 为什么「实际远没到」

### 1. 可验证域内改进 ≠ 通用递归改进
AlphaEvolve 等系统在**可验证域**（如数学表达式、程序）内做进化搜索，能改进目标函数。但这依赖：
- **可验证目标**：需要明确的奖励函数/验证器。
- **有限搜索空间**：进化搜索需要能枚举/采样的空间。
- **无自指**：改进的是目标函数，不是 agent 自身的认知架构。

这不构成通用递归自我改进——它改的是「被求解的问题」，不是「求解者」。

### 2. 评测器捕获（evaluator capture）是硬障碍
如果自我改进以评测分数为目标，改进可能「钻评测空子」而非提升真实能力。这是 `agent-verifiability` / P3（自我进化 evaluator capture）研究的核心问题——分数涨了，能力没涨。

### 3. 权重不可在线更新
LLM 权重训练后固定（除非重训/微调），在线递归改进受限于此。自我改进若局限于「提示/工具/记忆」层面，那是**外循环改进**，不是权重级递归改进。

## 现有证据（本仓引用）

| 证据 | 来源 | 状态 |
|---|---|---|
| 自我进化 evaluator capture | `agi-research-program/P3`（GSM8K 五键门 FPR、4 模型 null） | not in this clone; figures not recomputable here |
| 自我进化 McNemar 缺陷 | `evo_agent`（独立仓库） | not in this clone; not checked here |
| agent 可核查性 | `agent-verifiability`（独立仓库） | not in this clone; not checked here |

## 文献锚点（已验真，见 `../../refs/2026-11-01-verified-literature.md`）

| 文献 | 锚点 | 验真状态 |
|---|---|---|
| [6] Self-Referential Introspection（Entropy 2026, doi 10.3390/e28090951） | 自指内省临界阈值，递归自我改进的可行性边界 | ✅ |

> **判断③的直接理论锚点**：文献[6] 研究 LLM 自指内省的临界阈值，决定递归自我改进是否可能。与 AlphaEvolve（可验证域内改进≠通用递归）共同构成本判断的实证基础。

## 缺口

1. **通用递归改进的可行性边界**：什么条件下「改进求解者」才是可能的（vs 只能改进被求解问题）。文献[6] 给出临界阈值的理论视角，但未与 AlphaEvolve 类系统做实证对照。
2. **改进算子的自指性**：$f$ 能否由 $A$ 自身执行，而不是依赖外部系统。文献[6] 研究自指内省，但改进算子执行主体问题仍开放。
3. **能力 vs 分数的分离**：任何自我改进主张必须分离「真实能力提升」与「评测器钻空」。文献[6] 未涉及 evaluator capture——这仍是本判断最硬的工程障碍。

## 研究方向（第一阶段只立框架）

- **R3.1 边界梳理**：系统梳理已有「自我改进」工作，按「可验证域内 / 外循环 / 权重级」分类，明确哪些是通用递归、哪些不是。
- **R3.2 改进算子自指性**：设计「agent 能否改进自己的提示/工具/记忆」的判定实验（外循环层面）。
- **R3.3 能力/分数分离**：对任何自我改进主张，用 evaluator-capture 门禁验证（衔接 P3 方法）。

## 关联

- `agi-research-program/P3`：evaluator capture 是自我改进主张的必要校验。
- `agent-verifiability`：可核查性是自我改进可信度的前提。
- 工程轨：记忆系统作为「外循环改进」的一种（agent 通过记忆改进自身行为）——这是现实可达的改进形式。

> **R3.1 笔记已落盘（非实证）**（2026-11-01）：`boundary-classification.md` 递归自我改进边界梳理——按**改进对象/执行主体/验证方式/更新层级**四维分类已有工作。**可验证域内改进（AlphaEvolve 类）≠ 通用递归**（改被求解问题非求解者）；**外循环改进（记忆/提示/工具）是现实可达的有限递归**（本仓工程轨正属此层，需有效验证）；**权重级递归未实现**（硬障碍：evaluator capture + 权重不可在线更新）。P3 实证锚点：无检验晋升率 41.25%（R2），best-of-8 达 98.25%（R7）都是假阳性——自我改进主张必须过有效统计门禁（R1 FPR=0.0125）。边界分类文档 `boundary-classification.md`。
> **R3.2 脚本已落盘（非实证）**（2026-11-01）：`experiments/r3_2_self_reference.py` 自指性判定实验——**agent 能用自身记忆改进自身行为**（自指外循环改进）。5 episode 长程任务：no_memory 0.025 → self_improve 0.262（**自指增益 +0.237**），且自指增益**超外部知识注入**（+0.144）——agent 自身经验沉淀比外部注入更有效（情境化）。判据 SELF_REFERENTIAL——外循环层面自指性成立，支持工程轨（记忆系统是有限递归自我改进的实现）。证据 `evidence/2026-11-01-r3_2-self-reference.json`。
> **R3.3 脚本已落盘（非实证）**（2026-11-01）：`experiments/r3_3_capability_score.py` 能力/分数分离门禁——**evaluator capture 门禁正确区分「真改进」vs「假改进」**。场景 A（无过拟合）：分数 +0.25（p<.001）AND held-out +0.195（p<.001）→ CAPABILITY_IMPROVEMENT。场景 B（过拟合）：分数 +0.345（p<.001）但 held-out +0.01（p=0.918）→ **EVALUATOR_CAPTURE**（分数涨但能力没涨）。门禁判据：任何自我改进主张必须验证「分数涨 AND held-out 涨」（McNemar p<.05 + held-out 迁移）。证据 `evidence/2026-11-01-r3_3-capability-score.json`。

> 本文件是研究框架加脚本笔记。「脚本已落盘」指 JSON 已写入，不是判断已被实证。AlphaEvolve 与 evaluator capture 的外部说法不在本克隆内复核。
