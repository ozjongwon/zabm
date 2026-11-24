# 06: Procedure candidate and step extraction

**What to build:** Stricter procedure-candidate and numbered-step extraction that
uses section context, numbering continuity, vertical order, and block type. It
must reject contents entries, table cells, figure callouts, and page numbers.

**Blocked by:** 03, 05.

**Status:** ready-for-agent

- [x] Require a procedure heading or approved section context before extracting steps.
- [x] Accept only contiguous numbered steps in source order unless an approved profile defines a different numbering style.
- [x] Reject numbered lines that contain section references, page references, table values, or figure-callout-only content.
- [x] Require substantive action text rather than heading fragments or isolated numbers.
- [x] Prevent a line from combining multiple source columns or unrelated list entries.
- [x] Record rejected numbered candidates and the reason for rejection.
- [x] Add tests where contents entries and torque tables contain numbers that look like steps.

## Comments

- 2026-11-24: Current `_step_starts` accepts broad inline-number patterns and
  standalone numbers near x=60-75, producing all four MAGURA false positives.

- 2026-11-24: Implemented procedure-context and action validation, typed
  rejected-candidate diagnostics, source/table/figure/mixed-column filtering,
  and contiguous-prefix numbering checks in parser `pdf-ingestion-v5`. Added
  CLI-seam tests for page furniture, table values, figure callouts, isolated
  numbers, missing procedure headings, joined columns, heading fragments, and
  discontinuous numbering.
