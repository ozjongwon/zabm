# 13: Remote OpenAI-compatible provider

**What to build:** An optional OpenAI-compatible remote provider usable through the same interface and answer path as the local reference provider. Evaluators can select it through configuration, keep credentials outside the repository, and distinguish its results by provider and model without changing evidence or refusal behavior.

**Blocked by:** 05.

**Status:** ready-for-agent

- [x] The remote model and embeddings adapter satisfies the same provider interface as the local reference provider.
- [x] Provider selection uses configuration rather than a separate answer workflow.
- [x] Credentials come from environment variables or an equivalent secret store and never appear in committed files, generated results, or logs.
- [x] Results and latency are tagged with the remote provider, model, configuration, and source-pack identifiers.
- [x] Evidence selection, numerical verification, procedure completeness, compatibility outcomes, status, citations, and final acceptance remain owned by deterministic application code.
- [x] Remote unavailability produces a clear operational failure without falling back to unsupported substantive claims.
- [x] Adapter-contract tests use a deterministic fake remote endpoint and cover authentication configuration, tags, unavailable service, and malformed provider output.
- [x] The live remote smoke procedure is documented for an evaluator who supplies credentials.

## Comments

- 2026-11-24: Added named OpenAI, DeepSeek, and custom OpenAI-compatible
  provider profiles over the existing answer path, environment-only
  credentials, canonical provider/model/configuration/source-pack tags,
  provider interaction logging with secret redaction, and a `provider-smoke`
  command that exercises both chat and embeddings. Provider transport failures
  now fail `ask`, evaluation, and smoke commands operationally rather than
  becoming substantive or misleading `not_found` results. Deterministic
  fake-endpoint tests cover authentication, tags, unavailable services, malformed
  chat output, and malformed embedding output. `make verify` passes with 103
  tests.

