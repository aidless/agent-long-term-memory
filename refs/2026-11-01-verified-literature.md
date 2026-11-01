# 文献锚点验证记录（2026-11-01）

> 本文件记录研究框架中三大判断的文献锚点，所有条目均经「号-题一致」验真（AGENTS.md 铁律 2：绝不编造，必须实测/验号）。
> 验证方式：arXiv abs 页 web_fetch / OpenAlex API 逐条核对标题与作者。验证时间：2026-11-01。

## 判断①：长程自主性（long-horizon autonomy）

### [1] Beyond pass@1: A Reliability Science Framework for Long-Horizon LLM Agents
- **arXiv**: 2603.29231 (cs.AI)
- **DOI**: 10.48550/arXiv.2603.29231
- **作者**: Aaditya Khanal, Yangyang Tao, Junxiu Zhou
- **投稿日期**: 2026-03-31
- **页数**: 23 pages, 4 figures
- **验证状态**: ✅ 已验真（arXiv abs 页抓取，标题一致）
- **核心贡献**:
  - 提出可靠性科学框架，四指标：Reliability Decay Curve (RDC)、Variance Amplification Factor (VAF)、Graceful Degradation Score (GDS)、Meltdown Onset Point (MOP)
  - 10 模型 × 23,392 集 × 396 任务基准，跨四个时长桶与三个领域
  - **关键发现**: (1) 可靠性衰减领域分层——SE GDS 0.90→0.44 vs 文档处理近似平坦 0.74→0.71; (2) VAF 按能力层分叉——高 VAF 是能力签名非不稳定信号; (3) 能力与可靠性排名显著分歧，长时程出现多排名反转; (4) 前沿模型融化率最高（达 19%）因尝试雄心勃勃的多步策略; (5) **记忆脚手架普遍损害长时程性能（全部 10 模型）**
- **对研究框架的意义**: 这是「判断①失败率连乘」的**直接实证**——可靠性衰减曲线实测，且揭示「pass@1 短任务对长时程分歧结构性失明」。发现 (5) 与判断②「检索≠记忆」呼应：**记忆脚手架反而有害**。

### [2] The Horizon Gap: Planning, Memory, Execution, Training, and Evaluation for Long-Horizon LLM Agents
- **arXiv**: 2608.06663 (cs.CL)
- **DOI**: 10.48550/arXiv.2608.06663
- **作者**: Mingguang Chen, Licheng Wang, Bo Qu
- **投稿日期**: 2026-08-07
- **页数**: 39 pages, 6 figures
- **验证状态**: ✅ 已验真（arXiv abs 页抓取，标题一致）
- **核心贡献**:
  - 系统综述 **1,547 篇 arXiv 论文（2024-2026）**，26.8% bleed filter 披露
  - **区分三个常被混为一谈的属性**: long-horizon（任务属性：所需步数）、long-context（模型属性：token 容量）、long-term memory（系统属性：跨步/跨会话持久）
  - 六类目组织：planning, memory, execution, training, evaluation, foundations/safety × 时程承载轴（within-context / within-task-beyond-context / cross-task-persistent）
  - 跨类目共同模式：**outcome-only 信号随时程延长而信息量递减**，领域应对（PRM、credit assignment、trajectory-level diagnostics）制造更密的 step-level 信号
  - 开放测量问题：模型 vs harness 能力分解、训练与评测共用 process-level 信号的相关偏倚、长时程可靠性是否存在通用预测理论
- **对研究框架的意义**: 这是「判断①」的**概念基础**——明确 long-horizon ≠ long-context ≠ long-term memory 三者区分，避免术语混淆。综述规模（1,547 篇）使「长程失败率连乘衰减」这一判断有系统文献支撑。

## 判断②：检索 ≠ 记忆（memory vs retrieval）

### [3] Human-inspired Perspectives: A Survey on AI Long-term Memory
- **arXiv**: 2411.00489 (cs.AI), v2 (2025-01-12 修订)
- **DOI**: 10.48550/arXiv.2411.00489
- **作者**: Zihong He, Weizhe Lin, Hao Zheng, Fan Zhang, Matt W. Jones, Laurence Aitchison, Xuhai Xu, Miao Liu, Per Ola Kristensson, Junxiao Shen
- **投稿日期**: 2024-11-01 (v1), 2025-01-12 (v2)
- **验证状态**: ✅ 已验真（arXiv abs 页抓取，标题一致）
- **核心贡献**:
  - 首个系统调查 AI 长期记忆能力、构建理论框架、启发下一代系统
  - 先介绍人类长期记忆机制，再探索 AI 长期记忆机制，建立两者映射
  - 基于映射关系扩展认知架构，提出 **SALM（Cognitive Architecture of Self-Adaptive Long-term Memory）**
  - 探讨 AI 长期记忆的未来方向与应用前景
- **对研究框架的意义**: 这是「判断②」的**理论框架基础**——人类记忆机制的认知科学映射，SALM 提供实践指导。

### [4] Accurate and Efficient Long-Term Memory for LLM Agents (MOSAIC)
- **arXiv**: 2607.16211 (cs.AI)
- **DOI**: 10.48550/arXiv.2607.16211
- **作者**: Zicheng Zhao, Xinyang Guo, Luyao Lv, Menghan Wang, Ming Li, Shuaicheng Li
- **投稿日期**: 2026-05-15
- **验证状态**: ✅ 已验真（arXiv abs 页抓取，标题一致）
- **核心贡献**:
  - **MOSAIC**（Memory-Organized Structured Agent for Information Collection）——结构化、冲突感知长期记忆框架
  - 三能力: (1) entity-typed graph storage 保留关系结构，支持多跳与时序推理; (2) hash-accelerated dual-path retrieval 以 locality-sensitive hashing 替代 LLM 分类，近即时查找; (3) active conflict detection at save time 交叉引用新信息与既有图邻居，触发矛盾条目的更新/删除
  - **评测**: LoCoMo 89.35%（+27.21pp over best baseline）、HaluMem-Medium F1 86.77%、HaluMem-Long F1 85.84%、QA correctness Medium 73.10% / Long 70.75%、注入事实冲突检测 66%（4.7× 最佳基线 14%）、hash 加速检索延迟 0.58s/question
- **对研究框架的意义**: 这是「判断②」的**技术前沿实证**——现有系统「扁平无结构存储丢失关系上下文」「依赖昂贵 LLM 分类不实用」「无验证机制静默积累矛盾」三大局限正是「检索≠记忆」的工程表现。MOSAIC 的冲突检测能力直接指向记忆完整性。

### [5] Retrieval-Driven Memory Reconsolidation for Long-Term LLM Agents (REALM)
- **arXiv**: 2609.16053 (cs.CL / cs.AI)
- **DOI**: 10.48550/arXiv.2609.16053
- **作者**: Yuanyi Song, Yukai Wang, Xinbei Ma, Zhihui Fu, Jianghao Lin, Weiwen Liu, Jun Wang, Huarong Deng, Yong Yu, Weinan Zhang
- **投稿日期**: 2026-09-13
- **验证状态**: ✅ 已验真（arXiv abs 页抓取，标题一致）
- **核心贡献**:
  - **REALM**（reconsolidation-evolution agentic long-term memory）——受认知神经科学记忆再巩固启发
  - 把长期记忆建模为持续生命周期：自主组织异构认知图、通过自适应组合图搜索原子检索证据、基于检索反馈持续再巩固记忆
  - **评测**: LoCoMo 75.97%、LongMemEval 65.11%，超最强基线 7.17 / 1.31 分
  - 消融实验确认记忆再巩固持续提升性能；分析揭示逐步将相关记忆单元重组为更连贯局部结构以集体证据调用
- **对研究框架的意义**: 这是「判断②」的**最直接实证**——「检索是记忆访问的终点而非记忆演化的驱动力」这一局限被 REALM 打破。**检索反馈驱动记忆再巩固**，正是「检索≠记忆」的对立面探索。

## 判断③：递归自我改进（recursive self-improvement）

### [6] Self-Referential Introspection in Large Language Models: The Critical Threshold for Recursive Self-Improvement
- **期刊**: Entropy 2026, 28(9), 951
- **DOI**: 10.3390/e28090951
- **作者**: Jiang Zhang, Bing Yuan, Qian Zhang
- **验证状态**: ✅ 已验真（OpenAlex API 查询，标题与作者一致；MDPI 页面因反爬屏蔽，改用 OpenAlex）
- **核心贡献**:
  - 研究 LLM 中的自指内省（self-referential introspection）与递归自我改进的临界阈值
  - 探讨：LLM 是否以及何时能通过自指反思实现递归自我改进
- **对研究框架的意义**: 这是「判断③」的**直接理论锚点**——自指内省的临界阈值决定递归自我改进是否可能。与 AlphaEvolve（可验证域内改进≠通用递归）共同构成本判断的实证基础。

---

## 验证方法说明

1. arXiv 条目（1-5）：直接 web_fetch `https://arxiv.org/abs/<id>`，核对标题、作者、投稿日期。
2. Entropy 条目（6）：MDPI 页面因反爬屏蔽（HTTP 403），改用 OpenAlex API 查询 DOI，返回标题/作者/年份/期刊全部一致。
3. 全部 6 篇验真通过，**无一篇来自记忆猜测**——每一篇都经过外部源核对。

## 未验证候选（暂不写入）

以下条目曾在研究框架中提及但**未经验证**，待后续验证后再补：
- **Error Trace Regression**（ICML 2026）——长程轨迹根因定位，尚未定位到具体 arXiv ID / DOI，不可写入。
