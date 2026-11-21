# 02: Specification answer tracer

**What to build:** An end-to-end specification lookup over one audited accepted source. A mechanic can use the CLI to ask for a human-verified fastener or component specification and receive the exact value, unit, applicability conditions, canonical response status, and citation, or `not_found` when the evidence is inadequate.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] One first-party, publicly downloadable accepted source is recorded with its source URL, SHA-256 hash, retrieval date, revision metadata where available, and manifest version.
- [ ] The source can be acquired and ingested without relying on a manually retained PDF, database, index, or earlier generated-data state.
- [ ] At least one exact specification is transcribed, human-verified, and stored as structured evidence with all source-defined applicability conditions.
- [ ] A CLI question for the verified specification returns the exact value, unit, conditions, document, printed page, section, physical page in structured output, and retrieval date.
- [ ] A specification whose required conditions, unit, or human verification is missing returns `not_found` without a substantive value.
- [ ] A number that cannot be matched after unit normalization to the claim's evidence excerpt causes the answer to be rejected.
- [ ] Unverified extraction and retrieval evidence cannot support a specification or compatibility claim.
- [ ] CLI-seam tests cover a supported specification, an unsupported specification, an unmatched number, and a citation-integrity check.

