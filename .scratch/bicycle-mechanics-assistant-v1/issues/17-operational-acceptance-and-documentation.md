# 17: Operational acceptance and documentation

**What to build:** A complete, reviewable v1 handoff proving the assistant can be installed, rebuilt, tested, evaluated, and exercised from clean workspaces on both development and target systems. Documentation records the architecture, empirical choices, evaluation evidence, safety boundaries, and known limitations.

**Blocked by:** 01, 13, 14, 15, 16, 23, general-pdf-ingestion/12.

**Status:** resolved

- [x] The development installer completes on a clean supported development system and the CLI health command and automated suite pass.
- [x] The target-runtime installer completes on a clean supported target and the CLI, web chat, remote LLM, configured embedding provider, and evidence smoke checks pass.
- [x] The two rebuild commands reconstruct the frozen source pack from empty generated-data directories.
- [x] Acceptance verifies source hashes, page alignment, record counts, frozen dataset counts, and canonical artifact checksums.
- [x] The automated test suite passes at the approved CLI seam.
- [x] All 120 scored items run three times for LLM-only, plain RAG, hybrid retrieval, and full agent with canonical local reports.
- [x] The remote-LLM acceptance run meets every approved accuracy, improvement, confidence-interval, citation, abstention, fabrication, and latency gate.
- [x] Successful LangSmith logging is demonstrated when credentials are available, without becoming a local evaluation dependency.
- [x] CLI and web chat are exercised for supported specifications, compatibility, procedures, citations, clarification, conflicts, not-found, and out-of-scope outcomes.
- [x] The repository contains a quickstart, architecture overview, source-selection audit, evaluation protocol and report, empirical choice record, safety boundaries, and known limitations.
- [x] Documentation explains that a passing evaluation does not establish production safety, domain-wide coverage, or current manufacturer guidance.

## Comments

- 2026-11-24: Added `general-pdf-ingestion/12` as a blocker because the final
  operational handoff depends on stable, documented ingestion provenance.
- 2026-11-26: All blockers are resolved, including ticket 23's canonical remote
  acceptance evidence. Selected as the next agent ticket.
- 2026-11-26: Added `docs/operational-handoff.md` as the v1 review entry point.
  It records the quickstart, architecture, source-selection audit, reproducible
  rebuild evidence, evaluation protocol and accepted results, empirical
  choices, CLI/web outcome matrix, observability, safety boundaries, and known
  limitations. The web acceptance table now includes a complete procedure.
  Two independent clean ingestion runs reproduced the same 149-page alignment,
  record counts, empty validation issues, artifact bytes, and checksums.
  Health, Ruff lint and format checks, and Pyright pass; the full suite reports
  295 passed; and `zabm acceptance` passes every gate with the canonical
  checksums unchanged.

