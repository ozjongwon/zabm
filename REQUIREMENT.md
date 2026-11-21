# Bicycle Mechanic Assistant: v1 Requirements and Specification

Nov 21, 2026 · @J

Status: accepted for v1.

## 1. Purpose

Build a chatbot for road and MTB bicycle mechanics that returns exact specifications, explicit compatibility results, and complete service procedures from manufacturer documentation. Every substantive claim must be traceable to evidence, and the assistant must refuse when the loaded evidence cannot support an answer.

This is a portfolio-first reference implementation. Its central claim is not that an LLM can discuss bicycles, but that its accuracy and refusal behavior are reproducible and measurably better than weaker baselines.

V1 is not production software, a safety certification, or a substitute for checking current manufacturer instructions.

## 2. Users and questions

The primary users are professional mechanics and serious amateur mechanics who need a specific value or procedure for an identified component.

V1 supports three question families:

1. **Specification lookup:** an exact component or fastener value, including its unit and applicability conditions.
2. **Compatibility check:** whether two identified components may be used together according to an explicit manufacturer rule.
3. **Service procedure:** the complete ordered steps and attached warnings for one maintenance task.

Part and model aliases, incomplete references, and false premises must be handled conceptually rather than by choosing a nearby part.

## 3. Scope

### In scope

- Bicycle maintenance questions answered from a frozen source pack.
- Documents from any manufacturer, provided they satisfy the accepted-source and reproducibility rules.
- English source documents and English questions.
- Korean questions and answers as a separately evaluated, feature-flagged stretch capability.
- Local open-weight models plus configurable OpenAI-compatible remote providers.
- A CLI for evaluation and a minimal local web chat for demonstration.
- Source acquisition, provenance, ingestion, retrieval, answer verification, and evaluation.

### Out of scope

- Buying advice, bike fit and sizing, riding technique, training, and general coaching.
- Photo or audio input.
- Live web search or answers from documents outside the source pack.
- Inferred compatibility based only on dimensions, tolerances, or geometry.
- E-bike motor firmware and electronic shifting firmware.
- User accounts, multi-tenant operation, production deployment, availability guarantees, and polished product design.
- Claims of domain-wide bicycle coverage. Coverage is exactly the coverage of the frozen source pack.

## 4. Domain language

The project glossary is [GLOSSARY.md](./GLOSSARY.md). It defines evidence, claims, specifications, procedures, compatibility outcomes, and refusal states.

Architectural decisions are recorded under [docs/adr](./docs/adr/). The glossary defines the language; it must not become a second specification.

## 5. Source-pack contract

### 5.1 Composition

- The demo source pack contains 4-8 official technical documents from at least two manufacturers.
- Candidate sources include service manuals, owner manuals, technical notices, and service bulletins.
- Each source must be first-party, public, and directly downloadable without an account, login, cookie, or private mirror.
- Forums, retailers, videos, dealer Q&A, community uploads, and third-party summaries are not accepted sources.
- The pack must provide enough depth to evaluate all three question families and realistic compatibility and refusal cases.

### 5.2 Selection and audit

Candidate selection must be auditable and completed before answer-accuracy baselines:

1. Check source authority and public availability.
2. Validate page, heading, table, and warning alignment.
3. Run a fixed retrieval-only smoke set covering specification, compatibility, and procedure evidence.
4. Require at least 85% Recall@5 on at least one predeclared baseline retrieval path, with per-path results recorded.
5. Freeze the source pack, smoke set, evaluation set, expected answers, and retrieval smoke-test configuration.

All candidate inclusion and exclusion decisions, smoke metrics, and reasons must be committed in the evaluation documentation. A document may be excluded for unverifiable extraction or unreliable retrieval, but must not later be removed merely because answer baselines perform poorly on it.

### 5.3 Change control

The download manifest pins every source URL with:

- SHA-256 content hash.
- Retrieval date.
- Document revision, date, or model-year metadata when available.
- Manifest version.

A normal rebuild fails on a checksum mismatch. Updating a source requires maintainer review, an explicit manifest change, and a complete evaluation rerun. Downloads must never silently replace frozen evidence.

## 6. Evidence model

### 6.1 Two evidence planes

The system has two distinct evidence planes:

1. **Structured evidence:** human-verified specifications and compatibility rules with source citations and applicability fields.
2. **Retrieval evidence:** page- and section-structured source chunks used for complete procedures and supporting context.

Specification and compatibility answers may use only structured evidence. Procedure answers may use only retrieval evidence that establishes a complete source-defined procedure section.

Storage technology may change, but the separation is a system contract. The two planes must share stable document, page, section, and excerpt provenance.

### 6.2 Citation and provenance

Every evidence item includes:

- Stable document identifier and title.
- Manufacturer and document date or revision where available.
- Printed page number.
- Physical PDF page number where available.
- Heading path.
- Short supporting excerpt.
- Source manifest version and retrieval date.

User-facing answers display the document, printed page, section, and source retrieval date. Physical-page details remain available in structured application output.

### 6.3 Extraction

- Ingestion preserves page boundaries, heading hierarchy, table structure, warnings, and procedure order.
- An LLM may propose extracted rows or chunks, but every exact value and compatibility rule is checked by a human against the original document before it can support an answer.
- A value or rule without human verification is not answerable.
- Figure-only content is unsupported unless a human transcribes it into text with an exact citation and verifies the transcription.
- OCR or model interpretation of a diagram is not sufficient evidence by itself.

## 7. Functional requirements

### FR1 Specification lookup

Given an identified model and component or fastener, return the exact requested value with unit, applicability conditions, citation, and evidence.

Every source-defined condition required to interpret the value must be included, including model revision, component side, material, thread condition, lubrication, or measurement state when relevant. If those conditions cannot be established, return `not_found`.

### FR2 Compatibility check

Given two components, return exactly one compatibility outcome:

- `compatible`
- `not_compatible`
- `unknown`
- `not_found`

`compatible` and `not_compatible` require an explicit manufacturer rule. `unknown` requires relevant evidence that explicitly leaves the pair unresolved and cites that limitation. `not_found` means the source pack has no adequate evidence.

A cited compatibility `unknown` is a supported answer with status `supported`; compatibility `not_found` is a terminal refusal with response status `not_found`.

Comparing dimensions, tolerances, or geometry is forbidden unless a cited source explicitly defines that comparison as the compatibility rule.

### FR3 Service procedure

Given a task, return the ordered service steps and all warnings attached to those steps, with citations.

A procedure is supported only when retrieval establishes a complete source-defined procedure section. If any required step may be missing, return `not_found` and explain that only partial evidence was available. A partial procedure must never be presented as complete.

### FR4 Model and part names

Recognize aliases such as model names, part numbers, common names, and reordered forms. An alias may resolve to one canonical entity. If multiple entities remain possible, request clarification. The system must never silently substitute an adjacent model or a visually similar part.

### FR5 Refusal and false premises

When evidence is absent, weak, incomplete, or contradictory without a resolved precedence, do not answer substantively.

When a claimed part or specification does not exist in the source pack, return `not_found` without suggesting an alternative component.

### FR6 Out-of-scope handling

Decline non-maintenance requests without searching for evidence or offering adjacent advice.

### FR7 Clarification

If the missing or ambiguous subject prevents a safe lookup, respond with `clarification_required` and ask for the minimum needed detail, such as the exact model, component, side, revision, or task.

`clarification_required` is an interaction outcome, not one of the terminal failure states in FR8. Scored evaluation questions are self-contained unless a case explicitly tests clarification.

### FR8 Response status and conflicts

A successful response has status `supported`. A response that can proceed after one clarification has status `clarification_required`.

A terminal unsuccessful answer has exactly one status:

- `not_found`
- `conflicting_evidence`
- `out_of_scope`

Equally applicable evidence that disagrees produces `conflicting_evidence`; both or all sources are shown and no substantive choice is made. A response may choose one claim when a cited source explicitly establishes precedence through model scope, supersession, revision date, or manufacturer-specific applicability. The rejected source and cited precedence reason remain visible.

Safety-related values are never averaged, interpolated, or silently selected.

### FR9 Answer assembly

The canonical response is a typed internal application object assembled by deterministic code. JSON is an API and persistence representation, not a schema that the LLM must emit.

The LLM may route, rewrite queries, select procedure evidence, phrase validated claims, and translate. Deterministic application code owns:

- Terminal response status.
- Compatibility outcome.
- Claim-to-evidence references.
- Citations and provenance.
- Numeric verification.
- Procedure completeness checks.
- Acceptance or rejection of the final response.

The LLM must not introduce extra advice, causes, safety assurances, substitutions, or inferred compatibility. A generated substantive sentence that cannot be associated with a validated claim is rejected.

### FR10 Numeric verification

Extract every number from a supported answer and match it, after unit normalization, to an evidence excerpt attached to its claim. Fail closed on an unmatched number.

No arithmetic, unit conversion, interpolation, or averaging is allowed unless the exact operation is explicitly present in applicable source evidence.

### FR11 Interfaces

Provide:

- A CLI for asking questions, running evaluation, inspecting evidence, and rebuilding data.
- A minimal local web chat for portfolio demonstration.

Both interfaces use the same application service and canonical response contract. The web UI must not contain a separate answer path.

### FR12 Model providers

Support the same provider interface for:

- A local OpenAI-compatible server using an open-weight model and embeddings.
- An optional OpenAI-compatible remote service such as DeepSeek.

Credentials come from environment variables or an equivalent secret store and are never committed. Results and latency are tagged with provider and model configuration. Remote operation is optional; local operation is the reproducible reference path.

### FR13 Reproducible data build

After a clean checkout, two user-facing commands rebuild the data pipeline:

1. `download`: bootstrap the locked environment, download every manifest source, verify hashes, and report provenance.
2. `ingest`: parse, verify, extract, index, and validate all derived stores from the verified downloads.

Only Python, the documented environment bootstrap, network access to source URLs, and a configured model provider may be prerequisites. The commands must not depend on manually retained PDFs, databases, indexes, or earlier workspace state.

The concrete script paths and command names are documented in the implementation. Rebuild validation includes source counts, page alignment, record counts, and canonical artifact checksums. Byte-identical vector indexes are not required.

### FR14 Evaluation

One command runs the frozen evaluation set for any registered configuration. Local JSON or SQLite artifacts are canonical and always produced. LangSmith receives a mirror of results and traces, but evaluation must still run when LangSmith is unavailable. The acceptance run must demonstrate successful LangSmith logging.

### FR15 Language behavior

English questions and answers are always supported. Korean is a feature-flagged stretch capability. It may be enabled only after a separately reviewed Korean sample demonstrates acceptable correctness and fluency, including preserved values, units, statuses, and citations.

When Korean output is disabled or fails validation, Korean questions receive a clear English answer. Unreviewed or structurally invalid Korean prose must not be returned.

## 8. Answer contract

Every response carries:

- Request identifier and timestamp.
- Response type and language.
- Outcome status.
- Clarification or failure message when applicable.
- Supported claims and evidence references.
- Compatibility outcome when applicable.
- Conflicts and precedence explanations when applicable.
- Source retrieval dates.
- Provider, model, configuration, and source-pack identifiers.

A supported response has no substantive claim without evidence. A terminal failure response has no substantive answer, substituted component, or speculative value.

External JSON may be produced from the typed object. Plain conversational text is a rendering of the same object, not a separate source of truth.

## 9. Evaluation design

### 9.1 Frozen set

The scored evaluation set contains 120 items:

| Category | Items |
| --- | ---: |
| Specification | 36 |
| Compatibility | 27 |
| Procedure | 27 |
| Not found | 15 |
| Conflicting evidence | 8 |
| Out of scope | 7 |

The set is hand-authored from the frozen source pack before any answer baseline runs. It includes realistic near misses: adjacent model numbers, wrong generations, cross-brand pairs, unsupported material combinations, missing attributes, truncated procedures, ambiguous aliases, and false premises.

Expected outcomes are derived from the source pack, not invented evaluator preferences. A separate Korean stretch set is reported independently and excluded from the v1 gate.

### 9.2 Baseline ladder

Within one model/provider comparison:

- **LLM-only:** no retrieved evidence.
- **Plain RAG:** vector retrieval over the same page-structured source chunks.
- **Hybrid retrieval:** vector retrieval plus BM25 and metadata filters, without query rewriting or final verification.
- **Full agent:** hybrid retrieval plus the measured enhancements, structured evidence checks, query rewriting where enabled, and final evidence verification.

All configurations use the same questions, model provider, prompt budget, decoding settings, and hardware where applicable. Retrieval parameters and configuration versions are frozen before scoring. Results are reported separately per model/provider and are not pooled.

### 9.3 Grading

- Specifications are graded by normalized value, range, unit, and required qualifiers.
- Compatibility and response statuses are graded exactly.
- Procedures receive a reviewable LLM-produced checklist marking each expected step and warning as supported, missing, or incorrect. Deterministic code decides whether the item passes.
- Every supported answer is checked for valid citations and unsupported numbers.

The procedure judge may interpret wording but cannot assign the final item score.

### 9.4 Repetition

Every configuration runs three times with temperature zero and a recorded seed where supported.

- Report every run and the spread.
- Use the median run for accuracy and latency thresholds.
- Pool repeated runs for fabricated-number and citation-validity rates.

### 9.5 Metrics and gates

The full agent passes when:

- Overall answer accuracy is at least 90% on the 120-item median run.
- It improves overall accuracy over both LLM-only and plain RAG by at least 10 percentage points.
- The 95% paired-bootstrap confidence interval for each baseline difference is wholly above zero.
- Citation validity is at least 95%.
- Correct abstention is at least 95% on not-found, conflicting-evidence, and out-of-scope items.
- Fabricated numeric values are zero across all three runs.

The paired bootstrap uses a fixed seed and the item-level paired differences averaged across the three runs. Retrieval diagnostics report Recall@5 and MRR independently so retrieval failure can be distinguished from answer-generation failure.

## 10. Performance

The local reference machine is:

- Linux x86_64.
- NVIDIA GTX 1060 with 6 GB VRAM.
- 32 GB system memory.
- A documented CUDA-capable Python environment.

Measure end-to-end latency from question submission until the complete answer with citations is rendered, excluding model warm-up. The local GPU target is:

- Median: 20 seconds or less.
- p95: 30 seconds or less.

Latency is measured over the frozen evaluation set and reported by provider and model. CPU-quantized operation requires a successful smoke run and documented performance but does not need to meet the GPU threshold. Remote-provider latency is reported separately and is not part of the reproducible pass condition.

## 11. Repository and licensing

The repository tracks:

- Requirements, glossary, ADRs, architecture, evaluation protocol, and limitations.
- Source manifest, checksums, retrieval dates, smoke-test results, and candidate audit trail.
- Curated verified facts and compatibility rules with source references.
- Evaluation labels, expected outcomes, page locators, and result summaries.
- Code, tests, and configuration metadata without secrets.

The repository does not track:

- Manufacturer PDFs.
- Large transcribed source excerpts.
- Downloaded source files.
- Generated chunks, databases, vector indexes, or caches.
- Credentials.
- Model weights unless their license and size make tracking appropriate.

Answerable excerpts are produced from the downloaded source pack at runtime. Committed evaluation material may include only the minimal references needed to reproduce a label.

## 12. Deliverables

V1 is complete only with:

- A quickstart README.
- This frozen requirement/specification.
- Glossary and ADRs.
- Architecture overview.
- Data manifest and source-selection audit.
- Evaluation protocol and report.
- Per-baseline, per-provider, per-run, hardware, and runtime results.
- Known limitations and safety boundaries.
- Two rebuild commands.
- Automated unit, integration, and evaluation-contract tests.
- CLI.
- Minimal local web UI.

## 13. Operational acceptance

From a fresh clone and empty generated-data directories:

1. Run the two rebuild commands.
2. Verify source hashes, page alignment, dataset counts, and artifact checksums.
3. Pass the automated test suite.
4. Run all 120 scored items three times for every required baseline and the full agent.
5. Produce local result reports.
6. Demonstrate successful LangSmith logging.
7. Meet the accuracy, improvement, citation, abstention, numeric-hallucination, and latency gates.
8. Exercise both CLI and web chat with the same application service.
9. Inspect representative evidence, refusal, and conflict responses for correct display.

## 14. Known limitations

- Official documents may change or disappear; checksums detect silent change but cannot preserve a future download.
- PDF parsing, tables, and figures remain a material failure source.
- Coverage is limited to the frozen source pack and selected question distribution.
- The evaluation set can contain authoring mistakes even when it is frozen.
- Small models may route or phrase poorly; deterministic gates can reject their output but cannot make an absent capability reliable.
- Korean support is optional until it passes separate review.
- Compatibility and exact facts intentionally refuse rather than reason beyond manufacturer evidence.
- Passing evaluation does not establish production safety or current manual accuracy.

## 15. Empirical choices

The following choices must be made from recorded experiments rather than silently assumed:

- The final 4-8 document source pack.
- The concrete local model and embedding model.
- Chunker, vector store, reranker, and final retrieval parameters.
- Which optional retrieval enhancements belong in the full agent.
- Whether Korean output meets the quality bar for enabling.
- CPU-quantized performance characteristics.

The evaluation report must record each choice, the alternatives considered, and the evidence used.

