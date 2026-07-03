"""
tests/merged/test_merged_knowledge_schema.py
Stage B の merged knowledge / manual overrides JSON Schema (初版) のテスト。

schemas/merged_knowledge.schema.json と schemas/manual_overrides.schema.json が
自作の最小fixtureを正しく受理し、不正な入力を拒否することを確認する。
Python merge engineは未実装のため、schema検証のみを対象とする。
"""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
MERGED_SCHEMA_PATH = SCHEMAS_DIR / "merged_knowledge.schema.json"
OVERRIDES_SCHEMA_PATH = SCHEMAS_DIR / "manual_overrides.schema.json"
CANONICAL_SCHEMA_PATH = SCHEMAS_DIR / "canonical_knowledge.schema.json"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "merged_knowledge"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def merged_schema() -> dict:
    assert MERGED_SCHEMA_PATH.exists(), f"Schema not found: {MERGED_SCHEMA_PATH}"
    return _load_json(MERGED_SCHEMA_PATH)


@pytest.fixture
def merged_validator(merged_schema) -> Draft7Validator:
    return Draft7Validator(merged_schema)


@pytest.fixture
def overrides_schema() -> dict:
    assert OVERRIDES_SCHEMA_PATH.exists(), f"Schema not found: {OVERRIDES_SCHEMA_PATH}"
    return _load_json(OVERRIDES_SCHEMA_PATH)


@pytest.fixture
def overrides_validator(overrides_schema) -> Draft7Validator:
    return Draft7Validator(overrides_schema)


@pytest.fixture
def character_instance() -> dict:
    return _load_json(FIXTURES_DIR / "minimal_merged_character.json")


@pytest.fixture
def relationship_instance() -> dict:
    return _load_json(FIXTURES_DIR / "minimal_merged_relationship.json")


@pytest.fixture
def timeline_instance() -> dict:
    return _load_json(FIXTURES_DIR / "minimal_merged_timeline_entry.json")


@pytest.fixture
def override_instance() -> dict:
    return _load_json(FIXTURES_DIR / "minimal_manual_override.json")


# ----------------------------------------------------------------
# 1. schemas themselves are valid Draft-07
# ----------------------------------------------------------------


def test_merged_schema_is_valid_json_schema(merged_schema):
    Draft7Validator.check_schema(merged_schema)


def test_overrides_schema_is_valid_json_schema(overrides_schema):
    Draft7Validator.check_schema(overrides_schema)


def test_canonical_placeholder_schema_is_valid_json_schema():
    schema = _load_json(CANONICAL_SCHEMA_PATH)
    Draft7Validator.check_schema(schema)


# ----------------------------------------------------------------
# 2. valid fixtures pass
# ----------------------------------------------------------------


def test_minimal_character_is_valid(merged_validator, character_instance):
    errors = list(merged_validator.iter_errors(character_instance))
    assert not errors, [e.message for e in errors]


def test_minimal_relationship_is_valid(merged_validator, relationship_instance):
    errors = list(merged_validator.iter_errors(relationship_instance))
    assert not errors, [e.message for e in errors]


def test_minimal_timeline_entry_is_valid(merged_validator, timeline_instance):
    errors = list(merged_validator.iter_errors(timeline_instance))
    assert not errors, [e.message for e in errors]


def test_minimal_override_is_valid(overrides_validator, override_instance):
    errors = list(overrides_validator.iter_errors(override_instance))
    assert not errors, [e.message for e in errors]


# ----------------------------------------------------------------
# 3. provenance is required (Stage Aのevidence/candidateを失わない)
# ----------------------------------------------------------------


def test_empty_evidence_refs_is_rejected(merged_validator, character_instance):
    instance = copy.deepcopy(character_instance)
    instance["evidenceRefs"] = []

    errors = list(merged_validator.iter_errors(instance))
    assert errors, "evidenceRefsが空のmerged entityは拒否されるべき (§10.1)"


def test_empty_source_candidates_is_rejected(merged_validator, character_instance):
    instance = copy.deepcopy(character_instance)
    instance["sourceCandidates"] = []

    errors = list(merged_validator.iter_errors(instance))
    assert errors, "sourceCandidatesが空のmerged entityは拒否されるべき"


def test_source_candidate_requires_candidate_id(merged_validator, character_instance):
    instance = copy.deepcopy(character_instance)
    del instance["sourceCandidates"][0]["candidateId"]

    errors = list(merged_validator.iter_errors(instance))
    assert errors, "sourceCandidateはcandidateId必須 (candidate id追跡)"


# ----------------------------------------------------------------
# 4. common field constraints
# ----------------------------------------------------------------


def test_confidence_out_of_range_is_rejected(merged_validator, character_instance):
    instance = copy.deepcopy(character_instance)
    instance["confidence"] = 1.5

    errors = list(merged_validator.iter_errors(instance))
    assert errors, "confidence > 1.0 は拒否されるべき"


def test_unknown_status_is_rejected(merged_validator, character_instance):
    instance = copy.deepcopy(character_instance)
    instance["status"] = "half_merged"

    errors = list(merged_validator.iter_errors(instance))
    assert errors, "statusはenum外の値を拒否すべき"


def test_unknown_source_type_is_rejected(merged_validator, character_instance):
    instance = copy.deepcopy(character_instance)
    instance["sourceTypes"] = ["guessed"]

    errors = list(merged_validator.iter_errors(instance))
    assert errors, "sourceTypesはenum外の値を拒否すべき"


def test_unknown_type_discriminator_is_rejected(merged_validator, character_instance):
    instance = copy.deepcopy(character_instance)
    instance["type"] = "faction"

    errors = list(merged_validator.iter_errors(instance))
    assert errors, "typeはenum外の値を拒否すべき (oneOfのどのブランチにも合致しない)"


# ----------------------------------------------------------------
# 5. relationship specifics
# ----------------------------------------------------------------


def test_relationship_requires_source_and_target(
    merged_validator, relationship_instance
):
    instance = copy.deepcopy(relationship_instance)
    del instance["sourceEntityId"]

    errors = list(merged_validator.iter_errors(instance))
    assert errors, "relationshipはsourceEntityId必須"


def test_relationship_allows_free_string_type(merged_validator, relationship_instance):
    # relationshipType taxonomyは未確定のため自由文字列を許容する (§6.3)
    instance = copy.deepcopy(relationship_instance)
    instance["relationshipType"] = "SOME_NOT_YET_STANDARDIZED_RELATION"

    errors = list(merged_validator.iter_errors(instance))
    assert not errors, [e.message for e in errors]


def test_relationship_rejects_unknown_direction(
    merged_validator, relationship_instance
):
    instance = copy.deepcopy(relationship_instance)
    instance["direction"] = "sideways"

    errors = list(merged_validator.iter_errors(instance))
    assert errors, "directionはenumで制限される"


# ----------------------------------------------------------------
# 6. manual override specifics
# ----------------------------------------------------------------


def test_override_source_type_must_be_manual(overrides_validator, override_instance):
    instance = copy.deepcopy(override_instance)
    instance["overrides"][0]["sourceType"] = "script"

    errors = list(overrides_validator.iter_errors(instance))
    assert errors, "override の sourceType は manual 固定 (§8.3)"


def test_override_rejects_unknown_operation(overrides_validator, override_instance):
    instance = copy.deepcopy(override_instance)
    instance["overrides"][0]["operation"] = "delete_everything"

    errors = list(overrides_validator.iter_errors(instance))
    assert errors, "operationはenum外の値を拒否すべき"


def test_override_requires_reason_and_author(overrides_validator, override_instance):
    instance = copy.deepcopy(override_instance)
    del instance["overrides"][0]["reason"]

    errors = list(overrides_validator.iter_errors(instance))
    assert errors, "override は reason 必須 (audit trail)"


def test_empty_overrides_array_is_valid(overrides_validator, override_instance):
    instance = copy.deepcopy(override_instance)
    instance["overrides"] = []

    errors = list(overrides_validator.iter_errors(instance))
    assert not errors, [e.message for e in errors]
