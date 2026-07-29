"""
tests/extractor/test_extraction_semantic_validation.py
agents/extractor/validator.py の semantic validation と、
scripts/validate_extraction_json.py --semantic のテスト。

JSON Schemaでは表現しにくい意味的整合性 (evidenceIdsの実在、candidate id重複、
extractionRunの一致、relationshipの基本チェック) を対象とする。
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from agents.extractor.validator import (
    SemanticValidationIssue,
    run_semantic_validation,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "extraction"
VALIDATOR_SCRIPT = PROJECT_ROOT / "scripts" / "validate_extraction_json.py"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "extraction.schema.json"

with open(SCHEMA_PATH, encoding="utf-8") as _schema_file:
    EXTRACTION_SCHEMA_VALIDATOR = Draft7Validator(json.load(_schema_file))


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _errors(issues: list[SemanticValidationIssue]) -> list[SemanticValidationIssue]:
    return [i for i in issues if i.severity == "error"]


def minimal_instance() -> dict:
    return _load_fixture("minimal_episode_extraction.json")


FIELD_VALUE_CANDIDATE_TYPES = (
    ("characters", "character_candidate", "CHAR"),
    ("organizations", "organization_candidate", "ORG"),
    ("locations", "location_candidate", "LOC"),
    ("items", "item_candidate", "ITEM"),
    ("lore", "lore_candidate", "LORE"),
    ("events", "event_candidate", "EVENT"),
    ("relationships", "relationship_candidate", "REL"),
    ("timelineCandidates", "timeline_candidate", "TL"),
)


def _candidate_with_field(
    instance: dict,
    *,
    array_key: str,
    candidate_type: str,
    id_type: str,
    field_evidence_ids: list[str] | None,
) -> dict:
    candidate = {
        "id": f"TEST_S01_C01_E01_CAND_{id_type}900",
        "type": candidate_type,
        "sourceType": "ai_extracted",
        "confidence": 0.8,
        "evidenceIds": ["TEST_S01_C01_E01_DLG0001"],
        "extractionRun": instance["extractionRun"],
        "fields": {
            "detail": {
                "value": "合成テスト用",
                "sourceType": "ai_extracted",
                "confidence": 0.8,
            }
        },
    }
    if field_evidence_ids is not None:
        candidate["fields"]["detail"]["evidenceIds"] = field_evidence_ids
    if array_key == "characters":
        candidate.update(
            {
                "existingCharacterId": None,
                "sourceCharacterId": None,
                "nameCandidates": ["合成キャラクター"],
            }
        )
    elif array_key == "organizations":
        candidate.update(
            {
                "existingOrganizationId": None,
                "nameCandidates": ["合成組織"],
            }
        )
    elif array_key == "locations":
        candidate.update(
            {
                "existingLocationId": None,
                "nameCandidates": ["合成場所"],
                "sceneRefs": [],
            }
        )
    elif array_key == "items":
        candidate.update(
            {
                "existingItemId": None,
                "nameCandidates": ["合成アイテム"],
            }
        )
    elif array_key == "lore":
        candidate.update(
            {
                "existingLoreId": None,
                "termCandidates": ["合成用語"],
            }
        )
    elif array_key == "events":
        candidate.update(
            {
                "existingEventId": None,
                "nameCandidates": ["合成イベント"],
            }
        )
    elif array_key == "relationships":
        candidate.update(
            {
                "existingRelationshipId": None,
                "sourceCandidate": "CHAR_A",
                "targetCandidate": "CHAR_B",
                "relationshipType": "TEST_RELATION",
                "direction": "source_to_target",
            }
        )
    elif array_key == "timelineCandidates":
        candidate.update({"kind": "explicit_order", "orderValue": 1})
    return candidate


# ----------------------------------------------------------------
# 1. valid fixture
# ----------------------------------------------------------------


def test_valid_minimal_fixture_passes_semantic_validation():
    issues = run_semantic_validation(minimal_instance())
    assert not _errors(issues), [i.message for i in _errors(issues)]


# ----------------------------------------------------------------
# 1. evidenceIds existence check
# ----------------------------------------------------------------


def test_missing_evidence_id_fails_semantic_validation():
    instance = minimal_instance()
    instance["characters"][0]["evidenceIds"] = ["TEST_S01_C01_E01_DLG9999"]

    errors = _errors(run_semantic_validation(instance))
    assert errors
    assert any(i.rule == "evidence_id_exists" for i in errors)
    assert any(i.evidence_id == "TEST_S01_C01_E01_DLG9999" for i in errors)


# ----------------------------------------------------------------
# 2. FieldValue evidenceIds existence check
# ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("array_key", "candidate_type", "id_type"),
    FIELD_VALUE_CANDIDATE_TYPES,
)
def test_field_value_existing_evidence_id_passes_for_all_candidate_types(
    array_key: str,
    candidate_type: str,
    id_type: str,
):
    instance = minimal_instance()
    instance[array_key].append(
        _candidate_with_field(
            instance,
            array_key=array_key,
            candidate_type=candidate_type,
            id_type=id_type,
            field_evidence_ids=["TEST_S01_C01_E01_DLG0001"],
        )
    )

    schema_errors = sorted(
        EXTRACTION_SCHEMA_VALIDATOR.iter_errors(instance),
        key=lambda error: list(error.path),
    )
    assert not schema_errors, [error.message for error in schema_errors]

    errors = _errors(run_semantic_validation(instance))
    assert not [i for i in errors if i.rule == "field_value_evidence_id_exists"]


@pytest.mark.parametrize(
    ("array_key", "candidate_type", "id_type"),
    FIELD_VALUE_CANDIDATE_TYPES,
)
def test_field_value_missing_evidence_id_fails_for_all_candidate_types(
    array_key: str,
    candidate_type: str,
    id_type: str,
):
    instance = minimal_instance()
    candidate = _candidate_with_field(
        instance,
        array_key=array_key,
        candidate_type=candidate_type,
        id_type=id_type,
        field_evidence_ids=["TEST_S01_C01_E01_DLG9999"],
    )
    instance[array_key].append(candidate)

    errors = _errors(run_semantic_validation(instance))
    field_errors = [i for i in errors if i.rule == "field_value_evidence_id_exists"]
    assert len(field_errors) == 1
    assert field_errors[0].array_key == array_key
    assert field_errors[0].candidate_id == candidate["id"]
    assert field_errors[0].field_name == "fields.detail"
    assert field_errors[0].evidence_id == "TEST_S01_C01_E01_DLG9999"


def test_field_value_without_evidence_ids_inherits_candidate_evidence():
    instance = minimal_instance()
    field_value = instance["characters"][0]["fields"]["description"]
    assert "evidenceIds" not in field_value

    errors = _errors(run_semantic_validation(instance))
    assert not [i for i in errors if i.rule == "field_value_evidence_id_exists"]


def test_field_value_empty_evidence_ids_keeps_candidate_evidence_fallback():
    instance = minimal_instance()
    instance["characters"][0]["fields"]["description"]["evidenceIds"] = []

    errors = _errors(run_semantic_validation(instance))
    assert not [i for i in errors if i.rule == "field_value_evidence_id_exists"]


# ----------------------------------------------------------------
# 3. duplicate candidate id check
# ----------------------------------------------------------------


def test_duplicate_candidate_id_fails_semantic_validation():
    instance = minimal_instance()
    duplicate = copy.deepcopy(instance["characters"][0])
    duplicate["type"] = "location_candidate"
    duplicate["nameCandidates"] = ["テスト場所"]
    duplicate["sceneRefs"] = []
    instance["locations"].append(duplicate)

    errors = _errors(run_semantic_validation(instance))
    assert errors
    assert any(i.rule == "duplicate_candidate_id" for i in errors)


def test_unique_candidate_ids_pass():
    instance = minimal_instance()
    other = copy.deepcopy(instance["characters"][0])
    other["id"] = "TEST_S01_C01_E01_CAND_CHAR002"
    instance["characters"].append(other)

    errors = _errors(run_semantic_validation(instance))
    assert not any(i.rule == "duplicate_candidate_id" for i in errors)


# ----------------------------------------------------------------
# 4. empty evidenceIndex check
# ----------------------------------------------------------------


def test_empty_evidence_index_with_candidates_fails_semantic_validation():
    instance = minimal_instance()
    instance["evidenceIndex"] = {}

    errors = _errors(run_semantic_validation(instance))
    assert errors
    assert any(i.rule == "empty_evidence_index" for i in errors)


def test_empty_evidence_index_without_candidates_passes():
    instance = minimal_instance()
    instance["evidenceIndex"] = {}
    instance["characters"] = []

    errors = _errors(run_semantic_validation(instance))
    assert not any(i.rule == "empty_evidence_index" for i in errors)


# ----------------------------------------------------------------
# 5. extractionRun consistency check
# ----------------------------------------------------------------


def test_extraction_run_mismatch_fails_semantic_validation():
    instance = minimal_instance()
    instance["characters"][0]["extractionRun"] = {
        **instance["characters"][0]["extractionRun"],
        "modelName": "different-model",
    }

    errors = _errors(run_semantic_validation(instance))
    assert errors
    assert any(i.rule == "extraction_run_consistency" for i in errors)


def test_missing_document_extraction_run_fails_semantic_validation():
    instance = minimal_instance()
    del instance["extractionRun"]

    errors = _errors(run_semantic_validation(instance))
    assert any(i.rule == "extraction_run_present" for i in errors)


# ----------------------------------------------------------------
# 6. relationship basic and candidate endpoint checks
# ----------------------------------------------------------------


def _relationship_candidate(instance: dict, **overrides) -> dict:
    base = {
        "id": "TEST_S01_C01_E01_CAND_REL001",
        "type": "relationship_candidate",
        "sourceType": "ai_inferred",
        "confidence": 0.6,
        "evidenceIds": ["TEST_S01_C01_E01_DLG0001"],
        "extractionRun": instance["extractionRun"],
        "existingRelationshipId": None,
        "sourceCandidate": "CHAR_A",
        "targetCandidate": "CHAR_B",
        "relationshipType": "SOME_RELATION",
        "direction": "source_to_target",
        "temporalNote": None,
        "fields": {},
    }
    base.update(overrides)
    return base


def test_relationship_self_reference_is_warning_not_error():
    instance = minimal_instance()
    instance["relationships"].append(
        _relationship_candidate(
            instance, sourceCandidate="CHAR_A", targetCandidate="CHAR_A"
        )
    )

    issues = run_semantic_validation(instance)
    self_ref_issues = [i for i in issues if i.rule == "relationship_self_reference"]
    assert self_ref_issues
    assert all(i.severity == "warning" for i in self_ref_issues)
    assert not _errors(issues)


def test_relationship_empty_source_is_error():
    instance = minimal_instance()
    instance["relationships"].append(
        _relationship_candidate(instance, sourceCandidate="")
    )

    errors = _errors(run_semantic_validation(instance))
    assert any(i.rule == "relationship_endpoint_not_empty" for i in errors)


def test_relationship_empty_target_is_error():
    instance = minimal_instance()
    instance["relationships"].append(
        _relationship_candidate(instance, targetCandidate="")
    )

    errors = _errors(run_semantic_validation(instance))
    assert any(i.rule == "relationship_endpoint_not_empty" for i in errors)


def test_relationship_distinct_endpoints_pass():
    instance = minimal_instance()
    instance["relationships"].append(_relationship_candidate(instance))

    issues = run_semantic_validation(instance)
    assert not _errors(issues)
    assert not [i for i in issues if i.rule == "relationship_self_reference"]


def test_relationship_unknown_direction_is_warning_not_error():
    instance = minimal_instance()
    instance["relationships"].append(
        _relationship_candidate(instance, direction="sideways")
    )

    issues = run_semantic_validation(instance)
    direction_issues = [
        issue for issue in issues if issue.rule == "relationship_direction_known"
    ]

    assert len(direction_issues) == 1
    assert direction_issues[0].severity == "warning"
    assert direction_issues[0].field_name == "direction"
    assert "sideways" in direction_issues[0].message
    assert not _errors(issues)


@pytest.mark.parametrize(
    "direction", ("source_to_target", "target_to_source", "bidirectional")
)
def test_relationship_known_direction_has_no_warning(direction: str):
    instance = minimal_instance()
    instance["relationships"].append(
        _relationship_candidate(instance, direction=direction)
    )

    issues = run_semantic_validation(instance)

    assert not [
        issue for issue in issues if issue.rule == "relationship_direction_known"
    ]


def test_relationship_local_candidate_endpoints_pass():
    instance = minimal_instance()
    source_id = instance["characters"][0]["id"]
    target = copy.deepcopy(instance["characters"][0])
    target["id"] = "TEST_S01_C01_E01_CAND_CHAR002"
    instance["characters"].append(target)
    instance["relationships"].append(
        _relationship_candidate(
            instance,
            sourceCandidate=source_id,
            targetCandidate=target["id"],
        )
    )

    errors = _errors(run_semantic_validation(instance))
    assert not [i for i in errors if i.rule == "relationship_candidate_endpoint_exists"]


@pytest.mark.parametrize("endpoint_name", ("sourceCandidate", "targetCandidate"))
def test_relationship_missing_local_candidate_endpoint_is_error(
    endpoint_name: str,
):
    instance = minimal_instance()
    instance["relationships"].append(
        _relationship_candidate(
            instance,
            **{endpoint_name: "TEST_S01_C01_E01_CAND_CHAR999"},
        )
    )

    errors = _errors(run_semantic_validation(instance))
    endpoint_errors = [
        i for i in errors if i.rule == "relationship_candidate_endpoint_exists"
    ]
    assert len(endpoint_errors) == 1
    assert endpoint_errors[0].field_name == endpoint_name


def test_relationship_canonical_entity_endpoints_do_not_require_local_candidates():
    instance = minimal_instance()
    instance["relationships"].append(
        _relationship_candidate(
            instance,
            sourceCandidate="CHAR_AKAGI_HINA",
            targetCandidate="ORG_SPECIAL_TEAM",
        )
    )

    errors = _errors(run_semantic_validation(instance))
    assert not [i for i in errors if i.rule == "relationship_candidate_endpoint_exists"]


def test_relationship_canonical_id_containing_cand_segment_is_not_local_candidate():
    instance = minimal_instance()
    instance["relationships"].append(
        _relationship_candidate(
            instance,
            sourceCandidate="CHAR_CAND_ALPHA",
            targetCandidate="ORG_CAND_GROUP",
        )
    )

    errors = _errors(run_semantic_validation(instance))
    assert not [i for i in errors if i.rule == "relationship_candidate_endpoint_exists"]


def test_relationship_opaque_external_endpoints_remain_fail_open():
    instance = minimal_instance()
    instance["relationships"].append(
        _relationship_candidate(
            instance,
            sourceCandidate="LEGACY_SOURCE_REFERENCE",
            targetCandidate="LEGACY_TARGET_REFERENCE",
        )
    )

    errors = _errors(run_semantic_validation(instance))
    assert not [i for i in errors if i.rule == "relationship_candidate_endpoint_exists"]


# ----------------------------------------------------------------
# CLI --semantic
# ----------------------------------------------------------------


def _run_cli(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT), *extra_args],
        capture_output=True,
        text=True,
    )


def test_cli_semantic_accepts_valid_fixture():
    result = _run_cli(
        "--input",
        str(FIXTURES_DIR / "minimal_episode_extraction.json"),
        "--semantic",
    )
    assert result.returncode == 0, result.stderr


def test_cli_semantic_rejects_missing_evidence_ref_fixture():
    result = _run_cli(
        "--input",
        str(FIXTURES_DIR / "invalid_semantic_missing_evidence_ref.json"),
        "--semantic",
    )
    assert result.returncode == 1
    assert "evidence_id_exists" in result.stderr


def test_cli_semantic_rejects_duplicate_candidate_id_fixture():
    result = _run_cli(
        "--input",
        str(FIXTURES_DIR / "invalid_semantic_duplicate_candidate_id.json"),
        "--semantic",
    )
    assert result.returncode == 1
    assert "duplicate_candidate_id" in result.stderr


def test_cli_semantic_rejects_missing_field_value_evidence_id(tmp_path: Path):
    instance = minimal_instance()
    instance["characters"][0]["fields"]["description"]["evidenceIds"] = [
        "TEST_S01_C01_E01_DLG9999"
    ]
    input_path = tmp_path / "missing_field_value_evidence.json"
    input_path.write_text(
        json.dumps(instance, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = _run_cli("--input", str(input_path), "--semantic")

    assert result.returncode == 1
    assert "field_value_evidence_id_exists" in result.stderr
    assert "fields.description" in result.stderr


def test_cli_semantic_rejects_missing_relationship_candidate_endpoint(
    tmp_path: Path,
):
    instance = minimal_instance()
    instance["relationships"].append(
        _relationship_candidate(
            instance,
            sourceCandidate="TEST_S01_C01_E01_CAND_CHAR999",
        )
    )
    input_path = tmp_path / "missing_relationship_candidate_endpoint.json"
    input_path.write_text(
        json.dumps(instance, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = _run_cli("--input", str(input_path), "--semantic")

    assert result.returncode == 1
    assert "relationship_candidate_endpoint_exists" in result.stderr
    assert "sourceCandidate" in result.stderr


def test_cli_semantic_accepts_unknown_relationship_direction_with_warning(
    tmp_path: Path,
):
    instance = minimal_instance()
    instance["relationships"].append(
        _relationship_candidate(instance, direction="sideways")
    )
    input_path = tmp_path / "unknown_relationship_direction.json"
    input_path.write_text(
        json.dumps(instance, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = _run_cli("--input", str(input_path), "--semantic")

    assert result.returncode == 0, result.stderr
    assert "relationship_direction_known" in result.stderr
    assert "sideways" in result.stderr


def test_cli_without_semantic_flag_ignores_semantic_errors():
    # --semanticを指定しない場合、JSON Schema上は妥当なので通常検証は成功する
    result = _run_cli(
        "--input",
        str(FIXTURES_DIR / "invalid_semantic_missing_evidence_ref.json"),
    )
    assert result.returncode == 0, result.stderr
