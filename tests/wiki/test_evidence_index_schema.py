"""
tests/wiki/test_evidence_index_schema.py
schemas/evidence_index.schema.json の軽量な整合性テスト。

合成データ (docs/templates/evidence_index_template.yaml、およびテスト内で
組み立てる合成dict) のみを使う。実イベント名・実キャラ名・実あらすじ・
実セリフは一切含まない (docs/architecture/06_AI/Evidence_Index_Design.md 参照)。
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "evidence_index.schema.json"
TEMPLATE_PATH = PROJECT_ROOT / "docs" / "templates" / "evidence_index_template.yaml"

_REAL_STORY_TERMS = ("レイン", "赤城陽菜", "デタリキ")


def _load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _validate(document: dict) -> list[str]:
    errors = sorted(
        Draft7Validator(_load_schema()).iter_errors(document),
        key=lambda e: list(e.path),
    )
    return [f"{list(e.path)}: {e.message}" for e in errors]


def _entry(**overrides) -> dict:
    entry = {
        "evidenceId": "EVT_SYNTHETIC_SAMPLE_E01_DLG0001",
        "evidenceType": "dialogue",
        "storyId": "EVT_SYNTHETIC_SAMPLE",
        "publicStoryId": None,
        "episodeId": "EVT_SYNTHETIC_SAMPLE_E01",
        "publicEpisodeId": None,
        "sceneId": None,
        "blockId": None,
        "speaker": None,
        "relatedEntities": [],
        "referencedBy": None,
        "visibility": {"public": True, "rawTextIncluded": False},
        "notes": None,
    }
    entry.update(overrides)
    return entry


def _document(**overrides) -> dict:
    doc = {
        "evidenceIndexVersion": 1,
        "generatedFrom": None,
        "entries": [_entry()],
        "notes": None,
    }
    doc.update(overrides)
    return doc


# ----------------------------------------------------------------
# schemaファイル自体
# ----------------------------------------------------------------


def test_schema_file_exists():
    assert SCHEMA_PATH.is_file()


def test_schema_is_valid_json():
    _load_schema()


# ----------------------------------------------------------------
# template
# ----------------------------------------------------------------


def test_template_exists():
    assert TEMPLATE_PATH.is_file()


def test_template_validates_against_schema():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert _validate(document) == []


def test_template_does_not_contain_real_story_terms():
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    for term in _REAL_STORY_TERMS:
        assert term not in content


def test_template_all_entries_have_raw_text_included_false():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    for entry in document["entries"]:
        assert entry["visibility"]["rawTextIncluded"] is False


# ----------------------------------------------------------------
# 合成データでのschema検証: 基本
# ----------------------------------------------------------------


def test_minimal_document_is_valid():
    assert _validate(_document()) == []


def test_document_with_empty_entries_is_valid():
    assert _validate(_document(entries=[])) == []


def test_document_with_full_entry_is_valid():
    document = _document(
        entries=[
            _entry(
                publicStoryId="EVT_TEST_PUBLIC_001",
                publicEpisodeId="EVT_TEST_PUBLIC_001_E01",
                sceneId="EVT_SYNTHETIC_SAMPLE_E01_SC001",
                blockId="EVT_SYNTHETIC_SAMPLE_E01_DLG0001",
                speaker={
                    "speakerId": "CHAR_TEST_001",
                    "displayName": "Synthetic Speaker",
                    "resolutionStatus": "resolved",
                },
                relatedEntities=[
                    {
                        "entityType": "character",
                        "id": "CHAR_TEST_001",
                        "displayName": "Synthetic Speaker",
                    }
                ],
                referencedBy={
                    "summaries": [
                        {
                            "storyId": "EVT_SYNTHETIC_SAMPLE",
                            "summaryType": "episode",
                            "episodeId": "EVT_SYNTHETIC_SAMPLE_E01",
                        }
                    ],
                    "candidates": [
                        {"candidateId": "CAND_TEST_001", "entityType": "character"}
                    ],
                },
            )
        ]
    )
    assert _validate(document) == []


# ----------------------------------------------------------------
# 必須フィールド
# ----------------------------------------------------------------


def test_rejects_missing_evidence_index_version():
    document = _document()
    del document["evidenceIndexVersion"]
    assert _validate(document) != []


def test_rejects_missing_entries():
    document = _document()
    del document["entries"]
    assert _validate(document) != []


def test_generated_from_is_optional():
    document = _document()
    del document["generatedFrom"]
    assert _validate(document) == []


def test_notes_is_optional():
    document = _document()
    del document["notes"]
    assert _validate(document) == []


def test_entry_requires_evidence_id():
    document = _document(
        entries=[
            {
                "evidenceType": "dialogue",
                "storyId": "X",
                "episodeId": "X_E01",
                "visibility": {"public": True, "rawTextIncluded": False},
            }
        ]
    )
    assert _validate(document) != []


def test_entry_requires_evidence_type():
    entry = _entry()
    del entry["evidenceType"]
    assert _validate(_document(entries=[entry])) != []


def test_entry_requires_story_id():
    entry = _entry()
    del entry["storyId"]
    assert _validate(_document(entries=[entry])) != []


def test_entry_requires_episode_id():
    entry = _entry()
    del entry["episodeId"]
    assert _validate(_document(entries=[entry])) != []


def test_entry_requires_visibility():
    entry = _entry()
    del entry["visibility"]
    assert _validate(_document(entries=[entry])) != []


def test_entry_optional_fields_can_be_omitted():
    entry = {
        "evidenceId": "EVT_SYNTHETIC_SAMPLE_E01_DLG0001",
        "evidenceType": "dialogue",
        "storyId": "EVT_SYNTHETIC_SAMPLE",
        "episodeId": "EVT_SYNTHETIC_SAMPLE_E01",
        "visibility": {"public": True, "rawTextIncluded": False},
    }
    assert _validate(_document(entries=[entry])) == []


def test_visibility_requires_public():
    entry = _entry(visibility={"rawTextIncluded": False})
    assert _validate(_document(entries=[entry])) != []


def test_visibility_requires_raw_text_included():
    entry = _entry(visibility={"public": True})
    assert _validate(_document(entries=[entry])) != []


# ----------------------------------------------------------------
# ID format validation
# ----------------------------------------------------------------


def test_rejects_invalid_evidence_id_format():
    document = _document(entries=[_entry(evidenceId="not-a-valid-id")])
    assert _validate(document) != []


def test_rejects_invalid_story_id_format():
    document = _document(entries=[_entry(storyId="not-a-valid-id")])
    assert _validate(document) != []


def test_rejects_invalid_public_story_id_format():
    document = _document(entries=[_entry(publicStoryId="not-a-valid-id")])
    assert _validate(document) != []


def test_public_story_id_null_is_valid():
    document = _document(entries=[_entry(publicStoryId=None)])
    assert _validate(document) == []


def test_rejects_invalid_related_entity_id_format():
    entry = _entry(
        relatedEntities=[{"entityType": "character", "id": "not-a-valid-id"}]
    )
    assert _validate(_document(entries=[entry])) != []


# ----------------------------------------------------------------
# evidenceType enum
# ----------------------------------------------------------------


def test_all_evidence_types_are_valid():
    for evidence_type in (
        "dialogue",
        "monologue",
        "narration",
        "choice",
        "stage_direction",
        "speaker_label",
        "scene",
        "episode",
        "story",
        "unknown",
    ):
        document = _document(entries=[_entry(evidenceType=evidence_type)])
        assert _validate(document) == [], f"failed for {evidence_type}"


def test_rejects_unknown_evidence_type():
    document = _document(entries=[_entry(evidenceType="not_a_real_type")])
    assert _validate(document) != []


def test_rejects_raw_command_as_evidence_type():
    document = _document(entries=[_entry(evidenceType="@ChTalk")])
    assert _validate(document) != []


# ----------------------------------------------------------------
# visibility.rawTextIncluded
# ----------------------------------------------------------------


def test_rejects_raw_text_included_true():
    document = _document(
        entries=[_entry(visibility={"public": True, "rawTextIncluded": True})]
    )
    assert _validate(document) != []


def test_accepts_raw_text_included_false():
    document = _document(
        entries=[_entry(visibility={"public": True, "rawTextIncluded": False})]
    )
    assert _validate(document) == []


# ----------------------------------------------------------------
# speaker
# ----------------------------------------------------------------


def test_all_speaker_resolution_statuses_are_valid():
    for status in ("resolved", "unresolved", "ambiguous", "unknown"):
        entry = _entry(
            speaker={
                "speakerId": None,
                "displayName": "Synthetic Speaker",
                "resolutionStatus": status,
            }
        )
        assert _validate(_document(entries=[entry])) == [], f"failed for {status}"


def test_rejects_unknown_speaker_resolution_status():
    entry = _entry(
        speaker={
            "speakerId": None,
            "displayName": "Synthetic Speaker",
            "resolutionStatus": "not_a_real_status",
        }
    )
    assert _validate(_document(entries=[entry])) != []


def test_speaker_null_is_valid():
    document = _document(entries=[_entry(speaker=None)])
    assert _validate(document) == []


# ----------------------------------------------------------------
# relatedEntities
# ----------------------------------------------------------------


def test_related_entities_valid():
    entry = _entry(
        relatedEntities=[
            {
                "entityType": "character",
                "id": "CHAR_TEST_001",
                "displayName": "Synthetic",
            }
        ]
    )
    assert _validate(_document(entries=[entry])) == []


def test_rejects_unknown_related_entity_type():
    entry = _entry(
        relatedEntities=[{"entityType": "not_a_real_type", "id": "CHAR_TEST_001"}]
    )
    assert _validate(_document(entries=[entry])) != []


def test_related_entity_requires_id():
    entry = _entry(relatedEntities=[{"entityType": "character"}])
    assert _validate(_document(entries=[entry])) != []


# ----------------------------------------------------------------
# referencedBy
# ----------------------------------------------------------------


def test_referenced_by_summaries_valid():
    entry = _entry(
        referencedBy={
            "summaries": [
                {
                    "storyId": "EVT_SYNTHETIC_SAMPLE",
                    "summaryType": "story",
                }
            ],
            "candidates": [],
        }
    )
    assert _validate(_document(entries=[entry])) == []


def test_referenced_by_candidates_valid():
    entry = _entry(
        referencedBy={
            "summaries": [],
            "candidates": [{"candidateId": "CAND_TEST_001", "entityType": "character"}],
        }
    )
    assert _validate(_document(entries=[entry])) == []


def test_rejects_unknown_summary_type():
    entry = _entry(
        referencedBy={
            "summaries": [
                {"storyId": "EVT_SYNTHETIC_SAMPLE", "summaryType": "not_a_type"}
            ],
            "candidates": [],
        }
    )
    assert _validate(_document(entries=[entry])) != []


def test_referenced_by_null_is_valid():
    document = _document(entries=[_entry(referencedBy=None)])
    assert _validate(document) == []


# ----------------------------------------------------------------
# additionalProperties
# ----------------------------------------------------------------


def test_rejects_additional_properties_at_top_level():
    document = _document(unexpectedField="not allowed")
    assert _validate(document) != []


def test_rejects_additional_properties_in_entry():
    entry = _entry(unexpectedField="not allowed")
    assert _validate(_document(entries=[entry])) != []


def test_rejects_additional_properties_in_visibility():
    entry = _entry(
        visibility={
            "public": True,
            "rawTextIncluded": False,
            "unexpectedField": "not allowed",
        }
    )
    assert _validate(_document(entries=[entry])) != []
