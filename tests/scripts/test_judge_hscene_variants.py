"""
tests/scripts/test_judge_hscene_variants.py
scripts/judge_hscene_variants.py のCLIスモークテスト。

すべて合成データ (tmp_path配下に組み立てる最小.decファイル) のみを使う。
実DECファイル・実キャラ名・実セリフは一切使わない
(docs/runbooks/AI_PR_Playbook.md §4 実装PR「テストは合成fixtureのみ」)。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
JUDGE_SCRIPT = PROJECT_ROOT / "scripts" / "judge_hscene_variants.py"


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(JUDGE_SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _make_char_dir(tmp_path: Path) -> Path:
    char_dir = tmp_path / "char_export"
    _write(
        char_dir / "H_scene1.dec",
        "$num0 = 1\n@ChTalk 0 a/1\nせりふ1\n",
    )
    # subset変種 (パースされない)
    _write(char_dir / "H_scene1_n.dec", "$num0 = 1\n@ChTalk 0 a/1\nせりふ1\n")
    # exception変種 (#9、本体に無い追加内容を含む)
    _write(
        char_dir / "H_scene1 #9.dec",
        "$num0 = 1\n@ChTalk 0 a/1\nせりふ1\n@ChTalk 0 a/2\n追加のせりふ\n",
    )
    # _VRは常にskip対象
    _write(char_dir / "H_scene1_VR.dec", "$num0 = 1\n@ChTalk 0 a/1\nせりふ1\n")
    return char_dir


def test_judge_only_reports_expected_summary(tmp_path):
    char_dir = _make_char_dir(tmp_path)
    report_output = tmp_path / "report"

    result = _run_cli(
        [
            "--input",
            str(char_dir),
            "--story-id",
            "CHAR_HS_TEST",
            "--report-output",
            str(report_output),
            "--report-format",
            "both",
            "--quiet",
        ]
    )

    assert result.returncode == 0, result.stderr

    json_path = report_output.with_suffix(".json")
    md_path = report_output.with_suffix(".md")
    assert json_path.exists()
    assert md_path.exists()

    with open(json_path, encoding="utf-8") as f:
        report = json.load(f)

    summary = report["summary"]
    assert summary["totalSubset"] == 1
    assert summary["totalException"] == 1
    assert summary["totalSkippedVr"] == 1
    assert summary["byPattern"]["hash"]["exception"] == 1
    assert summary["byPattern"]["n"]["subset"] == 1
    assert summary["byPattern"]["vr"]["skipped_vr"] == 1


def test_normalize_without_story_id_fails(tmp_path):
    char_dir = _make_char_dir(tmp_path)
    result = _run_cli(["--input", str(char_dir), "--normalize"])
    assert result.returncode == 1
    assert "--story-id" in result.stderr


def test_normalize_writes_char_hs_episode_for_exception_variant_only(tmp_path):
    char_dir = _make_char_dir(tmp_path)
    output_dir = tmp_path / "normalized_out"

    result = _run_cli(
        [
            "--input",
            str(char_dir),
            "--story-id",
            "CHAR_HS_TEST",
            "--normalize",
            "--output",
            str(output_dir),
            "--quiet",
        ]
    )

    assert result.returncode == 0, result.stderr

    character_dir = output_dir / "character"
    assert character_dir.is_dir()
    produced = sorted(p.name for p in character_dir.glob("*.json"))
    # exception判定 (#9) の1件のみnormalizeされる (subset/skipped_vrはparseしない)
    assert produced == ["CHAR_HS_TEST_E01_VD9.json"]

    with open(character_dir / "CHAR_HS_TEST_E01_VD9.json", encoding="utf-8") as f:
        story_json = json.load(f)

    assert story_json["storyCategory"] == "CHAR_HS"
    assert story_json["storyId"] == "CHAR_HS_TEST"
    assert story_json["episodes"][0]["episodeId"] == "CHAR_HS_TEST_E01_VD9"

    trace = story_json["source"]["hsceneVariantTrace"]
    assert trace["baseEpisodeId"] == "CHAR_HS_TEST_E01"
    assert trace["variantPattern"] == "hash"
    assert trace["dupIndex"] == 9
    assert trace["judgment"] == "exception"


def test_no_hscene_body_files_returns_zero_with_warning(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    result = _run_cli(["--input", str(empty_dir)])
    assert result.returncode == 0
    assert "見つかりませんでした" in result.stderr
