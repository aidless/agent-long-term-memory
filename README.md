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

## 快速开始（工程轨基线）

```bash
cd engineering/memory-system
pip install -r requirements.txt
pytest tests/ -q          # 跑记忆系统测试
```

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
