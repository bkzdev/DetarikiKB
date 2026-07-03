"""
tests/merger/test_relationship_type_normalization.py
agents/merger/relationship.py への relationshipType 正規化の適用テスト。

build_relationship_entities経由で、既知typeの複数表記が1つのmerged
relationshipへ統合されること、元のrelationshipTypeがfieldValuesへ
保持されること、未知typeが破棄されずreport.relationshipTypeSummaryへ
反映されることを確認する。CLI/MergeEngine経由のcollection schema
validationも合わせて確認する。

実データ・data/extracted/生成物は使わず、本ファイル内で組み立てる自作の
最小episode_extraction fixtureのみを使う。
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator

from agents.merger import MergeEngine
from agents.merger.relationship import build_relationship_entities

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
COLLECTION_SCHEMA_PATH = SCHEMAS_DIR / "merged_knowledge_collection.schema.json"
MERGE_SCRIPT = PROJECT_ROOT / "scripts" / "merge_extractions.py"


def _extraction_run() -> dict[str, Any]:
    return {
        "extractionVersion": "0.1.0",
        "extractionMethod": "rule_based",
        "modelProvider": None,
        "modelName": None,
        "promptVersion": None,
        "extractedAt": None,
        "parserCompatibilityAtExtraction": "compatible",
    }


def _evidence_ref(source_id: str, episode_id: str) -> dict[str, Any]:
    return {
        "sourceId": source_id,
        "storyId": "TAXTEST_STORY",
        "episodeId": episode_id,
        "sceneId": None,
        "confidence": 0.9,
    }


def _relationship_candidate(
    candidate_id: str,
    evidence_id: str,
    source_candidate: str,
    target_candidate: str,
    relationship_type: str,
    direction: str = "source_to_target",
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "relationship_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": [evidence_id],
        "extractionRun": _extraction_run(),
        "existingRelationshipId": None,
        "sourceCandidate": source_candidate,
        "targetCandidate": target_candidate,
        "relationshipType": relationship_type,
        "direction": direction,
        "temporalNote": None,
        "fields": {},
    }


def _episode_extraction(
    episode_id: str,
    relationships: list[dict[str, Any]],
    evidence_index: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schemaVersion": "0.1",
        "documentType": "episode_extraction",
        "episodeId": episode_id,
        "storyId": "TAXTEST_STORY",
        "storyCategory": "MAIN",
        "extractionRun": _extraction_run(),
        "evidenceIndex": evidence_index,
        "characters": [],
        "organizations": [],
        "locations": [],
        "items": [],
        "lore": [],
        "events": [],
        "relationships": relationships,
        "timelineCandidates": [],
        "extractionErrors": [],
    }


_KNOWN_ENTITIES = [
    {"id": "CHAR_A", "sourceCandidates": []},
    {"id": "CHAR_B", "sourceCandidates": []},
    {"id": "CHAR_C", "sourceCandidates": []},
]


# ----------------------------------------------------------------
# 1. 既知typeの複数表記が1つのmerged relationshipにmergeされる
#    (merge keyが正規化後relationshipTypeを使うことの間接確認)
# ----------------------------------------------------------------


def test_known_type_spelling_variants_merge_into_one_entity():
    relationship1 = _relationship_candidate(
        "EP01_CAND_REL001", "EP01_DLG0001", "CHAR_A", "CHAR_B", "MEMBER_OF"
    )
    relationship2 = _relationship_candidate(
        "EP01_CAND_REL002", "EP01_DLG0002", "CHAR_A", "CHAR_B", "member-of"
    )
    relationship3 = _relationship_candidate(
        "EP01_CAND_REL003", "EP01_DLG0003", "CHAR_A", "CHAR_B", "member of"
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship1, relationship2, relationship3],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
            "EP01_DLG0003": _evidence_ref("EP01_DLG0003", "EP01"),
        },
    )

    entities, warnings = build_relationship_entities(
        [("ep01.json", document)], _KNOWN_ENTITIES
    )

    assert warnings == []
    assert len(entities) == 1
    entity = entities[0]
    assert len(entity["sourceCandidates"]) == 3
    assert len(entity["evidenceRefs"]) == 3


def test_original_relationship_type_preserved_in_field_values():
    relationship1 = _relationship_candidate(
        "EP01_CAND_REL001", "EP01_DLG0001", "CHAR_A", "CHAR_B", "MEMBER_OF"
    )
    relationship2 = _relationship_candidate(
        "EP01_CAND_REL002", "EP01_DLG0002", "CHAR_A", "CHAR_B", "member-of"
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship1, relationship2],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )

    entities, _warnings = build_relationship_entities(
        [("ep01.json", document)], _KNOWN_ENTITIES
    )

    entity = entities[0]
    # entity.relationshipType自体は元の表記 (先頭観測値) を保持する
    # (自由文字列として書き換えない、既存挙動との互換性のため)
    assert entity["relationshipType"] == "MEMBER_OF"

    original_types = entity["fieldValues"]["originalRelationshipTypes"]["value"]
    assert set(original_types) == {"MEMBER_OF", "member-of"}

    normalization = entity["fieldValues"]["relationshipTypeNormalization"]["value"]
    assert normalization["normalizedValue"] == "member_of"
    assert normalization["isKnown"] is True
    assert normalization["warnings"] == []


# ----------------------------------------------------------------
# 2. 未知typeは破棄されず保持される
# ----------------------------------------------------------------


def test_unknown_relationship_type_is_not_discarded():
    relationship = _relationship_candidate(
        "EP01_CAND_REL001", "EP01_DLG0001", "CHAR_A", "CHAR_B", "rival-ish"
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    entities, warnings = build_relationship_entities(
        [("ep01.json", document)], _KNOWN_ENTITIES
    )

    # 未知typeでもrelationship mergeそのものはskipされない (warningsは空のまま)
    assert warnings == []
    assert len(entities) == 1
    entity = entities[0]
    assert entity["relationshipType"] == "rival-ish"

    normalization = entity["fieldValues"]["relationshipTypeNormalization"]["value"]
    assert normalization["normalizedValue"] == "rival_ish"
    assert normalization["isKnown"] is False
    assert normalization["warnings"] != []


# ----------------------------------------------------------------
# 3. direction/source/targetが違うものはmergeされない
# ----------------------------------------------------------------


def test_different_target_with_same_type_does_not_merge():
    relationship1 = _relationship_candidate(
        "EP01_CAND_REL001", "EP01_DLG0001", "CHAR_A", "CHAR_B", "MEMBER_OF"
    )
    relationship2 = _relationship_candidate(
        "EP01_CAND_REL002", "EP01_DLG0002", "CHAR_A", "CHAR_C", "member-of"
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship1, relationship2],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )

    entities, _warnings = build_relationship_entities(
        [("ep01.json", document)], _KNOWN_ENTITIES
    )

    assert len(entities) == 2
    targets = {e["targetEntityId"] for e in entities}
    assert targets == {"CHAR_B", "CHAR_C"}


def test_different_direction_with_same_type_does_not_merge():
    relationship1 = _relationship_candidate(
        "EP01_CAND_REL001",
        "EP01_DLG0001",
        "CHAR_A",
        "CHAR_B",
        "MEMBER_OF",
        direction="source_to_target",
    )
    relationship2 = _relationship_candidate(
        "EP01_CAND_REL002",
        "EP01_DLG0002",
        "CHAR_A",
        "CHAR_B",
        "member-of",
        direction="bidirectional",
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship1, relationship2],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )

    entities, _warnings = build_relationship_entities(
        [("ep01.json", document)], _KNOWN_ENTITIES
    )

    assert len(entities) == 2
    directions = {e["direction"] for e in entities}
    assert directions == {"source_to_target", "bidirectional"}


# ----------------------------------------------------------------
# 4. report.relationshipTypeSummary (MergeEngine経由)
# ----------------------------------------------------------------


@pytest.fixture
def engine() -> MergeEngine:
    return MergeEngine()


@pytest.fixture
def collection_validator() -> Draft7Validator:
    with open(COLLECTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


def _write_document(tmp_path: Path, name: str, document: dict[str, Any]) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def test_relationship_type_summary_reports_known_and_unknown_types(engine, tmp_path):
    relationship_known = _relationship_candidate(
        "EP01_CAND_REL001", "EP01_DLG0001", "CHAR_A", "CHAR_B", "MEMBER_OF"
    )
    relationship_unknown = _relationship_candidate(
        "EP01_CAND_REL002", "EP01_DLG0002", "CHAR_B", "CHAR_C", "rival-ish"
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship_known, relationship_unknown],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )
    # sourceCandidate/targetCandidateがCHAR_*のentity idそのものを指す
    # ケースなので、CharacterCandidateでCHAR_A/CHAR_B/CHAR_Cが解決済み
    # entityとして先に構築されるようにする (engine.merge_inputs経由)。
    character_a = {
        "id": "EP01_CAND_CHARA",
        "type": "character_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": ["EP01_DLG0001"],
        "extractionRun": _extraction_run(),
        "existingCharacterId": "CHAR_A",
        "sourceCharacterId": None,
        "nameCandidates": ["A"],
        "fields": {},
    }
    character_b = {
        "id": "EP01_CAND_CHARB",
        "type": "character_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": ["EP01_DLG0001"],
        "extractionRun": _extraction_run(),
        "existingCharacterId": "CHAR_B",
        "sourceCharacterId": None,
        "nameCandidates": ["B"],
        "fields": {},
    }
    character_c = {
        "id": "EP01_CAND_CHARC",
        "type": "character_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": ["EP01_DLG0002"],
        "extractionRun": _extraction_run(),
        "existingCharacterId": "CHAR_C",
        "sourceCharacterId": None,
        "nameCandidates": ["C"],
        "fields": {},
    }
    document["characters"] = [character_a, character_b, character_c]
    path = _write_document(tmp_path, "ep01.json", document)

    collection = engine.merge_inputs([str(path)])
    summary = collection["report"]["relationshipTypeSummary"]

    assert summary["knownTypes"].get("member_of") == 1
    assert summary["unknownTypes"].get("rival_ish") == 1
    assert summary["normalizedTypes"]["MEMBER_OF"] == "member_of"
    assert summary["normalizedTypes"]["rival-ish"] == "rival_ish"


def test_schema_validates_with_relationship_type_summary(
    collection_validator, engine, tmp_path
):
    relationship = _relationship_candidate(
        "EP01_CAND_REL001", "EP01_DLG0001", "CHAR_A", "CHAR_B", "MEMBER_OF"
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    character_a = {
        "id": "EP01_CAND_CHARA",
        "type": "character_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": ["EP01_DLG0001"],
        "extractionRun": _extraction_run(),
        "existingCharacterId": "CHAR_A",
        "sourceCharacterId": None,
        "nameCandidates": ["A"],
        "fields": {},
    }
    character_b = {
        "id": "EP01_CAND_CHARB",
        "type": "character_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": ["EP01_DLG0001"],
        "extractionRun": _extraction_run(),
        "existingCharacterId": "CHAR_B",
        "sourceCharacterId": None,
        "nameCandidates": ["B"],
        "fields": {},
    }
    document["characters"] = [character_a, character_b]
    path = _write_document(tmp_path, "ep01.json", document)

    collection = engine.merge_inputs([str(path)])
    errors = list(collection_validator.iter_errors(collection))
    assert not errors, [e.message for e in errors]
    assert "relationshipTypeSummary" in collection["report"]


def test_cli_output_with_relationship_type_summary_matches_collection_schema(
    collection_validator, tmp_path
):
    relationship = _relationship_candidate(
        "EP01_CAND_REL001", "EP01_DLG0001", "CHAR_A", "CHAR_B", "affiliated with"
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    character_a = {
        "id": "EP01_CAND_CHARA",
        "type": "character_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": ["EP01_DLG0001"],
        "extractionRun": _extraction_run(),
        "existingCharacterId": "CHAR_A",
        "sourceCharacterId": None,
        "nameCandidates": ["A"],
        "fields": {},
    }
    character_b = {
        "id": "EP01_CAND_CHARB",
        "type": "character_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": ["EP01_DLG0001"],
        "extractionRun": _extraction_run(),
        "existingCharacterId": "CHAR_B",
        "sourceCharacterId": None,
        "nameCandidates": ["B"],
        "fields": {},
    }
    document["characters"] = [character_a, character_b]
    path = _write_document(tmp_path, "ep01.json", document)
    output_dir = tmp_path / "merge_preview"

    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(path),
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
    summary = data["report"]["relationshipTypeSummary"]
    assert summary["knownTypes"].get("affiliated_with") == 1
