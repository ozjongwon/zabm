# 14: Optional LangSmith result mirror

**What to build:** Optional LangSmith mirroring for evaluation results and traces. Local canonical artifacts remain the source of truth and a complete evaluation still succeeds when LangSmith is disabled, misconfigured, slow, or unavailable.

**Blocked by:** 11.

**Status:** ready-for-agent

- [ ] Evaluation always produces the canonical local result artifacts whether LangSmith is enabled or not.
- [ ] When enabled, evaluation results and traces are mirrored to LangSmith with the run, provider, model, configuration, and source-pack identifiers.
- [ ] LangSmith credentials are read only from environment variables or an equivalent secret store and are not committed or logged.
- [ ] A LangSmith connection failure or timeout is reported as an observability warning without invalidating the local evaluation run.
- [ ] Retry or timeout behavior is bounded and does not stall canonical local evaluation indefinitely.
- [ ] CLI-seam tests cover mirroring through a deterministic fake sink, disabled operation, unavailable service, and preservation of local artifacts.
- [ ] The acceptance procedure documents how to prove successful LangSmith logging when credentials are available.

