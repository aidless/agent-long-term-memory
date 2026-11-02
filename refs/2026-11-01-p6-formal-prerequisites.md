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
