from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest
from test_cli_evaluation import (
    prepare_evaluation_fixture,
    write_evaluation_fixture,
)
from test_cli_evaluation import (
    run_evaluation as run_evaluation_command,
)
from test_cli_specification import (
    download_and_ingest,
    prepare_source_fixture,
    provider_server,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli_with_env(
    env_updates: dict[str, str | None],
    *args: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    for key, value in env_updates.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, "-m", "zabm", *args],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def generated_specification() -> dict[str, object]:
    return {
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


def unused_local_provider_url() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = cast(tuple[str, int], listener.getsockname())[1]
    return f"http://127.0.0.1:{port}/v1"


def test_cli_selects_environment_configured_remote_provider_without_leaking_secret(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, data_dir)
    api_key = "environment-only-remote-secret"

    with provider_server(generated_specification()) as (provider_url, requests):
        result = run_cli_with_env(
            {
                "ZABM_PROVIDER": "openai-compatible",
                "ZABM_PROVIDER_URL": provider_url,
                "ZABM_MODEL": "remote-test-model",
                "ZABM_EMBEDDING_MODEL": "remote-test-embedding",
                "ZABM_PROVIDER_CONFIGURATION": "remote-environment-v1",
                "ZABM_PROVIDER_API_KEY": api_key,
                "ZABM_DEBUG": "1",
            },
            "ask",
            "What is the Trail Post Standard Remote clamp bolt torque?",
            "--data-dir",
            str(data_dir),
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["provider"] == {
        "provider": "openai-compatible",
        "model": "remote-test-model",
        "embedding_model": "remote-test-embedding",
        "configuration": "remote-environment-v1",
    }
    assert response["source_pack_id"] == "test-1"
    assert requests[0]["authorization"] == f"Bearer {api_key}"
    assert api_key not in result.stdout
    assert api_key not in result.stderr


def test_cli_reports_remote_provider_unavailability_without_a_substantive_answer(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, data_dir)
    api_key = "unavailable-provider-secret"

    result = run_cli_with_env(
        {"ZABM_PROVIDER_API_KEY": api_key},
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--provider",
        "openai-compatible",
        "--provider-url",
        unused_local_provider_url(),
        "--model",
        "remote-test-model",
        "--embedding-model",
        "remote-test-embedding",
        "--provider-configuration",
        "remote-unavailable-v1",
        "--json",
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "zabm ask: provider request failed:" in result.stderr
    assert api_key not in result.stderr


def test_evaluation_reports_remote_provider_unavailability_as_an_operational_failure(
    tmp_path: Path,
) -> None:
    manifest_path, pdf_dir, data_dir = prepare_evaluation_fixture(tmp_path)
    evaluation_set_path = write_evaluation_fixture(tmp_path)

    result, report, output_path = run_evaluation_command(
        tmp_path=tmp_path,
        manifest_path=manifest_path,
        pdf_dir=pdf_dir,
        data_dir=data_dir,
        evaluation_set_path=evaluation_set_path,
        provider_url=unused_local_provider_url(),
    )

    assert result.returncode == 1
    assert report == {}
    assert not output_path.exists()
    assert "zabm evaluation: provider request failed:" in result.stderr


def test_cli_fails_closed_on_a_malformed_remote_provider_response(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, data_dir)

    with provider_server(
        response_body=b'{"choices": []}',
    ) as (provider_url, _):
        result = run_cli_with_env(
            {"ZABM_PROVIDER_API_KEY": None},
            "ask",
            "What is the Trail Post Standard Remote clamp bolt torque?",
            "--data-dir",
            str(data_dir),
            "--provider",
            "openai-compatible",
            "--provider-url",
            provider_url,
            "--model",
            "remote-test-model",
            "--embedding-model",
            "remote-test-embedding",
            "--provider-configuration",
            "remote-malformed-v1",
            "--json",
        )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "zabm ask: provider returned an invalid chat completion" in result.stderr


def test_cli_uses_the_deepseek_provider_profile(tmp_path: Path) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, data_dir)

    with provider_server(generated_specification()) as (provider_url, requests):
        result = run_cli_with_env(
            {
                "ZABM_PROVIDER_API_KEY": None,
                "DEEPSEEK_API_KEY": "deepseek-test-key",
                "DEEPSEEK_MODEL": None,
                "ZABM_MODEL": None,
                "ZABM_EMBEDDING_MODEL": None,
            },
            "ask",
            "What is the Trail Post Standard Remote clamp bolt torque?",
            "--data-dir",
            str(data_dir),
            "--provider",
            "deepseek",
            "--provider-url",
            provider_url,
            "--debug",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["provider"] == {
        "provider": "deepseek",
        "model": "deepseek-flash",
        "embedding_model": "not-configured",
        "configuration": "deepseek:temperature=0",
    }
    assert requests[0]["authorization"] == "Bearer deepseek-test-key"
    assert requests[0]["body"]["model"] == "deepseek-flash"
    assert "seed" not in requests[0]["body"]
    assert "DEBUG zabm.agent route" in result.stderr
    assert "DEBUG zabm.llm request provider=deepseek model=deepseek-flash" in result.stderr
    assert "DEBUG zabm.llm response provider=deepseek model=deepseek-flash" in result.stderr


def test_provider_smoke_exercises_chat_and_embedding_contracts() -> None:
    api_key = "provider-smoke-secret"

    with provider_server(generated_specification()) as (provider_url, requests):
        result = run_cli_with_env(
            {"ZABM_PROVIDER_API_KEY": api_key},
            "provider-smoke",
            "--provider",
            "openai-compatible",
            "--provider-url",
            provider_url,
            "--model",
            "remote-smoke-model",
            "--embedding-model",
            "remote-smoke-embedding",
            "--provider-configuration",
            "remote-smoke-v1",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["provider"] == {
        "provider": "openai-compatible",
        "model": "remote-smoke-model",
        "embedding_model": "remote-smoke-embedding",
        "configuration": "remote-smoke-v1",
    }
    assert report["chat"]["response_characters"] > 0
    assert {key: value for key, value in report["embeddings"].items() if key != "latency_ms"} == {
        "input_count": 1,
        "vector_count": 1,
        "dimensions": 3,
    }
    assert report["embeddings"]["latency_ms"] >= 0
    assert [request["path"] for request in requests] == [
        "/v1/chat/completions",
        "/v1/embeddings",
    ]
    assert all(request["authorization"] == f"Bearer {api_key}" for request in requests)
    assert api_key not in result.stdout
    assert api_key not in result.stderr


def test_provider_smoke_can_skip_embeddings_for_chat_only_profiles() -> None:
    with provider_server(generated_specification()) as (provider_url, requests):
        result = run_cli_with_env(
            {"DEEPSEEK_API_KEY": "deepseek-test-key"},
            "provider-smoke",
            "--provider",
            "deepseek",
            "--provider-url",
            provider_url,
            "--model",
            "deepseek-test-model",
            "--embedding-model",
            "not-configured",
            "--skip-embeddings",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["embeddings"] == {"status": "skipped"}
    assert [request["path"] for request in requests] == ["/v1/chat/completions"]


def test_provider_smoke_supports_remote_chat_with_local_embeddings() -> None:
    with (
        provider_server(generated_specification()) as (chat_url, chat_requests),
        provider_server(generated_specification()) as (embedding_url, embedding_requests),
    ):
        result = run_cli_with_env(
            {
                "DEEPSEEK_API_KEY": "deepseek-test-key",
                "ZABM_EMBEDDING_PROVIDER_URL": embedding_url,
            },
            "provider-smoke",
            "--provider",
            "deepseek",
            "--provider-url",
            chat_url,
            "--model",
            "deepseek-test-model",
            "--embedding-model",
            "mxbai-embed-large:latest",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["provider"]["model"] == "deepseek-test-model"
    assert report["provider"]["embedding_model"] == "mxbai-embed-large:latest"
    assert [request["path"] for request in chat_requests] == ["/v1/chat/completions"]
    assert chat_requests[0]["authorization"] == "Bearer deepseek-test-key"
    assert [request["path"] for request in embedding_requests] == ["/v1/embeddings"]
    assert embedding_requests[0]["authorization"] is None


def test_cpu_quantized_provider_smoke_writes_acceptance_evidence(tmp_path: Path) -> None:
    output_path = tmp_path / "cpu-smoke.json"

    with provider_server(generated_specification()) as (provider_url, _):
        result = run_cli_with_env(
            {},
            "provider-smoke",
            "--provider",
            "openai-compatible",
            "--provider-url",
            provider_url,
            "--model",
            "local-cpu-model",
            "--embedding-model",
            "local-cpu-embedding",
            "--provider-configuration",
            "cpu-quantized-test-v1",
            "--cpu-quantized",
            "--output",
            str(output_path),
            "--json",
        )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert output_path.is_file()
    assert json.loads(output_path.read_text(encoding="utf-8")) == report
    assert report["artifact_version"] == "cpu-smoke-v1"
    assert report["status"] == "passed"
    assert report["provider"]["model"] == "local-cpu-model"
    assert report["hardware"]["machine"] == platform.machine()
    assert report["hardware"]["gpu"] is None
    assert report["runtime"]["application"] == "zabm"
    assert report["latency_ms"] == pytest.approx(
        report["chat"]["latency_ms"] + report["embeddings"]["latency_ms"],
        abs=0.002,
    )


def test_provider_smoke_rejects_an_embedding_count_mismatch() -> None:
    with provider_server(
        generated_specification(),
        embedding_response_body=json.dumps(
            {
                "data": [
                    {"embedding": [0.1, 0.2, 0.3]},
                    {"embedding": [0.4, 0.5, 0.6]},
                ]
            }
        ).encode(),
    ) as (provider_url, _):
        result = run_cli_with_env(
            {"ZABM_PROVIDER_API_KEY": None},
            "provider-smoke",
            "--provider",
            "openai-compatible",
            "--provider-url",
            provider_url,
            "--model",
            "remote-smoke-model",
            "--embedding-model",
            "remote-smoke-embedding",
            "--provider-configuration",
            "remote-smoke-v1",
            "--json",
        )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "provider returned 2 embeddings for 1 input" in result.stderr


def test_cli_uses_the_openai_provider_profile(tmp_path: Path) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_and_ingest(manifest_path, evidence_path, data_dir)

    with provider_server(generated_specification()) as (provider_url, requests):
        result = run_cli_with_env(
            {
                "ZABM_PROVIDER_API_KEY": None,
                "OPENAI_API_KEY": "openai-test-key",
                "OPENAI_MODEL": None,
                "ZABM_MODEL": None,
                "ZABM_EMBEDDING_MODEL": None,
            },
            "ask",
            "What is the Trail Post Standard Remote clamp bolt torque?",
            "--data-dir",
            str(data_dir),
            "--provider",
            "openai",
            "--provider-url",
            provider_url,
            "--model",
            "gpt-test-model",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["provider"] == {
        "provider": "openai",
        "model": "gpt-test-model",
        "embedding_model": "text-embedding-3-small",
        "configuration": "openai:temperature=0,seed=0",
    }
    assert requests[0]["authorization"] == "Bearer openai-test-key"
    assert requests[0]["body"]["seed"] == 0


def test_cli_requires_the_named_provider_api_key(tmp_path: Path) -> None:
    result = run_cli_with_env(
        {
            "ZABM_PROVIDER_API_KEY": None,
            "DEEPSEEK_API_KEY": None,
        },
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(tmp_path / "missing-data"),
        "--provider",
        "deepseek",
        "--provider-url",
        "http://127.0.0.1:1/v1",
        "--json",
    )

    assert result.returncode == 1
    assert "DEEPSEEK_API_KEY is required" in result.stderr
