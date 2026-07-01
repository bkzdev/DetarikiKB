"""
tests/extraction/test_extraction_schema.py
episode_extraction JSON が schemas/extraction.schema.json に準拠しているかテストする
"""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "extraction.schema.json"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "extraction"


@pytest.fixture
def schema():
    assert SCHEMA_PATH.exists(), f"Schema file not found at {SCHEMA_PATH}"
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def validator(schema):
    return Draft7Validator(schema)


@pytest.fixture
def minimal_instance():
    path = FIXTURES_DIR / "minimal_episode_extraction.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_schema_itself_is_valid_json_schema(schema):
    Draft7Validator.check_schema(schema)


def test_minimal_fixture_is_valid(validator, minimal_instance):
    errors = list(validator.iter_errors(minimal_instance))
    assert not errors, f"Unexpected validation errors: {[e.message for e in errors]}"


def test_invalid_missing_evidence_fixture_is_rejected(validator):
    path = FIXTURES_DIR / "invalid_missing_evidence.json"
    with open(path, encoding="utf-8") as f:
        instance = json.load(f)

    errors = list(validator.iter_errors(instance))
    assert errors, "evidenceIds が空配列のcandidateはエラーになるべき"
    assert any("minItems" in (e.validator or "") for e in errors)


def test_confidence_out_of_range_is_rejected(validator, minimal_instance):
    instance = copy.deepcopy(minimal_instance)
    instance["characters"][0]["confidence"] = 1.5

    errors = list(validator.iter_errors(instance))
    assert errors, "confidenceが1.0を超える場合はエラーになるべき"


def test_confidence_below_zero_is_rejected(validator, minimal_instance):
    instance = copy.deepcopy(minimal_instance)
    instance["characters"][0]["confidence"] = -0.1

    errors = list(validator.iter_errors(instance))
    assert errors, "confidenceが0.0未満の場合はエラーになるべき"


def test_unknown_source_type_is_rejected(validator, minimal_instance):
    instance = copy.deepcopy(minimal_instance)
    instance["characters"][0]["sourceType"] = "guessed"

    errors = list(validator.iter_errors(instance))
    assert errors, "sourceTypeはenum外の値を拒否すべき"


def test_missing_required_top_level_field_is_rejected(validator, minimal_instance):
    instance = copy.deepcopy(minimal_instance)
    del instance["evidenceIndex"]

    errors = list(validator.iter_errors(instance))
    assert errors, "必須フィールド欠如はエラーになるべき"


def test_unknown_extraction_method_is_rejected(validator, minimal_instance):
    instance = copy.deepcopy(minimal_instance)
    instance["extractionRun"]["extractionMethod"] = "manual_review"

    errors = list(validator.iter_errors(instance))
    assert errors, "extractionMethodはenum外の値を拒否すべき"


def test_relationship_candidate_allows_free_string_type(validator, minimal_instance):
    # relationshipType の語彙は Relationships.md 未確定のため自由文字列を許容する
    # (Extraction_Result_Schema.md §12, §16.4)
    instance = copy.deepcopy(minimal_instance)
    instance["relationships"].append(
        {
            "id": "TEST_S01_C01_E01_CAND_REL001",
            "type": "relationship_candidate",
            "sourceType": "ai_inferred",
            "confidence": 0.6,
            "evidenceIds": ["TEST_S01_C01_E01_DLG0001"],
            "extractionRun": instance["extractionRun"],
            "existingRelationshipId": None,
            "sourceCandidate": "CHAR_A",
            "targetCandidate": "CHAR_B",
            "relationshipType": "SOME_NOT_YET_STANDARDIZED_RELATION",
            "direction": "source_to_target",
            "temporalNote": None,
            "fields": {},
        }
    )

    errors = list(validator.iter_errors(instance))
    assert not errors, f"Unexpected validation errors: {[e.message for e in errors]}"


def test_evidence_index_entries_validated(validator, minimal_instance):
    instance = copy.deepcopy(minimal_instance)
    instance["evidenceIndex"]["TEST_S01_C01_E01_DLG0001"]["confidence"] = 2.0

    errors = list(validator.iter_errors(instance))
    assert errors, "evidenceIndex内のEvidenceRefもconfidence制約を受けるべき"
