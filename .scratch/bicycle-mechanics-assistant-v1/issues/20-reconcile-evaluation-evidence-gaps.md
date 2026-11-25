# 20: Reconcile frozen evaluation evidence gaps

**What to build:** Bring the frozen evaluation expectations and the verified structured evidence into agreement. Every item expected to return a supported conflict or compatibility outcome must have human-verified source evidence with all applicability conditions, or its expectation must be corrected through a reviewed evaluation replacement.

**Blocked by:** None.

**Status:** resolved

- [x] Audit conflict items 001-008 and compatibility items 012-015 against their cited manufacturer sources.
- [x] For each item, record whether the expected top-cap conflict, hose-barb conflict, composite-rail outcome, or seatpost-diameter outcome is explicitly supported by source text.
- [x] Add human-verified structured evidence, including exact excerpts, locators, and applicability conditions, where the source supports the expected outcome.
- [x] Correct evaluation expectations and regenerate the evaluation freeze where the source does not support the expected outcome.
- [x] Keep the source-pack change distinct from any evaluation-label correction and record the maintainer review for each artifact that changes.
- [x] Run source validation, retrieval smoke, and the complete evaluation after either kind of change.
- [x] Report every remaining unsupported item without inventing compatibility, conflict, citation, or applicability evidence.

## Comments

- 2026-11-25: Created from ticket 12 review. Conflict items 001-008 expect
  top-cap or hose-barb claims that are absent from
  `data/evidence/verified-specifications.json`. Compatibility items 012-015
  expect composite-rail and seatpost-diameter outcomes with no corresponding
  rule in `data/evidence/verified-compatibility.json`. ADR-0002 prohibits
  inferring compatibility from dimensions alone.
- 2026-11-26: Audited the cited PDF pages and recorded proposed dispositions in
  `data/audits/evaluation-evidence-reconciliation-v1.md`. Reba top-cap items
  001-004 are supported as conflicting variants. Reverb hose-barb items 005-008
  concern different joints and should become clarification requests.
  Compatibility items 012-013 are explicitly supported by the Reverb AXS
  composite 7x9 rail statement. Items 014-015 are supported by the explicit
  requirement that seatpost and seat-tube diameters match. Human verification
  of the proposed records and evaluation-label replacement is still required.
- 2026-11-26: Maintainer review accepted the audit and implementation. Added
  two Reba top-cap specifications, two joint-specific Reverb hose-barb
  specifications, and two Reverb AXS compatibility rules. Changed conflict
  items 005-008 to clarification requests and aligned the Reba conflict claims
  with the verified records. Regenerated the evaluation freeze under
  `ticket-20-evaluation-evidence-reconciliation-2026-11-26`; the source pack
  did not change.
- 2026-11-26: Fresh ingestion, source coverage, and retrieval smoke passed.
  All three complete-evaluation full-agent runs reached 98.33% accuracy,
  100% citation validity, 100% correct abstention, and zero fabricated numbers.
  All twelve audited items pass in every run. `compat-006` and `compat-007`
  remain unsupported outside this ticket's audited set and were not inferred.
