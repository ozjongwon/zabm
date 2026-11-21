# 11: Baseline ladder and canonical evaluation results

**What to build:** One evaluation command that runs LLM-only, plain RAG, hybrid retrieval, and full-agent configurations under matched conditions and produces canonical local results. Each configuration runs three times, reports every run and spread, grades expected outcomes, and exposes retrieval and answer-generation failures separately.

**Blocked by:** 05, 06, 09, 10.

**Status:** ready-for-agent

- [ ] All four configurations use the same frozen questions, provider, prompt budget, decoding settings, and hardware where applicable.
- [ ] Retrieval parameters, prompts, and configuration versions are frozen before scored runs.
- [ ] Each configuration runs three times at temperature zero with a recorded seed where supported.
- [ ] Every run and its spread are reported rather than replacing them with a single best run.
- [ ] Specifications are graded by normalized value, range, unit, and required qualifiers; compatibility and statuses are graded exactly.
- [ ] Procedure grading uses a reviewable checklist of each expected step and warning, with deterministic application code assigning pass or fail.
- [ ] Every supported answer is checked for valid citations and unsupported numbers.
- [ ] Recall@5 and MRR are reported independently from answer accuracy.
- [ ] Results and latency are tagged by provider, model, configuration, source-pack version, hardware, and runtime.
- [ ] Canonical local JSON or SQLite artifacts are always produced, with a small deterministic fixture suite covering all four baselines and repeated runs.
- [ ] Evaluation remains operational without requiring LangSmith.

