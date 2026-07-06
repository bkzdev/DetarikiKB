"""
tests/merger/test_speaker_label_merge.py
agents/merger/speaker_labels.py の special speaker label merge のテスト。

SpecialSpeakerLabelCandidateが、通常のCharacter merged entityとは混ざらず
別枠 (entities.specialSpeakerLabels) として組み立てられ、常に
status: unresolved / canonicalId: null のままであることを確認する。
"""

from typing import Any

from agents.merger.character import build_character_entities
from agents.merger.engine import MergeEngine
from agents.merger.models import MergeReport
from agents.merger.speaker_labels import (
    build_special_speaker_label_entities,
    summarize_special_speaker_labels,
)


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
        "storyId": "TEST_STORY",
        "episodeId": episode_id,
        "sceneId": None,
        "confidence": 1.0,
    }


def _special_speaker_label_candidate(
    candidate_id: str,
    evidence_ids: list[str],
    raw_label: str,
    label_type: str,
    components: list[str] | None = None,
    modifier: str | None = None,
    resolution_status: str = "inferred",
    inferred_speakers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "special_speaker_label_candidate",
        "sourceType": "script",
        "confidence": 0.5,
        "evidenceIds": evidence_ids,
        "extractionRun": _extraction_run(),
        "rawLabel": raw_label,
        "labelSource": "name_command",
        "labelType": label_type,
        "components": components or [],
        "modifier": modifier,
        "baseLabel": None,
        "inferredSpeakers": inferred_speakers or [],
        "resolutionStatus": resolution_status,
    }


def _character_candidate(
    candidate_id: str, evidence_ids: list[str], name_candidates: list[str]
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "character_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": evidence_ids,
        "extractionRun": _extraction_run(),
        "existingCharacterId": "CHAR_RAIN",
        "sourceCharacterId": "26",
        "nameCandidates": name_candidates,
        "fields": {},
    }


def _episode_extraction(
    episode_id: str,
    characters: list[dict[str, Any]] | None = None,
    special_speaker_labels: list[dict[str, Any]] | None = None,
    evidence_index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": "0.1",
        "documentType": "episode_extraction",
        "episodeId": episode_id,
        "storyId": "TEST_STORY",
        "storyCategory": "EVT",
        "extractionRun": _extraction_run(),
        "evidenceIndex": evidence_index or {},
        "characters": characters or [],
        "organizations": [],
        "locations": [],
        "items": [],
        "lore": [],
        "events": [],
        "relationships": [],
        "timelineCandidates": [],
        "specialSpeakerLabelCandidates": special_speaker_labels or [],
        "extractionErrors": [],
    }


# ----------------------------------------------------------------
# build_special_speaker_label_entities
# ----------------------------------------------------------------


def test_special_speaker_label_never_becomes_character_entity():
    candidate = _special_speaker_label_candidate(
        "EP01_CAND_SSL001",
        ["EP01_DLG0001"],
        raw_label="セイナ＆イヴ",
        label_type="speaker_group",
        components=["セイナ", "イヴ"],
    )
    document = _episode_extraction(
        "EP01",
        special_speaker_labels=[candidate],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    character_entities = build_character_entities([("ep01.json", document)])
    special_entities = build_special_speaker_label_entities([("ep01.json", document)])

    assert character_entities == []
    assert len(special_entities) == 1
    entity = special_entities[0]
    assert entity["type"] == "special_speaker_label"
    assert entity["rawLabel"] == "セイナ＆イヴ"
    assert entity["labelType"] == "speaker_group"
    assert entity["components"] == ["セイナ", "イヴ"]
    assert entity["displayName"] == "セイナ＆イヴ"


def test_special_speaker_label_always_unresolved_never_confirmed():
    candidate = _special_speaker_label_candidate(
        "EP01_CAND_SSL001",
        ["EP01_DLG0001"],
        raw_label="紬（小声）",
        label_type="speaker_with_modifier",
        components=["紬"],
        modifier="小声",
        inferred_speakers=[
            {
                "matchedName": "紬",
                "characterId": "CHAR_TSUMUGI",
                "matchStatus": "dictionary_confirmed",
                "confidence": "high",
            }
        ],
    )
    document = _episode_extraction(
        "EP01",
        special_speaker_labels=[candidate],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    entities = build_special_speaker_label_entities([("ep01.json", document)])

    assert len(entities) == 1
    entity = entities[0]
    # inferredSpeakersにcharacterId候補があっても、statusは常にunresolved・
    # canonicalIdは常にnull (自動でconfirmed character解決はしない)
    assert entity["status"] == "unresolved"
    assert entity["canonicalId"] is None
    assert entity["resolutionStatus"] == "inferred"
    assert entity["resolutionStatus"] != "confirmed"
    assert entity["inferredSpeakers"][0]["characterId"] == "CHAR_TSUMUGI"


def test_special_speaker_labels_do_not_auto_merge_across_episodes():
    """同一rawLabelでもエピソードをまたいでは自動統合しない
    (名前一致だけでの自動確定はしない方針、unresolved characterと同じ扱い)。
    """
    candidate1 = _special_speaker_label_candidate(
        "EP01_CAND_SSL001",
        ["EP01_DLG0001"],
        raw_label="？？？",
        label_type="generic_speaker",
    )
    candidate2 = _special_speaker_label_candidate(
        "EP02_CAND_SSL001",
        ["EP02_DLG0001"],
        raw_label="？？？",
        label_type="generic_speaker",
    )
    doc1 = _episode_extraction(
        "EP01",
        special_speaker_labels=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        special_speaker_labels=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_special_speaker_label_entities(
        [("ep01.json", doc1), ("ep02.json", doc2)]
    )

    assert len(entities) == 2
    assert {e["id"] for e in entities} == {
        "UNRESOLVED_SSL_0001",
        "UNRESOLVED_SSL_0002",
    }


def test_multiple_distinct_labels_produce_distinct_entities():
    candidate1 = _special_speaker_label_candidate(
        "EP01_CAND_SSL001",
        ["EP01_DLG0001"],
        raw_label="セイナ＆イヴ",
        label_type="speaker_group",
        components=["セイナ", "イヴ"],
    )
    candidate2 = _special_speaker_label_candidate(
        "EP01_CAND_SSL002",
        ["EP01_DLG0002"],
        raw_label="紬（小声）",
        label_type="speaker_with_modifier",
        components=["紬"],
        modifier="小声",
    )
    document = _episode_extraction(
        "EP01",
        special_speaker_labels=[candidate1, candidate2],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )

    entities = build_special_speaker_label_entities([("ep01.json", document)])
    labels = {e["rawLabel"] for e in entities}

    assert len(entities) == 2
    assert labels == {"セイナ＆イヴ", "紬（小声）"}


# ----------------------------------------------------------------
# summarize_special_speaker_labels
# ----------------------------------------------------------------


def test_summarize_special_speaker_labels_counts_by_type_and_status():
    entities = [
        {"labelType": "speaker_group", "resolutionStatus": "inferred"},
        {"labelType": "speaker_group", "resolutionStatus": "inferred"},
        {"labelType": "generic_speaker", "resolutionStatus": "needs_review"},
    ]
    summary = summarize_special_speaker_labels(entities)

    assert summary["total"] == 3
    assert summary["byLabelType"] == {"speaker_group": 2, "generic_speaker": 1}
    assert summary["byResolutionStatus"] == {"inferred": 2, "needs_review": 1}


def test_summarize_special_speaker_labels_empty():
    summary = summarize_special_speaker_labels([])
    assert summary == {"total": 0, "byLabelType": {}, "byResolutionStatus": {}}


# ----------------------------------------------------------------
# MergeEngine統合: entities.specialSpeakerLabels / report.specialSpeakerLabelSummary
# ----------------------------------------------------------------


def test_merge_engine_separates_characters_and_special_speaker_labels():
    character_candidate = _character_candidate(
        "EP01_CAND_CHAR001", ["EP01_DLG0001"], ["レイン"]
    )
    special_candidate = _special_speaker_label_candidate(
        "EP01_CAND_SSL001",
        ["EP01_DLG0002"],
        raw_label="セイナ＆イヴ",
        label_type="speaker_group",
        components=["セイナ", "イヴ"],
    )
    document = _episode_extraction(
        "EP01",
        characters=[character_candidate],
        special_speaker_labels=[special_candidate],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )

    engine = MergeEngine()
    collection = engine.build_collection(
        [("ep01.json", document)], MergeReport(input_files=1)
    )

    assert len(collection["entities"]["characters"]) == 1
    assert collection["entities"]["characters"][0]["id"] == "CHAR_RAIN"

    special = collection["entities"]["specialSpeakerLabels"]
    assert len(special) == 1
    assert special[0]["rawLabel"] == "セイナ＆イヴ"

    summary = collection["report"]["specialSpeakerLabelSummary"]
    assert summary["total"] == 1
    assert summary["byLabelType"] == {"speaker_group": 1}
    assert summary["byResolutionStatus"] == {"inferred": 1}


def test_merge_engine_special_speaker_labels_do_not_affect_merged_entity_counts():
    """entities.specialSpeakerLabelsは、既存のmergedEntityCounts/
    unresolvedEntityCounts (8種固定) の集計には一切影響しない。
    """
    special_candidate = _special_speaker_label_candidate(
        "EP01_CAND_SSL001",
        ["EP01_DLG0001"],
        raw_label="？？？",
        label_type="generic_speaker",
        resolution_status="needs_review",
    )
    document = _episode_extraction(
        "EP01",
        special_speaker_labels=[special_candidate],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    engine = MergeEngine()
    collection = engine.build_collection(
        [("ep01.json", document)], MergeReport(input_files=1)
    )

    merged_counts = collection["report"]["mergedEntityCounts"]
    unresolved_counts = collection["report"]["unresolvedEntityCounts"]
    assert set(merged_counts.keys()) == {
        "characters",
        "locations",
        "organizations",
        "items",
        "lore",
        "events",
        "relationships",
        "timeline",
    }
    assert set(unresolved_counts.keys()) == set(merged_counts.keys())
    assert all(v == 0 for v in merged_counts.values())
