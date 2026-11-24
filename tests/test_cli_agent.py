from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from test_cli_specification import (
    download_and_ingest,
    prepare_source_fixture,
    provider_server,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, "-m", "zabm", *args],
        cwd=REPO_ROOT,
        env=env,
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
