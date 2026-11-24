# Development bootstrap acceptance

Use this procedure on throwaway Debian 13 and Ubuntu 24.04 x86_64 hosts. Run
it from a fresh clone with no existing `.venv`, managed Python, or uv binary.
Record the host image name and date with the command outputs.

## Prerequisites

- A clean Debian 13 or Ubuntu 24.04 x86_64 machine.
- Root or passwordless `sudo` for distribution packages.
- Network access to Debian or Ubuntu package mirrors, Astral's pinned uv
  installer, and the Python package index.
- A working `git` installation and enough disk space for the managed Python
  environment and source PDFs.

Do not pre-install Python, uv, test dependencies, or evaluation dependencies.
The NVIDIA driver is the only GPU prerequisite. The installer reports a missing
driver but does not install or replace it.

## Development profile

```bash
git clone <repository-url> zabm-bootstrap
cd zabm-bootstrap
./scripts/install-dev.sh
./.venv/bin/python -m zabm health --json
.venv/bin/python -m pytest -q 2>&1 | tail -30
```

Retain the successful health JSON and pytest summary. The health command must
report Python 3.13.5 and the pinned runtime dependency versions.

Run the installer a second time on the same host:

```bash
./scripts/install-dev.sh
./.venv/bin/python -m zabm health
.venv/bin/python -m pytest -q tests/test_cli_health.py
```

The second run must leave a working environment without adding development
tools through the runtime profile. Confirm the installation did not create
tracked credentials or generated source data:

```bash
git status --short
git ls-files .zabm pdf-doc .venv .env credentials secrets
```

Only intentional source changes may appear in `git status`; the second command
must print nothing.

## Runtime profile

This narrower profile installs the locked application environment and runtime
packages only. It is not the complete target installer. Use
`./scripts/install-runtime.sh` for the model server, external weights, evidence
stores, and installed-target smoke.

Use a second fresh checkout so the development environment remains available
for comparison:

```bash
git clone <repository-url> zabm-runtime
cd zabm-runtime
./scripts/install-dev.sh --profile runtime
./.venv/bin/python -m zabm health
./.venv/bin/python -c 'import pytest' 2>/dev/null && exit 1 || true
```

The import check must fail because runtime dependencies do not include pytest.
The runtime profile still installs the application CLI and pinned runtime
packages.

## Evidence record

Capture at minimum:

- host image and architecture;
- installer command and exit status;
- `uv --version`, Python version, and health JSON;
- development pytest summary;
- second-run result;
- runtime-only pytest exclusion result;
- any NVIDIA warning and the operator's prerequisite follow-up.
