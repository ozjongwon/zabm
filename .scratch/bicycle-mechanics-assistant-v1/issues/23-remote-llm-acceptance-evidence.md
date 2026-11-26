# 23: Remote LLM acceptance and performance evidence

**What to build:** Produce the canonical v1 acceptance evidence for the revised
provider topology: a remote OpenAI-compatible LLM, normally DeepSeek, with
either a remote embedding API or local Ollama embeddings.

**Blocked by:** None.

**Status:** resolved

- [x] Run the frozen 120-item set for LLM-only, plain RAG, hybrid retrieval, and full agent, three times each, with `deepseek-chat` and the selected embedding provider.
- [x] Resolve full-agent routing or provider-output failures exposed by the remote run without bypassing application-owned evidence and safety gates.
- [x] Meet the 90% median accuracy, 10-point improvement, paired-bootstrap interval, citation, abstention, and fabricated-number gates.
- [x] Meet remote-LLM latency at 20 seconds median and 30 seconds p95 over the frozen set, excluding warm-up.
- [x] Record provider, chat model, embedding provider deployment, embedding model, configuration, runtime, and per-run latency in the canonical artifact.
- [x] Regenerate the canonical acceptance report and preserve any failed gate with diagnostic evidence.
- [x] Update evaluation and operational documentation with the exact passing provider command and environment configuration.

## Comments

- 2026-11-26: Split from ticket 12 after the v1 provider requirement changed
  from local GPU inference to remote LLM inference with remote or local Ollama
  embeddings. A DeepSeek chat plus local Ollama embedding smoke passed. The
  five-item fixture completed but full-agent accuracy was 60%, so routing and
  provider-output failures must be understood before the full ladder.
- 2026-11-26: Resolved the five-item failures through the CLI seam. An
  unambiguous prototype out-of-scope route now overrides a model route that
  would otherwise ask for non-maintenance evidence details. A model
  clarification or ambiguous route now falls back to prototype routing only
  when deterministic evidence produces a fully supported answer. Provider
  phrasing may split one validated claim across multiple sentences, but every
  sentence still passes the existing claim-ID, number, and token-support
  checks. Regression coverage is in `tests/test_cli_agent.py`.
- 2026-11-26: The canonical remote ladder passed with `deepseek-chat`,
  Ollama `mxbai-embed-large:latest` (1024 dimensions), temperature zero, seeds
  0/1/2, a 12,000-character prompt budget, and top-k 5. Full-agent accuracy was
  94.17% median (93.33%-95.00%); improvements were 94.17 points over LLM-only
  with a [89.72%, 97.78%] interval and 93.33 points over plain RAG with a
  [88.61%, 97.22%] interval. Citation validity was 100%, correct abstention was
  97.78% overall and at least 95.83% in each refusal category, fabricated
  numbers were zero, and latency was 2,041.80 ms median / 4,128.14 ms p95 after
  warm-up. The provider identity records
  `embedding_deployment: http://127.0.0.1:11434/v1`.
- 2026-11-26: No acceptance gate failed. Six to eight full-agent item misses per
  run remain in the canonical artifact as diagnostics: the DOT-contaminated
  syringe/fluid compatibility variant returns `not_found`, and underspecified
  procedure or compatibility requests return clarification with different
  frozen vocabulary. Exact commands, environment, results, and artifact
  checksums are recorded in `docs/remote-llm-acceptance.md`; evaluation and
  target-runtime documentation link to that evidence.
