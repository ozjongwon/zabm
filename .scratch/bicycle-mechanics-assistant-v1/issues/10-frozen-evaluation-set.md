# 10: Frozen evaluation set

**What to build:** A hand-authored, frozen 120-item evaluation set derived from the frozen source pack. Each item records a self-contained maintenance question, expected outcome, required qualifiers or steps, and minimal source locators so the same results can be reproduced.

**Blocked by:** 09.

**Status:** ready-for-agent

- [ ] The set contains exactly 36 specification, 27 compatibility, 27 procedure, 15 not-found, 8 conflicting-evidence, and 7 out-of-scope items.
- [ ] Every expected outcome is derived from the frozen source pack rather than invented evaluator preference.
- [ ] The set includes adjacent model numbers, wrong generations, cross-brand pairs, unsupported material combinations, missing attributes, truncated procedures, ambiguous aliases, and false premises.
- [ ] Specification expectations include normalized value, range, unit, and required qualifiers.
- [ ] Compatibility and response-status expectations are exact.
- [ ] Procedure expectations identify each required step and warning for deterministic pass/fail grading.
- [ ] Each item records only the minimal source references and page locators needed to reproduce its label.
- [ ] The evaluation set and expected outcomes are frozen before any answer-accuracy baseline is run.
- [ ] Evaluation-contract tests reject missing categories, incorrect counts, duplicate identifiers, missing expected outcomes, and malformed source locators.

