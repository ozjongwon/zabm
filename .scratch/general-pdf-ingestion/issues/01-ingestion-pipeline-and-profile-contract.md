# 01: Ingestion pipeline and profile contract

**What to build:** A staged, deterministic PDF-ingestion contract with versioned
document profiles. Shared extraction stages must operate through explicit typed
boundaries, while unusual layouts receive declarative profile overrides instead
of manufacturer-specific branches.

**Blocked by:** None.

**Status:** ready-for-agent

- [x] Define typed stage contracts for page/block classification, layout spans, heading hierarchy, procedure candidates, completeness, and evidence verification.
- [x] Define a versioned profile schema for layout, language, heading, table, figure, end-boundary, and action-alias overrides.
- [x] Resolve profile selection deterministically from source metadata or an explicit manifest reference.
- [x] Include parser version, profile version, and profile SHA-256 in every derived retrieval catalog.
- [x] Reject unknown profile versions and invalid profile overrides with actionable errors.
- [x] Preserve the existing CLI ingestion seam and fail-closed behavior.
- [x] Add CLI-seam tests for profile selection, invalid profiles, and stable parser/profile provenance.

## Comments

- 2026-11-24: Created from the MAGURA procedure-catalog audit. The contract is
  the foundation for all other general ingestion tickets.

- 2026-11-24: Implemented typed ingestion-stage boundaries and Pydantic
  contracts for all requested artifacts. Added a versioned profile manifest,
  deterministic explicit/metadata selection, canonical profile and manifest
  hashes, parser provenance in reports and retrieval catalogs, safe
  section-boundary review validation, and CLI-seam tests for selection,
  precedence, unknown versions, invalid overrides, and fail-closed writes.
