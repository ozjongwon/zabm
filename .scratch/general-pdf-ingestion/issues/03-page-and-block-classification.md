# 03: Page and block classification

**What to build:** Deterministic classification of PDF pages and blocks before
procedure extraction. Contents, index, cover, contact, legal, advertisement,
pure-table, figure, warning, heading, paragraph, and procedural-step content
must be distinguishable.

**Blocked by:** 01, 02.

**Status:** resolved

- [x] Classify contents/index pages using heading text, dotted leaders, section-number density, and page-reference patterns.
- [x] Classify table blocks before step extraction and prevent table rows from becoming procedure steps.
- [x] Classify contact, legal, warranty, cover, and navigation pages as non-procedure content.
- [x] Classify figure and callout regions separately from prose steps.
- [x] Record classification confidence or explicit uncertainty and fail closed when a page cannot be classified safely.
- [x] Preserve page furniture for retrieval when useful while excluding it from procedure extraction.
- [x] Add regression tests for all classifications, including the current MAGURA false positives.

## Comments

- 2026-11-24: Current failures include Gustav Pro contents page 2 and tightening
  torque page 22 being interpreted as procedures.

- 2026-11-24: Implemented typed deterministic page/block classification before
  procedure extraction, persisted classification confidence and uncertainty,
  filtered tables, figures, navigation, front matter, and page furniture, and
  added CLI regression coverage including Gustav-style contents and torque
  layouts. Parser provenance advanced to `pdf-ingestion-v2`.
