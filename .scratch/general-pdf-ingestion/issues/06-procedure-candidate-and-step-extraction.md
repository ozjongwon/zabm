# 06: Procedure candidate and step extraction

**What to build:** Stricter procedure-candidate and numbered-step extraction that
uses section context, numbering continuity, vertical order, and block type. It
must reject contents entries, table cells, figure callouts, and page numbers.

**Blocked by:** 03, 05.

**Status:** ready-for-agent

- [ ] Require a procedure heading or approved section context before extracting steps.
- [ ] Accept only contiguous numbered steps in source order unless an approved profile defines a different numbering style.
- [ ] Reject numbered lines that contain section references, page references, table values, or figure-callout-only content.
- [ ] Require substantive action text rather than heading fragments or isolated numbers.
- [ ] Prevent a line from combining multiple source columns or unrelated list entries.
- [ ] Record rejected numbered candidates and the reason for rejection.
- [ ] Add tests where contents entries and torque tables contain numbers that look like steps.

## Comments

- 2026-11-24: Current `_step_starts` accepts broad inline-number patterns and
  standalone numbers near x=60-75, producing all four MAGURA false positives.
