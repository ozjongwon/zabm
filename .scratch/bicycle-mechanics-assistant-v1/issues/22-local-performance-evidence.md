# 22: Local GPU performance evidence

**What to build:** Produce the local GPU performance evidence required by the v1 acceptance report, or obtain an explicit reviewed revision to an infeasible hardware requirement. Results must be tied to provider, model, hardware, configuration, and frozen-set identity.

**Blocked by:** 16.

**Status:** wontfix

- [ ] Run the full frozen evaluation on a supported local NVIDIA GPU, including the explicit warm-up, and record median and p95 per-item latency.
- [ ] Verify the GPU gate against the unchanged 20-second median and 30-second p95 thresholds.
- [ ] If local GPU hardware is unavailable, request and document an explicit maintainer decision that revises or removes the GPU requirement; record the rationale and effective date.
- [ ] Preserve failed or unavailable evidence in the acceptance report rather than reclassifying it as a pass.

## Comments

- 2026-11-25: Created from ticket 12 review. The current environment has no
  NVIDIA GPU, no Ollama installation or local models, and therefore no
  successful CPU-quantized smoke. The DeepSeek chat smoke succeeded but is not
  CPU-quantized or GPU evidence.
- 2026-11-25: Maintainer review removed the CPU-quantized fallback claim from
  v1. ZABM targets remote OpenAI-compatible APIs or a GPU-backed local Ollama
  service; CPU execution is not part of local reference acceptance.
- 2026-11-26: Attempted the full GPU ladder on `hope.local` (NVIDIA GTX 1060
  6 GB, Ollama 0.40.18) with an 8192-token context. Hermes Q4_0 produced valid
  route/answer output but exceeded 60 seconds on one unbounded response; after
  adding a 1024-token completion bound, llama3.2 Q4_K_M completed most requests
  but eventually returned an invalid routing result. A bounded Hermes rerun was
  still incomplete after 2h32m and approximately 610 requests, so it was
  stopped. No canonical evaluation artifact was produced; the existing
  acceptance report therefore retains a failed GPU latency gate. The temporary
  model-store ACL and Ollama process were removed afterward.
- 2026-11-26: Closed as `wontfix` by maintainer direction. No local GPU
  performance claim is being made from the incomplete attempts. Reopen with
  faster local hardware if this evidence is needed for v1 acceptance.
- 2026-11-26: Superseded by the revised v1 provider requirement in ticket 12
  and ADR 0008. V1 now uses a remote OpenAI-compatible LLM with remote or local
  Ollama embeddings; local GPU performance is no longer required. This ticket
  remains historical evidence for the GTX 1060 attempts.
