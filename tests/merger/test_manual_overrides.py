"""
tests/merger/test_manual_overrides.py
agents/merger/overrides.py (manual override loader) のテスト。

manual overrideは、AI抽出・rule-based抽出やmerge結果を直接書き換える
のではなく「人間が明示した補正レイヤー」として扱う。evidenceRefs/
sourceCandidates/extractionRunRefs/conflicts (根拠情報) を失わないこと、
名前一致だけでは対象entityを特定しないこと (誤爆防止) を重点的に確認する。

実データ・data/extracted/生成物は使わない。fixtureは自作の
CHAR_TEST_A等の合成IDのみを使う。
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from agents.merger.overrides import (
    apply_manual_overrides,
    build_manual_overrides_report,
    load_manual_overrides,
    load_manual_overrides_schema,
    validate_manual_overrides,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
OVERRIDES_SCHEMA_PATH = SCHEMAS_DIR / "manual_overrides.schema.json"
COLLECTION_SCHEMA_PATH = SCHEMAS_DIR / "merged_knowledge_collection.schema.json"
MERGE_SCRIPT = PROJECT_ROOT / "scripts" / "merge_extractions.py"

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "merger" / "overrides"
VALID_OVERRIDES_FIXTURE = FIXTURES_DIR / "manual_overrides_valid.json"
INVALID_OVERRIDES_FIXTURE = FIXTURES_DIR / "manual_overrides_invalid.json"


def _minimal_evidence_ref(evidence_id: str = "EP01_DLG0001") -> dict:
    return {
        "evidenceId": evidence_id,
        "storyId": "TEST_STORY",
        "episodeId": "EP01",
        "sceneId": None,
        "blockId": evidence_id,
        "sourceDocumentId": "EP01",
        "evidenceType": "dialogue",
        "confidence": 0.9,
    }


def _minimal_source_candidate(candidate_id: str = "EP01_CAND_CHAR001") -> dict:
    return {
        "candidateId": candidate_id,
        "candidateType": "character_candidate",
        "sourceDocumentId": "EP01",
        "episodeId": "EP01",
        "evidenceIds": ["EP01_DLG0001"],
        "extractionRunRef": "EP01",
        "sourceType": "script",
        "confidence": 0.9,
    }


def _minimal_entity(
    entity_id: str,
    entity_type: str = "character",
    display_name: str = "テスト太郎",
    canonical_id: str | None = None,
    status: str = "merged",
    candidate_id: str = "EP01_CAND_CHAR001",
) -> dict:
    return {
        "schemaVersion": "0.1",
        "id": entity_id,
        "type": entity_type,
        "canonicalId": canonical_id,
        "mergedId": None if canonical_id else entity_id,
        "displayName": display_name,
        "aliases": [],
        "status": status,
        "sourceTypes": ["script"],
        "confidence": 0.9,
        "evidenceRefs": [_minimal_evidence_ref()],
        "sourceCandidates": [_minimal_source_candidate(candidate_id)],
        "extractionRunRefs": {
            "EP01": {
                "extractionVersion": "0.1.0",
                "extractionMethod": "rule_based",
                "modelProvider": None,
                "modelName": None,
                "promptVersion": None,
                "extractedAt": None,
                "parserCompatibilityAtExtraction": "compatible",
            }
        },
        "fieldValues": {},
        "conflicts": [
            {
                "conflictType": "field_value_conflict",
                "field": "displayName",
                "values": ["a", "b"],
                "sourceCandidateIds": [candidate_id],
                "severity": "warning",
                "resolutionStatus": "unresolved",
                "selectedValue": "a",
            }
        ],
        "manualOverridesApplied": [],
        "mergedFrom": ["EP01"],
        "createdAt": None,
        "updatedAt": None,
    }


def _minimal_collection(entities: dict[str, list[dict]] | None = None) -> dict:
    base_entities = {
        "characters": [],
        "locations": [],
        "organizations": [],
        "items": [],
        "lore": [],
        "events": [],
        "relationships": [],
        "timeline": [],
    }
    if entities:
        base_entities.update(entities)
    return {
        "schemaVersion": "0.1.0",
        "documentType": "merged_knowledge_collection",
        "generatedAt": "2026-07-03T00:00:00+00:00",
        "sourceDocuments": [],
        "entities": base_entities,
        "report": {
            "inputFiles": 1,
            "resolvedInputFiles": 1,
            "validInputs": 1,
            "invalidInputs": 0,
            "skippedInputs": [],
            "candidateCounts": {
                "characters": 0,
                "locations": 0,
                "organizations": 0,
                "items": 0,
                "lore": 0,
                "events": 0,
                "relationships": 0,
                "timelineCandidates": 0,
            },
            "mergedEntityCounts": {
                "characters": 0,
                "locations": 0,
                "organizations": 0,
                "items": 0,
                "lore": 0,
                "events": 0,
                "relationships": 0,
                "timeline": 0,
            },
            "conflictsCount": 0,
            "unresolvedCount": 0,
            "unresolvedEntityCounts": {
                "characters": 0,
                "locations": 0,
                "organizations": 0,
                "items": 0,
                "lore": 0,
                "events": 0,
                "relationships": 0,
                "timeline": 0,
            },
            "conflictCounts": {
                "total": 0,
                "bySeverity": {},
                "byType": {},
                "byEntityType": {},
            },
            "warningCounts": {
                "total": 0,
                "unresolvedRelationships": 0,
                "skippedOverrides": 0,
                "other": 0,
            },
            "entityTypeSummaries": {
                key: {
                    "candidateCount": 0,
                    "mergedCount": 0,
                    "unresolvedCount": 0,
                    "conflictCount": 0,
                }
                for key in (
                    "characters",
                    "locations",
                    "organizations",
                    "items",
                    "lore",
                    "events",
                    "relationships",
                    "timeline",
                )
            },
            "inputSummaries": [],
            "inputResults": [],
            "warnings": [],
            "errors": [],
        },
    }


def _override(
    override_id: str,
    operation: str,
    target_type: str,
    target_id: str | None,
    **extra,
) -> dict:
    payload = {
        "overrideId": override_id,
        "overrideType": "field",
        "operation": operation,
        "targetType": target_type,
        "targetId": target_id,
        "reason": "test",
        "author": "test-author",
        "createdAt": "2026-07-03",
        "sourceType": "manual",
    }
    payload.update(extra)
    return payload


@pytest.fixture
def overrides_schema() -> dict:
    return load_manual_overrides_schema()


@pytest.fixture
def collection_validator() -> Draft7Validator:
    with open(COLLECTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


# ----------------------------------------------------------------
# 1. manual override schema validation
# ----------------------------------------------------------------


def test_valid_fixture_passes_schema_validation(overrides_schema):
    data = load_manual_overrides(VALID_OVERRIDES_FIXTURE)
    errors = validate_manual_overrides(data, schema=overrides_schema)
    assert errors == []


def test_invalid_fixture_fails_schema_validation(overrides_schema):
    data = load_manual_overrides(INVALID_OVERRIDES_FIXTURE)
    errors = validate_manual_overrides(data, schema=overrides_schema)
    assert errors
    assert any("author" in message for message in errors)


# ----------------------------------------------------------------
# 2. displayName override
# ----------------------------------------------------------------


def test_display_name_override_is_applied():
    entity = _minimal_entity("CHAR_TEST_A", display_name="旧名前")
    collection = _minimal_collection({"characters": [entity]})
    overrides_data = {
        "overrides": [
            _override(
                "OVR_0001",
                "set_field",
                "character",
                "CHAR_TEST_A",
                field="displayName",
                value="新名前",
            )
        ]
    }

    updated, results = apply_manual_overrides(collection, overrides_data)

    assert updated["entities"]["characters"][0]["displayName"] == "新名前"
    assert results[0].status == "applied"
    assert results[0].fields_changed == ["displayName"]
    assert "OVR_0001" in updated["entities"]["characters"][0]["manualOverridesApplied"]


# ----------------------------------------------------------------
# 3. aliases追加
# ----------------------------------------------------------------


def test_add_alias_override_is_applied():
    entity = _minimal_entity("CHAR_TEST_A")
    collection = _minimal_collection({"characters": [entity]})
    overrides_data = {
        "overrides": [
            _override("OVR_0001", "add_alias", "character", "CHAR_TEST_A", alias="太郎")
        ]
    }

    updated, results = apply_manual_overrides(collection, overrides_data)

    assert updated["entities"]["characters"][0]["aliases"] == ["太郎"]
    assert results[0].status == "applied"


def test_remove_alias_override_is_applied():
    entity = _minimal_entity("CHAR_TEST_A")
    entity["aliases"] = ["太郎", "たろう"]
    collection = _minimal_collection({"characters": [entity]})
    overrides_data = {
        "overrides": [
            _override(
                "OVR_0001", "remove_alias", "character", "CHAR_TEST_A", alias="たろう"
            )
        ]
    }

    updated, results = apply_manual_overrides(collection, overrides_data)

    assert updated["entities"]["characters"][0]["aliases"] == ["太郎"]
    assert results[0].status == "applied"


# ----------------------------------------------------------------
# 4. status変更
# ----------------------------------------------------------------


def test_status_override_is_applied():
    entity = _minimal_entity("EVENT_TEST_X", entity_type="event", status="merged")
    collection = _minimal_collection({"events": [entity]})
    overrides_data = {
        "overrides": [
            _override(
                "OVR_0001",
                "set_field",
                "event",
                "EVENT_TEST_X",
                field="status",
                value="deprecated",
            )
        ]
    }

    updated, results = apply_manual_overrides(collection, overrides_data)

    assert updated["entities"]["events"][0]["status"] == "deprecated"
    assert results[0].status == "applied"


def test_invalid_status_value_is_an_error():
    entity = _minimal_entity("CHAR_TEST_A")
    collection = _minimal_collection({"characters": [entity]})
    overrides_data = {
        "overrides": [
            _override(
                "OVR_0001",
                "set_field",
                "character",
                "CHAR_TEST_A",
                field="status",
                value="not_a_real_status",
            )
        ]
    }

    updated, results = apply_manual_overrides(collection, overrides_data)

    assert results[0].status == "error"
    # 不正な値は適用しない (元のstatusを維持)
    assert updated["entities"]["characters"][0]["status"] == "merged"


# ----------------------------------------------------------------
# 5. canonicalId指定
# ----------------------------------------------------------------


def test_canonical_id_override_is_applied():
    entity = _minimal_entity(
        "UNRESOLVED_ORG_0001", entity_type="organization", canonical_id=None
    )
    entity["status"] = "unresolved"
    collection = _minimal_collection({"organizations": [entity]})
    overrides_data = {
        "overrides": [
            _override(
                "OVR_0001",
                "set_field",
                "organization",
                "UNRESOLVED_ORG_0001",
                field="canonicalId",
                value="ORG_TEST_ALPHA",
            )
        ]
    }

    updated, results = apply_manual_overrides(collection, overrides_data)

    assert updated["entities"]["organizations"][0]["canonicalId"] == "ORG_TEST_ALPHA"
    assert results[0].status == "applied"


# ----------------------------------------------------------------
# 6. 対象idが見つからない / 名前一致だけでは適用しない
# ----------------------------------------------------------------


def test_missing_target_id_is_skipped():
    entity = _minimal_entity("CHAR_TEST_A")
    collection = _minimal_collection({"characters": [entity]})
    overrides_data = {
        "overrides": [
            _override(
                "OVR_0001",
                "set_field",
                "character",
                "CHAR_DOES_NOT_EXIST",
                field="displayName",
                value="誰か",
            )
        ]
    }

    updated, results = apply_manual_overrides(collection, overrides_data)

    assert results[0].status == "skipped"
    assert updated["entities"]["characters"][0]["displayName"] == "テスト太郎"


def test_name_match_alone_does_not_apply_override():
    # targetIdとして表記そのもの (displayNameの値) を指定しても、
    # 名前一致では絶対に解決しない (id/canonicalId/candidateId以外は不可)
    entity = _minimal_entity("CHAR_TEST_A", display_name="テスト太郎")
    collection = _minimal_collection({"characters": [entity]})
    overrides_data = {
        "overrides": [
            _override(
                "OVR_0001",
                "set_field",
                "character",
                "テスト太郎",  # 名前そのものをtargetIdとして指定
                field="displayName",
                value="なりすまし",
            )
        ]
    }

    updated, results = apply_manual_overrides(collection, overrides_data)

    assert results[0].status == "skipped"
    assert updated["entities"]["characters"][0]["displayName"] == "テスト太郎"


def test_source_candidate_id_resolves_target():
    entity = _minimal_entity("CHAR_TEST_A", candidate_id="EP01_CAND_CHAR001")
    collection = _minimal_collection({"characters": [entity]})
    overrides_data = {
        "overrides": [
            _override(
                "OVR_0001",
                "set_field",
                "character",
                "EP01_CAND_CHAR001",  # merged entity idではなくStage A candidate id
                field="displayName",
                value="新名前",
            )
        ]
    }

    updated, results = apply_manual_overrides(collection, overrides_data)

    assert results[0].status == "applied"
    assert updated["entities"]["characters"][0]["displayName"] == "新名前"


# ----------------------------------------------------------------
# 7. 根拠情報 (evidenceRefs/sourceCandidates/extractionRunRefs/conflicts) の保持
# ----------------------------------------------------------------


def test_evidence_and_provenance_are_not_lost_after_override():
    entity = _minimal_entity("CHAR_TEST_A")
    original_evidence_refs = copy.deepcopy(entity["evidenceRefs"])
    original_source_candidates = copy.deepcopy(entity["sourceCandidates"])
    original_extraction_run_refs = copy.deepcopy(entity["extractionRunRefs"])
    original_conflicts = copy.deepcopy(entity["conflicts"])

    collection = _minimal_collection({"characters": [entity]})
    overrides_data = {
        "overrides": [
            _override(
                "OVR_0001",
                "set_field",
                "character",
                "CHAR_TEST_A",
                field="displayName",
                value="新名前",
            )
        ]
    }

    updated, _results = apply_manual_overrides(collection, overrides_data)
    updated_entity = updated["entities"]["characters"][0]

    assert updated_entity["evidenceRefs"] == original_evidence_refs
    assert updated_entity["sourceCandidates"] == original_source_candidates
    assert updated_entity["extractionRunRefs"] == original_extraction_run_refs
    assert updated_entity["conflicts"] == original_conflicts


def test_apply_manual_overrides_does_not_mutate_original_collection():
    entity = _minimal_entity("CHAR_TEST_A", display_name="旧名前")
    collection = _minimal_collection({"characters": [entity]})
    overrides_data = {
        "overrides": [
            _override(
                "OVR_0001",
                "set_field",
                "character",
                "CHAR_TEST_A",
                field="displayName",
                value="新名前",
            )
        ]
    }

    apply_manual_overrides(collection, overrides_data)

    assert collection["entities"]["characters"][0]["displayName"] == "旧名前"


# ----------------------------------------------------------------
# 8. build_manual_overrides_report
# ----------------------------------------------------------------


def test_build_manual_overrides_report_counts_results():
    entity = _minimal_entity("CHAR_TEST_A")
    collection = _minimal_collection({"characters": [entity]})
    overrides_data = {
        "overrides": [
            _override(
                "OVR_0001",
                "set_field",
                "character",
                "CHAR_TEST_A",
                field="displayName",
                value="新名前",
            ),
            _override(
                "OVR_0002",
                "set_field",
                "character",
                "CHAR_DOES_NOT_EXIST",
                field="displayName",
                value="誰か",
            ),
        ]
    }

    _updated, results = apply_manual_overrides(collection, overrides_data)
    report = build_manual_overrides_report(["overrides.json"], results)

    assert report["enabled"] is True
    assert report["overrideFiles"] == ["overrides.json"]
    assert report["appliedCount"] == 1
    assert report["skippedCount"] == 1
    assert report["errorCount"] == 0
    assert len(report["results"]) == 2


# ----------------------------------------------------------------
# 9. collection schema validation (override適用後もschemaに通る)
# ----------------------------------------------------------------


def test_collection_after_override_passes_collection_schema(collection_validator):
    entity = _minimal_entity("CHAR_TEST_A")
    collection = _minimal_collection({"characters": [entity]})
    overrides_data = {
        "overrides": [
            _override(
                "OVR_0001",
                "set_field",
                "character",
                "CHAR_TEST_A",
                field="displayName",
                value="新名前",
            )
        ]
    }

    updated, results = apply_manual_overrides(collection, overrides_data)
    updated["report"]["manualOverrides"] = build_manual_overrides_report(
        ["overrides.json"], results
    )

    errors = list(collection_validator.iter_errors(updated))
    assert not errors, [e.message for e in errors]


# ----------------------------------------------------------------
# CLI連携
# ----------------------------------------------------------------


def _extraction_run() -> dict:
    return {
        "extractionVersion": "0.1.0",
        "extractionMethod": "rule_based",
        "modelProvider": None,
        "modelName": None,
        "promptVersion": None,
        "extractedAt": None,
        "parserCompatibilityAtExtraction": "compatible",
    }


def _episode_extraction_fixture() -> dict:
    return {
        "schemaVersion": "0.1",
        "documentType": "episode_extraction",
        "episodeId": "EP01",
        "storyId": "TEST_STORY",
        "storyCategory": "MAIN",
        "extractionRun": _extraction_run(),
        "evidenceIndex": {
            "EP01_DLG0001": {
                "sourceId": "EP01_DLG0001",
                "storyId": "TEST_STORY",
                "episodeId": "EP01",
                "sceneId": None,
                "confidence": 1.0,
            }
        },
        "characters": [
            {
                "id": "EP01_CAND_CHAR001",
                "type": "character_candidate",
                "sourceType": "script",
                "confidence": 0.9,
                "evidenceIds": ["EP01_DLG0001"],
                "extractionRun": _extraction_run(),
                "existingCharacterId": "CHAR_TEST_A",
                "sourceCharacterId": None,
                "nameCandidates": ["テスト太郎"],
                "fields": {},
            }
        ],
        "organizations": [],
        "locations": [],
        "items": [],
        "lore": [],
        "events": [],
        "relationships": [],
        "timelineCandidates": [],
        "extractionErrors": [],
    }


def test_cli_applies_overrides_when_specified(tmp_path):
    input_path = tmp_path / "EP01.extraction.json"
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(_episode_extraction_fixture(), f, ensure_ascii=False)

    overrides_path = tmp_path / "overrides.json"
    overrides_data = {
        "schemaVersion": "0.1",
        "documentType": "manual_overrides",
        "overrides": [
            _override(
                "OVR_0001",
                "set_field",
                "character",
                "CHAR_TEST_A",
                field="displayName",
                value="上書き済み",
            )
        ],
    }
    with open(overrides_path, "w", encoding="utf-8") as f:
        json.dump(overrides_data, f, ensure_ascii=False)

    output_dir = tmp_path / "merge_preview"
    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--overrides",
            str(overrides_path),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    output_file = output_dir / "merged_knowledge_collection.json"
    with open(output_file, encoding="utf-8") as f:
        data = json.load(f)

    assert data["entities"]["characters"][0]["displayName"] == "上書き済み"
    assert data["report"]["manualOverrides"]["enabled"] is True
    assert data["report"]["manualOverrides"]["appliedCount"] == 1


def test_cli_without_overrides_keeps_existing_behavior(tmp_path):
    input_path = tmp_path / "EP01.extraction.json"
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(_episode_extraction_fixture(), f, ensure_ascii=False)

    output_dir = tmp_path / "merge_preview"
    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(input_path),
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

    assert data["entities"]["characters"][0]["displayName"] == "テスト太郎"
    assert "manualOverrides" not in data["report"]


def test_cli_rejects_invalid_override_file(tmp_path):
    input_path = tmp_path / "EP01.extraction.json"
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(_episode_extraction_fixture(), f, ensure_ascii=False)

    output_dir = tmp_path / "merge_preview"
    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--overrides",
            str(INVALID_OVERRIDES_FIXTURE),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert not (output_dir / "merged_knowledge_collection.json").exists()
