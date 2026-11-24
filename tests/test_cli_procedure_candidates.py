from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from cross_layout_corpus import (
    CorpusWorkspace,
    ingest_corpus,
    materialize_corpus,
    write_positioned_pdf,
)
from test_cli_procedure import run_cli


def _workspace_with_pages(
    tmp_path: Path,
    *,
    document_id: str,
    title: str,
    lines: list[list[Any]],
) -> CorpusWorkspace:
    workspace = materialize_corpus(tmp_path)
    source_path = workspace.pdf_dir / f"{document_id}.pdf"
    write_positioned_pdf(source_path, [{"lines": lines}])
    workspace.manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": f"{document_id}-v1",
                "sources": [
                    {
                        "id": document_id,
                        "title": title,
                        "manufacturer": "Cross Layout Fixtures",
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
    return workspace


def test_cli_rejects_numbered_page_furniture_and_records_why(tmp_path: Path) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="mixed-number-noise",
        title="Mixed Number Noise Manual",
        lines=[
            [720, 72, "27 Replace the brake pad", {"font": "F2", "size": 16}],
            [690, 72, "1 Remove the wheel .......... 7"],
            [672, 72, "1 Clamp bolt 5 N m"],
            [654, 72, "1 Figure 3"],
            [636, 72, "1"],
            [618, 72, "1 Remove the brake pad."],
            [600, 72, "2 Install the brake pad."],
            [582, 72, "This concludes the brake pad replacement."],
        ],
    )

    _, catalog = ingest_corpus(workspace)
    page = catalog["sources"][0]["pages"][0]

    assert [
        (candidate["text"], candidate["reason"]) for candidate in page["rejected_step_candidates"]
    ] == [
        ("Remove the wheel .......... 7", "source-reference"),
        ("Clamp bolt 5 N m", "table-value"),
        ("Figure 3", "figure-callout"),
        ("1", "missing-action-text"),
    ]

    result = run_cli(
        "evidence",
        "What are the steps to replace the brake pad?",
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    inspection: dict[str, Any] = json.loads(result.stdout)
    assert len(inspection["matches"]) == 1
    match = inspection["matches"][0]
    assert match["complete"] is True
    assert [step["text"] for step in match["steps"]] == [
        "Remove the brake pad.",
        "Install the brake pad.",
    ]


def test_cli_rejects_numbered_items_without_a_procedure_section(tmp_path: Path) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="numbered-checklist",
        title="Maintenance Checklist Manual",
        lines=[
            [720, 72, "Maintenance checklist", {"font": "F2", "size": 16}],
            [690, 72, "1 Inspect the frame."],
            [672, 72, "2 Check the brakes."],
            [654, 72, "This concludes the checklist."],
        ],
    )

    _, catalog = ingest_corpus(workspace)
    page = catalog["sources"][0]["pages"][0]

    assert [
        (candidate["text"], candidate["reason"]) for candidate in page["rejected_step_candidates"]
    ] == [
        ("Inspect the frame.", "missing-procedure-heading"),
        ("Check the brakes.", "missing-procedure-heading"),
    ]


def test_cli_rejects_a_numbered_line_that_joins_two_columns(tmp_path: Path) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="joined-columns",
        title="Joined Columns Manual",
        lines=[
            [720, 72, "31 Replace the brake pad", {"font": "F2", "size": 16}],
            [690, 72, "1 Remove the brake pad."],
            [690, 360, "2 Install the brake pad."],
            [672, 72, "This concludes the brake pad replacement."],
        ],
    )

    _, catalog = ingest_corpus(workspace)
    page = catalog["sources"][0]["pages"][0]

    assert [
        (candidate["text"], candidate["reason"]) for candidate in page["rejected_step_candidates"]
    ] == [
        ("Remove the brake pad. 2 Install the brake pad.", "mixed-column"),
    ]


def test_cli_rejects_numbered_heading_fragments_without_an_action(tmp_path: Path) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="numbered-heading-fragment",
        title="Heading Fragment Manual",
        lines=[
            [720, 72, "32 Replace the brake pad", {"font": "F2", "size": 16}],
            [690, 72, "1 Part"],
            [672, 72, "This concludes the brake pad replacement."],
        ],
    )

    _, catalog = ingest_corpus(workspace)
    page = catalog["sources"][0]["pages"][0]

    assert [
        (candidate["text"], candidate["reason"]) for candidate in page["rejected_step_candidates"]
    ] == [("Part", "missing-action-text")]


def test_cli_rejects_discontinuous_step_numbering_in_a_section(tmp_path: Path) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="discontinuous-numbering",
        title="Discontinuous Numbering Manual",
        lines=[
            [720, 72, "33 Replace the brake pad", {"font": "F2", "size": 16}],
            [690, 72, "1 Remove the brake pad."],
            [672, 72, "3 Inspect the brake pad."],
            [654, 72, "2 Install the brake pad."],
            [636, 72, "This concludes the brake pad replacement."],
        ],
    )

    _, catalog = ingest_corpus(workspace)
    page = catalog["sources"][0]["pages"][0]

    assert [
        (candidate["text"], candidate["reason"]) for candidate in page["rejected_step_candidates"]
    ] == [
        ("Inspect the brake pad.", "numbering-discontinuous"),
        ("Install the brake pad.", "numbering-discontinuous"),
    ]
    assert [block["text"] for block in page["blocks"] if block["kind"] == "step"] == [
        "Remove the brake pad."
    ]
