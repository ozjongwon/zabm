# 03: Compatibility answer tracer

**What to build:** An end-to-end compatibility check backed by explicit manufacturer evidence. A mechanic can ask whether two identified components may be used together and receive exactly one of `compatible`, `not_compatible`, cited `unknown`, or `not_found`, with citations and no inference from dimensions, tolerances, or geometry.

**Blocked by:** 02.

**Status:** ready-for-agent

- [ ] At least one explicit manufacturer compatibility rule, compatibility table, or statement is human-verified and stored as structured evidence.
- [ ] A pair supported by an explicit manufacturer rule returns `compatible` with evidence and citations.
- [ ] A pair prohibited by an explicit manufacturer rule returns `not_compatible` with evidence and citations.
- [ ] Relevant evidence that explicitly leaves a pair unresolved returns compatibility `unknown` with response status `supported` and a citation for that limitation.
- [ ] A pair with no adequate source-pack evidence returns compatibility `not_found` with terminal response status `not_found`.
- [ ] Matching dimensions, tolerances, geometry, or visually similar component names cannot produce `compatible` or `not_compatible`.
- [ ] CLI-seam tests cover all four compatibility outcomes and a dimensional near miss.

