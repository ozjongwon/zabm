# 21: Complete procedure evidence coverage

**What to build:** Ensure every procedure item in the frozen evaluation resolves to complete source-defined procedure evidence or to an explicit partial-evidence refusal with the expected diagnostic. Procedure extraction must remain source-bounded and must not synthesize or complete missing steps.

**Blocked by:** 09, 10, general-pdf-ingestion/12.

**Status:** resolved

- [x] Inventory all 27 procedure items and the four not-found items whose expected diagnostic is `only partial procedure evidence was available`.
- [x] Classify each failure as routing, retrieval, procedure-boundary extraction, step extraction, warning extraction, or missing source evidence.
- [x] Fix extraction or matching defects where a complete source section exists, preserving page and section provenance and the source-defined end boundary.
- [x] Return `not_found` with the partial-evidence diagnostic where the source does not contain a complete procedure; do not return partial steps as supported.
- [x] Add CLI-seam tests for newly supported procedures, partial-evidence refusals, and any routing corrections.
- [x] Verify that complete procedures retain ordered steps, attached warnings, and citations.
- [x] Regenerate generated retrieval data and the complete evaluation artifact against the unchanged frozen evaluation set.
- [x] Record remaining unsupported procedure items for ticket 20 or a reviewed evidence update rather than changing expectations silently.

## Comments

- 2026-11-25: Created from ticket 12 review. The current retrieval catalog
  exposes only two complete procedures, while the frozen set contains 27
  procedure items and four expected partial-evidence refusals.
- 2026-11-25: Resolved procedure coverage. Standalone number markers, multiline
  procedure pages containing navigation notes, continuation-page headings, and
  explicit end markers are now handled without turning partial sections into
  supported instructions. Routing accepts explicit steps/procedure wording,
  reviewed action aliases, source-title model context, and unambiguous
  content-overlap requests; adjacent-model requests still refuse.
- 2026-11-25: The rebuilt retrieval catalog contains the complete Hose Sizing
  and Remote Installation and Test Function procedures with ordered steps,
  attached notices, physical page citations, and source-defined end boundaries.
  All 27 frozen procedure items and all four required partial-evidence
  refusals pass. The complete evaluation remains tied to the unchanged frozen
  evaluation set and now reports full-agent median accuracy of 88.33%, up from
  62.50%. Remaining evaluation failures are compatibility/conflict evidence
  gaps outside this ticket; no additional procedure evidence gap remains.

## Coverage inventory

| Item | Expected outcome | Original failure class | Resolution |
| --- | --- | --- | --- |
| procedure-001 | supported | routing, step extraction | Explicit procedure routing; split-marker extraction and wrapped prose |
| procedure-002 | supported | matching, step extraction | Content-overlap fallback; split-marker extraction |
| procedure-003 | supported | routing, step extraction | Procedure routing; split-marker Test Function extraction |
| procedure-004 | supported | matching | Reviewed action vocabulary and source-title context |
| procedure-005 | not_found | missing source evidence | Source is a tool-compatibility table, not a service procedure |
| procedure-006 | not_found | missing source evidence, boundary | Partial MT A2 section; explicit partial-evidence refusal |
| procedure-007 | not_found | missing source evidence, step extraction | Unnumbered GUSTAV instructions; explicit partial-evidence refusal |
| procedure-008 | not_found | missing source evidence, boundary | Split Reba section lacks a complete accepted sequence; partial refusal |
| procedure-009 | supported | matching, step extraction | Sizing/install normalization; split-marker extraction |
| procedure-010 | supported | routing, step extraction | Explicit procedure routing; split-marker extraction |
| procedure-011 | supported | matching, step extraction | Test/confirm vocabulary; split-marker extraction |
| procedure-012 | supported | matching, step extraction | Test Function action and source-title context |
| procedure-013 | not_found | missing source evidence, boundary | Reverb 1x candidate is incomplete; explicit partial refusal |
| procedure-014 | supported | routing, step extraction | Explicit procedure routing; split-marker extraction |
| procedure-015 | supported | matching | Ordered-step vocabulary and Test Function matching |
| procedure-016 | supported | matching, warning extraction | Notice vocabulary; warnings remain attached outside step prose |
| procedure-017 | supported | matching, step extraction | Content-overlap fallback; complete Test Function evidence |
| procedure-018 | clarification_required | routing | Missing task retained as clarification |
| procedure-019 | supported | routing, matching | Explicit procedure routing and content overlap |
| procedure-020 | supported | matching, step extraction | Test Function and bleed vocabulary; complete continuation |
| procedure-021 | not_found | missing source evidence | Source is a tool-compatibility table, not a service procedure |
| procedure-022 | not_found | missing source evidence, boundary | Partial MT A2 section; explicit partial-evidence refusal |
| procedure-023 | not_found | missing source evidence, step extraction | Unnumbered GUSTAV instructions; explicit partial-evidence refusal |
| procedure-024 | not_found | missing source evidence, boundary | Split Reba section lacks a complete accepted sequence; partial refusal |
| procedure-025 | clarification_required | routing | Missing task retained as clarification |
| procedure-026 | clarification_required | routing | Missing task retained as clarification |
| procedure-027 | clarification_required | routing | Missing task retained as clarification |
| not-found-012 | not_found | missing source evidence, boundary | Partial MT A2 section; required partial diagnostic |
| not-found-013 | not_found | missing source evidence, step extraction | Unnumbered GUSTAV instructions; required partial diagnostic |
| not-found-014 | not_found | missing source evidence, boundary | Split Reba section; required partial diagnostic |
| not-found-015 | not_found | missing source evidence, boundary | Incomplete Reverb 1x candidate; required partial diagnostic |
