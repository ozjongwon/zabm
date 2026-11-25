# 22: Local CPU-quantized and GPU performance evidence

**What to build:** Produce the local performance evidence required by the v1 acceptance report, or obtain an explicit reviewed revision to an infeasible hardware requirement. CPU-quantized and GPU results must remain distinguishable and tied to provider, model, hardware, configuration, and frozen-set identity.

**Blocked by:** 16.

**Status:** ready-for-human

- [ ] Run a successful CPU-quantized provider smoke with a local OpenAI-compatible runtime and record hardware, model, quantization, configuration, latency, and frozen-set identity.
- [ ] Pass the successful CPU smoke report to `zabm acceptance` and verify the CPU-quantized gate.
- [ ] Run the full frozen evaluation on a supported local NVIDIA GPU, including the explicit warm-up, and record median and p95 per-item latency.
- [ ] Verify the GPU gate against the unchanged 20-second median and 30-second p95 thresholds.
- [ ] If local GPU hardware is unavailable, request and document an explicit maintainer decision that revises or removes the GPU requirement; record the rationale and effective date.
- [ ] Preserve failed or unavailable evidence in the acceptance report rather than reclassifying it as a pass.

## Comments

- 2026-11-25: Created from ticket 12 review. The current environment has no
  NVIDIA GPU, no Ollama installation or local models, and therefore no
  successful CPU-quantized smoke. The DeepSeek chat smoke succeeded but is not
  CPU-quantized or GPU evidence.
