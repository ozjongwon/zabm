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
                        "title": "Procedure Continuation Manual",
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


def test_adjacent_page_continuation_preserves_steps_pages_and_merge_reason(
    tmp_path: Path,
) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="continued-procedure",
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

    assert len(catalog["procedures"]) == 1
    procedure = catalog["procedures"][0]
    assert procedure["heading_path"] == ["Brake service", "Bleed the brake"]
    assert procedure["page_numbers"] == [1, 2]
    assert [step["number"] for step in procedure["steps"]] == [1, 2, 3]
    assert [step["citation"]["physical_page"] for step in procedure["steps"]] == [1, 1, 2]
    assert procedure["grouping_decisions"] == [
        {
            "decision": "merged",
            "reason": "continued step numbering on the adjacent page",
            "pages": [1, 2],
        }
    ]


def test_repeated_title_on_next_page_restarted_at_step_one_stays_separate(
    tmp_path: Path,
) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="repeated-procedure",
        pages=[
            {
                "lines": [
                    [720, 72, "18 Bleed the brake", {"font": "F2", "size": 16}],
                    [690, 72, "1 Fit the road syringe."],
                    [672, 72, "2 Open the road valve."],
                    [654, 72, "This concludes the road bleed."],
                    [20, 500, "18"],
                ]
            },
            {
                "lines": [
                    [720, 72, "19 Bleed the brake", {"font": "F2", "size": 16}],
                    [690, 72, "1 Fit the trail syringe."],
                    [672, 72, "2 Open the trail valve."],
                    [654, 72, "This concludes the trail bleed."],
                    [20, 500, "19"],
                ]
            },
        ],
    )
    _, catalog = ingest_corpus(workspace)

    assert len(catalog["procedures"]) == 2
    assert [procedure["page_numbers"] for procedure in catalog["procedures"]] == [[1], [2]]
    assert [
        [step["text"] for step in procedure["steps"]] for procedure in catalog["procedures"]
    ] == [
        ["Fit the road syringe.", "Open the road valve."],
        ["Fit the trail syringe.", "Open the trail valve."],
    ]
    assert all(procedure["validation_issues"] == [] for procedure in catalog["procedures"])
    assert catalog["procedures"][1]["grouping_decisions"] == [
        {
            "decision": "kept-separate",
            "reason": "repeated title started again at step 1",
            "pages": [1, 2],
        }
    ]


def test_same_title_on_a_different_heading_path_stays_separate(tmp_path: Path) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="different-heading-paths",
        pages=[
            {
                "lines": [
                    [720, 72, "18 Road service", {"font": "F2", "size": 16}],
                    [690, 72, "4.2 Bleed the brake", {"font": "F2", "size": 13}],
                    [672, 72, "1 Fit the syringe."],
                    [654, 72, "2 Open the valve."],
                    [20, 500, "18"],
                ]
            },
            {
                "lines": [
                    [720, 72, "19 Trail service", {"font": "F2", "size": 16}],
                    [690, 72, "4.2 Bleed the brake", {"font": "F2", "size": 13}],
                    [672, 72, "3 Close the valve."],
                    [654, 72, "4 Remove the syringe."],
                    [636, 72, "This concludes the trail bleed."],
                    [20, 500, "19"],
                ]
            },
        ],
    )
    _, catalog = ingest_corpus(workspace)

    assert len(catalog["procedures"]) == 2
    assert [procedure["heading_path"] for procedure in catalog["procedures"]] == [
        ["Road service", "Bleed the brake"],
        ["Trail service", "Bleed the brake"],
    ]
    assert [procedure["page_numbers"] for procedure in catalog["procedures"]] == [[1], [2]]
    assert catalog["procedures"][1]["grouping_decisions"] == [
        {
            "decision": "kept-separate",
            "reason": "heading path differs from the repeated title",
            "pages": [1, 2],
        }
    ]
    inspection = run_cli(
        "evidence",
        "What are the steps to bleed the brake?",
        "--data-dir",
        str(workspace.data_dir),
        "--json",
    )
    assert inspection.returncode == 0, inspection.stderr
    matches = json.loads(inspection.stdout)["matches"]
    assert [match["heading_path"] for match in matches] == [
        ["Road service", "Bleed the brake"],
        ["Trail service", "Bleed the brake"],
    ]
    assert matches[1]["grouping_decisions"] == [
        {
            "decision": "kept-separate",
            "reason": "heading path differs from the repeated title",
            "pages": [1, 2],
        }
    ]
    assert any("procedure end was not found" in issue for issue in matches[0]["validation_issues"])
    assert any(
        "required step 1 may be missing" in issue for issue in matches[1]["validation_issues"]
    )


def test_explicit_end_on_prior_page_prevents_title_based_continuation(tmp_path: Path) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="ended-repeat",
        pages=[
            {
                "lines": [
                    [720, 72, "18 Bleed the brake", {"font": "F2", "size": 16}],
                    [690, 72, "1 Fit the road syringe."],
                    [672, 72, "2 Open the road valve."],
                    [654, 72, "This concludes the road bleed."],
                    [20, 500, "18"],
                ]
            },
            {
                "lines": [
                    [720, 72, "19 Bleed the brake", {"font": "F2", "size": 16}],
                    [690, 72, "3 Fit the trail syringe."],
                    [672, 72, "4 Open the trail valve."],
                    [654, 72, "This concludes the trail bleed."],
                    [20, 500, "19"],
                ]
            },
        ],
    )
    _, catalog = ingest_corpus(workspace)

    assert len(catalog["procedures"]) == 2
    assert [procedure["page_numbers"] for procedure in catalog["procedures"]] == [[1], [2]]
    assert catalog["procedures"][1]["grouping_decisions"] == [
        {
            "decision": "kept-separate",
            "reason": "previous procedure ended before the repeated title",
            "pages": [1, 2],
        }
    ]


def test_intervening_heading_prevents_page_continuation(tmp_path: Path) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="interrupted-continuation",
        pages=[
            {
                "lines": [
                    [720, 72, "18 Brake service", {"font": "F2", "size": 16}],
                    [690, 72, "4.2 Bleed the brake", {"font": "F2", "size": 13}],
                    [672, 72, "1 Fit the bleed syringe."],
                    [654, 72, "2 Open the bleed valve."],
                    [620, 72, "4.3 Replace the brake pads", {"font": "F2", "size": 13}],
                    [20, 500, "18"],
                ]
            },
            {
                "lines": [
                    [720, 72, "4.2 Bleed the brake", {"font": "F2", "size": 13}],
                    [702, 72, "3 Close the bleed valve."],
                    [684, 72, "4 Remove the bleed syringe."],
                    [666, 72, "This concludes the bleed procedure."],
                    [20, 500, "19"],
                ]
            },
        ],
    )
    _, catalog = ingest_corpus(workspace)

    assert len(catalog["procedures"]) == 2
    assert [procedure["page_numbers"] for procedure in catalog["procedures"]] == [[1], [2]]
    assert catalog["procedures"][1]["grouping_decisions"] == [
        {
            "decision": "kept-separate",
            "reason": "an intervening heading ended the prior section",
            "pages": [1, 2],
        }
    ]


def test_cross_page_duplicate_step_number_is_merged_then_rejected(tmp_path: Path) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="cross-page-duplicate",
        pages=[
            {
                "lines": [
                    [720, 72, "18 Bleed the brake", {"font": "F2", "size": 16}],
                    [690, 72, "1 Fit the bleed syringe."],
                    [672, 72, "2 Open the bleed valve."],
                    [20, 500, "18"],
                ]
            },
            {
                "lines": [
                    [720, 72, "19 Bleed the brake", {"font": "F2", "size": 16}],
                    [690, 72, "2 Open the bleed valve."],
                    [672, 72, "3 Close the bleed valve."],
                    [654, 72, "This concludes the bleed procedure."],
                    [20, 500, "19"],
                ]
            },
        ],
    )
    _, catalog = ingest_corpus(workspace)

    assert len(catalog["procedures"]) == 1
    procedure = catalog["procedures"][0]
    assert procedure["page_numbers"] == [1, 2]
    assert [step["number"] for step in procedure["steps"]] == [1, 2, 3]
    assert procedure["validation_issues"] == ["step 2 appears more than once"]
    assert procedure["grouping_decisions"] == [
        {
            "decision": "merged",
            "reason": "resumed non-initial step numbering on the adjacent page",
            "pages": [1, 2],
        },
        {
            "decision": "rejected",
            "reason": "step 2 appears more than once in one candidate",
            "pages": [1, 2],
        },
    ]


def test_duplicate_step_numbers_remain_unsupported_and_record_rejection(
    tmp_path: Path,
) -> None:
    workspace = _workspace_with_pages(
        tmp_path,
        document_id="duplicate-numbers",
        pages=[
            {
                "lines": [
                    [720, 72, "22 Replace brake pads", {"font": "F2", "size": 16}],
                    [690, 72, "1 Remove the brake pad."],
                    [672, 72, "1 Remove the pad spring."],
                    [654, 72, "2 Install the brake pad."],
                    [636, 72, "This concludes the brake pad replacement."],
                ]
            }
        ],
    )
    _, catalog = ingest_corpus(workspace)

    assert len(catalog["procedures"]) == 1
    procedure = catalog["procedures"][0]
    assert procedure["validation_issues"] == ["step 1 appears more than once"]
    assert procedure["grouping_decisions"] == [
        {
            "decision": "rejected",
            "reason": "step 1 appears more than once in one candidate",
            "pages": [1],
        }
    ]
