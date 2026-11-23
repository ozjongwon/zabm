# 03: Compatibility answer tracer

**What to build:** An end-to-end compatibility check backed by explicit manufacturer evidence. A mechanic can ask whether two identified components may be used together and receive exactly one of `compatible`, `not_compatible`, cited `unknown`, or `not_found`, with citations and no inference from dimensions, tolerances, or geometry.

**Blocked by:** 02.

**Status:** ready-for-agent

- [x] At least one explicit manufacturer compatibility rule, compatibility table, or statement is human-verified and stored as structured evidence.
- [x] A pair supported by an explicit manufacturer rule returns `compatible` with evidence and citations.
- [x] A pair prohibited by an explicit manufacturer rule returns `not_compatible` with evidence and citations.
- [x] Relevant evidence that explicitly leaves a pair unresolved returns compatibility `unknown` with response status `supported` and a citation for that limitation.
- [x] A pair with no adequate source-pack evidence returns compatibility `not_found` with terminal response status `not_found`.
- [x] Matching dimensions, tolerances, geometry, or visually similar component names cannot produce `compatible` or `not_compatible`.
- [x] CLI-seam tests cover all four compatibility outcomes and a dimensional near miss.

## Comments

- 2026-11-23: Added human-verified SRAM compatibility evidence for the Reverb
  Stealth hose barb with barb sleeve on A2/B1 seatposts and for DOT-contaminated
  syringes against the Reverb hydraulic system. The CLI now ingests the
  compatibility evidence plane and returns all four outcomes through one
  canonical response. Tests cover natural "use with" routing, dimensional and
  visual near misses, unverified rules, invalid citations, and dimension-only
  evidence labelled as compatible. The live pinned source returns page-11
  `compatible` and page-26 `not_compatible` answers with full citations.

