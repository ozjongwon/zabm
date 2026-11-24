# 12: Acceptance gates and performance report

**What to build:** A scored acceptance report proving whether the full agent meets the v1 accuracy, improvement, abstention, citation, fabrication, and local performance gates. The report preserves per-baseline, per-run, hardware, and runtime evidence and uses the approved paired-bootstrap methodology.

**Blocked by:** 11, general-pdf-ingestion/12.

**Status:** ready-for-agent

- [ ] The 120-item median run reaches at least 90% overall answer accuracy. Current run: 30.83%, failed.
- [x] The full agent improves overall accuracy over both LLM-only and plain RAG by at least 10 percentage points.
- [x] The fixed-seed paired-bootstrap 95% confidence interval for each required baseline difference is wholly above zero.
- [x] Citation validity is at least 95%.
- [ ] Correct abstention is at least 95% across not-found, conflicting-evidence, and out-of-scope items. Current run: 56.67%, failed.
- [x] Fabricated numeric values are zero across all three runs.
- [ ] Local GPU latency has a median of 20 seconds or less and a p95 of 30 seconds or less over the frozen evaluation set, excluding warm-up. No local NVIDIA GPU was available for this run.
- [ ] CPU-quantized operation has a successful smoke run and documented performance without being required to meet the GPU threshold.
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
