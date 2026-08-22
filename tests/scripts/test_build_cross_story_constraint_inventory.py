"""scripts/build_cross_story_constraint_inventory.py のCLI契約テスト。"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_cross_story_constraint_inventory.py"
FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "extraction"
    / "minimal_episode_extraction.json"
)
REPORT_SCHEMA_PATH = (
    PROJECT_ROOT / "schemas" / "cross_story_constraint_inventory.schema.json"
)
DRY_RUN_ROOT = PROJECT_ROOT / "workspace" / "dry_runs"


def _candidate(episode_id: str, relative_to: str) -> dict[str, Any]:
    extraction_run = {
        "extractionVersion": "0.1.0",
        "extractionMethod": "rule_based",
        "modelProvider": None,
        "modelName": None,
        "promptVersion": None,
        "extractedAt": None,
        "parserCompatibilityAtExtraction": "compatible",
    }
    return {
        "id": f"{episode_id}_CAND_TL001",
        "type": "timeline_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": [f"{episode_id}_DLG0001"],
        "extractionRun": extraction_run,
        "kind": "relative_order",
        "scope": "episode",
        "relativeTo": relative_to,
        "relation": "before",
        "sourceTimelineId": None,
        "nameCandidates": [],
        "sceneRefs": [],
        "orderValue": None,
        "orderField": None,
        "markerType": None,
        "fields": {},
    }


def _document(
    story_id: str,
    episode_id: str,
    relative_to: str | None = None,
    *,
    category: str = "EVT",
) -> dict[str, Any]:
    document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    document["episodeId"] = episode_id
    document["storyId"] = story_id
    document["storyCategory"] = category
    document["characters"] = []
    document["extractionRun"] = {
        "extractionVersion": "0.1.0",
        "extractionMethod": "rule_based",
        "modelProvider": None,
        "modelName": None,
        "promptVersion": None,
        "extractedAt": None,
        "parserCompatibilityAtExtraction": "compatible",
    }
    evidence_id = f"{episode_id}_DLG0001"
    document["evidenceIndex"] = {
        evidence_id: {
            "sourceId": evidence_id,
            "storyId": story_id,
            "episodeId": episode_id,
            "sceneId": f"{episode_id}_SC001",
            "confidence": 0.9,
        }
    }
    document["timelineCandidates"] = (
        [_candidate(episode_id, relative_to)] if relative_to is not None else []
    )
    return document


def _write_document(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


@pytest.fixture
def report_dir() -> Path:
    DRY_RUN_ROOT.mkdir(parents=True, exist_ok=True)
    path = Path(
        tempfile.mkdtemp(prefix="cross-story-inventory-test-", dir=DRY_RUN_ROOT)
    )
    try:
        yield path
    finally:
        shutil.rmtree(path)


def test_cli_writes_schema_valid_nonjudgmental_inventory(tmp_path, report_dir):
    input_dir = tmp_path / "input"
    _write_document(
        input_dir / "source.json",
        _document("EVT_STORY_A", "EVT_STORY_A_E01", "EVT_STORY_B_E01"),
    )
    _write_document(
        input_dir / "target.json",
        _document("EVT_STORY_B", "EVT_STORY_B_E01"),
    )
    report_path = report_dir / "report.json"

    result = _run(
        "--input", str(input_dir), "--report-output", str(report_path), "--quiet"
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    report = json.loads(report_path.read_text(encoding="utf-8"))
    schema = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert not list(Draft7Validator(schema).iter_errors(report))
    assert report["schemaVersion"] == "0.1"
    assert report["status"] == "passed"
    assert report["scopeStoryCategory"] == "EVT"
    assert report["crossStoryCandidateObservationCount"] == 1
    assert report["distinctStoryPairCount"] == 1
    assert "canonicalOrder" not in json.dumps(report)
    assert "reviewStatus" not in json.dumps(report)


def test_cli_accepts_recursive_directory_and_glob_inputs(tmp_path):
    nested = tmp_path / "nested"
    _write_document(
        nested / "one" / "source.json",
        _document("EVT_STORY_A", "EVT_STORY_A_E01", "EVT_STORY_B_E01"),
    )
    _write_document(
        nested / "two" / "target.json",
        _document("EVT_STORY_B", "EVT_STORY_B_E01"),
    )

    recursive = _run("--input", str(nested), "--recursive", "--quiet")
    globbed = _run("--input", str(nested / "**" / "*.json"), "--recursive", "--quiet")

    assert recursive.returncode == 0
    assert globbed.returncode == 0


def test_cli_report_is_independent_of_input_argument_order(tmp_path, report_dir):
    source_path = tmp_path / "source.json"
    target_path = tmp_path / "target.json"
    _write_document(
        source_path,
        _document("EVT_STORY_A", "EVT_STORY_A_E01", "EVT_STORY_B_E01"),
    )
    _write_document(target_path, _document("EVT_STORY_B", "EVT_STORY_B_E01"))
    first_path = report_dir / "first.json"
    second_path = report_dir / "second.json"

    first = _run(
        "--input",
        str(source_path),
        str(target_path),
        "--report-output",
        str(first_path),
        "--quiet",
    )
    second = _run(
        "--input",
        str(target_path),
        str(source_path),
        "--report-output",
        str(second_path),
        "--quiet",
    )

    assert first.returncode == 0
    assert second.returncode == 0
    assert first_path.read_bytes() == second_path.read_bytes()


def test_cli_deduplicates_the_same_resolved_files_across_input_forms(
    tmp_path, report_dir
):
    input_dir = tmp_path / "input"
    source_path = input_dir / "source.json"
    target_path = input_dir / "target.json"
    _write_document(
        source_path,
        _document("EVT_STORY_A", "EVT_STORY_A_E01", "EVT_STORY_B_E01"),
    )
    _write_document(target_path, _document("EVT_STORY_B", "EVT_STORY_B_E01"))
    report_path = report_dir / "deduplicated.json"

    result = _run(
        "--input",
        str(input_dir),
        str(source_path),
        str(input_dir / "*.json"),
        "--report-output",
        str(report_path),
        "--quiet",
    )

    assert result.returncode == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["inputFiles"] == 3
    assert report["resolvedInputFiles"] == 2
    assert report["crossStoryCandidateObservationCount"] == 1
    assert report["storyPairs"][0]["candidateObservationCount"] == 1


def test_cli_marks_invalid_and_skipped_inputs_without_dropping_valid_input(
    tmp_path, report_dir
):
    valid_path = tmp_path / "valid.json"
    invalid_path = tmp_path / "invalid.json"
    missing_path = tmp_path / "missing.json"
    _write_document(valid_path, _document("EVT_STORY_A", "EVT_STORY_A_E01"))
    invalid = copy.deepcopy(_document("EVT_STORY_B", "EVT_STORY_B_E01"))
    del invalid["documentType"]
    _write_document(invalid_path, invalid)
    report_path = report_dir / "invalid-input.json"

    result = _run(
        "--input",
        str(valid_path),
        str(invalid_path),
        str(missing_path),
        "--report-output",
        str(report_path),
        "--quiet",
    )

    assert result.returncode == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid_input"
    assert report["validInputs"] == 1
    assert report["invalidInputs"] == 1
    assert len(report["skippedInputs"]) == 1
    assert {item["status"] for item in report["inputResults"]} == {
        "valid",
        "invalid",
        "skipped",
    }


def test_cli_returns_two_when_no_input_resolves(tmp_path, report_dir):
    report_path = report_dir / "unwritten.json"

    result = _run(
        "--input",
        str(tmp_path / "missing"),
        "--report-output",
        str(report_path),
        "--quiet",
    )

    assert result.returncode == 2
    assert not report_path.exists()


def test_cli_reports_only_anonymous_aggregates_to_stdout(tmp_path, report_dir):
    internal_marker = "EVT_PRIVATE_MARKER_E01"
    input_path = tmp_path / "private-source-name.json"
    _write_document(
        input_path,
        _document("EVT_PRIVATE_STORY", internal_marker, "EVT_NOT_LOADED_E01"),
    )
    report_path = report_dir / "private-report-name.json"

    result = _run("--input", str(input_path), "--report-output", str(report_path))

    assert result.returncode == 0
    combined = result.stdout + result.stderr
    assert "status=passed" in result.stdout
    assert "report_written=true" in result.stdout
    assert internal_marker not in combined
    assert str(input_path) not in combined
    assert str(report_path) not in combined


@pytest.mark.parametrize("existing", [False, True])
def test_cli_refuses_output_outside_dry_run_or_existing_file(
    tmp_path, report_dir, existing
):
    input_path = tmp_path / "input.json"
    _write_document(input_path, _document("EVT_STORY_A", "EVT_STORY_A_E01"))
    report_path = report_dir / "report.json" if existing else tmp_path / "report.json"
    if existing:
        report_path.write_text("reserved", encoding="utf-8")

    result = _run("--input", str(input_path), "--report-output", str(report_path))

    assert result.returncode == 2
    if existing:
        assert report_path.read_text(encoding="utf-8") == "reserved"
    else:
        assert not report_path.exists()
    assert str(report_path) not in result.stderr


def test_cli_refuses_report_inside_input_directory(tmp_path):
    input_dir = tmp_path / "input"
    input_path = input_dir / "input.json"
    report_path = input_dir / "report.json"
    _write_document(input_path, _document("EVT_STORY_A", "EVT_STORY_A_E01"))

    result = _run("--input", str(input_dir), "--report-output", str(report_path))

    assert result.returncode == 2
    assert not report_path.exists()


def test_report_schema_rejects_canonical_or_unknown_fields(tmp_path, report_dir):
    input_path = tmp_path / "input.json"
    report_path = report_dir / "report.json"
    _write_document(input_path, _document("EVT_STORY_A", "EVT_STORY_A_E01"))
    result = _run(
        "--input",
        str(input_path),
        "--report-output",
        str(report_path),
        "--quiet",
    )
    assert result.returncode == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    schema = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

    report["canonicalOrder"] = 1
    errors = list(Draft7Validator(schema).iter_errors(report))

    assert any("Additional properties" in error.message for error in errors)
