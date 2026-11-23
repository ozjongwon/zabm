# 07: Reproducible multi-source pack build

**What to build:** A candidate source pack of 4-8 accepted manufacturer documents from at least two manufacturers, plus reproducible acquisition and ingestion workflows. A maintainer can rebuild the candidate pack from a clean generated-data state, see provenance and validation results, and have changed source files rejected before they enter the derived stores.

**Blocked by:** 02, 03, 04.

**Status:** ready-for-agent

- [x] The candidate pack contains 4-8 first-party, public, directly downloadable documents from at least two manufacturers.
- [x] The candidate pack has enough source depth for specification, compatibility, complete procedure, not-found, conflict, and realistic refusal cases.
- [x] The source manifest pins every source URL, SHA-256 hash, retrieval date, revision or model-year metadata where available, and manifest version.
- [x] One documented acquisition command bootstraps the environment, downloads every manifest source, verifies hashes, and reports provenance.
- [x] One documented ingestion command parses, verifies, extracts, indexes, and validates all derived stores from verified downloads.
- [x] Both workflows run from a clean generated-data state without manually retained PDFs, databases, indexes, caches, or earlier workspace state.
- [x] Ingestion preserves and validates page boundaries, heading paths, table structure, warnings, and procedure order.
- [x] A checksum mismatch fails the normal rebuild before the changed source can enter an evidence store.
- [x] Rebuild validation reports source counts, page alignment, record counts, and canonical artifact checksums.
- [x] CLI-seam tests cover successful clean rebuild, checksum mismatch, repeatable rebuild, provenance output, and validation reports.

## Comments

- 2026-11-23: Added a six-document candidate pack from SRAM, RockShox, and
  MAGURA. The documents cover exact specifications and conditions,
  compatibility/tool tables, complete and partial procedures, warnings,
  adjacent models, and cross-manufacturer refusal cases.
- 2026-11-23: Added acquisition and ingestion wrappers, source preflight
  verification, download provenance, manufacturer counts, page-alignment
  diagnostics, table/warning/procedure counts, and canonical artifact
  checksums. Source or build checksum mismatches fail before derived evidence is
  written.
- 2026-11-23: A live clean rebuild downloaded and verified all six sources and
  ingested 149 aligned pages, 451 table rows, 21 warnings, 55 candidate
  procedures, and two complete procedures. Repeated clean builds produced
  identical artifact hashes:
  `specifications.json` `b5cb336ed5880d115e7fa647299c0f078d19af352ec54c18c27487600ab7d461`,
  `compatibility.json` `6ce227a8365702e105d0f427864a8411119a7e9a06912a0853e0f730ab59f86a`,
  and `retrieval.json` `efb65ec68245e93170be488ec7765bb59e80792dda839a3e37d2dee4b332355e`.
- 2026-11-23: `make verify` passes with 59 tests, including clean multi-source
  rebuild, download and ingestion hash mismatch, repeatable artifact hashes,
  provenance, validation-report coverage, and executable build wrappers.

