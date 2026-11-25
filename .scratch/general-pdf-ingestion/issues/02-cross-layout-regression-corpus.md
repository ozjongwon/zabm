# 02: Cross-layout regression corpus

**What to build:** A small deterministic corpus of PDF layouts and expected
ingestion outcomes that exercises shared parser behavior without overfitting to
MAGURA or RockShox. Tests run through the CLI ingestion and evidence seams.

**Blocked by:** 01.

**Status:** resolved

- [x] Cover single-column procedures, two-column procedures, and multilingual multi-column pages.
- [x] Cover table-of-contents, torque-table, contact-information, legal, cover, and figure-only pages.
- [x] Cover repeated headers, warnings, page numbers, figure callouts, and broken words.
- [x] Cover complete procedures, missing first or final steps, duplicate numbering, and ambiguous continuations.
- [x] Assert that disallowed pages produce no procedure candidates.
- [x] Assert accepted procedures preserve order, warnings, citations, and source-defined boundaries.
- [x] Include at least one fixture whose behavior requires a declarative document profile.
- [x] Keep expected outputs independent of parser internals and stable across repeated ingestion.

## Comments

- 2026-11-24: This corpus should be built alongside parser changes so each
  extraction rule has a red-capable CLI regression case.

- 2026-11-24: Added the deterministic `cross-layout-v1` corpus under
  `tests/fixtures/cross-layout-v1/`, generated at test time from declarative
  page/line data and a versioned profile manifest. The cases run through
  `zabm ingest`, `zabm evidence`, and `zabm ask`. Current parser gaps for
  disallowed pages and layout/multilingual spans are strict expected failures
  tied to tickets 03 and 04; accepted multi-page and profile-driven cases,
  fail-closed completeness cases, PDF determinism, and byte-stable re-ingestion
  pass now.
