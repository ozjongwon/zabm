# 19: Language-neutral intent routing

**What to build:** A structured request-routing path that classifies specification, compatibility, procedure, out-of-scope, and ambiguous requests from meaning rather than English keyword matching. The router may use the configured model or another language-neutral semantic mechanism, and deterministic application code validates its result before evidence search or answer assembly.

**Blocked by:** 05.

**Status:** resolved

- [x] The CLI no longer chooses a question family by searching English compatibility words, procedure words, or imperative action verbs.
- [x] Routing returns a validated intent plus recognized entities and missing or ambiguous fields without allowing the model to choose terminal status, citations, compatibility outcome, or procedure completeness.
- [x] Paraphrased English requests reach the same question family when their meaning is unchanged.
- [x] Non-English requests can be routed correctly while English remains the reviewed answer language and fallback.
- [x] A request that plausibly belongs to multiple families or has an uncertain intent does not default silently to specification lookup.
- [x] Out-of-scope requests are identified before any evidence search.
- [x] CLI-seam tests use injected routing behavior to cover paraphrases, non-English routing, ambiguity, and out-of-scope rejection without network access.
- [x] Provider, model, configuration, and routing-version identity are retained in diagnostics and evaluation artifacts.

## Comments

- 2026-11-24: Replaced the CLI's family-specific English cue classifier
  with a validated `structured-intent-v1` route. Configured providers classify
  by meaning and normalize non-English requests to an English evidence query;
  deterministic mode uses a bounded multilingual prototype fallback. The route
  exposes recognized entities and missing or ambiguous fields, rejects extra
  model-owned response fields, and returns clarification rather than silently
  defaulting. Out-of-scope decisions happen before evidence access. Canonical
  responses retain routing strategy/version plus provider identity, and
  evaluation artifacts retain routing identity. CLI-seam coverage includes
  paraphrase, German routing, ambiguity, early scope refusal, malformed route
  output, and fake-provider diagnostics. Verified with 211 tests, Ruff, and
  strict Pyright.
