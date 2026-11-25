# 03: Language-neutral translation and validation

**What to build:** Generalize the Korean translation prompt and validation
pipeline so any approved target language can be translated while canonical
answer structure remains application-owned.

**Blocked by:** 01, 02.

**Status:** ready-for-agent

- [ ] Replace Korean-specific translation models, prompt markers, test fixtures, and Hangul validation with target-language profile inputs.
- [ ] Require the translator to return the requested language tag and the exact canonical claim, condition, procedure, warning, message, and conflict structure.
- [ ] Preserve claim IDs, numbers, units, normalized display values, conditions, statuses, compatibility outcomes, warning severities, citation references, and conflict candidates.
- [ ] Reject translations that report the wrong target tag, return English canonical text unchanged, add unsupported prose, omit required prose, or violate the profile's language check.
- [ ] Keep accepted translated prose in a separate localized answer object and leave canonical English fields unchanged.
- [ ] Fall back to English for invalid or unreviewed translations without returning partially accepted target-language prose.
- [ ] Add deterministic CLI-seam tests for accepted, structurally invalid, wrong-language, and added-content translations in at least two non-English languages.

## Comments

- 2026-11-25: Initial ticket from the multilingual reviewed-output spec.
