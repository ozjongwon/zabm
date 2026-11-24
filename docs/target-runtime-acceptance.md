# Target runtime acceptance

Run this procedure on disposable Debian 13 and Ubuntu 24.04 x86_64 hosts. Start
from a fresh clone with no existing `.venv`, managed Python, uv, model weights,
or generated evidence. Ollama is a separately installed prerequisite.

## Prerequisites

- Root or passwordless `sudo` for distribution packages.
- Network access to Debian or Ubuntu mirrors, Astral's pinned uv installer,
  the Python package index, GitHub release assets, Hugging Face model files,
  and the frozen source-pack URLs.
- Enough space outside the runtime home for the Python environment, source
  PDFs, and evidence stores. The installer verifies the large runtime-home
  requirement separately.
- A working NVIDIA kernel driver for GPU execution. The installer validates
  `nvidia-smi -L` and does not install or replace the driver.
- At least 12 GiB free on the runtime-home filesystem. The installer checks
  this before downloading model weights.
- Ollama v0.40.18 installed under `/home/ollama` or exposed through
  `ZABM_OLLAMA_BIN`, with `ollama.service` enabled and active.
- `/home/ollama` keeps its existing owner and group. Missing write access for
  the invoking user is granted through a POSIX ACL.

Inspect the plan first:

```bash
./scripts/install-runtime.sh --dry-run
```

The plan must identify Ollama v0.40.18 and active `ollama.service` as external
prerequisites, and name the Qwen chat model and BGE embedding model with
SHA-256 values, the model directory, runtime-only dependency profile, and
installed-target smoke checks.

## Install

```bash
./scripts/install-runtime.sh
./.venv/bin/python -c 'import pytest' 2>/dev/null && exit 1 || true
```

The import check must fail. The installer must finish with the CLI health
check, local chat and embedding provider smoke, source/evidence verification,
one supported CLI answer, and the same answer through the web endpoint.
It must not install, start, stop, enable, disable, or rewrite Ollama or its
systemd unit.

The following generated paths are outside the repository and must not appear
in `git status`:

- `${XDG_CONFIG_HOME:-$HOME/.config}/zabm/runtime.env`
- `/home/ollama/models`
- `/home/ollama/state`
- `~/.local/bin/zabm-runtime`

Model weights are deliberately separate from the installer binary and runtime
configuration:

```bash
./scripts/fetch-runtime-models.sh
```

## Verify the installed commands

```bash
zabm-runtime ask \
  "What torque should I use for the RockShox Reverb Standard Remote clamp bolt?" \
  --json
zabm-runtime web --data-dir .zabm
```

Open the reported loopback URL and ask the same question. Both responses must
be `supported`, with claims and citations, and must identify the local
`openai-compatible` provider and pinned model names.

Run the automated installed-target checks independently:

```bash
./scripts/runtime-smoke.sh
sudo systemctl status ollama.service
sudo journalctl --unit ollama.service --lines 50
```

## Idempotence

Run the installer a second time:

```bash
./scripts/install-runtime.sh
```

The second run must reuse the externally managed Ollama service and imported
models, leave `ollama.service` active, leave permission mode `600` on
`runtime.env`, and pass the same smoke checks. It must not add development,
test, or evaluation Python packages. Confirm `~/.local/bin/zabm-runtime` is
replaced in place rather than duplicated.

## Evidence record

Capture at minimum:

- host image, architecture, date, and kernel;
- `nvidia-smi -L` output or the installer's prerequisite warning;
- dry-run plan and both installer exit statuses;
- installed Ollama and Python versions;
- model filenames and SHA-256 values;
- CLI `health --json`, provider smoke, supported answer envelope, and web
  endpoint response;
- second-run result and the pytest-import exclusion result;
- `git status --short`, which must contain only intentional source changes.
