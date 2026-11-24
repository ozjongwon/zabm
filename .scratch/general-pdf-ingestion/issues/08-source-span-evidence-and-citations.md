# 08: Source-span evidence and citation verification

**What to build:** Procedure and warning evidence that references exact stored
source spans rather than reconstructed strings. All citations must resolve to
the same document, physical page, printed page, section, and bounding-box/span
source.

**Blocked by:** 04, 05.

**Status:** ready-for-agent

- [ ] Store stable span identifiers and bounding boxes for accepted step and warning text.
- [ ] Build excerpts from the stored source spans instead of concatenating arbitrary nearby fragments.
- [ ] Normalize ligatures, tabs, soft hyphens, spacing, and line wraps for comparison while retaining original text.
- [ ] Reject a step when its excerpt does not resolve exactly after approved normalization.
- [ ] Validate printed and physical page locators independently.
- [ ] Include span provenance in the retrieval catalog without exposing it in user-facing answers unless requested.
- [ ] Add fixtures for multi-column joins, broken words, ligatures, and excerpt mismatches.

## Comments

- 2026-11-24: Current MAGURA candidates repeatedly fail because reconstructed
  step text is not present in the cited source page.
