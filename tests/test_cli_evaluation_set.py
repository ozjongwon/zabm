from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from test_cli_specification import run_cli

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVALUATION_SET = REPO_ROOT / "data" / "evaluation" / "evaluation-set-v1.json"
EXPECTED_COUNTS = {
    "specification": 36,
    "compatibility": 27,
    "procedure": 27,
    "not_found": 15,
    "conflicting_evidence": 8,
    "out_of_scope": 7,
}
REQUIRED_EDGE_CASES = {
    "adjacent_model",
    "wrong_generation",
    "cross_brand_pair",
    "unsupported_material",
    "missing_attribute",
    "truncated_procedure",
    "ambiguous_alias",
    "false_premise",
}


def load_evaluation_set() -> dict[str, Any]:
    return json.loads(DEFAULT_EVALUATION_SET.read_text(encoding="utf-8"))


def write_evaluation_set(path: Path, evaluation_set: dict[str, Any]) -> None:
    path.write_text(json.dumps(evaluation_set), encoding="utf-8")


def test_cli_validates_the_frozen_120_item_evaluation_set() -> None:
    result = run_cli("evaluation-set", "--json")

    assert result.returncode == 0, result.stderr
    report: dict[str, Any] = json.loads(result.stdout)
    assert report["status"] == "valid"
    assert report["evaluation_set_id"] == "bicycle-maintenance-evaluation-v1"
    assert report["source_pack_id"] == "2026-11-23.3-frozen-1"
    assert report["item_count"] == 120
    assert report["category_counts"] == EXPECTED_COUNTS
    assert report["freeze_verified"] is True

    evaluation_set = load_evaluation_set()
    assert len({item["id"] for item in evaluation_set["items"]}) == 120
    assert all(item["question"].strip() for item in evaluation_set["items"])
    assert all("expected" in item for item in evaluation_set["items"])

    observed_edge_cases = {
        edge_case for item in evaluation_set["items"] for edge_case in item.get("edge_cases", [])
    }
    assert observed_edge_cases >= REQUIRED_EDGE_CASES

    for item in evaluation_set["items"]:
        if item["category"] == "out_of_scope":
            assert item["evidence"] == []
        else:
            assert item["evidence"]

    supported_specifications = [
        item
        for item in evaluation_set["items"]
        if item["category"] == "specification" and item["expected"]["status"] == "supported"
    ]
    assert supported_specifications
    assert all(
        item["expected"]["specification"]["value"]["minimum"]
        <= item["expected"]["specification"]["value"]["maximum"]
        for item in supported_specifications
    )
    assert all(
        item["expected"]["specification"]["value"]["unit"] for item in supported_specifications
    )
    assert all(
        item["expected"]["specification"]["required_qualifiers"]
        for item in supported_specifications
    )

    supported_procedures = [
        item
        for item in evaluation_set["items"]
        if item["category"] == "procedure" and item["expected"]["status"] == "supported"
    ]
    assert supported_procedures
    assert all(item["expected"]["procedure"]["steps"] for item in supported_procedures)


def test_cli_rejects_an_evaluation_set_with_a_missing_category(
    tmp_path: Path,
) -> None:
    evaluation_set = load_evaluation_set()
    evaluation_set["items"] = [
        item for item in evaluation_set["items"] if item["category"] != "conflicting_evidence"
    ]
    evaluation_set_path = tmp_path / "evaluation-set.json"
    write_evaluation_set(evaluation_set_path, evaluation_set)

    result = run_cli(
        "evaluation-set",
        "--evaluation-set",
        str(evaluation_set_path),
        "--json",
    )

    assert result.returncode == 1
    assert "conflicting_evidence: expected 8, found 0" in result.stderr


def test_cli_rejects_an_evaluation_set_with_incorrect_category_counts(
    tmp_path: Path,
) -> None:
    evaluation_set = load_evaluation_set()
    evaluation_set["items"] = [item for item in evaluation_set["items"] if item["id"] != "oos-007"]
    evaluation_set_path = tmp_path / "evaluation-set.json"
    write_evaluation_set(evaluation_set_path, evaluation_set)

    result = run_cli(
        "evaluation-set",
        "--evaluation-set",
        str(evaluation_set_path),
        "--json",
    )

    assert result.returncode == 1
    assert "out_of_scope: expected 7, found 6" in result.stderr


def test_cli_rejects_duplicate_evaluation_item_ids(tmp_path: Path) -> None:
    evaluation_set = load_evaluation_set()
    evaluation_set["items"][1]["id"] = evaluation_set["items"][0]["id"]
    evaluation_set_path = tmp_path / "evaluation-set.json"
    write_evaluation_set(evaluation_set_path, evaluation_set)

    result = run_cli(
        "evaluation-set",
        "--evaluation-set",
        str(evaluation_set_path),
        "--json",
    )

    assert result.returncode == 1
    assert "evaluation item IDs must be unique" in result.stderr


def test_cli_rejects_an_evaluation_item_without_an_expected_outcome(
    tmp_path: Path,
) -> None:
    evaluation_set = load_evaluation_set()
    del evaluation_set["items"][0]["expected"]
    evaluation_set_path = tmp_path / "evaluation-set.json"
    write_evaluation_set(evaluation_set_path, evaluation_set)

    result = run_cli(
        "evaluation-set",
        "--evaluation-set",
        str(evaluation_set_path),
        "--json",
    )

    assert result.returncode == 1
    assert "expected" in result.stderr


def test_cli_rejects_a_malformed_evaluation_source_locator(
    tmp_path: Path,
) -> None:
    evaluation_set = load_evaluation_set()
    evaluation_set["items"][0]["evidence"][0]["document_id"] = "not-a-frozen-source"
    evaluation_set_path = tmp_path / "evaluation-set.json"
    write_evaluation_set(evaluation_set_path, evaluation_set)

    result = run_cli(
        "evaluation-set",
        "--evaluation-set",
        str(evaluation_set_path),
        "--json",
    )

    assert result.returncode == 1
    assert "references unknown source not-a-frozen-source" in result.stderr


def test_cli_rejects_a_source_locator_outside_the_document(
    tmp_path: Path,
) -> None:
    evaluation_set = load_evaluation_set()
    evaluation_set["items"][0]["evidence"][0]["physical_page"] = 9999
    evaluation_set_path = tmp_path / "evaluation-set.json"
    write_evaluation_set(evaluation_set_path, evaluation_set)

    result = run_cli(
        "evaluation-set",
        "--evaluation-set",
        str(evaluation_set_path),
        "--json",
    )

    assert result.returncode == 1
    assert "references physical page 9999 outside source" in result.stderr


def test_cli_rejects_an_unreviewed_change_to_frozen_expected_outcomes(
    tmp_path: Path,
) -> None:
    evaluation_set_path = tmp_path / "evaluation-set.json"
    write_evaluation_set(evaluation_set_path, load_evaluation_set())
    freeze_path = tmp_path / "evaluation-freeze.json"

    freeze = run_cli(
        "evaluation-set",
        "--evaluation-set",
        str(evaluation_set_path),
        "--freeze",
        str(freeze_path),
        "--maintainer-review",
        "ticket-10-evaluation-review",
        "--json",
    )
    assert freeze.returncode == 0, freeze.stderr
    frozen_bytes = evaluation_set_path.read_bytes()

    evaluation_set = load_evaluation_set()
    evaluation_set["items"][0]["expected"]["specification"]["value"]["display"] = "3 N·m"
    write_evaluation_set(evaluation_set_path, evaluation_set)
    verify = run_cli(
        "evaluation-set",
        "--evaluation-set",
        str(evaluation_set_path),
        "--verify-freeze",
        str(freeze_path),
        "--json",
    )

    assert verify.returncode == 1
    assert "evaluation set differs from the frozen evaluation set" in verify.stderr
    assert evaluation_set_path.read_bytes() != frozen_bytes
