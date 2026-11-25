# 06: Cross-language acceptance and review guide

**What to build:** Prove the generic workflow end to end with representative
language profiles, a reusable review procedure, and CLI plus browser acceptance.

**Blocked by:** 01, 02, 03, 04, 05.

**Status:** ready-for-agent

- [ ] Provide a reviewed Korean profile migration and at least one additional deterministic test profile for a non-Latin or regional language.
- [ ] Document how to add a sample set, complete human review, calculate the sample hash, approve the review, allowlist the language, and disable it again.
- [ ] Demonstrate that a Korean question receives Korean through automatic selection without `--language ko`.
- [ ] Demonstrate that an explicit tag overrides detected input language.
- [ ] Demonstrate that an unsupported or unreviewed language returns the canonical English answer with fallback metadata.
- [ ] Compare CLI and web output for supported specifications, compatibility, procedures, clarification, conflicts, not-found, and out-of-scope responses in at least two target languages.
- [ ] Confirm per-language results do not alter the v1 evaluation or acceptance artifacts.
- [ ] Record the final command-level acceptance procedure and expected JSON markers.

## Comments

- 2026-11-25: Initial ticket from the multilingual reviewed-output spec.
