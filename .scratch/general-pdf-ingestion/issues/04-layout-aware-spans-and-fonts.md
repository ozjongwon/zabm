# 04: Layout-aware spans, columns, languages, and fonts

**What to build:** Layout-aware text extraction that preserves font metadata,
page coordinates, line spans, column regions, and language regions. Procedure
text must be read in source order without merging unrelated columns.

**Blocked by:** 01, 02.

**Status:** resolved

- [x] Preserve font name, size, weight/style hints, page coordinates, and line/span IDs during extraction.
- [x] Detect column bands and assemble text column-by-column in source reading order.
- [x] Detect multilingual regions and select the configured or requested language without merging languages.
- [x] Keep each text span tied to its original page and bounding box.
- [x] Add pinned PDF font/encoding support, including `fonttools`, and verify the lock files.
- [x] Normalize glyph ligatures, soft hyphens, tabs, and broken words without losing the original source span.
- [x] Add fixtures for two-column and multilingual layouts and assert no step crosses an unrelated column boundary.

## Comments

- 2026-11-24: The MAGURA Gustav pages mix columns at several x positions, while
  MT A2 contains a large multilingual sheet. Current x < 300 extraction merges
  unrelated content.

- 2026-11-24: Implemented layout-aware extraction through the existing CLI
  ingestion seam. Retrieval pages now retain ordered spans with raw and
  normalized text, stable line/span IDs, font metadata, column and language
  ownership, normalized boxes, and page-point boxes. Added profile-driven and
  automatic column bands, configured and limited automatic language isolation,
  `--language` selection, hyphen/ligature/soft-hyphen normalization, and
  `fonttools==4.68.0` with locked hashes and parser provenance. Cross-layout
  tests now pass for multilingual pages, broken words, styled fonts, and
  automatically detected left/right columns.
