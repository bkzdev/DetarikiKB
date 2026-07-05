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
