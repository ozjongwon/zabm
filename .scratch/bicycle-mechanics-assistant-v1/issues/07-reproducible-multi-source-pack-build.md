# 07: Reproducible multi-source pack build

**What to build:** A candidate source pack of 4-8 accepted manufacturer documents from at least two manufacturers, plus reproducible acquisition and ingestion workflows. A maintainer can rebuild the candidate pack from a clean generated-data state, see provenance and validation results, and have changed source files rejected before they enter the derived stores.

**Blocked by:** 02, 03, 04.

**Status:** ready-for-agent

- [ ] The candidate pack contains 4-8 first-party, public, directly downloadable documents from at least two manufacturers.
- [ ] The candidate pack has enough source depth for specification, compatibility, complete procedure, not-found, conflict, and realistic refusal cases.
- [ ] The source manifest pins every source URL, SHA-256 hash, retrieval date, revision or model-year metadata where available, and manifest version.
- [ ] One documented acquisition command bootstraps the environment, downloads every manifest source, verifies hashes, and reports provenance.
- [ ] One documented ingestion command parses, verifies, extracts, indexes, and validates all derived stores from verified downloads.
- [ ] Both workflows run from a clean generated-data state without manually retained PDFs, databases, indexes, caches, or earlier workspace state.
- [ ] Ingestion preserves and validates page boundaries, heading paths, table structure, warnings, and procedure order.
- [ ] A checksum mismatch fails the normal rebuild before the changed source can enter an evidence store.
- [ ] Rebuild validation reports source counts, page alignment, record counts, and canonical artifact checksums.
- [ ] CLI-seam tests cover successful clean rebuild, checksum mismatch, repeatable rebuild, provenance output, and validation reports.

