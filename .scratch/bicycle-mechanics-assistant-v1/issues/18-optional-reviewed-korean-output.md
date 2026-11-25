# 18: Optional reviewed Korean output

**What to build:** A separately reviewed Korean answer capability behind a feature flag. Korean output preserves every claim, value, unit, status, warning, and citation; disabled or structurally invalid Korean output falls back to a clear English answer.

**Blocked by:** 05, 09, general-pdf-ingestion/12.

**Status:** resolved

- [x] Korean output is controlled by a feature flag and remains disabled by default until review passes.
- [x] A separately authored Korean sample set covers all three question families plus clarification and refusal outcomes.
- [x] Korean answers preserve normalized values, units, applicability conditions, compatibility outcomes, statuses, warnings, and citation references from the canonical response.
- [x] Review demonstrates acceptable correctness and fluency before Korean output can be enabled.
- [x] Structurally invalid, unreviewed, or otherwise rejected Korean prose is never returned.
- [x] When Korean output is disabled or fails validation, the user receives a clear English answer through the same canonical service.
- [x] CLI-seam tests cover disabled output, an accepted Korean response, invalid translation fallback, and preservation of values and citations.
- [x] Korean evaluation results are reported independently and do not alter the v1 acceptance gate.

## Comments

- 2026-11-24: Added `general-pdf-ingestion/12` as a blocker so Korean procedure
  output is reviewed only after stable source extraction and provenance exist.
- 2026-11-25: Added the `--language ko` semantic translation path behind
  `ZABM_KOREAN_OUTPUT` and an approved, hash-bound review record. The canonical
  English response remains application-owned; accepted Korean prose is stored
  separately and validated for claim IDs, numbers, units, conditions, statuses,
  procedure warnings, and citations. Disabled or rejected translations return
  the canonical English answer with explicit localization metadata. Added a
  five-case separately authored Korean sample set, a pending review record, the
  independent `korean-review` report, and CLI coverage for disabled, accepted,
  invalid-value, clarification, and procedure-warning paths. The committed
  review remains pending, so Korean output cannot be enabled until a human
  reviewer approves the sample set and records correctness and fluency results.
- 2026-11-25: Changed the default output-language policy to `auto`. Korean
  questions now request the reviewed Korean response without an explicit CLI
  flag; English and unsupported-language questions continue to receive the
  canonical English answer. Explicit `--language en` or `--language ko`
  overrides detection.
- 2026-11-25: Hardened installed-runtime discovery of the Korean review. The
  runtime installer now records absolute sample-set and review paths in
  `runtime.env`, and blank path overrides fall back to those defaults instead of
  resolving to the current directory.
- 2026-11-25: The five-case Korean sample review was approved by `jc` with full
  correctness and fluency scores and all preservation checks passing. An
  end-to-end DeepSeek run now returns Korean prose with
  `localization.status=translated`, preserving the canonical torque value,
  conditions, status, and citation.
