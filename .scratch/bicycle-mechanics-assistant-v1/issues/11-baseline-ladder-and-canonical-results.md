# 11: Baseline ladder and canonical evaluation results

**What to build:** One evaluation command that runs LLM-only, plain RAG, hybrid retrieval, and full-agent configurations under matched conditions and produces canonical local results. Each configuration runs three times, reports every run and spread, grades expected outcomes, and exposes retrieval and answer-generation failures separately.

**Blocked by:** 05, 06, 09, 10.

**Status:** ready-for-agent

- [x] All four configurations use the same frozen questions, provider, prompt budget, decoding settings, and hardware where applicable.
- [x] Retrieval parameters, prompts, and configuration versions are frozen before scored runs.
- [x] Each configuration runs three times at temperature zero with a recorded seed where supported.
- [x] Every run and its spread are reported rather than replacing them with a single best result.
- [x] Specifications are graded by normalized value, range, unit, and required qualifiers; compatibility and statuses are graded exactly.
- [x] Procedure grading uses a reviewable checklist of each expected step and warning, with deterministic application code assigning pass or fail.
- [x] Every supported answer is checked for valid citations and unsupported numbers.
- [x] Recall@5 and MRR are reported independently from answer accuracy.
- [x] Results and latency are tagged by provider, model, configuration, source-pack version, hardware, and runtime.
- [x] Canonical local JSON or SQLite artifacts are always produced, with a small deterministic fixture suite covering all four baselines and repeated runs.
- [x] Evaluation remains operational without requiring LangSmith.

## Comments

- 2026-11-24: Added `zabm evaluation`, the frozen baseline configuration, and
  a five-case deterministic fixture suite. The command runs all four
  configurations three times, retains every run, reports accuracy and latency
  spreads, grades outputs independently, reports Recall@5 and MRR separately,
  and writes a canonical local JSON artifact without importing LangSmith. The
  committed fixture result demonstrates the full CLI path offline.

