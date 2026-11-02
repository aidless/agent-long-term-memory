# R2.3 剩余缺口补全：程序记忆陈化检测 + 重要性校准

> 2026-11-01 · 项目 agent-long-term-memory · R2.3 缺口 3/4

## 缺口定义（来自 design-space.md）

- **缺口 3 程序记忆陈化**：技能随环境变化陈化，需要「技能失效」机制而非纯时间衰减。
- **缺口 4 重要性校准**：重要性评分（`alpha·manual+beta·access_freq+gamma·recency`）的主观性——需要与遗忘策略联动校准。

## 实现

### 新文件 `engineering/memory-system/manager/calibration.py`

**ProceduralStalenessDetector**（程序记忆陈化检测器）：
- 判据（任一成立即陈化）：
  1. **失败过多**：成功率 < min_success_rate(0.4) 且使用次数 ≥ min_usage_count(5)
  2. **长期未用且低重要性**：未使用超 stale_after_days(90) 且 importance < stale_importance_threshold(0.3)
  3. **近期失败级联**：近期（recent_failure_window=30 天）失败 ≥ recent_failure_threshold(3) 次
- `is_stale(item, current_time)` / `find_stale(items, current_time)`
- **与纯时间衰减区分**：陈化 = 技能失效（环境变了），不是「变旧」——forgetter 处理纯时间衰减，本检测器处理技能失效。

**ImportanceCalibrator**（重要性校准器）：
- `calibrate(item, current_time)` → `clip(manual_base + access_bonus + recency_bonus - failure_penalty - stale_penalty)`
- 手动基础重要性 × 0.5 + 访问频率奖励（log 平滑，上限 0.2）+ 近期使用奖励（30 天窗口线性递减）- 每次失败惩罚 0.1 - 陈化惩罚 0.2（仅程序记忆）
- 下限 0.05 / 上限 1.0
- **与遗忘联动**：校准后的重要性写回记忆，直接喂给 forgetter 的保留分数计算——高重要性不易遗忘，低重要性易遗忘。

### MemoryManager 集成（`manager/memory_manager.py`）

- `__init__` 新增 `self.staleness_detector` + `self.importance_calibrator`
- 新方法：
  - `detect_stale_procedural()` → 陈化的程序记忆列表
  - `calibrate_importance(memory_type, memory_id)` → 校准单条并写回
  - `calibrate_all_importance(memory_type)` → 校准全部并写回

## 测试（`tests/test_calibration.py`，12 个）

- **StalenessDetector**（6）：失败过多→陈化 / 健康技能→不陈化 / 长期未用低重要性→陈化 / 长期未用高重要性→不陈化 / 近期失败级联→陈化 / find_stale 多个
- **ImportanceCalibrator**（4）：访问频率奖励 / 失败惩罚 / 上下限 / 近期使用奖励
- **集成**（2）：MemoryManager 检测陈化程序记忆 / MemoryManager 校准重要性（失败→降低）

## 结果

- `test_calibration.py`：**12 passed**
- 全套件：**110 passed**（原 98 + 新 12），无回归

## 复现

```bash
cd engineering/memory-system
python3 -m pytest tests/test_calibration.py -v   # 12 passed
python3 -m pytest tests/                          # 110 passed
```
