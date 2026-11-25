# 14: Optional LangSmith result mirror

**What to build:** Optional LangSmith mirroring for evaluation results and traces. Local canonical artifacts remain the source of truth and a complete evaluation still succeeds when LangSmith is disabled, misconfigured, slow, or unavailable.

**Blocked by:** 11.

**Status:** resolved

- [x] Evaluation always produces the canonical local result artifacts whether LangSmith is enabled or not.
- [x] When enabled, evaluation results and traces are mirrored to LangSmith with the run, provider, model, configuration, and source-pack identifiers.
- [x] LangSmith credentials are read only from environment variables or an equivalent secret store and are not committed or logged.
- [x] A LangSmith connection failure or timeout is reported as an observability warning without invalidating the local evaluation run.
- [x] Retry or timeout behavior is bounded and does not stall canonical local evaluation indefinitely.
- [x] CLI-seam tests cover mirroring through a deterministic fake sink, disabled operation, unavailable service, and preservation of local artifacts.
- [x] The acceptance procedure documents how to prove successful LangSmith logging when credentials are available.

## Comments

- 2026-11-25: Added an optional environment-configured LangSmith mirror after
  canonical artifact persistence. It sends the evaluation root, configuration
  runs, and item traces to the bounded LangSmith batch-ingestion API with
  provider, model, configuration, source-pack, and run identifiers. Mirror
  failures and timeouts are sanitized observability warnings and do not change
  the local command result. CLI integration tests use a deterministic local
  sink for success, disablement, rejection, timeout, and missing-credential
  paths. The LangSmith acceptance procedure is documented in
  `docs/langsmith-evaluation-acceptance.md`.

