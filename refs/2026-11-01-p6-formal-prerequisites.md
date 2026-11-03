# P6 正式运行前置条件（阶段三）

> 本文件登记 P6 长期记忆预注册正式运行的前置条件。**当前 pilot（N=36，synthetic=true）不满足正式实验要求**——以下条件全部闭合后才能启动正式运行（N=72 pairs）。正式运行属于独立日程（4-6 周），本仓不空跑合成数据冒充正式实验。

## 前置条件清单（P6 正式运行）

| # | 条件 | 当前状态 | 验证方式 | 来源 |
|---|------|---------|---------|------|
| C1 | **真实数据替换**：synthetic flag=false | ❌ 全部 18 个 per_seed 文件 synthetic=true | 读 run_records/pilot-p2-20260907.json 确认 synthetic 字段 | `dataset_spec.md:13`、`analysis_plan.md:29`、`protocol.md:24`、`P6-memory.md:14` |
| C2 | **样本量**：12 场景 × 6 seeds = 72 pairs | ❌ 当前 3 seeds（N=36） | 数 per_seed JSON 数量 + 每个 JSON 的 scenarios 长度 | `P6-memory.md:14`（McNemar 先验 N=60、paired t N=34） |
| C3 | **H3 非劣效界正式预设** | ❌ 当前 +0.05 是试点值 | 读 cfg_snapshot.json h3_delta 字段；正式运行前在 P6 预注册冻结 | `WORKING_NOTES.md:6` |
| C4 | **TODO-D1 闭合**：数据集版本/切分/许可操作化 | ❌ 未闭合 | 读 analysis_plan.md:27；P2 启动前必须闭合，否则 P2 gate FAIL | `analysis_plan.md:27` |
| C5 | **分析纪律**：Holm 用未舍入 p；唯一脚本一次产出 W/p/r/rank-biserial；assert mean(d)==组间均值差 | ⚠️ 部分 | 读 analysis_p3.py 确认 | `analysis_plan.md` |

## 正式运行决策规则（P6 预注册）

- **H1（primary）**：Full 任务成功率高于各基线 → exact McNemar + Holm，p_holm < 0.05 且方向一致 → PROVEN。
- **H2（secondary）**：Full 记忆命中高于 no-forgetting 消融 → Wilcoxon + CLES + bootstrap CI 不跨 0 → PROVEN。
- **H3（secondary）**：Full 成本显著更低 + 安全违规率在非劣效界内 → PROVEN。

## 当前 pilot 结果（N=36，synthetic，仅供参数估计）

| 假设 | 结果 | 决策 | 备注 |
|------|------|------|------|
| H1 | abl_noNegot OR=3.33，p_holm=0.4614（最接近） | inconclusive | 未达 McNemar N=60；achieved power=0.617 |
| H2 | vs abl_noForget mean_diff=+0.0922，p_holm=0.0066 | PROVEN 候选 | 合成伪影可能，需真实数据验证 |
| H3 | cost_mean_diff=-77.55（p_holm=1.16e-10）；viol_diff=+0.0278 在界内 | PROVEN 候选 | 需正式界与真实数据 |

## 功效推算（正式 N=72）

- 以 abl_noNegot OR=3.33 为效应量外推：n_disc=30（b=23,c=7）raw_p=0.0026 → Holm 5 比较 sig。
- **正式 N=72 有足够功效检测 abl_noNegot 差异**（若效应量保持）。

## 结论

- 阶段三正式运行**无法在本仓用现有合成资产完成**——需要真实数据源（外部基准或真实运行），且 C1-C4 未闭合。
- **合理动作**：登记本仓 P6 引用 + 明确前置条件（本文件），不空跑合成数据冒充正式实验。
- 正式运行启动条件：C1-C4 全部闭合 + 用户确认启动（独立日程 4-6 周）。

## C1 数据源扫描结论（2026-11-02 更新）

**结论：工作区内无现成的「多智能体协作 + 记忆-遗忘 + 安全协商」真实数据集，C1 无法用现有资产闭合。**

### 扫描结果

| 数据源 | 规模 | 结构 | 可用性 |
|--------|------|------|--------|
| multiagent_scaling/results/e1b_replay_raw.jsonl | 25920 runs | 真实 multiagent 延迟（makespan） | ❌ 非任务成功/失败（无 0/1） |
| paper_agent/data/*.jsonl | 6013 条 | 全 synthetic=true | ❌ 无真实轨迹 |
| ai-agent-playground/memory/reliability.jsonl | 99 条 | 单步工具调用 | ❌ 非长程 |
| ai-agent-playground/memory/traces/pytest_001.jsonl | 112 步 | 测试演示 | ❌ 非 agent 真实运行 |

### C1 闭合路径

P6 正式实验需要：① 多智能体协作任务（12 场景）② 记忆-遗忘框架（MemoryManager 已有）③ 轻量安全协商（需构造）④ 真实 agent 运行轨迹（无）。

**C1 闭合需要构造真实数据管道**：设计多智能体协作任务 + 安全协商模块 + 真实运行 agent 采集轨迹（独立工作项，4-6 周）。

> 本仓不空跑合成数据冒充正式实验——这是科研诚信要求。正式运行启动需 C1-C4 闭合 + 用户确认。

## C1 进展（2026-11-03 更新）

**管道已打通 + 冒烟证据落盘；C1 仍需正式标定才能闭合。**

- `engineering/real-pipeline/run_mini_free_pilot.py`（新增）：在真实 DAG 任务上运行
  真实 LLM agent（Magpie `opencode-zen-free/deepseek-v4.1-flash-free`，工具调用），
  集成真实 `MemoryManager.search` 检索 + `LightweightSecurityNegotiator` 协商，
  采集真实轨迹（`synthetic=false, calibration=true`）。RED/GREEN selftest 全过。
- `engineering/real-pipeline/evidence/trace_T08_full_seed0_smoke.json`（新增）：
  真实轨迹冒烟（T08，2 节点，mem_hits=1，neg=allow）。`preregister_real_run.py --check`
  已把 C1 识别为 `ok=true`（存在 synthetic=false 证据）。
- **诚实限制**：这是**冒烟级证据**（1 条轨迹，无 baseline 对照），可证明管道工作，
  但不足以估计 4 个标定常数（tool_fail_rate/mem_benefit/negotiation_benefit/
  base_mem_hit_rate）。C1 正式闭合需多臂对比标定。
- **免费通道容量**：`opencode-zen-free` 实测约 35k token/日触发 429；微型 pilot
  （6 任务×1 seed×3 臂=18 轨迹）需约 47.5 万 token（~1100/节点含 reasoning）。
  **免费通道单日无法完成微型 pilot**，需分批/额度内通道/付费授权。
