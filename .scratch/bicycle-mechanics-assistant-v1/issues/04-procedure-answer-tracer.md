# 04: Procedure answer tracer

**What to build:** An end-to-end service-procedure answer over complete retrieval evidence. A mechanic can ask for an identified maintenance task and receive the complete ordered steps and all attached warnings with citations, while evidence that may be missing any required step is refused as `not_found`.

**Blocked by:** 02.

**Status:** ready-for-agent

- [ ] Ingestion preserves page boundaries, heading hierarchy, tables, warnings, and procedure order for at least one accepted source.
- [ ] A retrieval-evidence section is considered eligible only when it establishes a complete source-defined service procedure.
- [ ] A complete procedure returns every ordered step and attached warning with document, printed page, section, and retrieval-date citations.
- [ ] A truncated or uncertain procedure returns `not_found`, explains that only partial evidence was available, and includes no procedure steps.
- [ ] Structured specifications or compatibility rows cannot substitute for missing procedure evidence.
- [ ] The CLI can inspect the retrieval evidence used for a procedure response.
- [ ] CLI-seam tests cover a complete procedure, its warnings, a truncated section, and citation integrity for every step.

