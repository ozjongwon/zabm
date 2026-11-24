from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from cross_layout_corpus import (
    CorpusWorkspace,
    ingest_corpus,
    materialize_corpus,
    read_catalog,
    write_positioned_pdf,
)
from test_cli_procedure import run_cli


def _workspace_with_boundary_profile(
    tmp_path: Path,
    *,
    document_id: str,
    lines: list[list[Any]] | None = None,
    pages: list[list[list[Any]]] | None = None,
    strategy: str = "explicit-marker",
    reviewed_by: str | None = None,
    markers: list[str] | None = None,
) -> CorpusWorkspace:
    workspace = materialize_corpus(tmp_path)
    source_path = workspace.pdf_dir / f"{document_id}.pdf"
    if (lines is None) == (pages is None):
        raise ValueError("provide exactly one of lines or pages")
    page_payloads = (
        [{"lines": lines}] if lines is not None else [{"lines": page} for page in pages or []]
    )
    write_positioned_pdf(source_path, page_payloads)
    workspace.manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": f"{document_id}-v1",
                "sources": [
                    {
                        "id": document_id,
                        "title": "Procedure Boundary Manual",
                        "manufacturer": "Boundary Fixtures",
                        "url": source_path.as_uri(),
                        "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                        "retrieval_date": "2026-11-24",
                        "revision": "Fixture Rev 1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    profiles = json.loads(workspace.profile_path.read_text(encoding="utf-8"))
    end_boundaries = profiles["profiles"][0]["end_boundaries"]
    end_boundaries["strategy"] = strategy
    if markers is not None:
        end_boundaries["markers"] = markers
    if reviewed_by is not None:
        end_boundaries["section_boundary_reviewed_by"] = reviewed_by
    workspace.profile_path.write_text(json.dumps(profiles), encoding="utf-8")
    return workspace


def _ask(workspace: CorpusWorkspace, question: str) -> dict[str, Any]:
    result = run_cli(
        "ask",
        question,
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_artifact_records_an_explicit_end_and_preserves_audit_text(tmp_path: Path) -> None:
    workspace = _workspace_with_boundary_profile(
        tmp_path,
        document_id="explicit-boundary",
        lines=[
            [720, 72, "17 Bleed the brake", {"font": "F2", "size": 16}],
            [690, 72, "1 Fit the bleed syringe."],
            [672, 72, "WARNING"],
            [654, 72, "Do not spill hydraulic fluid."],
            [636, 72, "2 Open the bleed valve."],
            [618, 72, "This concludes the bleed procedure."],
        ],
    )
    _, catalog = ingest_corpus(workspace)

    procedure = catalog["procedures"][0]
    assert procedure["start_boundary"] == "Bleed the brake"
    assert procedure["end_boundary"] == "This concludes the bleed procedure."
    assert procedure["end_strategy"] == "explicit-marker"
    assert procedure["completeness_notes"] == ["This concludes the bleed procedure."]
    assert [
        {"severity": warning["severity"], "text": warning["text"]}
        for warning in procedure["steps"][0]["warnings"]
    ] == [{"severity": "warning", "text": "Do not spill hydraulic fluid."}]

    response = _ask(workspace, "What are the steps to bleed the brake?")
    assert response["status"] == "supported"
    assert read_catalog(workspace)["procedures"][0]["end_boundary"] == (
        "This concludes the bleed procedure."
    )


def test_approved_section_boundary_ends_a_procedure_at_the_next_peer_heading(
    tmp_path: Path,
) -> None:
    workspace = _workspace_with_boundary_profile(
        tmp_path,
        document_id="section-boundary",
        strategy="section-boundary",
        reviewed_by="repository-maintainer: ticket-07",
        lines=[
            [720, 72, "18 Brake service", {"font": "F2", "size": 16}],
            [690, 72, "4.2 Bleed the brake", {"font": "F2", "size": 13}],
            [672, 72, "1 Fit the bleed syringe."],
            [654, 72, "2 Open the bleed valve."],
            [610, 72, "4.3 Replace the brake pads", {"font": "F2", "size": 13}],
            [592, 72, "1 Remove the worn pads."],
            [574, 72, "2 Install the new pads."],
        ],
    )
    _, catalog = ingest_corpus(workspace)

    bleed = next(
        procedure for procedure in catalog["procedures"] if procedure["title"] == "Bleed the brake"
    )
    assert bleed["start_boundary"] == "Brake service > Bleed the brake"
    assert bleed["end_boundary"] == "Brake service > Replace the brake pads"
    assert bleed["end_strategy"] == "section-boundary"

    response = _ask(workspace, "What are the steps to bleed the brake?")
    assert response["status"] == "supported"


def test_child_heading_is_ambiguous_and_cannot_complete_a_procedure(tmp_path: Path) -> None:
    workspace = _workspace_with_boundary_profile(
        tmp_path,
        document_id="ambiguous-child",
        strategy="section-boundary",
        reviewed_by="repository-maintainer: ticket-07",
        lines=[
            [720, 72, "18 Brake service", {"font": "F2", "size": 16}],
            [690, 72, "4.2 Bleed the brake", {"font": "F2", "size": 13}],
            [672, 72, "1 Fit the bleed syringe."],
            [654, 72, "2 Open the bleed valve."],
            [610, 72, "4.2.1 Fluid notes", {"font": "F2", "size": 12}],
            [592, 72, "Use fresh hydraulic fluid."],
            [548, 72, "4.3 Replace the brake pads", {"font": "F2", "size": 13}],
            [530, 72, "1 Remove the worn pads."],
        ],
    )
    _, catalog = ingest_corpus(workspace)

    bleed = catalog["procedures"][0]
    assert bleed["end_boundary"] is None
    assert bleed["end_strategy"] == "section-boundary"

    response = _ask(workspace, "What are the steps to bleed the brake?")
    assert response["status"] == "not_found"
    assert "only partial procedure evidence" in response["failure"]["message"]


def test_document_end_without_a_closing_marker_or_next_heading_is_partial(
    tmp_path: Path,
) -> None:
    workspace = _workspace_with_boundary_profile(
        tmp_path,
        document_id="missing-end",
        strategy="section-boundary",
        reviewed_by="repository-maintainer: ticket-07",
        lines=[
            [720, 72, "17 Bleed the brake", {"font": "F2", "size": 16}],
            [690, 72, "1 Fit the bleed syringe."],
            [672, 72, "2 Open the bleed valve."],
        ],
    )
    _, catalog = ingest_corpus(workspace)

    procedure = catalog["procedures"][0]
    assert procedure["end_boundary"] is None
    assert procedure["end_strategy"] == "section-boundary"

    inspection = run_cli(
        "evidence",
        "What are the steps to bleed the brake?",
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )
    assert inspection.returncode == 0, inspection.stderr
    match = json.loads(inspection.stdout)["matches"][0]
    assert match["complete"] is False
    assert "the source-defined procedure end was not found" in match["validation_issues"]

    response = _ask(workspace, "What are the steps to bleed the brake?")
    assert response["status"] == "not_found"
    assert response["procedure"] is None


def test_explicit_end_marker_on_the_next_page_completes_the_procedure(
    tmp_path: Path,
) -> None:
    workspace = _workspace_with_boundary_profile(
        tmp_path,
        document_id="next-page-end",
        pages=[
            [
                [720, 72, "17 Bleed the brake", {"font": "F2", "size": 16}],
                [690, 72, "1 Fit the bleed syringe."],
                [672, 72, "2 Open the bleed valve."],
            ],
            [[720, 72, "This concludes the bleed procedure."]],
        ],
    )
    _, catalog = ingest_corpus(workspace)

    procedure = catalog["procedures"][0]
    assert procedure["page_numbers"] == [1]
    assert procedure["end_boundary"] == "This concludes the bleed procedure."
    assert procedure["end_strategy"] == "explicit-marker"

    response = _ask(workspace, "What are the steps to bleed the brake?")
    assert response["status"] == "supported"


def test_warning_collection_stops_before_an_explicit_end_marker(tmp_path: Path) -> None:
    workspace = _workspace_with_boundary_profile(
        tmp_path,
        document_id="warning-before-end",
        markers=["End of procedure"],
        lines=[
            [720, 72, "17 Bleed the brake", {"font": "F2", "size": 16}],
            [690, 72, "1 Fit the bleed syringe."],
            [672, 72, "WARNING"],
            [654, 72, "Do not spill hydraulic fluid."],
            [636, 72, "End of procedure"],
        ],
    )
    _, catalog = ingest_corpus(workspace)

    procedure = catalog["procedures"][0]
    assert procedure["end_boundary"] == "End of procedure"
    assert [
        {"severity": warning["severity"], "text": warning["text"]}
        for warning in procedure["steps"][0]["warnings"]
    ] == [{"severity": "warning", "text": "Do not spill hydraulic fluid."}]

    response = _ask(workspace, "What are the steps to bleed the brake?")
    assert response["status"] == "supported"


def test_contradictory_navigation_note_keeps_an_explicitly_ended_procedure_partial(
    tmp_path: Path,
) -> None:
    workspace = _workspace_with_boundary_profile(
        tmp_path,
        document_id="continued-after-end",
        lines=[
            [720, 72, "17 Bleed the brake", {"font": "F2", "size": 16}],
            [690, 72, "1 Fit the bleed syringe."],
            [672, 72, "2 Open the bleed valve."],
            [654, 72, "This concludes the bleed procedure."],
            [618, 72, "Procedure continued on page 99."],
        ],
    )
    _, catalog = ingest_corpus(workspace)

    procedure = catalog["procedures"][0]
    assert procedure["completeness_notes"] == [
        "This concludes the bleed procedure.",
        "Procedure continued on page 99.",
    ]

    response = _ask(workspace, "What are the steps to bleed the brake?")
    assert response["status"] == "not_found"
    assert "partial or truncated" in response["failure"]["message"]


def test_next_page_navigation_note_after_an_explicit_end_keeps_the_procedure_partial(
    tmp_path: Path,
) -> None:
    workspace = _workspace_with_boundary_profile(
        tmp_path,
        document_id="continued-after-next-page-end",
        pages=[
            [
                [720, 72, "17 Bleed the brake", {"font": "F2", "size": 16}],
                [690, 72, "1 Fit the bleed syringe."],
                [672, 72, "2 Open the bleed valve."],
                [654, 72, "This concludes the bleed procedure."],
            ],
            [[720, 72, "Procedure continued on page 99."]],
        ],
    )
    _, catalog = ingest_corpus(workspace)

    procedure = catalog["procedures"][0]
    assert procedure["end_boundary"] == "This concludes the bleed procedure."
    assert procedure["completeness_notes"] == [
        "This concludes the bleed procedure.",
        "Procedure continued on page 99.",
    ]

    response = _ask(workspace, "What are the steps to bleed the brake?")
    assert response["status"] == "not_found"
    assert "partial or truncated" in response["failure"]["message"]


@pytest.mark.parametrize(
    ("case_id", "step_lines", "expected_issue"),
    [
        (
            "begins-after-step-1",
            [[690, 72, "2 Open the bleed valve."], [672, 72, "3 Close the bleed valve."]],
            "required step 1 may be missing",
        ),
        (
            "duplicate-step",
            [
                [690, 72, "1 Fit the bleed syringe."],
                [672, 72, "2 Open the bleed valve."],
                [654, 72, "2 Open the bleed valve."],
            ],
            "step 2 appears more than once",
        ),
        (
            "unordered-step",
            [
                [690, 72, "1 Fit the bleed syringe."],
                [672, 72, "3 Close the bleed valve."],
                [654, 72, "2 Open the bleed valve."],
            ],
            "numbered step 3 is discontinuous after step 1",
        ),
    ],
)
def test_incomplete_or_ambiguous_step_sequences_never_become_supported(
    tmp_path: Path,
    case_id: str,
    step_lines: list[list[Any]],
    expected_issue: str,
) -> None:
    workspace = _workspace_with_boundary_profile(
        tmp_path,
        document_id=case_id,
        lines=[
            [720, 72, "17 Bleed the brake", {"font": "F2", "size": 16}],
            *step_lines,
            [600, 72, "This concludes the bleed procedure."],
        ],
    )
    ingest_corpus(workspace)

    inspection = run_cli(
        "evidence",
        "What are the steps to bleed the brake?",
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )
    assert inspection.returncode == 0, inspection.stderr
    match = json.loads(inspection.stdout)["matches"][0]
    assert match["complete"] is False
    assert any(expected_issue in issue for issue in match["validation_issues"])

    response = _ask(workspace, "What are the steps to bleed the brake?")
    assert response["status"] == "not_found"
    assert response["procedure"] is None
