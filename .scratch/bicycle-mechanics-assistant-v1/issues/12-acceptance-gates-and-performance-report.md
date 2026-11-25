# 12: Acceptance gates and performance report

**What to build:** A scored acceptance report proving whether the full agent meets the v1 accuracy, improvement, abstention, citation, fabrication, and local performance gates. The report preserves per-baseline, per-run, hardware, and runtime evidence and uses the approved paired-bootstrap methodology.

**Blocked by:** None. Ticket 20 resolved on 2026-11-26.

**Status:** ready-for-human

- [x] The 120-item median run reaches at least 90% overall answer accuracy. Current run: 98.33%, passed.
- [x] The full agent improves overall accuracy over both LLM-only and plain RAG by at least 10 percentage points.
- [x] The fixed-seed paired-bootstrap 95% confidence interval for each required baseline difference is wholly above zero.
- [x] Citation validity is at least 95%.
- [x] Correct abstention is at least 95% across not-found, conflicting-evidence, and out-of-scope items. Current run: 100.00%, passed.
- [x] Fabricated numeric values are zero across all three runs.
- [ ] Local GPU latency has a median of 20 seconds or less and a p95 of 30 seconds or less over the frozen evaluation set, excluding warm-up. No local NVIDIA GPU was available for this run.
- [x] The report includes every baseline, provider, run, hardware, configuration version, latency, retrieval metric, and gate result.
- [x] A failed gate is reported as a failure with diagnostic evidence; no threshold or result is silently changed.

## Comments

- 2026-11-24: Added `general-pdf-ingestion/12` as a blocker. Accuracy and
  procedure acceptance must run after the generalized ingestion and parser
  provenance work is complete.
- 2026-11-24: Added `zabm acceptance`, fixed-seed item-paired bootstrap
  confidence intervals, per-scored-item latency after an explicit warm-up,
  hardware/GPU evidence, CPU-quantized smoke evidence, and
  `data/evaluation/acceptance-report-v1.json`. Regenerated the source and
  evaluation freezes through a reviewed rebuild and ran the full 120-item,
  four-baseline, three-run evaluation. Improvement, paired confidence
  intervals, citation validity, and fabrication gates pass; accuracy (30.83%),
  abstention (56.67%), local GPU evidence, and CPU-quantized smoke remain
  failed and are preserved in the report.
- 2026-11-25: Fixed the `during 50/200 Hour Service` specification regression
  and generalized matching for plurals, fastener/caliper synonyms, omitted
  descriptive tokens, passive compatibility wording, and abbreviated component
  clarification. Regenerated the 120-item ladder and acceptance report against
  the unchanged frozen source pack. Full-agent median accuracy is now 62.50%,
  correct abstention is 60.00%, citation validity is 100%, and fabricated
  numeric values remain zero. All seven out-of-scope items now abstain
  correctly. The DeepSeek chat provider smoke passed and is recorded in
  `data/evaluation/deepseek-provider-smoke-v1.json`.
- 2026-11-25: A full DeepSeek ladder was started with the frozen set but was
  stopped after 20 minutes before it produced a complete artifact; it is not
  used as evidence. Ollama is not installed and has no local models, so the
  requested DeepSeek/Ollama combination and CPU-quantized smoke could not be
  run. No local NVIDIA GPU is available.
- 2026-11-25: Human triage is required for evidence gaps exposed by the
  remaining failures. All eight conflicting-evidence items expect top-cap or
  hose-barb conflicts, but the verified specification evidence contains no
  corresponding claims. Compatibility items 012-015 expect composite-rail or
  seatpost-diameter outcomes with no matching verified compatibility rule.
  The retrieval catalog also exposes only two complete procedures, so most
  expected procedure answers cannot be sourced. Accuracy, abstention, GPU
  latency, and CPU-quantized smoke gates therefore remain open; no threshold
  or failed result was changed.
- 2026-11-25: Split the remaining blockers into ticket 20 for evidence and
  evaluation reconciliation, ticket 21 for complete procedure coverage, and
  ticket 22 for CPU-quantized and GPU performance evidence. Ticket 12 remains
  the final acceptance gate and is blocked until those tickets resolve.
- 2026-11-25: Maintainer review removed the CPU-quantized smoke gate. The
  local reference deployment is GPU-only; remote provider comparison and
  local Ollama smoke coverage do not establish a CPU performance claim.
- 2026-11-26: Re-scored the post-ticket-20 evaluation into a temporary
  acceptance report. Accuracy, both improvement gates, citation validity,
  abstention, and fabrication all pass. Correct abstention is 100% in every
  refusal category. The only failed gate remains local GPU latency because no
  NVIDIA GPU is available and no provider-backed latency run could be recorded.
