from __future__ import annotations

import math
import statistics
from collections import Counter
from pathlib import Path
from random import Random
from typing import Any, Literal

from pydantic import BaseModel, Field

from zabm.evaluation import (
    ConfigurationId,
    ConfigurationResult,
    EvaluationArtifact,
    EvaluationConditions,
    EvaluationRun,
    HardwareIdentity,
    MetricSpread,
    ProviderIdentity,
    RunMetrics,
    RunSpread,
    RuntimeIdentity,
)
from zabm.specifications import file_sha256, write_json

GateStatus = Literal["passed", "failed", "not_applicable"]
ExecutionEnvironment = Literal["remote-llm"]
REQUIRED_EVALUATION_ITEMS = 120
REQUIRED_RUNS = 3
DEFAULT_BOOTSTRAP_SEED = 20_261_124
DEFAULT_BOOTSTRAP_RESAMPLES = 10_000
ABSTENTION_CATEGORIES = frozenset({"not_found", "conflicting_evidence", "out_of_scope"})
FROZEN_CATEGORY_COUNTS = {
    "specification": 36,
    "compatibility": 27,
    "procedure": 27,
    "not_found": 15,
    "conflicting_evidence": 8,
    "out_of_scope": 7,
}


class AcceptanceEvaluationIdentity(BaseModel):
    path: str
    sha256: str
    artifact_version: str
    configuration_id: str
    prompt_version: str
    evaluation_set_id: str
    evaluation_set_sha256: str
    baseline_config_sha256: str
    retrieval_configuration_id: str
    retrieval_config_sha256: str
    source_pack_id: str
    source_pack_manifest_sha256: str


class AcceptanceMethodology(BaseModel):
    bootstrap_method: Literal["item-paired-averaged-runs-percentile-v1"] = (
        "item-paired-averaged-runs-percentile-v1"
    )
    bootstrap_seed: int
    bootstrap_resamples: int = Field(gt=0)
    confidence_level: float = 0.95
    latency_scope: Literal["per-scored-item"] = "per-scored-item"
    latency_run_selection: Literal["median-accuracy-run"] = "median-accuracy-run"
    warmup_excluded: bool


class AcceptanceRun(BaseModel):
    run: int
    seed: int
    seed_supported: bool
    temperature: float
    metrics: RunMetrics


class AcceptanceConfiguration(BaseModel):
    id: ConfigurationId
    answer_mode: str
    retrieval_mode: str
    run_count: int
    runs: list[AcceptanceRun]
    accuracy: MetricSpread
    citation_validity: MetricSpread
    correct_abstention: MetricSpread
    fabricated_number_count: MetricSpread
    retrieval_recall_at_5: MetricSpread | None
    retrieval_mrr: MetricSpread | None
    latency_ms: MetricSpread


class PairedDifference(BaseModel):
    baseline_id: Literal["llm-only", "plain-rag"]
    item_count: int
    observed_mean_difference: float
    lower_bound: float
    upper_bound: float
    positive_item_differences: int
    equal_item_differences: int
    item_differences: list[float]


class GateResult(BaseModel):
    id: str
    status: GateStatus
    threshold: Any
    observed: Any
    diagnosis: str


class AcceptanceReport(BaseModel):
    artifact_version: Literal["acceptance-report-v1"] = "acceptance-report-v1"
    status: Literal["passed", "failed"]
    execution_environment: ExecutionEnvironment
    evaluation: AcceptanceEvaluationIdentity
    methodology: AcceptanceMethodology
    provider: ProviderIdentity
    hardware: HardwareIdentity
    runtime: RuntimeIdentity
    conditions: EvaluationConditions
    configurations: list[AcceptanceConfiguration]
    paired_differences: list[PairedDifference]
    gates: list[GateResult]
    failed_gates: list[str]


def load_evaluation_artifact(path: Path) -> EvaluationArtifact:
    return EvaluationArtifact.model_validate_json(path.read_text(encoding="utf-8"))


def build_acceptance_report(
    *,
    evaluation_path: Path,
    evaluation: EvaluationArtifact,
    execution_environment: ExecutionEnvironment,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
    bootstrap_resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
) -> AcceptanceReport:
    configurations = _validate_evaluation(evaluation)
    full_agent = configurations["full-agent"]
    median_full_agent_run = _median_run(full_agent)
    full_accuracy = median_full_agent_run.metrics.accuracy
    baseline_accuracies = {
        configuration_id: _median_run(configurations[configuration_id]).metrics.accuracy
        for configuration_id in ("llm-only", "plain-rag")
    }
    paired_differences = [
        _paired_difference(
            full_agent,
            configurations[baseline_id],
            baseline_id,
            seed=bootstrap_seed,
            resamples=bootstrap_resamples,
        )
        for baseline_id in ("llm-only", "plain-rag")
    ]
    citation_validity, supported_count = _citation_validity(full_agent)
    abstention, abstention_by_category = _abstention(full_agent)
    fabricated_count = sum(
        len(item.unsupported_numbers) for run in full_agent.runs for item in run.items
    )
    latencies = [item.latency_ms for item in median_full_agent_run.items]
    latency_median = statistics.median(latencies)
    latency_p95 = _percentile(latencies, 0.95)

    gates = [
        _gate(
            "full_agent_accuracy",
            full_accuracy >= 0.90,
            threshold=0.90,
            observed=full_accuracy,
            success="median scored run meets the 90% accuracy threshold",
            failure=(
                f"median scored run accuracy {full_accuracy:.2%} is below 90%; "
                f"select the failing item diagnostics from the evaluation artifact"
            ),
        ),
        _improvement_gate(
            "improvement_over_llm_only",
            full_accuracy,
            baseline_accuracies["llm-only"],
            paired_differences[0],
        ),
        _improvement_gate(
            "improvement_over_plain_rag",
            full_accuracy,
            baseline_accuracies["plain-rag"],
            paired_differences[1],
        ),
        _gate(
            "citation_validity",
            supported_count > 0 and citation_validity >= 0.95,
            threshold=0.95,
            observed=citation_validity,
            success="pooled citation validity meets the 95% threshold",
            failure=(
                f"pooled citation validity {citation_validity:.2%} across "
                f"{supported_count} supported item-runs is below 95%"
            ),
        ),
        _gate(
            "correct_abstention",
            abstention >= 0.95 and all(value >= 0.95 for value in abstention_by_category.values()),
            threshold=0.95,
            observed={
                "overall": abstention,
                "by_category": abstention_by_category,
            },
            success="pooled abstention meets the 95% threshold in every category",
            failure=(
                f"pooled correct abstention {abstention:.2%} is below 95% "
                "or a refusal category is below the threshold"
            ),
        ),
        _gate(
            "fabricated_numeric_values",
            fabricated_count == 0,
            threshold=0,
            observed=fabricated_count,
            success="no fabricated numeric values were recorded",
            failure=f"{fabricated_count} fabricated numeric value(s) were recorded",
        ),
        _remote_llm_latency_gate(
            latency_median,
            latency_p95,
            warmup_excluded=evaluation.latency_measurement.warmup_excluded,
            model_backed=evaluation.provider.provider != "local-deterministic",
        ),
    ]
    failed_gates = [gate.id for gate in gates if gate.status == "failed"]
    return AcceptanceReport(
        status="failed" if failed_gates else "passed",
        execution_environment=execution_environment,
        evaluation=AcceptanceEvaluationIdentity(
            path=_portable_path(evaluation_path),
            sha256=file_sha256(evaluation_path),
            artifact_version=evaluation.artifact_version,
            configuration_id=evaluation.configuration_id,
            prompt_version=evaluation.prompt_version,
            evaluation_set_id=evaluation.evaluation_set_id,
            evaluation_set_sha256=evaluation.evaluation_set_sha256,
            baseline_config_sha256=evaluation.baseline_config_sha256,
            retrieval_configuration_id=evaluation.retrieval_configuration_id,
            retrieval_config_sha256=evaluation.retrieval_config_sha256,
            source_pack_id=evaluation.source_pack_id,
            source_pack_manifest_sha256=evaluation.source_pack_manifest_sha256,
        ),
        methodology=AcceptanceMethodology(
            bootstrap_seed=bootstrap_seed,
            bootstrap_resamples=bootstrap_resamples,
            warmup_excluded=evaluation.latency_measurement.warmup_excluded,
        ),
        provider=evaluation.provider,
        hardware=evaluation.hardware,
        runtime=evaluation.runtime,
        conditions=evaluation.conditions,
        configurations=[_configuration_evidence(result) for result in evaluation.configurations],
        paired_differences=paired_differences,
        gates=gates,
        failed_gates=failed_gates,
    )


def write_acceptance_report(report: AcceptanceReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_path, report.model_dump(mode="json"))


def _validate_evaluation(
    evaluation: EvaluationArtifact,
) -> dict[ConfigurationId, ConfigurationResult]:
    configurations: dict[ConfigurationId, ConfigurationResult] = {
        result.id: result for result in evaluation.configurations
    }
    expected_ids = ("llm-only", "plain-rag", "hybrid-retrieval", "full-agent")
    if tuple(result.id for result in evaluation.configurations) != expected_ids:
        raise ValueError(
            "acceptance requires ordered llm-only, plain-rag, hybrid-retrieval, "
            "and full-agent configurations"
        )
    expected_item_ids: list[str] | None = None
    for configuration in evaluation.configurations:
        if configuration.run_count != REQUIRED_RUNS or len(configuration.runs) != REQUIRED_RUNS:
            raise ValueError(
                f"acceptance requires exactly {REQUIRED_RUNS} runs for "
                f"{configuration.id}, found {len(configuration.runs)}"
            )
        seeds = [run.seed for run in configuration.runs]
        if len(seeds) != len(set(seeds)):
            raise ValueError(f"acceptance run seeds must be unique for {configuration.id}")
        for run in configuration.runs:
            item_ids = [item.id for item in run.items]
            if len(item_ids) != REQUIRED_EVALUATION_ITEMS:
                raise ValueError(
                    f"acceptance requires {REQUIRED_EVALUATION_ITEMS} items for "
                    f"{configuration.id} run {run.run}, found {len(item_ids)}"
                )
            if len(item_ids) != len(set(item_ids)):
                raise ValueError(
                    f"acceptance item IDs must be unique in {configuration.id} run {run.run}"
                )
            category_counts = Counter(item.category for item in run.items)
            if category_counts != FROZEN_CATEGORY_COUNTS:
                raise ValueError(
                    f"acceptance frozen category counts differ in {configuration.id} "
                    f"run {run.run}: {dict(sorted(category_counts.items()))}"
                )
            if expected_item_ids is None:
                expected_item_ids = item_ids
            elif item_ids != expected_item_ids:
                raise ValueError(
                    f"acceptance item order differs in {configuration.id} run {run.run}"
                )
    if not evaluation.latency_measurement.warmup_excluded:
        raise ValueError("acceptance latency evidence must exclude provider warm-up")
    return configurations


def _median_run(configuration: ConfigurationResult) -> EvaluationRun:
    ordered = sorted(configuration.runs, key=lambda run: (run.metrics.accuracy, run.run))
    return ordered[len(ordered) // 2]


def _paired_difference(
    full_agent: ConfigurationResult,
    baseline: ConfigurationResult,
    baseline_id: Literal["llm-only", "plain-rag"],
    *,
    seed: int,
    resamples: int,
) -> PairedDifference:
    full_runs = {run.seed: {item.id: item for item in run.items} for run in full_agent.runs}
    baseline_runs = {run.seed: {item.id: item for item in run.items} for run in baseline.runs}
    if tuple(full_runs) != tuple(baseline_runs):
        raise ValueError(f"paired runs for {baseline_id} do not align by seed")

    item_ids = [item.id for item in full_agent.runs[0].items]
    differences = [
        statistics.fmean(
            float(full_runs[run_seed][item_id].answer_passed)
            - float(baseline_runs[run_seed][item_id].answer_passed)
            for run_seed in full_runs
        )
        for item_id in item_ids
    ]
    observed = statistics.fmean(differences)
    random = Random(seed)
    bootstrap_means = [
        statistics.fmean(differences[random.randrange(len(differences))] for _ in differences)
        for _ in range(resamples)
    ]
    return PairedDifference(
        baseline_id=baseline_id,
        item_count=len(differences),
        observed_mean_difference=observed,
        lower_bound=_percentile(bootstrap_means, 0.025),
        upper_bound=_percentile(bootstrap_means, 0.975),
        positive_item_differences=sum(difference > 0 for difference in differences),
        equal_item_differences=sum(difference == 0 for difference in differences),
        item_differences=differences,
    )


def _citation_validity(configuration: ConfigurationResult) -> tuple[float, int]:
    supported = [
        item
        for run in configuration.runs
        for item in run.items
        if item.actual_status == "supported"
    ]
    if not supported:
        return 0.0, 0
    valid = sum(item.citation_valid for item in supported)
    return valid / len(supported), len(supported)


def _abstention(configuration: ConfigurationResult) -> tuple[float, dict[str, float]]:
    abstention_items = [
        item
        for run in configuration.runs
        for item in run.items
        if item.category in ABSTENTION_CATEGORIES
    ]
    counts = Counter(item.category for item in abstention_items)
    passed = Counter(item.category for item in abstention_items if item.answer_passed)
    by_category = {
        category: passed[category] / counts[category] for category in sorted(ABSTENTION_CATEGORIES)
    }
    overall = (
        sum(item.answer_passed for item in abstention_items) / len(abstention_items)
        if abstention_items
        else 0.0
    )
    return overall, by_category


def _configuration_evidence(
    configuration: ConfigurationResult,
) -> AcceptanceConfiguration:
    spread: RunSpread = configuration.spread
    return AcceptanceConfiguration(
        id=configuration.id,
        answer_mode=configuration.answer_mode,
        retrieval_mode=configuration.retrieval_mode,
        run_count=configuration.run_count,
        runs=[
            AcceptanceRun(
                run=run.run,
                seed=run.seed,
                seed_supported=run.seed_supported,
                temperature=run.temperature,
                metrics=run.metrics,
            )
            for run in configuration.runs
        ],
        accuracy=spread.accuracy,
        citation_validity=spread.citation_validity,
        correct_abstention=spread.correct_abstention,
        fabricated_number_count=spread.fabricated_number_count,
        retrieval_recall_at_5=spread.retrieval_recall_at_5,
        retrieval_mrr=spread.retrieval_mrr,
        latency_ms=spread.latency_ms,
    )


def _improvement_gate(
    gate_id: str,
    full_accuracy: float,
    baseline_accuracy: float,
    difference: PairedDifference,
) -> GateResult:
    observed = full_accuracy - baseline_accuracy
    passed = observed >= 0.10 and difference.lower_bound > 0
    return GateResult(
        id=gate_id,
        status="passed" if passed else "failed",
        threshold={"minimum_improvement": 0.10, "confidence_interval_lower_bound": 0.0},
        observed={
            "improvement": observed,
            "confidence_interval": [
                difference.lower_bound,
                difference.upper_bound,
            ],
        },
        diagnosis=(
            f"{difference.baseline_id} improvement {observed:.2%} and paired-bootstrap "
            f"95% interval [{difference.lower_bound:.2%}, {difference.upper_bound:.2%}] "
            f"{'meet' if passed else 'do not meet'} the improvement gates"
        ),
    )


def _remote_llm_latency_gate(
    median_ms: float,
    p95_ms: float,
    *,
    warmup_excluded: bool,
    model_backed: bool,
) -> GateResult:
    passed = warmup_excluded and model_backed and median_ms <= 20_000 and p95_ms <= 30_000
    reasons: list[str] = []
    if not warmup_excluded:
        reasons.append("warm-up was not excluded")
    if not model_backed:
        reasons.append("no model provider was used for the measured answers")
    if median_ms > 20_000:
        reasons.append("median exceeds 20 seconds")
    if p95_ms > 30_000:
        reasons.append("p95 exceeds 30 seconds")
    return GateResult(
        id="remote_llm_latency",
        status="passed" if passed else "failed",
        threshold={"median_ms": 20_000, "p95_ms": 30_000},
        observed={"median_ms": median_ms, "p95_ms": p95_ms},
        diagnosis=(
            "remote LLM latency meets the median and p95 thresholds"
            if passed
            else "; ".join(reasons)
        ),
    )


def _gate(
    gate_id: str,
    passed: bool,
    *,
    threshold: Any,
    observed: Any,
    success: str,
    failure: str,
) -> GateResult:
    return GateResult(
        id=gate_id,
        status="passed" if passed else "failed",
        threshold=threshold,
        observed=observed,
        diagnosis=success if passed else failure,
    )


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("cannot calculate a percentile without values")
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _portable_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)
