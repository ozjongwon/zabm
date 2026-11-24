# 12: Ingestion diagnostics, provenance, and rebuild policy

**What to build:** Inspectable ingestion diagnostics and version provenance.
Operators must be able to see why content was classified or rejected, while
rebuilds and frozen results must make parser/profile changes explicit.

**Blocked by:** 01, 03, 06, 07, 08.

**Status:** resolved

- [x] Add a CLI or debug mode that reports page classification, detected columns/languages, headings, candidate steps, and rejection reasons.
- [x] Record parser version, profile version/hash, font-extraction dependencies, source hash, and artifact checksums.
- [x] Make normal ingestion report counts for accepted and rejected procedure candidates by reason.
- [x] Include diagnostic details in JSON reports without logging credentials or unrelated page content.
- [x] Require a parser/profile/version change to produce a new derived-artifact checksum and reviewed rebuild decision.
- [x] State when parser changes require a new source freeze, retrieval smoke run, and complete evaluation rerun.
- [x] Add tests for diagnostics, provenance stability, and explicit rejection reporting.

## Comments

- 2026-11-24: This ticket makes parser behavior observable and prevents silent
  changes to frozen evaluation evidence.

- 2026-11-24: Implemented parser `pdf-ingestion-v11` diagnostics and provenance.
  `zabm ingest --diagnostics` now reports page classification, layout, headings,
  and accepted/rejected candidate steps; normal output groups rejected steps by
  reason. Retrieval catalogs record the source-manifest and per-source hashes,
  while `generated/ingestion-report.json` records diagnostics, artifact
  checksums, and the rebuild decision. Parser/profile/dependency changes fail
  closed until `--rebuild-review` is supplied, then identify the required
  replacement source-pack freeze, retrieval smoke rerun, and complete
  evaluation rerun. Added CLI-seam coverage for diagnostics, rejection counts,
  provenance stability, reviewed rebuilds, and checksum changes. Verified with
  the full test suite, Ruff, and Pyright.
