# 23: Remote LLM acceptance and performance evidence

**What to build:** Produce the canonical v1 acceptance evidence for the revised
provider topology: a remote OpenAI-compatible LLM, normally DeepSeek, with
either a remote embedding API or local Ollama embeddings.

**Blocked by:** None.

**Status:** ready-for-agent

- [ ] Run the frozen 120-item set for LLM-only, plain RAG, hybrid retrieval, and full agent, three times each, with `deepseek-chat` and the selected embedding provider.
- [ ] Resolve full-agent routing or provider-output failures exposed by the remote run without bypassing application-owned evidence and safety gates.
- [ ] Meet the 90% median accuracy, 10-point improvement, paired-bootstrap interval, citation, abstention, and fabricated-number gates.
- [ ] Meet remote-LLM latency at 20 seconds median and 30 seconds p95 over the frozen set, excluding warm-up.
- [ ] Record provider, chat model, embedding provider deployment, embedding model, configuration, runtime, and per-run latency in the canonical artifact.
- [ ] Regenerate the canonical acceptance report and preserve any failed gate with diagnostic evidence.
- [ ] Update evaluation and operational documentation with the exact passing provider command and environment configuration.

## Comments

- 2026-11-26: Split from ticket 12 after the v1 provider requirement changed
  from local GPU inference to remote LLM inference with remote or local Ollama
  embeddings. A DeepSeek chat plus local Ollama embedding smoke passed. The
  five-item fixture completed but full-agent accuracy was 60%, so routing and
  provider-output failures must be understood before the full ladder.
