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

## Local web chat

Start the minimal local web chat against the generated evidence directory:

```bash
./.venv/bin/python -m zabm web --data-dir .zabm
```

Open <http://127.0.0.1:8765>. The server binds to the loopback interface by
default. Use `--host` and `--port` to change the binding, including `--port 0`
to select an available port. Provider options match `zabm ask`, so the web chat
uses the same deterministic default or selected remote provider.

The browser posts to `/api/ask`, which returns the complete canonical response
envelope. The web page only presents that envelope: it does not retrieve
evidence, decide compatibility, verify numbers, or choose refusal statuses.
Supported responses show claims and citations with document, printed page,
physical page, section, and retrieval date. Refusals suppress answer
components, while conflicts show every candidate source and any cited
precedence.

See [Web chat acceptance](docs/web-chat-acceptance.md) for the procedure that
compares the web and CLI behavior.

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

## PDF ingestion profiles

Retrieval ingestion uses the versioned profile manifest at
`data/ingestion/profiles-v1.json`. The default `standard-en` profile applies to
ordinary English documents. A source manifest can select another profile
explicitly:

```json
{
  "id": "example-source",
  "ingestion_profile": {
    "id": "two-column-en",
    "version": "1"
  }
}
```

It can instead supply metadata matched by a profile selector:

```json
{
  "id": "example-source",
  "ingestion_metadata": {
    "layout_family": "two-column"
  }
}
```

Select a different profile manifest during ingestion with
`--ingestion-profiles /path/to/profiles.json`. Profiles are declarative,
versioned data for page-classification exceptions, column and language regions,
heading rules, table and figure exclusions, procedure end boundaries, and
action aliases. Unknown profile or schema versions, ambiguous metadata
selection, and invalid overrides fail ingestion before any generated evidence
is written.

Figure-only, callout-only, and text-free or scanned pages remain inspectable in
the generated catalog but receive the `transcription-required` ingestion
outcome and do not produce procedures. Human transcriptions are loaded from the
separate artifact selected with `--transcriptions`; the default is the empty
`data/evidence/verified-transcriptions.json`. Each transcription records its
document, physical and printed pages, section and heading path, source box,
contiguous numbered steps with source boxes, attached warnings, an explicit end
boundary, and a named reviewer and verification date.

Only entries with `verification.status` set to `human_verified` are accepted,
and their procedures use the separate `verified-transcription` evidence plane.
Unverified OCR or vision output is preserved under the page's
`unverified_transcriptions` field but remains ineligible for answers. The
ingestion report lists pages awaiting transcription under
`transcription_required_pages`, and accepted artifact pages use the
`transcription-verified` outcome. The artifact SHA-256 is recorded in ingestion
provenance; malformed verified entries fail ingestion closed.

Extraction preserves per-span font name, size, weight/style hints, normalized
and raw text, line and span IDs, and both normalized and page-point bounding
boxes. Declared column bands are read in profile order; otherwise deterministic
column-gap detection supplies automatic bands. Configured language regions and
limited script/word-hint detection keep multilingual columns separate. Use
`--language de` with `zabm ingest` to prefer another language over each
profile's primary language.

Every generated `retrieval.json` records the parser version, profile schema and
manifest versions, the profile-manifest SHA-256, and each source's selected
profile ID, version, and canonical profile SHA-256. It also records the pinned
`pypdf` and `fonttools` versions used for extraction. These fields also appear
in the `zabm ingest --json` report. The retrieval catalog additionally records
the source-manifest and per-source SHA-256 values, while the ingestion report
records SHA-256 checksums for the three canonical generated artifacts.

Use `zabm ingest --diagnostics` to inspect page classifications, confidence and
outcome, detected columns and languages, headings, and accepted or rejected
candidate steps. The JSON report and `generated/ingestion-report.json` contain
the same diagnostics without dumping full page text. Normal ingestion reports
accepted and rejected candidate-step counts, grouped by rejection reason.

When the parser version, PDF dependencies, profile schema or content, source
manifest, or transcription evidence differs from the existing retrieval
catalog, ingestion stops before writing derived evidence. Review the listed
provenance changes, then repeat the command with `--rebuild-review
<review-reference>`. A completed build records whether it was an initial build,
unchanged, or reviewed, and the new retrieval checksum is reported with the
other canonical artifacts. Any such rebuild requires a replacement source-pack
freeze, a rerun of the retrieval smoke set, and a complete evaluation rerun.

## Local grounded model path

By default, `zabm ask` uses the deterministic local evidence renderer and needs
no network service. Its bounded prototype router classifies the request family
from multilingual exemplars; no family-specific English cue list chooses the
answer path. Select one of four provider modes with `--provider`:

| Provider | Purpose |
| --- | --- |
| `deterministic` | Offline evidence renderer; no model request. |
| `openai-compatible` | Custom/local endpoint with an explicit URL and model. |
| `openai` | OpenAI API preset using `OPENAI_API_KEY`. |
| `deepseek` | DeepSeek API preset using `DEEPSEEK_API_KEY`. |

To use a local open-weight model through an OpenAI-compatible server, configure
both the chat and embedding model identifiers:

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

When a model provider is configured, its first call is a validated
request-routing call. The route returns an intent, a normalized English
evidence query, recognized entities, and any missing or ambiguous fields.
Application code validates that route before loading evidence. Ambiguous
families and missing identity fields return `clarification_required`; the model
cannot set terminal status, compatibility outcome, citations, claim links,
numeric acceptance, or procedure completeness. Every response records the
`structured-intent-v1` routing strategy alongside the provider, model, and
configuration identity.

Use the DeepSeek preset with its default `deepseek-flash` model and
`https://api.deepseek.com` endpoint:

```bash
export DEEPSEEK_API_KEY="..."

./.venv/bin/python -m zabm ask \
  "What torque should I use for the RockShox Reverb Standard Remote clamp bolt?" \
  --provider deepseek
```

Override the DeepSeek endpoint or model with `--provider-url`/`DEEPSEEK_BASE_URL`
and `--model`/`DEEPSEEK_MODEL`. The OpenAI preset similarly defaults to
`https://api.openai.com/v1`, requires `OPENAI_API_KEY`, accepts
`OPENAI_MODEL`, and defaults to the `text-embedding-3-small` embedding model.
DeepSeek has no configured embedding model by default, so its identity records
`not-configured`; current RAG evaluation uses the deterministic local page
vectors and does not request DeepSeek embeddings.

CLI values take precedence over provider-specific environment variables. The
generic `ZABM_PROVIDER_API_KEY` can override either typed API key. Named
provider identities, model, embedding model, and configuration are recorded in
every canonical response.

Enable interaction tracing with `--debug` or `ZABM_DEBUG=1`:

```bash
./.venv/bin/python -m zabm ask \
  "What are the steps for Test Function?" \
  --provider deepseek \
  --model deepseek-flash \
  --debug
```

Debug events are written to stderr so `--json` output remains machine-readable.
They use three logger names:

- `zabm.llm`: chat request messages, model/provider/seed, response content, and
  embedding requests when used.
- `zabm.agent`: question routing and canonical response summaries.
- `zabm.rag`: procedure candidates, BM25/vector retrieval, and final
  reciprocal-rank-fusion output during hybrid evaluation.

API keys are never logged. A terminal evidence failure does not produce an LLM
answer-generation request, so a `not_found` response may show request-routing
and RAG events without a phrasing request.

### Remote-provider smoke procedure

Use the ignored local environment file for evaluator credentials; never put a
key in a tracked profile or command transcript. `.env.example` lists every
supported provider variable and is safe to copy:

```bash
cp .env.example .env.local
# Fill OPENAI_API_KEY and OPENAI_MODEL in the ignored .env.local file.
set -a
. ./.env.local
set +a
```

With the source pack downloaded and ingested, exercise the remote provider
through the normal answer path and retain the canonical response:

```bash
./.venv/bin/python -m zabm ask \
  "What torque should I use for the RockShox Reverb Standard Remote clamp bolt?" \
  --provider openai \
  --provider-configuration openai-live-smoke-v1 \
  --json > /tmp/zabm-openai-smoke.json
```

The smoke passes when the command exits zero, the response has
`"provider": "openai"`, the selected model and source-pack version are present,
and the response contains citations for any supported claim. Authentication,
timeout, and malformed-response failures exit nonzero with a
`zabm ask: provider ...` error and do not print a fallback answer.

Exercise both halves of the provider interface with the operational smoke
command:

```bash
./.venv/bin/python -m zabm provider-smoke \
  --provider openai \
  --provider-configuration openai-live-smoke-v1 \
  --json
```

It reports provider/model/configuration identity plus chat and embedding
request latency. A timeout, unavailable endpoint, malformed completion, or
embedding count/shape mismatch exits nonzero without printing a success report.

For remote latency and provenance, run the deterministic evaluation fixture
with the same provider profile. The artifact records the provider, model,
configuration, source-pack version, and latency spread together:

```bash
./.venv/bin/python -m zabm evaluation \
  --evaluation-set data/evaluation/baseline-fixture-v1.json \
  --output /tmp/zabm-openai-evaluation-smoke.json \
  --provider openai \
  --provider-configuration openai-live-smoke-v1
```

The DeepSeek preset follows the same `ask` and evaluation procedure with
`--provider deepseek` and `DEEPSEEK_API_KEY`. It records
`embedding_model: "not-configured"` by default. Run the embedding smoke only
when `DEEPSEEK_EMBEDDING_MODEL` names a model supported by that endpoint.

The provider may phrase validated claims only. It must return one sentence for
each supplied claim identifier; missing, extra, or malformed sentences and
numbers absent from the claim evidence cause the response to be rejected.
Provider, model, embedding model, configuration, and source-pack identifiers
are recorded in every canonical response.

Questions outside bicycle maintenance return `out_of_scope` before evidence
access. Missing or ambiguous identity details return `clarification_required`;
false-premise components and specifications return `not_found` without a nearby
substitute. Evaluation artifacts record the routing version and strategy used
for the run.

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
page and reason. It becomes answerable only through a human-verified entry in
the transcription artifact selected by `--transcriptions`, which binds each
step to its source page and box and records the reviewer and verification date.
Unverified transcriptions remain ineligible. Incomplete procedures remain
`not_found`; the coverage inventory keeps their completeness or citation
defects inspectable.

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

Evaluation accepts the same provider profiles:

```bash
export DEEPSEEK_API_KEY="..."

./.venv/bin/python -m zabm evaluation --provider deepseek
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
