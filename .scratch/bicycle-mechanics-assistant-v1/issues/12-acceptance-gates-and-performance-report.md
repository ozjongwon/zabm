# 12: Acceptance gates and performance report

**What to build:** A scored acceptance report proving whether the full agent meets the v1 accuracy, improvement, abstention, citation, fabrication, and local performance gates. The report preserves per-baseline, per-run, hardware, and runtime evidence and uses the approved paired-bootstrap methodology.

**Blocked by:** 11.

**Status:** ready-for-agent

- [ ] The 120-item median run reaches at least 90% overall answer accuracy.
- [ ] The full agent improves overall accuracy over both LLM-only and plain RAG by at least 10 percentage points.
- [ ] The fixed-seed paired-bootstrap 95% confidence interval for each required baseline difference is wholly above zero.
- [ ] Citation validity is at least 95%.
- [ ] Correct abstention is at least 95% across not-found, conflicting-evidence, and out-of-scope items.
- [ ] Fabricated numeric values are zero across all three runs.
- [ ] Local GPU latency has a median of 20 seconds or less and a p95 of 30 seconds or less over the frozen evaluation set, excluding warm-up.
- [ ] CPU-quantized operation has a successful smoke run and documented performance without being required to meet the GPU threshold.
- [ ] The report includes every baseline, provider, run, hardware, configuration version, latency, retrieval metric, and gate result.
- [ ] A failed gate is reported as a failure with diagnostic evidence; no threshold or result is silently changed.
