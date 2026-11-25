# 08: Source-span evidence and citation verification

**What to build:** Procedure and warning evidence that references exact stored
source spans rather than reconstructed strings. All citations must resolve to
the same document, physical page, printed page, section, and bounding-box/span
source.

**Blocked by:** 04, 05.

**Status:** resolved

- [x] Store stable span identifiers and bounding boxes for accepted step and warning text.
- [x] Build excerpts from the stored source spans instead of concatenating arbitrary nearby fragments.
- [x] Normalize ligatures, tabs, soft hyphens, spacing, and line wraps for comparison while retaining original text.
- [x] Reject a step when its excerpt does not resolve exactly after approved normalization.
- [x] Validate printed and physical page locators independently.
- [x] Include span provenance in the retrieval catalog without exposing it in user-facing answers unless requested.
- [x] Add fixtures for multi-column joins, broken words, ligatures, and excerpt mismatches.

## Comments

- 2026-11-24: Current MAGURA candidates repeatedly fail because reconstructed
  step text is not present in the cited source page.

- 2026-11-24: Implemented source-span evidence in parser `pdf-ingestion-v7`.
  Stored steps and warnings now carry their document, physical and printed page,
  section, heading path, span IDs, normalized and physical boxes, language, and
  raw and normalized text. Excerpts are built only from those spans; raw text
  retains ligatures, soft hyphens, and line breaks while comparison uses the
  shared PDF normalization. Ingestion and retrieval reject only the step whose
  excerpt, locator, page, section, reading order, language, box, or text no
  longer resolves, while `evidence --json` can expose the provenance and
  ordinary answers omit it. Tests cover multi-column joins, broken words,
  ligatures, document/page mismatches, and excerpt tampering.
