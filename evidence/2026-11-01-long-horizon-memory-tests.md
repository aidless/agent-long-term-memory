<!-- COUNT-HISTORICAL: suite counts below are a point-in-time note, not the live count. Live count: evidence/offline-claims.json -->

# 长程任务记忆支撑测试证据

> **Historical snapshot.** Counts in this file, including an older "83" figure and a later full-suite number, are notes from 2026-11-01. The live count is `evidence/offline-claims.json`. The test names below include retrieval checks; see `FAILURE_MODES.md` before reading a pass as a memory benefit.

> 日期：2026-11-01
> 测试文件：`engineering/memory-system/tests/test_long_horizon.py`（6 个测试）
> 结果：**112 passed**（完整套件；含 6 个长程任务测试。本文件记录的是新增测试当时的口径 83，实测当前为 112）

## 测试内容

| 测试 | 验证目标 | 结果 |
|---|---|---|
| test_memory_storage_across_steps | 跨步记忆存储（每步上下文正确存入语义记忆） | ✅ PASS |
| test_cross_step_retrieval_hit_rate | 跨步检索命中（后续步骤能检索前期记忆） | ✅ PASS |
| test_long_horizon_memory_benefit | 20 步任务机械对照（无记忆组完成率 ≈ 理论 p^k，±5% 容差） | ✅ PASS |
| test_memory_persistence_across_sessions | 跨会话持久性（会话 2 能加载会话 1 的记忆） | ✅ PASS |
| test_memory_retrieval_quality_no_degradation | 高重要性记忆不被过早遗忘（15 步后保留 ≥10） | ✅ PASS |
| test_memory_consolidation_over_long_horizon | 长程记忆整合（相关记忆被合并） | ✅ PASS |

## 关键验证

1. **p^k 衰减对照**：无记忆组完成率与理论值 `p_step^n_steps` 偏差 < 5%（随机种子 42，可复现）。
2. **记忆不损害长程性能**：有记忆组在机械对照中不劣于无记忆组。
3. **跨会话持久性**：`SimpleVectorStore` 自动持久化（`persist_path`），会话 2 成功加载会话 1 的记忆。
4. **中文分词限制**：`_simple_cluster` 用 `content.split()` 按空格分词，中文整句退化为单 token（相似度 0），需用英文内容测试整合——这是系统的已知限制（改进方向：接入 jieba 分词）。

## 复现命令

```bash
cd <REPO_ROOT>
python3 -m pytest engineering/memory-system/tests/ -q
# 预期：112 passed
```
