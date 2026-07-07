"""
tests/scripts/test_validate_evidence_index.py
scripts/validate_evidence_index.py のCLIスモークテスト。

合成データのみを一時ファイルとして生成して使う。実データ・実データ由来
fixtureは一切使わない。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "validate_evidence_index.py"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "evidence_index.schema.json"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "evidence_index"


def _minimal_entry(**overrides) -> dict:
    entry = {
        "evidenceId": "EVT_TEST_A_E01_DLG0001",
        "evidenceType": "dialogue",
        "storyId": "EVT_TEST_A",
        "publicStoryId": None,
        "episodeId": "EVT_TEST_A_E01",
        "publicEpisodeId": None,
        "sceneId": None,
        "blockId": None,
        "speaker": None,
        "relatedEntities": [],
        "referencedBy": None,
        "visibility": {"public": True, "rawTextIncluded": False},
        "notes": None,
    }
    entry.update(overrides)
    return entry


def _minimal_document(**overrides) -> dict:
    data = {
        "evidenceIndexVersion": 1,
        "generatedFrom": None,
        "entries": [_minimal_entry()],
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
    result = _run_cli("--input", str(FIXTURES_DIR / "valid_evidence_index.yaml"))
    assert result.returncode == 0, result.stderr


def test_cli_missing_input_path_exits_two(tmp_path):
    result = _run_cli("--input", str(tmp_path / "does_not_exist"))
    assert result.returncode == 2


def test_cli_missing_schema_path_exits_two(tmp_path):
    result = _run_cli(
        "--input",
        str(FIXTURES_DIR / "valid_evidence_index.yaml"),
        "--schema",
        str(tmp_path / "does_not_exist.schema.json"),
    )
    assert result.returncode == 2


def test_cli_schema_violation_exits_one(tmp_path):
    path = _write(
        tmp_path / "bad.yaml",
        _minimal_document(entries=[_minimal_entry(evidenceType="@ChTalk")]),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1


def test_cli_raw_text_included_true_exits_one(tmp_path):
    path = _write(
        tmp_path / "bad_visibility.yaml",
        _minimal_document(
            entries=[
                _minimal_entry(visibility={"public": True, "rawTextIncluded": True})
            ]
        ),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1


def test_cli_raw_command_in_notes_exits_one(tmp_path):
    path = _write(
        tmp_path / "bad_text.yaml",
        _minimal_document(
            entries=[_minimal_entry(notes="この文章には @ChTalk が混入しています。")]
        ),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1
    assert "禁止文字列" in result.stderr


def test_cli_duplicate_evidence_id_exits_one(tmp_path):
    path = _write(
        tmp_path / "dup.yaml",
        _minimal_document(
            entries=[
                _minimal_entry(evidenceId="EVT_TEST_A_E01_DLG0001"),
                _minimal_entry(evidenceId="EVT_TEST_A_E01_DLG0001"),
            ]
        ),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1
    assert "重複しています" in result.stderr


def test_cli_invalid_evidence_type_exits_one(tmp_path):
    path = _write(
        tmp_path / "bad_type.yaml",
        _minimal_document(entries=[_minimal_entry(evidenceType="not_a_real_type")]),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1


def test_cli_does_not_contain_forbidden_content(tmp_path):
    path = _write(tmp_path / "clean.yaml", _minimal_document())
    result = _run_cli("--input", str(path))
    assert ".dec" not in result.stdout
    assert "@ChTalk" not in result.stdout
