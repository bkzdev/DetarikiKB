"""
tests/wiki/test_story_summary_schema.py
schemas/story_summary.schema.json の軽量な整合性テスト。

合成データ (docs/templates/story_summary_template.yaml、およびテスト内で
組み立てる合成dict) のみを使う。実イベント名・実キャラ名・実あらすじ・
実セリフは一切含まない (docs/architecture/06_AI/Story_Summary_Design.md 参照)。
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "story_summary.schema.json"
TEMPLATE_PATH = PROJECT_ROOT / "docs" / "templates" / "story_summary_template.yaml"

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


def _document(**overrides) -> dict:
    doc = {
        "schemaVersion": "0.1.0",
        "documentType": "story_summary",
        "storyId": "EVT_SYNTHETIC_SAMPLE",
        "publicStoryId": None,
        "language": "ja",
        "generationStatus": "generated",
        "storySummary": None,
        "episodeSummaries": [],
        "source": {
            "sourceType": "manual",
            "model": None,
            "promptVersion": None,
            "generatedAt": None,
            "inputRefs": [],
        },
        "review": {
            "status": "reviewed",
            "reviewer": None,
            "reviewedAt": None,
            "notes": None,
        },
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


# ----------------------------------------------------------------
# 合成データでのschema検証: 基本
# ----------------------------------------------------------------


def test_minimal_document_is_valid():
    assert _validate(_document()) == []


def test_document_with_story_summary_and_episode_summaries_is_valid():
    document = _document(
        storySummary={
            "text": "合成要約です。",
            "confidence": 0.7,
            "evidenceRefs": ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"],
        },
        episodeSummaries=[
            {
                "episodeId": "EVT_SYNTHETIC_SAMPLE_E01",
                "publicEpisodeId": "PUB_E01",
                "episodeNumber": 1,
                "text": "合成episode要約です。",
                "confidence": 0.6,
                "evidenceRefs": ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"],
            }
        ],
    )
    assert _validate(document) == []


def test_document_with_empty_episode_summaries_is_valid():
    """Story Summaryのみ先に生成されるケース (episodeSummaries空配列)。"""
    document = _document(
        storySummary={"text": "合成要約です。", "confidence": None, "evidenceRefs": []}
    )
    assert _validate(document) == []


def test_document_with_null_story_summary_is_valid():
    """storySummary未生成のケース。"""
    assert _validate(_document(storySummary=None)) == []


# ----------------------------------------------------------------
# 必須フィールド
# ----------------------------------------------------------------


def test_rejects_missing_story_id():
    document = _document()
    del document["storyId"]
    assert _validate(document) != []


def test_rejects_missing_language():
    document = _document()
    del document["language"]
    assert _validate(document) != []


def test_rejects_missing_generation_status():
    document = _document()
    del document["generationStatus"]
    assert _validate(document) != []


def test_rejects_missing_episode_summaries():
    document = _document()
    del document["episodeSummaries"]
    assert _validate(document) != []


def test_rejects_missing_source():
    document = _document()
    del document["source"]
    assert _validate(document) != []


def test_rejects_missing_review():
    document = _document()
    del document["review"]
    assert _validate(document) != []


def test_public_story_id_is_optional():
    document = _document()
    del document["publicStoryId"]
    assert _validate(document) == []


def test_notes_is_optional():
    document = _document()
    del document["notes"]
    assert _validate(document) == []


def test_episode_summary_requires_episode_id():
    document = _document(episodeSummaries=[{"text": "テキストのみ、episodeId欠落"}])
    assert _validate(document) != []


def test_episode_summary_requires_text():
    document = _document(episodeSummaries=[{"episodeId": "EVT_SYNTHETIC_SAMPLE_E01"}])
    assert _validate(document) != []


def test_story_summary_requires_text_when_present():
    document = _document(storySummary={"confidence": 0.5})
    assert _validate(document) != []


def test_source_requires_source_type():
    document = _document()
    document["source"] = {"model": None}
    assert _validate(document) != []


def test_review_requires_status():
    document = _document()
    document["review"] = {"reviewer": None}
    assert _validate(document) != []


# ----------------------------------------------------------------
# ID format validation
# ----------------------------------------------------------------


def test_rejects_invalid_story_id_format():
    document = _document(storyId="not-a-valid-id")
    assert _validate(document) != []


def test_rejects_invalid_public_story_id_format():
    document = _document(publicStoryId="not-a-valid-id")
    assert _validate(document) != []


def test_accepts_valid_public_story_id_format():
    document = _document(publicStoryId="EVT_TEST_PUBLIC_001")
    assert _validate(document) == []


def test_rejects_invalid_episode_id_format():
    document = _document(
        episodeSummaries=[{"episodeId": "not-a-valid-id", "text": "合成テキスト"}]
    )
    assert _validate(document) != []


def test_rejects_invalid_public_episode_id_format():
    document = _document(
        episodeSummaries=[
            {
                "episodeId": "EVT_SYNTHETIC_SAMPLE_E01",
                "publicEpisodeId": "not-a-valid-id",
                "text": "合成テキスト",
            }
        ]
    )
    assert _validate(document) != []


def test_public_episode_id_null_is_valid():
    document = _document(
        episodeSummaries=[
            {
                "episodeId": "EVT_SYNTHETIC_SAMPLE_E01",
                "publicEpisodeId": None,
                "text": "合成テキスト",
            }
        ]
    )
    assert _validate(document) == []


# ----------------------------------------------------------------
# evidenceRefs
# ----------------------------------------------------------------


def test_valid_evidence_refs_pass():
    document = _document(
        storySummary={
            "text": "合成テキスト",
            "evidenceRefs": [
                "EVT_SYNTHETIC_SAMPLE_E01_DLG0001",
                "EVT_SYNTHETIC_SAMPLE_E01_SC001",
            ],
        }
    )
    assert _validate(document) == []


def test_invalid_evidence_ref_format_fails():
    document = _document(
        storySummary={
            "text": "合成テキスト",
            "evidenceRefs": ["not a valid ref!"],
        }
    )
    assert _validate(document) != []


def test_evidence_refs_not_required():
    document = _document(storySummary={"text": "合成テキスト"})
    assert _validate(document) == []


def test_episode_summary_evidence_refs_validated():
    document = _document(
        episodeSummaries=[
            {
                "episodeId": "EVT_SYNTHETIC_SAMPLE_E01",
                "text": "合成テキスト",
                "evidenceRefs": ["invalid ref"],
            }
        ]
    )
    assert _validate(document) != []


# ----------------------------------------------------------------
# enum方針
# ----------------------------------------------------------------


def test_rejects_unknown_generation_status():
    document = _document(generationStatus="not_a_real_status")
    assert _validate(document) != []


def test_all_generation_statuses_are_valid():
    for status in ("missing", "draft", "generated", "deprecated"):
        document = _document(generationStatus=status)
        assert _validate(document) == [], f"failed for {status}"


def test_rejects_unknown_review_status():
    document = _document()
    document["review"]["status"] = "not_a_real_status"
    assert _validate(document) != []


def test_all_review_statuses_are_valid():
    for status in (
        "unreviewed",
        "reviewed",
        "approved",
        "rejected",
        "needs_revision",
    ):
        document = _document()
        document["review"]["status"] = status
        assert _validate(document) == [], f"failed for {status}"


def test_rejects_unknown_source_type():
    document = _document()
    document["source"]["sourceType"] = "not_a_real_type"
    assert _validate(document) != []


def test_all_source_types_are_valid():
    for source_type in ("manual", "ai_generated", "imported", "unknown"):
        document = _document()
        document["source"]["sourceType"] = source_type
        assert _validate(document) == [], f"failed for {source_type}"


def test_rejects_wrong_document_type():
    document = _document()
    document["documentType"] = "not_story_summary"
    assert _validate(document) != []


def test_rejects_additional_properties_at_top_level():
    document = _document(unexpectedField="not allowed")
    assert _validate(document) != []


def test_rejects_additional_properties_in_episode_summary():
    document = _document(
        episodeSummaries=[
            {
                "episodeId": "EVT_SYNTHETIC_SAMPLE_E01",
                "text": "合成テキスト",
                "unexpectedField": "not allowed",
            }
        ]
    )
    assert _validate(document) != []


# ----------------------------------------------------------------
# confidence
# ----------------------------------------------------------------


def test_confidence_out_of_range_rejected():
    document = _document(storySummary={"text": "合成テキスト", "confidence": 1.5})
    assert _validate(document) != []


def test_confidence_null_is_valid():
    document = _document(storySummary={"text": "合成テキスト", "confidence": None})
    assert _validate(document) == []
