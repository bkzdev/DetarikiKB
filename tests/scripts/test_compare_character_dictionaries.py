"""
tests/scripts/test_compare_character_dictionaries.py
scripts/compare_character_dictionaries.py のユニット・CLIスモークテスト。

すべて合成データ (CHAR_TEST_* 等) のみを使う。実データ由来の
sourceCharacterId・displayName・fixtureは一切含まない。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from agents.parser.character_dictionary import (
    STATUS_CONFIRMED,
    STATUS_NAME_ONLY,
    CharacterDictionaryEntry,
    load_character_dictionary,
)
from scripts.compare_character_dictionaries import (
    compute_diff,
    format_new_entry_yaml,
    load_reference_json,
    write_new_entries,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "compare_character_dictionaries.py"


def _write_reference_json(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "characters_reference.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def _write_dictionary_yaml(tmp_path: Path, characters: list[dict]) -> Path:
    """実際のknowledge/dictionaries/characters.yamlと同じ構造
    (schemaVersionが先、charactersリストがファイル末尾) で書き出す。
    sort_keys=Falseを指定しないとPyYAMLがキーをアルファベット順に
    並べ替え、charactersがファイル末尾に来なくなる
    (write_new_entriesは末尾追記のみを行うため、charactersが末尾に
    あることを前提とする)。"""
    path = tmp_path / "characters.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"schemaVersion": "0.1", "characters": characters},
            f,
            sort_keys=False,
        )
    return path


# ----------------------------------------------------------------
# load_reference_json
# ----------------------------------------------------------------


def test_load_reference_json_flat_strings(tmp_path):
    path = _write_reference_json(tmp_path, {"9001": "Test Character A"})
    result = load_reference_json(path)
    assert result == {"9001": "Test Character A"}


def test_load_reference_json_dict_values_with_name_key(tmp_path):
    path = _write_reference_json(
        tmp_path, {"9001": {"name": "Test Character A", "id": "irrelevant"}}
    )
    result = load_reference_json(path)
    assert result == {"9001": "Test Character A"}


def test_load_reference_json_missing_file_returns_empty(tmp_path):
    assert load_reference_json(tmp_path / "does_not_exist.json") == {}


# ----------------------------------------------------------------
# compute_diff
# ----------------------------------------------------------------


@pytest.fixture
def sample_yaml_entries():
    return [
        CharacterDictionaryEntry(
            source_character_id="9001",
            display_name="Test Character A",
            character_id="CHAR_TEST_A",
            status=STATUS_CONFIRMED,
        ),
        CharacterDictionaryEntry(
            source_character_id="9002",
            display_name="Test Character B",
            status=STATUS_NAME_ONLY,
        ),
        CharacterDictionaryEntry(
            source_character_id="9003",
            display_name="Test Character C (YAML only)",
            status=STATUS_NAME_ONLY,
        ),
    ]


def test_compute_diff_identifies_missing_from_yaml(sample_yaml_entries):
    reference = {
        "9001": "Test Character A",
        "9002": "Test Character B",
        "9999": "Brand New Character",
    }
    diff = compute_diff(reference, sample_yaml_entries)

    assert diff.json_total == 3
    assert diff.yaml_total == 3
    assert diff.matching_count == 2
    assert diff.missing_from_yaml == {"9999": "Brand New Character"}
    assert diff.yaml_only_ids == ["9003"]
    assert diff.display_name_conflicts == []
    assert diff.confirmed_count == 1
    assert diff.name_only_count == 2


def test_compute_diff_detects_display_name_conflict(sample_yaml_entries):
    reference = {"9002": "A Totally Different Name"}
    diff = compute_diff(reference, sample_yaml_entries)

    assert diff.display_name_conflicts == [
        ("9002", "A Totally Different Name", "Test Character B")
    ]
    # 名前が違っても自動上書きはしない (compute_diffは検出するだけ)
    assert diff.missing_from_yaml == {}


def test_compute_diff_no_conflict_when_names_match(sample_yaml_entries):
    reference = {"9001": "Test Character A"}
    diff = compute_diff(reference, sample_yaml_entries)
    assert diff.display_name_conflicts == []


# ----------------------------------------------------------------
# format_new_entry_yaml / write_new_entries
# ----------------------------------------------------------------


def test_format_new_entry_yaml_is_name_only_never_confirmed():
    text = format_new_entry_yaml("9999", "Brand New Character")
    assert 'sourceCharacterId: "9999"' in text
    assert "characterId: null" in text
    assert 'displayName: "Brand New Character"' in text
    assert 'status: "name_only"' in text
    assert "aliases: []" in text
    assert "requires human confirmation" in text
    # confirmedという文字列がstatus値として出てこないこと
    assert 'status: "confirmed"' not in text


def test_write_new_entries_appends_without_touching_existing_lines(tmp_path):
    dictionary_path = _write_dictionary_yaml(
        tmp_path,
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
    original_content = dictionary_path.read_text(encoding="utf-8")

    write_new_entries(dictionary_path, {"9999": "Brand New Character"})

    new_content = dictionary_path.read_text(encoding="utf-8")
    assert new_content.startswith(original_content)
    assert 'sourceCharacterId: "9999"' in new_content

    entries = load_character_dictionary(dictionary_path)
    assert len(entries) == 2
    existing = next(e for e in entries if e.source_character_id == "9001")
    assert existing.status == STATUS_CONFIRMED
    assert existing.character_id == "CHAR_TEST_A"

    added = next(e for e in entries if e.source_character_id == "9999")
    assert added.status == STATUS_NAME_ONLY
    assert added.character_id is None
    assert added.display_name == "Brand New Character"
    assert "requires human confirmation" in (added.notes or "")


def test_write_new_entries_noop_when_nothing_missing(tmp_path):
    dictionary_path = _write_dictionary_yaml(
        tmp_path,
        [
            {
                "sourceCharacterId": "9001",
                "characterId": None,
                "displayName": "Test Character A",
                "aliases": [],
                "status": "name_only",
                "notes": None,
            }
        ],
    )
    original_content = dictionary_path.read_text(encoding="utf-8")
    write_new_entries(dictionary_path, {})
    assert dictionary_path.read_text(encoding="utf-8") == original_content


# ----------------------------------------------------------------
# CLI smoke tests
# ----------------------------------------------------------------


def test_cli_dry_run_does_not_modify_dictionary(tmp_path):
    reference_path = _write_reference_json(
        tmp_path,
        {"9001": "Test Character A", "9999": "Brand New Character"},
    )
    dictionary_path = _write_dictionary_yaml(
        tmp_path,
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
    original_content = dictionary_path.read_text(encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--reference-json",
            str(reference_path),
            "--dictionary",
            str(dictionary_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "9999" in result.stdout
    assert dictionary_path.read_text(encoding="utf-8") == original_content


def test_cli_write_adds_name_only_entries_only(tmp_path):
    reference_path = _write_reference_json(
        tmp_path,
        {"9001": "Test Character A", "9999": "Brand New Character"},
    )
    dictionary_path = _write_dictionary_yaml(
        tmp_path,
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

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--reference-json",
            str(reference_path),
            "--dictionary",
            str(dictionary_path),
            "--write",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    entries = load_character_dictionary(dictionary_path)
    by_id = {e.source_character_id: e for e in entries}

    assert by_id["9001"].status == STATUS_CONFIRMED
    assert by_id["9001"].character_id == "CHAR_TEST_A"

    assert by_id["9999"].status == STATUS_NAME_ONLY
    assert by_id["9999"].character_id is None
    assert by_id["9999"].display_name == "Brand New Character"


def test_cli_reports_display_name_conflict_as_warning(tmp_path):
    reference_path = _write_reference_json(tmp_path, {"9001": "Different Name"})
    dictionary_path = _write_dictionary_yaml(
        tmp_path,
        [
            {
                "sourceCharacterId": "9001",
                "characterId": None,
                "displayName": "Original Name",
                "aliases": [],
                "status": "name_only",
                "notes": None,
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--reference-json",
            str(reference_path),
            "--dictionary",
            str(dictionary_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "displayNameが異なるエントリ" in result.stderr
    assert "9001" in result.stderr

    # displayNameは自動で書き換えられていない
    entries = load_character_dictionary(dictionary_path)
    assert entries[0].display_name == "Original Name"


def test_cli_invalid_dictionary_returns_exit_1(tmp_path):
    reference_path = _write_reference_json(tmp_path, {"9001": "Test Character A"})
    invalid_dictionary_path = tmp_path / "invalid_characters.yaml"
    with open(invalid_dictionary_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "schemaVersion": "0.1",
                "characters": [
                    {
                        "sourceCharacterId": "9001",
                        "characterId": "not-a-valid-id",
                        "displayName": "Bad Entry",
                        "aliases": [],
                        "status": "confirmed",
                    }
                ],
            },
            f,
        )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--reference-json",
            str(reference_path),
            "--dictionary",
            str(invalid_dictionary_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1


def test_cli_missing_reference_json_returns_exit_1(tmp_path):
    dictionary_path = _write_dictionary_yaml(
        tmp_path,
        [
            {
                "sourceCharacterId": "9001",
                "characterId": None,
                "displayName": "Test Character A",
                "aliases": [],
                "status": "name_only",
                "notes": None,
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--reference-json",
            str(tmp_path / "does_not_exist.json"),
            "--dictionary",
            str(dictionary_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
