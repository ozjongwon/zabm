from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from test_cli_specification import run_cli

CATEGORY_COUNTS = {
    "specification": 36,
    "compatibility": 27,
    "procedure": 27,
    "not_found": 15,
    "conflicting_evidence": 8,
    "out_of_scope": 7,
}
ABSTENTION_CATEGORIES = {"not_found", "conflicting_evidence", "out_of_scope"}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def item_categories() -> list[str]:
    return [category for category, count in CATEGORY_COUNTS.items() for _ in range(count)]


def response_for(category: str) -> dict[str, Any]:
    status = {
        "not_found": "not_found",
        "conflicting_evidence": "conflicting_evidence",
        "out_of_scope": "out_of_scope",
    }.get(category, "supported")
    response_type = "out_of_scope" if category == "out_of_scope" else "specification"
    return {
        "request_id": f"request-{category}",
        "timestamp": "2026-11-24T00:00:00Z",
        "response_type": response_type,
        "language": "en",
        "status": status,
        "failure": None,
        "clarification": None,
        "claims": [],
        "specification": None,
        "compatibility": None,
        "procedure": None,
        "conflicts": None,
        "citations": [],
        "provider": {
            "provider": "local-test",
            "model": "test-model",
            "embedding_model": "test-embedding",
            "configuration": "test-v1",
        },
        "routing": None,
        "source_pack_id": "acceptance-test-pack-v1",
    }


def make_run(
    *,
    run: int,
    seed: int,
    passing_count: int,
    latency_ms: float,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for index, category in enumerate(item_categories()):
        status = response_for(category)["status"]
        abstention = category in {"not_found", "conflicting_evidence", "out_of_scope"}
        passed = index < passing_count
        if passing_count >= 30 and abstention:
            passed = True
        elif passing_count >= 30 and category not in {
            "not_found",
            "conflicting_evidence",
            "out_of_scope",
        }:
            passed = index < passing_count - 30
        items.append(
            {
                "id": f"item-{index:03d}",
                "category": category,
                "expected_status": status,
                "actual_status": status,
                "answer_passed": passed,
                "answer_generation_failed": not passed,
                "retrieval_failed": False,
                "grading_issues": [] if passed else ["not accepted"],
                "citation_valid": True,
                "citation_issues": [],
                "unsupported_numbers": [],
                "procedure_checklist": [],
                "prompt_evidence_characters": 100,
                "prompt_budget_characters": 12_000,
                "retrieval": None,
                "response": response_for(category),
                "latency_ms": latency_ms,
            }
        )
    return {
        "run": run,
        "seed": seed,
        "seed_supported": True,
        "temperature": 0.0,
        "items": items,
        "metrics": {
            "accuracy": sum(item["answer_passed"] for item in items) / 120,
            "supported_item_count": 90,
            "citation_validity": 1.0,
            "fabricated_number_count": 0,
            "fabricated_number_rate": 0.0,
            "correct_abstention": 1.0,
            "answer_generation_failures": sum(item["answer_generation_failed"] for item in items),
            "retrieval_failures": 0,
            "retrieval": {"recall_at_5": 0.9, "mrr": 0.8},
            "latency_median_ms": latency_ms,
            "latency_p95_ms": latency_ms,
        },
    }


def make_evaluation_artifact(
    path: Path,
    *,
    full_agent_passing_count: int = 108,
) -> None:
    configurations: list[dict[str, Any]] = []
    for configuration_id, answer_mode, retrieval_mode, passing_count in [
        ("llm-only", "no-evidence", "none", 12),
        ("plain-rag", "retrieval", "vector", 18),
        ("hybrid-retrieval", "retrieval", "hybrid", 24),
        ("full-agent", "full-agent", "hybrid", full_agent_passing_count),
    ]:
        runs = [
            make_run(
                run=index + 1,
                seed=index,
                passing_count=passing_count,
                latency_ms=18_000 + index * 500,
            )
            for index in range(3)
        ]
        configurations.append(
            {
                "id": configuration_id,
                "answer_mode": answer_mode,
                "retrieval_mode": retrieval_mode,
                "run_count": 3,
                "runs": runs,
                "spread": {
                    "accuracy": {
                        "minimum": passing_count / 120,
                        "median": passing_count / 120,
                        "maximum": passing_count / 120,
                    },
                    "citation_validity": {
                        "minimum": 1.0,
                        "median": 1.0,
                        "maximum": 1.0,
                    },
                    "correct_abstention": {
                        "minimum": 1.0,
                        "median": 1.0,
                        "maximum": 1.0,
                    },
                    "fabricated_number_count": {
                        "minimum": 0.0,
                        "median": 0.0,
                        "maximum": 0.0,
                    },
                    "retrieval_recall_at_5": {
                        "minimum": 0.9,
                        "median": 0.9,
                        "maximum": 0.9,
                    },
                    "retrieval_mrr": {
                        "minimum": 0.8,
                        "median": 0.8,
                        "maximum": 0.8,
                    },
                    "latency_ms": {
                        "minimum": 18_000,
                        "median": 18_500,
                        "maximum": 19_000,
                    },
                },
            }
        )

    write_json(
        path,
        {
            "artifact_version": "evaluation-results-v1",
            "configuration_id": "acceptance-test-v1",
            "prompt_version": "acceptance-prompts-v1",
            "evaluation_set_id": "acceptance-set-v1",
            "evaluation_set_sha256": "a" * 64,
            "baseline_config_sha256": "b" * 64,
            "retrieval_configuration_id": "acceptance-retrieval-v1",
            "retrieval_paths": [],
            "retrieval_config_sha256": "c" * 64,
            "source_pack_id": "acceptance-test-pack-v1",
            "source_pack_manifest_sha256": "d" * 64,
            "provider": {
                "provider": "openai-compatible",
                "model": "local-test-model",
                "embedding_model": "local-test-embedding",
                "configuration": "remote-llm-test-v1",
            },
            "routing": {"version": "structured-intent-v1", "strategy": "model"},
            "hardware": {
                "platform": "Linux-test",
                "machine": "x86_64",
                "processor": "test-cpu",
                "python_version": "3.13.5",
                "memory_bytes": 34_359_738_368,
                "gpu": {"name": "NVIDIA GeForce GTX 1060", "memory_mib": 6144},
            },
            "runtime": {
                "application": "zabm",
                "application_version": "0.1.0",
                "python_version": "3.13.5",
                "python_implementation": "CPython",
            },
            "conditions": {
                "temperature": 0.0,
                "seeds": [0, 1, 2],
                "prompt_budget": {"unit": "characters", "value": 12_000},
                "retrieval_top_k": 5,
            },
            "latency_measurement": {
                "unit": "ms",
                "scope": "per-scored-item",
                "warmup_excluded": True,
                "warmup_requests": 2,
            },
            "langsmith_required": False,
            "configurations": configurations,
        },
    )


def test_acceptance_report_scores_every_gate_and_preserves_run_evidence(
    tmp_path: Path,
) -> None:
    evaluation_path = tmp_path / "evaluation-results.json"
    output_path = tmp_path / "acceptance-report.json"
    make_evaluation_artifact(evaluation_path)

    result = run_cli(
        "acceptance",
        "--results",
        str(evaluation_path),
        "--output",
        str(output_path),
        "--execution-environment",
        "remote-llm",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written == report
    assert report["artifact_version"] == "acceptance-report-v1"
    assert report["status"] == "passed"
    assert report["failed_gates"] == []
    assert (
        report["evaluation"]["sha256"] == hashlib.sha256(evaluation_path.read_bytes()).hexdigest()
    )
    assert report["methodology"] == {
        "bootstrap_method": "item-paired-averaged-runs-percentile-v1",
        "bootstrap_seed": 20_261_124,
        "bootstrap_resamples": 10_000,
        "confidence_level": 0.95,
        "latency_scope": "per-scored-item",
        "latency_run_selection": "median-accuracy-run",
        "warmup_excluded": True,
    }
    assert {gate["id"] for gate in report["gates"]} == {
        "full_agent_accuracy",
        "improvement_over_llm_only",
        "improvement_over_plain_rag",
        "citation_validity",
        "correct_abstention",
        "fabricated_numeric_values",
        "remote_llm_latency",
    }
    assert all(gate["status"] == "passed" for gate in report["gates"])
    full_agent_runs = report["configurations"][-1]["runs"]
    assert [run["seed"] for run in full_agent_runs] == [0, 1, 2]
    assert all(run["metrics"]["retrieval"] is not None for run in full_agent_runs)
    assert report["configurations"][-1]["accuracy"]["median"] == 0.9
    assert report["paired_differences"][0]["lower_bound"] > 0
    assert report["paired_differences"][1]["lower_bound"] > 0


def test_acceptance_failure_is_written_without_changing_the_threshold(
    tmp_path: Path,
) -> None:
    evaluation_path = tmp_path / "evaluation-results.json"
    output_path = tmp_path / "acceptance-report.json"
    make_evaluation_artifact(evaluation_path, full_agent_passing_count=101)

    result = run_cli(
        "acceptance",
        "--results",
        str(evaluation_path),
        "--output",
        str(output_path),
        "--execution-environment",
        "remote-llm",
        "--json",
    )

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert output_path.is_file()
    assert report["status"] == "failed"
    assert "full_agent_accuracy" in report["failed_gates"]
    accuracy_gate = next(gate for gate in report["gates"] if gate["id"] == "full_agent_accuracy")
    assert accuracy_gate["threshold"] == 0.9
    assert accuracy_gate["observed"] == statistics.fmean([101 / 120] * 3)


def test_acceptance_requires_each_refusal_category_to_meet_abstention_threshold(
    tmp_path: Path,
) -> None:
    evaluation_path = tmp_path / "evaluation-results.json"
    output_path = tmp_path / "acceptance-report.json"
    make_evaluation_artifact(evaluation_path)
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    full_agent = evaluation["configurations"][-1]
    for run in full_agent["runs"]:
        out_of_scope = next(item for item in run["items"] if item["category"] == "out_of_scope")
        out_of_scope["answer_passed"] = False
        out_of_scope["answer_generation_failed"] = True
    write_json(evaluation_path, evaluation)

    result = run_cli(
        "acceptance",
        "--results",
        str(evaluation_path),
        "--output",
        str(output_path),
        "--execution-environment",
        "remote-llm",
        "--json",
    )

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert "correct_abstention" in report["failed_gates"]
    abstention_gate = next(gate for gate in report["gates"] if gate["id"] == "correct_abstention")
    assert abstention_gate["observed"]["overall"] >= 0.95
    assert abstention_gate["observed"]["by_category"]["out_of_scope"] == 6 / 7


def test_acceptance_rejects_misaligned_items_across_baselines(tmp_path: Path) -> None:
    evaluation_path = tmp_path / "evaluation-results.json"
    make_evaluation_artifact(evaluation_path)
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    for run in evaluation["configurations"][1]["runs"]:
        run["items"][0]["id"] = "misaligned-item"
    write_json(evaluation_path, evaluation)

    result = run_cli(
        "acceptance",
        "--results",
        str(evaluation_path),
        "--output",
        str(tmp_path / "acceptance-report.json"),
        "--execution-environment",
        "remote-llm",
        "--json",
    )

    assert result.returncode == 1
    assert "item order differs" in result.stderr


def test_acceptance_does_not_use_deterministic_output_as_remote_llm_evidence(
    tmp_path: Path,
) -> None:
    evaluation_path = tmp_path / "evaluation-results.json"
    make_evaluation_artifact(evaluation_path)
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    evaluation["provider"] = {
        "provider": "local-deterministic",
        "model": "evidence-renderer-v1",
        "embedding_model": "canonical-alias-index-v1",
        "configuration": "offline-v1",
    }
    write_json(evaluation_path, evaluation)

    result = run_cli(
        "acceptance",
        "--results",
        str(evaluation_path),
        "--output",
        str(tmp_path / "acceptance-report.json"),
        "--execution-environment",
        "remote-llm",
        "--json",
    )

    assert result.returncode == 1
    report = json.loads(result.stdout)
    latency_gate = next(gate for gate in report["gates"] if gate["id"] == "remote_llm_latency")
    assert latency_gate["status"] == "failed"
    assert "no model provider" in latency_gate["diagnosis"]


def test_acceptance_remote_llm_latency_does_not_require_gpu(
    tmp_path: Path,
) -> None:
    evaluation_path = tmp_path / "evaluation-results.json"
    output_path = tmp_path / "acceptance-report.json"
    make_evaluation_artifact(evaluation_path)
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    evaluation["hardware"]["gpu"] = None
    write_json(evaluation_path, evaluation)

    result = run_cli(
        "acceptance",
        "--results",
        str(evaluation_path),
        "--output",
        str(output_path),
        "--execution-environment",
        "remote-llm",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["execution_environment"] == "remote-llm"
    latency_gate = next(gate for gate in report["gates"] if gate["id"] == "remote_llm_latency")
    assert latency_gate["status"] == "passed"


def test_acceptance_rejects_wrong_frozen_category_counts(tmp_path: Path) -> None:
    evaluation_path = tmp_path / "evaluation-results.json"
    make_evaluation_artifact(evaluation_path)
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    for configuration in evaluation["configurations"]:
        for run in configuration["runs"]:
            run["items"][0]["category"] = "procedure"
    write_json(evaluation_path, evaluation)

    result = run_cli(
        "acceptance",
        "--results",
        str(evaluation_path),
        "--output",
        str(tmp_path / "acceptance-report.json"),
        "--execution-environment",
        "remote-llm",
        "--json",
    )

    assert result.returncode == 1
    assert "frozen category counts" in result.stderr


def test_acceptance_applies_latency_thresholds_to_the_median_run(
    tmp_path: Path,
) -> None:
    evaluation_path = tmp_path / "evaluation-results.json"
    make_evaluation_artifact(evaluation_path)
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    full_agent = evaluation["configurations"][-1]
    supported_passes = (66, 78, 84)
    for run, passing_supported in zip(full_agent["runs"], supported_passes, strict=True):
        supported_seen = 0
        for item in run["items"]:
            if item["category"] in ABSTENTION_CATEGORIES:
                passed = True
            else:
                passed = supported_seen < passing_supported
                supported_seen += 1
            item["answer_passed"] = passed
            item["answer_generation_failed"] = not passed
        run["metrics"]["accuracy"] = sum(item["answer_passed"] for item in run["items"]) / len(
            run["items"]
        )
    for run, latency_ms in zip(full_agent["runs"], (31_000, 18_000, 31_000), strict=True):
        for item in run["items"]:
            item["latency_ms"] = latency_ms
        run["metrics"]["latency_median_ms"] = latency_ms
        run["metrics"]["latency_p95_ms"] = latency_ms
    write_json(evaluation_path, evaluation)

    result = run_cli(
        "acceptance",
        "--results",
        str(evaluation_path),
        "--output",
        str(tmp_path / "acceptance-report.json"),
        "--execution-environment",
        "remote-llm",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    latency_gate = next(gate for gate in report["gates"] if gate["id"] == "remote_llm_latency")
    assert latency_gate["status"] == "passed"
    assert latency_gate["observed"] == {"median_ms": 18_000, "p95_ms": 18_000}
