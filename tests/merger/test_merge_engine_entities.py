"""
tests/merger/test_merge_engine_entities.py
MergeEngine経由でCharacter/Location/Organizationのmerged entityが生成され、
schemas/merged_knowledge.schema.json (個別entity) と
schemas/merged_knowledge_collection.schema.json (collection全体) の
両方に通ることを確認する統合テスト。

Item/Lore/Event/Relationship/Timelineは今回もentities配下が空のままである
ことも合わせて確認する。実データ・data/extracted/生成物は使わない。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from agents.merger import MergeEngine

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
ENTITY_SCHEMA_PATH = SCHEMAS_DIR / "merged_knowledge.schema.json"
COLLECTION_SCHEMA_PATH = SCHEMAS_DIR / "merged_knowledge_collection.schema.json"
MERGE_SCRIPT = PROJECT_ROOT / "scripts" / "merge_extractions.py"


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


def _episode_with_resolved_candidates(episode_id: str) -> dict:
    """existingCharacterId/existingLocationId/existingOrganizationIdを
    それぞれ持つ最小episode_extractionを組み立てる。
    """
    return {
        "schemaVersion": "0.1",
        "documentType": "episode_extraction",
        "episodeId": episode_id,
        "storyId": "TEST_STORY",
        "storyCategory": "MAIN",
        "extractionRun": _extraction_run(),
        "evidenceIndex": {
            f"{episode_id}_DLG0001": {
                "sourceId": f"{episode_id}_DLG0001",
                "storyId": "TEST_STORY",
                "episodeId": episode_id,
                "sceneId": f"{episode_id}_SC001",
                "confidence": 1.0,
            },
            f"{episode_id}_SC001": {
                "sourceId": f"{episode_id}_SC001",
                "storyId": "TEST_STORY",
                "episodeId": episode_id,
                "sceneId": f"{episode_id}_SC001",
                "confidence": 1.0,
            },
        },
        "characters": [
            {
                "id": f"{episode_id}_CAND_CHAR001",
                "type": "character_candidate",
                "sourceType": "script",
                "confidence": 0.9,
                "evidenceIds": [f"{episode_id}_DLG0001"],
                "extractionRun": _extraction_run(),
                "existingCharacterId": "CHAR_RAIN",
                "sourceCharacterId": "26",
                "nameCandidates": ["レイン"],
                "fields": {},
            }
        ],
        "organizations": [
            {
                "id": f"{episode_id}_CAND_ORG001",
                "type": "organization_candidate",
                "sourceType": "script",
                "confidence": 0.9,
                "evidenceIds": [f"{episode_id}_DLG0001"],
                "extractionRun": _extraction_run(),
                "existingOrganizationId": "ORG_TAISAKUHAN",
                "nameCandidates": ["異形生物対策班"],
                "fields": {},
            }
        ],
        "locations": [
            {
                "id": f"{episode_id}_CAND_LOC001",
                "type": "location_candidate",
                "sourceType": "script",
                "confidence": 0.9,
                "evidenceIds": [f"{episode_id}_SC001"],
                "extractionRun": _extraction_run(),
                "existingLocationId": "LOC_HQ",
                "nameCandidates": ["本部"],
                "sceneRefs": [f"{episode_id}_SC001"],
                "fields": {},
            }
        ],
        "items": [],
        "lore": [],
        "events": [],
        "relationships": [],
        "timelineCandidates": [],
        "extractionErrors": [],
    }


def _episode_with_all_merge_candidates(episode_id: str) -> dict:
    """Character/Location/Organization/Item/Lore/Eventすべてについて
    existing*Idを持つ最小episode_extractionを組み立てる
    (relationships/timelineCandidatesは今回もmerge対象外のため空のまま)。
    """
    doc = _episode_with_resolved_candidates(episode_id)
    doc["evidenceIndex"][f"{episode_id}_NAR0001"] = {
        "sourceId": f"{episode_id}_NAR0001",
        "storyId": "TEST_STORY",
        "episodeId": episode_id,
        "sceneId": f"{episode_id}_SC001",
        "confidence": 1.0,
    }
    doc["items"] = [
        {
            "id": f"{episode_id}_CAND_ITEM001",
            "type": "item_candidate",
            "sourceType": "script",
            "confidence": 0.85,
            "evidenceIds": [f"{episode_id}_DLG0001"],
            "extractionRun": _extraction_run(),
            "existingItemId": "ITEM_DETARIKI",
            "nameCandidates": ["デタリキ"],
            "fields": {},
        }
    ]
    doc["lore"] = [
        {
            "id": f"{episode_id}_CAND_LORE001",
            "type": "lore_candidate",
            "sourceType": "script",
            "confidence": 0.8,
            "evidenceIds": [f"{episode_id}_DLG0001"],
            "extractionRun": _extraction_run(),
            "existingLoreId": "LORE_DETARIKI_Z",
            "termCandidates": ["デタリキZ"],
            "fields": {},
        }
    ]
    doc["events"] = [
        {
            "id": f"{episode_id}_CAND_EVENT001",
            "type": "event_candidate",
            "sourceType": "ai_extracted",
            "confidence": 0.75,
            "evidenceIds": [f"{episode_id}_NAR0001"],
            "extractionRun": _extraction_run(),
            "existingEventId": "EVENT_JAMMER_FIRST",
            "nameCandidates": ["ジャマー初出現"],
            "participantCandidates": [],
            "locationCandidates": [],
            "fields": {},
        }
    ]
    return doc


def _episode_with_relationship_candidate(episode_id: str) -> dict:
    """_episode_with_all_merge_candidatesに、既存のCharacter/Organization
    candidateを参照するRelationshipCandidateを追加した最小episode_extraction。
    """
    doc = _episode_with_all_merge_candidates(episode_id)
    doc["relationships"] = [
        {
            "id": f"{episode_id}_CAND_REL001",
            "type": "relationship_candidate",
            "sourceType": "script",
            "confidence": 0.9,
            "evidenceIds": [f"{episode_id}_DLG0001"],
            "extractionRun": _extraction_run(),
            "existingRelationshipId": None,
            "sourceCandidate": f"{episode_id}_CAND_CHAR001",
            "targetCandidate": f"{episode_id}_CAND_ORG001",
            "relationshipType": "MEMBER_OF",
            "direction": "source_to_target",
            "temporalNote": None,
            "fields": {},
        }
    ]
    return doc


def _episode_with_timeline_candidate(episode_id: str) -> dict:
    """_episode_with_relationship_candidateに、既存evidenceを参照する
    TimelineCandidateを追加した最小episode_extraction
    (Character/Location/Organization/Item/Lore/Event/Relationship/Timeline
    すべてが揃う)。
    """
    doc = _episode_with_relationship_candidate(episode_id)
    doc["timelineCandidates"] = [
        {
            "id": f"{episode_id}_CAND_TL001",
            "type": "timeline_candidate",
            "sourceType": "script",
            "confidence": 0.7,
            "evidenceIds": [f"{episode_id}_DLG0001"],
            "extractionRun": _extraction_run(),
            "kind": "explicit_order",
            "scope": "episode",
            "relativeTo": None,
            "relation": None,
            "sourceTimelineId": "TL_ARC1",
            "nameCandidates": ["第一部"],
            "orderValue": 1,
            "orderField": "canonicalOrder",
            "markerType": None,
            "fields": {},
        }
    ]
    return doc


@pytest.fixture
def entity_validator() -> Draft7Validator:
    with open(ENTITY_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


@pytest.fixture
def collection_validator() -> Draft7Validator:
    with open(COLLECTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


@pytest.fixture
def engine() -> MergeEngine:
    return MergeEngine()


# ----------------------------------------------------------------
# 1. MergeEngine経由でCharacter/Location/Organizationが生成される
# ----------------------------------------------------------------


def test_merge_engine_produces_character_location_organization_entities(
    engine, tmp_path
):
    doc = _episode_with_resolved_candidates("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    entities = collection["entities"]

    assert len(entities["characters"]) == 1
    assert len(entities["locations"]) == 1
    assert len(entities["organizations"]) == 1
    assert entities["characters"][0]["id"] == "CHAR_RAIN"
    assert entities["locations"][0]["id"] == "LOC_HQ"
    assert entities["organizations"][0]["id"] == "ORG_TAISAKUHAN"
    for key in ("items", "lore", "events", "relationships", "timeline"):
        assert entities[key] == []


def test_merged_entity_counts_in_report(engine, tmp_path):
    doc = _episode_with_resolved_candidates("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    counts = collection["report"]["mergedEntityCounts"]

    assert counts["characters"] == 1
    assert counts["locations"] == 1
    assert counts["organizations"] == 1
    assert counts["items"] == 0
    assert collection["report"]["conflictsCount"] == 0
    assert collection["report"]["unresolvedCount"] == 0


def test_entities_aggregate_across_multiple_episodes(engine, tmp_path):
    doc1 = _episode_with_resolved_candidates("EP01")
    doc2 = _episode_with_resolved_candidates("EP02")
    path1 = tmp_path / "EP01.extraction.json"
    path2 = tmp_path / "EP02.extraction.json"
    with open(path1, "w", encoding="utf-8") as f:
        json.dump(doc1, f, ensure_ascii=False)
    with open(path2, "w", encoding="utf-8") as f:
        json.dump(doc2, f, ensure_ascii=False)

    collection = engine.merge_inputs([str(path1), str(path2)])
    entities = collection["entities"]

    # 同一existingCharacterId/existingLocationId/existingOrganizationIdは
    # 2エピソードにまたがっても1entityへ統合される
    assert len(entities["characters"]) == 1
    assert len(entities["locations"]) == 1
    assert len(entities["organizations"]) == 1
    assert set(entities["characters"][0]["mergedFrom"]) == {"EP01", "EP02"}


def test_merge_engine_produces_item_lore_event_entities(engine, tmp_path):
    doc = _episode_with_all_merge_candidates("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    entities = collection["entities"]

    assert len(entities["items"]) == 1
    assert len(entities["lore"]) == 1
    assert len(entities["events"]) == 1
    assert entities["items"][0]["id"] == "ITEM_DETARIKI"
    assert entities["lore"][0]["id"] == "LORE_DETARIKI_Z"
    assert entities["events"][0]["id"] == "EVENT_JAMMER_FIRST"
    # Relationship/Timelineは今回もmerge対象外
    assert entities["relationships"] == []
    assert entities["timeline"] == []


def test_merged_entity_counts_include_item_lore_event(engine, tmp_path):
    doc = _episode_with_all_merge_candidates("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    counts = collection["report"]["mergedEntityCounts"]

    assert counts["characters"] == 1
    assert counts["locations"] == 1
    assert counts["organizations"] == 1
    assert counts["items"] == 1
    assert counts["lore"] == 1
    assert counts["events"] == 1
    assert counts["relationships"] == 0
    assert counts["timeline"] == 0


def test_item_lore_event_entities_aggregate_across_episodes(engine, tmp_path):
    doc1 = _episode_with_all_merge_candidates("EP01")
    doc2 = _episode_with_all_merge_candidates("EP02")
    path1 = tmp_path / "EP01.extraction.json"
    path2 = tmp_path / "EP02.extraction.json"
    with open(path1, "w", encoding="utf-8") as f:
        json.dump(doc1, f, ensure_ascii=False)
    with open(path2, "w", encoding="utf-8") as f:
        json.dump(doc2, f, ensure_ascii=False)

    collection = engine.merge_inputs([str(path1), str(path2)])
    entities = collection["entities"]

    assert len(entities["items"]) == 1
    assert len(entities["lore"]) == 1
    assert len(entities["events"]) == 1
    assert set(entities["items"][0]["mergedFrom"]) == {"EP01", "EP02"}


def test_generated_item_lore_event_entities_pass_entity_schema(
    entity_validator, engine, tmp_path
):
    doc = _episode_with_all_merge_candidates("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    entities = collection["entities"]

    for key in ("items", "lore", "events"):
        for entity in entities[key]:
            errors = list(entity_validator.iter_errors(entity))
            assert not errors, f"{key}: {[e.message for e in errors]}"


def test_collection_with_item_lore_event_entities_passes_collection_schema(
    collection_validator, engine, tmp_path
):
    doc = _episode_with_all_merge_candidates("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    errors = list(collection_validator.iter_errors(collection))
    assert not errors, [e.message for e in errors]


def test_cli_output_with_item_lore_event_entities_passes_collection_schema(
    collection_validator, tmp_path
):
    doc = _episode_with_all_merge_candidates("EP01")
    input_path = tmp_path / "EP01.extraction.json"
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

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

    errors = list(collection_validator.iter_errors(data))
    assert not errors, [e.message for e in errors]
    assert len(data["entities"]["items"]) == 1
    assert len(data["entities"]["lore"]) == 1
    assert len(data["entities"]["events"]) == 1


def test_merge_engine_produces_relationship_entity(engine, tmp_path):
    doc = _episode_with_relationship_candidate("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    entities = collection["entities"]

    assert len(entities["relationships"]) == 1
    relationship = entities["relationships"][0]
    assert relationship["sourceEntityId"] == "CHAR_RAIN"
    assert relationship["targetEntityId"] == "ORG_TAISAKUHAN"
    assert relationship["relationshipType"] == "MEMBER_OF"
    assert relationship["status"] == "merged"
    # Timelineは今回もmerge対象外
    assert entities["timeline"] == []


def test_merged_entity_counts_include_relationships(engine, tmp_path):
    doc = _episode_with_relationship_candidate("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    counts = collection["report"]["mergedEntityCounts"]

    assert counts["relationships"] == 1
    assert counts["timeline"] == 0


def test_relationship_entities_aggregate_across_episodes(engine, tmp_path):
    doc1 = _episode_with_relationship_candidate("EP01")
    doc2 = _episode_with_relationship_candidate("EP02")
    path1 = tmp_path / "EP01.extraction.json"
    path2 = tmp_path / "EP02.extraction.json"
    with open(path1, "w", encoding="utf-8") as f:
        json.dump(doc1, f, ensure_ascii=False)
    with open(path2, "w", encoding="utf-8") as f:
        json.dump(doc2, f, ensure_ascii=False)

    collection = engine.merge_inputs([str(path1), str(path2)])
    entities = collection["entities"]

    assert len(entities["relationships"]) == 1
    assert set(entities["relationships"][0]["mergedFrom"]) == {"EP01", "EP02"}


def test_unresolvable_relationship_is_recorded_as_warning_not_crash(engine, tmp_path):
    doc = _episode_with_all_merge_candidates("EP01")
    doc["relationships"] = [
        {
            "id": "EP01_CAND_REL001",
            "type": "relationship_candidate",
            "sourceType": "script",
            "confidence": 0.6,
            "evidenceIds": ["EP01_DLG0001"],
            "extractionRun": _extraction_run(),
            "existingRelationshipId": None,
            "sourceCandidate": "謎の人物",
            "targetCandidate": "ORG_TAISAKUHAN",
            "relationshipType": "MEMBER_OF",
            "direction": "source_to_target",
            "temporalNote": None,
            "fields": {},
        }
    ]
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)

    assert collection["entities"]["relationships"] == []
    assert any(
        "sourceCandidate" in warning for warning in collection["report"]["warnings"]
    )


def test_generated_relationship_entity_passes_entity_schema(
    entity_validator, engine, tmp_path
):
    doc = _episode_with_relationship_candidate("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)

    for entity in collection["entities"]["relationships"]:
        errors = list(entity_validator.iter_errors(entity))
        assert not errors, [e.message for e in errors]


def test_collection_with_relationship_entity_passes_collection_schema(
    collection_validator, engine, tmp_path
):
    doc = _episode_with_relationship_candidate("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    errors = list(collection_validator.iter_errors(collection))
    assert not errors, [e.message for e in errors]


def test_cli_output_with_relationship_entity_passes_collection_schema(
    collection_validator, tmp_path
):
    doc = _episode_with_relationship_candidate("EP01")
    input_path = tmp_path / "EP01.extraction.json"
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

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

    errors = list(collection_validator.iter_errors(data))
    assert not errors, [e.message for e in errors]
    assert len(data["entities"]["relationships"]) == 1
    assert data["entities"]["timeline"] == []


def test_merge_engine_produces_timeline_entity(engine, tmp_path):
    doc = _episode_with_timeline_candidate("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    entities = collection["entities"]

    assert len(entities["timeline"]) == 1
    timeline_entry = entities["timeline"][0]
    assert timeline_entry["sourceTimelineId"] == "TL_ARC1"
    assert timeline_entry["label"] == "第一部"
    assert timeline_entry["status"] == "unresolved"
    # Relationshipとの共存確認 (既存のresolved candidateも引き続き生成される)
    assert len(entities["relationships"]) == 1


def test_merged_entity_counts_include_timeline(engine, tmp_path):
    doc = _episode_with_timeline_candidate("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    counts = collection["report"]["mergedEntityCounts"]

    assert counts["timeline"] == 1
    assert counts["relationships"] == 1


def test_timeline_entities_aggregate_across_episodes(engine, tmp_path):
    doc1 = _episode_with_timeline_candidate("EP01")
    doc2 = _episode_with_timeline_candidate("EP02")
    path1 = tmp_path / "EP01.extraction.json"
    path2 = tmp_path / "EP02.extraction.json"
    with open(path1, "w", encoding="utf-8") as f:
        json.dump(doc1, f, ensure_ascii=False)
    with open(path2, "w", encoding="utf-8") as f:
        json.dump(doc2, f, ensure_ascii=False)

    collection = engine.merge_inputs([str(path1), str(path2)])
    entities = collection["entities"]

    assert len(entities["timeline"]) == 1
    assert set(entities["timeline"][0]["mergedFrom"]) == {"EP01", "EP02"}


def test_generated_timeline_entity_passes_entity_schema(
    entity_validator, engine, tmp_path
):
    doc = _episode_with_timeline_candidate("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)

    for entity in collection["entities"]["timeline"]:
        errors = list(entity_validator.iter_errors(entity))
        assert not errors, [e.message for e in errors]


def test_collection_with_timeline_entity_passes_collection_schema(
    collection_validator, engine, tmp_path
):
    doc = _episode_with_timeline_candidate("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    errors = list(collection_validator.iter_errors(collection))
    assert not errors, [e.message for e in errors]


def test_cli_output_with_timeline_entity_passes_collection_schema(
    collection_validator, tmp_path
):
    doc = _episode_with_timeline_candidate("EP01")
    input_path = tmp_path / "EP01.extraction.json"
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

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

    errors = list(collection_validator.iter_errors(data))
    assert not errors, [e.message for e in errors]
    assert len(data["entities"]["timeline"]) == 1
    assert len(data["entities"]["relationships"]) == 1


# ----------------------------------------------------------------
# 2. 生成されたentityがmerged_knowledge.schema.jsonに通る
# ----------------------------------------------------------------


def test_generated_entities_pass_entity_schema(entity_validator, engine, tmp_path):
    doc = _episode_with_resolved_candidates("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    entities = collection["entities"]

    for key in ("characters", "locations", "organizations"):
        for entity in entities[key]:
            errors = list(entity_validator.iter_errors(entity))
            assert not errors, f"{key}: {[e.message for e in errors]}"


# ----------------------------------------------------------------
# 3. collectionがmerged_knowledge_collection.schema.jsonに通る
# ----------------------------------------------------------------


def test_collection_with_merged_entities_passes_collection_schema(
    collection_validator, engine, tmp_path
):
    doc = _episode_with_resolved_candidates("EP01")
    path = tmp_path / "EP01.extraction.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    collection = engine.merge_file(path)
    errors = list(collection_validator.iter_errors(collection))
    assert not errors, [e.message for e in errors]


# ----------------------------------------------------------------
# CLI連携
# ----------------------------------------------------------------


def test_cli_output_with_merged_entities_passes_collection_schema(
    collection_validator, tmp_path
):
    doc = _episode_with_resolved_candidates("EP01")
    input_path = tmp_path / "EP01.extraction.json"
    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

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

    errors = list(collection_validator.iter_errors(data))
    assert not errors, [e.message for e in errors]
    assert len(data["entities"]["characters"]) == 1
