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

## 7. Free-channel capacity audit (2026-11-02, probed)

The user asked to find a FREE path first. Findings:

| Free channel | Status | Capacity |
|--------------|--------|----------|
| `opencode-zen-free/deepseek-v4.1-flash-free` | ✅ usable now (tool-call works) | **NOT enough**: 429 "free usage limit reached" after ~35k tokens today; needs ~6.2M tokens for 432 trajectories |
| `opencode-zen-free/mimo-v2.6-flash-free` | ✅ usable now (tool-call works) | same free limit |
| openrouter `*:free` | ❌ blocked by account privacy setting | n/a |
| `opencode-go/*-free` | ❌ "not available in your country" | n/a |

### Conclusion

The free channels are **intermittent and small-capacity**: opencode-zen-free
returned 429 (limit reached) after ~35k tokens today, while the calibration
needs ~6.2M prompt tokens (432 trajectories × 24 nodes × ~600 prompt tokens).
**The free path alone cannot support the full calibration sweep.**

### Options for the user

1. **Shrink calibration**: run a mini-pilot (e.g. 6 tasks × 1 seed × 3 arms =
   18 trajectories ≈ 260k tokens) within the free channel, only if the free
   quota resets. This gives a rough parameter estimate, NOT the formal run.
2. **Use an in-quota free-plan channel**: `volcengine` (month 100k units) or
   `minimax-code` (4824 credits) — these are "free plan within monthly quota",
   may cover 6.2M tokens but are not strictly $0.
3. **Authorize a small paid budget**: `openrouter` has $8.28 balance; a partial
   calibration within budget is possible but not full.
4. **Defer**: keep calibration as protocol+plan, C1 stays open, paper stays a
   report. Most honest if the user does not want to spend.
