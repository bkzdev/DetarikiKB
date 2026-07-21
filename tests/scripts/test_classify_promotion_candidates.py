"""Synthetic CLI tests for promotion candidate classification."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "classify_promotion_candidates.py"
DEFAULT_TYPES = ["choice", "dialogue", "monologue", "narration", "unknown"]


def _write_json(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def _normalized(story_id: str, status: str) -> dict:
    return {
        "schemaVersion": "0.2",
        "documentType": "normalized_story",
        "storyId": story_id,
        "compatibilityReport": {"parserCompatibility": status},
        "episodes": [],
    }


def _report(
    story_reports: list[dict],
    *,
    public_profile: str = "default",
    included_types: list[str] | None = None,
) -> dict:
    global_counts: dict[str, int] = {}
    for story in story_reports:
        for evidence_type, count in story["entriesByEvidenceType"].items():
            global_counts[evidence_type] = global_counts.get(evidence_type, 0) + count
    return {
        "publicProfile": public_profile,
        "includedTypes": included_types
        if included_types is not None
        else DEFAULT_TYPES,
        "storyCount": len(story_reports),
        "entriesByEvidenceType": global_counts,
        "storyReports": story_reports,
    }


def _story_report(story_id: str, counts: dict[str, int]) -> dict:
    return {
        "storyId": story_id,
        "entryCount": sum(counts.values()),
        "entriesByEvidenceType": counts,
    }


def _run_cli(
    report_path: Path,
    normalized_input: Path,
    output_dir: Path,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--report",
            str(report_path),
            "--normalized-input",
            str(normalized_input),
            "--output",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )


def test_cli_writes_matrix_and_only_returns_promotion_candidates(tmp_path):
    report_path = _write_json(
        tmp_path / "generation" / "report.json",
        _report(
            [
                _story_report("TEST_STORY_B", {"dialogue": 69, "unknown": 31}),
                _story_report("TEST_STORY_A", {"dialogue": 90, "unknown": 10}),
                _story_report("TEST_STORY_C", {"dialogue": 100}),
            ]
        ),
    )
    normalized_dir = tmp_path / "normalized"
    _write_json(
        normalized_dir / "story_a_e01.json",
        _normalized("TEST_STORY_A", "compatible"),
    )
    _write_json(
        normalized_dir / "story_a_e02.json",
        _normalized("TEST_STORY_A", "warning"),
    )
    _write_json(
        normalized_dir / "nested" / "story_b.json",
        _normalized("TEST_STORY_B", "warning"),
    )
    _write_json(
        normalized_dir / "story_c.json",
        _normalized("TEST_STORY_C", "needs_update"),
    )
    _write_json(
        normalized_dir / "unrelated.json",
        _normalized("UNRELATED_STORY", "blocked"),
    )
    output_dir = tmp_path / "classification"

    result = _run_cli(report_path, normalized_dir, output_dir)

    assert result.returncode == 0, result.stderr
    output = json.loads(
        (output_dir / "classification_report.json").read_text(encoding="utf-8")
    )
    assert output["promotionCandidateStoryIds"] == ["TEST_STORY_A"]
    assert [story["storyId"] for story in output["stories"]] == [
        "TEST_STORY_A",
        "TEST_STORY_B",
        "TEST_STORY_C",
    ]
    by_id = {story["storyId"]: story for story in output["stories"]}
    assert by_id["TEST_STORY_A"]["parserCompatibility"] == "warning"
    assert by_id["TEST_STORY_A"]["classification"] == "promotion-candidate"
    assert by_id["TEST_STORY_B"]["classification"] == "parser-improvement-wait"
    assert by_id["TEST_STORY_C"]["classification"] == "excluded"

    markdown = (output_dir / "classification_report.md").read_text(encoding="utf-8")
    assert "| Story | total | unknown比率 | 意味あるentry比率" in markdown
    assert "10.00%" in markdown
    assert "promotion-candidate" in markdown
    assert "parser-improvement-wait" in markdown
    assert "excluded" in markdown


def test_cli_rejects_non_default_public_profile(tmp_path):
    story_reports = [_story_report("TEST_STORY_A", {"dialogue": 1})]
    report_path = _write_json(
        tmp_path / "report.json",
        _report(story_reports, public_profile="full"),
    )
    normalized_path = _write_json(
        tmp_path / "normalized.json", _normalized("TEST_STORY_A", "compatible")
    )

    result = _run_cli(report_path, normalized_path, tmp_path / "out")

    assert result.returncode == 2
    assert "--public-profile default" in result.stderr


def test_cli_rejects_custom_included_types_on_default_profile(tmp_path):
    story_reports = [_story_report("TEST_STORY_A", {"dialogue": 1})]
    report_path = _write_json(
        tmp_path / "report.json",
        _report(story_reports, included_types=["dialogue"]),
    )
    normalized_path = _write_json(
        tmp_path / "normalized.json", _normalized("TEST_STORY_A", "compatible")
    )

    result = _run_cli(report_path, normalized_path, tmp_path / "out")

    assert result.returncode == 2
    assert "includedTypes" in result.stderr


def test_cli_rejects_missing_required_normalized_story(tmp_path):
    report_path = _write_json(
        tmp_path / "report.json",
        _report([_story_report("TEST_STORY_A", {"dialogue": 1})]),
    )
    normalized_path = _write_json(
        tmp_path / "other.json", _normalized("OTHER_STORY", "compatible")
    )

    result = _run_cli(report_path, normalized_path, tmp_path / "out")

    assert result.returncode == 2
    assert "TEST_STORY_A" in result.stderr


def test_cli_rejects_inconsistent_story_entry_count(tmp_path):
    story_report = _story_report("TEST_STORY_A", {"dialogue": 2})
    story_report["entryCount"] = 1
    report_path = _write_json(tmp_path / "report.json", _report([story_report]))
    normalized_path = _write_json(
        tmp_path / "normalized.json", _normalized("TEST_STORY_A", "compatible")
    )

    result = _run_cli(report_path, normalized_path, tmp_path / "out")

    assert result.returncode == 2
    assert "entryCount" in result.stderr


def test_cli_rejects_invalid_parser_compatibility(tmp_path):
    report_path = _write_json(
        tmp_path / "report.json",
        _report([_story_report("TEST_STORY_A", {"dialogue": 1})]),
    )
    normalized_path = _write_json(
        tmp_path / "normalized.json", _normalized("TEST_STORY_A", "future_status")
    )

    result = _run_cli(report_path, normalized_path, tmp_path / "out")

    assert result.returncode == 2
    assert "parserCompatibility" in result.stderr


@pytest.mark.parametrize(
    ("story_id", "unknown_count", "parser_status", "band", "classification"),
    [
        ("TEST_EXACT_TEN", 10, "compatible", "acceptable", "promotion-candidate"),
        ("TEST_ABOVE_TEN", 11, "warning", "human-review-required", None),
        ("TEST_EXACT_THIRTY", 30, "compatible", "human-review-required", None),
        ("TEST_ABOVE_THIRTY", 31, "warning", "blocking", "parser-improvement-wait"),
    ],
)
def test_cli_unknown_ratio_bands_and_candidate_exclusion(
    tmp_path,
    story_id,
    unknown_count,
    parser_status,
    band,
    classification,
):
    report_path = _write_json(
        tmp_path / "report.json",
        _report(
            [
                _story_report(
                    story_id,
                    {"dialogue": 100 - unknown_count, "unknown": unknown_count},
                )
            ]
        ),
    )
    normalized_path = _write_json(
        tmp_path / "normalized.json", _normalized(story_id, parser_status)
    )
    output_dir = tmp_path / "out"

    result = _run_cli(report_path, normalized_path, output_dir)

    assert result.returncode == 0, result.stderr
    output = json.loads(
        (output_dir / "classification_report.json").read_text(encoding="utf-8")
    )
    story = output["stories"][0]
    assert story["unknownRatioBand"] == band
    assert story["classification"] == classification
    if band == "human-review-required":
        assert story["humanReviewRequired"] is True
        assert story["decisionReasonCodes"] == ["unknown-ratio-human-review-required"]
        assert output["promotionCandidateStoryIds"] == []
        assert "human-review-required" in (
            output_dir / "classification_report.md"
        ).read_text(encoding="utf-8")
    elif classification == "promotion-candidate":
        assert output["promotionCandidateStoryIds"] == [story_id]
    else:
        assert output["promotionCandidateStoryIds"] == []


def test_cli_hard_parser_blocker_excludes_human_review_band(tmp_path):
    story_id = "TEST_BLOCKED"
    report_path = _write_json(
        tmp_path / "report.json",
        _report([_story_report(story_id, {"dialogue": 89, "unknown": 11})]),
    )
    normalized_path = _write_json(
        tmp_path / "normalized.json", _normalized(story_id, "needs_update")
    )

    result = _run_cli(report_path, normalized_path, tmp_path / "out")

    assert result.returncode == 0, result.stderr
    output = json.loads(
        (tmp_path / "out" / "classification_report.json").read_text(encoding="utf-8")
    )
    story = output["stories"][0]
    assert story["classification"] == "excluded"
    assert story["humanReviewRequired"] is False
    assert story["decisionReasonCodes"] == ["parser-compatibility-needs_update"]
