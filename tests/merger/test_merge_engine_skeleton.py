"""
tests/merger/test_merge_engine_skeleton.py
agents/merger の merge engine skeleton (単一ファイル入力) のテスト。

本格的なcandidate merge・canonical ID割り当て・manual override適用・
conflict解決はまだ実装していない。ここでは以下のみを対象とする。
- 検証ゲート (JSON Schema + semantic validation) が効くこと
- 検証済み入力からcandidate件数が正しく集計されること
- 出力collectionに8種のentity配列が存在すること
- CLIが成功/失敗の両方で正しいexit codeを返すこと

実データ・data/extracted/生成物は使わず、既存の
tests/fixtures/extraction/ の自作フィクスチャのみを使う。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agents.merger import MergeEngine

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "extraction"
MERGE_SCRIPT = PROJECT_ROOT / "scripts" / "merge_extractions.py"

MINIMAL_FIXTURE = FIXTURES_DIR / "minimal_episode_extraction.json"
SCHEMA_INVALID_FIXTURE = FIXTURES_DIR / "invalid_missing_evidence.json"
SEMANTIC_INVALID_FIXTURE = FIXTURES_DIR / "invalid_semantic_missing_evidence_ref.json"


@pytest.fixture
def engine() -> MergeEngine:
    return MergeEngine()


# ----------------------------------------------------------------
# 1. valid inputで成功する
# ----------------------------------------------------------------


def test_merge_file_with_valid_input_succeeds(engine):
    collection = engine.merge_file(MINIMAL_FIXTURE)
    report = collection["report"]

    assert report["inputFiles"] == 1
    assert report["validInputs"] == 1
    assert report["invalidInputs"] == 0
    assert report["errors"] == []


def test_merge_file_records_source_document(engine):
    collection = engine.merge_file(MINIMAL_FIXTURE)

    assert len(collection["sourceDocuments"]) == 1
    assert collection["sourceDocuments"][0]["episodeId"] == "TEST_S01_C01_E01"


# ----------------------------------------------------------------
# 2. candidateCountsが正しく集計される
# ----------------------------------------------------------------


def test_candidate_counts_reflect_input_document(engine):
    with open(MINIMAL_FIXTURE, encoding="utf-8") as f:
        fixture = json.load(f)

    collection = engine.merge_file(MINIMAL_FIXTURE)
    counts = collection["report"]["candidateCounts"]

    assert counts["characters"] == len(fixture["characters"])
    assert counts["locations"] == len(fixture["locations"])
    assert counts["organizations"] == len(fixture["organizations"])
    assert counts["items"] == len(fixture["items"])
    assert counts["lore"] == len(fixture["lore"])
    assert counts["events"] == len(fixture["events"])
    assert counts["relationships"] == len(fixture["relationships"])
    assert counts["timelineCandidates"] == len(fixture["timelineCandidates"])


# ----------------------------------------------------------------
# 3. 出力collectionの構造 (8種のentity配列が空のまま存在する)
# ----------------------------------------------------------------


def test_output_collection_has_all_eight_entity_arrays(engine):
    collection = engine.merge_file(MINIMAL_FIXTURE)
    entities = collection["entities"]

    for key in (
        "characters",
        "locations",
        "organizations",
        "items",
        "lore",
        "events",
        "relationships",
        "timeline",
    ):
        assert key in entities
        assert entities[key] == [], f"{key} はskeletonでは空のはず"


def test_output_collection_has_expected_top_level_fields(engine):
    collection = engine.merge_file(MINIMAL_FIXTURE)

    assert collection["documentType"] == "merged_knowledge_collection"
    assert collection["schemaVersion"] == "0.1.0"
    assert "generatedAt" in collection
    assert "sourceDocuments" in collection
    assert "entities" in collection
    assert "report" in collection


# ----------------------------------------------------------------
# 4. invalid inputは失敗として記録される
# ----------------------------------------------------------------


def test_merge_file_with_schema_invalid_input_is_rejected(engine):
    collection = engine.merge_file(SCHEMA_INVALID_FIXTURE)
    report = collection["report"]

    assert report["validInputs"] == 0
    assert report["invalidInputs"] == 1
    assert str(SCHEMA_INVALID_FIXTURE) in report["skippedInputs"]
    assert report["errors"], "schema検証失敗の内容がerrorsに記録されるべき"
    # invalid入力はcandidate集計対象から除外される
    assert all(count == 0 for count in report["candidateCounts"].values())
    assert collection["entities"]["characters"] == []


def test_merge_file_with_semantic_invalid_input_is_rejected(engine):
    collection = engine.merge_file(SEMANTIC_INVALID_FIXTURE)
    report = collection["report"]

    assert report["validInputs"] == 0
    assert report["invalidInputs"] == 1
    assert report["errors"], "semantic検証失敗の内容がerrorsに記録されるべき"


# ----------------------------------------------------------------
# CLI smoke test
# ----------------------------------------------------------------


def test_cli_succeeds_with_valid_input(tmp_path):
    output_dir = tmp_path / "merge_preview"

    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(MINIMAL_FIXTURE),
            "--output",
            str(output_dir),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    output_file = output_dir / "merged_knowledge_collection.json"
    assert output_file.exists()

    with open(output_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data["report"]["validInputs"] == 1


def test_cli_fails_with_invalid_input(tmp_path):
    output_dir = tmp_path / "merge_preview"

    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(SCHEMA_INVALID_FIXTURE),
            "--output",
            str(output_dir),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1


def test_cli_reports_missing_input_file(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(tmp_path / "does_not_exist.json"),
            "--output",
            str(tmp_path / "merge_preview"),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
