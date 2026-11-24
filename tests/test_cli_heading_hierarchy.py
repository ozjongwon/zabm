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
    pages: list[dict[str, Any]],
) -> CorpusWorkspace:
    workspace = materialize_corpus(tmp_path)
    source_path = workspace.pdf_dir / f"{document_id}.pdf"
    write_positioned_pdf(source_path, pages)
    workspace.manifest_path.write_text(
        json.dumps(
            {
                "manifest_version": f"{document_id}-v1",
                "sources": [
                    {
                        "id": document_id,
                        "title": "Heading Hierarchy Manual",
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


def _evidence(workspace: CorpusWorkspace, question: str) -> dict[str, Any]:
    result = run_cli(
        "evidence",
        question,
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_cli_separates_adjacent_numbered_sections_and_ignores_body_text_as_a_title(
    tmp_path: Path,
) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="numbered-sections",
        pages=[
            {
                "lines": [
                    [720, 72, "18 Brake service", {"font": "F2", "size": 16}],
                    [690, 72, "4.2 Bleed the brake", {"font": "F2", "size": 13}],
                    [672, 72, "Bleed the system from the reservoir."],
                    [654, 72, "NOTICE"],
                    [636, 72, "Use fresh hydraulic fluid."],
                    [618, 72, "1 Fit the bleed syringe."],
                    [600, 72, "2 Open the bleed valve."],
                    [582, 72, "This concludes the bleed procedure."],
                    [550, 72, "4.3 Replace the brake pads", {"font": "F2", "size": 13}],
                    [532, 72, "1 Remove the worn pads."],
                    [514, 72, "2 Install the new pads."],
                    [496, 72, "This concludes the pad procedure."],
                ]
            }
        ],
    )
    _, catalog = ingest_corpus(workspace)

    page = catalog["sources"][0]["pages"][0]
    assert [
        (block["text"], block["heading_path"])
        for block in page["blocks"]
        if block["kind"] == "heading"
    ] == [
        ("18 Brake service", ["Brake service"]),
        ("4.2 Bleed the brake", ["Brake service", "Bleed the brake"]),
        ("4.3 Replace the brake pads", ["Brake service", "Replace the brake pads"]),
    ]

    bleed = _evidence(workspace, "What are the steps to bleed the brake?")
    assert bleed["matches"][0]["title"] == "Bleed the brake"
    assert bleed["matches"][0]["heading_path"] == ["Brake service", "Bleed the brake"]
    assert bleed["matches"][0]["steps"][0]["citation"]["section"] == "Bleed the brake"

    pads = _evidence(workspace, "What are the steps to replace the brake pads?")
    assert pads["matches"][0]["title"] == "Replace the brake pads"
    assert [step["number"] for step in pads["matches"][0]["steps"]] == [1, 2]


def test_cli_keeps_repeated_section_titles_as_distinct_heading_paths(
    tmp_path: Path,
) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="repeated-sections",
        pages=[
            {
                "lines": [
                    [720, 72, "20 Spring replacement", {"font": "F2", "size": 16}],
                    [
                        690,
                        72,
                        "50 Hour Service Spring replacement",
                        {"font": "F2", "size": 13},
                    ],
                    [672, 72, "1 Remove the road spring."],
                    [654, 72, "2 Install the road spring."],
                    [636, 72, "This concludes the road spring procedure."],
                    [
                        600,
                        72,
                        "200 Hour Service Spring replacement",
                        {"font": "F2", "size": 13},
                    ],
                    [582, 72, "1 Remove the trail spring."],
                    [564, 72, "2 Install the trail spring."],
                    [546, 72, "This concludes the trail spring procedure."],
                ]
            }
        ],
    )
    _, catalog = ingest_corpus(workspace)

    headings = [
        (block["text"], block["heading_path"])
        for block in catalog["sources"][0]["pages"][0]["blocks"]
        if block["kind"] == "heading"
    ]
    assert headings == [
        ("20 Spring replacement", ["Spring replacement"]),
        (
            "50 Hour Service Spring replacement",
            ["Spring replacement", "50 Hour Service Spring replacement"],
        ),
        (
            "200 Hour Service Spring replacement",
            ["Spring replacement", "200 Hour Service Spring replacement"],
        ),
    ]

    matches = _evidence(workspace, "What are the steps for spring replacement?")["matches"]
    assert [match["title"] for match in matches] == [
        "Spring replacement",
        "Spring replacement",
    ]
    assert [match["heading_path"][-1] for match in matches] == [
        "50 Hour Service Spring replacement",
        "200 Hour Service Spring replacement",
    ]
    assert catalog["procedures"][1]["grouping_decisions"] == [
        {
            "decision": "kept-separate",
            "reason": "heading path differs from the repeated title",
            "pages": [1],
        }
    ]


def test_cli_continues_numbered_heading_hierarchy_across_pages(tmp_path: Path) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="continued-sections",
        pages=[
            {
                "lines": [
                    [720, 72, "18 Brake service", {"font": "F2", "size": 16}],
                    [690, 72, "4.2 Bleed the brake", {"font": "F2", "size": 13}],
                    [672, 72, "1 Fit the bleed syringe."],
                    [654, 72, "2 Open the bleed valve."],
                    [20, 500, "18"],
                ]
            },
            {
                "lines": [
                    [
                        720,
                        72,
                        "4.2 Bleed the brake continued",
                        {"font": "F2", "size": 13},
                    ],
                    [702, 72, "3 Close the bleed valve."],
                    [684, 72, "This concludes the bleed procedure."],
                    [20, 500, "19"],
                ]
            },
        ],
    )
    _, catalog = ingest_corpus(workspace)

    continuation_blocks = [
        (block["text"], block["heading_path"])
        for block in catalog["sources"][0]["pages"][1]["blocks"]
        if block["kind"] == "heading"
    ]
    assert continuation_blocks == [
        (
            "4.2 Bleed the brake continued",
            ["Brake service", "Bleed the brake"],
        )
    ]

    match = _evidence(workspace, "What are the steps to bleed the brake?")["matches"][0]
    assert match["complete"] is True
    assert match["heading_path"] == ["Brake service", "Bleed the brake"]
    assert [step["number"] for step in match["steps"]] == [1, 2, 3]
    assert [page["physical_page"] for page in match["pages"]] == [1, 2]


def test_cli_applies_profile_heading_rules_and_excludes_page_furniture(
    tmp_path: Path,
) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="profile-headings",
        pages=[
            {
                "lines": [
                    [720, 72, "21 Brake service", {"font": "F2", "size": 16}],
                    [690, 72, "MAGURA | Bleed the brake"],
                    [672, 72, "Bleed the system from the reservoir."],
                    [654, 72, "1 Fit the bleed syringe."],
                    [636, 72, "2 Open the bleed valve."],
                    [618, 72, "This concludes the bleed procedure."],
                    [20, 72, "4.9 Footer heading", {"font": "F2", "size": 13}],
                ]
            }
        ],
    )
    profiles = json.loads(workspace.profile_path.read_text(encoding="utf-8"))
    profiles["profiles"][0]["headings"]["rules"] = [
        {
            "pattern": r"^MAGURA \| (?P<title>.+)$",
            "level": 2,
            "title_group": 1,
        }
    ]
    workspace.profile_path.write_text(json.dumps(profiles), encoding="utf-8")
    _, catalog = ingest_corpus(workspace)

    headings = [
        (block["text"], block["heading_path"])
        for block in catalog["sources"][0]["pages"][0]["blocks"]
        if block["kind"] == "heading"
    ]
    assert headings == [
        ("21 Brake service", ["Brake service"]),
        ("MAGURA | Bleed the brake", ["Brake service", "Bleed the brake"]),
    ]
