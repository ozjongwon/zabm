# 01: Language profile contract and Korean migration

**What to build:** Replace the Korean-only profile and artifact layout with a
validated, language-neutral profile contract. Migrate the existing Korean
sample set, pending review, configuration paths, and loader behavior without
enabling Korean output.

**Blocked by:** None.

**Status:** ready-for-agent

- [ ] Define a versioned language-profile schema with a normalized BCP 47 tag, display name, adapter labels, language checks, sample-set path, and review path.
- [ ] Load profiles from `data/localization/<language-tag>/` and reject duplicate tags, invalid tags, path traversal, missing files, and cross-profile review references.
- [ ] Migrate the Korean sample set, pending review, and review hash to `data/localization/ko/` without changing reviewed content.
- [ ] Replace `ZABM_KOREAN_SAMPLE_SET` and `ZABM_KOREAN_REVIEW` runtime configuration with language-neutral localization-directory configuration while preserving a documented migration path.
- [ ] Keep English built in and keep every non-English profile disabled until its own review is approved.
- [ ] Add profile-loading tests at the CLI seam, including valid Korean migration, malformed tags, missing profiles, and mismatched hashes.
- [ ] Update existing Korean tests and documentation to use the generic profile layout.

## Comments

- 2026-11-25: Initial ticket from the multilingual reviewed-output spec.
