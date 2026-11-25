# 07: Procedure boundaries and completeness

**What to build:** A reviewed boundary model for deciding where a procedure
starts and ends. Completeness may use explicit markers or an approved,
unambiguous section boundary, but must fail closed when ambiguity remains.

**Blocked by:** 05, 06.

**Status:** resolved

- [x] Define the accepted evidence for explicit end markers and section-boundary end markers.
- [x] Require maintainer approval for profile rules that infer completeness from a following heading.
- [x] Reject procedures that begin after step 1, end without boundary evidence, or contain unordered or duplicate steps.
- [x] Record start boundary, end boundary, and end strategy in the procedure artifact.
- [x] Preserve warnings and navigation text that affects completeness.
- [x] Ensure a partial section can never become `supported`.
- [x] Add tests for explicit end markers, heading-based ends, missing ends, and ambiguous next sections.

## Comments

- 2026-11-24: MAGURA procedures lack the current “This concludes” style marker,
  so all candidates fail completeness even where useful procedure text exists.

- 2026-11-24: Implemented boundary evidence in parser `pdf-ingestion-v6`.
  Explicit end markers take precedence. Reviewed profiles may complete at the
  immediately following same-or-shallower heading; a child heading is
  ambiguous and leaves the procedure partial even when a peer heading follows.
  Procedure artifacts now record start/end boundaries, the end strategy, and
  completeness notes. Missing ends, contradictory continuation notes, and
  invalid step sequences remain ineligible for supported answers. See
  `docs/adr/0005-procedure-boundary-evidence.md`.
