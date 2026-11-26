# Remote LLM acceptance evidence

This is the v1 acceptance procedure for the remote provider topology. It uses
DeepSeek for chat and local Ollama for embeddings, while preserving the
canonical CLI and application-owned evidence gates.

The passing run on 2026-11-26 used:

| Component | Value |
| --- | --- |
| Chat provider | `deepseek` |
| Chat model | `deepseek-chat` |
| Chat endpoint | `https://api.deepseek.com` |
| Embedding provider | Ollama via an SSH-forwarded HTTP endpoint |
| Embedding model | `mxbai-embed-large:latest` |
| Embedding endpoint | `http://127.0.0.1:11434/v1` |
| Provider configuration | `deepseek-chat,mxbai-embed-large:latest,temperature=0` |
| Temperature | `0` |
| Seeds | `0`, `1`, `2` |
| Prompt budget | `12,000` characters |
| Retrieval top-k | `5` |

The canonical provider identity records `embedding_deployment` as
`http://127.0.0.1:11434/v1`; this appears in the evaluation artifact and every
per-item response.

## Environment

Keep `DEEPSEEK_API_KEY` outside the repository. If Ollama is already reachable
from the machine running ZABM, point `ZABM_EMBEDDING_PROVIDER_URL` at that
endpoint directly. The accepted run used an SSH tunnel because Ollama was
remote:

```bash
export DEEPSEEK_API_KEY="<secret>"
export ZABM_EMBEDDING_PROVIDER_URL="http://127.0.0.1:11434/v1"
export ZABM_EMBEDDING_MODEL="mxbai-embed-large:latest"

ssh -N -L 11434:127.0.0.1:11434 zbm@hope.local
```

Run the tunnel in a separate terminal. The accepted deployment used
`mxbai-embed-large:latest`, which produces 1024-dimensional embeddings.

## Commands

Exercise both provider halves first:

```bash
./.venv/bin/python -m zabm provider-smoke \
  --provider deepseek \
  --model deepseek-chat \
  --embedding-model mxbai-embed-large:latest \
  --provider-configuration "deepseek-chat,mxbai-embed-large:latest,temperature=0" \
  --output data/evaluation/deepseek-provider-smoke-v1.json
```

Run the frozen 120-item ladder, all four configurations, and all three seeds:

```bash
./.venv/bin/python -m zabm evaluation \
  --output data/evaluation/baseline-results-v1.json \
  --provider deepseek \
  --model deepseek-chat \
  --embedding-model mxbai-embed-large:latest \
  --provider-configuration "deepseek-chat,mxbai-embed-large:latest,temperature=0"
```

Score the canonical result and regenerate the acceptance report:

```bash
./.venv/bin/python -m zabm acceptance \
  --execution-environment remote-llm
```

## Accepted result

| Gate or metric | Observed | Threshold or requirement |
| --- | ---: | ---: |
| Full-agent median accuracy | 94.17% | at least 90% |
| Full-agent accuracy range | 93.33%-95.00% | reported across three runs |
| Improvement over LLM-only | 94.17% | at least 10 points |
| LLM-only paired-bootstrap 95% interval | 89.72%-97.78% | wholly above zero |
| Improvement over plain RAG | 93.33% | at least 10 points |
| Plain-RAG paired-bootstrap 95% interval | 88.61%-97.22% | wholly above zero |
| Citation validity | 100.00% | at least 95% |
| Correct abstention | 97.78% overall; at least 95.83% per category | at least 95% |
| Fabricated numeric values | 0 | 0 |
| Remote-LLM latency | 2,041.80 ms median, 4,128.14 ms p95 | at most 20,000/30,000 ms |

The latency is measured per scored item in the full-agent median-accuracy run
after the recorded warm-up. Hardware and runtime identity are in both canonical
artifacts.

The full agent missed 6-8 of 120 items per run. These misses are retained in
`data/evaluation/baseline-results-v1.json`; no gate failed. They consist of:

- `compat-007`: the DOT-contaminated syringe/fluid compatibility variant
  returned `not_found` instead of the expected cited `not_compatible` rule.
- `compat-025`: returned `clarification_required`, but with different
  clarification wording and missing-field labels than the frozen expectation.
- `procedure-018`, `procedure-025`, `procedure-026`, and `procedure-027`:
  returned `clarification_required` for underspecified tasks, with different
  clarification wording and missing-field labels than the frozen expectation.
- `oos-005`, `compat-024`, and `conflict-008` also missed once each across the
  three runs; their per-run diagnostics remain in the canonical artifact.

## Canonical artifacts

- `data/evaluation/deepseek-provider-smoke-v1.json`
- `data/evaluation/baseline-results-v1.json`
- `data/evaluation/acceptance-report-v1.json`

Checksums from the accepted run:

```text
1f1a9a2e5e35d4715c6b304b95266c6bae298fbb0afd23749676c457866c0809  data/evaluation/baseline-results-v1.json
26a8a582a3a0784700719f5981a5f1a3664b76505a2fb31decc8063dc3add467  data/evaluation/acceptance-report-v1.json
d5ee25dc2e6192ac3817497048abd074808b85597bd4fd5f5531bbdb4dbad7fe  data/evaluation/deepseek-provider-smoke-v1.json
```
