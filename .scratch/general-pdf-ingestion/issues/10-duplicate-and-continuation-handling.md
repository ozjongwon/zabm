# 10: Duplicate and continuation handling

**What to build:** Deterministic handling for repeated step numbers, repeated
section titles, continuation pages, and multi-run procedures. Ambiguous repeats
must remain separate candidates or be rejected rather than merged silently.

**Blocked by:** 06, 07.

**Status:** ready-for-agent

- [ ] Group procedures by authoritative document and heading path in addition to title.
- [ ] Distinguish page continuation from a repeated procedure with the same title.
- [ ] Reject duplicate step numbers within one candidate unless an approved profile supplies an unambiguous differentiation rule.
- [ ] Preserve page ranges and source order when a valid procedure spans pages.
- [ ] Record why repeated candidates were kept separate, merged, or rejected.
- [ ] Add tests for repeated headers, repeated section titles, duplicate step numbers, and legitimate continuation pages.

## Comments

- 2026-11-24: MT A2 current duplicates steps 3, 8, and 10 because layout and page
  labels are reused across pages.
