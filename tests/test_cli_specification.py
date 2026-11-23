from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

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
        "--pdf-dir",
        str(pdf_dir),
        "--data-dir",
        str(data_dir),
        "--json",
    )
    assert ingest.returncode == 0, ingest.stderr
    return json.loads(download.stdout)
