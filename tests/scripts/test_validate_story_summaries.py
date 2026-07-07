"""
tests/scripts/test_validate_story_summaries.py
scripts/validate_story_summaries.py のCLIスモークテスト。

合成データのみを一時ファイルとして生成して使う。実データ・実データ由来
fixtureは一切使わない。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "validate_story_summaries.py"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "story_summary.schema.json"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "story_summaries"


def _minimal_document(**overrides) -> dict:
    data = {
        "schemaVersion": "0.1.0",
        "documentType": "story_summary",
        "storyId": "EVT_TEST_A",
        "publicStoryId": None,
        "language": "ja",
        "generationStatus": "generated",
        "storySummary": None,
        "episodeSummaries": [],
        "source": {
            "sourceType": "manual",
            "model": None,
            "promptVersion": None,
            "generatedAt": None,
            "inputRefs": [],
        },
        "review": {
            "status": "reviewed",
            "reviewer": None,
            "reviewedAt": None,
            "notes": None,
        },
        "notes": None,
    }
    data.update(overrides)
    return data


def _write(path: Path, data: dict) -> Path:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)
    return path


def _run_cli(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *extra_args],
        capture_output=True,
        text=True,
    )


def test_cli_valid_fixture_directory_exits_zero():
    result = _run_cli("--input", str(FIXTURES_DIR))
    assert result.returncode == 0, result.stderr
    assert "3 " in result.stdout


def test_cli_single_valid_file_exits_zero():
    result = _run_cli("--input", str(FIXTURES_DIR / "valid_story_summary.yaml"))
    assert result.returncode == 0, result.stderr


def test_cli_missing_input_path_exits_two(tmp_path):
    result = _run_cli("--input", str(tmp_path / "does_not_exist"))
    assert result.returncode == 2


def test_cli_missing_schema_path_exits_two(tmp_path):
    result = _run_cli(
        "--input",
        str(FIXTURES_DIR / "valid_story_summary.yaml"),
        "--schema",
        str(tmp_path / "does_not_exist.schema.json"),
    )
    assert result.returncode == 2


def test_cli_schema_violation_exits_one(tmp_path):
    path = _write(
        tmp_path / "bad.yaml",
        _minimal_document(storyId="not_valid_lowercase_id"),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1
    assert "schema" in result.stderr.lower() or "schema" in result.stderr


def test_cli_raw_text_forbidden_string_exits_one(tmp_path):
    path = _write(
        tmp_path / "bad_text.yaml",
        _minimal_document(
            storySummary={
                "text": "この文章には $num が混入しています。",
                "confidence": None,
                "evidenceRefs": [],
            }
        ),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1
    assert "禁止文字列" in result.stderr


def test_cli_duplicate_story_id_across_files_exits_one(tmp_path):
    _write(tmp_path / "a.yaml", _minimal_document(storyId="EVT_TEST_DUP"))
    _write(tmp_path / "b.yaml", _minimal_document(storyId="EVT_TEST_DUP"))
    result = _run_cli("--input", str(tmp_path))
    assert result.returncode == 1
    assert "重複しています" in result.stderr


def test_cli_duplicate_episode_id_within_story_exits_one(tmp_path):
    path = _write(
        tmp_path / "dup_episode.yaml",
        _minimal_document(
            episodeSummaries=[
                {
                    "episodeId": "EVT_TEST_A_E01",
                    "publicEpisodeId": None,
                    "episodeNumber": 1,
                    "text": "1件目",
                    "confidence": None,
                    "evidenceRefs": [],
                },
                {
                    "episodeId": "EVT_TEST_A_E01",
                    "publicEpisodeId": None,
                    "episodeNumber": 1,
                    "text": "2件目",
                    "confidence": None,
                    "evidenceRefs": [],
                },
            ]
        ),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1
    assert "重複しています" in result.stderr


def test_cli_require_reviewed_rejects_unreviewed_status(tmp_path):
    path = _write(
        tmp_path / "unreviewed.yaml",
        _minimal_document(
            review={
                "status": "unreviewed",
                "reviewer": None,
                "reviewedAt": None,
                "notes": None,
            }
        ),
    )
    result = _run_cli("--input", str(path), "--require-reviewed")
    assert result.returncode == 1
    assert "reviewed/approved" in result.stderr


def test_cli_require_reviewed_accepts_approved_status(tmp_path):
    path = _write(
        tmp_path / "approved.yaml",
        _minimal_document(
            review={
                "status": "approved",
                "reviewer": "x",
                "reviewedAt": "2026-07-08",
                "notes": None,
            }
        ),
    )
    result = _run_cli("--input", str(path), "--require-reviewed")
    assert result.returncode == 0, result.stderr


def test_cli_without_require_reviewed_allows_unreviewed_status(tmp_path):
    path = _write(
        tmp_path / "unreviewed.yaml",
        _minimal_document(
            review={
                "status": "unreviewed",
                "reviewer": None,
                "reviewedAt": None,
                "notes": None,
            }
        ),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 0, result.stderr


def test_cli_does_not_contain_forbidden_content(tmp_path):
    path = _write(tmp_path / "clean.yaml", _minimal_document())
    result = _run_cli("--input", str(path))
    assert ".dec" not in result.stdout
    assert "@ChTalk" not in result.stdout
