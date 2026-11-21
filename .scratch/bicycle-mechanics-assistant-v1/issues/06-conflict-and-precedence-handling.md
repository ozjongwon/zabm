# 06: Conflict and precedence handling

**What to build:** A trusted conflict path for disagreeing applicable evidence. The assistant returns `conflicting_evidence` and exposes all applicable sources when precedence is unresolved, or chooses one claim only when cited model scope, supersession, revision, or manufacturer applicability establishes precedence, retaining the rejected evidence visibly.

**Blocked by:** 03, 05.

**Status:** ready-for-agent

- [ ] Two or more applicable evidence items that disagree produce `conflicting_evidence` rather than an averaged, interpolated, or silently selected value.
- [ ] A conflict response shows every applicable source with its document, page, section, excerpt, and retrieval date.
- [ ] Precedence may be selected only from an explicit cited applicability rule, supersession statement, revision date, or manufacturer scope.
- [ ] When precedence is established, the rejected claim and the cited precedence reason remain visible.
- [ ] Safety-related values are never averaged, interpolated, or silently selected.
- [ ] The same conflict handling applies to specifications and compatibility results through the canonical application service.
- [ ] CLI-seam tests cover unresolved conflict, cited precedence, visible rejected evidence, and an attempted dimensional resolution.
