# 06: Conflict and precedence handling

**What to build:** A trusted conflict path for disagreeing applicable evidence. The assistant returns `conflicting_evidence` and exposes all applicable sources when precedence is unresolved, or chooses one claim only when cited model scope, supersession, revision, or manufacturer applicability establishes precedence, retaining the rejected evidence visibly.

**Blocked by:** 03, 05.

**Status:** ready-for-agent

- [x] Two or more applicable evidence items that disagree produce `conflicting_evidence` rather than an averaged, interpolated, or silently selected value.
- [x] A conflict response shows every applicable source with its document, page, section, excerpt, and retrieval date.
- [x] Precedence may be selected only from an explicit cited applicability rule, supersession statement, revision date, or manufacturer scope.
- [x] When precedence is established, the rejected claim and the cited precedence reason remain visible.
- [x] Safety-related values are never averaged, interpolated, or silently selected.
- [x] The same conflict handling applies to specifications and compatibility results through the canonical application service.
- [x] CLI-seam tests cover unresolved conflict, cited precedence, visible rejected evidence, and an attempted dimensional resolution.

## Comments

- 2026-11-23: Added a shared conflict adjudicator and canonical conflict report for
  specification and compatibility evidence. Unresolved conflicts return
  `conflicting_evidence` with every candidate claim, excerpt, citation, and
  retrieval date. Human-verified precedence can select one candidate only when
  its cited excerpt establishes model scope, supersession, revision date, or
  manufacturer scope; invalid or non-explicit precedence leaves the conflict
  unresolved. Resolved responses retain selected and rejected candidates and
  the precedence citation in both JSON and plain CLI output. CLI tests cover
  unresolved conflicts, cited precedence, invalid precedence, visible rejected
  evidence, shared compatibility handling, and a dimensional near miss.
  Review also tightened revision precedence so a model year alone is not treated
  as a revision statement. `make verify` passes with 87 tests.
