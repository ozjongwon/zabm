# 21: Complete procedure evidence coverage

**What to build:** Ensure every procedure item in the frozen evaluation resolves to complete source-defined procedure evidence or to an explicit partial-evidence refusal with the expected diagnostic. Procedure extraction must remain source-bounded and must not synthesize or complete missing steps.

**Blocked by:** 09, 10, general-pdf-ingestion/12.

**Status:** ready-for-agent

- [ ] Inventory all 27 procedure items and the four not-found items whose expected diagnostic is `only partial procedure evidence was available`.
- [ ] Classify each failure as routing, retrieval, procedure-boundary extraction, step extraction, warning extraction, or missing source evidence.
- [ ] Fix extraction or matching defects where a complete source section exists, preserving page and section provenance and the source-defined end boundary.
- [ ] Return `not_found` with the partial-evidence diagnostic where the source does not contain a complete procedure; do not return partial steps as supported.
- [ ] Add CLI-seam tests for newly supported procedures, partial-evidence refusals, and any routing corrections.
- [ ] Verify that complete procedures retain ordered steps, attached warnings, and citations.
- [ ] Regenerate generated retrieval data and the complete evaluation artifact against the unchanged frozen evaluation set.
- [ ] Record remaining unsupported procedure items for ticket 20 or a reviewed evidence update rather than changing expectations silently.

## Comments

- 2026-11-25: Created from ticket 12 review. The current retrieval catalog
  exposes only two complete procedures, while the frozen set contains 27
  procedure items and four expected partial-evidence refusals.
