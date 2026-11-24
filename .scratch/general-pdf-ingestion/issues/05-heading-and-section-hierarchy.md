# 05: Heading and section hierarchy

**What to build:** Reconstruct document headings and section paths from layout
and typography. Procedure titles and citations must use the nearest authoritative
section heading rather than body text, footers, or concatenated headings.

**Blocked by:** 03, 04.

**Status:** ready-for-agent

- [x] Recognize numbered headings such as `4.2`, unnumbered section headings, and manufacturer-specific heading styles.
- [x] Infer hierarchy from numbering, font style, position, and document profile hints.
- [x] Associate body blocks and steps with the nearest preceding heading.
- [x] Prevent body sentences, warnings, and footer text from becoming section titles.
- [x] Separate adjacent headings that share a physical page.
- [x] Record stable heading paths for retrieval and citation validation.
- [x] Add tests for multi-section pages, repeated titles, and headings that continue across pages.

## Comments

- 2026-11-24: Current MAGURA section titles are sometimes taken from body text or
  combine multiple headings on one page.

- 2026-11-24: Implemented deterministic heading reconstruction from layout,
  typography, numbering, profile rules, and collected page furniture. Procedure
  blocks and citations now carry the nearest heading path; adjacent and repeated
  headings create distinct sections, and continued subsections retain their
  cross-page ancestry. Parser provenance advanced to `pdf-ingestion-v4`.
