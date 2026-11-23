from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, cast

from test_cli_procedure import write_fixture_pdf
from test_cli_specification import run_cli


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def prepare_evaluation_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    pdf_dir = tmp_path / "pdf-doc"
    pdf_dir.mkdir()
    source_path = pdf_dir / "test-manual.pdf"
    write_fixture_pdf(
        source_path,
        [
            "17 Trail Post service",
            "17 Trail Post Standard Remote clamp bolt torque",
            "Remote    Fastener    Tool    Torque",
            "Standard Remote    remote clamp bolt    T25 TORX wrench    2.8-3.4 N*m",
            "50/200 Hour Service Trail Post spring replacement",
            "1 Remove the spring cap.",
            "2 Replace the spring.",
            "NOTICE",
            "Hold the spring under compression.",
            "3 Install the spring cap.",
            "This concludes the Trail Post spring replacement procedure.",
        ],
    )
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    manifest_path = tmp_path / "source-manifest.json"
    _write_json(
        manifest_path,
        {
            "manifest_version": "test-evaluation-1",
            "sources": [
                {
                    "id": "test-manual",
                    "title": "Test Bicycle Manual",
                    "manufacturer": "Test Manufacturer",
                    "url": source_path.as_uri(),
                    "sha256": source_hash,
                    "retrieval_date": "2026-11-23",
                    "revision": "Rev C",
                }
            ],
        },
    )
    specification_evidence = tmp_path / "verified-specifications.json"
    _write_json(
        specification_evidence,
        {
            "specifications": [
                {
                    "id": "test-clamp-torque",
                    "manufacturer": "Test Manufacturer",
                    "model": "Trail Post",
                    "component": "remote clamp bolt",
                    "attribute": "torque",
                    "aliases": ["Trail Post Standard Remote clamp bolt torque"],
                    "value": {
                        "minimum": 2.8,
                        "maximum": 3.4,
                        "unit": "N·m",
                        "display": "2.8-3.4 N·m",
                    },
                    "conditions": [
                        "Remote: Standard Remote",
                        "Fastener: remote clamp bolt",
                        "Tool: T25 TORX wrench",
                        "Service: 50/200 Hour Service",
                    ],
                    "source_id": "test-manual",
                    "citation": {
                        "printed_page": 17,
                        "physical_page": 1,
                        "section": "Trail Post service",
                    },
                    "evidence_excerpts": [
                        "Standard Remote remote clamp bolt T25 TORX wrench 2.8-3.4 N*m",
                        "50/200 Hour Service Trail Post spring replacement",
                    ],
                    "verification": {
                        "status": "human_verified",
                        "verified_by": "repository-maintainer",
                        "verified_at": "2026-11-23",
                    },
                }
            ]
        },
    )
    compatibility_evidence = tmp_path / "verified-compatibility.json"
    _write_json(compatibility_evidence, {"compatibility_rules": []})
    data_dir = tmp_path / "data"
    download = run_cli(
        "download",
        "--manifest",
        str(manifest_path),
        "--pdf-dir",
        str(pdf_dir),
        "--json",
    )
    assert download.returncode == 0, download.stderr
    ingest = run_cli(
        "ingest",
        "--manifest",
        str(manifest_path),
        "--evidence",
        str(specification_evidence),
        "--compatibility-evidence",
        str(compatibility_evidence),
        "--pdf-dir",
        str(pdf_dir),
        "--data-dir",
        str(data_dir),
        "--json",
    )
    assert ingest.returncode == 0, ingest.stderr
    return manifest_path, pdf_dir, data_dir


def write_evaluation_fixture(
    tmp_path: Path,
    *,
    expected_value: dict[str, Any] | None = None,
    extra_qualifier: str | None = None,
    expected_warning: str = "Hold the spring under compression.",
    retrieval_physical_page: int = 1,
) -> Path:
    value = expected_value or {
        "minimum": 2.8,
        "maximum": 3.4,
        "unit": "N·m",
        "display": "2.8-3.4 N·m",
    }
    qualifiers = [
        "Remote: Standard Remote",
        "Fastener: remote clamp bolt",
        "Tool: T25 TORX wrench",
        "Service: 50/200 Hour Service",
    ]
    if extra_qualifier is not None:
        qualifiers.append(extra_qualifier)
    path = tmp_path / "baseline-fixture.json"
    _write_json(
        path,
        {
            "evaluation_set_id": "baseline-fixture-test-v1",
            "source_pack_id": "test-evaluation-1",
            "frozen_at": "2026-11-23",
            "maintainer_review": "ticket-11-test-fixture",
            "items": [
                {
                    "id": "spec-fixture-001",
                    "category": "specification",
                    "question": (
                        "What torque should I use for the Trail Post Standard Remote clamp bolt?"
                    ),
                    "edge_cases": [],
                    "evidence": [
                        {
                            "document_id": "test-manual",
                            "physical_page": retrieval_physical_page,
                            "printed_page": 17,
                            "section": "Trail Post service",
                        }
                    ],
                    "expected": {
                        "response_type": "specification",
                        "status": "supported",
                        "specification": {
                            "value": value,
                            "required_qualifiers": qualifiers,
                        },
                    },
                },
                {
                    "id": "procedure-fixture-001",
                    "category": "procedure",
                    "question": "What are the steps to replace the Trail Post spring?",
                    "edge_cases": [],
                    "evidence": [
                        {
                            "document_id": "test-manual",
                            "physical_page": 1,
                            "printed_page": 17,
                            "section": "Trail Post spring replacement",
                        }
                    ],
                    "expected": {
                        "response_type": "procedure",
                        "status": "supported",
                        "procedure": {
                            "title": "Trail Post spring replacement",
                            "steps": [
                                {
                                    "number": 1,
                                    "text": "Remove the spring cap.",
                                    "warnings": [],
                                },
                                {
                                    "number": 2,
                                    "text": "Replace the spring.",
                                    "warnings": [
                                        {
                                            "severity": "notice",
                                            "text": expected_warning,
                                        }
                                    ],
                                },
                                {
                                    "number": 3,
                                    "text": "Install the spring cap.",
                                    "warnings": [],
                                },
                            ],
                        },
                    },
                },
                {
                    "id": "out-of-scope-fixture-001",
                    "category": "out_of_scope",
                    "question": "Which carbon saddle should I buy for my road bike?",
                    "edge_cases": [],
                    "evidence": [],
                    "expected": {
                        "response_type": "out_of_scope",
                        "status": "out_of_scope",
                        "failure_contains": "only answers bicycle maintenance questions",
                    },
                },
            ],
        },
    )
    return path


def write_baseline_config(tmp_path: Path) -> Path:
    path = tmp_path / "baseline-config.json"
    _write_json(
        path,
        {
            "configuration_id": "baseline-ladder-test-v1",
            "frozen_at": "2026-11-24",
            "maintainer_review": "ticket-11-test-config",
            "prompt_version": "baseline-prompts-test-v1",
            "runs_per_configuration": 3,
            "temperature": 0,
            "seeds": [0, 1, 2],
            "prompt_budget": {"unit": "characters", "value": 12000},
            "retrieval_top_k": 5,
            "configurations": [
                {
                    "id": "llm-only",
                    "answer_mode": "no-evidence",
                    "retrieval_mode": "none",
                },
                {
                    "id": "plain-rag",
                    "answer_mode": "retrieval",
                    "retrieval_mode": "vector",
                },
                {
                    "id": "hybrid-retrieval",
                    "answer_mode": "retrieval",
                    "retrieval_mode": "hybrid",
                },
                {
                    "id": "full-agent",
                    "answer_mode": "full-agent",
                    "retrieval_mode": "hybrid",
                },
            ],
        },
    )
    return path


def run_evaluation(
    *,
    tmp_path: Path,
    manifest_path: Path,
    pdf_dir: Path,
    data_dir: Path,
    evaluation_set_path: Path,
    provider_url: str | None = None,
    debug: bool = False,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], Path]:
    baseline_config_path = write_baseline_config(tmp_path)
    retrieval_config_path = tmp_path / "retrieval-config.json"
    _write_json(
        retrieval_config_path,
        {
            "configuration_id": "test-evaluation-retrieval-v1",
            "top_k": 5,
            "required_recall_at_5": 0.85,
            "minimum_passing_paths": 1,
            "paths": [
                {
                    "id": "page-bm25-title-section",
                    "kind": "bm25",
                    "k1": 1.2,
                    "b": 0.75,
                    "title_boost": 3.0,
                    "section_boost": 3.0,
                }
            ],
        },
    )
    output_path = tmp_path / "evaluation-results.json"
    provider_args = (
        [
            "--provider",
            "openai-compatible",
            "--provider-url",
            provider_url,
            "--model",
            "local-test-model",
            "--embedding-model",
            "local-test-embedding",
            "--provider-configuration",
            "evaluation-test-v1",
        ]
        if provider_url is not None
        else []
    )
    result = run_cli(
        "evaluation",
        "--evaluation-set",
        str(evaluation_set_path),
        "--manifest",
        str(manifest_path),
        "--pdf-dir",
        str(pdf_dir),
        "--data-dir",
        str(data_dir),
        "--retrieval-config",
        str(retrieval_config_path),
        "--config",
        str(baseline_config_path),
        "--output",
        str(output_path),
        *provider_args,
        *(["--debug"] if debug else []),
        "--json",
    )
    report = cast(dict[str, Any], json.loads(result.stdout)) if result.stdout else {}
    return result, report, output_path


@contextmanager
def evaluation_provider_server(
    baseline_generated: dict[str, Any] | None = None,
) -> Generator[tuple[str, list[dict[str, Any]]]]:
    requests: list[dict[str, Any]] = []

    class ProviderHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = cast(dict[str, Any], json.loads(self.rfile.read(length)))
            requests.append({"path": self.path, "body": body})
            messages = cast(list[dict[str, str]], body["messages"])
            system = messages[0]["content"]
            user = json.loads(messages[1]["content"])
            generated: dict[str, Any]
            if "Phrase every supplied validated claim" in system:
                generated = {
                    "sentences": [
                        {"claim_id": claim["claim_id"], "text": claim["text"]}
                        for claim in cast(list[dict[str, str]], user["claims"])
                    ]
                }
            elif baseline_generated is not None:
                generated = baseline_generated
            else:
                generated = {
                    "response_type": "specification",
                    "status": "not_found",
                    "failure_message": "Baseline provider found no supported answer.",
                    "claims": [],
                    "specification": None,
                    "compatibility": None,
                    "procedure": None,
                    "clarification_message": None,
                    "clarification_missing_information": [],
                }
            payload = json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(generated),
                            }
                        }
                    ]
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = cast(tuple[str, int], server.server_address)
    try:
        yield f"http://{host}:{port}/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_evaluation_runs_four_baselines_three_times_and_writes_canonical_results(
    tmp_path: Path,
) -> None:
    manifest_path, pdf_dir, data_dir = prepare_evaluation_fixture(tmp_path)
    evaluation_set_path = write_evaluation_fixture(tmp_path)

    result, report, output_path = run_evaluation(
        tmp_path=tmp_path,
        manifest_path=manifest_path,
        pdf_dir=pdf_dir,
        data_dir=data_dir,
        evaluation_set_path=evaluation_set_path,
    )

    assert result.returncode == 0, result.stderr
    assert report["artifact_version"] == "evaluation-results-v1"
    assert report["evaluation_set_id"] == "baseline-fixture-test-v1"
    assert report["source_pack_id"] == "test-evaluation-1"
    assert report["prompt_version"] == "baseline-prompts-test-v1"
    assert report["provider"] == {
        "provider": "local-deterministic",
        "model": "evidence-renderer-v1",
        "embedding_model": "canonical-alias-index-v1",
        "configuration": "offline-v1",
    }
    assert report["conditions"] == {
        "temperature": 0.0,
        "seeds": [0, 1, 2],
        "prompt_budget": {"unit": "characters", "value": 12000},
        "retrieval_top_k": 5,
    }
    assert report["langsmith_required"] is False
    assert [config["id"] for config in report["configurations"]] == [
        "llm-only",
        "plain-rag",
        "hybrid-retrieval",
        "full-agent",
    ]
    assert json.loads(output_path.read_text(encoding="utf-8")) == report

    for configuration in report["configurations"]:
        assert configuration["run_count"] == 3
        assert [run["seed"] for run in configuration["runs"]] == [0, 1, 2]
        assert all(run["temperature"] == 0.0 for run in configuration["runs"])
        assert all(
            [item["id"] for item in run["items"]]
            == [
                "spec-fixture-001",
                "procedure-fixture-001",
                "out-of-scope-fixture-001",
            ]
            for run in configuration["runs"]
        )
        assert set(configuration["spread"]) == {
            "accuracy",
            "citation_validity",
            "correct_abstention",
            "fabricated_number_count",
            "retrieval_recall_at_5",
            "retrieval_mrr",
            "latency_ms",
        }

    full_agent = report["configurations"][-1]
    first_run = full_agent["runs"][0]
    specification_result = first_run["items"][0]
    procedure_result = first_run["items"][1]
    assert specification_result["answer_passed"] is True
    assert specification_result["citation_valid"] is True
    assert specification_result["unsupported_numbers"] == []
    assert procedure_result["answer_passed"] is True
    assert [
        (check["kind"], check["result"]) for check in procedure_result["procedure_checklist"]
    ] == [
        ("step", "supported"),
        ("step", "supported"),
        ("warning", "supported"),
        ("step", "supported"),
    ]
    assert first_run["metrics"]["retrieval"]["recall_at_5"] == 1.0
    assert first_run["metrics"]["retrieval"]["mrr"] == 1.0

    plain_rag = report["configurations"][1]
    plain_specification = plain_rag["runs"][0]["items"][0]
    assert plain_specification["actual_status"] == "supported"
    assert plain_specification["response"]["specification"] is None
    assert any("has no specification" in issue for issue in plain_specification["grading_issues"])


def test_evaluation_grades_specification_value_qualifiers_and_procedure_checklist(
    tmp_path: Path,
) -> None:
    manifest_path, pdf_dir, data_dir = prepare_evaluation_fixture(tmp_path)
    evaluation_set_path = write_evaluation_fixture(
        tmp_path,
        expected_value={
            "minimum": 4.0,
            "maximum": 5.0,
            "unit": "N·m",
            "display": "4.0-5.0 N·m",
        },
        extra_qualifier="Side: left",
        expected_warning="Do not hold the spring under compression.",
    )

    result, report, output_path = run_evaluation(
        tmp_path=tmp_path,
        manifest_path=manifest_path,
        pdf_dir=pdf_dir,
        data_dir=data_dir,
        evaluation_set_path=evaluation_set_path,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.is_file()
    full_agent = next(config for config in report["configurations"] if config["id"] == "full-agent")
    items = full_agent["runs"][0]["items"]
    specification_result = items[0]
    procedure_result = items[1]
    assert specification_result["answer_passed"] is False
    assert any("value" in issue for issue in specification_result["grading_issues"])
    assert any("qualifier" in issue for issue in specification_result["grading_issues"])
    assert procedure_result["answer_passed"] is False
    warning_check = next(
        check for check in procedure_result["procedure_checklist"] if check["kind"] == "warning"
    )
    assert warning_check["result"] == "incorrect"


def test_evaluation_debug_logs_rag_and_hybrid_combination(
    tmp_path: Path,
) -> None:
    manifest_path, pdf_dir, data_dir = prepare_evaluation_fixture(tmp_path)
    evaluation_set_path = write_evaluation_fixture(tmp_path)

    result, _, _ = run_evaluation(
        tmp_path=tmp_path,
        manifest_path=manifest_path,
        pdf_dir=pdf_dir,
        data_dir=data_dir,
        evaluation_set_path=evaluation_set_path,
        debug=True,
    )

    assert result.returncode == 0, result.stderr
    assert "DEBUG zabm.rag retrieval-skip mode=none" in result.stderr
    assert "DEBUG zabm.rag vector query=" in result.stderr
    assert "DEBUG zabm.rag bm25 path=" in result.stderr
    assert "DEBUG zabm.rag combine strategy=reciprocal-rank-fusion" in result.stderr


def test_evaluation_reports_retrieval_failure_separately_from_answer_generation(
    tmp_path: Path,
) -> None:
    manifest_path, pdf_dir, data_dir = prepare_evaluation_fixture(tmp_path)
    evaluation_set_path = write_evaluation_fixture(
        tmp_path,
        retrieval_physical_page=2,
    )

    result, report, _ = run_evaluation(
        tmp_path=tmp_path,
        manifest_path=manifest_path,
        pdf_dir=pdf_dir,
        data_dir=data_dir,
        evaluation_set_path=evaluation_set_path,
    )

    assert result.returncode == 0, result.stderr
    full_agent = next(config for config in report["configurations"] if config["id"] == "full-agent")
    item = full_agent["runs"][0]["items"][0]
    assert item["answer_passed"] is True
    assert item["retrieval_failed"] is True
    assert item["answer_generation_failed"] is False
    assert item["retrieval"]["recall_at_5"] == 0.0
    assert item["retrieval"]["mrr"] == 0.0


def test_evaluation_uses_one_provider_budget_and_run_seed_for_every_baseline(
    tmp_path: Path,
) -> None:
    manifest_path, pdf_dir, data_dir = prepare_evaluation_fixture(tmp_path)
    evaluation_set_path = write_evaluation_fixture(tmp_path)

    with evaluation_provider_server() as (provider_url, requests):
        result, report, _ = run_evaluation(
            tmp_path=tmp_path,
            manifest_path=manifest_path,
            pdf_dir=pdf_dir,
            data_dir=data_dir,
            evaluation_set_path=evaluation_set_path,
            provider_url=provider_url,
        )

    assert result.returncode == 0, result.stderr
    assert report["provider"] == {
        "provider": "openai-compatible",
        "model": "local-test-model",
        "embedding_model": "local-test-embedding",
        "configuration": "evaluation-test-v1",
    }
    assert report["source_pack_id"] == "test-evaluation-1"
    assert set(report["configurations"][0]["spread"]["latency_ms"]) == {
        "minimum",
        "median",
        "maximum",
    }
    baseline_requests = [
        request
        for request in requests
        if "The baseline has no application evidence gates."
        in request["body"]["messages"][0]["content"]
    ]
    full_agent_requests = [
        request
        for request in requests
        if "Phrase every supplied validated claim" in request["body"]["messages"][0]["content"]
    ]
    assert len(baseline_requests) == 27
    assert len(full_agent_requests) == 6
    assert all(request["body"]["temperature"] == 0 for request in requests)

    llm_only_requests = baseline_requests[:9]
    plain_requests = baseline_requests[9:18]
    hybrid_requests = baseline_requests[18:27]
    assert all(
        json.loads(request["body"]["messages"][1]["content"])["evidence"] == ""
        for request in llm_only_requests
    )
    assert all(
        json.loads(request["body"]["messages"][1]["content"])["evidence"]
        for request in [*plain_requests, *hybrid_requests]
    )
    assert all(
        len(json.loads(request["body"]["messages"][1]["content"])["evidence"]) <= 12000
        for request in baseline_requests
    )
    assert all(
        len(request["body"]["messages"][0]["content"])
        + len(request["body"]["messages"][1]["content"])
        <= 12000
        for request in baseline_requests
    )
    assert [request["body"]["seed"] for request in baseline_requests[:9]] == [
        *([0] * 3),
        *([1] * 3),
        *([2] * 3),
    ]
    assert [request["body"]["seed"] for request in full_agent_requests] == [
        0,
        0,
        1,
        1,
        2,
        2,
    ]
    assert all(run["seed_supported"] is True for run in report["configurations"][0]["runs"])


def test_evaluation_records_numbers_unsupported_by_the_retrieved_evidence(
    tmp_path: Path,
) -> None:
    manifest_path, pdf_dir, data_dir = prepare_evaluation_fixture(tmp_path)
    evaluation_set_path = write_evaluation_fixture(tmp_path)
    generated = {
        "response_type": "specification",
        "status": "supported",
        "claims": [{"text": "The clamp bolt torque is 9 N·m."}],
        "specification": {
            "manufacturer": "Test Manufacturer",
            "model": "Trail Post",
            "component": "remote clamp bolt",
            "attribute": "torque",
            "value": {
                "minimum": 2.8,
                "maximum": 3.4,
                "unit": "N·m",
                "display": "2.8-3.4 N·m",
            },
            "conditions": [
                "Remote: Standard Remote",
                "Fastener: remote clamp bolt",
                "Tool: T25 TORX wrench",
                "Service: 50/200 Hour Service",
            ],
        },
        "compatibility": None,
        "procedure": None,
        "failure_message": None,
        "clarification_message": None,
        "clarification_missing_information": [],
    }

    with evaluation_provider_server(generated) as (provider_url, _):
        result, report, _ = run_evaluation(
            tmp_path=tmp_path,
            manifest_path=manifest_path,
            pdf_dir=pdf_dir,
            data_dir=data_dir,
            evaluation_set_path=evaluation_set_path,
            provider_url=provider_url,
        )

    assert result.returncode == 0, result.stderr
    plain_rag = next(
        configuration
        for configuration in report["configurations"]
        if configuration["id"] == "plain-rag"
    )
    specification_result = plain_rag["runs"][0]["items"][0]
    assert specification_result["answer_passed"] is False
    assert specification_result["unsupported_numbers"] == ["9"]


def test_evaluation_uses_the_explicit_pdf_directory(tmp_path: Path) -> None:
    manifest_path, pdf_dir, data_dir = prepare_evaluation_fixture(tmp_path)
    evaluation_set_path = write_evaluation_fixture(tmp_path)
    separate_pdf_dir = tmp_path / "separate-source-pdfs"
    pdf_dir.rename(separate_pdf_dir)

    result, report, _ = run_evaluation(
        tmp_path=tmp_path,
        manifest_path=manifest_path,
        pdf_dir=separate_pdf_dir,
        data_dir=data_dir,
        evaluation_set_path=evaluation_set_path,
    )

    assert result.returncode == 0, result.stderr
    full_agent = next(
        configuration
        for configuration in report["configurations"]
        if configuration["id"] == "full-agent"
    )
    assert full_agent["runs"][0]["items"][0]["answer_passed"] is True
