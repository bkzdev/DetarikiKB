"""
tests/merger/test_entity_merge_relationship.py
agents/merger の RelationshipCandidate 最小merge実装のテスト。

build_relationship_entities を直接呼び出すユニットテスト。source/target
解決には既にmerge済みのCharacter/Location/Organization entity一覧が必要
なため、agents.merger.character等のbuild_*_entitiesも併用して
known_entitiesを組み立てる。

自然文からの関係推定は行わないこと、relationshipTypeが自由文字列のまま
保持されること、source/targetが解決できない候補は無理にmergeしないことを
重点的に確認する。
"""

from typing import Any

import pytest

from agents.merger.character import build_character_entities
from agents.merger.organization import build_organization_entities
from agents.merger.relationship import build_relationship_entities


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


def _character_candidate(
    candidate_id: str,
    evidence_ids: list[str],
    name_candidates: list[str],
    existing_character_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "character_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": evidence_ids,
        "extractionRun": _extraction_run(),
        "existingCharacterId": existing_character_id,
        "sourceCharacterId": None,
        "nameCandidates": name_candidates,
        "fields": {},
    }


def _organization_candidate(
    candidate_id: str,
    evidence_ids: list[str],
    name_candidates: list[str],
    existing_organization_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "organization_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": evidence_ids,
        "extractionRun": _extraction_run(),
        "existingOrganizationId": existing_organization_id,
        "nameCandidates": name_candidates,
        "fields": {},
    }


def _relationship_candidate(
    candidate_id: str,
    evidence_ids: list[str],
    source_candidate: str | None,
    target_candidate: str | None,
    relationship_type: str | None,
    direction: str = "source_to_target",
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "relationship_candidate",
        "sourceType": "script",
        "confidence": confidence,
        "evidenceIds": evidence_ids,
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
    characters: list[dict[str, Any]] | None = None,
    organizations: list[dict[str, Any]] | None = None,
    relationships: list[dict[str, Any]] | None = None,
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
        "locations": [],
        "items": [],
        "lore": [],
        "events": [],
        "relationships": relationships or [],
        "timelineCandidates": [],
        "extractionErrors": [],
    }


# ----------------------------------------------------------------
# 1. RelationshipCandidateがmerged relationshipになる
#    (source/targetは既にmerged entity idを指すケース)
# ----------------------------------------------------------------


def test_relationship_with_resolved_entity_ids_becomes_merged_relationship():
    relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_AKAGI_HINA",
        target_candidate="CHAR_RAIN",
        relationship_type="TRUSTS",
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    # source/targetがすでにmerged entity id (CHAR_AKAGI_HINA/CHAR_RAIN) を
    # 指すケースなので、known_entitiesにその id を持つentityがあればよい。
    known_entities = [
        {"id": "CHAR_AKAGI_HINA", "sourceCandidates": []},
        {"id": "CHAR_RAIN", "sourceCandidates": []},
    ]

    entities, warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities
    )

    assert warnings == []
    assert len(entities) == 1
    entity = entities[0]
    assert entity["type"] == "relationship"
    assert entity["sourceEntityId"] == "CHAR_AKAGI_HINA"
    assert entity["targetEntityId"] == "CHAR_RAIN"
    assert entity["relationshipType"] == "TRUSTS"
    assert entity["direction"] == "source_to_target"
    assert entity["status"] == "merged"
    assert entity["canonicalId"] is not None
    assert entity["canonicalId"].startswith("REL_CHAR_AKAGI_HINA_TRUSTS_CHAR_RAIN")


def test_unknown_direction_is_reported_and_skipped():
    relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_AKAGI_HINA",
        target_candidate="CHAR_RAIN",
        relationship_type="TRUSTS",
        direction="sideways",
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    known_entities = [
        {"id": "CHAR_AKAGI_HINA", "sourceCandidates": []},
        {"id": "CHAR_RAIN", "sourceCandidates": []},
    ]

    entities, merge_warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities
    )

    assert entities == []
    assert len(merge_warnings) == 1
    assert "EP01/EP01_CAND_REL001" in merge_warnings[0]
    assert "sideways" in merge_warnings[0]
    assert "relationship mergeをskip" in merge_warnings[0]


# ----------------------------------------------------------------
# 2. 同じsource/target/type/directionの複数candidateが1つにmergeされる
# ----------------------------------------------------------------


def test_same_source_target_type_direction_merges_into_one_entity():
    relationship1 = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="CHAR_B",
        relationship_type="TRUSTS",
    )
    relationship2 = _relationship_candidate(
        "EP02_CAND_REL001",
        ["EP02_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="CHAR_B",
        relationship_type="TRUSTS",
    )
    doc1 = _episode_extraction(
        "EP01",
        relationships=[relationship1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        relationships=[relationship2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )
    known_entities = [
        {"id": "CHAR_A", "sourceCandidates": []},
        {"id": "CHAR_B", "sourceCandidates": []},
    ]

    entities, warnings = build_relationship_entities(
        [("ep01.json", doc1), ("ep02.json", doc2)], known_entities
    )

    assert warnings == []
    assert len(entities) == 1
    entity = entities[0]
    assert set(entity["mergedFrom"]) == {"EP01", "EP02"}
    assert len(entity["sourceCandidates"]) == 2
    assert len(entity["evidenceRefs"]) == 2


@pytest.mark.parametrize(
    "directions",
    [
        ("source_to_target", "bidirectional"),
        ("bidirectional", "source_to_target"),
        ("target_to_source", "bidirectional"),
        ("source_to_target", "target_to_source"),
    ],
)
def test_conflicting_directions_stay_separate_with_review_records(directions):
    relationships = [
        _relationship_candidate(
            f"EP01_CAND_REL{index:03d}",
            [f"EP01_DLG{index:04d}"],
            source_candidate="CHAR_A",
            target_candidate="CHAR_B",
            relationship_type="RELATED_TO",
            direction=direction,
        )
        for index, direction in enumerate(directions, start=1)
    ]
    document = _episode_extraction(
        "EP01",
        relationships=relationships,
        evidence_index={
            f"EP01_DLG{index:04d}": _evidence_ref(f"EP01_DLG{index:04d}", "EP01")
            for index in range(1, 3)
        },
    )
    known_entities = [
        {"id": "CHAR_A", "sourceCandidates": []},
        {"id": "CHAR_B", "sourceCandidates": []},
    ]

    review_records = []
    entities, warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities, review_records
    )

    assert warnings == []
    assert len(entities) == 2
    assert {entity["direction"] for entity in entities} == set(directions)
    assert all(entity["publicationStatus"] == "review_required" for entity in entities)
    assert all(entity["conflicts"][0]["field"] == "direction" for entity in entities)
    assert all("direction_conflict" in record["reasons"] for record in review_records)


@pytest.mark.parametrize("direction", ["target_to_source", "bidirectional"])
def test_fixed_direction_type_is_retained_for_review(direction):
    relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="ORG_A",
        relationship_type="MEMBER_OF",
        direction=direction,
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    known_entities = [
        {"id": "CHAR_A", "type": "character", "sourceCandidates": []},
        {"id": "ORG_A", "type": "organization", "sourceCandidates": []},
    ]

    review_records = []
    entities, warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities, review_records
    )

    assert len(entities) == 1
    assert entities[0]["publicationStatus"] == "review_required"
    assert len(warnings) == 1
    assert "EP01/EP01_CAND_REL001" in warnings[0]
    assert "MEMBER_OF" in warnings[0]
    assert direction in warnings[0]
    assert "source_to_target固定" in warnings[0]
    assert review_records[0]["reasons"] == ["invalid_formal_direction"]


def test_formal_type_and_semantic_alias_are_not_automatically_merged():
    relationships = [
        _relationship_candidate(
            "EP01_CAND_REL001",
            ["EP01_DLG0001"],
            source_candidate="CHAR_A",
            target_candidate="ORG_A",
            relationship_type="MEMBER_OF",
            direction="source_to_target",
        ),
        _relationship_candidate(
            "EP01_CAND_REL002",
            ["EP01_DLG0002"],
            source_candidate="CHAR_A",
            target_candidate="ORG_A",
            relationship_type="belongs-to",
            direction="bidirectional",
        ),
    ]
    document = _episode_extraction(
        "EP01",
        relationships=relationships,
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )
    known_entities = [
        {"id": "CHAR_A", "type": "character", "sourceCandidates": []},
        {"id": "ORG_A", "type": "organization", "sourceCandidates": []},
    ]

    review_records = []
    entities, warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities, review_records
    )

    assert len(entities) == 2
    formal = next(e for e in entities if e["normalizedRelationshipType"] == "member_of")
    alias = next(e for e in entities if e["normalizedRelationshipType"] == "belongs_to")
    assert formal["publicationStatus"] == "review_required"
    assert alias["publicationStatus"] == "review_required"
    assert warnings == []
    alias_record = next(
        record
        for record in review_records
        if record["candidateId"] == "EP01_CAND_REL002"
    )
    assert alias_record["suggestedType"] == "member_of"
    assert "semantic_alias" in alias_record["reasons"]


def test_formal_script_relationship_is_publication_eligible():
    relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="ORG_A",
        relationship_type="MEMBER OF",
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    known_entities = [
        {"id": "CHAR_A", "type": "character", "sourceCandidates": []},
        {"id": "ORG_A", "type": "organization", "sourceCandidates": []},
    ]
    review_records = []

    entities, warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities, review_records
    )

    assert warnings == []
    assert review_records == []
    assert entities[0]["normalizedRelationshipType"] == "member_of"
    assert entities[0]["taxonomyState"] == "formal_v1"
    assert entities[0]["sourceType"] == "script"
    assert entities[0]["publicationStatus"] == "eligible"


def test_formal_relationship_endpoint_type_mismatch_requires_review():
    relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="CHAR_B",
        relationship_type="MEMBER_OF",
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    known_entities = [
        {"id": "CHAR_A", "type": "character", "sourceCandidates": []},
        {"id": "CHAR_B", "type": "character", "sourceCandidates": []},
    ]
    review_records = []

    entities, _warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities, review_records
    )

    assert entities[0]["publicationStatus"] == "review_required"
    assert review_records[0]["reasons"] == ["endpoint_type_mismatch"]
    assert review_records[0]["targetEntityType"] == "character"


def test_source_types_are_separate_and_ai_extracted_requires_review():
    script_relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="ORG_A",
        relationship_type="AFFILIATED_WITH",
    )
    ai_relationship = _relationship_candidate(
        "EP01_CAND_REL002",
        ["EP01_DLG0002"],
        source_candidate="CHAR_A",
        target_candidate="ORG_A",
        relationship_type="AFFILIATED_WITH",
    )
    ai_relationship["sourceType"] = "ai_extracted"
    document = _episode_extraction(
        "EP01",
        relationships=[script_relationship, ai_relationship],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )
    known_entities = [
        {"id": "CHAR_A", "type": "character", "sourceCandidates": []},
        {"id": "ORG_A", "type": "organization", "sourceCandidates": []},
    ]
    review_records = []

    entities, _warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities, review_records
    )

    assert len(entities) == 2
    assert len({entity["id"] for entity in entities}) == 2
    by_source = {entity["sourceType"]: entity for entity in entities}
    assert by_source["script"]["publicationStatus"] == "eligible"
    assert by_source["ai_extracted"]["publicationStatus"] == "review_required"
    assert review_records[0]["candidateId"] == "EP01_CAND_REL002"
    assert review_records[0]["reasons"] == ["non_public_source_type"]


def test_cross_source_type_conflict_quarantines_otherwise_eligible_record():
    script_relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="ORG_A",
        relationship_type="MEMBER_OF",
    )
    ai_relationship = _relationship_candidate(
        "EP01_CAND_REL002",
        ["EP01_DLG0002"],
        source_candidate="CHAR_A",
        target_candidate="ORG_A",
        relationship_type="AFFILIATED_WITH",
    )
    ai_relationship["sourceType"] = "ai_inferred"
    document = _episode_extraction(
        "EP01",
        relationships=[script_relationship, ai_relationship],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )
    known_entities = [
        {"id": "CHAR_A", "type": "character", "sourceCandidates": []},
        {"id": "ORG_A", "type": "organization", "sourceCandidates": []},
    ]
    review_records = []

    entities, _warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities, review_records
    )

    assert len(entities) == 2
    assert all(entity["publicationStatus"] == "review_required" for entity in entities)
    by_candidate = {record["candidateId"]: record for record in review_records}
    assert by_candidate["EP01_CAND_REL001"]["reasons"] == [
        "endpoint_relationship_conflict"
    ]
    assert by_candidate["EP01_CAND_REL001"]["sourceCandidate"] == "CHAR_A"
    assert by_candidate["EP01_CAND_REL002"]["reasons"] == [
        "non_public_source_type",
        "endpoint_relationship_conflict",
    ]


def test_different_relationship_type_produces_separate_merged_relationship():
    relationship1 = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="CHAR_B",
        relationship_type="TRUSTS",
    )
    relationship2 = _relationship_candidate(
        "EP01_CAND_REL002",
        ["EP01_DLG0002"],
        source_candidate="CHAR_A",
        target_candidate="CHAR_B",
        relationship_type="APPEARS_WITH",
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship1, relationship2],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )
    known_entities = [
        {"id": "CHAR_A", "sourceCandidates": []},
        {"id": "CHAR_B", "sourceCandidates": []},
    ]

    entities, warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities
    )

    assert warnings == []
    assert len(entities) == 2


# ----------------------------------------------------------------
# 3. evidenceRefs / sourceCandidates / extractionRunRefsの保持
# ----------------------------------------------------------------


def test_relationship_evidence_refs_are_not_lost():
    relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001", "EP01_DLG0002"],
        source_candidate="CHAR_A",
        target_candidate="CHAR_B",
        relationship_type="TRUSTS",
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )
    known_entities = [
        {"id": "CHAR_A", "sourceCandidates": []},
        {"id": "CHAR_B", "sourceCandidates": []},
    ]

    entities, _warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities
    )
    entity = entities[0]

    evidence_ids = {ref["evidenceId"] for ref in entity["evidenceRefs"]}
    assert evidence_ids == {"EP01_DLG0001", "EP01_DLG0002"}


def test_relationship_source_candidates_are_retained():
    relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="CHAR_B",
        relationship_type="TRUSTS",
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    known_entities = [
        {"id": "CHAR_A", "sourceCandidates": []},
        {"id": "CHAR_B", "sourceCandidates": []},
    ]

    entities, _warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities
    )
    entity = entities[0]

    assert len(entity["sourceCandidates"]) == 1
    source_candidate = entity["sourceCandidates"][0]
    assert source_candidate["candidateId"] == "EP01_CAND_REL001"
    assert source_candidate["candidateType"] == "relationship_candidate"


def test_relationship_extraction_run_refs_are_deduplicated():
    relationship1 = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="CHAR_B",
        relationship_type="TRUSTS",
    )
    relationship2 = _relationship_candidate(
        "EP02_CAND_REL001",
        ["EP02_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="CHAR_B",
        relationship_type="TRUSTS",
    )
    doc1 = _episode_extraction(
        "EP01",
        relationships=[relationship1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        relationships=[relationship2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )
    known_entities = [
        {"id": "CHAR_A", "sourceCandidates": []},
        {"id": "CHAR_B", "sourceCandidates": []},
    ]

    entities, _warnings = build_relationship_entities(
        [("ep01.json", doc1), ("ep02.json", doc2)], known_entities
    )
    entity = entities[0]

    assert set(entity["extractionRunRefs"].keys()) == {"EP01", "EP02"}


# ----------------------------------------------------------------
# 4. source/target candidate idがmerged entity idに解決される
# ----------------------------------------------------------------


def test_source_target_candidate_ids_resolve_to_merged_entity_ids():
    character1 = _character_candidate(
        "EP01_CAND_CHAR001",
        ["EP01_DLG0001"],
        ["赤城陽菜"],
        existing_character_id="CHAR_AKAGI_HINA",
    )
    character2 = _character_candidate(
        "EP01_CAND_CHAR002",
        ["EP01_DLG0002"],
        ["レイン"],
        existing_character_id="CHAR_RAIN",
    )
    relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0003"],
        # sourceCandidate/targetCandidateはStage Aのcandidate idを指す
        source_candidate="EP01_CAND_CHAR001",
        target_candidate="EP01_CAND_CHAR002",
        relationship_type="TRUSTS",
    )
    document = _episode_extraction(
        "EP01",
        characters=[character1, character2],
        relationships=[relationship],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
            "EP01_DLG0003": _evidence_ref("EP01_DLG0003", "EP01"),
        },
    )

    known_entities = build_character_entities([("ep01.json", document)])
    entities, warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities
    )

    assert warnings == []
    assert len(entities) == 1
    entity = entities[0]
    assert entity["sourceEntityId"] == "CHAR_AKAGI_HINA"
    assert entity["targetEntityId"] == "CHAR_RAIN"


def test_source_and_target_can_resolve_across_different_entity_types():
    character = _character_candidate(
        "EP01_CAND_CHAR001",
        ["EP01_DLG0001"],
        ["レイン"],
        existing_character_id="CHAR_RAIN",
    )
    organization = _organization_candidate(
        "EP01_CAND_ORG001",
        ["EP01_DLG0001"],
        ["異形生物対策班"],
        existing_organization_id="ORG_TAISAKUHAN",
    )
    relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="EP01_CAND_CHAR001",
        target_candidate="EP01_CAND_ORG001",
        relationship_type="MEMBER_OF",
    )
    document = _episode_extraction(
        "EP01",
        characters=[character],
        organizations=[organization],
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    known_entities = build_character_entities(
        [("ep01.json", document)]
    ) + build_organization_entities([("ep01.json", document)])
    entities, warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities
    )

    assert warnings == []
    assert len(entities) == 1
    entity = entities[0]
    assert entity["sourceEntityId"] == "CHAR_RAIN"
    assert entity["targetEntityId"] == "ORG_TAISAKUHAN"
    assert entity["relationshipType"] == "MEMBER_OF"


# ----------------------------------------------------------------
# 5. 解決できないsource/targetは無理にmergeしない
# ----------------------------------------------------------------


def test_unresolvable_source_does_not_produce_relationship():
    relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="謎の人物",  # 名前だけ、candidate idでもentity idでもない
        target_candidate="CHAR_RAIN",
        relationship_type="TRUSTS",
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    known_entities = [{"id": "CHAR_RAIN", "sourceCandidates": []}]

    review_records = []
    entities, warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities, review_records
    )

    assert entities == []
    assert len(warnings) == 1
    assert "sourceCandidate" in warnings[0]
    assert review_records[0]["reasons"] == [
        "unrecognized_type",
        "unresolved_endpoint",
    ]
    assert review_records[0]["sourceCandidate"] == "謎の人物"
    assert review_records[0]["evidenceIds"] == ["EP01_DLG0001"]
    assert review_records[0]["extractionRun"]["extractionMethod"] == "rule_based"


def test_unresolvable_target_does_not_produce_relationship():
    relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_RAIN",
        target_candidate="謎の組織",
        relationship_type="MEMBER_OF",
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    known_entities = [{"id": "CHAR_RAIN", "sourceCandidates": []}]

    entities, warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities
    )

    assert entities == []
    assert len(warnings) == 1
    assert "targetCandidate" in warnings[0]


def test_empty_relationship_type_does_not_produce_relationship():
    relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="CHAR_B",
        relationship_type="",
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    known_entities = [
        {"id": "CHAR_A", "sourceCandidates": []},
        {"id": "CHAR_B", "sourceCandidates": []},
    ]

    entities, warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities
    )

    assert entities == []
    assert len(warnings) == 1
    assert "relationshipType" in warnings[0]


# ----------------------------------------------------------------
# 6. relationshipTypeは自由文字列として保持される
# ----------------------------------------------------------------


def test_relationship_type_is_kept_as_free_string():
    relationship = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="CHAR_B",
        relationship_type="SOME_NOT_YET_STANDARDIZED_RELATION",
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    known_entities = [
        {"id": "CHAR_A", "sourceCandidates": []},
        {"id": "CHAR_B", "sourceCandidates": []},
    ]

    entities, _warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities
    )

    assert entities[0]["relationshipType"] == "SOME_NOT_YET_STANDARDIZED_RELATION"


# ----------------------------------------------------------------
# 7. endpoint conflict (同じsource/targetで異なるtype/direction)
# ----------------------------------------------------------------


def test_conflicting_relationship_type_for_same_endpoints_is_recorded():
    relationship1 = _relationship_candidate(
        "EP01_CAND_REL001",
        ["EP01_DLG0001"],
        source_candidate="CHAR_A",
        target_candidate="CHAR_B",
        relationship_type="TRUSTS",
    )
    relationship2 = _relationship_candidate(
        "EP01_CAND_REL002",
        ["EP01_DLG0002"],
        source_candidate="CHAR_A",
        target_candidate="CHAR_B",
        relationship_type="DISTRUSTS",
    )
    document = _episode_extraction(
        "EP01",
        relationships=[relationship1, relationship2],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )
    known_entities = [
        {"id": "CHAR_A", "sourceCandidates": []},
        {"id": "CHAR_B", "sourceCandidates": []},
    ]

    entities, _warnings = build_relationship_entities(
        [("ep01.json", document)], known_entities
    )

    assert len(entities) == 2
    for entity in entities:
        assert len(entity["conflicts"]) == 1
        conflict = entity["conflicts"][0]
        assert conflict["conflictType"] == "relationship_conflict"
        assert conflict["severity"] == "warning"
        assert conflict["resolutionStatus"] == "unresolved"
