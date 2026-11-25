# Target runtime acceptance

Run this procedure on disposable Debian 13 and Ubuntu 24.04 x86_64 hosts. Start
from a fresh clone with no existing `.venv`, managed Python, uv, or generated
evidence. The default uses DeepSeek chat with local Ollama embeddings.

## Prerequisites

- Root or passwordless `sudo` for distribution packages.
- Network access to Debian or Ubuntu mirrors, Astral's pinned uv installer,
  the Python package index, GitHub release assets, and the frozen source-pack
  URLs.
- Enough space outside the runtime home for the Python environment, source
  PDFs, and evidence stores.
- For local Ollama: a working NVIDIA kernel driver for GPU execution, Ollama
  v0.40.18 installed under `/home/ollama` or exposed through
  `ZABM_OLLAMA_BIN`, active `ollama.service`, and at least one installed model.
  The installer validates `nvidia-smi -L` and does not replace the driver.
- For remote access: credentials for DeepSeek, OpenAI, or another
  OpenAI-compatible endpoint. The installer prompts without echoing the key.
- The default DeepSeek profile also requires local Ollama v0.40.18, an active
  `ollama.service`, and an installed embedding model.

Inspect the plan first:

```bash
./scripts/install-runtime.sh --dry-run
```

The plan must identify the selected provider and models. For local Ollama it
must also identify v0.40.18 and active `ollama.service` as external
prerequisites. The plan must state that no downloads or imports occur.

## Install

```bash
./scripts/install-runtime.sh
./.venv/bin/python -c 'import pytest' 2>/dev/null && exit 1 || true
```

The import check must fail. The installer must finish with the CLI health
check, selected-provider smoke, source/evidence verification, one supported CLI
answer, and the same answer through the web endpoint. It must not install,
start, stop, enable, disable, or rewrite Ollama or its systemd unit.

The following generated paths are outside the repository and must not appear
in `git status`:

- `${XDG_CONFIG_HOME:-$HOME/.config}/zabm/runtime.env`
- `/home/ollama/models`
- `/home/ollama/state`
- `~/.local/bin/zabm-runtime`

The provider and models can be changed again without reinstalling the runtime:

```bash
./scripts/select-runtime-models.sh
```

## Verify the installed commands

```bash
zabm-runtime ask \
  "What torque should I use for the RockShox Reverb Standard Remote clamp bolt?" \
  --json
zabm-runtime web --data-dir .zabm
```

Open the reported loopback URL and ask the same question. Both responses must
be `supported`, with claims and citations, and must identify the selected
provider and models.

Run the automated installed-target checks independently:

```bash
./scripts/runtime-smoke.sh
if [[ "${ZABM_RUNTIME_PROVIDER_KIND:-}" == "local" ]]; then
  sudo systemctl status ollama.service
  sudo journalctl --unit ollama.service --lines 50
fi
```

## Idempotence

Run the installer a second time:

```bash
./scripts/install-runtime.sh
```

The second run must preserve the selected provider and models, leave permission
mode `600` on `runtime.env`, and pass the same smoke checks. For local Ollama,
`ollama.service` must remain active. The run must not add development, test, or
evaluation Python packages. Confirm `~/.local/bin/zabm-runtime` is replaced in
place rather than duplicated.

## Evidence record

Capture at minimum:

- host image, architecture, date, and kernel;
- `nvidia-smi -L` output or the installer's prerequisite warning;
- dry-run plan and both installer exit statuses;
- installed Ollama and Python versions, when using local models;
- selected provider, model names, and generated provider identity;
- CLI `health --json`, provider smoke, supported answer envelope, and web
  endpoint response;
- second-run result and the pytest-import exclusion result;
- `git status --short`, which must contain only intentional source changes.
