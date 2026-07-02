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

from agents.extractor.validator import (
    SemanticValidationIssue,
    run_semantic_validation,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "extraction"
VALIDATOR_SCRIPT = PROJECT_ROOT / "scripts" / "validate_extraction_json.py"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _errors(issues: list[SemanticValidationIssue]) -> list[SemanticValidationIssue]:
    return [i for i in issues if i.severity == "error"]


def minimal_instance() -> dict:
    return _load_fixture("minimal_episode_extraction.json")


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
# 2. duplicate candidate id check
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
# 3. empty evidenceIndex check
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
# 4. extractionRun consistency check
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
# 5. relationship basic check
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


def test_cli_without_semantic_flag_ignores_semantic_errors():
    # --semanticを指定しない場合、JSON Schema上は妥当なので通常検証は成功する
    result = _run_cli(
        "--input",
        str(FIXTURES_DIR / "invalid_semantic_missing_evidence_ref.json"),
    )
    assert result.returncode == 0, result.stderr
