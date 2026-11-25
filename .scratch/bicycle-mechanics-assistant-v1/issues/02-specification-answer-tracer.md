# 02: Specification answer tracer

**What to build:** An end-to-end specification lookup over one audited accepted source. A mechanic can use the CLI to ask for a human-verified fastener or component specification and receive the exact value, unit, applicability conditions, canonical response status, and citation, or `not_found` when the evidence is inadequate.

**Blocked by:** 01.

**Status:** resolved

- [x] One first-party, publicly downloadable accepted source is recorded with its source URL, SHA-256 hash, retrieval date, revision metadata where available, and manifest version.
- [x] The source can be acquired and ingested without relying on a manually retained PDF, database, index, or earlier generated-data state.
- [x] At least one exact specification is transcribed, human-verified, and stored as structured evidence with all source-defined applicability conditions.
- [x] A CLI question for the verified specification returns the exact value, unit, conditions, document, printed page, section, physical page in structured output, and retrieval date.
- [x] A specification whose required conditions, unit, or human verification is missing returns `not_found` without a substantive value.
- [x] A number that cannot be matched after unit normalization to the claim's evidence excerpt causes the answer to be rejected.
- [x] Unverified extraction and retrieval evidence cannot support a specification or compatibility claim.
- [x] CLI-seam tests cover a supported specification, an unsupported specification, an unmatched number, and a citation-integrity check.

## Comments

- 2026-11-23: Added the pinned SRAM RockShox Reverb Rev C source, clean-state
  `download` and `ingest` commands, a human-verified Standard Remote clamp
  torque record, and the specification answer path. Downloaded PDFs are stored
  under the configured data directory's `sources/` directory. CLI tests cover
  supported and unsupported specifications, missing conditions/unit/verification,
  unmatched numeric fields, wrong units, and citation integrity. A live clean
  rebuild returned the page-36 specification with full provenance; `make verify`
  passes with 13 tests.

