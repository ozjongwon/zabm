# Target runtime acceptance

Run this procedure on disposable Debian 13 and Ubuntu 24.04 x86_64 hosts. Start
from a fresh clone with no existing `.venv`, managed Python, uv, Ollama, model
weights, or generated evidence.

## Prerequisites

- Root or passwordless `sudo` for distribution packages.
- Network access to Debian or Ubuntu mirrors, Astral's pinned uv installer,
  the Python package index, GitHub release assets, Hugging Face model files,
  and the frozen source-pack URLs.
- About 6 GB free for the Python environment, pinned Ollama package, model
  files, source PDFs, and evidence stores.
- A working NVIDIA kernel driver for GPU execution. The installer validates
  `nvidia-smi -L` and does not install or replace the driver.

Inspect the plan first:

```bash
./scripts/install-runtime.sh --dry-run
```

The plan must name Ollama v0.40.18, the Qwen chat model and BGE embedding model
with SHA-256 values, an external model directory, the runtime-only dependency
profile, and the installed-target smoke checks.

## Install

```bash
./scripts/install-runtime.sh
./.venv/bin/python -c 'import pytest' 2>/dev/null && exit 1 || true
```

The import check must fail. The installer must finish with the CLI health
check, local chat and embedding provider smoke, source/evidence verification,
one supported CLI answer, and the same answer through the web endpoint.

The following generated paths are outside the repository and must not appear
in `git status`:

- `${XDG_CONFIG_HOME:-$HOME/.config}/zabm/runtime.env`
- `${XDG_DATA_HOME:-$HOME/.local/share}/zabm-runtime/models`
- `${XDG_DATA_HOME:-$HOME/.local/share}/zabm-runtime/server`
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
```

## Idempotence

Run the installer a second time:

```bash
./scripts/install-runtime.sh
```

The second run must reuse the pinned server and imported models, leave one
runtime server process, leave permission mode `600` on `runtime.env`, and pass
the same smoke checks. It must not add development, test, or evaluation Python
packages. Confirm `~/.local/bin/zabm-runtime` is replaced in place rather than
duplicated.

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
