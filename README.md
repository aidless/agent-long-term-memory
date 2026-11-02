# agent-long-term-memory

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**智能体长期记忆工程仓** — 研究「智能体与长期记忆」方向，从三大关键判断出发，走向可运行的工程系统。

## 方向定位

本仓库研究三个关键判断，每个判断都指向 agent 落地的一个硬瓶颈：

### 判断①：长程自主性的失败率连乘衰减
> 多步工具调用、跨天自主、错误复合——每一步都有失败率，连乘起来指数级衰减。这是 agent 落地最卡的环节。

- 单步成功率 0.98，20 步后只剩约 0.67；50 步后只剩约 0.36。
- 研究方向：长程任务的可靠性建模、错误恢复策略、记忆对长程自主性的支撑。

### 判断②：没有真·长期记忆
> 模型本身没有训练意义上的持久记忆，靠外部存储（RAG/向量库）补，但那是「检索」不是「记忆」。检索不到 = 记忆失效。

- 概念区分：检索（retrieval）≠ 记忆（memory）。
- 研究方向：记忆架构（分层/情景/语义/程序）、遗忘与整合、记忆基准。

### 判断③：递归自我改进没有实现
> 很多人以为快到了，实际远没到。

- 边界限定：AlphaEvolve 类是可验证域内自我改进，不是通用递归改进。
- 研究方向：自我改进的可行性边界、评测器捕获（evaluator capture）、可验证性。

## 研究路线图

```
第一阶段（当前）：研究框架 + 证据池
  ├── research/01-long-horizon-autonomy/   # 判断①
  ├── research/02-memory-vs-retrieval/     # 判断②
  └── research/03-recursive-self-improve/  # 判断③
第二阶段：各方向实验设计 + 预注册
第三阶段：工程系统（长期记忆系统支撑长程任务）
```

## 已有资产（本仓引用的前序工作）

| 资产 | 内容 | 位置 |
|---|---|---|
| P6-long-horizon-memory | 长期记忆/遗忘项目，N=72 对预注册 + 功效分析 | `agi-research-program/prereg/P6-memory.md` |
| 18-agent-long-term-memory | 可运行 FastAPI 记忆系统原型（4 类记忆 + 混合检索 + 遗忘） | `engineering/memory-system/`（已搬入） |
| PAPER5 (memory-architecture-bias) | 记忆架构污染研究，1,155 行验证脚本 + 预注册链 | 独立仓库，本仓引用 |
| agent-verifiability / agent-loop-safety | agent 可靠性/可核查性/循环安全 | 独立仓库，本仓引用 |

> 注：P6 与 PAPER5 的正式实验是独立日程，本仓只登记与引用，不重复启动。

## 目录结构

```
agent-long-term-memory/
├── README.md
├── research/               # 研究轨：三大判断的系统研究
│   ├── 01-long-horizon-autonomy/
│   ├── 02-memory-vs-retrieval/
│   └── 03-recursive-self-improve/
├── engineering/            # 工程轨
│   └── memory-system/      # 长期记忆系统（18-agent 原型升级基线）
│       ├── manager/        # Python 记忆管理（forgetter.py 等）
│       └── forgetting-js/  # 选择性遗忘 JS 实现（独立 npm 模块，25 单测）
├── evidence/               # 证据与可复现数据
├── docs/design/            # 设计文档
└── refs/                   # 参考文献 + 引用库
```

## 研究进度

> 截至 2026-11-01，三大判断的实验验证与工程补全已完成（21 个本地提交，110 测试通过）。

### 判断①：长程自主性（`research/01-long-horizon-autonomy/`）

| 实验 | 结论 | 证据 |
|---|---|---|
| R1.1 可靠性曲线 | p^k 指数衰减验证，R²=0.999976（0.98 单步，50 步剩 0.365） | `evidence/2026-11-01-r1_1-reliability-curve.json` |
| R1.2 错误复合 | 错误复合比 p^k 更坏：k=50 惩罚 -0.2423，错误分散 9.0 vs 0.98 | `evidence/2026-11-01-r1_2-error-compound.json` |
| R1.3 记忆支撑 | 记忆帮助长程（上下文不足时 +0.375）但也可能损害（上下文足够时 -0.625） | `evidence/2026-11-01-r1_3-memory-benefit.json` |
| 工程强化 | 冲突检测+关联遗忘补全（94 测试通过） | `manager/conflict.py` + `manager/associated_forgetter.py` |

### 判断②：记忆 vs 检索（`research/02-memory-vs-retrieval/`）

| 实验 | 结论 | 证据 |
|---|---|---|
| R2.1 检索vs记忆 | 模糊查询：纯检索 0.000 / 记忆 1.000（+1.000）；记忆对噪音鲁棒 | `evidence/2026-11-01-r2_1-retrieval-vs-memory.json` |
| R2.2 记忆基准 | 判据 M=P(成功\|模糊,记忆)-P(成功\|模糊,检索)：M=1.000（真记忆） | `evidence/2026-11-01-r2_2-memory-benchmark.json` |
| R2.3 架构分类 | 分层×遗忘×整合设计空间；缺口=冲突检测/关联遗忘 | `research/02-memory-vs-retrieval/design-space.md` |
| R2-E2E 端到端长程 | 真实 MemoryManager 系统支撑长程：k=20 无记忆 0.000/有记忆 0.6925（+0.6925）；上下文足够（C=20）时记忆不再帮助（-0.0145） | `evidence/2026-11-01-r2_e2e-long-horizon.json` |
| R2-INTEGRATION 整合验证 | 强化路径不损害无冲突场景：k=10/20/50 基础 vs 强化差异全 0（0.8505/0.6925/0.3925） | `evidence/2026-11-01-r2-integration-check.json` |
| R2-CONFLICT 冲突场景 | 真实矛盾记忆端到端：detect→mark→resolve→保留高重要性；无冲突 0 误伤 | `evidence/2026-11-01-r2-conflict-integration.json` |

### 判断③：递归自我改进（`research/03-recursive-self-improve/`）

| 实验 | 结论 | 证据 |
|---|---|---|
| R3.1 边界梳理 | AlphaEvolve≠通用递归；外循环=有限递归；权重级未实现 | `boundary-classification.md` |
| R3.2 自指性 | agent 用自身记忆改进：+0.237（超外部注入 +0.144） | `evidence/2026-11-01-r3_2-self-reference.json` |
| R3.3 能力/分数分离 | evaluator capture 门禁：分数+0.345 但 held-out+0.01（p=0.918）→ 假改进 | `evidence/2026-11-01-r3_3-capability-score.json` |

## 快速开始（工程轨基线）

```bash
cd engineering/memory-system
pip install -r requirements.txt
pytest tests/ -q          # 跑记忆系统测试（94 passed）
```

## 工程强化（R2.3 缺口补全）

- **冲突检测**（`manager/conflict.py`）：检测矛盾记忆（同一主题+反义表述），解决冲突保留重要性高者。呼应文献[4] MOSAIC 局限——静默矛盾积累。
- **关联遗忘**（`manager/associated_forgetter.py`）：遗忘触发关联处置（低重要性级联遗忘 / 高重要性断联保留）。
- **冲突场景验证**（`research/02-memory-vs-retrieval/experiments/r2_conflict_integration.py`）：真实矛盾记忆（中文/英文反义对）端到端验证 detect → mark → resolve → keep-higher-importance，无冲突场景 0 误伤。测试：110 passed。

## 阶段报告（2026-11-01）

### 阶段一：研究框架 + 证据池（已完成）

**三大判断全部完成实验验证与工程补全：**

| 判断 | 核心结论 | 关键证据 |
|------|---------|---------|
| ①长程自主性 | p^k 指数衰减（R²=0.999976）；错误复合比连乘更坏（k=50 惩罚 -0.2423）；记忆在上下文不足时帮助（+0.375）但足够时损害（-0.625） | R1.1/R1.2/R1.3 |
| ②记忆 vs 检索 | 检索≠记忆（M=1.000 真记忆）；真实系统支撑长程（+0.6925）；冲突检测/关联遗忘补全 | R2.1/R2.2/R2-E2E/R2-INTEGRATION/R2-CONFLICT |
| ③递归自我改进 | AlphaEvolve≠通用递归；自指增益 +0.237 超外部注入；evaluator capture 门禁（分数+0.345 但 held-out+0.01） | R3.1/R3.2/R3.3 |

**工程强化已接入主流程**：`add_*` 自动冲突检查、`consolidate_memories` 整合后冲突检查、`forget` 触发关联遗忘、`calibration.py`（陈化检测+校准）。测试 110 passed（无回归）。

### 阶段二：实验设计细化 + 预注册（进行中）

**三类实验变体已完成设计与实现（可证伪）：**

| 变体 | 结果 | 关键发现 |
|------|------|---------|
| V2.1 冲突场景 | 多对冲突 resolved_count=2、级联 resolved_count=2、重要性接近保留 0.51、无冲突 0 误伤 | 残留判断须用 `find_conflicts`（真实判据），非 metadata 标记 |
| V2.2 长程任务 | k=100 收益 +0.146（递减）、干扰 +0.693（鲁棒）、混合上下文 +0.677 | 长程收益递减（呼应 R1.1 p^k）；记忆对干扰鲁棒 |
| V2.3 检索 vs 记忆 | 英文基准 M=1.000、噪音全档 M=1.000、高质量检索 M=0.000 | 高质量检索时记忆优势消失（呼应 R1.3 翻转） |

- 实验设计文档：`docs/design/2026-11-01-phase2-design.md`。
- 预注册链：P6 长期记忆预注册 + PAPER5 证据链复用。
- 工程轨：forgetting-js v6 survival potential（已并入）。

### 阶段二：实验设计 + 预注册（下一步）

- 各方向实验设计细化（冲突场景、长程任务变体、检索 vs 记忆对照）。
- 预注册链：P6 长期记忆预注册 + PAPER5 证据链复用。
- 工程轨：forgetting-js v6 survival potential（并行会话进行中）。

## forgetting-js（选择性遗忘 JS 实现）

```bash
cd engineering/memory-system/forgetting-js
npm install
npm test          # 25 断言全过
```

多维度评分（时间/使用/冗余/复用/漂移）+ 两段式遗忘（软遗忘→归档）+ 四判据 + 保护规则。
与 `manager/forgetter.py`（Python）并列，两者覆盖不同运行时栈。

## 复现与验证

本仓库所有研究结论必须能从 `evidence/` 落盘证据重算。设计文档见 `docs/design/2026-11-01-design.md`。

## License

MIT — Liu Zewen, 2026
