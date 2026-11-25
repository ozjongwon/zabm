# 05: Language-neutral CLI and web rendering

**What to build:** Render reviewed localized prose and labels for any active
language in both adapters while retaining canonical values and citations.

**Blocked by:** 01, 03, 04.

**Status:** ready-for-agent

- [ ] Replace hard-coded Korean status, condition, source, warning, and refusal labels with profile-provided or validated translation-prose labels.
- [ ] Render localized claims, conditions, procedures, warnings, clarifications, refusals, and conflict prose in the CLI.
- [ ] Render the same localized prose in the web answer pane while keeping the browser as a presentation adapter only.
- [ ] Keep canonical values, statuses, warnings, citations, and the complete response envelope available for inspection.
- [ ] Ensure the web endpoint uses automatic question-language selection without a separate language-specific answer path.
- [ ] Display a clear English fallback when the profile or translation is unavailable.
- [ ] Add adapter tests for arbitrary language tags and update web acceptance instructions with Korean and one additional language fixture.

## Comments

- 2026-11-25: Initial ticket from the multilingual reviewed-output spec.
