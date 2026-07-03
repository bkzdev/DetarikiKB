"""
tests/merger/test_entity_merge.py
agents/merger の Character/Location/Organization 最小merge実装のテスト。

build_character_entities / build_location_entities / build_organization_entities
を直接呼び出すユニットテスト。実ファイルI/Oは不要なため、episode_extraction
document をPythonの辞書としてインラインで組み立てる (schemas/extraction.schema.json
準拠の最小構造)。

構造化ID (existing*Id) があるcandidateだけを自動mergeし、名前一致だけでは
自動mergeしないこと (Merged_Knowledge_Design.md §4.1原則2) を重点的に確認する。
"""

from typing import Any

from agents.merger.character import build_character_entities
from agents.merger.location import build_location_entities
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


def _evidence_ref(
    source_id: str, episode_id: str, scene_id: str | None = None
) -> dict[str, Any]:
    return {
        "sourceId": source_id,
        "storyId": "TEST_STORY",
        "episodeId": episode_id,
        "sceneId": scene_id,
        "confidence": 1.0,
    }


def _character_candidate(
    candidate_id: str,
    evidence_ids: list[str],
    name_candidates: list[str],
    existing_character_id: str | None = None,
    source_character_id: str | None = None,
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "character_candidate",
        "sourceType": "script",
        "confidence": confidence,
        "evidenceIds": evidence_ids,
        "extractionRun": _extraction_run(),
        "existingCharacterId": existing_character_id,
        "sourceCharacterId": source_character_id,
        "nameCandidates": name_candidates,
        "fields": {},
    }


def _location_candidate(
    candidate_id: str,
    evidence_ids: list[str],
    name_candidates: list[str],
    scene_refs: list[str],
    existing_location_id: str | None = None,
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "location_candidate",
        "sourceType": "script",
        "confidence": confidence,
        "evidenceIds": evidence_ids,
        "extractionRun": _extraction_run(),
        "existingLocationId": existing_location_id,
        "nameCandidates": name_candidates,
        "sceneRefs": scene_refs,
        "fields": {},
    }


def _organization_candidate(
    candidate_id: str,
    evidence_ids: list[str],
    name_candidates: list[str],
    existing_organization_id: str | None = None,
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "organization_candidate",
        "sourceType": "script",
        "confidence": confidence,
        "evidenceIds": evidence_ids,
        "extractionRun": _extraction_run(),
        "existingOrganizationId": existing_organization_id,
        "nameCandidates": name_candidates,
        "fields": {},
    }


def _episode_extraction(
    episode_id: str,
    characters: list[dict[str, Any]] | None = None,
    locations: list[dict[str, Any]] | None = None,
    organizations: list[dict[str, Any]] | None = None,
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
        "items": [],
        "lore": [],
        "events": [],
        "relationships": [],
        "timelineCandidates": [],
        "extractionErrors": [],
    }


# ----------------------------------------------------------------
# 1. CharacterCandidate: existingCharacterIdありは1 merged characterになる
# ----------------------------------------------------------------


def test_character_with_existing_id_becomes_one_merged_character():
    candidate = _character_candidate(
        "EP01_CAND_CHAR001",
        ["EP01_DLG0001"],
        ["レイン"],
        existing_character_id="CHAR_RAIN",
    )
    document = _episode_extraction(
        "EP01",
        characters=[candidate],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    entities = build_character_entities([("ep01.json", document)])

    assert len(entities) == 1
    entity = entities[0]
    assert entity["id"] == "CHAR_RAIN"
    assert entity["canonicalId"] == "CHAR_RAIN"
    assert entity["mergedId"] is None
    assert entity["status"] == "merged"
    assert entity["type"] == "character"
    assert entity["displayName"] == "レイン"


def test_same_existing_character_id_across_episodes_merges_into_one_entity():
    candidate1 = _character_candidate(
        "EP01_CAND_CHAR001",
        ["EP01_DLG0001"],
        ["レイン"],
        existing_character_id="CHAR_RAIN",
    )
    candidate2 = _character_candidate(
        "EP02_CAND_CHAR001",
        ["EP02_DLG0001"],
        ["レイン"],
        existing_character_id="CHAR_RAIN",
    )
    doc1 = _episode_extraction(
        "EP01",
        characters=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        characters=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_character_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    assert len(entities) == 1
    entity = entities[0]
    assert entity["id"] == "CHAR_RAIN"
    assert set(entity["mergedFrom"]) == {"EP01", "EP02"}
    assert len(entity["sourceCandidates"]) == 2
    assert len(entity["evidenceRefs"]) == 2


def test_name_only_character_candidates_are_not_auto_merged():
    # 構造化IDが無く、同じ名前のcandidateが2つの別episodeにあっても
    # 自動で同一人物とはしない (個別unresolved entityになる)
    candidate1 = _character_candidate(
        "EP01_CAND_CHAR001", ["EP01_DLG0001"], ["謎の人物"]
    )
    candidate2 = _character_candidate(
        "EP02_CAND_CHAR001", ["EP02_DLG0001"], ["謎の人物"]
    )
    doc1 = _episode_extraction(
        "EP01",
        characters=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        characters=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_character_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    assert len(entities) == 2
    for entity in entities:
        assert entity["status"] == "unresolved"
        assert entity["canonicalId"] is None
        assert entity["mergedId"] is not None
        assert entity["id"].startswith("UNRESOLVED_CHAR_")
    assert entities[0]["id"] != entities[1]["id"]


def test_source_character_id_only_merges_conservatively_as_unresolved():
    # sourceCharacterIdのみ (existingCharacterId無し) は同じ値同士でmergeは
    # するが、canonical IDには解決しない (status: unresolved)
    candidate1 = _character_candidate(
        "EP01_CAND_CHAR001", ["EP01_DLG0001"], ["ノイズ"], source_character_id="26"
    )
    candidate2 = _character_candidate(
        "EP02_CAND_CHAR001", ["EP02_DLG0001"], ["ノイズ"], source_character_id="26"
    )
    doc1 = _episode_extraction(
        "EP01",
        characters=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        characters=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_character_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    assert len(entities) == 1
    entity = entities[0]
    assert entity["status"] == "unresolved"
    assert entity["canonicalId"] is None
    assert entity["sourceCharacterIds"] == ["26"]
    assert len(entity["sourceCandidates"]) == 2


# ----------------------------------------------------------------
# 2. LocationCandidate: existingLocationIdありは1 merged locationになる
# ----------------------------------------------------------------


def test_location_with_existing_id_becomes_one_merged_location():
    candidate = _location_candidate(
        "EP01_CAND_LOC001",
        ["EP01_SC001"],
        ["本部"],
        ["EP01_SC001"],
        existing_location_id="LOC_HQ",
    )
    document = _episode_extraction(
        "EP01",
        locations=[candidate],
        evidence_index={
            "EP01_SC001": _evidence_ref("EP01_SC001", "EP01", "EP01_SC001")
        },
    )

    entities = build_location_entities([("ep01.json", document)])

    assert len(entities) == 1
    entity = entities[0]
    assert entity["id"] == "LOC_HQ"
    assert entity["canonicalId"] == "LOC_HQ"
    assert entity["status"] == "merged"
    assert entity["type"] == "location"
    assert entity["sceneRefs"] == ["EP01_SC001"]


def test_location_name_only_is_not_auto_merged():
    candidate1 = _location_candidate(
        "EP01_CAND_LOC001", ["EP01_SC001"], ["公園"], ["EP01_SC001"]
    )
    candidate2 = _location_candidate(
        "EP02_CAND_LOC001", ["EP02_SC001"], ["公園"], ["EP02_SC001"]
    )
    doc1 = _episode_extraction(
        "EP01",
        locations=[candidate1],
        evidence_index={
            "EP01_SC001": _evidence_ref("EP01_SC001", "EP01", "EP01_SC001")
        },
    )
    doc2 = _episode_extraction(
        "EP02",
        locations=[candidate2],
        evidence_index={
            "EP02_SC001": _evidence_ref("EP02_SC001", "EP02", "EP02_SC001")
        },
    )

    entities = build_location_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    assert len(entities) == 2
    for entity in entities:
        assert entity["status"] == "unresolved"
        assert entity["canonicalId"] is None


# ----------------------------------------------------------------
# 3. OrganizationCandidate: existingOrganizationIdありは1 merged organizationになる
# ----------------------------------------------------------------


def test_organization_with_existing_id_becomes_one_merged_organization():
    candidate = _organization_candidate(
        "EP01_CAND_ORG001",
        ["EP01_DLG0001"],
        ["異形生物対策班"],
        existing_organization_id="ORG_TAISAKUHAN",
    )
    document = _episode_extraction(
        "EP01",
        organizations=[candidate],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    entities = build_organization_entities([("ep01.json", document)])

    assert len(entities) == 1
    entity = entities[0]
    assert entity["id"] == "ORG_TAISAKUHAN"
    assert entity["canonicalId"] == "ORG_TAISAKUHAN"
    assert entity["status"] == "merged"
    assert entity["type"] == "organization"


def test_organization_name_only_is_not_auto_merged():
    candidate1 = _organization_candidate(
        "EP01_CAND_ORG001", ["EP01_DLG0001"], ["対策班"]
    )
    candidate2 = _organization_candidate(
        "EP02_CAND_ORG001", ["EP02_DLG0001"], ["対策班"]
    )
    doc1 = _episode_extraction(
        "EP01",
        organizations=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        organizations=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_organization_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    assert len(entities) == 2
    for entity in entities:
        assert entity["status"] == "unresolved"


# ----------------------------------------------------------------
# 4. evidenceRefs / sourceCandidates / extractionRunRefsの保持
# ----------------------------------------------------------------


def test_evidence_refs_are_not_lost():
    candidate = _character_candidate(
        "EP01_CAND_CHAR001",
        ["EP01_DLG0001", "EP01_DLG0002"],
        ["レイン"],
        existing_character_id="CHAR_RAIN",
    )
    document = _episode_extraction(
        "EP01",
        characters=[candidate],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )

    entities = build_character_entities([("ep01.json", document)])
    entity = entities[0]

    evidence_ids = {ref["evidenceId"] for ref in entity["evidenceRefs"]}
    assert evidence_ids == {"EP01_DLG0001", "EP01_DLG0002"}
    for ref in entity["evidenceRefs"]:
        assert ref["episodeId"] == "EP01"
        assert ref["sourceDocumentId"] == "EP01"


def test_source_candidates_are_retained():
    candidate = _character_candidate(
        "EP01_CAND_CHAR001",
        ["EP01_DLG0001"],
        ["レイン"],
        existing_character_id="CHAR_RAIN",
    )
    document = _episode_extraction(
        "EP01",
        characters=[candidate],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    entities = build_character_entities([("ep01.json", document)])
    entity = entities[0]

    assert len(entity["sourceCandidates"]) == 1
    source_candidate = entity["sourceCandidates"][0]
    assert source_candidate["candidateId"] == "EP01_CAND_CHAR001"
    assert source_candidate["candidateType"] == "character_candidate"
    assert source_candidate["episodeId"] == "EP01"
    assert source_candidate["evidenceIds"] == ["EP01_DLG0001"]
    assert source_candidate["sourceType"] == "script"


def test_extraction_run_refs_are_deduplicated():
    candidate1 = _character_candidate(
        "EP01_CAND_CHAR001",
        ["EP01_DLG0001"],
        ["レイン"],
        existing_character_id="CHAR_RAIN",
    )
    candidate2 = _character_candidate(
        "EP02_CAND_CHAR001",
        ["EP02_DLG0001"],
        ["レイン"],
        existing_character_id="CHAR_RAIN",
    )
    doc1 = _episode_extraction(
        "EP01",
        characters=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        characters=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_character_entities([("ep01.json", doc1), ("ep02.json", doc2)])
    entity = entities[0]

    assert set(entity["extractionRunRefs"].keys()) == {"EP01", "EP02"}
    assert entity["extractionRunRefs"]["EP01"]["extractionMethod"] == "rule_based"


# ----------------------------------------------------------------
# 5. displayName conflict
# ----------------------------------------------------------------


def test_display_name_conflict_is_recorded_when_names_differ():
    candidate1 = _character_candidate(
        "EP01_CAND_CHAR001",
        ["EP01_DLG0001"],
        ["レイン"],
        existing_character_id="CHAR_RAIN",
    )
    candidate2 = _character_candidate(
        "EP02_CAND_CHAR001",
        ["EP02_DLG0001"],
        ["零"],
        existing_character_id="CHAR_RAIN",
    )
    doc1 = _episode_extraction(
        "EP01",
        characters=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        characters=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_character_entities([("ep01.json", doc1), ("ep02.json", doc2)])
    entity = entities[0]

    assert entity["displayName"] == "レイン"
    assert entity["aliases"] == ["零"]
    assert len(entity["conflicts"]) == 1
    conflict = entity["conflicts"][0]
    assert conflict["conflictType"] == "field_value_conflict"
    assert conflict["field"] == "displayName"
    assert conflict["severity"] == "warning"
    assert conflict["resolutionStatus"] == "unresolved"
    assert set(conflict["values"]) == {"レイン", "零"}


def test_no_conflict_when_names_match():
    candidate1 = _character_candidate(
        "EP01_CAND_CHAR001",
        ["EP01_DLG0001"],
        ["レイン"],
        existing_character_id="CHAR_RAIN",
    )
    candidate2 = _character_candidate(
        "EP02_CAND_CHAR001",
        ["EP02_DLG0001"],
        ["レイン"],
        existing_character_id="CHAR_RAIN",
    )
    doc1 = _episode_extraction(
        "EP01",
        characters=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        characters=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_character_entities([("ep01.json", doc1), ("ep02.json", doc2)])
    entity = entities[0]

    assert entity["conflicts"] == []
    assert entity["aliases"] == []
