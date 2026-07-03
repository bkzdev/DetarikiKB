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
