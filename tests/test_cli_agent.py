from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from test_cli_procedure import (
    complete_procedure_lines,
    prepare_procedure_fixture,
)
from test_cli_procedure import download_and_ingest as download_and_ingest_procedure
from test_cli_specification import (
    download_and_ingest,
    prepare_source_fixture,
    provider_server,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
KOREAN_SAMPLE_SET = REPO_ROOT / "data" / "korean" / "sample-set-v1.json"


def run_cli(
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    effective_env = os.environ.copy()
    effective_env.pop("PYTHONPATH", None)
    if env is not None:
        effective_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "zabm", *args],
        cwd=REPO_ROOT,
        env=effective_env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_cli_declines_an_out_of_scope_request_before_loading_evidence(
    tmp_path: Path,
) -> None:
    result = run_cli(
        "ask",
        "What bicycle should I buy for commuting?",
        "--data-dir",
        str(tmp_path / "missing-data"),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "out_of_scope"
    assert response["response_type"] == "out_of_scope"
    assert response["failure"]["code"] == "out_of_scope"
    assert response["claims"] == []
    assert response["citations"] == []
    assert response["source_pack_id"] == "not-consulted"


def test_cli_renders_an_out_of_scope_refusal_without_a_traceback(
    tmp_path: Path,
) -> None:
    result = run_cli(
        "ask",
        "What bicycle should I buy for commuting?",
        "--data-dir",
        str(tmp_path / "missing-data"),
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("out_of_scope: ")
    assert "bicycle maintenance" in result.stdout
    assert "Traceback" not in result.stderr


def test_cli_returns_the_english_answer_when_korean_output_is_disabled(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--language",
        "ko",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["language"] == "en"
    assert response["localization"] == {
        "requested_language": "ko",
        "active_language": "en",
        "status": "disabled",
        "review_id": None,
        "reason": "Korean output is disabled until its separate review passes.",
    }
    assert response["claims"][0]["text"].startswith("Test Manufacturer Trail Post")
    assert not any("\uac00" <= character <= "\ud7a3" for character in result.stdout)


def _korean_review(
    tmp_path: Path,
    *,
    status: str = "approved",
) -> tuple[Path, dict[str, str]]:
    sample_bytes = KOREAN_SAMPLE_SET.read_bytes()
    review_path = tmp_path / "korean-review.json"
    review_path.write_text(
        json.dumps(
            {
                "artifact_version": "korean-review-v1",
                "review_id": "test-korean-review-v1",
                "language": "ko",
                "sample_set_id": "korean-sample-set-v1",
                "sample_set_sha256": hashlib.sha256(sample_bytes).hexdigest(),
                "status": status,
                "reviewer": "test-reviewer" if status == "approved" else None,
                "reviewed_at": "2026-11-25" if status == "approved" else None,
                "scores": {
                    "correctness": 1.0 if status == "approved" else None,
                    "fluency": 1.0 if status == "approved" else None,
                },
                "checks": {
                    "values_preserved": status == "approved",
                    "units_preserved": status == "approved",
                    "conditions_preserved": status == "approved",
                    "statuses_preserved": status == "approved",
                    "warnings_preserved": status == "approved",
                    "citations_preserved": status == "approved",
                },
            }
        ),
        encoding="utf-8",
    )
    return review_path, {
        "ZABM_KOREAN_OUTPUT": "1",
        "ZABM_KOREAN_SAMPLE_SET": str(KOREAN_SAMPLE_SET),
        "ZABM_KOREAN_REVIEW": str(review_path),
    }


def test_cli_returns_reviewed_korean_prose_with_preserved_canonical_facts(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, data_dir)
    _, environment = _korean_review(tmp_path)
    environment["ZABM_KOREAN_SAMPLE_SET"] = ""
    route: dict[str, Any] = {
        "intent": "specification",
        "normalized_question": "What is the Trail Post Standard Remote clamp bolt torque?",
        "entities": [
            {"kind": "model", "text": "Trail Post"},
            {"kind": "component", "text": "remote clamp bolt"},
            {"kind": "attribute", "text": "torque"},
        ],
        "missing_fields": [],
        "ambiguous_fields": [],
        "candidate_intents": [],
    }
    generated = {
        "sentences": [
            {
                "claim_id": "test-clamp-torque",
                "text": (
                    "Test Manufacturer Trail Post remote clamp bolt torque is "
                    "2.8-3.4 N·m (25-30 in-lb)."
                ),
            }
        ]
    }
    translation: dict[str, Any] = {
        "claims": [
            {
                "claim_id": "test-clamp-torque",
                "text": (
                    "테스트 제조사 트레일 포스트 리모트 클램프 볼트 토크는 "
                    "2.8-3.4 N·m (25-30 in-lb)입니다."
                ),
            }
        ],
        "conditions": [
            "리모트: 스탠다드 리모트",
            "체결구: 리모트 클램프 볼트",
            "공구: T25 TORX 렌치",
        ],
        "procedure": None,
        "clarification_message": None,
        "failure_message": None,
    }

    with provider_server(
        generated,
        route_response=route,
        translation_response=translation,
    ) as (provider_url, requests):
        result = run_cli(
            "ask",
            "트레일 포스트 스탠다드 리모트 클램프 볼트의 토크는 얼마입니까?",
            "--data-dir",
            str(data_dir),
            "--provider-url",
            provider_url,
            "--model",
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--json",
            env=environment,
        )
        first_request_count = len(requests)
        text_result = run_cli(
            "ask",
            "트레일 포스트 스탠다드 리모트 클램프 볼트의 토크는 얼마입니까?",
            "--data-dir",
            str(data_dir),
            "--provider-url",
            provider_url,
            "--model",
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            env=environment,
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["language"] == "ko", response["localization"]
    assert response["localization"] == {
        "requested_language": "ko",
        "active_language": "ko",
        "status": "translated",
        "review_id": "test-korean-review-v1",
        "reason": None,
    }
    assert response["localized"]["claims"] == translation["claims"]
    assert response["localized"]["conditions"] == translation["conditions"]
    assert response["specification"]["value"] == {
        "minimum": 2.8,
        "maximum": 3.4,
        "unit": "N·m",
        "display": "2.8-3.4 N·m (25-30 in-lb)",
    }
    assert response["specification"]["conditions"] == [
        "Remote: Standard Remote",
        "Fastener: remote clamp bolt",
        "Tool: T25 TORX wrench",
    ]
    assert response["citations"][0]["printed_page"] == 17
    assert first_request_count == 3
    assert "korean-translation" in requests[-1]["body"]["messages"][0]["content"]
    assert text_result.returncode == 0, text_result.stderr
    assert "테스트 제조사 트레일 포스트" in text_result.stdout
    assert "조건:" in text_result.stdout
    assert "리모트: 스탠다드 리모트" in text_result.stdout
    assert "출처:" in text_result.stdout
    assert "printed page 17" in text_result.stdout
    assert "Test Manufacturer Trail Post remote clamp bolt torque is" not in text_result.stdout


def test_cli_keeps_korean_output_disabled_until_the_review_is_approved(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, data_dir)
    _, environment = _korean_review(tmp_path, status="pending")

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--language",
        "ko",
        "--json",
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["language"] == "en"
    assert response["localization"] == {
        "requested_language": "ko",
        "active_language": "en",
        "status": "disabled",
        "review_id": None,
        "reason": "Korean output is disabled until its separate review passes.",
    }
    assert response["localized"] is None
    assert response["claims"][0]["text"].startswith("Test Manufacturer Trail Post")


def test_cli_explicit_english_language_overrides_korean_question_detection(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, data_dir)
    _, environment = _korean_review(tmp_path)
    route: dict[str, Any] = {
        "intent": "specification",
        "normalized_question": "What is the Trail Post Standard Remote clamp bolt torque?",
        "entities": [],
        "missing_fields": [],
        "ambiguous_fields": [],
        "candidate_intents": [],
    }
    generated = {
        "sentences": [
            {
                "claim_id": "test-clamp-torque",
                "text": (
                    "Test Manufacturer Trail Post remote clamp bolt torque is "
                    "2.8-3.4 N·m (25-30 in-lb)."
                ),
            }
        ]
    }

    with provider_server(generated, route_response=route) as (provider_url, requests):
        result = run_cli(
            "ask",
            "트레일 포스트 스탠다드 리모트 클램프 볼트의 토크는 얼마입니까?",
            "--data-dir",
            str(data_dir),
            "--provider-url",
            provider_url,
            "--model",
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--language",
            "en",
            "--json",
            env=environment,
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["language"] == "en"
    assert response["localization"] is None
    assert response["localized"] is None
    assert len(requests) == 2


def test_cli_reports_korean_review_coverage_outside_the_v1_acceptance_gate(
    tmp_path: Path,
) -> None:
    review_path, environment = _korean_review(tmp_path)

    result = run_cli(
        "korean-review",
        "--review",
        str(review_path),
        "--json",
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["artifact_version"] == "korean-review-results-v1"
    assert report["sample_set_id"] == "korean-sample-set-v1"
    assert report["review_id"] == "test-korean-review-v1"
    assert report["review_status"] == "approved"
    assert report["enabled"] is True
    assert report["v1_acceptance_gate_affected"] is False
    assert report["scores"] == {"correctness": 1.0, "fluency": 1.0}
    assert report["checks"] == {
        "values_preserved": True,
        "units_preserved": True,
        "conditions_preserved": True,
        "statuses_preserved": True,
        "warnings_preserved": True,
        "citations_preserved": True,
    }
    assert report["coverage"] == {
        "specification": 1,
        "compatibility": 1,
        "procedure": 1,
        "clarification": 1,
        "refusal": 1,
    }
    assert report["case_count"] == 5


def test_cli_rejects_korean_prose_that_changes_a_canonical_value(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, data_dir)
    _, environment = _korean_review(tmp_path)
    generated = {
        "sentences": [
            {
                "claim_id": "test-clamp-torque",
                "text": (
                    "Test Manufacturer Trail Post remote clamp bolt torque is "
                    "2.8-3.4 N·m (25-30 in-lb)."
                ),
            }
        ]
    }
    translation: dict[str, Any] = {
        "claims": [
            {
                "claim_id": "test-clamp-torque",
                "text": "트레일 포스트 클램프 볼트 토크는 9.9 N·m입니다.",
            }
        ],
        "conditions": [
            "리모트: 스탠다드 리모트",
            "체결구: 리모트 클램프 볼트",
            "공구: T25 TORX 렌치",
        ],
        "procedure": None,
        "clarification_message": None,
        "failure_message": None,
    }

    with provider_server(
        generated,
        translation_response=translation,
    ) as (provider_url, _):
        result = run_cli(
            "ask",
            "What is the Trail Post Standard Remote clamp bolt torque?",
            "--data-dir",
            str(data_dir),
            "--provider-url",
            provider_url,
            "--model",
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--language",
            "ko",
            "--json",
            env=environment,
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["language"] == "en"
    assert response["localization"]["status"] == "fallback"
    assert response["localized"] is None
    assert response["claims"][0]["text"].endswith("2.8-3.4 N·m (25-30 in-lb).")
    assert response["citations"][0]["printed_page"] == 17
    assert "9.9" not in response["claims"][0]["text"]


def test_cli_preserves_procedure_warnings_and_citations_in_korean(
    tmp_path: Path,
) -> None:
    manifest_path, specification_path, compatibility_path, data_dir = prepare_procedure_fixture(
        tmp_path, complete_procedure_lines()
    )
    download_and_ingest_procedure(
        manifest_path,
        specification_path,
        compatibility_path,
        data_dir,
    )
    _, environment = _korean_review(tmp_path)
    procedure_id = "test-manual#trail-post-spring-replacement-p1"
    generated = {
        "sentences": [
            {
                "claim_id": f"{procedure_id}#step-1",
                "text": "Step 1: Remove the spring cap.",
            },
            {
                "claim_id": f"{procedure_id}#step-1-warning-1",
                "text": "Notice: Hold the spring under compression.",
            },
            {
                "claim_id": f"{procedure_id}#step-2",
                "text": "Step 2: Replace the spring.",
            },
            {
                "claim_id": f"{procedure_id}#step-3",
                "text": "Step 3: Install the spring cap.",
            },
        ]
    }
    translation: dict[str, Any] = {
        "claims": [
            {
                "claim_id": f"{procedure_id}#step-1",
                "text": "1단계: 스프링 캡을 제거합니다.",
            },
            {
                "claim_id": f"{procedure_id}#step-1-warning-1",
                "text": "알림: 스프링을 압축한 상태로 유지하십시오.",
            },
            {
                "claim_id": f"{procedure_id}#step-2",
                "text": "2단계: 스프링을 교체합니다.",
            },
            {
                "claim_id": f"{procedure_id}#step-3",
                "text": "3단계: 스프링 캡을 설치합니다.",
            },
        ],
        "conditions": [],
        "procedure": {
            "title": "트레일 포스트 스프링 교체",
            "steps": [
                {
                    "number": 1,
                    "text": "스프링 캡을 제거합니다.",
                    "warnings": [
                        {
                            "severity": "notice",
                            "text": "스프링을 압축한 상태로 유지하십시오.",
                        }
                    ],
                },
                {
                    "number": 2,
                    "text": "스프링을 교체합니다.",
                    "warnings": [],
                },
                {
                    "number": 3,
                    "text": "스프링 캡을 설치합니다.",
                    "warnings": [],
                },
            ],
        },
        "clarification_message": None,
        "failure_message": None,
    }

    with provider_server(
        generated,
        translation_response=translation,
    ) as (provider_url, _):
        result = run_cli(
            "ask",
            "What are the steps to replace the Trail Post spring?",
            "--data-dir",
            str(data_dir),
            "--provider-url",
            provider_url,
            "--model",
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--language",
            "ko",
            "--json",
            env=environment,
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["language"] == "ko", response["localization"]
    assert response["status"] == "supported"
    assert response["procedure"]["steps"][0]["warnings"] == [
        {
            "severity": "notice",
            "text": "Hold the spring under compression.",
        }
    ]
    assert response["localized"]["procedure"]["steps"][0]["warnings"] == [
        {
            "severity": "notice",
            "text": "스프링을 압축한 상태로 유지하십시오.",
        }
    ]
    assert response["procedure"]["steps"][0]["citation"]["printed_page"] == 17
    assert (
        response["localized"]["procedure"]["steps"][0]["warnings"][0]["severity"]
        == response["procedure"]["steps"][0]["warnings"][0]["severity"]
    )


def test_cli_translates_a_clarification_without_changing_its_status(
    tmp_path: Path,
) -> None:
    _, environment = _korean_review(tmp_path)
    route = {
        "intent": "ambiguous",
        "normalized_question": "Trail Post",
        "entities": [{"kind": "model", "text": "Trail Post"}],
        "missing_fields": ["task"],
        "ambiguous_fields": ["question_family"],
        "candidate_intents": ["specification", "procedure"],
    }
    translation: dict[str, Any] = {
        "claims": [],
        "conditions": [],
        "procedure": None,
        "clarification_message": (
            "사양, 호환성 결과 또는 절차 중 무엇이 필요한지 명확히 알려 주십시오."
        ),
        "failure_message": None,
    }

    with provider_server(
        {},
        route_response=route,
        translation_response=translation,
    ) as (provider_url, _):
        result = run_cli(
            "ask",
            "트레일 포스트",
            "--data-dir",
            str(tmp_path / "missing-data"),
            "--provider-url",
            provider_url,
            "--model",
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--language",
            "ko",
            "--json",
            env=environment,
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "clarification_required"
    assert response["response_type"] == "ambiguous"
    assert response["language"] == "ko"
    assert response["clarification"]["message"].startswith("Please clarify")
    assert response["localized"]["clarification_message"] == (translation["clarification_message"])


def test_cli_declines_unrelated_general_knowledge_as_out_of_scope(
    tmp_path: Path,
) -> None:
    result = run_cli(
        "ask",
        "What is the capital of France?",
        "--data-dir",
        str(tmp_path / "missing-data"),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "out_of_scope"
    assert response["failure"]["code"] == "out_of_scope"
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_declines_photo_identification_as_out_of_scope(
    tmp_path: Path,
) -> None:
    result = run_cli(
        "ask",
        "Upload this photo and identify the part on my bike.",
        "--data-dir",
        str(tmp_path / "missing-data"),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "out_of_scope"
    assert response["response_type"] == "out_of_scope"


def test_out_of_scope_declines_before_evidence_or_answer_generation(
    tmp_path: Path,
) -> None:
    route = {
        "intent": "out_of_scope",
        "normalized_question": "Which bicycle should I buy for commuting?",
        "entities": [{"kind": "other", "text": "buying advice"}],
        "missing_fields": [],
        "ambiguous_fields": [],
        "candidate_intents": [],
    }
    with provider_server({"sentences": []}, route_response=route) as (provider_url, requests):
        result = run_cli(
            "ask",
            "Which bicycle should I buy for commuting?",
            "--data-dir",
            str(tmp_path / "missing-data"),
            "--provider",
            "openai-compatible",
            "--provider-url",
            provider_url,
            "--model",
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "out_of_scope"
    assert response["provider"] == {
        "provider": "openai-compatible",
        "model": "local-open-weight-model",
        "embedding_model": "local-embedding-model",
        "configuration": "local-test-v1",
    }
    assert response["routing"]["intent"] == "out_of_scope"
    assert response["claims"] == []
    assert len(requests) == 1
    assert any(
        "request-routing" in message["content"] for message in requests[0]["body"]["messages"]
    )


def test_cli_routes_a_non_english_request_through_a_semantic_route(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, data_dir)
    route = {
        "intent": "specification",
        "normalized_question": "What is the Trail Post Standard Remote clamp bolt torque?",
        "entities": [
            {"kind": "model", "text": "Trail Post"},
            {"kind": "component", "text": "remote clamp bolt"},
            {"kind": "attribute", "text": "torque"},
        ],
        "missing_fields": [],
        "ambiguous_fields": [],
        "candidate_intents": [],
    }
    generated = {
        "sentences": [
            {
                "claim_id": "test-clamp-torque",
                "text": (
                    "Test Manufacturer Trail Post remote clamp bolt torque is "
                    "2.8-3.4 N·m (25-30 in-lb)."
                ),
            }
        ]
    }

    with provider_server(generated, route_response=route) as (provider_url, requests):
        result = run_cli(
            "ask",
            "Welches Drehmoment gilt für die Klemmschraube am Trail Post?",
            "--data-dir",
            str(data_dir),
            "--provider",
            "openai-compatible",
            "--provider-url",
            provider_url,
            "--model",
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["response_type"] == "specification"
    assert response["routing"] == {
        "routing_version": "structured-intent-v1",
        "strategy": "model",
        "intent": "specification",
        "normalized_question": "What is the Trail Post Standard Remote clamp bolt torque?",
        "entities": route["entities"],
        "missing_fields": [],
        "ambiguous_fields": [],
        "candidate_intents": [],
    }
    assert len(requests) == 2
    assert any(
        "request-routing" in message["content"] for message in requests[0]["body"]["messages"]
    )
    assert not any(
        "request-routing" in message["content"] for message in requests[1]["body"]["messages"]
    )


def test_cli_falls_back_to_prototype_routing_when_a_model_route_finds_no_evidence(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, data_dir)
    route: dict[str, object] = {
        "intent": "procedure",
        "normalized_question": "Service the component.",
        "entities": [],
        "missing_fields": [],
        "ambiguous_fields": [],
        "candidate_intents": [],
    }
    generated = {
        "sentences": [
            {
                "claim_id": "test-clamp-torque",
                "text": (
                    "Test Manufacturer Trail Post remote clamp bolt torque is "
                    "2.8-3.4 N·m (25-30 in-lb)."
                ),
            }
        ]
    }

    with provider_server(generated, route_response=route) as (provider_url, requests):
        result = run_cli(
            "ask",
            "What torque should I use for the Trail Post Standard Remote clamp bolt?",
            "--data-dir",
            str(data_dir),
            "--provider",
            "openai-compatible",
            "--provider-url",
            provider_url,
            "--model",
            "weak-routing-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["routing"]["strategy"] == "prototype"
    assert response["routing"]["intent"] == "specification"
    assert response["provider"]["model"] == "weak-routing-model"
    assert len(requests) == 2
    assert (
        "What torque should I use for the Trail Post"
        in requests[1]["body"]["messages"][-1]["content"]
    )


def test_cli_reports_the_model_response_when_claim_phrasing_is_invalid(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, data_dir)
    route: dict[str, object] = {
        "intent": "specification",
        "normalized_question": "What is the Trail Post Standard Remote clamp bolt torque?",
        "entities": [],
        "missing_fields": [],
        "ambiguous_fields": [],
        "candidate_intents": [],
    }
    model_response = "The torque is 2.8-3.4 N·m, but this is not JSON."

    with provider_server(
        {"sentences": []},
        route_response=route,
        generated_response_body=json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": model_response,
                        }
                    }
                ]
            }
        ).encode(),
    ) as (provider_url, _):
        result = run_cli(
            "ask",
            "What is the Trail Post Standard Remote clamp bolt torque?",
            "--data-dir",
            str(data_dir),
            "--provider",
            "openai-compatible",
            "--provider-url",
            provider_url,
            "--model",
            "weak-phrasing-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert response["failure"]["message"] == (
        "Generated answer was rejected because the model response was not valid "
        f"claim-linked JSON. Response: {model_response}"
    )


def test_cli_requests_clarification_when_the_request_family_is_ambiguous(
    tmp_path: Path,
) -> None:
    route = {
        "intent": "ambiguous",
        "normalized_question": "Trail Post",
        "entities": [{"kind": "model", "text": "Trail Post"}],
        "missing_fields": ["task"],
        "ambiguous_fields": ["question_family"],
        "candidate_intents": ["specification", "procedure"],
    }

    with provider_server({"sentences": []}, route_response=route) as (provider_url, requests):
        result = run_cli(
            "ask",
            "Trail Post",
            "--data-dir",
            str(tmp_path / "missing-data"),
            "--provider",
            "openai-compatible",
            "--provider-url",
            provider_url,
            "--model",
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "clarification_required"
    assert response["response_type"] == "ambiguous"
    assert response["claims"] == []
    assert response["citations"] == []
    assert response["clarification"] == {
        "message": (
            "Please clarify whether you need a specification, compatibility result, or procedure."
        ),
        "missing_information": ["question family", "task"],
    }
    assert response["routing"]["intent"] == "ambiguous"
    assert response["routing"]["candidate_intents"] == ["specification", "procedure"]
    assert len(requests) == 1


def test_router_output_cannot_set_status_or_citations(tmp_path: Path) -> None:
    route = {
        "intent": "specification",
        "normalized_question": "What is the Trail Post clamp bolt torque?",
        "entities": [],
        "missing_fields": [],
        "ambiguous_fields": [],
        "candidate_intents": [],
        "status": "supported",
        "citations": ["fabricated"],
    }

    with provider_server(
        {"sentences": []},
        route_response=route,
    ) as (provider_url, _):
        result = run_cli(
            "ask",
            "What is the Trail Post clamp bolt torque?",
            "--data-dir",
            str(tmp_path / "missing-data"),
            "--provider",
            "openai-compatible",
            "--provider-url",
            provider_url,
            "--model",
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--json",
        )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "provider returned an invalid request-routing result" in result.stderr
