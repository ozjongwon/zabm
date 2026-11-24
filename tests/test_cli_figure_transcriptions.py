from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from cross_layout_corpus import ingest_corpus, materialize_corpus
from test_cli_procedure import run_cli


def _transcription_artifact() -> dict[str, Any]:
    return {
        "artifact_version": "verified-transcriptions-v1",
        "transcriptions": [
            {
                "id": "figure-only-reach-adjust",
                "document_id": "figure-only-page",
                "title": "Adjust the reach",
                "location": {
                    "physical_page": 1,
                    "printed_page": 1,
                    "section": "Adjust the reach",
                    "heading_path": ["Adjust the reach"],
                    "box": {
                        "x_min": 60,
                        "y_min": 600,
                        "x_max": 550,
                        "y_max": 760,
                    },
                },
                "steps": [
                    {
                        "number": 1,
                        "text": "Loosen the reach adjuster screw.",
                        "source_box": {
                            "x_min": 70,
                            "y_min": 650,
                            "x_max": 360,
                            "y_max": 675,
                        },
                        "warnings": [],
                    },
                    {
                        "number": 2,
                        "text": "Turn the adjuster to the desired reach.",
                        "source_box": {
                            "x_min": 70,
                            "y_min": 620,
                            "x_max": 380,
                            "y_max": 645,
                        },
                        "warnings": [
                            {
                                "severity": "notice",
                                "text": "Do not force the adjuster past its stop.",
                            }
                        ],
                    },
                ],
                "end_boundary": "This concludes the reach adjustment.",
                "verification": {
                    "status": "human_verified",
                    "verified_by": "repository-maintainer",
                    "verified_at": "2026-11-24",
                },
            }
        ],
    }


def _write_transcription_artifact(
    path: Path,
    artifact: dict[str, Any],
) -> Path:
    path.write_text(json.dumps(artifact), encoding="utf-8")
    return path


def test_text_free_and_callout_only_pages_require_transcription(
    tmp_path: Path,
) -> None:
    workspace = materialize_corpus(
        tmp_path,
        extra_documents=[
            {
                "id": "scanned-reach-page",
                "title": "Scanned Reach Sheet",
                "manufacturer": "Cross Layout Fixtures",
                "pages": [{"lines": []}],
            },
            {
                "id": "callout-reach-page",
                "title": "Callout Reach Sheet",
                "manufacturer": "Cross Layout Fixtures",
                "pages": [
                    {
                        "lines": [
                            [720, 72, "Reach adjustment"],
                            [690, 72, "1 Figure callout"],
                            [672, 72, "2 Figure callout"],
                        ]
                    }
                ],
            },
        ],
    )

    report, catalog = ingest_corpus(workspace)

    pages = {
        source["document_id"]: source["pages"][0]
        for source in catalog["sources"]
        if source["document_id"] in {"scanned-reach-page", "callout-reach-page"}
    }
    assert {document_id: page["ingestion_outcome"] for document_id, page in pages.items()} == {
        "scanned-reach-page": "transcription-required",
        "callout-reach-page": "transcription-required",
    }
    assert {page["document_id"] for page in report["transcription_required_pages"]} >= {
        "scanned-reach-page",
        "callout-reach-page",
    }
    assert "Figure callout" in pages["callout-reach-page"]["text"]
    assert not any(
        procedure["document_id"] in {"scanned-reach-page", "callout-reach-page"}
        for procedure in catalog["procedures"]
    )


def test_unverified_transcription_remains_inspectable_but_ineligible(
    tmp_path: Path,
) -> None:
    workspace = materialize_corpus(tmp_path)
    artifact = _transcription_artifact()
    artifact["transcriptions"][0]["verification"] = {
        "status": "ocr_unverified",
        "verified_by": "",
        "verified_at": None,
    }
    transcriptions_path = _write_transcription_artifact(
        tmp_path / "unverified-transcriptions.json",
        artifact,
    )

    report, catalog = ingest_corpus(
        workspace,
        transcriptions_path=transcriptions_path,
    )

    page = next(
        page
        for source in catalog["sources"]
        if source["document_id"] == "figure-only-page"
        for page in source["pages"]
    )
    assert page["ingestion_outcome"] == "transcription-required"
    assert "Figure callout" in page["text"]
    assert page["verified_transcription_spans"] == []
    assert [
        transcription["steps"][1]["text"] for transcription in page["unverified_transcriptions"]
    ] == ["Turn the adjuster to the desired reach."]
    assert report["verified_transcription_count"] == 0
    assert not any(
        procedure["document_id"] == "figure-only-page" for procedure in catalog["procedures"]
    )

    result = run_cli(
        "ask",
        "How do I adjust the reach?",
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "not_found"


@pytest.mark.parametrize(
    ("case", "expected_error"),
    [
        ("missing-reviewer", "requires a named reviewer"),
        ("missing-date", "requires a verification date"),
        ("missing-page", "references missing physical page 2"),
        ("discontinuous-steps", "steps must be contiguous from 1"),
        ("box-outside-location", "lies outside the verified source location"),
        ("non-canonical-id", "must be lowercase alphanumeric words separated by hyphens"),
    ],
)
def test_invalid_human_verified_transcription_fails_closed(
    tmp_path: Path,
    case: str,
    expected_error: str,
) -> None:
    workspace = materialize_corpus(tmp_path)
    artifact = _transcription_artifact()
    transcription = artifact["transcriptions"][0]
    if case == "missing-reviewer":
        transcription["verification"]["verified_by"] = ""
    elif case == "missing-date":
        transcription["verification"]["verified_at"] = None
    elif case == "missing-page":
        transcription["location"]["physical_page"] = 2
    elif case == "discontinuous-steps":
        transcription["steps"][1]["number"] = 3
    elif case == "box-outside-location":
        transcription["steps"][1]["source_box"]["x_min"] = 20
    elif case == "non-canonical-id":
        transcription["id"] = "Figure_Only Reach"
    transcriptions_path = _write_transcription_artifact(
        tmp_path / f"{case}.json",
        artifact,
    )

    result = run_cli(
        "ingest",
        "--manifest",
        str(workspace.manifest_path),
        "--evidence",
        str(workspace.specification_evidence_path),
        "--compatibility-evidence",
        str(workspace.compatibility_evidence_path),
        "--ingestion-profiles",
        str(workspace.profile_path),
        "--transcriptions",
        str(transcriptions_path),
        "--pdf-dir",
        str(workspace.pdf_dir),
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )

    assert result.returncode == 1
    assert expected_error in result.stderr


def test_figure_only_content_reports_transcription_required_and_is_ineligible(
    tmp_path: Path,
) -> None:
    workspace = materialize_corpus(tmp_path)

    report, catalog = ingest_corpus(workspace)

    page = next(
        page
        for source in catalog["sources"]
        if source["document_id"] == "figure-only-page"
        for page in source["pages"]
    )
    assert page["page_kind"] == "figure"
    assert page["ingestion_outcome"] == "transcription-required"
    assert "Figure callout" in page["text"]
    assert page["spans"]
    assert {entry["document_id"]: entry for entry in report["transcription_required_pages"]} == {
        "figure-only-page": {
            "document_id": "figure-only-page",
            "physical_page": 1,
            "printed_page": 1,
            "page_kind": "figure",
            "reason": "figure and scanned content requires human-verified transcription",
        },
        "uncertain-page": {
            "document_id": "uncertain-page",
            "physical_page": 1,
            "printed_page": 1,
            "page_kind": "unknown",
            "reason": (
                "scanned content has no extractable text and requires human-verified transcription"
            ),
        },
    }
    assert not any(
        procedure["document_id"] == "figure-only-page" for procedure in catalog["procedures"]
    )

    result = run_cli(
        "ask",
        "How do I adjust the reach?",
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "not_found"
    assert response["procedure"] is None


def test_verified_transcription_makes_figure_procedure_answerable(tmp_path: Path) -> None:
    workspace = materialize_corpus(tmp_path)
    transcriptions_path = tmp_path / "verified-transcriptions.json"
    transcriptions_path.write_text(
        json.dumps(
            {
                "artifact_version": "verified-transcriptions-v1",
                "transcriptions": [
                    {
                        "id": "figure-only-reach-adjust",
                        "document_id": "figure-only-page",
                        "title": "Adjust the reach",
                        "location": {
                            "physical_page": 1,
                            "printed_page": 1,
                            "section": "Adjust the reach",
                            "heading_path": ["Adjust the reach"],
                            "box": {
                                "x_min": 60,
                                "y_min": 600,
                                "x_max": 550,
                                "y_max": 760,
                            },
                        },
                        "steps": [
                            {
                                "number": 1,
                                "text": "Loosen the reach adjuster screw.",
                                "source_box": {
                                    "x_min": 70,
                                    "y_min": 650,
                                    "x_max": 360,
                                    "y_max": 675,
                                },
                                "warnings": [],
                            },
                            {
                                "number": 2,
                                "text": "Turn the adjuster to the desired reach.",
                                "source_box": {
                                    "x_min": 70,
                                    "y_min": 620,
                                    "x_max": 380,
                                    "y_max": 645,
                                },
                                "warnings": [
                                    {
                                        "severity": "notice",
                                        "text": "Do not force the adjuster past its stop.",
                                    }
                                ],
                            },
                        ],
                        "end_boundary": "This concludes the reach adjustment.",
                        "verification": {
                            "status": "human_verified",
                            "verified_by": "repository-maintainer",
                            "verified_at": "2026-11-24",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report, catalog = ingest_corpus(
        workspace,
        transcriptions_path=transcriptions_path,
    )

    page = next(
        page
        for source in catalog["sources"]
        if source["document_id"] == "figure-only-page"
        for page in source["pages"]
    )
    assert page["ingestion_outcome"] == "transcription-verified"
    assert "Figure callout" in page["text"]
    assert {span["evidence_plane"] for span in page["spans"]} == {"pdf-text"}
    assert {span["evidence_plane"] for span in page["verified_transcription_spans"]} == {
        "verified-transcription"
    }
    assert [
        page
        for page in report["transcription_required_pages"]
        if page["document_id"] == "figure-only-page"
    ] == []
    assert report["verified_transcription_count"] == 1
    assert report["ingestion_provenance"]["transcription_evidence_sha256"] == (
        hashlib.sha256(transcriptions_path.read_bytes()).hexdigest()
    )

    procedure = next(
        procedure
        for procedure in catalog["procedures"]
        if procedure["document_id"] == "figure-only-page"
    )
    assert procedure["evidence_plane"] == "verified-transcription"
    assert procedure["verified_transcription"]["transcription_id"] == ("figure-only-reach-adjust")
    assert procedure["verified_transcription"]["source_location"] == {
        **json.loads(transcriptions_path.read_text(encoding="utf-8"))["transcriptions"][0][
            "location"
        ]
    }
    assert procedure["verified_transcription"]["verification"] == {
        "status": "human_verified",
        "verified_by": "repository-maintainer",
        "verified_at": "2026-11-24",
    }

    result = run_cli(
        "ask",
        "How do I adjust the reach?",
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    response: dict[str, Any] = json.loads(result.stdout)
    assert response["status"] == "supported"
    assert response["procedure"]["title"] == "Adjust the reach"
    assert [step["text"] for step in response["procedure"]["steps"]] == [
        "Loosen the reach adjuster screw.",
        "Turn the adjuster to the desired reach.",
    ]
    assert response["procedure"]["steps"][1]["warnings"] == [
        {"severity": "notice", "text": "Do not force the adjuster past its stop."}
    ]
    assert response["citations"][0]["section"] == "Adjust the reach"
    assert response["citations"][0]["physical_page"] == 1
    assert response["citations"][0]["printed_page"] == 1
