"""
tests/scripts/test_build_character_review_packet.py
scripts/build_character_review_packet.py のCLIスモークテスト。

合成fixture
(tests/fixtures/character_dictionary/synthetic_review_packet_collection.json、
tests/fixtures/character_dictionary/synthetic_review_packet_dictionary.yaml)
のみを入力に使い、出力先は常にtmp_pathにする。実データ由来のfixtureは使わない。
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_character_review_packet.py"
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "character_dictionary"
COLLECTION_PATH = FIXTURE_DIR / "synthetic_review_packet_collection.json"
DICTIONARY_PATH = FIXTURE_DIR / "synthetic_review_packet_dictionary.yaml"


def _run_cli(output: Path, format_: str = "yaml") -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--merged-collection",
            str(COLLECTION_PATH),
            "--dictionary",
            str(DICTIONARY_PATH),
            "--output",
            str(output),
            "--format",
            format_,
            "--batch-id",
            "character-dictionary-review-batch-test",
        ],
        capture_output=True,
        text=True,
    )


def test_cli_generates_yaml_packet(tmp_path):
    output = tmp_path / "packet.yaml"
    result = _run_cli(output, format_="yaml")

    assert result.returncode == 0, result.stderr
    assert output.is_file()

    with open(output, encoding="utf-8") as f:
        content = f.read()
    packet = yaml.safe_load(content)

    assert packet["reviewBatchId"] == "character-dictionary-review-batch-test"
    assert "generatedFrom" in packet
    assert isinstance(packet["entries"], list)
    assert len(packet["entries"]) >= 1


def test_cli_yaml_packet_excludes_confirmed_merged_character(tmp_path):
    output = tmp_path / "packet.yaml"
    _run_cli(output, format_="yaml")

    with open(output, encoding="utf-8") as f:
        packet = yaml.safe_load(f)

    source_ids = {entry["sourceCharacterId"] for entry in packet["entries"]}
    # 合成fixtureのCHAR_TEST_A (9001) はconfirmed済み・status:mergedのため
    # レビュー対象から除外される
    assert "9001" not in source_ids


def test_cli_yaml_packet_includes_name_only_and_unknown_entries(tmp_path):
    output = tmp_path / "packet.yaml"
    _run_cli(output, format_="yaml")

    with open(output, encoding="utf-8") as f:
        packet = yaml.safe_load(f)

    entries_by_id = {e["sourceCharacterId"]: e for e in packet["entries"]}
    assert "9002" in entries_by_id
    assert entries_by_id["9002"]["existingDictionaryStatus"] == "name_only"
    assert "9999" in entries_by_id
    assert entries_by_id["9999"]["existingDictionaryStatus"] == "unknown"


def test_cli_yaml_packet_human_review_placeholders_are_empty(tmp_path):
    output = tmp_path / "packet.yaml"
    _run_cli(output, format_="yaml")

    with open(output, encoding="utf-8") as f:
        packet = yaml.safe_load(f)

    for entry in packet["entries"]:
        assert entry["humanReviewStatus"] == "pending"
        assert entry["humanConfirmedCharacterId"] is None


def test_cli_yaml_packet_does_not_contain_forbidden_content(tmp_path):
    """packetファイルに元セリフ・raw payload相当の文字列が含まれないことを
    確認する (evidenceRefs/textExcerpt/sourceCandidates等のキー名も含めて
    出現しないこと)。"""
    output = tmp_path / "packet.yaml"
    _run_cli(output, format_="yaml")

    content = output.read_text(encoding="utf-8")
    assert "evidenceRefs" not in content
    assert "textExcerpt" not in content
    assert "sourceCandidates" not in content


def test_cli_generates_csv_packet(tmp_path):
    output = tmp_path / "packet.csv"
    result = _run_cli(output, format_="csv")

    assert result.returncode == 0, result.stderr
    assert output.is_file()

    with open(output, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 1
    assert "sourceCharacterId" in rows[0]
    assert "humanConfirmedCharacterId" in rows[0]


def test_cli_missing_merged_collection_returns_exit_code_1(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--merged-collection",
            str(tmp_path / "does_not_exist.json"),
            "--dictionary",
            str(DICTIONARY_PATH),
            "--output",
            str(tmp_path / "packet.yaml"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
