# 04: Procedure answer tracer

**What to build:** An end-to-end service-procedure answer over complete retrieval evidence. A mechanic can ask for an identified maintenance task and receive the complete ordered steps and all attached warnings with citations, while evidence that may be missing any required step is refused as `not_found`.

**Blocked by:** 02.

**Status:** resolved

- [x] Ingestion preserves page boundaries, heading hierarchy, tables, warnings, and procedure order for at least one accepted source.
- [x] A retrieval-evidence section is considered eligible only when it establishes a complete source-defined service procedure.
- [x] A complete procedure returns every ordered step and attached warning with document, printed page, section, and retrieval-date citations.
- [x] A truncated or uncertain procedure returns `not_found`, explains that only partial evidence was available, and includes no procedure steps.
- [x] Structured specifications or compatibility rows cannot substitute for missing procedure evidence.
- [x] The CLI can inspect the retrieval evidence used for a procedure response.
- [x] CLI-seam tests cover a complete procedure, its warnings, a truncated section, and citation integrity for every step.

## Comments

- 2026-11-23: Added a page-structured retrieval catalog, ordered procedure
  extraction with per-step citations and attached warnings, completeness gates,
  canonical procedure responses, and the `zabm evidence` inspection command.
  The pinned SRAM source ingests as 40 retrieval pages with preserved table and
  warning blocks. A live query for "hose sizing and remote installation"
  returns all five ordered steps across printed pages 21-22 with three attached
  notices. CLI-seam tests cover complete, truncated, structured-evidence
  substitution, and retrieval-inspection behavior. `make verify` passes.
- 2026-11-23: Code review hardened completeness to require source-defined end
  evidence positioned after the final numbered step, added imperative-task
  routing, retained warnings that precede step 1, grouped repeated titles by
  contiguous section identity, and tightened table inference. `make verify`
  passes with 31 tests.

