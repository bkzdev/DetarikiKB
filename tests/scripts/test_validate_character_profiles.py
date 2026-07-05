"""
tests/scripts/test_validate_character_profiles.py
scripts/validate_character_profiles.py のCLIスモークテスト。

合成データのみを一時ファイルとして生成して使う。実データ・実データ由来
fixtureは一切使わない。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "validate_character_profiles.py"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "character_profiles.schema.json"


def _write_profiles(path: Path, profiles: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "schemaVersion": "0.1.0",
                "documentType": "character_profiles",
                "profiles": profiles,
            },
            f,
            allow_unicode=True,
        )


def _write_characters(path: Path, characters: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"schemaVersion": "0.1", "characters": characters}, f, allow_unicode=True
        )


def _run_cli(profiles_path: Path, characters_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--profiles",
            str(profiles_path),
            "--characters",
            str(characters_path),
            "--schema",
            str(SCHEMA_PATH),
        ],
        capture_output=True,
        text=True,
    )


def test_cli_empty_profiles_is_valid(tmp_path):
    profiles_path = tmp_path / "character_profiles.yaml"
    characters_path = tmp_path / "characters.yaml"
    _write_profiles(profiles_path, [])
    _write_characters(characters_path, [])

    result = _run_cli(profiles_path, characters_path)
    assert result.returncode == 0, result.stderr
    assert "0 " in result.stdout


def test_cli_valid_synthetic_profile_matching_confirmed_character(tmp_path):
    profiles_path = tmp_path / "character_profiles.yaml"
    characters_path = tmp_path / "characters.yaml"
    _write_profiles(
        profiles_path,
        [
            {
                "characterId": "CHAR_TEST_A",
                "displayName": "Test Character A",
                "status": "confirmed",
                "affiliation": ["Test Team"],
                "heightCm": 150,
            }
        ],
    )
    _write_characters(
        characters_path,
        [
            {
                "sourceCharacterId": "9001",
                "characterId": "CHAR_TEST_A",
                "displayName": "Test Character A",
                "aliases": [],
                "status": "confirmed",
                "notes": None,
            }
        ],
    )

    result = _run_cli(profiles_path, characters_path)
    assert result.returncode == 0, result.stderr


def test_cli_rejects_profile_for_name_only_character(tmp_path):
    profiles_path = tmp_path / "character_profiles.yaml"
    characters_path = tmp_path / "characters.yaml"
    _write_profiles(
        profiles_path,
        [
            {
                "characterId": "CHAR_TEST_B",
                "displayName": "Test Character B",
                "status": "draft",
            }
        ],
    )
    _write_characters(
        characters_path,
        [
            {
                "sourceCharacterId": "9002",
                "characterId": "CHAR_TEST_B",
                "displayName": "Test Character B",
                "aliases": [],
                "status": "name_only",
                "notes": None,
            }
        ],
    )

    result = _run_cli(profiles_path, characters_path)
    assert result.returncode == 2
    assert "confirmedではありません" in result.stderr


def test_cli_rejects_profile_for_unknown_character_id(tmp_path):
    profiles_path = tmp_path / "character_profiles.yaml"
    characters_path = tmp_path / "characters.yaml"
    _write_profiles(
        profiles_path,
        [
            {
                "characterId": "CHAR_TEST_UNKNOWN",
                "displayName": "Test Character Unknown",
                "status": "confirmed",
            }
        ],
    )
    _write_characters(characters_path, [])

    result = _run_cli(profiles_path, characters_path)
    assert result.returncode == 2
    assert "存在しません" in result.stderr


def test_cli_rejects_duplicate_character_id(tmp_path):
    profiles_path = tmp_path / "character_profiles.yaml"
    characters_path = tmp_path / "characters.yaml"
    entry = {
        "characterId": "CHAR_TEST_A",
        "displayName": "Test Character A",
        "status": "confirmed",
    }
    _write_profiles(profiles_path, [entry, dict(entry)])
    _write_characters(
        characters_path,
        [
            {
                "sourceCharacterId": "9001",
                "characterId": "CHAR_TEST_A",
                "displayName": "Test Character A",
                "aliases": [],
                "status": "confirmed",
                "notes": None,
            }
        ],
    )

    result = _run_cli(profiles_path, characters_path)
    assert result.returncode == 2
    assert "重複しています" in result.stderr


def test_cli_rejects_invalid_character_id_prefix(tmp_path):
    profiles_path = tmp_path / "character_profiles.yaml"
    characters_path = tmp_path / "characters.yaml"
    _write_profiles(
        profiles_path,
        [
            {
                "characterId": "NOT_CHAR_PREFIXED",
                "displayName": "Test",
                "status": "confirmed",
            }
        ],
    )
    _write_characters(characters_path, [])

    result = _run_cli(profiles_path, characters_path)
    assert result.returncode == 2


def test_cli_missing_profiles_file_returns_exit_code_1(tmp_path):
    characters_path = tmp_path / "characters.yaml"
    _write_characters(characters_path, [])
    result = _run_cli(tmp_path / "does_not_exist.yaml", characters_path)
    assert result.returncode == 1


def test_cli_allows_wiki_member_table_source_type(tmp_path):
    """character-profile-import-batch-001で使うsource.sourceType:
    wiki_member_tableがschema validationを通ることを確認する。"""
    profiles_path = tmp_path / "character_profiles.yaml"
    characters_path = tmp_path / "characters.yaml"
    _write_profiles(
        profiles_path,
        [
            {
                "characterId": "CHAR_TEST_A",
                "displayName": "Test Character A",
                "status": "confirmed",
                "reading": {"kana": "てすとえー", "romaji": None},
                "affiliation": ["Test Team"],
                "heightCm": 150,
                "birthday": {"month": 4, "day": 23, "display": "04/23"},
                "bloodType": "A",
                "cv": "Test Voice Actor",
                "profileHighlight": {"label": "好きなこと", "value": "テスト"},
                "selfIntroduction": None,
                "source": {
                    "sourceType": "wiki_member_table",
                    "label": "Test synthetic wiki member table",
                    "referenceId": None,
                    "notes": "Synthetic test entry only.",
                },
                "notes": "Synthetic test entry.",
            }
        ],
    )
    _write_characters(
        characters_path,
        [
            {
                "sourceCharacterId": "9001",
                "characterId": "CHAR_TEST_A",
                "displayName": "Test Character A",
                "aliases": [],
                "status": "confirmed",
                "notes": None,
            }
        ],
    )

    result = _run_cli(profiles_path, characters_path)
    assert result.returncode == 0, result.stderr


def test_cli_validates_multiple_confirmed_profiles(tmp_path):
    """character_profiles.yamlに複数のconfirmed済みprofileがあっても
    validateできることを確認する (batch 001で複数件投入するケースに対応)。"""
    profiles_path = tmp_path / "character_profiles.yaml"
    characters_path = tmp_path / "characters.yaml"
    _write_profiles(
        profiles_path,
        [
            {
                "characterId": "CHAR_TEST_A",
                "displayName": "Test Character A",
                "status": "confirmed",
                "selfIntroduction": None,
            },
            {
                "characterId": "CHAR_TEST_C",
                "displayName": "Test Character C",
                "status": "confirmed",
                "selfIntroduction": None,
            },
        ],
    )
    _write_characters(
        characters_path,
        [
            {
                "sourceCharacterId": "9001",
                "characterId": "CHAR_TEST_A",
                "displayName": "Test Character A",
                "aliases": [],
                "status": "confirmed",
                "notes": None,
            },
            {
                "sourceCharacterId": "9003",
                "characterId": "CHAR_TEST_C",
                "displayName": "Test Character C",
                "aliases": [],
                "status": "confirmed",
                "notes": None,
            },
        ],
    )

    result = _run_cli(profiles_path, characters_path)
    assert result.returncode == 0, result.stderr
    assert "confirmed=2" in result.stdout


def test_cli_does_not_contain_forbidden_content(tmp_path):
    """CLI標準出力・標準エラーに合成テスト以外の実データ本文が
    含まれないことを確認する (存在しないので混入しようがないが、
    念のため確認する)。"""
    profiles_path = tmp_path / "character_profiles.yaml"
    characters_path = tmp_path / "characters.yaml"
    _write_profiles(profiles_path, [])
    _write_characters(characters_path, [])
    result = _run_cli(profiles_path, characters_path)
    assert "textExcerpt" not in result.stdout
    assert "textExcerpt" not in result.stderr
