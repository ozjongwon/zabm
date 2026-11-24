# 12: Ingestion diagnostics, provenance, and rebuild policy

**What to build:** Inspectable ingestion diagnostics and version provenance.
Operators must be able to see why content was classified or rejected, while
rebuilds and frozen results must make parser/profile changes explicit.

**Blocked by:** 01, 03, 06, 07, 08.

**Status:** ready-for-agent

- [ ] Add a CLI or debug mode that reports page classification, detected columns/languages, headings, candidate steps, and rejection reasons.
- [ ] Record parser version, profile version/hash, font-extraction dependencies, source hash, and artifact checksums.
- [ ] Make normal ingestion report counts for accepted and rejected procedure candidates by reason.
- [ ] Include diagnostic details in JSON reports without logging credentials or unrelated page content.
- [ ] Require a parser/profile/version change to produce a new derived-artifact checksum and reviewed rebuild decision.
- [ ] State when parser changes require a new source freeze, retrieval smoke run, and complete evaluation rerun.
- [ ] Add tests for diagnostics, provenance stability, and explicit rejection reporting.

## Comments

- 2026-11-24: This ticket makes parser behavior observable and prevents silent
  changes to frozen evaluation evidence.
