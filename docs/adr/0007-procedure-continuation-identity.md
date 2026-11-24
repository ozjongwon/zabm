# Procedure continuation requires document, heading path, and numbered continuity

A repeated procedure title is not sufficient evidence that two PDF sections are
the same procedure. Procedure candidates are grouped by authoritative document,
exact heading path, and title. A section continues the preceding candidate
across pages only when it is the first procedure section on the adjacent
physical page, repeats the same heading path, follows a candidate without an
explicit end boundary, has no intervening heading after the prior steps, and
resumes with non-initial step numbering.

A repeated title that starts again at step 1 is a separate candidate. A
different heading path under the same title is also separate. If a non-initial
number resumes on the expected adjacent page but overlaps or skips the prior
sequence, the sections remain one candidate and the duplicate or discontinuity
check rejects it. This avoids both silently joining separate procedures and
hiding duplicated steps that PDF layout emitted across a page boundary.

Each stored procedure records whether sections were merged, kept separate, or
rejected, with the reason and the involved physical pages. The same decisions
are included in procedure evidence inspection. A duplicate step number is never
accepted without an approved, unambiguous differentiation rule.
