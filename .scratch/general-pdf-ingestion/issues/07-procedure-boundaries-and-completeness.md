# 07: Procedure boundaries and completeness

**What to build:** A reviewed boundary model for deciding where a procedure
starts and ends. Completeness may use explicit markers or an approved,
unambiguous section boundary, but must fail closed when ambiguity remains.

**Blocked by:** 05, 06.

**Status:** ready-for-human

- [ ] Define the accepted evidence for explicit end markers and section-boundary end markers.
- [ ] Require maintainer approval for profile rules that infer completeness from a following heading.
- [ ] Reject procedures that begin after step 1, end without boundary evidence, or contain unordered or duplicate steps.
- [ ] Record start boundary, end boundary, and end strategy in the procedure artifact.
- [ ] Preserve warnings and navigation text that affects completeness.
- [ ] Ensure a partial section can never become `supported`.
- [ ] Add tests for explicit end markers, heading-based ends, missing ends, and ambiguous next sections.

## Comments

- 2026-11-24: MAGURA procedures lack the current “This concludes” style marker,
  so all candidates fail completeness even where useful procedure text exists.
