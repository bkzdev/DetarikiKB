"""
tests/scripts/test_check_character_dictionary_coverage.py
scripts/check_character_dictionary_coverage.py のCLIスモークテスト。

実データではなく、tmp_path上に組み立てた合成 .dec ライクなスクリプト・
合成キャラクター辞書のみを使う。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_character_dictionary_coverage.py"


def _write_dictionary(tmp_path: Path) -> Path:
    path = tmp_path / "characters.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "schemaVersion": "0.1",
                "characters": [
                    {
                        "sourceCharacterId": "9001",
                        "characterId": "CHAR_TEST_CLI_A",
                        "displayName": "Test CLI Character A",
                        "aliases": [],
                        "status": "confirmed",
                    }
                ],
            },
            f,
        )
    return path


def _write_script(tmp_path: Path) -> Path:
    path = tmp_path / "sample.dec"
    path.write_text(
        "$num0 = 9001\n@ChTalk 0\n既知キャラクターのセリフ\n"
        "$num1 = 9999\n@ChTalk 1\n未登録キャラクターのセリフ\n",
        encoding="utf-8",
    )
    return path


def test_cli_reports_coverage(tmp_path):
    dictionary_path = _write_dictionary(tmp_path)
    script_path = _write_script(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            str(script_path),
            "--dictionary",
            str(dictionary_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "observedCount: 2" in result.stdout
    assert "knownCount:    1" in result.stdout
    assert "unknownCount:  1" in result.stdout
    assert "9999" in result.stdout


def test_cli_missing_target_returns_exit_1(tmp_path):
    dictionary_path = _write_dictionary(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            str(tmp_path / "does_not_exist"),
            "--dictionary",
            str(dictionary_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1


def test_cli_invalid_dictionary_returns_exit_2(tmp_path):
    invalid_path = tmp_path / "invalid_characters.yaml"
    with open(invalid_path, "w", encoding="utf-8") as f:
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
    script_path = _write_script(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            str(script_path),
            "--dictionary",
            str(invalid_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2


def test_cli_missing_dictionary_returns_exit_2(tmp_path):
    script_path = _write_script(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            str(script_path),
            "--dictionary",
            str(tmp_path / "does_not_exist.yaml"),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
