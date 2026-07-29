"""merge report独立JSON artifactのCLI出力を検証する。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
MERGE_SCRIPT = PROJECT_ROOT / "scripts" / "merge_extractions.py"
EXTRACTION_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "extraction"
MINIMAL_FIXTURE = EXTRACTION_FIXTURES_DIR / "minimal_episode_extraction.json"
SCHEMA_INVALID_FIXTURE = EXTRACTION_FIXTURES_DIR / "invalid_missing_evidence.json"


def _run_merge(
    input_path: Path,
    output_dir: Path,
    report_output: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(MERGE_SCRIPT),
        "--input",
        str(input_path),
        "--output",
        str(output_dir),
        "--quiet",
    ]
    if report_output is not None:
        command.extend(["--report-output", str(report_output)])
    return subprocess.run(command, capture_output=True, text=True)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_cli_writes_final_report_to_explicit_nested_path(tmp_path):
    output_dir = tmp_path / "merged"
    report_output = tmp_path / "reports" / "run_001" / "merge_report.json"

    result = _run_merge(MINIMAL_FIXTURE, output_dir, report_output)

    assert result.returncode == 0, result.stderr
    collection = _load_json(output_dir / "merged_knowledge_collection.json")
    assert _load_json(report_output) == collection["report"]


def test_cli_preserves_existing_behavior_when_report_output_is_omitted(tmp_path):
    output_dir = tmp_path / "merged"

    result = _run_merge(MINIMAL_FIXTURE, output_dir)

    assert result.returncode == 0, result.stderr
    assert (output_dir / "merged_knowledge_collection.json").is_file()
    assert not (output_dir / "merge_report.json").exists()


def test_cli_writes_report_for_invalid_input_before_returning_exit_one(tmp_path):
    output_dir = tmp_path / "merged"
    report_output = tmp_path / "reports" / "merge_report.json"

    result = _run_merge(SCHEMA_INVALID_FIXTURE, output_dir, report_output)

    assert result.returncode == 1
    collection = _load_json(output_dir / "merged_knowledge_collection.json")
    report = _load_json(report_output)
    assert report == collection["report"]
    assert report["invalidInputs"] == 1
    assert report["errors"]


def test_cli_rejects_report_path_that_would_overwrite_collection(tmp_path):
    output_dir = tmp_path / "merged"
    collection_path = output_dir / "merged_knowledge_collection.json"

    result = _run_merge(MINIMAL_FIXTURE, output_dir, collection_path)

    assert result.returncode == 2
    assert "--report-output" in result.stderr
    assert not collection_path.exists()


def test_cli_rejects_report_path_that_is_the_collection_output_directory(tmp_path):
    output_dir = tmp_path / "merged"

    result = _run_merge(MINIMAL_FIXTURE, output_dir, output_dir)

    assert result.returncode == 2
    assert "--report-output" in result.stderr
    assert not output_dir.exists()


def test_cli_rejects_existing_directory_as_report_file_before_writing_collection(
    tmp_path,
):
    output_dir = tmp_path / "merged"
    report_output = tmp_path / "reports"
    report_output.mkdir()

    result = _run_merge(MINIMAL_FIXTURE, output_dir, report_output)

    assert result.returncode == 2
    assert "ファイルパス" in result.stderr
    assert not (output_dir / "merged_knowledge_collection.json").exists()


def test_cli_does_not_write_report_when_no_input_file_can_be_resolved(tmp_path):
    output_dir = tmp_path / "merged"
    report_output = tmp_path / "reports" / "merge_report.json"

    result = _run_merge(
        tmp_path / "does_not_exist.json",
        output_dir,
        report_output,
    )

    assert result.returncode == 2
    assert not report_output.exists()
    assert not (output_dir / "merged_knowledge_collection.json").exists()
