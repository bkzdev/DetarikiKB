"""
tests/scripts/test_build_story_manifest_candidates.py
scripts/build_story_manifest_candidates.py のCLIスモークテスト。

コアロジックのユニットテストは
tests/parser/test_story_manifest_candidates.py を参照
(agents/parser/story_manifest_candidates.pyを直接テストする)。

すべて合成データのみ (tmp_path配下に空の.decファイルを作成) を使う。
実DECファイル・実イベント名・実データ由来fixtureは一切使わない。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_story_manifest_candidates.py"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "story_manifest.schema.json"

SOURCE_KEY = "250626_synthetic_dancer"


def _make_export_dir(raw_root: Path, source_key: str = SOURCE_KEY) -> Path:
    export_dir = raw_root / "EVENT" / f"csl_script_event_{source_key}_export"
    export_dir.mkdir(parents=True)
    return export_dir


def _make_episode_file(export_dir: Path, source_key: str, episode_number: int) -> Path:
    path = export_dir / f"CAB-csl_script_event_{source_key}-episode{episode_number}.dec"
    path.write_text("", encoding="utf-8")
    return path


def test_cli_missing_raw_root_returns_exit_1(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--raw-root",
            str(tmp_path / "does_not_exist"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1


def test_cli_generates_output_matching_schema(tmp_path):
    export_dir = _make_export_dir(tmp_path)
    _make_episode_file(export_dir, SOURCE_KEY, 1)
    _make_episode_file(export_dir, SOURCE_KEY, 2)
    output_path = tmp_path / "out" / "story_manifest_candidates.yaml"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--raw-root",
            str(tmp_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output_path.is_file()

    with open(output_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    errors = list(Draft7Validator(schema).iter_errors(document))
    assert errors == []
    assert document["stories"][0]["episodes"][0]["episodeNumber"] == 1


def test_cli_without_output_does_not_write_file(tmp_path):
    export_dir = _make_export_dir(tmp_path)
    _make_episode_file(export_dir, SOURCE_KEY, 1)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--raw-root", str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "EVT_250626_SYNTHETIC_DANCER" in result.stdout
    assert not (tmp_path / "story_manifest_candidates.yaml").exists()


def test_cli_quiet_suppresses_summary_output(tmp_path):
    export_dir = _make_export_dir(tmp_path)
    _make_episode_file(export_dir, SOURCE_KEY, 1)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--raw-root", str(tmp_path), "--quiet"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_cli_empty_raw_root_succeeds_with_zero_stories(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--raw-root", str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "検出したストーリー数: 0" in result.stdout


# ----------------------------------------------------------------
# CHARACTER / CHARACTER_DATE
# (feature/story-manifest-character-category-support、
# Character_Story_ID_Manifest_Design.md §4・§8・§9 PR C)
# ----------------------------------------------------------------

CHARACTER_SOURCE_ID = "42"
CHARACTER_ID = "CHAR_SYNTH_TEST"
UNCONFIRMED_SOURCE_ID = "43"


def _make_character_export_dir(
    raw_root: Path, source_id: str = CHARACTER_SOURCE_ID
) -> Path:
    export_dir = (
        raw_root / "CHARACTER" / f"csl_script_charastory_character{source_id}_export"
    )
    export_dir.mkdir(parents=True)
    return export_dir


def _make_character_file(export_dir: Path, source_id: str, suffix: str) -> Path:
    path = export_dir / f"CAB-csl_script_charastory_character{source_id}-{suffix}.dec"
    path.write_text("", encoding="utf-8")
    return path


def _write_character_dictionary(
    path: Path, source_id: str = CHARACTER_SOURCE_ID, character_id: str = CHARACTER_ID
) -> None:
    document = {
        "characters": [
            {
                "sourceCharacterId": source_id,
                "displayName": "Synthetic Character",
                "characterId": character_id,
                "status": "confirmed",
            }
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(document, f, allow_unicode=True)


def test_cli_generates_character_candidates_with_dictionary(tmp_path):
    export_dir = _make_character_export_dir(tmp_path)
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "episode1")
    dictionary_path = tmp_path / "characters.yaml"
    _write_character_dictionary(dictionary_path)
    output_path = tmp_path / "out" / "candidates.yaml"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--raw-root",
            str(tmp_path),
            "--character-dictionary",
            str(dictionary_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    with open(output_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    errors = list(Draft7Validator(schema).iter_errors(document))
    assert errors == []
    story_ids = {story["storyId"] for story in document["stories"]}
    assert "CHAR_MAIN_SYNTH_TEST" in story_ids


def test_cli_reports_unconfirmed_character_without_silently_dropping(tmp_path):
    export_dir = _make_character_export_dir(tmp_path, UNCONFIRMED_SOURCE_ID)
    _make_character_file(export_dir, UNCONFIRMED_SOURCE_ID, "episode1")
    dictionary_path = tmp_path / "characters.yaml"
    _write_character_dictionary(dictionary_path)  # confirmed entry uses a different ID

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--raw-root",
            str(tmp_path),
            "--character-dictionary",
            str(dictionary_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "unconfirmed_character" in result.stdout
    assert UNCONFIRMED_SOURCE_ID in result.stdout


def test_cli_quiet_suppresses_character_report(tmp_path):
    export_dir = _make_character_export_dir(tmp_path, UNCONFIRMED_SOURCE_ID)
    _make_character_file(export_dir, UNCONFIRMED_SOURCE_ID, "episode1")
    dictionary_path = tmp_path / "characters.yaml"
    _write_character_dictionary(dictionary_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--raw-root",
            str(tmp_path),
            "--character-dictionary",
            str(dictionary_path),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_cli_character_dir_without_dictionary_arg_uses_default_and_does_not_crash(
    tmp_path,
):
    """--character-dictionary省略時は既定パスを使う。既定辞書に該当IDが
    無くてもクラッシュせず、pending報告として扱われることを確認する。"""
    export_dir = _make_character_export_dir(tmp_path, "999999")
    _make_character_file(export_dir, "999999", "episode1")

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--raw-root", str(tmp_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_cli_event_and_character_candidates_combined(tmp_path):
    """EVENT・CHARACTER両方のraw配置が存在する場合、両方のstoryが
    同一documentへ出力される (EVENT既存挙動の無回帰)。"""
    event_export_dir = _make_export_dir(tmp_path)
    _make_episode_file(event_export_dir, SOURCE_KEY, 1)

    character_export_dir = _make_character_export_dir(tmp_path)
    _make_character_file(character_export_dir, CHARACTER_SOURCE_ID, "episode1")
    dictionary_path = tmp_path / "characters.yaml"
    _write_character_dictionary(dictionary_path)

    output_path = tmp_path / "out" / "candidates.yaml"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--raw-root",
            str(tmp_path),
            "--character-dictionary",
            str(dictionary_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    with open(output_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    story_ids = {story["storyId"] for story in document["stories"]}
    assert "EVT_250626_SYNTHETIC_DANCER" in story_ids
    assert "CHAR_MAIN_SYNTH_TEST" in story_ids
