from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft7Validator

from agents.extractor.canonical_timeline_consistency import (
    CANONICAL_CYCLE,
    EDGE_DUPLICATE,
    SAME_TIME_CONTRADICTION,
)
from agents.extractor.canonical_timeline_promotion_plan import (
    build_canonical_timeline_promotion_plan,
)
from agents.extractor.canonical_timeline_promotion_preflight import (
    BASELINE_INVALID,
    _build_preflight_document,
    preflight_canonical_timeline_promotion,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
with open(
    PROJECT_ROOT / "schemas" / "canonical_timeline.schema.json", encoding="utf-8"
) as schema_file:
    CANONICAL_VALIDATOR = Draft7Validator(json.load(schema_file))


def _node(number: int) -> dict[str, str]:
    story = f"EVT_TEST_STORY_{number:02d}"
    return {"storyId": story, "episodeId": f"{story}_E01", "storyCategory": "EVT"}


def _source_edge(
    key: str, source: int, target: int, relation: str
) -> dict[str, object]:
    source_node, target_node = _node(source), _node(target)
    return {
        "reviewEdgeKey": key,
        "from": source_node,
        "to": target_node,
        "relationState": relation,
        "stateReason": None,
        "reviewStatus": "confirmed",
        "candidateProvenance": [
            {
                "candidateId": f"TEST_{key}",
                "sourceEpisode": deepcopy(source_node),
                "targetEpisode": deepcopy(target_node),
                "observedRelation": relation,
                "evidenceIds": ["TEST_EVIDENCE"],
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
        ],
        "humanDecision": {
            "reviewer": "TEST_REVIEWER",
            "decidedAt": "2099-01-02T00:00:00Z",
            "evidenceSummary": "Synthetic summary.",
            "notes": None,
        },
    }


def _plan(*edges: dict[str, object]) -> dict[str, object]:
    return build_canonical_timeline_promotion_plan(
        {
            "schemaVersion": "0.2",
            "documentType": "canonical_timeline_review_packet",
            "packetId": "ctrp-20990101T000000Z-deadbeef",
            "reviewBatchId": "test-batch-001",
            "classification": "local_internal",
            "commitAllowed": False,
            "scopeStoryCategory": "EVT",
            "visibility": "internal_only",
            "createdAt": "2099-01-01T00:00:00Z",
            "expiresAt": "2099-04-01T00:00:00Z",
            "storyPair": [
                {"storyId": "EVT_TEST_STORY_01", "storyCategory": "EVT"},
                {"storyId": "EVT_TEST_STORY_02", "storyCategory": "EVT"},
            ],
            "edges": list(edges),
        },
        created_at=datetime(2099, 1, 4, tzinfo=timezone.utc),
    )


def _canonical_edge(source: int, target: int, relation: str) -> dict[str, object]:
    edge = _source_edge("edge-canonical", source, target, relation)
    edge.pop("reviewEdgeKey")
    edge["adoptionStatus"] = "canonical"
    return edge


def _timeline(
    nodes: list[dict[str, str]] | None = None,
    edges: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline",
        "scopeStoryCategory": "EVT",
        "visibility": "internal_only",
        "nodes": nodes or [],
        "edges": edges or [],
    }


def test_empty_timeline_is_clean_and_projection_adds_missing_nodes_schema_valid() -> (
    None
):
    plan = _plan(_source_edge("edge-0001", 1, 2, "before"))
    timeline = _timeline()

    document, _ = _build_preflight_document(plan, timeline)

    assert list(CANONICAL_VALIDATOR.iter_errors(document)) == []
    assert document["nodes"] == [_node(1), _node(2)]
    assert preflight_canonical_timeline_promotion(plan, timeline) == {
        "status": "clean",
        "findings": [],
    }


def test_plan_cycle_and_transitive_same_time_are_aggregated_by_plan_entry() -> None:
    cycle_plan = _plan(_source_edge("edge-0001", 3, 1, "before"))
    cycle_timeline = _timeline(
        [_node(1), _node(2), _node(3)],
        [_canonical_edge(1, 2, "before"), _canonical_edge(2, 3, "before")],
    )
    same_time_plan = _plan(_source_edge("edge-0001", 1, 3, "before"))
    same_time_timeline = _timeline(
        [_node(1), _node(2), _node(3)],
        [_canonical_edge(1, 2, "same_time"), _canonical_edge(2, 3, "same_time")],
    )

    assert preflight_canonical_timeline_promotion(cycle_plan, cycle_timeline)[
        "findings"
    ] == [{"planEntryKey": "plan-entry-0001", "rule": CANONICAL_CYCLE, "count": 1}]
    assert preflight_canonical_timeline_promotion(same_time_plan, same_time_timeline)[
        "findings"
    ] == [
        {
            "planEntryKey": "plan-entry-0001",
            "rule": SAME_TIME_CONTRADICTION,
            "count": 1,
        }
    ]


def test_plan_same_time_is_attributed_when_existing_order_is_the_reported_edge() -> (
    None
):
    plan = _plan(_source_edge("edge-0001", 1, 2, "same_time"))
    timeline = _timeline([_node(1), _node(2)], [_canonical_edge(1, 2, "before")])

    assert preflight_canonical_timeline_promotion(plan, timeline) == {
        "status": "blocked",
        "findings": [
            {
                "planEntryKey": "plan-entry-0001",
                "rule": SAME_TIME_CONTRADICTION,
                "count": 1,
            }
        ],
    }


def test_exact_record_duplicate_is_plan_aggregate_but_existing_candidate_is_not() -> (
    None
):
    plan = _plan(_source_edge("edge-0001", 1, 2, "before"))
    projected, _ = _build_preflight_document(plan, _timeline())
    duplicate_timeline = _timeline([_node(1), _node(2)], [projected["edges"][0]])
    candidate = deepcopy(projected["edges"][0])
    candidate["adoptionStatus"] = "candidate"
    candidate_timeline = _timeline([_node(1), _node(2)], [candidate])

    assert preflight_canonical_timeline_promotion(plan, duplicate_timeline)[
        "findings"
    ] == [{"planEntryKey": "plan-entry-0001", "rule": EDGE_DUPLICATE, "count": 1}]
    assert preflight_canonical_timeline_promotion(plan, candidate_timeline) == {
        "status": "clean",
        "findings": [],
    }


def test_invalid_baseline_fails_closed_without_internal_details() -> None:
    plan = _plan(_source_edge("edge-0001", 1, 2, "before"))
    timeline = _timeline([_node(1)], [_canonical_edge(1, 2, "before")])

    assert preflight_canonical_timeline_promotion(plan, timeline) == {
        "status": "blocked",
        "findings": [{"rule": BASELINE_INVALID, "count": 1}],
    }


def test_does_not_mutate_inputs_and_is_independent_of_array_order() -> None:
    plan = _plan(
        _source_edge("edge-0001", 1, 2, "before"),
        _source_edge("edge-0002", 3, 1, "before"),
    )
    timeline = _timeline(
        [_node(3), _node(1), _node(2)],
        [_canonical_edge(1, 2, "before"), _canonical_edge(2, 3, "before")],
    )
    original_plan, original_timeline = deepcopy(plan), deepcopy(timeline)
    reordered_plan, reordered_timeline = deepcopy(plan), deepcopy(timeline)
    reordered_plan["entries"].reverse()
    reordered_timeline["nodes"].reverse()
    reordered_timeline["edges"].reverse()

    assert preflight_canonical_timeline_promotion(plan, timeline) == (
        preflight_canonical_timeline_promotion(reordered_plan, reordered_timeline)
    )
    assert plan == original_plan
    assert timeline == original_timeline
