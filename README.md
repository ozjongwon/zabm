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

When two or more applicable specification values or compatibility rules
disagree, the CLI returns `conflicting_evidence` with every candidate claim,
excerpt, and citation. It does not average, interpolate, or select a value from
confidence or matching dimensions. A human-verified evidence record may include
an optional `precedence` object when the cited source explicitly supports one
candidate:

```json
{
  "precedence": {
    "kind": "supersession",
    "supersedes": ["earlier-evidence-id"],
    "reason": "Revision C supersedes Revision B for this torque.",
    "source_id": "source-id",
    "citation": {
      "printed_page": 36,
      "physical_page": 32,
      "section": "Torque table"
    },
    "evidence_excerpts": ["Revision C supersedes Revision B for this torque."]
  }
}
```

The supported kinds are `model_scope`, `supersession`, `revision_date`, and
`manufacturer_scope`. The precedence excerpt must be present at its cited
location and must itself state the precedence; otherwise the precedence is
ignored and the conflict remains unresolved. A resolved response keeps the
selected and rejected candidates plus the cited reason in `conflicts`.

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

## Candidate source pack

The frozen pack is versioned by `data/manifests/source-pack-v1.json`. It
contains six public, first-party manufacturer documents from SRAM, RockShox,
and MAGURA:

- Reverb hydraulic hose replacement and remote bleed service manual.
- Reverb AXS user manual.
- SRAM Eagle, Flattop, and 11-speed chain-compatible tools map.
- 2011 RockShox technical manual.
- MAGURA GUSTAV PRO owner's manual.
- MAGURA MT A2 user instructions.

Together these sources provide specification values and conditions,
compatibility tables, complete and partial procedure sections, warnings, and
adjacent model or generation cases for evaluation work.

The candidate review is recorded in
`data/audits/source-pack-candidates-v1.json`. It records authority, public
availability, extraction, page alignment, headings, tables, warnings, and
procedure-order checks for every candidate. Two local-only candidates were
excluded because they could not be reacquired from a public manufacturer URL;
one was also encrypted and unreadable by the ingestion profile.

Build the candidate pack from empty `pdf-doc/` and `.zabm/` directories:

```bash
./scripts/download-sources.sh
./scripts/ingest-sources.sh
```

The acquisition wrapper installs the pinned development environment when
`.venv` is absent, then runs the `download` CLI. It verifies every pinned
SHA-256 before moving a source into `pdf-doc/`. The ingestion wrapper verifies
the source set again before creating any derived store. Add `--json` to either
script to receive its canonical report.

The JSON reports include source and manufacturer counts, source
provenance, page-alignment counts, table/warning/procedure counts, validation
issues, and SHA-256 checksums for the three canonical generated artifacts.
Re-running both commands from a clean generated-data state produces identical
artifact bytes and checksums.

## Verified coverage

The coverage set in `data/coverage/coverage-v1.json` exercises the CLI across
every document in the frozen source pack. It contains accepted specification,
compatibility, and complete-procedure questions plus per-document rejection
cases. Run it after ingestion:

```bash
./.venv/bin/python -m zabm coverage
```

The command exits nonzero unless every frozen source has at least one accepted
case that returns a supported claim and citation, and at least one rejected or
explicitly unanswerable case. `--json` emits the full report, including observed
claim IDs, physical page locators, rejection messages, structured-evidence
eligibility, and every rejected or incomplete procedure candidate.

Figure-only material is listed under `unanswerable_content` with its source
page and reason. It remains answerable only after a human transcribes the
content, attaches an exact citation, and records verification in the structured
evidence file. Incomplete procedures remain `not_found`; the coverage inventory
keeps their completeness or citation defects inspectable.

## Frozen evaluation set

The hand-authored evaluation set in
`data/evaluation/evaluation-set-v1.json` contains exactly 120 scored items:
36 specifications, 27 compatibility questions, 27 procedures, 15 not-found
cases, 8 conflicting-evidence cases, and 7 out-of-scope requests. It includes
adjacent models, wrong generations, cross-brand pairs, unsupported materials,
missing attributes, truncated procedures, ambiguous aliases, and false
premises. Specification labels include normalized values, ranges, units, and
required qualifiers; compatibility labels include exact statuses and
outcomes; and procedure labels include every required step and attached
warning.

Validate the set and its source locators:

```bash
make evaluation-set
```

The freeze record in `data/evaluation/evaluation-freeze-v1.json` binds the set
bytes to the frozen source-pack descriptor and manifest. `zabm evaluation-set`
verifies that record by default. Changing a question or expected outcome
requires a reviewed replacement freeze and a complete evaluation rerun:

```bash
./.venv/bin/python -m zabm evaluation-set \
  --freeze data/evaluation/evaluation-freeze-v1.json \
  --maintainer-review <review-reference>
```

No answer-accuracy baseline is run by this command.

## Baseline ladder

Run LLM-only, plain RAG, hybrid retrieval, and the full agent under the same
frozen questions, provider, prompt budget, decoding settings, and runtime:

```bash
make evaluation
```

The command verifies the default evaluation-set and source-pack freezes,
runs every configuration three times at temperature zero with recorded seeds,
and writes `data/evaluation/baseline-results-v1.json`. Every run remains in the
artifact. Accuracy and latency spreads are calculated from those runs rather
than replacing them with a best result.

Run the small deterministic fixture suite for a quicker end-to-end check:

```bash
make evaluation-fixture
```

The fixture is `data/evaluation/baseline-fixture-v1.json`; its canonical output
is `data/evaluation/baseline-fixture-results-v1.json`. The fixture covers a
supported specification, compatibility result, complete procedure, not-found
case, and out-of-scope request across all four configurations and three runs.

The report grades specification values, ranges, units, and qualifiers;
compatibility outcomes and statuses exactly; and procedures through a
reviewable per-step and per-warning checklist with deterministic pass/fail.
Every supported response also records citation validity and any unsupported
numbers. Recall@5 and MRR are reported independently from answer accuracy, and
item results identify retrieval failures separately from answer-generation
failures. Provider, model, configuration versions, source-pack version,
hardware, runtime, and latency are recorded in the artifact.

To use the same OpenAI-compatible provider for the baseline prompts and full
agent phrasing, pass the provider options accepted by `zabm ask`:

```bash
./.venv/bin/python -m zabm evaluation \
  --provider openai-compatible \
  --provider-url http://127.0.0.1:8000/v1 \
  --model local-open-weight-model \
  --embedding-model local-embedding-model \
  --provider-configuration local-evaluation-v1
```

LangSmith is not imported or required. The canonical local JSON artifact is
written before any optional remote mirroring.

## Retrieval-only freeze

Retrieval usability is checked before answer-accuracy work with a fixed
16-item smoke set covering specification, compatibility, and procedure
evidence. The smoke set and paths are predeclared in
`data/retrieval-smoke/`; they do not call an answer model or score answers.

Run both paths and write the canonical report:

```bash
./.venv/bin/python -m zabm retrieval-smoke
```

The accepted `page-bm25-title-section` path reaches 100% Recall@5. The
`page-token-overlap-title-section` comparison reaches 68.8%; both are recorded
separately, and the threshold decision requires at least one path at or above
85%.

Freeze the manifest, smoke set, retrieval configuration, and report together:

```bash
./.venv/bin/python -m zabm retrieval-smoke \
  --freeze data/manifests/source-pack-freeze-v1.json \
  --candidate-audit data/audits/source-pack-candidates-v1.json \
  --maintainer-review <review-reference>
```

`zabm ingest` verifies the frozen descriptor before writing derived evidence.
Any change to the manifest, smoke inputs, report, or source hashes is rejected.
Changing a frozen source therefore requires an explicit manifest version,
maintainer review, and a complete evaluation rerun before a replacement freeze
can be accepted. Do not remove an included source merely because a later
answer baseline performs poorly.

Register every unregistered PDF already present in `pdf-doc/`:

```bash
./scripts/register-sources.sh
```

The filename stem becomes the source ID. Files whose stem is already present in
the manifest are skipped. Every readable unregistered PDF is added with
derived title, manufacturer, hash, retrieval date, and available revision
metadata. The manifest version is bumped and the normal ingestion command runs.

For public provenance, place a sidecar beside the PDF using either
`<filename>.source-url` or `<filename>.url` containing the original direct URL.
Without a sidecar, the manifest records the local file URI.

Use `--manufacturer "Manufacturer Name"` when the filename does not identify
the manufacturer. `--skip-ingest` registers without rebuilding, and
`--retrieval-date YYYY-MM-DD` overrides the recorded retrieval date.

Encrypted PDFs without a readable password and PDFs with no extractable text
are reported and left unregistered. Other readable PDFs in the same scan are
still registered, and the command exits nonzero while any file remains
rejected. Provide a directly readable text PDF or human-transcribed source for
those documents.

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
