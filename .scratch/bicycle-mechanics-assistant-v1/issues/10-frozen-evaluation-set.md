# 10: Frozen evaluation set

**What to build:** A hand-authored, frozen 120-item evaluation set derived from the frozen source pack. Each item records a self-contained maintenance question, expected outcome, required qualifiers or steps, and minimal source locators so the same results can be reproduced.

**Blocked by:** 09.

**Status:** ready-for-agent

- [x] The set contains exactly 36 specification, 27 compatibility, 27 procedure, 15 not-found, 8 conflicting-evidence, and 7 out-of-scope items.
- [x] Every expected outcome is derived from the frozen source pack rather than invented evaluator preference.
- [x] The set includes adjacent model numbers, wrong generations, cross-brand pairs, unsupported material combinations, missing attributes, truncated procedures, ambiguous aliases, and false premises.
- [x] Specification expectations include normalized value, range, unit, and required qualifiers.
- [x] Compatibility and response-status expectations are exact.
- [x] Procedure expectations identify each required step and warning for deterministic pass/fail grading.
- [x] Each item records only the minimal source references and page locators needed to reproduce its label.
- [x] The evaluation set and expected outcomes are frozen before any answer-accuracy baseline is run.
- [x] Evaluation-contract tests reject missing categories, incorrect counts, duplicate identifiers, missing expected outcomes, and malformed source locators.

## Comments

- 2026-11-23: Added the hand-authored 120-item evaluation set. The set is
  bound to the frozen source-pack descriptor and manifest by
  `data/evaluation/evaluation-freeze-v1.json`. `zabm evaluation-set` validates
  category counts, required edge cases, item identifiers, expected outcome
  shapes, source existence, page bounds, and the frozen set checksum.
- 2026-11-23: Added CLI-seam tests for a valid frozen set and rejection of
  missing categories, incorrect counts, duplicate IDs, missing expected
  outcomes, unknown source locators, and unreviewed expected-outcome changes.

