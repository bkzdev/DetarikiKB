"""
tests/merger/test_merge_engine_skeleton.py
agents/merger の merge engine skeleton (複数ファイル・ディレクトリ・glob
パターン入力) のテスト。

本格的なcandidate merge・canonical ID割り当て・manual override適用・
conflict解決はまだ実装していない。ここでは以下のみを対象とする。
- 検証ゲート (JSON Schema + semantic validation) が効くこと
- 複数ファイル・ディレクトリ入力を解決できること
- 検証済み入力からcandidate件数が全valid input合算で正しく集計されること
- 出力collectionに8種のentity配列が存在すること
- 解決できなかった入力・validationに失敗した入力がreportへ記録されること
- CLIが成功/失敗の両方で正しいexit codeを返すこと

実データ・data/extracted/生成物は使わず、既存の
tests/fixtures/extraction/ の自作フィクスチャと、tests/fixtures/merger/
に追加した小さい自作フィクスチャのみを使う。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agents.merger import MergeEngine

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXTRACTION_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "extraction"
MERGER_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "merger"
MERGE_SCRIPT = PROJECT_ROOT / "scripts" / "merge_extractions.py"

MINIMAL_FIXTURE = EXTRACTION_FIXTURES_DIR / "minimal_episode_extraction.json"
SCHEMA_INVALID_FIXTURE = EXTRACTION_FIXTURES_DIR / "invalid_missing_evidence.json"
SEMANTIC_INVALID_FIXTURE = (
    EXTRACTION_FIXTURES_DIR / "invalid_semantic_missing_evidence_ref.json"
)
SECOND_VALID_FIXTURE = MERGER_FIXTURES_DIR / "second_valid_episode_extraction.json"


@pytest.fixture
def engine() -> MergeEngine:
    return MergeEngine()


# ----------------------------------------------------------------
# 1. 単一valid inputで成功する (後方互換)
# ----------------------------------------------------------------


def test_merge_file_with_valid_input_succeeds(engine):
    collection = engine.merge_file(MINIMAL_FIXTURE)
    report = collection["report"]

    assert report["inputFiles"] == 1
    assert report["resolvedInputFiles"] == 1
    assert report["validInputs"] == 1
    assert report["invalidInputs"] == 0
    assert report["errors"] == []


def test_merge_file_records_source_document(engine):
    collection = engine.merge_file(MINIMAL_FIXTURE)

    assert len(collection["sourceDocuments"]) == 1
    source_doc = collection["sourceDocuments"][0]
    assert source_doc["episodeId"] == "TEST_S01_C01_E01"
    assert source_doc["documentId"] == "TEST_S01_C01_E01"
    assert source_doc["path"] == str(MINIMAL_FIXTURE)
    assert "candidateCounts" in source_doc


# ----------------------------------------------------------------
# 2. candidateCountsが正しく集計される (単一input)
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
    assert report["errors"], "schema検証失敗の内容がerrorsに記録されるべき"
    assert any(
        r["path"] == str(SCHEMA_INVALID_FIXTURE) and r["status"] == "invalid"
        for r in report["inputResults"]
    )
    # invalid入力はcandidate集計対象から除外される
    assert all(count == 0 for count in report["candidateCounts"].values())
    assert collection["entities"]["characters"] == []


def test_merge_file_with_semantic_invalid_input_is_rejected(engine):
    collection = engine.merge_file(SEMANTIC_INVALID_FIXTURE)
    report = collection["report"]

    assert report["validInputs"] == 0
    assert report["invalidInputs"] == 1
    assert report["errors"], "semantic検証失敗の内容がerrorsに記録されるべき"
    assert any(
        r["path"] == str(SEMANTIC_INVALID_FIXTURE) and r["status"] == "invalid"
        for r in report["inputResults"]
    )


# ----------------------------------------------------------------
# 5. 複数ファイル入力
# ----------------------------------------------------------------


def test_merge_inputs_with_multiple_valid_files(engine):
    collection = engine.merge_inputs([str(MINIMAL_FIXTURE), str(SECOND_VALID_FIXTURE)])
    report = collection["report"]

    assert report["inputFiles"] == 2
    assert report["resolvedInputFiles"] == 2
    assert report["validInputs"] == 2
    assert report["invalidInputs"] == 0
    assert len(collection["sourceDocuments"]) == 2


def test_candidate_counts_aggregate_across_multiple_files(engine):
    with open(MINIMAL_FIXTURE, encoding="utf-8") as f:
        first = json.load(f)
    with open(SECOND_VALID_FIXTURE, encoding="utf-8") as f:
        second = json.load(f)

    collection = engine.merge_inputs([str(MINIMAL_FIXTURE), str(SECOND_VALID_FIXTURE)])
    counts = collection["report"]["candidateCounts"]

    assert counts["characters"] == len(first["characters"]) + len(second["characters"])
    assert counts["locations"] == len(first["locations"]) + len(second["locations"])


def test_source_documents_count_matches_valid_inputs(engine):
    collection = engine.merge_inputs(
        [str(MINIMAL_FIXTURE), str(SECOND_VALID_FIXTURE), str(SCHEMA_INVALID_FIXTURE)]
    )

    # invalid inputはsourceDocumentsに含まれない
    assert len(collection["sourceDocuments"]) == 2
    episode_ids = {doc["episodeId"] for doc in collection["sourceDocuments"]}
    assert episode_ids == {"TEST_S01_C01_E01", "TEST_S01_C01_E02"}


def test_mixed_valid_and_invalid_inputs_records_both(engine):
    collection = engine.merge_inputs(
        [str(MINIMAL_FIXTURE), str(SCHEMA_INVALID_FIXTURE)]
    )
    report = collection["report"]

    assert report["resolvedInputFiles"] == 2
    assert report["validInputs"] == 1
    assert report["invalidInputs"] == 1
    statuses = {r["path"]: r["status"] for r in report["inputResults"]}
    assert statuses[str(MINIMAL_FIXTURE)] == "valid"
    assert statuses[str(SCHEMA_INVALID_FIXTURE)] == "invalid"


# ----------------------------------------------------------------
# 6. ディレクトリ入力
# ----------------------------------------------------------------


def test_directory_input_resolves_json_files(engine):
    collection = engine.merge_inputs([str(MERGER_FIXTURES_DIR)])
    report = collection["report"]

    assert report["resolvedInputFiles"] == 1
    assert report["validInputs"] == 1
    assert collection["sourceDocuments"][0]["episodeId"] == "TEST_S01_C01_E02"


# ----------------------------------------------------------------
# 7. 存在しないpathの扱い
# ----------------------------------------------------------------


def test_missing_path_is_recorded_as_skipped(engine, tmp_path):
    missing = tmp_path / "does_not_exist.json"
    collection = engine.merge_inputs([str(missing)])
    report = collection["report"]

    assert report["resolvedInputFiles"] == 0
    assert report["validInputs"] == 0
    assert report["invalidInputs"] == 0
    assert str(missing) in report["skippedInputs"]
    assert any(
        r["path"] == str(missing) and r["status"] == "skipped"
        for r in report["inputResults"]
    )


def test_missing_path_mixed_with_valid_input(engine, tmp_path):
    missing = tmp_path / "does_not_exist.json"
    collection = engine.merge_inputs([str(MINIMAL_FIXTURE), str(missing)])
    report = collection["report"]

    assert report["resolvedInputFiles"] == 1
    assert report["validInputs"] == 1
    assert str(missing) in report["skippedInputs"]


# ----------------------------------------------------------------
# CLI smoke tests
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


def test_cli_succeeds_with_multiple_inputs(tmp_path):
    output_dir = tmp_path / "merge_preview"

    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(MINIMAL_FIXTURE),
            str(SECOND_VALID_FIXTURE),
            "--output",
            str(output_dir),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    output_file = output_dir / "merged_knowledge_collection.json"
    with open(output_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data["report"]["validInputs"] == 2
    assert len(data["sourceDocuments"]) == 2


def test_cli_succeeds_with_directory_input(tmp_path):
    output_dir = tmp_path / "merge_preview"

    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(MERGER_FIXTURES_DIR),
            "--output",
            str(output_dir),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    output_file = output_dir / "merged_knowledge_collection.json"
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
