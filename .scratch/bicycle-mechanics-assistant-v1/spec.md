# Bicycle Mechanics Assistant v1

Status: ready-for-agent
Published: 2026-11-21
Requirement revision: 2026-11-26

## Problem Statement

Professional mechanics and serious amateur mechanics need exact component specifications, explicit compatibility results, and complete service procedures. Manufacturer information is spread across manuals, technical notices, and service bulletins; it is difficult to search, changes without notice, and can differ by model revision or applicability condition. A general-purpose chatbot can produce a plausible-looking value or procedure without evidence, infer compatibility from dimensions the manufacturer never approved, or omit a safety warning.

The mechanic needs an assistant whose answers can be checked quickly, whose coverage is honestly bounded by a frozen source pack, and which refuses when the evidence cannot support a safe answer. The project maintainer also needs reproducible evidence that the assistant is measurably more accurate and appropriately abstaining than weaker baselines.

## Solution

Build a local-first bicycle maintenance assistant over a bounded, frozen source pack of accepted manufacturer documents. It answers specification, compatibility, and service-procedure questions using either human-verified structured evidence or complete retrieval evidence, as appropriate. Every supported claim carries a citation to an accepted source, and deterministic application code owns response status, evidence gates, numerical verification, and procedure completeness.

The same canonical application service powers both a CLI for asking questions, inspecting evidence, rebuilding data, and running evaluation, and a minimal local web chat for demonstration. A remote OpenAI-compatible LLM, normally DeepSeek, is the v1 reference chat provider. Embeddings may come from a remote OpenAI-compatible service or a local Ollama instance. Evaluation compares the full assistant against LLM-only, plain RAG, and hybrid retrieval baselines and reports accuracy, abstention, citation validity, fabricated-number rate, retrieval diagnostics, and latency.

## User Stories

1. As a professional bicycle mechanic, I want to ask for a fastener specification by identifying the model and component, so that I can use the exact manufacturer-defined value rather than a remembered or approximate one.
2. As a mechanic, I want each specification to include its unit and every source-defined applicability condition, so that I do not apply the value to the wrong revision, side, material, or assembly state.
3. As a mechanic, I want model revisions and generations distinguished explicitly, so that a nearby but different model is never silently substituted.
4. As a mechanic, I want common names, part numbers, aliases, and reordered names recognized, so that I can ask using the vocabulary already on the workshop floor.
5. As a mechanic, I want an ambiguous alias resolved through clarification, so that the assistant does not guess between multiple possible components.
6. As a mechanic, I want a false-premise request refused without suggesting a nearby component, so that a nonexistent part does not receive an invented answer.
7. As a mechanic, I want an explicit `compatible` result when a manufacturer rule supports using two components together, so that I can proceed with cited evidence.
8. As a mechanic, I want an explicit `not_compatible` result when a manufacturer rule prohibits combining two components, so that I can avoid an unsafe pairing.
9. As a mechanic, I want a cited `unknown` result when the source pack contains relevant evidence that explicitly leaves a pair unresolved, so that I can distinguish an unresolved manufacturer position from missing evidence.
10. As a mechanic, I want a `not_found` result when no adequate compatibility evidence exists, so that a lack of evidence is not mistaken for permission.
11. As a mechanic, I want compatibility never inferred from matching dimensions, tolerances, or geometry unless the cited source defines that comparison as the rule, so that plausible measurements cannot substitute for manufacturer approval.
12. As a mechanic, I want a complete ordered service procedure with every attached warning, so that I can perform the task without skipping a safety-critical step.
13. As a mechanic, I want a partial procedure refused as `not_found` with an explanation that only partial evidence was available, so that incomplete retrieval is never presented as a complete procedure.
14. As a mechanic, I want each procedure step and warning associated with its source, so that I can verify the instructions against the manufacturer document.
15. As a mechanic, I want citations to show the document, printed page, section, and source retrieval date, so that I can locate and recheck the evidence.
16. As a maintainer or evaluator, I want physical PDF page information retained in structured output, so that page-alignment defects can be diagnosed separately from printed-page errors.
17. As a mechanic, I want every numeric value in an answer checked against an attached evidence excerpt after unit normalization, so that a model-generated number cannot enter a supported answer unnoticed.
18. As a mechanic, I want arithmetic, conversion, interpolation, and averaging refused unless the source explicitly defines the operation, so that derived values do not appear as manufacturer facts.
19. As a mechanic, I want contradictory applicable evidence shown together, so that I can understand why the assistant will not choose between sources.
20. As a mechanic, I want a precedence decision only when a cited source establishes model scope, supersession, revision date, or manufacturer-specific applicability, so that conflicts are resolved by evidence rather than confidence.
21. As a mechanic, I want rejected conflicting evidence and its precedence reason kept visible, so that a superseded value does not disappear from the record.
22. As a mechanic, I want safety-related values never averaged or silently selected, so that the system fails closed when applicability is unresolved.
23. As a mechanic, I want non-maintenance requests declined without an evidence search or adjacent advice, so that the assistant stays within its promised scope.
24. As a mechanic, I want an essential missing model, component, side, revision, or task identified through `clarification_required`, so that I can provide the minimum detail needed for a safe lookup.
25. As a mechanic, I want clarification treated as an interaction state rather than a terminal failure, so that the conversation can continue without losing the request.
26. As an English-speaking mechanic, I want English questions and answers supported by default, so that the v1 reference workflow is always available.
27. As a Korean-speaking mechanic, I want Korean questions and answers available behind a feature flag after separate quality review, so that values, units, statuses, and citations remain correct in Korean.
28. As a Korean-speaking mechanic, I want a clear English fallback when reviewed Korean output is disabled or fails validation, so that invalid translated prose is never returned.
29. As a mechanic, I want the assistant to use a remote OpenAI-compatible LLM with either remote embeddings or local Ollama embeddings, so that v1 does not depend on a local GPU.
30. As an operator, I want the chat and embedding providers configured independently without committed credentials, so that I can use DeepSeek chat with either a remote embedding API or local Ollama.
31. As an evaluator, I want results and latency tagged by provider, model, and configuration, so that distinct runs are never pooled accidentally.
32. As a maintainer, I want candidate sources checked for first-party authority, public availability, extraction quality, and retrieval usability before inclusion, so that source selection is auditable.
33. As a maintainer, I want source inclusion and exclusion decisions and smoke metrics recorded, so that the frozen source pack can be defended after evaluation begins.
34. As a maintainer, I want the source pack frozen before answer-accuracy baselines are run, so that documents are not selected based on the answers they happen to produce.
35. As a maintainer, I want every source download pinned by content hash, retrieval date, revision metadata, and manifest version, so that silent document replacement is detected.
36. As a maintainer, I want a normal rebuild to fail on a checksum mismatch, so that changed source content cannot enter the evidence stores unnoticed.
37. As a maintainer, I want source updates to require explicit review, a manifest change, and a full evaluation rerun, so that reported accuracy remains tied to the evidence actually shipped.
38. As a maintainer, I want a clean checkout rebuilt with one command for downloading and verifying sources and one command for parsing, extracting, indexing, and validating data, so that no hidden workspace state is required.
39. As a maintainer, I want the rebuild to report source counts, page alignment, record counts, and canonical artifact checksums, so that I can verify the derived data was reproduced correctly.
40. As a safety reviewer, I want every exact specification and compatibility rule human-verified against the original document before it can support an answer, so that plausible model extraction cannot become an authoritative fact.
41. As a safety reviewer, I want figure-only content unsupported unless a human transcribes and verifies it with an exact citation, so that OCR or diagram interpretation is not treated as evidence.
42. As an evaluator, I want specifications and compatibility answers restricted to structured evidence, so that unverified facts cannot enter through retrieval.
43. As an evaluator, I want procedure answers restricted to retrieval evidence that establishes a complete source-defined procedure section, so that context snippets cannot masquerade as complete instructions.
44. As an evaluator, I want structured and retrieval evidence to share stable document, page, section, and excerpt provenance, so that citations remain consistent across both evidence planes.
45. As an evaluator, I want a frozen 120-item evaluation set covering specifications, compatibility, procedures, not-found cases, conflicting evidence, and out-of-scope requests, so that accuracy and abstention are measured against realistic near misses.
46. As an evaluator, I want every configuration run three times at temperature zero with recorded seeds where supported, so that result spread is visible rather than hidden by a single run.
47. As an evaluator, I want LLM-only, plain RAG, hybrid retrieval, and full-agent configurations compared under the same questions, provider, prompt budget, decoding settings, and hardware, so that the measured improvement is attributable to the described system.
48. As a portfolio reviewer, I want the full agent to meet the accepted accuracy, improvement, confidence-interval, citation, abstention, and fabricated-number gates, so that the central claim is reproducible rather than an anecdote.
49. As an evaluator, I want retrieval Recall@5 and MRR reported independently, so that retrieval failure can be distinguished from answer-generation failure.
50. As an operator, I want evaluation results stored locally in a canonical format and mirrored to LangSmith when available, so that evaluation still runs when LangSmith is unavailable.
51. As an operator, I want the acceptance run to demonstrate successful LangSmith logging, so that observability is proven rather than assumed.
52. As a mechanic or evaluator, I want a CLI for asking questions, inspecting evidence, rebuilding data, and running evaluation, so that the full workflow is scriptable and inspectable.
53. As a portfolio viewer, I want a minimal local web chat for bicycle maintenance questions, so that I can exercise the assistant interactively.
54. As an application developer, I want the CLI and web chat to call the same application service and canonical response contract, so that the web UI cannot bypass evidence or refusal rules.
55. As an application developer, I want the LLM limited to routing, query rewriting, procedure evidence selection, validated claim phrasing, and translation, so that model fluency cannot override deterministic evidence gates.
56. As an application developer, I want deterministic code to own terminal status, compatibility outcome, claim-to-evidence references, citations, numeric verification, procedure completeness, and final acceptance, so that malformed model output cannot become a supported answer.
57. As an application developer, I want each generated substantive sentence associated with a validated claim, so that extra advice, causes, safety assurances, substitutions, or inferred compatibility are rejected.
58. As an evaluator, I want local JSON or SQLite artifacts to remain canonical even when traces are mirrored remotely, so that the acceptance report does not depend on a third-party service.
59. As a maintainer, I want the evaluation report to record empirical choices and rejected alternatives for sources, models, retrieval parameters, enhancements, Korean support, and CPU performance, so that each decision is supported by evidence.
60. As a maintainer, I want known limitations and safety boundaries documented alongside results, so that readers do not mistake an evaluation pass for production safety or current-manual accuracy.

## Implementation Decisions

- Build a bounded, frozen source pack of 4-8 accepted manufacturer technical documents from at least two manufacturers. Sources must be first-party, public, directly downloadable, and suitable for testing all three question families plus realistic compatibility and refusal cases.
- Audit candidates before answer baselines. Check authority, availability, page and heading alignment, table and warning integrity, and a fixed retrieval-only smoke set. Include a source only if at least one predeclared retrieval path reaches 85% Recall@5, with per-path results recorded.
- Freeze the source pack, evaluation set, expected outcomes, retrieval smoke set, and smoke configuration before answer-accuracy baselines. Do not remove an included document merely because answer baselines perform poorly on it.
- Maintain a versioned source manifest containing source URLs, SHA-256 hashes, retrieval dates, revision or model-year metadata where available, and manifest version. A normal rebuild fails closed on a hash mismatch. Source updates require maintainer review and a complete evaluation rerun.
- Build separate acquisition and ingestion workflows. Acquisition verifies and reports the frozen sources. Ingestion parses, verifies, extracts, indexes, and validates all derived stores without relying on manually retained PDFs, databases, indexes, or earlier workspace state.
- Preserve page boundaries, heading hierarchy, tables, warnings, and procedure order during ingestion. Derived artifacts need not be byte-identical, but page alignment, counts, provenance, and canonical artifact checksums must be validated.
- Model two evidence planes. Structured evidence contains human-verified specifications and compatibility rules with applicability fields and citations. Retrieval evidence contains page- and section-structured source chunks used for complete procedures and supporting context. Both planes share stable document, page, section, and excerpt provenance.
- Restrict specification and compatibility answers to structured evidence. Restrict procedure answers to retrieval evidence that establishes a complete source-defined procedure section.
- Include every source-defined applicability condition needed to interpret a specification, including revision, side, material, thread condition, lubrication, and measurement state where relevant. Return `not_found` when those conditions cannot be established.
- Require human verification of every exact value and compatibility rule against the original document before answer eligibility. A proposed extraction without verification is not answerable. Figure-only content requires human transcription and verification.
- Canonicalize aliases to one entity when possible. If multiple entities remain possible, return `clarification_required`. Never silently substitute a nearby model or visually similar part.
- Represent a successful answer as `supported`; allow one clarification as `clarification_required`; use exactly one terminal failure status from `not_found`, `conflicting_evidence`, or `out_of_scope`.
- Compatibility uses exactly `compatible`, `not_compatible`, `unknown`, or `not_found`. Both definitive outcomes require an explicit manufacturer rule. `unknown` requires relevant evidence that explicitly leaves the pair unresolved. `not_found` means the source pack has no adequate evidence.
- A cited compatibility `unknown` is a supported answer with response status `supported`. Compatibility `not_found` is a terminal refusal with response status `not_found`.
- When applicable evidence disagrees, use `conflicting_evidence` and show all applicable sources unless a cited source explicitly establishes precedence. Keep the rejected evidence and precedence reason visible. Never average, interpolate, or silently select safety-related values.
- Build a canonical typed response through deterministic application code. It includes request identity and time, response type and language, outcome status, clarification or failure information, supported claims and evidence references, compatibility outcome, conflicts and precedence, retrieval dates, and provider, model, configuration, and source-pack identifiers.
- Let the LLM route, rewrite queries, select procedure evidence, phrase validated claims, and translate. Application code owns evidence gates, status, compatibility outcome, claim-to-evidence references, citations, numeric verification, procedure completeness, and final acceptance.
- Reject generated substantive prose that cannot be associated with a validated claim. A terminal failure contains no substantive answer, substituted component, or speculative value.
- Normalize units and verify every numeric token in a supported answer against the evidence excerpt attached to its claim. Fail closed on unmatched numbers. Do not perform arithmetic, conversion, interpolation, or averaging unless the cited source explicitly specifies that operation.
- Use one provider interface with a remote OpenAI-compatible chat service and
  an independently selected embedding service. Embeddings may use a remote
  OpenAI-compatible API or local Ollama. Load credentials from the environment
  or an equivalent secret store and never send chat credentials to a distinct
  embedding endpoint. Local chat remains supported for development but is not
  v1 acceptance evidence.
- Expose a CLI for asking questions, inspecting evidence, rebuilding data, and running evaluation. Expose a minimal web chat for the same maintenance-question path. Both adapters call one canonical application service and use the same response contract.
- Use a frozen 120-item scored evaluation set: 36 specification, 27 compatibility, 27 procedure, 15 not-found, 8 conflicting-evidence, and 7 out-of-scope items. Include adjacent models, wrong generations, cross-brand pairs, unsupported materials, missing attributes, truncated procedures, ambiguous aliases, and false premises.
- Compare LLM-only, plain RAG, hybrid retrieval, and full-agent configurations under matched questions, provider, prompt budget, decoding settings, and hardware. Freeze retrieval parameters and configuration versions before scoring.
- Grade specifications by normalized value, range, unit, and required qualifiers; compatibility and statuses exactly; and procedures through a reviewable LLM-produced checklist with deterministic pass/fail. Check every supported answer for valid citations and unsupported numbers.
- Run each configuration three times at temperature zero with a recorded seed where supported. Report every run and its spread, use the median run for accuracy and latency thresholds, and pool runs for fabricated-number and citation-validity rates.
- Accept the full agent only at 90% or higher median accuracy; at least a 10 percentage-point improvement over LLM-only and plain RAG; paired-bootstrap 95% confidence intervals wholly above zero for both differences; 95% or higher citation validity; 95% or higher correct abstention; and zero fabricated numeric values across all runs.
- Produce canonical local evaluation artifacts and treat LangSmith as an optional result and trace mirror. Keep evaluation operational when LangSmith is unavailable, while demonstrating successful logging in the acceptance run.
- Support English by default. Keep Korean behind a separate reviewed feature flag and retain an English fallback when Korean output is disabled or structurally invalid.
- Select the final source pack, remote LLM, embedding provider and model, chunker, vector store, reranker, retrieval parameters, optional full-agent enhancements, and Korean enablement from recorded experiments. The evaluation report records alternatives and evidence for each choice.

## Testing Decisions

- Use one automated seam: the CLI command surface. Tests invoke the same top-level commands a user runs to ask questions, inspect evidence, rebuild data, and evaluate. The seam exercises command behavior, the canonical application service, evidence gates, persistence boundaries, and user-visible output together.
- Treat a good test as black-box evidence of external behavior. It gives a maintenance question or a rebuild/evaluation command, a deterministic source-pack fixture, and an injected provider adapter, then asserts the canonical outcome, supported claims, citations, conflicts, refusal statuses, and numerical checks. Tests do not call private helpers, inspect internal call order, or assert implementation-only data shapes.
- Exercise specification answers with required qualifiers and units; compatibility answers for all four outcomes; complete and incomplete procedures; aliases and clarification; false premises; not-found, conflicting-evidence, and out-of-scope responses; citation validity; and rejected unsupported numbers.
- Exercise source acquisition with matching and mismatched hashes, provenance output, and manifest-version reporting. Exercise ingestion from empty generated-data state and assert page alignment, record counts, canonical artifact checksums, and repeatable rebuild behavior.
- Exercise evaluation contracts with a small fixture set across all four baseline configurations, repeated runs, exact grading, local artifact production, and operation without LangSmith. A separate acceptance run validates the frozen 120-item set and the approved performance gates.
- Use fixtures to vary providers without network access or model weight downloads. Keep a documented remote-LLM acceptance path using either remote embeddings or local Ollama.
- Treat the CLI as the sole automated test seam. Exercise the web chat as an adapter during acceptance against the same application service; it must not contain a separate answer path or independent evidence rules.
- There is no existing implementation or test suite to reuse as prior art. Establish the first suite as integration-first at the CLI seam, then add internal tests only where they expose external risk rather than routine implementation detail.

## Out of Scope

- Buying advice, bike fit and sizing, riding technique, training, or general coaching.
- Photo or audio input.
- Live web search or answering from documents outside the frozen source pack.
- Compatibility inferred only from dimensions, tolerances, or geometry.
- E-bike motor firmware and electronic shifting firmware.
- User accounts, multi-tenancy, production deployment, availability guarantees, or polished product design.
- Claims of domain-wide bicycle coverage beyond the frozen source pack.
- Automatic answers from unverified model extraction, OCR interpretation of diagrams, or partial procedure sections.
- Korean enablement before separate review of correctness, fluency, values, units, statuses, and citations.
- Guaranteeing current manufacturer guidance or certifying workshop safety.
- Selecting the final source pack, models, retrieval parameters, or optional enhancements without recorded comparative evidence.

## Further Notes

- This spec records the accepted v1 requirements dated 2026-11-21 and the current project glossary and ADRs. The glossary remains the authority for domain language, and the ADRs remain authoritative for bounded support, explicit compatibility evidence, human-verified safety facts, and application-owned response structure.
- The central portfolio claim is reproducible accuracy and refusal behavior against weaker baselines, not general conversational bicycle knowledge.
- The remote-LLM latency target is 20 seconds median and 30 seconds p95 over the frozen evaluation set, excluding model warm-up. The artifact records the remote chat and embedding deployment; local GPU operation is not required.
- A checksum detects future source changes but cannot preserve a source that disappears. PDF parsing, table extraction, figures, and small-model routing or phrasing remain material failure sources.
- Passing evaluation does not establish production safety, domain-wide coverage, or agreement with current manuals.
- The next workflow step is to split this spec into implementation tickets; the parent spec should not itself be treated as a single implementation ticket.
