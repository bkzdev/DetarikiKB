"""
tests/merger/test_entity_merge_timeline.py
agents/merger の TimelineCandidate 最小merge実装のテスト。

build_timeline_entities を直接呼び出すユニットテスト。実ファイルI/Oは
不要なため、episode_extraction document をPythonの辞書としてインラインで
組み立てる (schemas/extraction.schema.json準拠の最小構造)。

自然文からの時系列推定は行わないこと、同じlabelだけで広範な自動mergeを
しないこと、timelineIdやscope+kind+orderValueが明示された場合のみ保守的に
mergeすることを重点的に確認する。Stage Bでは順序の確定 (canonicalization)
を行わないため、生成されるentryは常にstatus: unresolvedであることも確認する。
"""

from typing import Any

from agents.merger.timeline import build_timeline_entities


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


def _timeline_candidate(
    candidate_id: str,
    evidence_ids: list[str],
    kind: str = "explicit_order",
    scope: str | None = "episode",
    order_value: float | None = None,
    order_field: str | None = None,
    name_candidates: list[str] | None = None,
    source_timeline_id: str | None = None,
    marker_type: str | None = None,
    confidence: float = 0.7,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "timeline_candidate",
        "sourceType": "script",
        "confidence": confidence,
        "evidenceIds": evidence_ids,
        "extractionRun": _extraction_run(),
        "kind": kind,
        "scope": scope,
        "relativeTo": None,
        "relation": None,
        "sourceTimelineId": source_timeline_id,
        "nameCandidates": name_candidates or [],
        "orderValue": order_value,
        "orderField": order_field,
        "markerType": marker_type,
        "fields": {},
    }


def _episode_extraction(
    episode_id: str,
    timeline_candidates: list[dict[str, Any]] | None = None,
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
        "characters": [],
        "organizations": [],
        "locations": [],
        "items": [],
        "lore": [],
        "events": [],
        "relationships": [],
        "timelineCandidates": timeline_candidates or [],
        "extractionErrors": [],
    }


# ----------------------------------------------------------------
# 1. timelineIdありのTimelineCandidateが1 merged timeline entryになる
# ----------------------------------------------------------------


def test_timeline_with_source_timeline_id_becomes_one_merged_entry():
    candidate = _timeline_candidate(
        "EP01_CAND_TL001",
        ["EP01_DLG0001"],
        source_timeline_id="TL_ARC1",
        name_candidates=["第一部"],
    )
    document = _episode_extraction(
        "EP01",
        timeline_candidates=[candidate],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    entities = build_timeline_entities([("ep01.json", document)])

    assert len(entities) == 1
    entity = entities[0]
    assert entity["type"] == "timeline_entry"
    assert entity["sourceTimelineId"] == "TL_ARC1"
    assert entity["label"] == "第一部"
    assert entity["status"] == "unresolved"
    assert entity["canonicalId"] is None
    assert entity["mergedId"] is not None


def test_same_source_timeline_id_across_episodes_merges_into_one_entry():
    candidate1 = _timeline_candidate(
        "EP01_CAND_TL001", ["EP01_DLG0001"], source_timeline_id="TL_ARC1"
    )
    candidate2 = _timeline_candidate(
        "EP02_CAND_TL001", ["EP02_DLG0001"], source_timeline_id="TL_ARC1"
    )
    doc1 = _episode_extraction(
        "EP01",
        timeline_candidates=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        timeline_candidates=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_timeline_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    assert len(entities) == 1
    entity = entities[0]
    assert set(entity["mergedFrom"]) == {"EP01", "EP02"}
    assert len(entity["sourceCandidates"]) == 2
    assert len(entity["evidenceRefs"]) == 2


# ----------------------------------------------------------------
# 2. scope + kind + orderValueが同じcandidateが1 entryにmergeされる
# ----------------------------------------------------------------


def test_same_scope_kind_order_value_merges_into_one_entry():
    candidate1 = _timeline_candidate(
        "EP01_CAND_TL001",
        ["EP01_DLG0001"],
        kind="explicit_order",
        scope="episode",
        order_value=1,
        order_field="canonicalOrder",
    )
    candidate2 = _timeline_candidate(
        "EP02_CAND_TL001",
        ["EP02_DLG0001"],
        kind="explicit_order",
        scope="episode",
        order_value=1,
        order_field="canonicalOrder",
    )
    doc1 = _episode_extraction(
        "EP01",
        timeline_candidates=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        timeline_candidates=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_timeline_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    assert len(entities) == 1
    entity = entities[0]
    assert entity["orderValue"] == 1
    assert entity["scope"] == "episode"
    assert entity["kind"] == "explicit_order"
    assert entity["sourceTimelineId"] is None
    assert set(entity["mergedFrom"]) == {"EP01", "EP02"}


def test_different_order_value_produces_separate_entries():
    candidate1 = _timeline_candidate(
        "EP01_CAND_TL001",
        ["EP01_DLG0001"],
        kind="explicit_order",
        scope="episode",
        order_value=1,
    )
    candidate2 = _timeline_candidate(
        "EP02_CAND_TL001",
        ["EP02_DLG0001"],
        kind="explicit_order",
        scope="episode",
        order_value=2,
    )
    document = _episode_extraction(
        "EP01",
        timeline_candidates=[candidate1, candidate2],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP01"),
        },
    )

    entities = build_timeline_entities([("ep01.json", document)])

    assert len(entities) == 2


# ----------------------------------------------------------------
# 3. labelのみのTimelineCandidateは広く自動mergeしない
# ----------------------------------------------------------------


def test_label_only_candidates_are_not_broadly_auto_merged():
    candidate1 = _timeline_candidate(
        "EP01_CAND_TL001",
        ["EP01_DLG0001"],
        kind="explicit_order",
        scope="block",
        order_value=None,
        name_candidates=["2日目"],
    )
    candidate2 = _timeline_candidate(
        "EP02_CAND_TL001",
        ["EP02_DLG0001"],
        kind="explicit_order",
        scope="block",
        order_value=None,
        name_candidates=["2日目"],
    )
    doc1 = _episode_extraction(
        "EP01",
        timeline_candidates=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        timeline_candidates=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_timeline_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    # orderValueが無いため、同じlabelでも別episodeのcandidateは統合しない
    assert len(entities) == 2
    for entity in entities:
        assert entity["status"] == "unresolved"
        assert entity["id"].startswith("UNRESOLVED_TL_")
    assert entities[0]["id"] != entities[1]["id"]


# ----------------------------------------------------------------
# 4. temporal markerがmerged timeline entryになる
# ----------------------------------------------------------------


def test_temporal_marker_becomes_merged_timeline_entry():
    candidate = _timeline_candidate(
        "EP01_CAND_TL001",
        ["EP01_STAGE0001"],
        kind="temporal_marker",
        scope="block",
        marker_type="flashback",
    )
    document = _episode_extraction(
        "EP01",
        timeline_candidates=[candidate],
        evidence_index={"EP01_STAGE0001": _evidence_ref("EP01_STAGE0001", "EP01")},
    )

    entities = build_timeline_entities([("ep01.json", document)])

    assert len(entities) == 1
    entity = entities[0]
    assert entity["kind"] == "temporal_marker"
    assert entity["markerType"] == "flashback"
    assert entity["status"] == "unresolved"


def test_temporal_markers_from_different_episodes_are_not_merged():
    candidate1 = _timeline_candidate(
        "EP01_CAND_TL001",
        ["EP01_STAGE0001"],
        kind="temporal_marker",
        scope="block",
        marker_type="flashback",
    )
    candidate2 = _timeline_candidate(
        "EP02_CAND_TL001",
        ["EP02_STAGE0001"],
        kind="temporal_marker",
        scope="block",
        marker_type="flashback",
    )
    doc1 = _episode_extraction(
        "EP01",
        timeline_candidates=[candidate1],
        evidence_index={"EP01_STAGE0001": _evidence_ref("EP01_STAGE0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        timeline_candidates=[candidate2],
        evidence_index={"EP02_STAGE0001": _evidence_ref("EP02_STAGE0001", "EP02")},
    )

    entities = build_timeline_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    # temporal_markerはorderValueを持たないため、個別unresolved entryのまま
    assert len(entities) == 2


# ----------------------------------------------------------------
# 5. evidenceRefs / sourceCandidates / extractionRunRefsの保持
# ----------------------------------------------------------------


def test_timeline_evidence_refs_are_not_lost():
    candidate = _timeline_candidate(
        "EP01_CAND_TL001",
        ["EP01_DLG0001", "EP01_DLG0002"],
        source_timeline_id="TL_ARC1",
    )
    document = _episode_extraction(
        "EP01",
        timeline_candidates=[candidate],
        evidence_index={
            "EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01"),
            "EP01_DLG0002": _evidence_ref("EP01_DLG0002", "EP01"),
        },
    )

    entities = build_timeline_entities([("ep01.json", document)])
    entity = entities[0]

    evidence_ids = {ref["evidenceId"] for ref in entity["evidenceRefs"]}
    assert evidence_ids == {"EP01_DLG0001", "EP01_DLG0002"}


def test_timeline_source_candidates_are_retained():
    candidate = _timeline_candidate(
        "EP01_CAND_TL001", ["EP01_DLG0001"], source_timeline_id="TL_ARC1"
    )
    document = _episode_extraction(
        "EP01",
        timeline_candidates=[candidate],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )

    entities = build_timeline_entities([("ep01.json", document)])
    entity = entities[0]

    assert len(entity["sourceCandidates"]) == 1
    source_candidate = entity["sourceCandidates"][0]
    assert source_candidate["candidateId"] == "EP01_CAND_TL001"
    assert source_candidate["candidateType"] == "timeline_candidate"


def test_timeline_extraction_run_refs_are_deduplicated():
    candidate1 = _timeline_candidate(
        "EP01_CAND_TL001", ["EP01_DLG0001"], source_timeline_id="TL_ARC1"
    )
    candidate2 = _timeline_candidate(
        "EP02_CAND_TL001", ["EP02_DLG0001"], source_timeline_id="TL_ARC1"
    )
    doc1 = _episode_extraction(
        "EP01",
        timeline_candidates=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        timeline_candidates=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_timeline_entities([("ep01.json", doc1), ("ep02.json", doc2)])
    entity = entities[0]

    assert set(entity["extractionRunRefs"].keys()) == {"EP01", "EP02"}


# ----------------------------------------------------------------
# 6. label/orderValue conflict
# ----------------------------------------------------------------


def test_label_conflict_recorded_for_same_source_timeline_id():
    candidate1 = _timeline_candidate(
        "EP01_CAND_TL001",
        ["EP01_DLG0001"],
        source_timeline_id="TL_ARC1",
        name_candidates=["第一部"],
    )
    candidate2 = _timeline_candidate(
        "EP02_CAND_TL001",
        ["EP02_DLG0001"],
        source_timeline_id="TL_ARC1",
        name_candidates=["序章"],
    )
    doc1 = _episode_extraction(
        "EP01",
        timeline_candidates=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        timeline_candidates=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_timeline_entities([("ep01.json", doc1), ("ep02.json", doc2)])
    entity = entities[0]

    assert entity["label"] == "第一部"
    assert entity["aliases"] == ["序章"]
    label_conflicts = [c for c in entity["conflicts"] if c["field"] == "label"]
    assert len(label_conflicts) == 1
    assert label_conflicts[0]["severity"] == "warning"
    assert label_conflicts[0]["resolutionStatus"] == "unresolved"


def test_order_value_conflict_recorded_for_same_source_timeline_id():
    candidate1 = _timeline_candidate(
        "EP01_CAND_TL001",
        ["EP01_DLG0001"],
        source_timeline_id="TL_ARC1",
        order_value=1,
    )
    candidate2 = _timeline_candidate(
        "EP02_CAND_TL001",
        ["EP02_DLG0001"],
        source_timeline_id="TL_ARC1",
        order_value=2,
    )
    doc1 = _episode_extraction(
        "EP01",
        timeline_candidates=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        timeline_candidates=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_timeline_entities([("ep01.json", doc1), ("ep02.json", doc2)])
    entity = entities[0]

    order_conflicts = [c for c in entity["conflicts"] if c["field"] == "orderValue"]
    assert len(order_conflicts) == 1
    assert order_conflicts[0]["conflictType"] == "timeline_conflict"
    assert order_conflicts[0]["severity"] == "warning"
    assert set(order_conflicts[0]["values"]) == {1, 2}


def test_no_conflict_when_source_timeline_id_values_match():
    candidate1 = _timeline_candidate(
        "EP01_CAND_TL001",
        ["EP01_DLG0001"],
        source_timeline_id="TL_ARC1",
        name_candidates=["第一部"],
        order_value=1,
    )
    candidate2 = _timeline_candidate(
        "EP02_CAND_TL001",
        ["EP02_DLG0001"],
        source_timeline_id="TL_ARC1",
        name_candidates=["第一部"],
        order_value=1,
    )
    doc1 = _episode_extraction(
        "EP01",
        timeline_candidates=[candidate1],
        evidence_index={"EP01_DLG0001": _evidence_ref("EP01_DLG0001", "EP01")},
    )
    doc2 = _episode_extraction(
        "EP02",
        timeline_candidates=[candidate2],
        evidence_index={"EP02_DLG0001": _evidence_ref("EP02_DLG0001", "EP02")},
    )

    entities = build_timeline_entities([("ep01.json", doc1), ("ep02.json", doc2)])

    assert entities[0]["conflicts"] == []
