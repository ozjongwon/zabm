# 02: Dynamic question-language routing

**What to build:** Add a validated question-language signal to semantic routing
and use it for automatic output-language selection. Replace the fixed
English/Korean output selector and Hangul-only detection.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] Extend the semantic routing contract and canonical routing metadata with a validated BCP 47 question-language tag.
- [ ] Update the routing prompt to identify the question language without deciding output status, evidence, or citations.
- [ ] Make `--language auto` select the router-reported question language and make an explicit language tag override detection.
- [ ] Accept arbitrary normalized BCP 47 output tags rather than an `en|ko` literal.
- [ ] Fall back to English with explicit localization metadata when the requested language has no available reviewed profile.
- [ ] Remove Hangul-only target-language detection and fixed Korean environment defaults from the selection path.
- [ ] Add CLI-seam tests for auto selection, explicit overrides, region/script tags, invalid tags, unsupported languages, and English fallback.

## Comments

- 2026-11-25: Initial ticket from the multilingual reviewed-output spec.
