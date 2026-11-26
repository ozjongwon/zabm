# Maintainability, architecture, and extension guide

This document explains how ZABM is structured, where new behavior belongs, and
which contracts must remain stable. It is aimed at maintainers changing the
code, reviewers checking whether a change respects the architecture, and future
agents who need a reliable map before editing the repository.

This describes the v1 implementation as of 2026-11-26. Product requirements and
accepted behavior remain authoritative in the
[v1 specification](../.scratch/bicycle-mechanics-assistant-v1/spec.md).
Architecture decisions remain authoritative in [`docs/adr/`](adr/), and domain
language remains authoritative in [`GLOSSARY.md`](../GLOSSARY.md).

## Contents

- [Architectural stance](#architectural-stance)
- [System context](#system-context)
- [Runtime architecture](#runtime-architecture)
- [Source structure](#source-structure)
- [Build lifecycle](#build-lifecycle)
- [Data and artifact ownership](#data-and-artifact-ownership)
- [Extension recipes](#extension-recipes)
- [Testing strategy](#testing-strategy)
- [Diagnostics and debugging](#diagnostics-and-debugging)
- [Current maintainability hotspots](#current-maintainability-hotspots)
- [Future direction](#future-direction)
- [Change checklist](#change-checklist)

## Architectural stance

ZABM is a local-first, evidence-gated answer engine with multiple adapters and
an offline artifact pipeline. Its central rule is that model fluency may improve
the presentation of an answer but cannot create evidence, choose a terminal
status, or weaken a safety invariant.

The implementation follows these rules:

- **One canonical answer interface.** The CLI and web chat both call
  `answer_question` in [`agent.py`](../src/zabm/agent.py).
- **Application code owns the answer.** Routing, evidence lookup, status,
  compatibility outcomes, citation validity, numeric checks, procedure
  completeness, and final acceptance are deterministic.
- **Evidence is selected before prose.** Model phrasing only runs after a
  supported response has been assembled from validated claims.
- **The source pack is bounded.** Inputs are explicit, versioned, and frozen;
  generated data is reproducible from tracked inputs.
- **Artifacts are interfaces.** JSON manifests, catalogs, freezes, evaluation
  results, and project records carry identities and checksums across process
  and workflow seams.
- **Adapters stay shallow.** CLI and web code validates input and presents the
  canonical envelope; neither owns a second answer path.
- **Fail closed on uncertainty.** Missing evidence, incomplete procedures,
  malformed model output, unsupported numbers, and unresolved conflicts return
  an explicit refusal rather than a plausible guess.

Use the vocabulary from the `codebase-design` skill when discussing these
structures: a **module** hides an **implementation** behind an **interface** at
a **seam**; **depth** is leverage at that interface; **locality** is the
maintainer benefit of keeping related change and verification together.

## System context

```text
                         tracked source inputs
                    manifest, verified evidence,
                    profiles, transcription records
                               |
                               v
  manufacturer PDFs ---> acquisition and ingestion ---> generated JSON catalogs
                                                              |
                                                              v
  user ---> CLI adapter ----------------------------> canonical answer service
             web adapter ----------------------------^          |
                                                                |
                                               evidence gates and routing
                                                                |
                                             specification / compatibility /
                                             complete procedure / refusal
                                                                |
  optional remote LLM <--- routing and phrased claims ---------+

  frozen evaluation set ---> evaluation ladder ---> canonical evaluation JSON
                                                        |
                                                        v
                                                  acceptance gates
                                                        |
                                             optional LangSmith mirror
```

There is no database, queue, or network service inside the core answer path.
The durable state is the file system: tracked source and evidence artifacts,
ignored downloaded PDFs, ignored generated catalogs, and generated reports.

## Runtime architecture

The CLI is the composition root. It parses commands, loads provider settings,
selects paths, invokes application or build modules, renders output, and maps
domain failures to process exit codes.

The web adapter is a second presentation adapter, not a second application. It
accepts a bounded JSON request in [`web.py`](../src/zabm/web.py) and calls the
same `answer_question` interface with the configured data directory and
provider supplied by the CLI.

### Canonical request lifecycle

1. The adapter validates the question and constructs or loads a `ModelProvider`.
   `configured_provider` in [`providers.py`](../src/zabm/providers.py) is the
   provider composition point.
2. `answer_question` invokes `_answer_canonical_question`. This runs a model
   router when a provider exists, otherwise the deterministic prototype router.
3. Out-of-scope requests return before evidence is loaded.
4. Ambiguous routes or missing identity fields return `clarification_required`.
5. A valid route selects one evidence module:
   `answer_specification`, `answer_compatibility`, or `answer_procedure`.
6. The evidence module loads its generated catalog, matches the request,
   rejects ineligible records, adjudicates disagreements, and constructs a
   `CanonicalResponse`.
7. Model-routed `not_found` and some clarification results may retry through
   the prototype router only when deterministic evidence produces a supported
   answer.
8. For a supported response with a provider, the model may phrase validated
   claims. Every generated sentence must map to an existing claim, number, and
   evidence ID.
9. Optional reviewed localization runs after canonical answer construction.
   Failure returns the English canonical answer with localization metadata.
10. The adapter renders or serializes the same final response envelope.

The main request flow lives in:

- [`cli.py`](../src/zabm/cli.py): `_ask_command`, `_web_command`, and rendering.
- [`agent.py`](../src/zabm/agent.py): `answer_question`, routing fallback,
  validated phrasing, logging, and localization orchestration.
- [`routing.py`](../src/zabm/routing.py): model and prototype `IntentRouter`.
- [`specifications.py`](../src/zabm/specifications.py),
  [`compatibility.py`](../src/zabm/compatibility.py), and
  [`procedures.py`](../src/zabm/procedures.py): evidence-specific answer
  implementations.

### Canonical response

`CanonicalResponse` in [`response.py`](../src/zabm/response.py) is the stable
application interface. It contains:

- request identity and timestamp;
- response type, language, and terminal status;
- refusal or clarification data;
- claims linked to evidence IDs;
- typed specification, compatibility, and procedure payloads;
- conflict candidates and cited precedence;
- citations with document, printed page, physical page, section, and retrieval
  date;
- provider and routing identity;
- source-pack ID and localization metadata.

Adapters may format this object but must not infer facts from it, reconstruct a
different status, or derive an answer from catalog contents directly.

### Interface invariants

| Interface | What callers may rely on | What callers must not do |
| --- | --- | --- |
| `answer_question` | Returns one validated `CanonicalResponse`; optional provider and router dependencies are injected | Copy routing, evidence, or refusal logic into an adapter |
| `ModelProvider` | `identity`, `seed_supported`, `complete`, and `embed` form the model seam | Treat unvalidated provider JSON as a canonical answer |
| `IntentRouter` | Returns a bounded `RequestRoute`; strategy is model or prototype | Let a route set status, citations, compatibility, or completeness |
| Evidence catalogs | JSON records carry source-pack identity, citations, and validation state | Read PDF text directly during a normal answer |
| Source and evaluation freezes | Bind exact bytes, hashes, and review references | Silently replace frozen inputs after evaluation |
| CLI commands | Are the automated test seam and scriptable operational interface | Add a web-only behavior that bypasses the corresponding service path |

## Source structure

| Module | Role | Main interface or change surface |
| --- | --- | --- |
| `__main__.py` | Package entry point | Delegates to `cli.main` |
| `cli.py` | Composition root and presentation adapter | Command parsing, path defaults, provider setup, rendering, exit codes |
| `web.py` | Local HTTP presentation adapter | `ZabmHTTPServer`, `/api/ask`, request bounds, response envelope rendering |
| `agent.py` | Canonical answer application | `answer_question`, routing fallback, validated phrasing |
| `routing.py` | Request interpretation | `RequestRoute`, `IntentRouter`, `ModelIntentRouter`, `PrototypeIntentRouter` |
| `response.py` | Canonical domain contracts | `CanonicalResponse` and nested answer, citation, conflict, and localization types |
| `providers.py` | Remote model adapter and configuration | `ModelProvider`, `OpenAICompatibleProvider`, provider profiles |
| `specifications.py` | Source acquisition and specification evidence | Manifest, verified specification ingestion, `answer_specification` |
| `compatibility.py` | Verified compatibility evidence | Rule ingestion, explicit-rule eligibility, `answer_compatibility` |
| `procedures.py` | PDF parsing, procedure retrieval, completeness, and answering | `ingest_retrieval`, `answer_procedure`, `resolve_procedure_evidence` |
| `classification.py` | Page-block classification | `DeterministicPageBlockClassifier` |
| `headings.py` | Heading hierarchy reconstruction | `DeterministicHeadingReconstructor` |
| `ingestion.py` | Versioned ingestion contracts and profiles | `DocumentProfile`, stage result types, profile loading and provenance |
| `matching.py` | Alias and token identity matching | `identity_matches`, `tokens`, `unknown_tokens` |
| `conflicts.py` | Conflict adjudication | `EvidenceCandidate`, `adjudicate`, conflict response |
| `source_pack.py` | Retrieval smoke, source freeze, lexical retrieval | `run_retrieval_smoke`, `verify_frozen_source_pack`, `retrieve_evidence` |
| `evaluation_set.py` | Frozen evaluation inputs | Set validation, evaluation freeze, category coverage |
| `evaluation.py` | Baseline ladder | Four configurations, grading, metrics, canonical evaluation artifact |
| `acceptance.py` | Acceptance gate scoring | Paired bootstrap, gate thresholds, acceptance report |
| `observability.py` | Optional LangSmith mirror | Environment configuration, bounded batch mirroring |
| `localization.py` | Reviewed Korean output | Review policy, translation, structural validation, English fallback |
| `coverage.py` | Per-source CLI coverage audit | Representative accepted and unanswerable cases |

### Dependency direction

Prefer dependencies that point from orchestration toward contracts and
behavior-specific modules, not back into adapters:

```text
cli / web
    |
    v
agent / evaluation / coverage
    |
    +--> specifications / compatibility / procedures
    |          |
    |          +--> conflicts / matching / response
    |          +--> ingestion contracts
    |
    +--> routing / providers / localization / observability

source_pack --> procedures + specifications
acceptance  --> evaluation
```

`cli.py` is intentionally allowed to import broadly because it is the
composition root. Domain modules should not import `cli`, `web`, `evaluation`,
or `acceptance` merely to reuse behavior. `response.py` is a shared contract
module and should remain free of I/O and orchestration.

The stage protocols in `ingestion.py` are declared contracts for
classification, layout, headings, procedure candidates, completeness, and
evidence verification. They are not currently wired as a generic staged
runtime; `procedures.py` contains the concrete pipeline. Treat them as a design
target when decomposing ingestion, not as an existing plug-in system.

## Build lifecycle

### Source acquisition and evidence build

```text
source manifest + PDF URLs
          |
          v
download_sources -----> pdf-doc/*.pdf
          |             (SHA-256 checked)
          v
ingestion profiles ---> page layout, classes, headings, tables, warnings
          |
          +-- verified specs/compat ---> generated/specifications.json
          |                              generated/compatibility.json
          |
          +-- procedures + transcriptions -> generated/retrieval.json
          |
          v
generated/ingestion-report.json
```

`zabm ingest` verifies the frozen source pack, checks PDF hashes, validates
ingestion profiles, assesses rebuild impact, and then writes all three catalogs.
The command refuses a normal rebuild when parser, profile, or dependency
provenance changes without an explicit rebuild review.

Structured specification and compatibility evidence is human-authored and
human-verified. Ingestion validates the citation against the original page and
checks eligibility rules such as units, explicit compatibility wording, and
applicability conditions. Procedure evidence is derived from page-structured
retrieval data, except for human-verified figure transcriptions on their
separate evidence plane.

Writes use a temporary file followed by `os.replace` through `write_json`.
JSON is sorted and uses a trailing newline so a stable environment produces
stable artifact bytes.

### Freeze and evaluation lifecycle

```text
source manifest + retrieval smoke inputs
                    |
                    v
              retrieval smoke report
                    |
            maintainer review
                    v
             source-pack freeze
                    |
           evaluation set freeze
                    |
         three-run baseline ladder
                    |
                    v
          canonical evaluation result
                    |
                    v
            acceptance report
                    |
            optional remote mirror
```

The order is intentional:

1. Select and audit sources.
2. Run retrieval-only smoke before answer accuracy.
3. Freeze the source pack with a maintainer review reference.
4. Validate and freeze the evaluation set against that source freeze.
5. Run every baseline three times with recorded seeds.
6. Preserve every run in the canonical local artifact.
7. Score gates into a separate acceptance report.
8. Attempt LangSmith mirroring only after the local artifact exists.

Do not edit expected answers after seeing a run. A source update or evaluation
change requires the documented review and full rerun. Existing failed gates
must remain visible; do not rewrite thresholds to manufacture a pass.

## Data and artifact ownership

### Tracked authoritative inputs

| Artifact | Purpose |
| --- | --- |
| `data/manifests/source-pack-v1.json` | Included sources, hashes, URLs, dates, and revision metadata |
| `data/evidence/verified-specifications.json` | Human-verified specification claims |
| `data/evidence/verified-compatibility.json` | Human-verified compatibility rules |
| `data/evidence/verified-transcriptions.json` | Human-verified figure or scanning transcriptions |
| `data/ingestion/profiles-v1.json` | Versioned document parsing profiles |
| `data/audits/source-pack-candidates-v1.json` | Source inclusion and exclusion audit |
| `data/retrieval-smoke/` | Fixed retrieval smoke set, configuration, report, and freeze inputs |
| `data/evaluation/evaluation-set-v1.json` | Frozen scored questions and expected outcomes |
| `data/evaluation/evaluation-freeze-v1.json` | Hash binding to evaluation and source-pack freezes |
| `data/evaluation/baseline-config-v1.json` | Baseline ladder configuration |
| `data/evaluation/*-results-v1.json` | Canonical evaluation evidence |
| `data/evaluation/acceptance-report-v1.json` | Gate outcomes and diagnostic evidence |
| `data/coverage/coverage-v1.json` | Per-source acceptance and unanswerable cases |
| `data/korean/` | Current reviewed-language sample and review records |

### Generated or local-only state

| Path | Rule |
| --- | --- |
| `pdf-doc/` | Downloaded originals; ignored and rebuildable |
| `.zabm/` | Generated catalogs and ingestion report; ignored and rebuildable |
| `~/.config/zabm/runtime.env` | Installed runtime provider configuration; mode `600`, outside the repository |
| `/home/ollama/` | Externally managed Ollama state and models |
| `.env`, `.env.*` | Local secrets; ignored except `.env.example` |

Never patch `.zabm/` or `pdf-doc/` to make an answer pass. Fix the tracked
evidence, source manifest, or ingestion implementation and rebuild. Generated
artifacts are evidence of what the tracked inputs produced, not independent
configuration.

Schema names such as `evaluation-results-v1` and `acceptance-report-v1` are
contract versions. An incompatible shape change should introduce a new version
and migration/review path rather than silently changing the meaning of an
existing artifact.

## Extension recipes

### Add a model or embedding provider

1. Add or reuse a `ProviderProfile` in `providers.py`.
2. Keep credentials in environment variables or the runtime secret store.
3. Return a valid `ProviderIdentity`; do not include the API key in identity.
4. Implement `ModelProvider.complete` and, when supported, `embed`.
5. Keep request timeouts bounded and convert transport or malformed-output
   failures to `ProviderError`.
6. Add provider smoke coverage and CLI-seam tests with a deterministic fake.
7. Update provider documentation and the empirical-choice record.

Do not put provider-specific branching into evidence modules. Chat and embedding
deployments remain independently configurable.

### Add source documents

1. Confirm first-party authority, public acquisition, extraction quality, and
   intended coverage.
2. Add the source to the candidate audit and source manifest with SHA-256,
   retrieval date, revision where available, and a public URL.
3. Validate page and heading alignment.
4. Add representative retrieval-smoke evidence before answer accuracy runs.
5. Add human-verified structured claims or transcriptions where applicable.
6. Rebuild from empty generated directories.
7. Review and replace the source freeze explicitly.
8. Replace the evaluation freeze if questions or expected outcomes change.
9. Rerun all baselines and acceptance.

Adding a source is an evidence release, not just a manifest edit.

### Add or adjust an ingestion profile

1. Edit the versioned profile in `data/ingestion/profiles-v1.json`.
2. Keep layout, language, heading, table, figure, end-boundary, and action-alias
   settings explicit.
3. Run `zabm ingest --diagnostics` and inspect classification, headings,
   rejected candidates, and provenance.
4. Add cross-layout tests through the CLI seam when behavior changes.
5. If the parser/profile provenance changes, supply a rebuild review and
   perform any required re-freeze and evaluation rerun.

Use a new profile or new profile version for layouts with materially different
rules. Do not hide document-specific exceptions in shared matching code.

### Add a question family or response type

This is a cross-cutting change. At minimum, update:

- `EvidenceIntent` and `CanonicalResponse` in `response.py`;
- routing prototypes, route validation, and routing metadata;
- the dispatch in `agent.py`;
- one deep evidence module that owns matching, eligibility, and response
  construction;
- CLI and web rendering;
- evaluation expectations, graders, and coverage fixtures;
- acceptance metrics when the new family changes the meaning of accuracy.

Add a new response type only when existing specification, compatibility, or
procedure semantics cannot represent the answer safely. Update an ADR when the
change alters the canonical contract or evidence policy.

### Add an adapter

1. Validate and bound adapter input.
2. Load the same data directory and provider configuration as the CLI.
3. Call `answer_question` and render the returned canonical envelope.
4. Add no evidence lookup, status inference, numeric logic, or refusal rules.
5. Exercise the adapter against representative supported and refused outcomes.

If the adapter needs data not present in `CanonicalResponse`, improve the
canonical interface deliberately rather than reading generated catalogs behind
the application service.

### Add a reviewed output language

The current Korean implementation is a bridge to the planned language-profile
architecture in
[`multilingual-reviewed-output/spec.md`](../.scratch/multilingual-reviewed-output/spec.md).

The intended design is:

- English remains built in and is the universal fallback.
- Each non-English language has a normalized BCP 47 tag, profile, sample set,
  and hash-bound review record.
- Translation changes presentation only; canonical values, conditions,
  statuses, warnings, citations, and conflict structure remain application-owned.
- A language is enabled only after its own review passes.
- CLI and web rendering read labels from the active profile instead of adding a
  new adapter-specific language path.

Do not generalize Korean-specific conditionals by adding another set of
per-language branches. Implement the profile seam and migrate Korean through it.

### Change retrieval or evaluation

Retrieval changes affect answer evidence, evaluation metrics, and likely the
source freeze:

- declare retrieval paths and configuration;
- run the fixed retrieval-only smoke set;
- record per-path Recall@5 and the threshold decision;
- freeze the source pack through maintainer review;
- run the complete baseline ladder;
- report retrieval failure separately from answer-generation failure.

Evaluation changes affect the acceptance contract:

- keep the four ordered configurations unless a reviewed requirement changes;
- use temperature zero and recorded seeds;
- preserve every run and spread;
- use the median-accuracy run for accuracy and latency thresholds;
- pool runs for citation, abstention, and fabricated-number checks;
- preserve failed gates and their observed values.

### Change an acceptance gate

Acceptance thresholds and methodology are product decisions. Update the issue,
specification, ADR when appropriate, `acceptance.py`, CLI tests, and
documentation together. A new gate must state its scope, aggregation method,
threshold, failure diagnosis, and whether it applies to pooled runs or a
selected run.

## Testing strategy

The CLI is the primary automated seam. This exercises command parsing, path
resolution, application behavior, persistence boundaries, and user-visible
output together.

- Use `./.venv/bin/python -m pytest -q 2>&1 | tail -30` for the full suite.
- Re-run failing tests with `--tb=short`.
- Add focused `tests/test_cli_*.py` coverage for behavior changes.
- Use deterministic PDFs, manifests, catalogs, and fake providers.
- Assert canonical outcomes, claims, citations, conflicts, refusal statuses,
  numeric checks, and exit codes rather than private helper call order.
- Treat web acceptance as manual adapter comparison against the CLI response.
- Rebuild from empty generated directories when ingestion behavior changes.
- Run `make verify` or its health, lint, format, Pyright, and pytest components
  before handoff.

Installer behavior is covered separately because it verifies shell scripts,
platform checks, runtime paths, secrets, and clean-host behavior that the Python
application tests cannot exercise.

## Diagnostics and debugging

Use the narrowest diagnostic that exposes the failing seam:

| Symptom | First check |
| --- | --- |
| Wrong route | `zabm ask ... --debug --json`; inspect `routing` |
| Missing or wrong evidence | `zabm evidence '<procedure question>' --json` |
| Ingestion classification issue | `zabm ingest --diagnostics --json` |
| Source or artifact drift | `generated/ingestion-report.json`, source freeze, artifact checksums |
| Provider failure | `zabm provider-smoke ... --json` |
| Evaluation failure | Per-item `grading_issues`, `retrieval_failed`, citations, unsupported numbers |
| Gate failure | The gate's `observed`, `threshold`, and `diagnosis` in the acceptance report |
| Web/CLI mismatch | Compare the complete canonical envelopes, excluding request ID and timestamp |
| Optional tracing failure | Treat it as an observability warning; verify the local artifact exists |

`--debug` or `ZABM_DEBUG=1` enables detailed route, retrieval, provider, and
grading logs. Logs may contain questions and model output, so review them before
sharing.

## Current maintainability hotspots

| Area | Why it is concentrated | Safe direction |
| --- | --- | --- |
| `procedures.py` | Owns parsing, layout, headings, procedure grouping, completeness, retrieval, matching, and answer construction | Preserve its public functions; extract internal parser/grouping modules behind fixtures before attempting a larger rewrite |
| `cli.py` | Large composition root also owns rendering and operational reporting | Move reusable rendering or report presentation into modules only when another caller needs it; keep command wiring explicit |
| `evaluation.py` | Holds models, baseline execution, retrieval variants, grading, metrics, and artifact construction | Split runner, grading, and reporting behind the existing `run_evaluation` interface if those areas begin changing independently |
| Korean localization | Implements one language-specific profile ahead of the planned generic seam | Migrate to the language-profile tickets rather than layering more language branches |
| Generated JSON catalog format | Read and written by multiple workflows | Introduce versioned loaders/migrations before changing shapes; avoid in-place reinterpretation |
| Ingestion stage protocols | Declared but not yet used by a generic orchestration path | Either adopt them during a focused parser decomposition or remove them if another design supersedes them |

These hotspots are not permission for a broad rewrite. Depth comes from stable,
small interfaces. Refactor behind `answer_question`, `run_evaluation`, and the
CLI seam so behavior remains testable.

## Future direction

The active planned extension is reviewed multilingual output. It changes
localization, routing, reviewed data artifacts, CLI options, and web labels, but
must preserve the canonical English answer and all evidence gates.

Likely later directions include:

- additional manufacturer source packs or domain profiles selected explicitly at
  the pack seam;
- additional model providers behind `ModelProvider`;
- broader adapter surfaces using the same `answer_question` interface;
- decomposed ingestion stages for layouts that require different parser
  implementations;
- larger evidence storage if JSON catalogs stop fitting comfortably, introduced
  behind catalog loaders rather than spread through callers;
- richer human review workflows for sources, translations, and evidence planes.

These are candidates, not commitments. Each material extension needs a written
requirement and empirical acceptance criteria. Do not broaden the source pack or
claim domain-wide coverage without a new frozen evaluation.

## Change checklist

Before handing off a change:

- Identify which interface, artifact, or freeze it changes.
- Keep application-owned safety decisions out of prompts and adapters.
- Add or update CLI-seam behavior tests.
- Update fixtures and expected artifacts deliberately.
- Rebuild generated data when ingestion or source inputs change.
- Regenerate freezes and evaluation evidence in the required order.
- Preserve failed evidence and diagnostics.
- Update the relevant ADR, spec, acceptance procedure, or maintainability notes.
- Run health, lint, format, type checking, focused tests, and the full suite.
- Check `git status` for accidental generated data, PDFs, secrets, or runtime
  configuration.

## Related documents

- [Operational handoff](operational-handoff.md): quickstart, evidence summary,
  safety boundaries, and known limitations.
- [Domain glossary](../GLOSSARY.md): authoritative project vocabulary.
- [Architecture decisions](adr/): accepted design decisions and tradeoffs.
- [v1 specification](../.scratch/bicycle-mechanics-assistant-v1/spec.md):
  requirements, implementation decisions, and testing decisions.
- [Multilingual reviewed output](../.scratch/multilingual-reviewed-output/spec.md):
  planned language-profile architecture.
- [Implementation order](../.scratch/implementation-order.md): current ticket
  frontier.
