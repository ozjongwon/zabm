from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from test_cli_specification import provider_server

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


def test_out_of_scope_declines_without_calling_the_model_provider(
    tmp_path: Path,
) -> None:
    with provider_server({"sentences": []}) as (provider_url, requests):
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
    assert requests == []
