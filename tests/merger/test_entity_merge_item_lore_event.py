"""
tests/merger/test_entity_merge_item_lore_event.py
agents/merger の Item/Lore/Event 最小merge実装のテスト。

build_item_entities / build_lore_entities / build_event_entities を直接
呼び出すユニットテスト。実ファイルI/Oは不要なため、episode_extraction
document をPythonの辞書としてインラインで組み立てる (schemas/extraction.schema.json
準拠の最小構造)。

構造化ID (existing*Id) があるcandidateだけを自動mergeし、名前一致だけでは
自動mergeしないこと (Merged_Knowledge_Design.md §4.1原則2) を重点的に確認する。
LoreCandidateのみ名前候補配列が termCandidates である点に注意する。
"""

from typing import Any

from agents.merger.character import build_character_entities
from agents.merger.event import build_event_entities
from agents.merger.item import build_item_entities
from agents.merger.location import build_location_entities
from agents.merger.lore import build_lore_entities
from agents.merger.organization import build_organization_entities


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


def _item_candidate(
    candidate_id: str,
    evidence_ids: list[str],
    name_candidates: list[str],
    existing_item_id: str | None = None,
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "item_candidate",
        "sourceType": "script",
        "confidence": confidence,
        "evidenceIds": evidence_ids,
        "extractionRun": _extraction_run(),
        "existingItemId": existing_item_id,
        "nameCandidates": name_candidates,
        "fields": {},
    }


def _lore_candidate(
    candidate_id: str,
    evidence_ids: list[str],
    term_candidates: list[str],
    existing_lore_id: str | None = None,
    confidence: float = 0.8,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "lore_candidate",
        "sourceType": "script",
        "confidence": confidence,
        "evidenceIds": evidence_ids,
        "extractionRun": _extraction_run(),
        "existingLoreId": existing_lore_id,
        "termCandidates": term_candidates,
        "fields": {},
    }


def _event_candidate(
    candidate_id: str,
    evidence_ids: list[str],
    name_candidates: list[str],
    existing_event_id: str | None = None,
    confidence: float = 0.75,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "event_candidate",
        "sourceType": "ai_extracted",
        "confidence": confidence,
        "evidenceIds": evidence_ids,
        "extractionRun": _extraction_run(),
        "existingEventId": existing_event_id,
        "nameCandidates": name_candidates,
        "participantCandidates": [],
        "locationCandidates": [],
        "fields": {},
    }


def _episode_extraction(
    episode_id: str,
    characters: list[dict[str, Any]] | None = None,
    locations: list[dict[str, Any]] | None = None,
    organizations: list[dict[str, Any]] | None = None,
    items: list[dict[str, Any]] | None = None,
    lore: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
    evidence_index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": "0.1",
        "documentType": "episode_extraction",
        "episodeId": episode_id,
        "storyId": "TEST_STORY",
        "storyCategory": "MAIN",
        "extractionRun": _extraction_run(),
        "evidenceIndex": evidence_index or {},
        "characters": characters or [],
        "organizations": organizations or [],
        "locations": locations or [],
        "items": items or [],
        "lore": lore or [],
        "events": events or [],
        "relationships": [],
        "timelineCandidates": [],
        "extractionErrors": [],
    }


# ----------------------------------------------------------------
# 1. ItemCandidate: existingItemIdありは1 merged itemになる
# ----------------------------------------------------------------


def test_item_with_existing_id_becomes_one_merged_item():
    candidate = _item_candidate(
        "EP01_CAND_ITEM001",
        ["EP01_DLG0001"],
        ["デタリキ"],
        existing_item_id="ITEM_DETARIKI",
    )
    document = _episode_extraction(
        "EP01",
        items=[candidate],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    entities = build_item_entities([("ep01.json", document)])

    assert len(entities) == 1
    entity = entities[0]
    assert entity["id"] == "ITEM_DETARIKI"
    assert entity["canonicalId"] == "ITEM_DETARIKI"
    assert entity["status"] == "merged"
    assert entity["type"] == "item"
    assert entity["displayName"] == "デタリキ"


def test_same_existing_item_id_across_episodes_merges_into_one_entity():
    candidate1 = _item_candidate(
        "EP01_CAND_ITEM001",
        ["EP01_DLG0001"],
        ["デタリキ"],
        existing_item_id="ITEM_DETARIKI",
    )
    candidate2 = _item_candidate(
        "EP02_CAND_ITEM001",
        ["EP02_DLG0001"],
        ["デタリキ"],
        existing_item_id="ITEM_DETARIKI",
    )
    doc1 = _episode_extraction(
        "EP01",
        items=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        items=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_item_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    assert len(entities) == 1
    entity = entities[0]
    assert set(entity["mergedFrom"]) == {"EP01", "EP02"}
    assert len(entity["sourceCandidates"]) == 2
    assert len(entity["evidenceRefs"]) == 2


def test_item_name_only_is_not_auto_merged():
    candidate1 = _item_candidate("EP01_CAND_ITEM001", ["EP01_DLG0001"], ["鍵"])
    candidate2 = _item_candidate("EP02_CAND_ITEM001", ["EP02_DLG0001"], ["鍵"])
    doc1 = _episode_extraction(
        "EP01",
        items=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        items=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_item_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    assert len(entities) == 2
    for entity in entities:
        assert entity["status"] == "unresolved"
        assert entity["canonicalId"] is None
        assert entity["id"].startswith("UNRESOLVED_ITEM_")
    assert entities[0]["id"] != entities[1]["id"]


# ----------------------------------------------------------------
# 2. LoreCandidate: existingLoreId/termIdありは1 merged lore entryになる
# ----------------------------------------------------------------


def test_lore_with_existing_id_becomes_one_merged_lore_entry():
    candidate = _lore_candidate(
        "EP01_CAND_LORE001",
        ["EP01_DLG0001"],
        ["デタリキZ"],
        existing_lore_id="LORE_DETARIKI_Z",
    )
    document = _episode_extraction(
        "EP01",
        lore=[candidate],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    entities = build_lore_entities([("ep01.json", document)])

    assert len(entities) == 1
    entity = entities[0]
    assert entity["id"] == "LORE_DETARIKI_Z"
    assert entity["canonicalId"] == "LORE_DETARIKI_Z"
    assert entity["status"] == "merged"
    assert entity["type"] == "lore"
    assert entity["displayName"] == "デタリキZ"


def test_lore_term_name_only_is_not_auto_merged():
    candidate1 = _lore_candidate("EP01_CAND_LORE001", ["EP01_DLG0001"], ["用語X"])
    candidate2 = _lore_candidate("EP02_CAND_LORE001", ["EP02_DLG0001"], ["用語X"])
    doc1 = _episode_extraction(
        "EP01",
        lore=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        lore=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_lore_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    assert len(entities) == 2
    for entity in entities:
        assert entity["status"] == "unresolved"
        assert entity["canonicalId"] is None
        assert entity["id"].startswith("UNRESOLVED_LORE_")


# ----------------------------------------------------------------
# 3. EventCandidate: existingEventIdありは1 merged eventになる
# ----------------------------------------------------------------


def test_event_with_existing_id_becomes_one_merged_event():
    candidate = _event_candidate(
        "EP01_CAND_EVENT001",
        ["EP01_NAR0003"],
        ["ジャマー初出現"],
        existing_event_id="EVENT_JAMMER_FIRST",
    )
    document = _episode_extraction(
        "EP01",
        events=[candidate],
        evidence_index={"EP01_NAR0003": _evidence_ref("EP01_NAR0003", "EP01")},
    )

    entities = build_event_entities([("ep01.json", document)])

    assert len(entities) == 1
    entity = entities[0]
    assert entity["id"] == "EVENT_JAMMER_FIRST"
    assert entity["canonicalId"] == "EVENT_JAMMER_FIRST"
    assert entity["status"] == "merged"
    assert entity["type"] == "event"
    assert entity["displayName"] == "ジャマー初出現"


def test_event_name_only_is_not_auto_merged():
    candidate1 = _event_candidate(
        "EP01_CAND_EVENT001", ["EP01_NAR0001"], ["謎の出来事"]
    )
    candidate2 = _event_candidate(
        "EP02_CAND_EVENT001", ["EP02_NAR0001"], ["謎の出来事"]
    )
    doc1 = _episode_extraction(
        "EP01",
        events=[candidate1],
        evidence_index={"EP01_NAR0001": _evidence_ref("EP01_NAR0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        events=[candidate2],
        evidence_index={"EP02_NAR0001": _evidence_ref("EP02_NAR0001", "EP02")},
    )

    entities = build_event_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    assert len(entities) == 2
    for entity in entities:
        assert entity["status"] == "unresolved"
        assert entity["canonicalId"] is None
        assert entity["id"].startswith("UNRESOLVED_EVENT_")


# ----------------------------------------------------------------
# 4. evidenceRefs / sourceCandidates / extractionRunRefsの保持
# ----------------------------------------------------------------


def test_item_evidence_refs_are_not_lost():
    candidate = _item_candidate(
        "EP01_CAND_ITEM001",
        ["EP01_DLG0001", "EP01_DLG0002"],
        ["デタリキ"],
        existing_item_id="ITEM_DETARIKI",
    )
    document = _episode_extraction(
        "EP01",
        items=[candidate],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )

    entities = build_item_entities([("ep01.json", document)])
    entity = entities[0]

    evidence_ids = {ref["evidenceId"] for ref in entity["evidenceRefs"]}
    assert evidence_ids == {"EP01_DLG0001", "EP01_DLG0002"}


def test_lore_source_candidates_are_retained():
    candidate = _lore_candidate(
        "EP01_CAND_LORE001",
        ["EP01_DLG0001"],
        ["デタリキZ"],
        existing_lore_id="LORE_DETARIKI_Z",
    )
    document = _episode_extraction(
        "EP01",
        lore=[candidate],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    entities = build_lore_entities([("ep01.json", document)])
    entity = entities[0]

    assert len(entity["sourceCandidates"]) == 1
    source_candidate = entity["sourceCandidates"][0]
    assert source_candidate["candidateId"] == "EP01_CAND_LORE001"
    assert source_candidate["candidateType"] == "lore_candidate"
    assert source_candidate["sourceType"] == "script"


def test_event_extraction_run_refs_are_deduplicated():
    candidate1 = _event_candidate(
        "EP01_CAND_EVENT001",
        ["EP01_NAR0001"],
        ["ジャマー初出現"],
        existing_event_id="EVENT_JAMMER_FIRST",
    )
    candidate2 = _event_candidate(
        "EP02_CAND_EVENT001",
        ["EP02_NAR0001"],
        ["ジャマー初出現"],
        existing_event_id="EVENT_JAMMER_FIRST",
    )
    doc1 = _episode_extraction(
        "EP01",
        events=[candidate1],
        evidence_index={"EP01_NAR0001": _evidence_ref("EP01_NAR0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        events=[candidate2],
        evidence_index={"EP02_NAR0001": _evidence_ref("EP02_NAR0001", "EP02")},
    )

    entities = build_event_entities([("ep01.json", doc1), ("ep02.json", doc2)])
    entity = entities[0]

    assert set(entity["extractionRunRefs"].keys()) == {"EP01", "EP02"}


# ----------------------------------------------------------------
# 5. displayName conflict
# ----------------------------------------------------------------


def test_item_display_name_conflict_is_recorded_when_names_differ():
    candidate1 = _item_candidate(
        "EP01_CAND_ITEM001",
        ["EP01_DLG0001"],
        ["デタリキ"],
        existing_item_id="ITEM_DETARIKI",
    )
    candidate2 = _item_candidate(
        "EP02_CAND_ITEM001",
        ["EP02_DLG0001"],
        ["デタリキ・Z"],
        existing_item_id="ITEM_DETARIKI",
    )
    doc1 = _episode_extraction(
        "EP01",
        items=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        items=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_item_entities([("ep01.json", doc1), ("ep02.json", doc2)])
    entity = entities[0]

    assert entity["displayName"] == "デタリキ"
    assert entity["aliases"] == ["デタリキ・Z"]
    assert len(entity["conflicts"]) == 1
    conflict = entity["conflicts"][0]
    assert conflict["conflictType"] == "field_value_conflict"
    assert conflict["field"] == "displayName"
    assert conflict["severity"] == "warning"
    assert conflict["resolutionStatus"] == "unresolved"


def test_lore_display_name_conflict_uses_term_candidates():
    # Loreはname_field="termCandidates"であることを、conflict検出でも確認する
    candidate1 = _lore_candidate(
        "EP01_CAND_LORE001",
        ["EP01_DLG0001"],
        ["デタリキZ"],
        existing_lore_id="LORE_DETARIKI_Z",
    )
    candidate2 = _lore_candidate(
        "EP02_CAND_LORE001",
        ["EP02_DLG0001"],
        ["デタリキ・Z"],
        existing_lore_id="LORE_DETARIKI_Z",
    )
    doc1 = _episode_extraction(
        "EP01",
        lore=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        lore=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_lore_entities([("ep01.json", doc1), ("ep02.json", doc2)])
    entity = entities[0]

    assert entity["displayName"] == "デタリキZ"
    assert entity["aliases"] == ["デタリキ・Z"]
    assert len(entity["conflicts"]) == 1


# ----------------------------------------------------------------
# 6. Character/Location/Organizationとの共存
# ----------------------------------------------------------------


def test_item_lore_event_coexist_with_character_location_organization():
    character = {
        "id": "EP01_CAND_CHAR001",
        "type": "character_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": ["EP01_DLG0001"],
        "extractionRun": _extraction_run(),
        "existingCharacterId": "CHAR_RAIN",
        "sourceCharacterId": "26",
        "nameCandidates": ["レイン"],
        "fields": {},
    }
    location = {
        "id": "EP01_CAND_LOC001",
        "type": "location_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": ["EP01_DLG0001"],
        "extractionRun": _extraction_run(),
        "existingLocationId": "LOC_HQ",
        "nameCandidates": ["本部"],
        "sceneRefs": [],
        "fields": {},
    }
    organization = {
        "id": "EP01_CAND_ORG001",
        "type": "organization_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": ["EP01_DLG0001"],
        "extractionRun": _extraction_run(),
        "existingOrganizationId": "ORG_TAISAKUHAN",
        "nameCandidates": ["異形生物対策班"],
        "fields": {},
    }
    item = _item_candidate(
        "EP01_CAND_ITEM001",
        ["EP01_DLG0001"],
        ["デタリキ"],
        existing_item_id="ITEM_DETARIKI",
    )
    lore = _lore_candidate(
        "EP01_CAND_LORE001",
        ["EP01_DLG0001"],
        ["デタリキZ"],
        existing_lore_id="LORE_DETARIKI_Z",
    )
    event = _event_candidate(
        "EP01_CAND_EVENT001",
        ["EP01_DLG0001"],
        ["ジャマー初出現"],
        existing_event_id="EVENT_JAMMER_FIRST",
    )

    document = _episode_extraction(
        "EP01",
        characters=[character],
        locations=[location],
        organizations=[organization],
        items=[item],
        lore=[lore],
        events=[event],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    entries = [("ep01.json", document)]

    assert len(build_character_entities(entries)) == 1
    assert len(build_location_entities(entries)) == 1
    assert len(build_organization_entities(entries)) == 1
    assert len(build_item_entities(entries)) == 1
    assert len(build_lore_entities(entries)) == 1
    assert len(build_event_entities(entries)) == 1
