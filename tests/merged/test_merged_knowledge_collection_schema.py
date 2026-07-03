"""
tests/merged/test_merged_knowledge_collection_schema.py
Stage B merge engine (agents/merger/) が返すcollection wrapperの
schemas/merged_knowledge_collection.schema.json (初版) のテスト。

schemas/merged_knowledge.schema.json (単一のmerged entity用) とは別物で、
merge engineの実際の出力 (sourceDocuments/entities/report) をそのまま
検証できることを確認する。Python side (MergeEngine) の出力構造は変更せず、
schema側を現在の実装に合わせている。
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from agents.merger import MergeEngine

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
COLLECTION_SCHEMA_PATH = SCHEMAS_DIR / "merged_knowledge_collection.schema.json"
MERGE_SCRIPT = PROJECT_ROOT / "scripts" / "merge_extractions.py"

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "merged_knowledge"
EXTRACTION_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "extraction"
MERGER_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "merger"

MINIMAL_EXTRACTION_FIXTURE = EXTRACTION_FIXTURES_DIR / "minimal_episode_extraction.json"
SCHEMA_INVALID_EXTRACTION_FIXTURE = (
    EXTRACTION_FIXTURES_DIR / "invalid_missing_evidence.json"
)
SECOND_VALID_EXTRACTION_FIXTURE = (
    MERGER_FIXTURES_DIR / "second_valid_episode_extraction.json"
)


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def collection_schema() -> dict:
    assert COLLECTION_SCHEMA_PATH.exists(), (
        f"Schema not found: {COLLECTION_SCHEMA_PATH}"
    )
    return _load_json(COLLECTION_SCHEMA_PATH)


@pytest.fixture
def collection_validator(collection_schema) -> Draft7Validator:
    return Draft7Validator(collection_schema)


@pytest.fixture
def minimal_collection_instance() -> dict:
    return _load_json(FIXTURES_DIR / "minimal_merged_collection.json")


@pytest.fixture
def engine() -> MergeEngine:
    return MergeEngine()


# ----------------------------------------------------------------
# 1. schema自体がDraft-07として妥当
# ----------------------------------------------------------------


def test_collection_schema_is_valid_json_schema(collection_schema):
    Draft7Validator.check_schema(collection_schema)


# ----------------------------------------------------------------
# 2. 自作fixtureが検証を通過する
# ----------------------------------------------------------------


def test_minimal_collection_fixture_is_valid(
    collection_validator, minimal_collection_instance
):
    errors = list(collection_validator.iter_errors(minimal_collection_instance))
    assert not errors, [e.message for e in errors]


def test_empty_entities_arrays_are_allowed(
    collection_validator, minimal_collection_instance
):
    # skeletonの現状: entities配下は常に空配列 (本格mergeは未実装)
    instance = copy.deepcopy(minimal_collection_instance)
    for key in instance["entities"]:
        instance["entities"][key] = []

    errors = list(collection_validator.iter_errors(instance))
    assert not errors, [e.message for e in errors]


# ----------------------------------------------------------------
# 3. MergeEngineの実出力が検証を通過する
# ----------------------------------------------------------------


def test_merge_engine_single_file_output_matches_collection_schema(
    collection_validator, engine
):
    collection = engine.merge_file(MINIMAL_EXTRACTION_FIXTURE)
    errors = list(collection_validator.iter_errors(collection))
    assert not errors, [e.message for e in errors]


def test_merge_engine_multiple_inputs_output_matches_collection_schema(
    collection_validator, engine
):
    collection = engine.merge_inputs(
        [str(MINIMAL_EXTRACTION_FIXTURE), str(SECOND_VALID_EXTRACTION_FIXTURE)]
    )
    errors = list(collection_validator.iter_errors(collection))
    assert not errors, [e.message for e in errors]


def test_merge_engine_output_with_invalid_input_matches_collection_schema(
    collection_validator, engine
):
    # invalid inputがあってもreport.inputResults/errorsの形自体はschemaに従う
    collection = engine.merge_inputs(
        [str(MINIMAL_EXTRACTION_FIXTURE), str(SCHEMA_INVALID_EXTRACTION_FIXTURE)]
    )
    errors = list(collection_validator.iter_errors(collection))
    assert not errors, [e.message for e in errors]


def test_merge_engine_output_with_missing_path_matches_collection_schema(
    collection_validator, engine, tmp_path
):
    # skippedになる (解決できない) 入力があってもschemaに従う
    missing = tmp_path / "does_not_exist.json"
    collection = engine.merge_inputs([str(MINIMAL_EXTRACTION_FIXTURE), str(missing)])
    errors = list(collection_validator.iter_errors(collection))
    assert not errors, [e.message for e in errors]


# ----------------------------------------------------------------
# 4. 必須フィールド・enum制約
# ----------------------------------------------------------------


def test_missing_candidate_counts_in_report_is_rejected(
    collection_validator, minimal_collection_instance
):
    instance = copy.deepcopy(minimal_collection_instance)
    del instance["report"]["candidateCounts"]

    errors = list(collection_validator.iter_errors(instance))
    assert errors, "report.candidateCountsは必須であるべき"


def test_missing_candidate_counts_in_source_document_is_rejected(
    collection_validator, minimal_collection_instance
):
    instance = copy.deepcopy(minimal_collection_instance)
    del instance["sourceDocuments"][0]["candidateCounts"]

    errors = list(collection_validator.iter_errors(instance))
    assert errors, "sourceDocuments[].candidateCountsは必須であるべき"


def test_input_result_invalid_status_is_rejected(
    collection_validator, minimal_collection_instance
):
    instance = copy.deepcopy(minimal_collection_instance)
    instance["report"]["inputResults"][0]["status"] = "pending"

    errors = list(collection_validator.iter_errors(instance))
    assert errors, "inputResults[].statusはvalid/invalid/skipped以外を拒否すべき"


def test_input_result_valid_statuses_are_accepted(
    collection_validator, minimal_collection_instance
):
    for status in ("valid", "invalid", "skipped"):
        instance = copy.deepcopy(minimal_collection_instance)
        instance["report"]["inputResults"][0]["status"] = status
        errors = list(collection_validator.iter_errors(instance))
        assert not errors, [e.message for e in errors]


def test_negative_candidate_count_is_rejected(
    collection_validator, minimal_collection_instance
):
    instance = copy.deepcopy(minimal_collection_instance)
    instance["report"]["candidateCounts"]["characters"] = -1

    errors = list(collection_validator.iter_errors(instance))
    assert errors, "candidateCountsの値は0以上であるべき"


def test_unknown_document_type_is_rejected(
    collection_validator, minimal_collection_instance
):
    instance = copy.deepcopy(minimal_collection_instance)
    instance["documentType"] = "something_else"

    errors = list(collection_validator.iter_errors(instance))
    assert errors, "documentTypeはmerged_knowledge_collection固定であるべき"


def test_missing_entities_key_is_rejected(
    collection_validator, minimal_collection_instance
):
    instance = copy.deepcopy(minimal_collection_instance)
    del instance["entities"]["timeline"]

    errors = list(collection_validator.iter_errors(instance))
    assert errors, "entitiesは8種すべてのキーを持つべき"


# ----------------------------------------------------------------
# CLI連携: scripts/merge_extractions.py の出力がschemaに通ること
# ----------------------------------------------------------------


def test_cli_output_matches_collection_schema(collection_validator, tmp_path):
    output_dir = tmp_path / "merge_preview"

    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(MINIMAL_EXTRACTION_FIXTURE),
            str(SECOND_VALID_EXTRACTION_FIXTURE),
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

    errors = list(collection_validator.iter_errors(data))
    assert not errors, [e.message for e in errors]
