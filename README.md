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

## Specification, compatibility, and procedure tracers

Download the original hash-verified source PDFs into the local `pdf-doc`
directory, ingest the structured and retrieval evidence, and ask a question:

```bash
./.venv/bin/python -m zabm download
./.venv/bin/python -m zabm ingest
./.venv/bin/python -m zabm ask \
  "What torque should I use for the RockShox Reverb Standard Remote clamp bolt?"
./.venv/bin/python -m zabm ask \
  "Is a Reverb Stealth hose barb with barb sleeve compatible with a Reverb Stealth A2 seatpost?"
./.venv/bin/python -m zabm ask \
  "What are the steps for hose sizing and remote installation?"
```

Add `--json` to any command for structured output. Original PDFs are stored in
`pdf-doc/` and generated evidence is stored under `.zabm/`. Both are local
artifacts and are never committed.

Compatibility answers use only human-verified manufacturer rules and return
`compatible`, `not_compatible`, `unknown`, or `not_found`. Dimensional matches
or visually similar names without an explicit rule do not produce a definitive
compatibility result.

Procedure answers use only page-structured retrieval evidence. A procedure is
returned only when its numbered steps form a complete source-defined sequence;
every step carries its own citation and attached warnings. A truncated or
uncertain sequence returns `not_found` without partial steps. Inspect the
selected procedure evidence with:

```bash
./.venv/bin/python -m zabm evidence \
  "What are the steps for hose sizing and remote installation?"
```

## Local grounded model path

By default, `zabm ask` uses the deterministic local evidence renderer and needs
no network service. To use a local open-weight model through an
OpenAI-compatible server, configure both the chat and embedding model
identifiers:

```bash
./.venv/bin/python -m zabm ask \
  "What torque should I use for the RockShox Reverb Standard Remote clamp bolt?" \
  --provider openai-compatible \
  --provider-url http://127.0.0.1:8000/v1 \
  --model local-open-weight-model \
  --embedding-model local-embedding-model \
  --provider-configuration local-v1
```

The same values can be supplied with `ZABM_PROVIDER`,
`ZABM_PROVIDER_URL`, `ZABM_MODEL`, `ZABM_EMBEDDING_MODEL`, and
`ZABM_PROVIDER_CONFIGURATION`. `ZABM_PROVIDER_API_KEY` is read only from the
environment and is never written to a response.

The provider may phrase validated claims only. It must return one sentence for
each supplied claim identifier; missing, extra, or malformed sentences and
numbers absent from the claim evidence cause the response to be rejected.
Provider, model, embedding model, configuration, and source-pack identifiers
are recorded in every canonical response.

Questions outside bicycle maintenance return `out_of_scope` before evidence or
model access. Missing or ambiguous identity details return
`clarification_required`; false-premise components and specifications return
`not_found` without a nearby substitute.

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
