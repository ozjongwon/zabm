# Bicycle Mechanics Assistant

This repository is bootstrapped for the evidence-gated bicycle maintenance
assistant described in [REQUIREMENT.md](REQUIREMENT.md) and the
[implementation spec](.scratch/bicycle-mechanics-assistant-v1/spec.md).

## Supported development machines

The bootstrap supports Debian 13 and Ubuntu 24.04 on x86_64. It installs the
system build prerequisites, uv 0.8.22, managed Python 3.13.5, and hash-locked
Python packages into `.venv`.

Run the development installer from the repository root:

```bash
./scripts/install-dev.sh
```

The installer is safe to re-run. It replaces the generated `.venv` so the
result is determined by the lock files rather than earlier workspace state.
Use `--dry-run` to validate platform and dependency inputs without changing the
machine.

A runtime-only environment can be prepared with:

```bash
./scripts/install-dev.sh --profile runtime
```

The runtime profile installs only `requirements/runtime.lock`. Development,
test, and evaluation dependencies stay in separate lock files and are installed
only by the development profile.

## Checks

```bash
./.venv/bin/python -m zabm health
./.venv/bin/python -m pytest
make verify
```

`make verify` runs the CLI health check, Ruff lint and formatting checks,
Pyright type checking, and the automated test suite.

## NVIDIA prerequisite

The installer detects `nvidia-smi` but never installs, upgrades, or replaces the
kernel GPU driver. If a machine has NVIDIA hardware and `nvidia-smi` is missing,
install the NVIDIA driver from the Debian or Ubuntu packages recommended for
that kernel, reboot, and verify `nvidia-smi` before running GPU model or
embedding workloads. CPU-only development can proceed without it.

## Environment changes

Dependency versions live in `.python-version`, `pyproject.toml`, and the four
files under `requirements/`. Any version change must update the matching
hash-locked file and be verified with a clean install. Credentials and generated
source data are never part of the installation path or committed files.
