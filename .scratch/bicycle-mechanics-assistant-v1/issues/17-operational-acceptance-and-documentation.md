# 17: Operational acceptance and documentation

**What to build:** A complete, reviewable v1 handoff proving the assistant can be installed, rebuilt, tested, evaluated, and exercised from clean workspaces on both development and target systems. Documentation records the architecture, empirical choices, evaluation evidence, safety boundaries, and known limitations.

**Blocked by:** 01, 13, 14, 15, 16, 23, general-pdf-ingestion/12.

**Status:** ready-for-agent

- [ ] The development installer completes on a clean supported development system and the CLI health command and automated suite pass.
- [ ] The target-runtime installer completes on a clean supported target and the CLI, web chat, remote LLM, configured embedding provider, and evidence smoke checks pass.
- [ ] The two rebuild commands reconstruct the frozen source pack from empty generated-data directories.
- [ ] Acceptance verifies source hashes, page alignment, record counts, frozen dataset counts, and canonical artifact checksums.
- [ ] The automated test suite passes at the approved CLI seam.
- [ ] All 120 scored items run three times for LLM-only, plain RAG, hybrid retrieval, and full agent with canonical local reports.
- [ ] The remote-LLM acceptance run meets every approved accuracy, improvement, confidence-interval, citation, abstention, fabrication, and latency gate.
- [ ] Successful LangSmith logging is demonstrated when credentials are available, without becoming a local evaluation dependency.
- [ ] CLI and web chat are exercised for supported specifications, compatibility, procedures, citations, clarification, conflicts, not-found, and out-of-scope outcomes.
- [ ] The repository contains a quickstart, architecture overview, source-selection audit, evaluation protocol and report, empirical choice record, safety boundaries, and known limitations.
- [ ] Documentation explains that a passing evaluation does not establish production safety, domain-wide coverage, or current manufacturer guidance.

## Comments

- 2026-11-24: Added `general-pdf-ingestion/12` as a blocker because the final
  operational handoff depends on stable, documented ingestion provenance.

