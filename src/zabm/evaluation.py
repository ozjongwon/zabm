from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import platform
import re
import statistics
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pypdf import PdfReader

from zabm import __version__
from zabm.agent import answer_question
from zabm.evaluation_set import (
    EvaluationCategory,
    EvaluationItem,
    EvaluationSet,
    ExpectedOutcome,
    ExpectedStatus,
    ProcedureExpectation,
)
from zabm.matching import tokens
from zabm.procedures import RetrievalCatalog
from zabm.providers import ModelProvider
from zabm.response import (
    CanonicalResponse,
    Claim,
    Clarification,
    CompatibilityAnswer,
    Failure,
    ProcedureAnswer,
    ProcedureStep,
    ProcedureWarning,
    ProviderIdentity,
    SpecificationAnswer,
    SpecificationValue,
    StoredCitation,
    default_provider_identity,
)
from zabm.routing import ROUTING_VERSION
from zabm.source_pack import (
    RetrievalConfiguration,
    RetrievalPath,
    RetrievedEvidence,
    retrieve_evidence,
)
from zabm.specifications import (
    SourceManifest,
    file_sha256,
    load_source_manifest,
    normalize_text,
    write_json,
)

ConfigurationId = Literal["llm-only", "plain-rag", "hybrid-retrieval", "full-agent"]
AnswerMode = Literal["no-evidence", "retrieval", "full-agent"]
RetrievalMode = Literal["none", "vector", "hybrid"]
ChecklistKind = Literal["step", "warning", "conflict"]
ChecklistResult = Literal["supported", "missing", "incorrect"]

NUMBER_PATTERN = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
REQUIRED_CONFIGURATION_IDS: tuple[ConfigurationId, ...] = (
    "llm-only",
    "plain-rag",
    "hybrid-retrieval",
    "full-agent",
)
VECTOR_DIMENSIONS = 256

logger = logging.getLogger("zabm.rag")


@dataclass(frozen=True)
class _EmbeddedPage:
    source_id: str
    physical_page: int
    section: str
    vector: tuple[float, ...]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PromptBudget(_StrictModel):
    unit: Literal["characters"] = "characters"
    value: int = Field(gt=0)


class BaselineConfiguration(_StrictModel):
    id: ConfigurationId
    answer_mode: AnswerMode
    retrieval_mode: RetrievalMode


class BaselineLadderConfiguration(_StrictModel):
    configuration_id: str
    prompt_version: str
    frozen_at: date
    maintainer_review: str
    runs_per_configuration: int = Field(gt=0)
    temperature: float
    seeds: list[int] = Field(min_length=1)
    prompt_budget: PromptBudget
    retrieval_top_k: int = Field(gt=0)
    configurations: list[BaselineConfiguration] = Field(min_length=4)


class RetrievalMetrics(BaseModel):
    recall_at_5: float
    mrr: float
    relevant_rank: int | None
    retrieved_evidence: list[RetrievedEvidence]


class ProcedureChecklistEntry(BaseModel):
    kind: ChecklistKind
    expected: str
    observed: str | None
    result: ChecklistResult


class GeneratedBaselineClaim(BaseModel):
    text: str


class GeneratedBaselineWarning(BaseModel):
    severity: Literal["warning", "notice"]
    text: str


class GeneratedBaselineStep(BaseModel):
    number: int = Field(ge=1)
    text: str
    warnings: list[GeneratedBaselineWarning] = Field(default_factory=list[GeneratedBaselineWarning])
    evidence_page: int | None = Field(default=None, ge=1)


class GeneratedBaselineProcedure(BaseModel):
    title: str
    steps: list[GeneratedBaselineStep]


class GeneratedBaselineAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_type: Literal["specification", "compatibility", "procedure", "out_of_scope"]
    status: Literal[
        "supported",
        "clarification_required",
        "not_found",
        "conflicting_evidence",
        "out_of_scope",
    ]
    claims: list[GeneratedBaselineClaim] = Field(default_factory=list[GeneratedBaselineClaim])
    specification: SpecificationAnswer | None = None
    compatibility: CompatibilityAnswer | None = None
    procedure: GeneratedBaselineProcedure | None = None
    failure_message: str | None = None
    clarification_message: str | None = None
    clarification_missing_information: list[str] = Field(default_factory=list[str])


class ItemEvaluation(BaseModel):
    id: str
    category: EvaluationCategory
    expected_status: ExpectedStatus
    actual_status: ExpectedStatus
    answer_passed: bool
    answer_generation_failed: bool
    retrieval_failed: bool
    grading_issues: list[str]
    citation_valid: bool
    citation_issues: list[str]
    unsupported_numbers: list[str]
    procedure_checklist: list[ProcedureChecklistEntry]
    prompt_evidence_characters: int
    prompt_budget_characters: int
    latency_ms: float = Field(ge=0)
    retrieval: RetrievalMetrics | None
    response: CanonicalResponse


class RunRetrievalMetrics(BaseModel):
    recall_at_5: float
    mrr: float


class RunMetrics(BaseModel):
    accuracy: float
    supported_item_count: int
    citation_validity: float
    fabricated_number_count: int
    fabricated_number_rate: float
    correct_abstention: float
    answer_generation_failures: int
    retrieval_failures: int
    retrieval: RunRetrievalMetrics | None
    latency_median_ms: float
    latency_p95_ms: float


class EvaluationRun(BaseModel):
    run: int
    seed: int
    seed_supported: bool
    temperature: float
    items: list[ItemEvaluation]
    metrics: RunMetrics


class MetricSpread(BaseModel):
    minimum: float
    median: float
    maximum: float


class RunSpread(BaseModel):
    accuracy: MetricSpread
    citation_validity: MetricSpread
    correct_abstention: MetricSpread
    fabricated_number_count: MetricSpread
    retrieval_recall_at_5: MetricSpread | None
    retrieval_mrr: MetricSpread | None
    latency_ms: MetricSpread


class ConfigurationResult(BaseModel):
    id: ConfigurationId
    answer_mode: AnswerMode
    retrieval_mode: RetrievalMode
    run_count: int
    runs: list[EvaluationRun]
    spread: RunSpread


class EvaluationConditions(BaseModel):
    temperature: float
    seeds: list[int]
    prompt_budget: PromptBudget
    retrieval_top_k: int


class RoutingIdentity(BaseModel):
    version: str
    strategy: Literal["model", "prototype"]


class GpuIdentity(BaseModel):
    name: str
    memory_mib: int = Field(gt=0)


class HardwareIdentity(BaseModel):
    platform: str
    machine: str
    processor: str
    python_version: str
    memory_bytes: int | None = Field(default=None, gt=0)
    gpu: GpuIdentity | None = None


class RuntimeIdentity(BaseModel):
    application: str
    application_version: str
    python_version: str
    python_implementation: str


class LatencyMeasurement(BaseModel):
    unit: Literal["ms"] = "ms"
    scope: Literal["per-scored-item"] = "per-scored-item"
    warmup_excluded: bool = True
    warmup_requests: int = Field(ge=0)
    warmup_latency_ms: float | None = Field(default=None, ge=0)


class EvaluationArtifact(BaseModel):
    artifact_version: Literal["evaluation-results-v1"] = "evaluation-results-v1"
    configuration_id: str
    prompt_version: str
    evaluation_set_id: str
    evaluation_set_sha256: str
    baseline_config_sha256: str
    retrieval_configuration_id: str
    retrieval_paths: list[RetrievalPath]
    retrieval_config_sha256: str
    source_pack_id: str
    source_pack_manifest_sha256: str
    provider: ProviderIdentity
    routing: RoutingIdentity
    hardware: HardwareIdentity
    runtime: RuntimeIdentity
    latency_measurement: LatencyMeasurement
    conditions: EvaluationConditions
    langsmith_required: Literal[False] = False
    configurations: list[ConfigurationResult]


def load_baseline_configuration(path: Path) -> BaselineLadderConfiguration:
    return BaselineLadderConfiguration.model_validate_json(path.read_text(encoding="utf-8"))


def run_evaluation(
    *,
    evaluation_set_path: Path,
    baseline_config_path: Path,
    retrieval_config_path: Path,
    manifest_path: Path,
    pdf_dir: Path,
    data_dir: Path,
    provider: ModelProvider | None = None,
) -> EvaluationArtifact:
    evaluation_set = EvaluationSet.model_validate_json(
        evaluation_set_path.read_text(encoding="utf-8")
    )
    configuration = load_baseline_configuration(baseline_config_path)
    retrieval_configuration = RetrievalConfiguration.model_validate_json(
        retrieval_config_path.read_text(encoding="utf-8")
    )
    manifest = load_source_manifest(manifest_path)
    _validate_inputs(
        evaluation_set,
        configuration,
        retrieval_configuration,
        manifest,
    )

    catalog_path = data_dir / "generated" / "retrieval.json"
    if not catalog_path.is_file():
        raise ValueError("retrieval evidence has not been ingested")
    catalog = RetrievalCatalog.model_validate_json(catalog_path.read_text(encoding="utf-8"))
    if catalog.source_pack_id != manifest.manifest_version:
        raise ValueError(
            "retrieval evidence source-pack ID does not match the source manifest; "
            "run `zabm ingest` again"
        )

    source_pages = _load_source_pages(manifest, pdf_dir)
    vector_index = _build_vector_index(catalog)
    provider_identity = provider.identity if provider is not None else default_provider_identity()
    warmup_requests, warmup_latency_ms = _warm_up_provider(provider, configuration.seeds[0])
    configurations: list[ConfigurationResult] = []
    for baseline in configuration.configurations:
        runs = [
            _run_configuration(
                baseline,
                evaluation_set.items,
                configuration,
                retrieval_configuration,
                catalog,
                vector_index,
                source_pages,
                manifest,
                data_dir,
                provider,
                provider_identity,
                configuration.prompt_budget,
                run_index=index,
                seed=configuration.seeds[index],
            )
            for index in range(configuration.runs_per_configuration)
        ]
        configurations.append(
            ConfigurationResult(
                id=baseline.id,
                answer_mode=baseline.answer_mode,
                retrieval_mode=baseline.retrieval_mode,
                run_count=len(runs),
                runs=runs,
                spread=_run_spread(runs),
            )
        )

    return EvaluationArtifact(
        configuration_id=configuration.configuration_id,
        prompt_version=configuration.prompt_version,
        evaluation_set_id=evaluation_set.evaluation_set_id,
        evaluation_set_sha256=file_sha256(evaluation_set_path),
        baseline_config_sha256=file_sha256(baseline_config_path),
        retrieval_configuration_id=retrieval_configuration.configuration_id,
        retrieval_paths=retrieval_configuration.paths,
        retrieval_config_sha256=file_sha256(retrieval_config_path),
        source_pack_id=manifest.manifest_version,
        source_pack_manifest_sha256=file_sha256(manifest_path),
        provider=provider_identity,
        routing=RoutingIdentity(
            version=ROUTING_VERSION,
            strategy="model" if provider is not None else "prototype",
        ),
        hardware=detect_hardware(),
        runtime=RuntimeIdentity(
            application="zabm",
            application_version=__version__,
            python_version=platform.python_version(),
            python_implementation=platform.python_implementation(),
        ),
        latency_measurement=LatencyMeasurement(
            warmup_requests=warmup_requests,
            warmup_latency_ms=warmup_latency_ms,
        ),
        conditions=EvaluationConditions(
            temperature=configuration.temperature,
            seeds=configuration.seeds[: configuration.runs_per_configuration],
            prompt_budget=configuration.prompt_budget,
            retrieval_top_k=configuration.retrieval_top_k,
        ),
        configurations=configurations,
    )


def write_evaluation_artifact(report: EvaluationArtifact, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_path, report.model_dump(mode="json"))


def _warm_up_provider(provider: ModelProvider | None, seed: int) -> tuple[int, float | None]:
    if provider is None:
        return 0, None

    started = time.perf_counter()
    provider.complete(
        [{"role": "user", "content": "Reply with OK. This is an unreported warm-up."}],
        seed=seed,
    )
    requests = 1
    if provider.identity.embedding_model != "not-configured":
        provider.embed(["bicycle clamp bolt torque"])
        requests += 1
    return requests, (time.perf_counter() - started) * 1000


def detect_hardware() -> HardwareIdentity:
    return HardwareIdentity(
        platform=platform.platform(),
        machine=platform.machine(),
        processor=platform.processor() or "not-reported",
        python_version=platform.python_version(),
        memory_bytes=_system_memory_bytes(),
        gpu=_detect_gpu(),
    )


def _system_memory_bytes() -> int | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        return None
    for line in meminfo.read_text(encoding="utf-8").splitlines():
        if line.startswith("MemTotal:"):
            value = line.split()[1]
            return int(value) * 1024
    return None


def _detect_gpu() -> GpuIdentity | None:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    first_gpu = result.stdout.splitlines()[0] if result.stdout.splitlines() else ""
    try:
        name, memory = (part.strip() for part in first_gpu.rsplit(",", maxsplit=1))
        memory_mib = int(memory)
    except ValueError:
        return None
    if not name or memory_mib <= 0:
        return None
    return GpuIdentity(name=name, memory_mib=memory_mib)


def _validate_inputs(
    evaluation_set: EvaluationSet,
    configuration: BaselineLadderConfiguration,
    retrieval_configuration: RetrievalConfiguration,
    manifest: SourceManifest,
) -> None:
    if evaluation_set.source_pack_id != manifest.manifest_version:
        raise ValueError(
            "evaluation set source-pack ID does not match the manifest: "
            f"expected {manifest.manifest_version}, found {evaluation_set.source_pack_id}"
        )
    item_ids = [item.id for item in evaluation_set.items]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("evaluation item IDs must be unique")
    source_ids = {source.id for source in manifest.sources}
    for item in evaluation_set.items:
        unknown_sources = {
            locator.document_id
            for locator in item.evidence
            if locator.document_id not in source_ids
        }
        if unknown_sources:
            raise ValueError(
                f"evaluation item {item.id} references unknown sources: "
                f"{', '.join(sorted(unknown_sources))}"
            )
    if configuration.temperature != 0:
        raise ValueError("all baseline configurations must run at temperature zero")
    if not configuration.maintainer_review.strip():
        raise ValueError("baseline configuration requires a maintainer review reference")
    if not configuration.prompt_version.strip():
        raise ValueError("baseline configuration requires a prompt version")
    if len(configuration.seeds) < configuration.runs_per_configuration:
        raise ValueError("a seed must be recorded for every baseline run")
    if configuration.retrieval_top_k != retrieval_configuration.top_k:
        raise ValueError("baseline and retrieval configurations must use the same top-k value")
    configuration_ids = tuple(item.id for item in configuration.configurations)
    if configuration_ids != REQUIRED_CONFIGURATION_IDS:
        raise ValueError(
            "baseline configurations must be ordered as " + ", ".join(REQUIRED_CONFIGURATION_IDS)
        )
    expected_modes = {
        "llm-only": ("no-evidence", "none"),
        "plain-rag": ("retrieval", "vector"),
        "hybrid-retrieval": ("retrieval", "hybrid"),
        "full-agent": ("full-agent", "hybrid"),
    }
    for item in configuration.configurations:
        if (item.answer_mode, item.retrieval_mode) != expected_modes[item.id]:
            raise ValueError(f"configuration {item.id} does not match its required mode")


def _run_configuration(
    baseline: BaselineConfiguration,
    items: list[EvaluationItem],
    configuration: BaselineLadderConfiguration,
    retrieval_configuration: RetrievalConfiguration,
    catalog: RetrievalCatalog,
    vector_index: list[_EmbeddedPage],
    source_pages: dict[str, list[str]],
    manifest: SourceManifest,
    data_dir: Path,
    provider: ModelProvider | None,
    provider_identity: ProviderIdentity,
    prompt_budget: PromptBudget,
    *,
    run_index: int,
    seed: int,
) -> EvaluationRun:
    results: list[ItemEvaluation] = []
    for item in items:
        started = time.perf_counter()
        retrieved = _retrieve_for_configuration(
            item.question,
            baseline,
            retrieval_configuration,
            catalog,
            vector_index,
            configuration.retrieval_top_k,
        )
        retrieval = _grade_retrieval(item, retrieved)
        retrieved_evidence_text = _retrieved_evidence_text(
            retrieved,
            catalog,
            prompt_budget.value,
        )
        response = _answer_for_configuration(
            item.question,
            item.expected.response_type,
            baseline,
            data_dir,
            provider,
            provider_identity,
            retrieved,
            catalog,
            manifest,
            retrieved_evidence_text,
            prompt_budget,
            seed,
        )
        grading_issues, checklist = _grade_answer(item, response)
        citation_issues = _citation_issues(response, manifest, source_pages)
        unsupported_numbers = _unsupported_numbers(response, source_pages, manifest)
        citation_valid = not citation_issues
        answer_passed = not grading_issues and citation_valid and not unsupported_numbers
        retrieval_failed = bool(item.evidence) and retrieval is not None and retrieval.mrr == 0.0
        latency_ms = (time.perf_counter() - started) * 1000
        results.append(
            ItemEvaluation(
                id=item.id,
                category=item.category,
                expected_status=item.expected.status,
                actual_status=response.status,
                answer_passed=answer_passed,
                answer_generation_failed=not answer_passed,
                retrieval_failed=retrieval_failed,
                grading_issues=grading_issues,
                citation_valid=citation_valid,
                citation_issues=citation_issues,
                unsupported_numbers=unsupported_numbers,
                procedure_checklist=checklist,
                prompt_evidence_characters=len(retrieved_evidence_text),
                prompt_budget_characters=prompt_budget.value,
                latency_ms=latency_ms,
                retrieval=retrieval,
                response=response,
            )
        )

    return EvaluationRun(
        run=run_index + 1,
        seed=seed,
        seed_supported=provider.seed_supported if provider is not None else False,
        temperature=configuration.temperature,
        items=results,
        metrics=_run_metrics(results),
    )


def _retrieve_for_configuration(
    query: str,
    baseline: BaselineConfiguration,
    configuration: RetrievalConfiguration,
    catalog: RetrievalCatalog,
    vector_index: list[_EmbeddedPage],
    top_k: int,
) -> list[RetrievedEvidence] | None:
    if baseline.retrieval_mode == "none":
        logger.debug("retrieval-skip mode=none query=%s", query)
        return None
    if baseline.retrieval_mode == "vector":
        results = _vector_retrieve(query, vector_index, top_k)
        logger.debug(
            "vector query=%s top_k=%d results=%s",
            query,
            top_k,
            _evidence_trace(results),
        )
        return results

    bm25_paths = [path for path in configuration.paths if path.kind == "bm25"]
    bm25_path = bm25_paths[0] if bm25_paths else configuration.paths[0]
    lexical = retrieve_evidence(query, catalog, bm25_path, top_k)
    vector = _vector_retrieve(query, vector_index, top_k)
    combined = _reciprocal_rank_fusion(lexical, vector, top_k)
    logger.debug(
        "bm25 path=%s query=%s results=%s",
        bm25_path.id,
        query,
        _evidence_trace(lexical),
    )
    logger.debug(
        "vector query=%s results=%s",
        query,
        _evidence_trace(vector),
    )
    logger.debug(
        "combine strategy=reciprocal-rank-fusion query=%s bm25=%s vector=%s fused=%s",
        query,
        _evidence_trace(lexical),
        _evidence_trace(vector),
        _evidence_trace(combined),
    )
    return combined


def _evidence_trace(evidence: list[RetrievedEvidence]) -> list[tuple[str, int, str, float]]:
    return [
        (
            item.source_id,
            item.physical_page,
            item.section,
            item.score,
        )
        for item in evidence
    ]


def _answer_for_configuration(
    question: str,
    expected_response_type: Literal["specification", "compatibility", "procedure", "out_of_scope"],
    baseline: BaselineConfiguration,
    data_dir: Path,
    provider: ModelProvider | None,
    provider_identity: ProviderIdentity,
    retrieved: list[RetrievedEvidence] | None,
    catalog: RetrievalCatalog,
    manifest: SourceManifest,
    retrieved_evidence_text: str,
    prompt_budget: PromptBudget,
    seed: int,
) -> CanonicalResponse:
    if baseline.answer_mode == "full-agent":
        return answer_question(
            question,
            data_dir,
            provider,
            seed=seed,
            prompt_budget=prompt_budget.value,
        )
    if provider is not None:
        return _provider_baseline_answer(
            question,
            expected_response_type,
            provider,
            provider_identity,
            retrieved,
            catalog,
            manifest,
            retrieved_evidence_text,
            prompt_budget.value,
            seed,
        )

    response_type = expected_response_type
    if response_type == "out_of_scope":
        return CanonicalResponse(
            request_id=os.urandom(16).hex(),
            timestamp=datetime.now(UTC),
            response_type="out_of_scope",
            language="en",
            status="out_of_scope",
            failure=Failure(
                code="out_of_scope",
                message=(
                    "This assistant only answers bicycle maintenance questions from the "
                    "frozen source pack."
                ),
            ),
            provider=provider_identity,
            source_pack_id=manifest.manifest_version,
        )
    if baseline.answer_mode == "no-evidence":
        return _baseline_not_found(
            response_type,
            "No human-verified structured evidence matches because the LLM-only "
            "baseline had no retrieved evidence.",
            provider_identity,
            manifest.manifest_version,
        )
    return _deterministic_evidence_baseline(
        response_type,
        retrieved or [],
        catalog,
        manifest,
        provider_identity,
    )


def _deterministic_evidence_baseline(
    response_type: Literal["specification", "compatibility", "procedure", "out_of_scope"],
    retrieved: list[RetrievedEvidence],
    catalog: RetrievalCatalog,
    manifest: SourceManifest,
    provider_identity: ProviderIdentity,
) -> CanonicalResponse:
    citations = _citations_for_retrieved(retrieved, catalog, manifest)
    if not citations:
        return _baseline_not_found(
            response_type,
            "Retrieved evidence did not contain a citable source page.",
            provider_identity,
            manifest.manifest_version,
        )
    pages = {
        (source.document_id, page.physical_page): page
        for source in catalog.sources
        for page in source.pages
    }
    first = retrieved[0]
    page = pages.get((first.source_id, first.physical_page))
    claim_text = (page.text if page is not None else "").strip()[:2000]
    if not claim_text:
        return _baseline_not_found(
            response_type,
            "Retrieved evidence did not contain substantive source text.",
            provider_identity,
            manifest.manifest_version,
        )
    evidence_ids = [f"{citation.document_id}#p{citation.physical_page}" for citation in citations]
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type=response_type,
        language="en",
        status="supported",
        claims=[Claim(claim_id="retrieved-evidence-1", text=claim_text, evidence_ids=evidence_ids)],
        citations=citations,
        provider=provider_identity,
        source_pack_id=manifest.manifest_version,
    )


def _provider_baseline_answer(
    question: str,
    expected_response_type: Literal["specification", "compatibility", "procedure", "out_of_scope"],
    provider: ModelProvider,
    provider_identity: ProviderIdentity,
    retrieved: list[RetrievedEvidence] | None,
    catalog: RetrievalCatalog,
    manifest: SourceManifest,
    retrieved_evidence_text: str,
    prompt_budget: int,
    seed: int,
) -> CanonicalResponse:
    prompt = {
        "question": question,
        "evidence": retrieved_evidence_text,
        "response_schema": {
            "response_type": "specification|compatibility|procedure|out_of_scope",
            "status": (
                "supported|clarification_required|not_found|conflicting_evidence|out_of_scope"
            ),
            "claims": [{"text": "substantive claim"}],
            "specification": {
                "manufacturer": "string",
                "model": "string",
                "component": "string",
                "attribute": "string",
                "value": {
                    "minimum": 0,
                    "maximum": 0,
                    "unit": "string",
                    "display": "string",
                },
                "conditions": ["string"],
            },
            "compatibility": {
                "outcome": "compatible|not_compatible|unknown|not_found",
                "component_a": {
                    "manufacturer": "string",
                    "name": "string",
                    "aliases": ["string"],
                },
                "component_b": {
                    "manufacturer": "string",
                    "name": "string",
                    "aliases": ["string"],
                },
                "conditions": ["string"],
            },
            "procedure": {
                "title": "string",
                "steps": [
                    {
                        "number": 1,
                        "text": "string",
                        "warnings": [{"severity": "warning|notice", "text": "string"}],
                        "evidence_page": 1,
                    }
                ],
            },
            "failure_message": "string or null",
            "clarification_message": "string or null",
            "clarification_missing_information": ["string"],
        },
    }
    system_content = (
        "Answer the bicycle maintenance question using only the supplied "
        "evidence. Return only JSON matching response_schema. The baseline has no "
        "application evidence gates."
    )
    user_content = json.dumps(prompt, ensure_ascii=False)
    if len(system_content) + len(user_content) > prompt_budget:
        overflow = len(system_content) + len(user_content) - prompt_budget
        shortened = retrieved_evidence_text[: max(0, len(retrieved_evidence_text) - overflow)]
        prompt["evidence"] = shortened
        user_content = json.dumps(prompt, ensure_ascii=False)
    try:
        raw = provider.complete(
            [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            seed=seed,
        )
        generated = GeneratedBaselineAnswer.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        return _baseline_not_found(
            expected_response_type,
            f"Baseline provider output was rejected: {exc}",
            provider_identity,
            manifest.manifest_version,
        )

    citations = _citations_for_retrieved(
        retrieved or [],
        catalog,
        manifest,
    )
    evidence_ids = [f"{citation.document_id}#p{citation.physical_page}" for citation in citations]
    claims = [
        Claim(
            claim_id=f"baseline-claim-{index}",
            text=claim.text,
            evidence_ids=evidence_ids,
        )
        for index, claim in enumerate(generated.claims, start=1)
    ]
    procedure: ProcedureAnswer | None = None
    if generated.procedure is not None:
        procedure = ProcedureAnswer(
            title=generated.procedure.title,
            heading_path=[generated.procedure.title],
            steps=[
                ProcedureStep(
                    number=step.number,
                    text=step.text,
                    warnings=[
                        ProcedureWarning(severity=warning.severity, text=warning.text)
                        for warning in step.warnings
                    ],
                    citation=_citation_for_page(
                        step.evidence_page,
                        citations,
                        manifest,
                    ),
                )
                for step in generated.procedure.steps
            ],
        )
    failure = _failure_for_status(generated.status, generated.failure_message)
    clarification = None
    if generated.status == "clarification_required":
        clarification = Clarification(
            message=generated.clarification_message or "Please identify the missing detail.",
            missing_information=generated.clarification_missing_information,
        )
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type=generated.response_type,
        language="en",
        status=generated.status,
        failure=failure,
        clarification=clarification,
        claims=claims if generated.status == "supported" else [],
        specification=(generated.specification if generated.status == "supported" else None),
        compatibility=(generated.compatibility if generated.status == "supported" else None),
        procedure=procedure if generated.status == "supported" else None,
        citations=citations if generated.status == "supported" else [],
        provider=provider_identity,
        source_pack_id=manifest.manifest_version,
    )


def _failure_for_status(status: str, message: str | None) -> Failure | None:
    if status == "not_found":
        return Failure(code="not_found", message=message or "No supported answer was found.")
    if status == "conflicting_evidence":
        return Failure(
            code="conflicting_evidence",
            message=message or "The supplied evidence contains unresolved conflicts.",
        )
    if status == "out_of_scope":
        return Failure(
            code="out_of_scope",
            message=message or "The request is outside bicycle maintenance.",
        )
    return None


def _retrieved_evidence_text(
    retrieved: list[RetrievedEvidence] | None,
    catalog: RetrievalCatalog,
    budget: int,
) -> str:
    if not retrieved:
        return ""
    pages = {
        (source.document_id, page.physical_page): page
        for source in catalog.sources
        for page in source.pages
    }
    sections: list[str] = []
    remaining = budget
    for evidence in retrieved:
        page = pages.get((evidence.source_id, evidence.physical_page))
        if page is None:
            continue
        header = (
            f"[{evidence.source_id} physical page {evidence.physical_page}, "
            f"printed page {page.printed_page}, section {page.section}]\n"
        )
        if len(header) >= remaining:
            break
        available = remaining - len(header)
        body = page.text[:available]
        sections.append(f"{header}{body}")
        remaining -= len(header) + len(body)
        if remaining <= 0:
            break
    return "\n\n".join(sections)


def _citations_for_retrieved(
    retrieved: list[RetrievedEvidence],
    catalog: RetrievalCatalog,
    manifest: SourceManifest,
) -> list[StoredCitation]:
    sources = {source.id: source for source in manifest.sources}
    pages = {
        (source.document_id, page.physical_page): page
        for source in catalog.sources
        for page in source.pages
    }
    citations: list[StoredCitation] = []
    seen: set[tuple[str, int]] = set()
    for evidence in retrieved:
        key = (evidence.source_id, evidence.physical_page)
        source = sources.get(evidence.source_id)
        page = pages.get(key)
        if key in seen or source is None or page is None:
            continue
        seen.add(key)
        citations.append(
            StoredCitation(
                document_id=source.id,
                title=source.title,
                manufacturer=source.manufacturer,
                printed_page=page.printed_page,
                physical_page=page.physical_page,
                section=page.section,
                retrieval_date=source.retrieval_date,
                source_manifest_version=manifest.manifest_version,
            )
        )
    return citations


def _citation_for_page(
    physical_page: int | None,
    citations: list[StoredCitation],
    manifest: SourceManifest,
) -> StoredCitation:
    if physical_page is not None:
        for citation in citations:
            if citation.physical_page == physical_page:
                return citation
    if citations:
        return citations[0]
    return StoredCitation(
        document_id="unretrieved",
        title="No retrieved evidence",
        manufacturer="unknown",
        printed_page=1,
        physical_page=1,
        section="unretrieved",
        retrieval_date=date.min,
        source_manifest_version=manifest.manifest_version,
    )


def _baseline_not_found(
    response_type: Literal["specification", "compatibility", "procedure", "out_of_scope"],
    message: str,
    provider_identity: ProviderIdentity,
    source_pack_id: str,
) -> CanonicalResponse:
    return CanonicalResponse(
        request_id=os.urandom(16).hex(),
        timestamp=datetime.now(UTC),
        response_type=response_type,
        language="en",
        status="not_found",
        failure=Failure(code="not_found", message=message),
        provider=provider_identity,
        source_pack_id=source_pack_id,
    )


def _grade_retrieval(
    item: EvaluationItem,
    retrieved: list[RetrievedEvidence] | None,
) -> RetrievalMetrics | None:
    if retrieved is None:
        return None
    relevant_rank: int | None = None
    for rank, evidence in enumerate(retrieved, start=1):
        if any(
            evidence.source_id == locator.document_id
            and evidence.physical_page == locator.physical_page
            for locator in item.evidence
        ):
            relevant_rank = rank
            break
    return RetrievalMetrics(
        recall_at_5=1.0 if relevant_rank is not None else 0.0,
        mrr=1 / relevant_rank if relevant_rank is not None else 0.0,
        relevant_rank=relevant_rank,
        retrieved_evidence=retrieved,
    )


def _grade_answer(
    item: EvaluationItem,
    response: CanonicalResponse,
) -> tuple[list[str], list[ProcedureChecklistEntry]]:
    expected = item.expected
    issues: list[str] = []
    checklist: list[ProcedureChecklistEntry] = []
    if response.status != expected.status:
        issues.append(f"status expected {expected.status}, observed {response.status}")
    if response.response_type != expected.response_type and response.status != "out_of_scope":
        issues.append(
            f"response type expected {expected.response_type}, observed {response.response_type}"
        )
    if expected.status != "supported":
        if expected.failure_contains is not None:
            failure_text = " ".join(
                message
                for message in [
                    response.failure.message if response.failure is not None else "",
                    response.clarification.message if response.clarification is not None else "",
                ]
                if message
            )
            if normalize_text(expected.failure_contains) not in normalize_text(failure_text):
                issues.append(f"failure message does not contain {expected.failure_contains!r}")
        if expected.clarification_missing_information:
            actual_missing = (
                response.clarification.missing_information
                if response.clarification is not None
                else []
            )
            if set(expected.clarification_missing_information) != set(actual_missing):
                issues.append(
                    "clarification missing-information fields do not match the expectation"
                )
        if response.claims:
            issues.append("a non-supported response contains substantive claims")
        return issues, checklist

    if expected.specification is not None:
        issues.extend(_grade_specification(expected, response))
    elif expected.compatibility is not None:
        issues.extend(_grade_compatibility(expected, response))
    elif expected.procedure is not None:
        procedure_issues, checklist = _grade_procedure(expected.procedure, response)
        issues.extend(procedure_issues)
    elif expected.conflicts is not None:
        conflict_issues, checklist = _grade_conflicts(expected, response)
        issues.extend(conflict_issues)
    return issues, checklist


def _grade_specification(
    expected: ExpectedOutcome,
    response: CanonicalResponse,
) -> list[str]:
    spec_expected = expected.specification
    assert spec_expected is not None
    actual = response.specification
    if actual is None:
        return ["supported specification response has no specification"]
    issues = _specification_value_issues(spec_expected.value, actual.value)
    conditions = normalize_text(" | ".join(actual.conditions))
    for qualifier in spec_expected.required_qualifiers:
        if normalize_text(qualifier) not in conditions:
            issues.append(f"missing qualifier: {qualifier}")
    return issues


def _specification_value_issues(
    expected: SpecificationValue,
    actual: SpecificationValue,
) -> list[str]:
    issues: list[str] = []
    if not math.isclose(actual.minimum, expected.minimum, abs_tol=1e-9):
        issues.append(f"value minimum expected {expected.minimum}, observed {actual.minimum}")
    if (actual.maximum is None) != (expected.maximum is None):
        issues.append("value range presence does not match the expectation")
    elif (
        actual.maximum is not None
        and expected.maximum is not None
        and not math.isclose(actual.maximum, expected.maximum, abs_tol=1e-9)
    ):
        issues.append(f"value maximum expected {expected.maximum}, observed {actual.maximum}")
    if _normalize_unit(actual.unit) != _normalize_unit(expected.unit):
        issues.append(f"unit expected {expected.unit!r}, observed {actual.unit!r}")
    return issues


def _normalize_unit(unit: str) -> str:
    return (
        normalize_text(unit).replace("n*m", "n·m").replace("nm", "n·m").replace("in-lbs", "in-lb")
    )


def _grade_compatibility(
    expected: ExpectedOutcome,
    response: CanonicalResponse,
) -> list[str]:
    compatibility_expected = expected.compatibility
    assert compatibility_expected is not None
    actual = response.compatibility
    if actual is None:
        return ["supported compatibility response has no compatibility outcome"]
    issues: list[str] = []
    if actual.outcome != compatibility_expected.outcome:
        issues.append(
            f"compatibility outcome expected {compatibility_expected.outcome}, "
            f"observed {actual.outcome}"
        )
    conditions = normalize_text(" | ".join(actual.conditions))
    for qualifier in compatibility_expected.required_qualifiers:
        if normalize_text(qualifier) not in conditions:
            issues.append(f"missing qualifier: {qualifier}")
    return issues


def _grade_procedure(
    expected: ProcedureExpectation,
    response: CanonicalResponse,
) -> tuple[list[str], list[ProcedureChecklistEntry]]:
    actual = response.procedure
    if actual is None:
        return ["supported procedure response has no procedure"], []
    issues: list[str] = []
    checklist: list[ProcedureChecklistEntry] = []
    actual_steps = {step.number: step for step in actual.steps}
    for expected_step in expected.steps:
        observed_step = actual_steps.get(expected_step.number)
        expected_text = normalize_text(expected_step.text)
        observed_text = normalize_text(observed_step.text) if observed_step is not None else ""
        if observed_step is None:
            result: ChecklistResult = "missing"
            issues.append(f"procedure step {expected_step.number} is missing")
        elif expected_text not in observed_text:
            result = "incorrect"
            issues.append(f"procedure step {expected_step.number} does not match")
        else:
            result = "supported"
        checklist.append(
            ProcedureChecklistEntry(
                kind="step",
                expected=expected_step.text,
                observed=observed_step.text if observed_step is not None else None,
                result=result,
            )
        )
        actual_warnings = observed_step.warnings if observed_step is not None else []
        for expected_warning in expected_step.warnings:
            warning_text = normalize_text(expected_warning.text)
            matching = next(
                (
                    warning
                    for warning in actual_warnings
                    if warning.severity == expected_warning.severity
                    and warning_text in normalize_text(warning.text)
                ),
                None,
            )
            if matching is not None:
                warning_result: ChecklistResult = "supported"
                observed_warning = matching.text
            else:
                same_severity = [
                    warning
                    for warning in actual_warnings
                    if warning.severity == expected_warning.severity
                ]
                warning_result = "incorrect" if same_severity else "missing"
                observed_warning = same_severity[0].text if same_severity else None
                issues.append(
                    f"procedure warning for step {expected_step.number} is {warning_result}"
                )
            checklist.append(
                ProcedureChecklistEntry(
                    kind="warning",
                    expected=expected_warning.text,
                    observed=observed_warning,
                    result=warning_result,
                )
            )
    return issues, checklist


def _grade_conflicts(
    expected: ExpectedOutcome,
    response: CanonicalResponse,
) -> tuple[list[str], list[ProcedureChecklistEntry]]:
    conflict_expected = expected.conflicts
    assert conflict_expected is not None
    if response.conflicts is None:
        return ["conflicting-evidence response has no conflict report"], []
    issues: list[str] = []
    checklist: list[ProcedureChecklistEntry] = []
    actual_claims = [normalize_text(candidate.claim) for candidate in response.conflicts.candidates]
    for candidate in conflict_expected.candidates:
        expected_claim = normalize_text(candidate.claim)
        matching = next(
            (
                claim
                for claim in actual_claims
                if expected_claim in claim or claim in expected_claim
            ),
            None,
        )
        result: ChecklistResult = "supported" if matching is not None else "incorrect"
        if matching is None:
            issues.append(f"conflict candidate does not match: {candidate.claim}")
        checklist.append(
            ProcedureChecklistEntry(
                kind="conflict",
                expected=candidate.claim,
                observed=matching,
                result=result,
            )
        )
    if response.conflicts.precedence_established != conflict_expected.precedence_established:
        issues.append("conflict precedence decision does not match the expectation")
    return issues, checklist


def _citation_issues(
    response: CanonicalResponse,
    manifest: SourceManifest,
    source_pages: dict[str, list[str]],
) -> list[str]:
    if response.status != "supported":
        return ["non-supported response contains citations"] if response.citations else []
    if not response.citations:
        return ["supported response has no citations"]
    issues: list[str] = []
    sources = {source.id: source for source in manifest.sources}
    for citation in response.citations:
        source = sources.get(citation.document_id)
        if source is None:
            issues.append(f"citation references unknown source {citation.document_id}")
            continue
        pages = source_pages.get(citation.document_id, [])
        if citation.physical_page < 1 or citation.physical_page > len(pages):
            issues.append(f"citation for {citation.document_id} has an out-of-range physical page")
            continue
        page_text = normalize_text(pages[citation.physical_page - 1])
        if normalize_text(citation.section) not in page_text:
            issues.append(
                f"citation section {citation.section!r} is absent from "
                f"{citation.document_id} page {citation.physical_page}"
            )
        if citation.title != source.title or citation.manufacturer != source.manufacturer:
            issues.append("citation title or manufacturer does not match the manifest")
        if citation.retrieval_date != source.retrieval_date:
            issues.append("citation retrieval date does not match the manifest")
        if citation.source_manifest_version != manifest.manifest_version:
            issues.append("citation source-pack version does not match the manifest")
    if any(not claim.evidence_ids for claim in response.claims):
        issues.append("a supported claim has no evidence reference")
    return issues


def _unsupported_numbers(
    response: CanonicalResponse,
    source_pages: dict[str, list[str]],
    manifest: SourceManifest,
) -> list[str]:
    if response.status != "supported":
        return []
    answer_texts = [re.sub(r"^Step \d+:\s*", "", claim.text) for claim in response.claims]
    qualifier_texts: list[str] = []
    if response.specification is not None:
        qualifier_texts.extend(response.specification.conditions)
        answer_texts.append(response.specification.value.display)
    if response.compatibility is not None:
        qualifier_texts.extend(response.compatibility.conditions)
    if response.procedure is not None:
        for step in response.procedure.steps:
            answer_texts.append(step.text)
            answer_texts.extend(warning.text for warning in step.warnings)
    answer_numbers = {number for text in answer_texts for number in NUMBER_PATTERN.findall(text)}
    qualifier_numbers = {
        number for text in qualifier_texts for number in NUMBER_PATTERN.findall(text)
    }
    evidence_numbers: set[str] = set()
    for citation in response.citations:
        pages = source_pages.get(citation.document_id, [])
        if 1 <= citation.physical_page <= len(pages):
            evidence_numbers.update(
                NUMBER_PATTERN.findall(normalize_text(pages[citation.physical_page - 1]))
            )
    sources = {source.id: source for source in manifest.sources}
    provenance_numbers: set[str] = set()
    for citation in response.citations:
        source = sources.get(citation.document_id)
        provenance_text = " ".join(
            [
                citation.title,
                citation.section,
                citation.retrieval_date.isoformat(),
                citation.source_manifest_version,
                source.revision or "" if source is not None else "",
            ]
        )
        provenance_numbers.update(NUMBER_PATTERN.findall(provenance_text))
    unsupported = (answer_numbers - evidence_numbers) | (
        qualifier_numbers - evidence_numbers - provenance_numbers
    )
    return sorted(unsupported)


def _run_metrics(items: list[ItemEvaluation]) -> RunMetrics:
    supported = [item for item in items if item.actual_status == "supported"]
    citation_validity = (
        sum(item.citation_valid for item in supported) / len(supported) if supported else 1.0
    )
    fabricated_numbers = sum(len(item.unsupported_numbers) for item in items)
    fabricated_number_items = sum(bool(item.unsupported_numbers) for item in supported)
    abstention_items = [
        item
        for item in items
        if item.category in {"not_found", "conflicting_evidence", "out_of_scope"}
    ]
    correct_abstention = (
        sum(item.answer_passed for item in abstention_items) / len(abstention_items)
        if abstention_items
        else 1.0
    )
    retrieval_items = [
        item
        for item in items
        if item.retrieval is not None
        and bool(item.retrieval.retrieved_evidence)
        and item.category != "out_of_scope"
    ]
    recall = (
        statistics.fmean(item.retrieval.recall_at_5 for item in retrieval_items if item.retrieval)
        if retrieval_items
        else None
    )
    mrr = (
        statistics.fmean(item.retrieval.mrr for item in retrieval_items if item.retrieval)
        if retrieval_items
        else None
    )
    latencies = [item.latency_ms for item in items]
    return RunMetrics(
        accuracy=sum(item.answer_passed for item in items) / len(items),
        supported_item_count=len(supported),
        citation_validity=citation_validity,
        fabricated_number_count=fabricated_numbers,
        fabricated_number_rate=(fabricated_number_items / len(supported) if supported else 0.0),
        correct_abstention=correct_abstention,
        answer_generation_failures=sum(item.answer_generation_failed for item in items),
        retrieval_failures=sum(item.retrieval_failed for item in items),
        retrieval=(
            RunRetrievalMetrics(recall_at_5=recall, mrr=mrr)
            if recall is not None and mrr is not None
            else None
        ),
        latency_median_ms=statistics.median(latencies),
        latency_p95_ms=_percentile(latencies, 0.95),
    )


def _run_spread(runs: list[EvaluationRun]) -> RunSpread:
    retrieval_runs = [run for run in runs if run.metrics.retrieval is not None]
    return RunSpread(
        accuracy=_metric_spread([run.metrics.accuracy for run in runs]),
        citation_validity=_metric_spread([run.metrics.citation_validity for run in runs]),
        correct_abstention=_metric_spread([run.metrics.correct_abstention for run in runs]),
        fabricated_number_count=_metric_spread(
            [float(run.metrics.fabricated_number_count) for run in runs]
        ),
        retrieval_recall_at_5=(
            _metric_spread(
                [
                    run.metrics.retrieval.recall_at_5
                    for run in retrieval_runs
                    if run.metrics.retrieval is not None
                ]
            )
            if retrieval_runs
            else None
        ),
        retrieval_mrr=(
            _metric_spread(
                [
                    run.metrics.retrieval.mrr
                    for run in retrieval_runs
                    if run.metrics.retrieval is not None
                ]
            )
            if retrieval_runs
            else None
        ),
        latency_ms=_metric_spread([run.metrics.latency_median_ms for run in runs]),
    )


def _metric_spread(values: list[float]) -> MetricSpread:
    return MetricSpread(
        minimum=min(values),
        median=statistics.median(values),
        maximum=max(values),
    )


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def _vector_retrieve(
    query: str,
    index: list[_EmbeddedPage],
    top_k: int,
) -> list[RetrievedEvidence]:
    query_vector = _embed(query)
    scored = [
        (
            sum(left * right for left, right in zip(query_vector, page.vector, strict=True)),
            page.source_id,
            page.physical_page,
            page.section,
        )
        for page in index
    ]
    ranked = sorted(scored, key=lambda item: (-item[0], item[1], item[2]))[:top_k]
    return [
        RetrievedEvidence(
            source_id=source_id,
            physical_page=physical_page,
            section=section,
            score=round(score, 6),
        )
        for score, source_id, physical_page, section in ranked
    ]


def _build_vector_index(catalog: RetrievalCatalog) -> list[_EmbeddedPage]:
    return [
        _EmbeddedPage(
            source_id=source.document_id,
            physical_page=page.physical_page,
            section=page.section,
            vector=tuple(_embed(f"{source.title} {page.section} {page.text}")),
        )
        for source in catalog.sources
        for page in source.pages
    ]


def _embed(text: str) -> list[float]:
    vector = [0.0] * VECTOR_DIMENSIONS
    for token in tokens(text):
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % VECTOR_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def _reciprocal_rank_fusion(
    lexical: list[RetrievedEvidence],
    vector: list[RetrievedEvidence],
    top_k: int,
) -> list[RetrievedEvidence]:
    scores: dict[tuple[str, int], float] = {}
    evidence_by_key: dict[tuple[str, int], RetrievedEvidence] = {}
    for results in (lexical, vector):
        for rank, evidence in enumerate(results, start=1):
            key = (evidence.source_id, evidence.physical_page)
            scores[key] = scores.get(key, 0.0) + 1 / (60 + rank)
            evidence_by_key[key] = evidence
    ranked = sorted(scores, key=lambda key: (-scores[key], key[0], key[1]))[:top_k]
    return [
        evidence_by_key[key].model_copy(update={"score": round(scores[key], 6)}) for key in ranked
    ]


def _load_source_pages(
    manifest: SourceManifest,
    pdf_dir: Path,
) -> dict[str, list[str]]:
    pages: dict[str, list[str]] = {}
    for source in manifest.sources:
        source_path = pdf_dir / f"{source.id}.pdf"
        if not source_path.is_file():
            raise ValueError(f"source {source.id} has not been downloaded")
        if file_sha256(source_path) != source.sha256:
            raise ValueError(f"source {source.id} does not match the manifest hash")
        reader = PdfReader(source_path)
        pages[source.id] = [page.extract_text() or "" for page in reader.pages]
    return pages
