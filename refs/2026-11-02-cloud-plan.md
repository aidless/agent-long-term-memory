# Cloud Compute Plan for C1 Real-Data Calibration

> Status: **plan** (no compute started). Author: local agent, 2026-11-02.
> Purpose: identify viable cloud paths for the real-agent trajectory
> calibration that closes C1. Execution requires explicit user authorization.

## 1. Available cloud paths (probed 2026-11-02, read-only)

| Path | Status | Notes |
|------|--------|-------|
| Magpie gateway `127.0.0.1:3425` | ✅ **ALIVE** | OpenAI-compatible; 63 models; many support `tools` |
| AMD T4 `36.150.116.206:34677` | ❌ refused | instance destroyed (matches CASMI report 11-02) |
| Kaggle GPU | ⚠️ CLI present, no `kaggle.json` | needs login + quota check |
| Aliyun `ecs-hz`/`ecs-us` | not probed | requires SSH config check |
| SeetaCloud GPU | not probed | requires account check |

## 2. Viable real-agent models (tool-calling capable)

Probed via Magpie `/v1/models` + completion smoke (all returned valid responses):

| Model id | Tools | Context | Notes |
|----------|-------|---------|-------|
| `kiro/qwen3-coder-next` | ✅ tools/tool_choice | 256K | Qwen3 Coder; good small-model agent candidate |
| `workbuddy/deepseek-v4.1-flash` | ✅ tools/tool_choice | — | DeepSeek V4.1 Flash |
| `nvidia/deepseek-ai/deepseek-v4.1-flash` | ✅ tools/tool_choice | — | DeepSeek V4.1 Flash |
| openrouter `*:free` | ❌ | — | blocked by account privacy setting ("paid model training violation") |

## 3. Calibration compute estimate (planning only)

Per the calibration protocol (`2026-11-02-real-calibration-protocol.md`):
- K=24 DAG tasks (stratified L-low/L-high), S=3 seeds, ~6 arms.
- Total real-agent runs ≈ 24 × 3 × 6 = 432 tool-calling trajectories.
- Each trajectory ≈ 24 DAG nodes → ≈ 10,368 LLM tool-call generations.
- At ~1-2s/generation on a cloud model → est. 3-6 hours wall-clock on one
  GPU host (or faster on a multi-host pool). **Planning estimate only.**

## 4. Authorization gate

- **Do NOT start any cloud host, call any paid model, or consume GPU quota
  without explicit user authorization.** (AGENTS.md rules 3 & 17.)
- Magpie is a gateway; using its models may consume balance/quota. Check
  `~/.config/magpie/balance-history.json` before any paid-model call.
- Prefer the cheapest capable path: Magpie `kiro/qwen3-coder-next` if it is
  free/quota-covered; otherwise ask the user which paid path to authorize.

## 5. Decision needed from user

1. **Which model**: `kiro/qwen3-coder-next` (Qwen Coder) vs a DeepSeek
   V4.1 Flash variant. Qwen Coder is closer to the multiagent_scaling
   `qwen3_1p7b` precedent; DeepSeek is larger/more capable.
2. **Which cloud path**: Magpie (currently alive) vs setting up Kaggle/Aliyun.
3. **Authorization to spend**: how much GPU/quota is acceptable for ~3-6h.

## 6. No-action alternative

If the user prefers not to spend GPU/quota now, the calibration stays a
protocol+plan (this repo's `refs/` documents). C1 remains open and the paper
stays a "research+engineering report", which is honest and consistent with
the P6 preregistration.
