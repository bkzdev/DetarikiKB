"""Canonical Timeline public projectorの合成fixtureテスト。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from agents.extractor.canonical_timeline_public_projection import (
    BASELINE_INVALID,
    PROJECTION_MISMATCH,
    PUBLIC_EPISODE_ID_DUPLICATE,
    PUBLIC_MAPPING_INVALID,
    PUBLIC_MAPPING_MISSING,
    PUBLIC_RELATION_DUPLICATE,
    PUBLIC_STORY_LABEL_CONFLICT,
    PUBLIC_STORY_MAPPING_CONFLICT,
    build_canonical_timeline_public_projection,
    validate_canonical_timeline_public_projection_consistency,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
PUBLIC_SCHEMA_PATH = (
    PROJECT_ROOT / "schemas" / "canonical_timeline_public_projection.schema.json"
)


def _episode(number: int, episode: int = 1) -> dict[str, str]:
    story_id = f"EVT_TEST_STORY_{number:02d}"
    return {
        "storyId": story_id,
        "episodeId": f"{story_id}_E{episode:02d}",
        "storyCategory": "EVT",
    }


def _provenance(
    source: dict[str, str], target: dict[str, str], relation: str, number: int
) -> dict[str, object]:
    return {
        "candidateId": f"TEST_CANDIDATE_{number:03d}",
        "sourceEpisode": deepcopy(source),
        "targetEpisode": deepcopy(target),
        "observedRelation": relation,
        "evidenceIds": [f"TEST_EVIDENCE_{number:03d}"],
        "sourceType": "manual",
        "confidence": 1.0,
        "extractionRun": {
            "extractionVersion": "test-0.1",
            "extractionMethod": "manual",
            "modelProvider": None,
            "modelName": None,
            "promptVersion": None,
            "extractedAt": "2099-01-01T00:00:00Z",
            "parserCompatibilityAtExtraction": "compatible",
        },
    }


def _decision(number: int) -> dict[str, object]:
    return {
        "reviewer": "TEST_REVIEWER",
        "decidedAt": "2099-01-02T00:00:00Z",
        "evidenceSummary": f"Synthetic decision {number}.",
        "notes": None,
    }


def _edge(
    source_number: int,
    target_number: int,
    relation: str,
    number: int,
    *,
    canonical: bool = True,
) -> dict[str, object]:
    source, target = _episode(source_number), _episode(target_number)
    known = relation in {"before", "after", "same_time"}
    provenances = [
        _provenance(source, target, "before" if not known else relation, number)
    ]
    if relation == "conflict":
        provenances.append(_provenance(source, target, "after", number + 100))
    return {
        "from": source,
        "to": target,
        "relationState": relation,
        "stateReason": None if known else "Synthetic unresolved reason.",
        "adoptionStatus": "canonical" if canonical else "candidate",
        "reviewStatus": "confirmed" if known else "needs_more_context",
        "candidateProvenance": provenances,
        "humanDecision": _decision(number),
    }


def _document(*edges: dict[str, object], node_count: int = 5) -> dict[str, object]:
    return {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline",
        "scopeStoryCategory": "EVT",
        "visibility": "internal_only",
        "nodes": [_episode(number) for number in range(1, node_count + 1)],
        "edges": list(edges),
    }


def _mapping_record(number: int, episode: int = 1) -> dict[str, str]:
    return {
        "publicStoryId": f"PUBLIC_EVENT_{number:02d}",
        "publicEpisodeId": f"PUBLIC_EVENT_{number:02d}_E{episode:02d}",
        "storyLabel": f"合成イベント{number}",
        "episodeLabel": f"合成エピソード{number}-{episode}",
    }


def _mapping(*numbers: int) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (_episode(number)["storyId"], _episode(number)["episodeId"]): _mapping_record(
            number
        )
        for number in numbers
    }


def _public_schema_errors(document: dict[str, object]) -> list:
    schema = json.loads(PUBLIC_SCHEMA_PATH.read_text(encoding="utf-8"))
    return list(Draft7Validator(schema).iter_errors(document))


def test_projector_selects_only_adopted_confirmed_known_relations() -> None:
    document = _document(
        _edge(1, 2, "before", 1),
        _edge(2, 3, "same_time", 2),
        _edge(3, 4, "after", 3, canonical=False),
        _edge(4, 5, "unknown", 4, canonical=False),
        _edge(1, 5, "conflict", 5, canonical=False),
    )

    result = build_canonical_timeline_public_projection(document, _mapping(1, 2, 3))

    assert result["report"]["status"] == "clean"
    assert result["report"]["findings"] == []
    assert result["report"]["counts"] == {
        "inputNodeCount": 5,
        "inputRelationCount": 5,
        "eligibleRelationCount": 2,
        "ineligibleKnownRelationCount": 1,
        "unknownRelationCount": 1,
        "conflictRelationCount": 1,
        "projectedComponentCount": 1,
        "projectedNodeCount": 3,
        "projectedRelationCount": 2,
    }
    projection = result["projection"]
    assert _public_schema_errors(projection) == []
    assert projection["publishStatus"] == "projection_candidate"
    assert projection["unresolvedRelationSummary"]["unknownCount"] == 1
    assert projection["unresolvedRelationSummary"]["conflictCount"] == 1
    assert [
        relation["labelKey"] for relation in projection["components"][0]["relations"]
    ] == [
        "timeline_before",
        "timeline_same_time",
    ]


def test_projector_is_deterministic_and_does_not_mutate_inputs() -> None:
    document = _document(
        _edge(3, 4, "after", 3),
        _edge(1, 2, "before", 1),
    )
    mapping = _mapping(1, 2, 3, 4)
    original_document, original_mapping = deepcopy(document), deepcopy(mapping)
    reordered_document = deepcopy(document)
    reordered_document["nodes"].reverse()
    reordered_document["edges"].reverse()
    reordered_mapping = dict(reversed(list(mapping.items())))

    result = build_canonical_timeline_public_projection(document, mapping)
    reordered = build_canonical_timeline_public_projection(
        reordered_document, reordered_mapping
    )

    assert result == reordered
    assert document == original_document
    assert mapping == original_mapping
    assert [item["componentKey"] for item in result["projection"]["components"]] == [
        "component-0001",
        "component-0002",
    ]


def test_projector_ignores_unconnected_nodes_and_unused_mapping_entries() -> None:
    document = _document(_edge(1, 2, "before", 1), node_count=3)
    mapping = _mapping(1, 2, 3, 9)

    result = build_canonical_timeline_public_projection(document, mapping)

    nodes = result["projection"]["components"][0]["nodes"]
    assert {node["publicStoryId"] for node in nodes} == {
        "PUBLIC_EVENT_01",
        "PUBLIC_EVENT_02",
    }
    assert result["report"]["counts"]["projectedNodeCount"] == 2


def test_no_eligible_relations_returns_clean_empty_projection_with_aggregate() -> None:
    document = _document(
        _edge(1, 2, "unknown", 1, canonical=False),
        _edge(2, 3, "conflict", 2, canonical=False),
    )

    result = build_canonical_timeline_public_projection(document, {})

    assert result["report"]["status"] == "clean"
    assert result["projection"]["components"] == []
    assert result["projection"]["unresolvedRelationSummary"] == {
        "countScope": "canonical_artifact_only",
        "noticeKey": "unresolved_relations_not_shown",
        "unknownCount": 1,
        "conflictCount": 1,
    }
    assert _public_schema_errors(result["projection"]) == []


def test_missing_mapping_blocks_without_exposing_internal_identifiers() -> None:
    document = _document(_edge(1, 2, "before", 1))

    result = build_canonical_timeline_public_projection(document, _mapping(1))

    assert result["report"]["status"] == "blocked"
    assert result["report"]["findings"] == [
        {"rule": PUBLIC_MAPPING_MISSING, "count": 1}
    ]
    assert result["projection"]["components"] == []
    assert result["projection"]["unresolvedRelationSummary"] is None
    report_text = json.dumps(result["report"], ensure_ascii=False)
    assert "EVT_TEST" not in report_text
    assert "PUBLIC_EVENT" not in report_text


@pytest.mark.parametrize(
    "mutate",
    [
        lambda record: record.update({"storyId": "EVT_TEST_STORY_01"}),
        lambda record: record.update({"publicStoryId": "PUBLIC-EVENT"}),
        lambda record: record.update({"storyLabel": "line 1\nline 2"}),
        lambda record: record.update({"episodeLabel": "x" * 201}),
    ],
)
def test_invalid_public_mapping_blocks(mutate) -> None:
    document = _document(_edge(1, 2, "before", 1))
    mapping = _mapping(1, 2)
    mutate(mapping[(_episode(1)["storyId"], _episode(1)["episodeId"])])

    result = build_canonical_timeline_public_projection(document, mapping)

    assert result["report"]["status"] == "blocked"
    assert result["report"]["findings"] == [
        {"rule": PUBLIC_MAPPING_INVALID, "count": 1}
    ]


def test_duplicate_public_episode_id_blocks() -> None:
    document = _document(_edge(1, 2, "before", 1))
    mapping = _mapping(1, 2)
    mapping[(_episode(2)["storyId"], _episode(2)["episodeId"])]["publicEpisodeId"] = (
        mapping[(_episode(1)["storyId"], _episode(1)["episodeId"])]["publicEpisodeId"]
    )

    result = build_canonical_timeline_public_projection(document, mapping)

    assert result["report"]["findings"] == [
        {"rule": PUBLIC_EPISODE_ID_DUPLICATE, "count": 1}
    ]


def _edge_between(
    source: dict[str, str], target: dict[str, str], number: int
) -> dict[str, object]:
    edge = _edge(1, 2, "before", number)
    edge["from"] = deepcopy(source)
    edge["to"] = deepcopy(target)
    edge["candidateProvenance"] = [_provenance(source, target, "before", number)]
    return edge


def test_one_internal_story_cannot_map_to_multiple_public_stories() -> None:
    first, bridge, second = _episode(1, 1), _episode(2), _episode(1, 2)
    document = _document(node_count=0)
    document["nodes"] = [first, bridge, second]
    document["edges"] = [
        _edge_between(first, bridge, 1),
        _edge_between(bridge, second, 2),
    ]
    mapping = {
        (first["storyId"], first["episodeId"]): _mapping_record(1, 1),
        (bridge["storyId"], bridge["episodeId"]): _mapping_record(2, 1),
        (second["storyId"], second["episodeId"]): _mapping_record(3, 2),
    }

    result = build_canonical_timeline_public_projection(document, mapping)

    assert result["report"]["findings"] == [
        {"rule": PUBLIC_STORY_MAPPING_CONFLICT, "count": 1}
    ]


def test_one_public_story_cannot_map_from_multiple_internal_stories() -> None:
    first, second = _episode(1), _episode(2)
    document = _document(_edge_between(first, second, 1), node_count=2)
    mapping = {
        (first["storyId"], first["episodeId"]): _mapping_record(1, 1),
        (second["storyId"], second["episodeId"]): {
            **_mapping_record(2, 1),
            "publicStoryId": "PUBLIC_EVENT_01",
            "publicEpisodeId": "PUBLIC_EVENT_01_E02",
        },
    }

    result = build_canonical_timeline_public_projection(document, mapping)

    assert result["report"]["findings"] == [
        {"rule": PUBLIC_STORY_MAPPING_CONFLICT, "count": 1}
    ]


def test_one_public_story_cannot_have_multiple_labels() -> None:
    first, bridge, second = _episode(1, 1), _episode(2), _episode(1, 2)
    document = _document(node_count=0)
    document["nodes"] = [first, bridge, second]
    document["edges"] = [
        _edge_between(first, bridge, 1),
        _edge_between(bridge, second, 2),
    ]
    mapping = {
        (first["storyId"], first["episodeId"]): _mapping_record(1, 1),
        (bridge["storyId"], bridge["episodeId"]): _mapping_record(2, 1),
        (second["storyId"], second["episodeId"]): {
            **_mapping_record(1, 2),
            "storyLabel": "異なる合成イベント名",
        },
    }

    result = build_canonical_timeline_public_projection(document, mapping)

    assert result["report"]["findings"] == [
        {"rule": PUBLIC_STORY_LABEL_CONFLICT, "count": 1}
    ]


def test_duplicate_public_relation_blocks_with_schema_valid_empty_projection() -> None:
    first = _edge(1, 2, "before", 1)
    second = _edge(1, 2, "before", 2)
    document = _document(first, second)
    mapping = _mapping(1, 2)

    result = build_canonical_timeline_public_projection(document, mapping)

    assert result["report"]["status"] == "blocked"
    assert result["report"]["findings"] == [
        {"rule": PUBLIC_RELATION_DUPLICATE, "count": 1}
    ]
    assert result["projection"]["components"] == []
    assert _public_schema_errors(result["projection"]) == []
    assert validate_canonical_timeline_public_projection_consistency(
        {}, document, mapping
    ) == [{"rule": PUBLIC_RELATION_DUPLICATE, "count": 1}]


def test_invalid_canonical_baseline_blocks_before_projection() -> None:
    document = _document(_edge(1, 2, "before", 1))
    document["nodes"].append(deepcopy(document["nodes"][0]))

    result = build_canonical_timeline_public_projection(document, _mapping(1, 2))

    assert result["report"]["status"] == "blocked"
    assert result["report"]["findings"] == [{"rule": BASELINE_INVALID, "count": 1}]
    assert result["projection"]["components"] == []


def test_cross_document_validator_accepts_exact_projection_and_rejects_change() -> None:
    document = _document(_edge(1, 2, "before", 1))
    mapping = _mapping(1, 2)
    projection = build_canonical_timeline_public_projection(document, mapping)[
        "projection"
    ]

    assert (
        validate_canonical_timeline_public_projection_consistency(
            projection, document, mapping
        )
        == []
    )
    changed = deepcopy(projection)
    changed["components"][0]["relations"][0]["labelKey"] = "timeline_after"
    assert validate_canonical_timeline_public_projection_consistency(
        changed, document, mapping
    ) == [{"rule": PROJECTION_MISMATCH, "count": 1}]


def test_cross_document_validator_returns_safe_blocking_findings() -> None:
    document = _document(_edge(1, 2, "before", 1))

    findings = validate_canonical_timeline_public_projection_consistency(
        {}, document, {}
    )

    assert findings == [{"rule": PUBLIC_MAPPING_MISSING, "count": 2}]
    assert "EVT_TEST" not in json.dumps(findings)
