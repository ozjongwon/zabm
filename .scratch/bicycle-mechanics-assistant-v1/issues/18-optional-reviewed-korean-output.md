# 18: Optional reviewed Korean output

**What to build:** A separately reviewed Korean answer capability behind a feature flag. Korean output preserves every claim, value, unit, status, warning, and citation; disabled or structurally invalid Korean output falls back to a clear English answer.

**Blocked by:** 05, 09, general-pdf-ingestion/12.

**Status:** ready-for-agent

- [ ] Korean output is controlled by a feature flag and remains disabled by default until review passes.
- [ ] A separately authored Korean sample set covers all three question families plus clarification and refusal outcomes.
- [ ] Korean answers preserve normalized values, units, applicability conditions, compatibility outcomes, statuses, warnings, and citation references from the canonical response.
- [ ] Review demonstrates acceptable correctness and fluency before Korean output can be enabled.
- [ ] Structurally invalid, unreviewed, or otherwise rejected Korean prose is never returned.
- [ ] When Korean output is disabled or fails validation, the user receives a clear English answer through the same canonical service.
- [ ] CLI-seam tests cover disabled output, an accepted Korean response, invalid translation fallback, and preservation of values and citations.
- [ ] Korean evaluation results are reported independently and do not alter the v1 acceptance gate.

## Comments

- 2026-11-24: Added `general-pdf-ingestion/12` as a blocker so Korean procedure
  output is reviewed only after stable source extraction and provenance exist.
