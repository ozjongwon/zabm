from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from pypdf import PdfReader
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


def write_fixture_pdf(path: Path, lines: list[str]) -> None:
    commands = [f"({_pdf_escape(line)}) Tj 0 -18 Td" for line in lines]
    stream = f"BT /F1 10 Tf 72 720 Td {' '.join(commands)} ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        (
            b"<< /Type /Page /Parent 2 0 R "
            b"/Resources << /Font << /F1 4 0 R >> >> "
            b"/MediaBox [0 0 612 792] /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    ]

    document = bytearray(b"%PDF-1.3\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(document))
        document.extend(f"{number} 0 obj\n".encode())
        document.extend(body)
        document.extend(b"\nendobj\n")

    xref_offset = len(document)
    document.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    path.write_bytes(document)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def prepare_procedure_fixture(
    tmp_path: Path,
    lines: list[str],
    *,
    pdf_writer: Callable[[Path, list[str]], None] = write_fixture_pdf,
) -> tuple[Path, Path, Path, Path]:
    source_path = tmp_path / "manual.pdf"
    pdf_writer(source_path, lines)
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()

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
    specification_evidence_path = tmp_path / "verified-specifications.json"
    specification_evidence_path.write_text(
        json.dumps({"specifications": []}),
        encoding="utf-8",
    )
    compatibility_evidence_path = tmp_path / "verified-compatibility.json"
    compatibility_evidence_path.write_text(
        json.dumps({"compatibility_rules": []}),
        encoding="utf-8",
    )
    return (
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        tmp_path / "data",
    )


def download_and_ingest(
    manifest_path: Path,
    specification_evidence_path: Path,
    compatibility_evidence_path: Path,
    data_dir: Path,
) -> None:
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
        str(specification_evidence_path),
        "--compatibility-evidence",
        str(compatibility_evidence_path),
        "--pdf-dir",
        str(pdf_dir),
        "--data-dir",
        str(data_dir),
        "--json",
    )
    assert ingest.returncode == 0, ingest.stderr


def complete_procedure_lines() -> list[str]:
    return [
        "17 Trail Post spring replacement",
        "Part    Tool    Torque",
        "Spring compressor    4 mm hex    5 N·m",
        "1 Remove the spring cap.",
        "NOTICE",
        "Hold the spring under compression.",
        "2 Replace the spring.",
        "3 Install the spring cap.",
        "This concludes the Trail Post spring replacement procedure.",
    ]


def test_cli_returns_every_ordered_step_and_warning_with_citations(tmp_path: Path) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, complete_procedure_lines())
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "What are the steps to replace the Trail Post spring?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["response_type"] == "procedure"
    assert response["procedure"]["title"] == "Trail Post spring replacement"
    assert [step["number"] for step in response["procedure"]["steps"]] == [1, 2, 3]
    assert [step["text"] for step in response["procedure"]["steps"]] == [
        "Remove the spring cap.",
        "Replace the spring.",
        "Install the spring cap.",
    ]
    assert response["procedure"]["steps"][0]["warnings"] == [
        {
            "severity": "notice",
            "text": "Hold the spring under compression.",
        }
    ]
    for step in response["procedure"]["steps"]:
        assert step["citation"] == {
            "document_id": "test-manual",
            "title": "Test Bicycle Manual",
            "manufacturer": "Test Manufacturer",
            "printed_page": 17,
            "physical_page": 1,
            "section": "Trail Post spring replacement",
            "retrieval_date": "2026-11-23",
            "source_manifest_version": "test-1",
        }
        reader = PdfReader(data_dir.parent / "pdf-doc" / "test-manual.pdf")
        source_page = cast(Any, reader.pages[step["citation"]["physical_page"] - 1])
        extracted_text: str = source_page.extract_text() or ""
        source_text = " ".join(extracted_text.split())
        assert " ".join(step["text"].split()) in source_text


def test_cli_uses_the_local_provider_for_complete_procedure_phrasing(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, complete_procedure_lines())
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )
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

    with provider_server(generated) as (provider_url, requests):
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
            "--json",
        )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["procedure"]["title"] == "Trail Post spring replacement"
    assert [step["number"] for step in response["procedure"]["steps"]] == [1, 2, 3]
    assert response["provider"]["provider"] == "openai-compatible"
    assert [claim["claim_id"] for claim in response["claims"]] == [
        sentence["claim_id"] for sentence in generated["sentences"]
    ]
    assert len(requests) == 1


def test_cli_refuses_a_truncated_procedure_without_returning_steps(tmp_path: Path) -> None:
    lines = [
        "17 Trail Post spring replacement",
        "1 Remove the spring cap.",
        "3 Install the spring cap.",
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, lines)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "What are the steps to replace the Trail Post spring?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert response["response_type"] == "procedure"
    assert response["failure"]["code"] == "not_found"
    assert "only partial procedure evidence" in response["failure"]["message"]
    assert response["procedure"] is None
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_does_not_substitute_structured_evidence_for_a_procedure(
    tmp_path: Path,
) -> None:
    lines = [
        "17 Trail Post spring torque table",
        "Trail Post spring torque: 20 N·m.",
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, lines)
    )
    specification_evidence_path.write_text(
        json.dumps(
            {
                "specifications": [
                    {
                        "id": "test-spring-torque",
                        "manufacturer": "Test Manufacturer",
                        "model": "Trail Post",
                        "component": "spring",
                        "attribute": "torque",
                        "aliases": [],
                        "value": {
                            "minimum": 20,
                            "maximum": 20,
                            "unit": "N·m",
                            "display": "20 N·m",
                        },
                        "conditions": ["Model: Trail Post"],
                        "source_id": "test-manual",
                        "citation": {
                            "printed_page": 17,
                            "physical_page": 1,
                            "section": "Trail Post spring torque table",
                        },
                        "evidence_excerpts": ["Trail Post spring torque: 20 N·m."],
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
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "How do I check the Trail Post spring torque?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert response["response_type"] == "procedure"
    assert response["specification"] is None
    assert response["procedure"] is None
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_inspects_the_retrieval_evidence_used_for_a_procedure(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, complete_procedure_lines())
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "evidence",
        "What are the steps to replace the Trail Post spring?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    inspection: dict[str, Any] = json.loads(result.stdout)
    assert inspection["source_pack_id"] == "test-1"
    assert len(inspection["matches"]) == 1
    match = inspection["matches"][0]
    assert match["title"] == "Trail Post spring replacement"
    assert match["complete"] is True
    assert match["validation_issues"] == []
    assert match["pages"][0]["physical_page"] == 1
    assert match["pages"][0]["printed_page"] == 17
    assert {block["kind"] for block in match["pages"][0]["blocks"]} >= {
        "heading",
        "table",
        "step",
        "warning",
    }
    table = next(block for block in match["pages"][0]["blocks"] if block["kind"] == "table")
    assert table["cells"] == ["Part", "Tool", "Torque"]
    assert [step["number"] for step in match["steps"]] == [1, 2, 3]


def test_cli_refuses_a_procedure_without_a_source_defined_end(tmp_path: Path) -> None:
    lines = [
        "17 Trail Post spring replacement",
        "1 Remove the spring cap.",
        "2 Replace the spring.",
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, lines)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "What are the steps to replace the Trail Post spring?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert "procedure end" in response["failure"]["message"]
    assert response["procedure"] is None
    assert response["claims"] == []


def test_cli_refuses_an_adjacent_model_without_reusing_a_procedure(tmp_path: Path) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, complete_procedure_lines())
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "What are the steps to replace the Trail Post X1 spring?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert response["procedure"] is None
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_rejects_an_end_marker_that_precedes_the_procedure_steps(
    tmp_path: Path,
) -> None:
    lines = [
        "17 Trail Post spring replacement",
        "This concludes the Trail Post spring replacement procedure.",
        "1 Remove the spring cap.",
        "2 Replace the spring.",
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, lines)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "What are the steps to replace the Trail Post spring?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert "procedure end" in response["failure"]["message"]
    assert response["procedure"] is None


def test_cli_routes_an_imperative_maintenance_task_to_a_procedure(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, complete_procedure_lines())
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "Replace the Trail Post spring.",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["response_type"] == "procedure"
    assert response["procedure"]["title"] == "Trail Post spring replacement"


def test_cli_attaches_a_warning_before_the_first_step(tmp_path: Path) -> None:
    lines = [
        "17 Trail Post spring replacement",
        "WARNING",
        "Release spring pressure before removing the cap.",
        "1 Remove the spring cap.",
        "2 Replace the spring.",
        "3 Install the spring cap.",
        "This concludes the Trail Post spring replacement procedure.",
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, lines)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "What are the steps to replace the Trail Post spring?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["procedure"]["steps"][0]["warnings"] == [
        {
            "severity": "warning",
            "text": "Release spring pressure before removing the cap.",
        }
    ]


def test_cli_keeps_multiple_procedures_and_leading_warnings_separate(
    tmp_path: Path,
) -> None:
    lines = [
        "17 Trail Post service procedures",
        "50 Hour Service Spring replacement",
        "NOTICE",
        "Hold the spring under compression.",
        "1 Remove the spring cap.",
        "2 Replace the spring.",
        "3 Install the spring cap.",
        "This concludes the Spring replacement procedure.",
        "200 Hour Service Bearing replacement",
        "1 Remove the bearing.",
        "2 Install the bearing.",
        "This concludes the Bearing replacement procedure.",
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, lines)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    spring_result = run_cli(
        "ask",
        "What are the steps for spring replacement?",
        "--data-dir",
        str(data_dir),
        "--json",
    )
    bearing_result = run_cli(
        "ask",
        "What are the steps for bearing replacement?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert spring_result.returncode == 0, spring_result.stderr
    spring: dict[str, Any] = json.loads(spring_result.stdout)
    assert spring["status"] == "supported"
    assert spring["procedure"]["title"] == "Spring replacement"
    assert [step["text"] for step in spring["procedure"]["steps"]] == [
        "Remove the spring cap.",
        "Replace the spring.",
        "Install the spring cap.",
    ]
    assert spring["procedure"]["steps"][0]["warnings"] == [
        {
            "severity": "notice",
            "text": "Hold the spring under compression.",
        }
    ]

    assert bearing_result.returncode == 0, bearing_result.stderr
    bearing: dict[str, Any] = json.loads(bearing_result.stdout)
    assert bearing["status"] == "supported"
    assert bearing["procedure"]["title"] == "Bearing replacement"
    assert [step["text"] for step in bearing["procedure"]["steps"]] == [
        "Remove the bearing.",
        "Install the bearing.",
    ]
    assert all(step["warnings"] == [] for step in bearing["procedure"]["steps"])


def test_cli_keeps_repeated_section_titles_as_separate_evidence(tmp_path: Path) -> None:
    lines = [
        "17 Trail Post service procedures",
        "50 Hour Service Spring replacement",
        "1 Remove the road spring.",
        "2 Install the road spring.",
        "This concludes the Spring replacement procedure.",
        "50 Hour Service Spring replacement",
        "1 Remove the trail spring.",
        "2 Install the trail spring.",
        "This concludes the Spring replacement procedure.",
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, lines)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "evidence",
        "What are the steps for spring replacement?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    inspection: dict[str, Any] = json.loads(result.stdout)
    assert len(inspection["matches"]) == 2
    assert all(match["complete"] for match in inspection["matches"])
    assert [[step["text"] for step in match["steps"]] for match in inspection["matches"]] == [
        ["Remove the road spring.", "Install the road spring."],
        ["Remove the trail spring.", "Install the trail spring."],
    ]


def test_cli_asks_for_the_task_when_two_procedures_share_an_identity(
    tmp_path: Path,
) -> None:
    lines = [
        "17 Trail Post service procedures",
        "50 Hour Service Spring replacement",
        "1 Remove the road spring.",
        "2 Install the road spring.",
        "This concludes the Spring replacement procedure.",
        "50 Hour Service Spring replacement",
        "1 Remove the trail spring.",
        "2 Install the trail spring.",
        "This concludes the Spring replacement procedure.",
    ]
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, lines)
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "What are the steps for spring replacement?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "clarification_required"
    assert response["clarification"] == {
        "message": "Please identify the exact task.",
        "missing_information": ["task"],
    }
    assert response["procedure"] is None
    assert response["claims"] == []
    assert response["citations"] == []


def test_cli_asks_for_a_task_when_the_procedure_request_has_no_subject(
    tmp_path: Path,
) -> None:
    manifest_path, specification_evidence_path, compatibility_evidence_path, data_dir = (
        prepare_procedure_fixture(tmp_path, complete_procedure_lines())
    )
    download_and_ingest(
        manifest_path,
        specification_evidence_path,
        compatibility_evidence_path,
        data_dir,
    )

    result = run_cli(
        "ask",
        "What are the steps?",
        "--data-dir",
        str(data_dir),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "clarification_required"
    assert response["clarification"] == {
        "message": "Please identify the exact task.",
        "missing_information": ["task"],
    }
    assert response["procedure"] is None
