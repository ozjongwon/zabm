# LangSmith evaluation acceptance

Use this procedure to prove that a completed evaluation was mirrored to
LangSmith without making LangSmith a dependency of the canonical local run.
The API key is read only from the process environment. Never put it in a
command-line argument, the evaluation artifact, the repository, or captured
command output.

## Configure the mirror

Enter the key without echoing it:

```bash
read -rsp "LangSmith API key: " LANGSMITH_API_KEY
printf '\n'
export LANGSMITH_API_KEY
export LANGSMITH_TRACING="true"
export LANGSMITH_PROJECT="zabm-evaluation-acceptance"
```

The optional settings are:

| Variable | Default | Purpose |
| --- | --- | --- |
| `LANGSMITH_ENDPOINT` | `https://api.smith.langchain.com` | LangSmith API endpoint |
| `LANGSMITH_PROJECT` | `zabm-evaluation` | Project receiving the traces |
| `LANGSMITH_TRACING` | disabled unless set to `true` | Explicitly enables mirroring |
| `LANGSMITH_TIMEOUT_SECONDS` | `10` | Total deadline for the mirror operation, capped at `60` |

`LANGCHAIN_API_KEY`, `LANGCHAIN_ENDPOINT`, and `LANGCHAIN_PROJECT` are accepted
as aliases for environments that already use the older names.

## Run and prove success

Run the normal evaluation command and preserve its status and diagnostics:

```bash
set +e
./.venv/bin/python -m zabm evaluation \
  --output /tmp/zabm-evaluation-langsmith.json \
  2>/tmp/zabm-langsmith.log
evaluation_status=$?
set -e

test "$evaluation_status" -eq 0
test -s /tmp/zabm-evaluation-langsmith.json
grep -F "LangSmith mirror completed:" /tmp/zabm-langsmith.log
! grep -F "observability warning:" /tmp/zabm-langsmith.log
! grep -Fq "$LANGSMITH_API_KEY" /tmp/zabm-langsmith.log
! grep -Fq "$LANGSMITH_API_KEY" /tmp/zabm-evaluation-langsmith.json
./.venv/bin/python -c '
import json

with open("/tmp/zabm-evaluation-langsmith.json", encoding="utf-8") as artifact:
    report = json.load(artifact)

assert report["artifact_version"] == "evaluation-results-v1"
assert report["langsmith_required"] is False
assert len(report["configurations"]) == 4
'
```

The success line reports the number of mirrored runs and the target project.
In LangSmith, open that project and verify:

- a root trace named `zabm-evaluation` with tag `zabm`;
- 12 configuration-run traces named
  `zabm-evaluation:<configuration>:run-<N>`;
- item traces named `zabm-evaluation-item:<configuration>:run-<N>:<item-id>`;
- provider, model, configuration, evaluation-set, and source-pack identifiers
  in every trace's metadata;
- the canonical response, grading result, latency, and retrieval metadata in
  item outputs.

Record the root trace ID, project name, local artifact SHA-256, command exit
status, and successful diagnostic line:

```bash
sha256sum /tmp/zabm-evaluation-langsmith.json
cat /tmp/zabm-langsmith.log
```

## Prove failure isolation

An unreachable mirror must produce a warning, not an evaluation failure. This
check uses a closed local port and keeps the local artifact:

```bash
set +e
LANGSMITH_ENDPOINT="http://127.0.0.1:9" \
LANGSMITH_TIMEOUT_SECONDS="0.2" \
./.venv/bin/python -m zabm evaluation \
  --output /tmp/zabm-evaluation-langsmith-unavailable.json \
  2>/tmp/zabm-langsmith-unavailable.log
unavailable_status=$?
set -e

test "$unavailable_status" -eq 0
test -s /tmp/zabm-evaluation-langsmith-unavailable.json
grep -F "observability warning:" /tmp/zabm-langsmith-unavailable.log
```

To exercise the fully disabled path, set `LANGSMITH_TRACING=false`; the
evaluation produces the same canonical local artifact without contacting
LangSmith.
