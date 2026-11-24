from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[1]

FIXTURE_PDF = base64.b64decode(
    "JVBERi0xLjMKJeLjz9MKMSAwIG9iago8PAovUHJvZHVjZXIgKHB5cGRmKQo+PgplbmRvYmoKMiAwIG9iago8PAovVHlwZSAvUGFnZXMKL0NvdW50IDEKL0tpZHMgWyA0IDAgUiBdCj4+CmVuZG9iagozIDAgb2JqCjw8Ci9UeXBlIC9DYXRhbG9nCi9QYWdlcyAyIDAgUgo+PgplbmRvYmoKNCAwIG9iago8PAovVHlwZSAvUGFnZQovUmVzb3VyY2VzIDw8Ci9Gb250IDw8Ci9GMSA1IDAgUgo+Pgo+PgovTWVkaWFCb3ggWyAwLjAgMC4wIDYxMiA3OTIgXQovUGFyZW50IDIgMCBSCi9Db250ZW50cyA2IDAgUgo+PgplbmRvYmoKNSAwIG9iago8PAovVHlwZSAvRm9udAovU3VidHlwZSAvVHlwZTEKL0Jhc2VGb250IC9IZWx2ZXRpY2EKPj4KZW5kb2JqCjYgMCBvYmoKPDwKL0xlbmd0aCAxNDcKPj4Kc3RyZWFtCkJUIC9GMSAxMCBUZiA3MiA3MjAgVGQgKDE3IFRvcnF1ZSB0YWJsZSkgVGogMCAtMTggVGQgKFN0YW5kYXJkIFJlbW90ZTogdGlnaHRlbiB0aGUgY2xhbXAgYm9sdC4pIFRqIDAgLTE4IFRkIChUMjUgMi44LTMuNCBOKm0gXCgyNS0zMCBpbi1sYlwpKSBUaiBFVAplbmRzdHJlYW0KZW5kb2JqCnhyZWYKMCA3CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDAxNSAwMDAwMCBuIAowMDAwMDAwMDU0IDAwMDAwIG4gCjAwMDAwMDAxMTMgMDAwMDAgbiAKMDAwMDAwMDE2MiAwMDAwMCBuIAowMDAwMDAwMjk0IDAwMDAwIG4gCjAwMDAwMDAzNjQgMDAwMDAgbiAKdHJhaWxlcgo8PAovU2l6ZSA3Ci9Sb290IDMgMCBSCi9JbmZvIDEgMCBSCj4+CnN0YXJ0eHJlZgo1NjIKJSVFT0YK"
)


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


def prepare_source_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    source_path = tmp_path / "manual.pdf"
    source_path.write_bytes(FIXTURE_PDF)
    source_hash = hashlib.sha256(FIXTURE_PDF).hexdigest()

    manifest_path = tmp_path / "source-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": "test-1",
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
            }
        ),
        encoding="utf-8",
    )
    evidence_path = tmp_path / "verified-specifications.json"
    evidence_path.write_text(
        json.dumps(
            {
                "specifications": [
                    {
                        "id": "test-clamp-torque",
                        "manufacturer": "Test Manufacturer",
                        "model": "Trail Post",
                        "component": "remote clamp bolt",
                        "attribute": "torque",
                        "aliases": ["remote clamp fastener torque"],
                        "value": {
                            "minimum": 2.8,
                            "maximum": 3.4,
                            "unit": "N·m",
                            "display": "2.8-3.4 N·m (25-30 in-lb)",
                        },
                        "conditions": [
                            "Remote: Standard Remote",
                            "Fastener: remote clamp bolt",
                            "Tool: T25 TORX wrench",
                        ],
                        "source_id": "test-manual",
                        "citation": {
                            "printed_page": 17,
                            "physical_page": 1,
                            "section": "Torque table",
                        },
                        "evidence_excerpts": [
                            "Standard Remote: tighten the clamp bolt.",
                            "T25 2.8-3.4 N*m (25-30 in-lb)",
                        ],
                        "verification": {
                            "status": "human_verified",
                            "verified_by": "repository-maintainer",
                            "verified_at": "2026-11-23",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return manifest_path, evidence_path, tmp_path / "data"


def update_specification(
    evidence_path: Path,
    *,
    value: dict[str, Any] | None = None,
    specification_updates: dict[str, Any] | None = None,
    citation_updates: dict[str, Any] | None = None,
) -> None:
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    specification = payload["specifications"][0]
    if value is not None:
        specification["value"].update(value)
    if specification_updates:
        specification.update(specification_updates)
    if citation_updates:
        specification["citation"].update(citation_updates)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")


def test_cli_returns_a_verified_specification_with_complete_provenance(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    download_report = _download_and_ingest(manifest_path, evidence_path, data_dir)
    downloaded_source = Path(download_report["sources"][0]["path"])
    assert downloaded_source.parent == tmp_path / "pdf-doc"
    assert downloaded_source.is_file()

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["response_type"] == "specification"
    assert response["provider"] == {
        "provider": "local-deterministic",
        "model": "evidence-renderer-v1",
        "embedding_model": "canonical-alias-index-v1",
        "configuration": "offline-v1",
    }
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
    assert response["citations"] == [
        {
            "document_id": "test-manual",
            "title": "Test Bicycle Manual",
            "manufacturer": "Test Manufacturer",
            "printed_page": 17,
            "physical_page": 1,
            "section": "Torque table",
            "retrieval_date": "2026-11-23",
            "source_manifest_version": "test-1",
        }
    ]


def test_cli_uses_and_records_a_configured_openai_compatible_provider(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    _download_and_ingest(manifest_path, evidence_path, data_dir)
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

    with provider_server(generated) as (provider_url, requests):
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
    assert response["provider"] == {
        "provider": "openai-compatible",
        "model": "local-open-weight-model",
        "embedding_model": "local-embedding-model",
        "configuration": "local-test-v1",
    }
    assert len(requests) == 2
    assert requests[0]["path"] == "/v1/chat/completions"
    assert requests[0]["body"]["model"] == "local-open-weight-model"
    assert requests[0]["body"]["temperature"] == 0


def test_cli_rejects_generated_prose_without_a_validated_claim(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    _download_and_ingest(manifest_path, evidence_path, data_dir)
    generated = {
        "sentences": [
            {
                "claim_id": "test-clamp-torque",
                "text": "Trail Post remote clamp bolt torque is 2.8-3.4 N·m.",
            },
            {
                "claim_id": "invented-claim",
                "text": "Apply thread-locking compound before installation.",
            },
        ]
    }

    with provider_server(generated) as (provider_url, _):
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
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert "every validated claim" in response["failure"]["message"]
    assert response["specification"] is None
    assert response["claims"] == []
    assert response["citations"] == []
    assert response["provider"]["model"] == "local-open-weight-model"


def test_cli_rejects_a_generated_number_absent_from_the_validated_claim(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    _download_and_ingest(manifest_path, evidence_path, data_dir)
    generated = {
        "sentences": [
            {
                "claim_id": "test-clamp-torque",
                "text": "Trail Post remote clamp bolt torque is 9 N·m.",
            }
        ]
    }

    with provider_server(generated) as (provider_url, _):
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
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert "unsupported number" in response["failure"]["message"]
    assert response["specification"] is None
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_rejects_extra_advice_attached_to_a_validated_claim_id(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    _download_and_ingest(manifest_path, evidence_path, data_dir)
    generated = {
        "sentences": [
            {
                "claim_id": "test-clamp-torque",
                "text": (
                    "Trail Post remote clamp bolt torque is 2.8-3.4 N·m. "
                    "Apply grease before installation."
                ),
            }
        ]
    }

    with provider_server(generated) as (provider_url, _):
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
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert "unsupported content" in response["failure"]["message"]
    assert response["specification"] is None
    assert response["claims"] == []
    assert response["citations"] == []


def test_generated_output_cannot_set_response_status_or_citations(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    _download_and_ingest(manifest_path, evidence_path, data_dir)
    generated = {
        "sentences": [
            {
                "claim_id": "test-clamp-torque",
                "text": "Trail Post remote clamp bolt torque is 2.8-3.4 N·m.",
            }
        ],
        "status": "out_of_scope",
        "citations": [],
        "response_type": "out_of_scope",
    }

    with provider_server(generated) as (provider_url, _):
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
            "local-open-weight-model",
            "--embedding-model",
            "local-embedding-model",
            "--provider-configuration",
            "local-test-v1",
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert response["response_type"] == "specification"
    assert response["citations"] == []


def test_cli_asks_for_the_missing_detail_when_an_alias_is_ambiguous(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    first = payload["specifications"][0]
    first["aliases"] = ["Trail Post remote torque"]
    second = copy.deepcopy(first)
    second["id"] = "test-clamp-torque-left"
    second["component"] = "left remote clamp bolt"
    second["conditions"] = [
        "Remote: Standard Remote",
        "Side: left",
        "Fastener: left remote clamp bolt",
    ]
    payload["specifications"].append(second)
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")
    _download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post remote torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "clarification_required"
    assert response["failure"] is None
    assert response["clarification"]["message"] == ("Please identify the exact component and side.")
    assert response["clarification"]["missing_information"] == ["component", "side"]
    assert response["specification"] is None
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_resolves_a_reordered_part_number_alias(tmp_path: Path) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    update_specification(
        evidence_path,
        specification_updates={
            "aliases": ["clamp bolt torque T25 Trail Post Standard Remote"],
        },
    )
    _download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the T25 Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["specification"]["component"] == "remote clamp bolt"
    assert response["claims"][0]["claim_id"] == "test-clamp-torque"


def test_cli_asks_for_a_missing_component_instead_of_treating_it_as_not_found(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    _download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "clarification_required"
    assert response["clarification"] == {
        "message": "Please identify the exact component.",
        "missing_information": ["component"],
    }
    assert response["specification"] is None
    assert response["claims"] == []


def test_cli_renders_a_clarification_request_without_a_traceback(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    _download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post torque?",
        "--data-dir",
        str(data_dir),
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "clarification_required: Please identify the exact component.\n"


def test_cli_refuses_an_adjacent_model_without_substituting_a_specification(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    _download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post V9 Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert response["failure"]["code"] == "not_found"
    assert response["specification"] is None
    assert response["claims"] == []
    assert response["citations"] == []
    assert "Trail Post" not in response["failure"]["message"]


def test_cli_returns_not_found_for_a_specification_outside_the_source_pack(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    _download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post dropper cable torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert response["failure"]["code"] == "not_found"
    assert response["specification"] is None
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_rejects_a_specification_value_not_in_its_evidence_excerpt(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    update_specification(
        evidence_path,
        value={"minimum": 4.0, "maximum": 5.0, "display": "4.0-5.0 N·m"},
    )
    _download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert "numeric value" in response["failure"]["message"]
    assert response["specification"] is None
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_rejects_a_numeric_field_not_in_its_evidence_excerpt(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    update_specification(evidence_path, value={"minimum": 3.2})
    _download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert "numeric value" in response["failure"]["message"]
    assert response["specification"] is None


def test_cli_rejects_a_specification_with_an_invalid_citation(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    update_specification(evidence_path, citation_updates={"section": "Missing section"})
    _download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert "cited section" in response["failure"]["message"]
    assert response["specification"] is None
    assert response["citations"] == []


def test_cli_rejects_a_specification_without_a_unit(tmp_path: Path) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    update_specification(evidence_path, value={"unit": ""})
    _download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert "unit" in response["failure"]["message"]
    assert response["specification"] is None


def test_cli_rejects_a_unit_that_does_not_match_the_evidence_excerpt(
    tmp_path: Path,
) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    update_specification(evidence_path, value={"unit": "mm"})
    _download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert "unit does not match" in response["failure"]["message"]
    assert response["specification"] is None


def test_cli_rejects_a_specification_without_required_conditions(tmp_path: Path) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    update_specification(evidence_path, specification_updates={"conditions": []})
    _download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert "conditions" in response["failure"]["message"]
    assert response["specification"] is None


def test_cli_does_not_answer_from_an_unverified_extraction(tmp_path: Path) -> None:
    manifest_path, evidence_path, data_dir = prepare_source_fixture(tmp_path)
    update_specification(
        evidence_path,
        specification_updates={
            "verification": {
                "status": "machine_extracted",
                "verified_by": "",
                "verified_at": None,
            }
        },
    )
    _download_and_ingest(manifest_path, evidence_path, data_dir)

    result = run_cli(
        "ask",
        "What is the Trail Post Standard Remote clamp bolt torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert "human verification" in response["failure"]["message"]
    assert response["specification"] is None


def _download_and_ingest(
    manifest_path: Path, evidence_path: Path, data_dir: Path
) -> dict[str, Any]:
    pdf_dir = data_dir.parent / "pdf-doc"
    compatibility_evidence_path = evidence_path.with_name("verified-compatibility.json")
    compatibility_evidence_path.write_text(
        json.dumps({"compatibility_rules": []}),
        encoding="utf-8",
    )
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
        str(evidence_path),
        "--compatibility-evidence",
        str(compatibility_evidence_path),
        "--pdf-dir",
        str(pdf_dir),
        "--data-dir",
        str(data_dir),
        "--json",
    )
    assert ingest.returncode == 0, ingest.stderr
    return json.loads(download.stdout)


def download_and_ingest(
    manifest_path: Path,
    evidence_path: Path,
    data_dir: Path,
) -> dict[str, Any]:
    return _download_and_ingest(manifest_path, evidence_path, data_dir)


@contextmanager
def provider_server(
    generated: dict[str, Any] | None = None,
    *,
    route_response: dict[str, Any] | None = None,
    response_body: bytes | None = None,
    embedding_response_body: bytes | None = None,
    embedding_status: int = 200,
) -> Generator[tuple[str, list[dict[str, Any]]]]:
    if generated is None and response_body is None:
        raise ValueError("provider_server requires generated content or a response body")
    requests: list[dict[str, Any]] = []

    class ProviderHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body: dict[str, Any] = json.loads(self.rfile.read(length))
            requests.append(
                {
                    "path": self.path,
                    "body": body,
                    "authorization": self.headers.get("Authorization"),
                }
            )
            status = 200
            if self.path.endswith("/embeddings"):
                status = embedding_status
                payload = (
                    embedding_response_body
                    if embedding_response_body is not None
                    else json.dumps(
                        {
                            "data": [
                                {
                                    "embedding": [0.1, 0.2, 0.3],
                                }
                            ]
                        }
                    ).encode()
                )
            elif response_body is not None:
                payload = response_body
            elif any(
                "request-routing" in message.get("content", "")
                for message in body.get("messages", [])
            ):
                question = json.loads(body["messages"][-1]["content"])["question"]
                effective_route = route_response or fake_route_for_question(question)
                payload = json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": json.dumps(effective_route),
                                }
                            }
                        ]
                    }
                ).encode()
            else:
                assert generated is not None
                content = json.dumps(generated)
                payload = json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": content,
                                }
                            }
                        ]
                    }
                ).encode()
            self.send_response(status)
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


def fake_route_for_question(question: str) -> dict[str, Any]:
    normalized = question.casefold()
    out_of_scope_terms = (
        "buy",
        "capital",
        "choose",
        "commuting",
        "firmware",
        "helmet",
        "photo",
        "sizing",
        "training",
        "upload",
        "web",
        "workout",
    )
    if any(term in normalized for term in out_of_scope_terms):
        intent = "out_of_scope"
    elif any(
        term in normalized
        for term in ("compatible", "compatibility", "paired", "use the", "with the")
    ):
        intent = "compatibility"
    elif any(
        term in normalized
        for term in (
            "how do i ",
            "how to ",
            "procedure",
            "steps",
            "replace the",
            "replace this",
        )
    ):
        intent = "procedure"
    else:
        intent = "specification"
    return {
        "intent": intent,
        "normalized_question": question,
        "entities": [],
        "missing_fields": [],
        "ambiguous_fields": [],
        "candidate_intents": [],
    }
