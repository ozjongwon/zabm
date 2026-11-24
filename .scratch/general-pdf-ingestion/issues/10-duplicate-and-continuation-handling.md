# 10: Duplicate and continuation handling

**What to build:** Deterministic handling for repeated step numbers, repeated
section titles, continuation pages, and multi-run procedures. Ambiguous repeats
must remain separate candidates or be rejected rather than merged silently.

**Blocked by:** 06, 07.

**Status:** ready-for-agent

- [x] Group procedures by authoritative document and heading path in addition to title.
- [x] Distinguish page continuation from a repeated procedure with the same title.
- [x] Reject duplicate step numbers within one candidate unless an approved profile supplies an unambiguous differentiation rule.
- [x] Preserve page ranges and source order when a valid procedure spans pages.
- [x] Record why repeated candidates were kept separate, merged, or rejected.
- [x] Add tests for repeated headers, repeated section titles, duplicate step numbers, and legitimate continuation pages.

## Comments

- 2026-11-24: MT A2 current duplicates steps 3, 8, and 10 because layout and page
  labels are reused across pages.

- 2026-11-24: Implemented in parser `pdf-ingestion-v9`. Grouping now requires
  authoritative document, title, and exact heading path. Adjacent sections only
  merge when numbering resumes from a non-initial step and no explicit end
  boundary or intervening heading preceded them; a step-1 restart remains
  separate. Cross-page overlap stays in one candidate and is rejected as a
  duplicate. Procedure artifacts and `evidence --json` now expose merged,
  kept-separate, and rejected decisions with reasons and page numbers. Added
  CLI-seam regression coverage for repeated headers, repeated titles, explicit
  ends, different heading paths, intervening headings, cross-page duplicates,
  and valid continuations. See
  `docs/adr/0007-procedure-continuation-identity.md`.
