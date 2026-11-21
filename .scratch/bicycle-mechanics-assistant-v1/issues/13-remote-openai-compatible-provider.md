# 13: Remote OpenAI-compatible provider

**What to build:** An optional OpenAI-compatible remote provider usable through the same interface and answer path as the local reference provider. Evaluators can select it through configuration, keep credentials outside the repository, and distinguish its results by provider and model without changing evidence or refusal behavior.

**Blocked by:** 05.

**Status:** ready-for-agent

- [ ] The remote model and embeddings adapter satisfies the same provider interface as the local reference provider.
- [ ] Provider selection uses configuration rather than a separate answer workflow.
- [ ] Credentials come from environment variables or an equivalent secret store and never appear in committed files, generated results, or logs.
- [ ] Results and latency are tagged with the remote provider, model, configuration, and source-pack identifiers.
- [ ] Evidence selection, numerical verification, procedure completeness, compatibility outcomes, status, citations, and final acceptance remain owned by deterministic application code.
- [ ] Remote unavailability produces a clear operational failure without falling back to unsupported substantive claims.
- [ ] Adapter-contract tests use a deterministic fake remote endpoint and cover authentication configuration, tags, unavailable service, and malformed provider output.
- [ ] The live remote smoke procedure is documented for an evaluator who supplies credentials.

