"""
tests/scripts/test_import_character_profiles_from_wiki.py
scripts/import_character_profiles_from_wiki.py のCLIスモークテスト。

合成HTML fixture (tests/fixtures/character_profiles/synthetic_wiki_member_table.html)
と合成辞書 (tests/fixtures/character_dictionary/synthetic_review_packet_dictionary.yaml)
のみを入力に使う。実データ・実Wiki本文・raw HTMLの取得は一切行わない
(ネットワークアクセスなし、--input-htmlのみを使う)。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "import_character_profiles_from_wiki.py"
HTML_FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "character_profiles"
    / "synthetic_wiki_member_table.html"
)
DICTIONARY_FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "character_dictionary"
    / "synthetic_review_packet_dictionary.yaml"
)


def _run_cli(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input-html",
            str(HTML_FIXTURE_PATH),
            "--characters",
            str(DICTIONARY_FIXTURE_PATH),
            *extra_args,
        ],
        capture_output=True,
        text=True,
    )


def test_cli_dry_run_prints_summary_only(tmp_path):
    output_path = tmp_path / "candidates.yaml"
    result = _run_cli("--output", str(output_path), "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "matched" in result.stdout
    assert "unmatched" in result.stdout
    assert not output_path.exists()


def test_cli_writes_yaml_candidate_file(tmp_path):
    output_path = tmp_path / "candidates.yaml"
    result = _run_cli("--output", str(output_path), "--format", "yaml")

    assert result.returncode == 0, result.stderr
    assert output_path.is_file()

    with open(output_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)

    assert document["documentType"] == "character_profile_import_candidates"
    assert len(document["candidates"]) == 3


def test_cli_matched_candidate_has_confirmed_character_id(tmp_path):
    output_path = tmp_path / "candidates.yaml"
    _run_cli("--output", str(output_path), "--format", "yaml")

    with open(output_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)

    matched = [c for c in document["candidates"] if c["matchStatus"] == "matched"]
    assert len(matched) == 1
    assert matched[0]["characterId"] == "CHAR_TEST_A"


def test_cli_unmatched_candidates_have_no_character_id(tmp_path):
    output_path = tmp_path / "candidates.yaml"
    _run_cli("--output", str(output_path), "--format", "yaml")

    with open(output_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)

    unmatched = [c for c in document["candidates"] if c["matchStatus"] == "unmatched"]
    assert len(unmatched) == 2
    assert all(c["characterId"] is None for c in unmatched)


def test_cli_self_introduction_is_null_for_matched_candidate(tmp_path):
    """一覧テーブルには自己紹介文が無いため、matchedエントリの
    selfIntroductionが常にnullであることを確認する。"""
    output_path = tmp_path / "candidates.yaml"
    _run_cli("--output", str(output_path), "--format", "yaml")

    with open(output_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)

    matched = next(c for c in document["candidates"] if c["matchStatus"] == "matched")
    assert matched["profile"]["selfIntroduction"] is None


def test_cli_height_cm_parsed_as_integer(tmp_path):
    output_path = tmp_path / "candidates.yaml"
    _run_cli("--output", str(output_path), "--format", "yaml")

    with open(output_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)

    matched = next(c for c in document["candidates"] if c["matchStatus"] == "matched")
    assert matched["profile"]["heightCm"] == 150
    assert isinstance(matched["profile"]["heightCm"], int)


def test_cli_writes_csv_candidate_file(tmp_path):
    output_path = tmp_path / "candidates.csv"
    result = _run_cli("--output", str(output_path), "--format", "csv")

    assert result.returncode == 0, result.stderr
    assert output_path.is_file()
    content = output_path.read_text(encoding="utf-8")
    assert "matchStatus" in content
    assert "CHAR_TEST_A" in content


def test_cli_does_not_generate_character_id_for_unknown():
    """standalone実行 (dry-run) の標準出力にAI生成characterIdらしき
    文字列が含まれないことを確認する。"""
    result = _run_cli("--dry-run")
    assert result.returncode == 0, result.stderr
    assert "CHAR_GENERATED" not in result.stdout


def test_cli_missing_input_html_returns_exit_code_1(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input-html",
            str(tmp_path / "does_not_exist.html"),
            "--characters",
            str(DICTIONARY_FIXTURE_PATH),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1


def test_cli_no_source_specified_returns_error():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--characters",
            str(DICTIONARY_FIXTURE_PATH),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
