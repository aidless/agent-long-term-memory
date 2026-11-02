# 预注册链登记（P6 复用）

> 本文件登记 P6 长期记忆预注册的引用，**不重复启动**——P6 正式实验（N=72 pairs）是独立日程（4-6 周），本仓只提供预实验（pilot）参数估计。

## P6 预注册引用

- **文件**：`agi-research-program/prereg/P6-memory.md`（仓库外，上级工作区）
- **状态**：draft（正式 N=60/72 运行前冻结）
- **假设**：
  - H6.1 (primary)：Full 任务成功率高于各基线（精确 McNemar + Holm）。
  - H6.2 (secondary)：Full 记忆命中高于 no-forgetting 消融（配对/Wilcoxon + Holm）。
  - H6.3 (secondary)：Full 成本更低且安全违规率在预注册非劣效边界内。
- **设计**：12 场景 × 6 seeds = 72 pairs；arms：Full / CoSkill / Compact-Memory / CONTINUITY / no-forget 消融 / no-negotiation 消融。

## 本仓预实验（阶段二）→ P6 参数估计

| 本仓实验 | P6 假设 | 提供参数 | 实测结果 |
|---------|---------|---------|---------|
| V2.1 冲突变体 | H6.2 memory hit | 冲突场景记忆命中/解决率 | 多对 resolved=2、级联 resolved=2、重要性接近保留 0.51 |
| V2.2 长程变体 | H6.1 primary | 效应量（长程收益） | k=100 收益 +0.146、k=20 +0.693（干扰/混合同） |
| V2.3 检索 vs 记忆 | H6.3 cost+safety | 记忆 vs 检索收益差 | M(模糊)=1.000；高质量检索 M=0.000（优势消失） |

## 纪律

- 正式运行（N=72）必须满足：synthetic flag=false、12 场景 × 6 seeds 完整、每 seed 报告排除、不跨层合并推断。
- 本仓实验保持 pilot-only 状态；若要升级为正式结果，需更新 P6 版本（日期条目）。

## P6 正式运行前置条件（2026-11-01 更新）

- 前置条件清单见 `refs/2026-11-01-p6-formal-prerequisites.md`（C1-C5）。
- **当前状态：C1-C4 未闭合**——真实数据替换（C1）、N=72（C2）、H3 界预设（C3）、TODO-D1 闭合（C4）。
- 正式运行（N=72 pairs）属于独立日程（4-6 周），需前置条件全部闭合 + 用户确认启动。
- 本仓实验保持 pilot-only 状态；不空跑合成数据冒充正式实验。
