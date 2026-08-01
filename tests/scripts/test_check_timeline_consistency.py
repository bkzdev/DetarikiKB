"""scripts/check_timeline_consistency.py のCLI契約テスト。"""

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
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_timeline_consistency.py"
FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "extraction"
    / "minimal_episode_extraction.json"
)
REPORT_SCHEMA_PATH = (
    PROJECT_ROOT / "schemas" / "timeline_consistency_report.schema.json"
)
DRY_RUN_ROOT = PROJECT_ROOT / "workspace" / "dry_runs"


def _candidate(
    episode_id: str, relative_to: str, relation: str = "before"
) -> dict[str, Any]:
    evidence_id = f"{episode_id}_DLG0001"
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
        "evidenceIds": [evidence_id],
        "extractionRun": extraction_run,
        "kind": "relative_order",
        "scope": "episode",
        "relativeTo": relative_to,
        "relation": relation,
        "sourceTimelineId": None,
        "nameCandidates": [],
        "sceneRefs": [],
        "orderValue": None,
        "orderField": None,
        "markerType": None,
        "fields": {},
    }


def _document(
    episode_id: str,
    relative_to: str | None = None,
    relation: str = "before",
) -> dict[str, Any]:
    document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    document["episodeId"] = episode_id
    document["storyId"] = "TEST_STORY"
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
            "storyId": "TEST_STORY",
            "episodeId": episode_id,
            "sceneId": f"{episode_id}_SC001",
            "confidence": 0.9,
        }
    }
    document["timelineCandidates"] = (
        [_candidate(episode_id, relative_to, relation)]
        if relative_to is not None
        else []
    )
    return document


def _write_document(path: Path, document: dict[str, Any]) -> None:
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
    path = Path(tempfile.mkdtemp(prefix="timeline-consistency-test-", dir=DRY_RUN_ROOT))
    try:
        yield path
    finally:
        shutil.rmtree(path)


def test_cli_returns_zero_for_acyclic_inputs(tmp_path):
    _write_document(tmp_path / "ep01.json", _document("EP01", "EP02"))
    _write_document(tmp_path / "ep02.json", _document("EP02"))

    result = _run("--input", str(tmp_path), "--quiet")

    assert result.returncode == 0
    assert result.stderr == ""


def test_cli_writes_schema_valid_report_and_returns_one_for_cycle(tmp_path, report_dir):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write_document(input_dir / "ep01.json", _document("EP01", "EP02"))
    _write_document(input_dir / "ep02.json", _document("EP02", "EP01"))
    report_path = report_dir / "report.json"

    result = _run(
        "--input",
        str(input_dir),
        "--report-output",
        str(report_path),
    )

    assert result.returncode == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    schema = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert not list(Draft7Validator(schema).iter_errors(report))
    assert report["status"] == "needs_review"
    assert report["findingCount"] == 1
    assert report["findings"][0]["episodeIds"] == ["EP01", "EP02"]


def test_cli_excludes_invalid_document_and_returns_one(tmp_path, report_dir):
    valid_path = tmp_path / "valid.json"
    invalid_path = tmp_path / "invalid.json"
    _write_document(valid_path, _document("EP01"))
    invalid = copy.deepcopy(_document("EP02"))
    del invalid["documentType"]
    _write_document(invalid_path, invalid)
    report_path = report_dir / "report.json"

    result = _run(
        "--input",
        str(valid_path),
        str(invalid_path),
        "--report-output",
        str(report_path),
        "--quiet",
    )

    assert result.returncode == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "invalid_input"
    assert report["validInputs"] == 1
    assert report["invalidInputs"] == 1


def test_cli_report_preserves_ignored_external_target_and_passes(tmp_path, report_dir):
    input_path = tmp_path / "input.json"
    report_path = report_dir / "report.json"
    _write_document(input_path, _document("EP01", "EP99"))

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
    assert not list(Draft7Validator(schema).iter_errors(report))
    assert report["status"] == "passed"
    assert report["ignoredCandidates"][0]["reason"] == "target_not_loaded"


def test_cli_reports_order_inside_same_time_class_with_v02_schema(tmp_path, report_dir):
    first = _document("EP01", "EP02", "same_time")
    order_candidate = _candidate("EP01", "EP02", "before")
    order_candidate["id"] = "EP01_CAND_TL002"
    first["timelineCandidates"].append(order_candidate)
    _write_document(tmp_path / "ep01.json", first)
    _write_document(tmp_path / "ep02.json", _document("EP02"))
    report_path = report_dir / "report.json"

    result = _run(
        "--input",
        str(tmp_path),
        "--report-output",
        str(report_path),
        "--quiet",
    )

    assert result.returncode == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    schema = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert not list(Draft7Validator(schema).iter_errors(report))
    assert report["schemaVersion"] == "0.2"
    assert report["checkedSameTimeCandidateCount"] == 1
    assert report["sameTimeClassCount"] == 1
    assert report["findings"][0]["rule"] == (
        "timeline_relative_order_within_same_time_class"
    )


def test_report_schema_remains_compatible_with_v01_reports():
    report = {
        "schemaVersion": "0.1",
        "documentType": "timeline_consistency_report",
        "status": "passed",
        "inputFiles": 0,
        "resolvedInputFiles": 0,
        "validInputs": 0,
        "invalidInputs": 0,
        "skippedInputs": [],
        "inputResults": [],
        "timelineCandidateCount": 0,
        "relativeOrderCandidateCount": 0,
        "checkedCandidateCount": 0,
        "distinctEdgeCount": 0,
        "ignoredCandidateCount": 0,
        "ignoredCandidates": [],
        "findingCount": 0,
        "findings": [],
    }

    schema = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert not list(Draft7Validator(schema).iter_errors(report))


def test_v02_schema_requires_nonempty_same_time_conflict_provenance():
    finding = {
        "rule": "timeline_relative_order_within_same_time_class",
        "severity": "warning",
        "episodeIds": ["EP01", "EP02"],
        "candidateRefs": [
            {
                "sourcePath": "input.json",
                "episodeId": "EP01",
                "candidateId": "EP01_CAND_TL001",
                "evidenceIds": ["EP01_EVD001"],
            }
        ],
        "edges": [
            {
                "fromEpisodeId": "EP01",
                "toEpisodeId": "EP02",
                "sourceEpisodeId": "EP01",
                "relativeTo": "EP02",
                "relation": "before",
                "sourcePath": "input.json",
                "candidateId": "EP01_CAND_TL001",
                "evidenceIds": ["EP01_EVD001"],
            }
        ],
    }
    report = {
        "schemaVersion": "0.2",
        "documentType": "timeline_consistency_report",
        "status": "needs_review",
        "inputFiles": 1,
        "resolvedInputFiles": 1,
        "validInputs": 1,
        "invalidInputs": 0,
        "skippedInputs": [],
        "inputResults": [],
        "timelineCandidateCount": 1,
        "relativeOrderCandidateCount": 1,
        "checkedCandidateCount": 1,
        "distinctEdgeCount": 1,
        "checkedSameTimeCandidateCount": 1,
        "distinctSameTimeEdgeCount": 1,
        "sameTimeClassCount": 1,
        "distinctClassEdgeCount": 0,
        "ignoredCandidateCount": 0,
        "ignoredCandidates": [],
        "findingCount": 1,
        "findings": [finding],
    }
    schema = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)

    missing_errors = list(validator.iter_errors(report))
    assert any("sameTimeEdges" in error.message for error in missing_errors)
    assert any("sameTimeClassEpisodeIds" in error.message for error in missing_errors)

    finding["sameTimeEdges"] = []
    finding["sameTimeClassEpisodeIds"] = []
    empty_errors = list(validator.iter_errors(report))
    assert any("should be non-empty" in error.message for error in empty_errors)


def test_cli_returns_two_without_writing_report_when_no_input_resolves(
    tmp_path, report_dir
):
    report_path = report_dir / "report.json"
    result = _run(
        "--input",
        str(tmp_path / "missing"),
        "--report-output",
        str(report_path),
        "--quiet",
    )

    assert result.returncode == 2
    assert not report_path.exists()


def test_cli_refuses_existing_report_output(tmp_path, report_dir):
    input_path = tmp_path / "input.json"
    report_path = report_dir / "report.json"
    _write_document(input_path, _document("EP01"))
    report_path.write_text("reserved", encoding="utf-8")

    result = _run(
        "--input",
        str(input_path),
        "--report-output",
        str(report_path),
    )

    assert result.returncode == 2
    assert report_path.read_text(encoding="utf-8") == "reserved"


def test_cli_refuses_report_inside_input_directory(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write_document(input_dir / "ep01.json", _document("EP01"))

    result = _run(
        "--input",
        str(input_dir),
        "--report-output",
        str(input_dir / "report.json"),
    )

    assert result.returncode == 2
    assert not (input_dir / "report.json").exists()


def test_cli_refuses_report_outside_workspace_dry_runs(tmp_path):
    input_path = tmp_path / "input.json"
    report_path = tmp_path / "report.json"
    _write_document(input_path, _document("EP01"))

    result = _run(
        "--input",
        str(input_path),
        "--report-output",
        str(report_path),
    )

    assert result.returncode == 2
    assert not report_path.exists()
