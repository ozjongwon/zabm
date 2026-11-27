# v1 operational handoff

This page is the entry point for reviewing the v1 delivery. It connects the
installation procedures, reproducible source-pack rebuild, automated tests,
evaluation artifacts, adapter acceptance, empirical choices, and safety limits.
The canonical evidence remains in the referenced local artifacts; this page
does not replace them.

Accepted: 2026-11-26.

## Quickstart

For development on Debian 13 or Ubuntu 24.04 x86_64:

```bash
git clone <repository-url> zabm
cd zabm
./scripts/install-dev.sh
./.venv/bin/python -m zabm health
make verify
```

For an installed runtime:

```bash
git clone <repository-url> zabm
cd zabm
./scripts/install-runtime.sh
zabm-runtime ask \
  "What torque should I use for the RockShox Reverb Standard Remote clamp bolt?"
zabm-runtime web --data-dir .zabm
```

The runtime installer requires an externally managed Ollama service for local
embeddings unless a remote embedding endpoint is configured. It never installs,
starts, stops, or replaces Ollama or the NVIDIA driver. The complete clean-host
procedures and evidence to collect are in
[Development bootstrap acceptance](development-bootstrap-acceptance.md) and
[Target runtime acceptance](target-runtime-acceptance.md).

Operator acceptance of both installation paths is recorded in [GitHub Issues](https://github.com/ozjongwon/zabm/issues).

## Architecture

```text
CLI and web chat adapters
          |
          v
canonical application service
  routing -> evidence resolution -> deterministic validation -> response
      |              |                       |
      |              +-- human-verified specs and compatibility
      |              +-- complete retrieval procedures
      |
      +-- optional remote LLM for routing, phrasing, and reviewed translation

frozen source PDFs -> acquisition/hash verification -> ingestion/indexing
                                                        |
                                      canonical JSON evidence and local reports
```

The CLI and web chat call the same application service. The web page renders
the canonical response envelope and has no evidence, compatibility, numerical,
or refusal logic of its own.

Application code owns the response type, terminal status, compatibility
outcome, citations, claim-to-evidence references, numeric verification,
procedure completeness, and final acceptance. The model may route, rewrite,
select procedure evidence, phrase validated claims, and translate. Model output
cannot add a substantive sentence without a validated claim, set a terminal
status, or introduce a number absent from the attached evidence.

Specifications and compatibility rules use human-verified structured evidence.
Procedures use page-structured retrieval evidence only when the source defines
a complete sequence; every step and warning carries a citation. See the
[domain glossary](../GLOSSARY.md) and [architecture decisions](adr/) for the
authoritative vocabulary and decisions.

For module responsibilities, request and build lifecycles, extension recipes,
testing guidance, artifact ownership, and maintainability hotspots, see the
[maintainability, architecture, and extension guide](maintainability.md).

## Source selection

The frozen source pack in
[`data/manifests/source-pack-v1.json`](../data/manifests/source-pack-v1.json)
contains six first-party manufacturer documents from three manufacturers:
SRAM, RockShox, and MAGURA. It covers exact specifications, compatibility
tables, complete and partial procedures, warnings, and near-miss model and
generation cases.

The source-selection audit is
[`data/audits/source-pack-candidates-v1.json`](../data/audits/source-pack-candidates-v1.json).
Eight candidates were reviewed. Two were excluded:

- `MAGURA-MT_Owners-manual_EN` lacked a public direct manufacturer URL and had
  no complete source-defined procedure.
- `MT-Caliper-Installation-Instruction` had unconfirmed authority, no public
  provenance, and was encrypted beyond the configured extraction profile.

Sources were frozen before answer-accuracy baselines. The retrieval-only smoke
set has 16 items across specifications, compatibility, and procedures. The
frozen BM25 path retrieved the expected source page in 16/16 cases (100%
Recall@5); the token-overlap path retrieved 10/16 (62.5%). The frozen threshold
requires at least one path at 85% or higher. See
[`data/retrieval-smoke/report-v1.json`](../data/retrieval-smoke/report-v1.json)
and [`data/manifests/source-pack-freeze-v1.json`](../data/manifests/source-pack-freeze-v1.json).

## Reproducible rebuild

The two rebuild commands are:

```bash
./scripts/download-sources.sh
./scripts/ingest-sources.sh
```

Run them from a checkout with empty `pdf-doc/` and `.zabm/` directories.
Acquisition verifies all six SHA-256 values before moving PDFs into `pdf-doc/`.
Ingestion verifies the source-pack freeze again before writing derived data. A
normal source or manifest change fails closed; it requires manifest review and
a complete evaluation rerun.

Two independent clean ingestion runs into empty data directories produced
byte-identical artifacts. Their shared acceptance counts were:

| Check | Observed |
| --- | ---: |
| Sources / manufacturers | 6 / 3 |
| Parsed physical pages | 149 / 149 |
| Pages with extractable text | 149 |
| Missing-text pages | 0 |
| Specifications / eligible | 9 / 9 |
| Compatibility rules / eligible | 6 / 6 |
| Retrieval pages | 149 |
| Procedure candidates / complete | 17 / 2 |
| Table rows | 322 |
| Warning blocks | 16 |
| Validation issues | 0 |

Canonical generated artifact checksums from that rebuild:

```text
07e2e0f0660f152ee8d75c13dfc2e575f50285c1aa0372fd4f501566e6dd2865  specifications.json
9ad7f6d2fd1f3ae184a172724164e84da1b414af6f0a851fe13e8abe33a31326  compatibility.json
5026b52b60ffa369e15ef426b811d2753d8b956a9e8fae1b2b446a805f24fe5d  retrieval.json
```

The ingestion report also records parser, PDF library, font library, profile,
transcription-artifact, and source-manifest hashes. These diagnostics make
parser or profile changes visible instead of silently altering the evidence.

## Tests and evaluation protocol

The CLI is the sole automated test seam:

```bash
./.venv/bin/python -m zabm health
make verify
```

`make verify` runs health, Ruff lint and format checks, Pyright, and the full
pytest suite. CLI tests exercise supported specifications, all compatibility
outcomes, complete and incomplete procedures, citations, clarification,
conflicts and precedence, not found, out of scope, source verification,
ingestion reconstruction, provider boundaries, evaluation, and web rendering.

The frozen scoring set contains exactly 120 items:

| Category | Items |
| --- | ---: |
| Specification | 36 |
| Compatibility | 27 |
| Procedure | 27 |
| Not found | 15 |
| Conflicting evidence | 8 |
| Out of scope | 7 |

Each of the four configurations runs three times with seeds 0, 1, and 2 at
temperature zero. The prompt budget is 12,000 characters and retrieval top-k is
5. The configurations are LLM-only, plain RAG, hybrid retrieval, and full agent.
Accuracy and latency use the median-accuracy run; citation validity, abstention,
and fabricated-number checks pool all runs.

The accepted remote run used `deepseek-chat` for chat and Ollama
`mxbai-embed-large:latest` for embeddings. Its full-agent median accuracy was
94.17%, both paired-bootstrap improvement intervals were wholly above zero,
citation validity was 100%, correct abstention was 97.78%, no fabricated numeric
values were found, and latency was 2,041.80 ms median / 4,128.14 ms p95. All
acceptance gates passed.

Canonical acceptance artifacts:

```text
1f1a9a2e5e35d4715c6b304b95266c6bae298fbb0afd23749676c457866c0809  data/evaluation/baseline-results-v1.json
26a8a582a3a0784700719f5981a5f1a3664b76505a2fb31decc8063dc3add467  data/evaluation/acceptance-report-v1.json
d5ee25dc2e6192ac3817497048abd074808b85597bd4fd5f5531bbdb4dbad7fe  data/evaluation/deepseek-provider-smoke-v1.json
```

See [Remote LLM acceptance evidence](remote-llm-acceptance.md) for the exact
environment, commands, gate table, and retained item misses.

## CLI and web acceptance

Use the same evidence directory and provider settings for both adapters. Ask
each question through `zabm ask --json`, then compare it with the web page's
canonical response envelope. Request IDs and timestamps are intentionally
different.

| Outcome | Representative question |
| --- | --- |
| Supported specification with citation | What torque should I use for the RockShox Reverb Standard Remote clamp bolt? |
| Supported compatibility | Is a Reverb Stealth hose barb with barb sleeve compatible with a Reverb Stealth A2 seatpost? |
| Supported complete procedure | What are the steps for hose sizing and remote installation? |
| Clarification required | What torque should I use for the bolt? |
| Not found | What torque should I use for a Reverb unicorn clamp bolt? |
| Conflicting evidence | What is the Trail Post Standard Remote clamp bolt torque? |
| Out of scope | What bicycle should I buy for commuting? |

For supported answers, verify claims and citations, including document, printed
page, physical page, section, and retrieval date. For procedures, verify the
ordered steps and every attached warning. Refusals must not render substantive
answer components. Conflicts must show every candidate source and any cited
precedence. The conflict example requires the repository's conflict fixture
data; it is not present in the standard frozen pack.

See [Web chat acceptance](web-chat-acceptance.md) for the complete comparison
procedure and HTTP boundary checks.

## Empirical choice record

| Decision | Selected | Alternatives or rejected evidence |
| --- | --- | --- |
| Source pack | Six public first-party documents from three manufacturers | Two locally acquired MAGURA candidates had missing public provenance, unreadable extraction, or incomplete procedures and were excluded. |
| Retrieval | Page BM25 with title and section boosts, top-k 5 | Token overlap reached 62.5% Recall@5 versus 100% for BM25. At least one predeclared path had to reach 85%. |
| Chat provider | Remote `deepseek-chat` | The available 6 GB GPU could not finish the local model ladder. DeepSeek Flash spent bounded output on reasoning. Local chat remains a development option, not v1 evidence. |
| Embeddings | Independent Ollama `mxbai-embed-large:latest` endpoint | Chat and embedding providers are separate concerns. Remote OpenAI-compatible embeddings remain supported. |
| Evaluation decoding | Temperature 0; seeds 0/1/2; 12,000-character prompt budget; three runs | Three runs expose spread; one best run is not substituted for the reported result. |
| Full-agent enhancement | Validated routing, evidence-gated claims, deterministic status and citation checks | Full-agent improvement and confidence intervals are measured against LLM-only and plain RAG; no enhancement is accepted from an anecdote. |
| Safety facts | Human-verified structured evidence | Unverified model extraction is not eligible, even when extraction appears plausible. |
| Korean output | Reviewed opt-in capability, outside the v1 acceptance gate | English remains the default fallback. Unreviewed or structurally invalid Korean prose is never returned. |
| Local CPU performance | Not claimed | The v1 performance claim applies to the recorded remote-LLM deployment after warm-up. Local GPU support is not required. |

The decision records are in [`docs/adr/`](adr/). The evaluation and source
artifacts retain the rejected alternatives and observed metrics needed to
review these choices rather than only the selected outcome.

## Observability

Local JSON artifacts are canonical. LangSmith is an optional mirror configured
only through environment variables and bounded by a timeout. Evaluation writes
the local artifact before attempting the mirror, and mirror failure produces a
warning without changing the local result. CLI tests use a deterministic sink
for the success, disabled, unavailable, timeout, and secret-redaction paths.

When credentials are available, demonstrate a real successful mirror with
[LangSmith evaluation acceptance](langsmith-evaluation-acceptance.md). Record
the project, root trace ID, local artifact checksum, exit status, and success
line. LangSmith is not required to reproduce acceptance.

## Safety boundaries

- Answers are limited to the frozen source pack. The application does not use
  live web search, general knowledge, or documents outside that pack.
- Exact specifications and compatibility rules require human-verified evidence
  with every source-defined applicability condition.
- Compatibility is never inferred from matching dimensions, tolerances, or
  geometry unless a cited manufacturer source defines that comparison as its
  rule.
- A partial or uncertain procedure is refused as `not_found`; it is never
  presented as complete instructions.
- Figure-only or scanned content requires a named human transcription bound to
  its source page and box. OCR or vision output alone is ineligible.
- Conflicting applicable evidence is shown together unless a cited source
  explicitly establishes model scope, supersession, revision date, or
  manufacturer applicability. The system does not average or silently select
  safety-related values.
- Unsupported numbers, extra generated advice, invalid citations, and model-set
  terminal statuses fail closed.
- The web chat has no authentication. Bind it to loopback on untrusted
  networks.

## Known limitations

- A passing evaluation does not establish production safety, domain-wide
  bicycle coverage, or agreement with current manufacturer guidance.
- The full agent missed 6-8 of 120 items per accepted run. The retained misses
  include a DOT-contaminated syringe/fluid compatibility variant and
  underspecified procedure or compatibility requests whose clarification
  vocabulary differed from the frozen labels.
- The frozen pack has six documents. Questions outside those models,
  generations, manufacturers, or maintenance tasks are intentionally not
  answered.
- PDF parsing, table extraction, figures, heading boundaries, and procedure
  completeness remain material failure sources. Checksums detect source drift
  but cannot preserve a document that disappears from the manufacturer site.
- Alias matching and semantic routing can remain ambiguous or produce a less
  precise clarification. The system refuses rather than substituting a nearby
  model or component.
- Remote chat and embedding providers are operational dependencies. Their
  credentials, availability, and response quality are outside the application's
  control; provider failures are not converted into supported answers.
- Reviewed Korean support is intentionally bounded and separately reviewed. It
  does not broaden source coverage or relax evidence checks.
- Latency measurements apply to the recorded deployment and workload. They are
  not a general service-level guarantee.

The requirement and these boundaries are also stated in
[`REQUIREMENT.md`](../REQUIREMENT.md) and the
[v1 specification](https://github.com/ozjongwon/zabm/issues).
