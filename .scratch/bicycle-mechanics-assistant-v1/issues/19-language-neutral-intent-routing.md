# 19: Language-neutral intent routing

**What to build:** A structured request-routing path that classifies specification, compatibility, procedure, out-of-scope, and ambiguous requests from meaning rather than English keyword matching. The router may use the configured model or another language-neutral semantic mechanism, and deterministic application code validates its result before evidence search or answer assembly.

**Blocked by:** 05.

**Status:** ready-for-agent

- [ ] The CLI no longer chooses a question family by searching English compatibility words, procedure words, or imperative action verbs.
- [ ] Routing returns a validated intent plus recognized entities and missing or ambiguous fields without allowing the model to choose terminal status, citations, compatibility outcome, or procedure completeness.
- [ ] Paraphrased English requests reach the same question family when their meaning is unchanged.
- [ ] Non-English requests can be routed correctly while English remains the reviewed answer language and fallback.
- [ ] A request that plausibly belongs to multiple families or has an uncertain intent does not default silently to specification lookup.
- [ ] Out-of-scope requests are identified before any evidence search.
- [ ] CLI-seam tests use injected routing behavior to cover paraphrases, non-English routing, ambiguity, and out-of-scope rejection without network access.
- [ ] Provider, model, configuration, and routing-version identity are retained in diagnostics and evaluation artifacts.
