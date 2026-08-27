"""Canonical Timeline promotion plan projectionの合成fixtureテスト。"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry, Resource

from agents.extractor.canonical_timeline_promotion_plan import (
    ELIGIBLE_EDGE_EXTRA,
    ELIGIBLE_EDGE_MISSING,
    EXPIRY_STATUS_MISMATCH,
    PLAN_ENTRY_KEY_DUPLICATE,
    REVIEW_EDGE_KEY_DUPLICATE,
    SOURCE_EDGE_MODIFIED,
    SOURCE_PACKET_MISMATCH,
    STORY_PAIR_MISMATCH,
    PromotionPlanBuildError,
    build_canonical_timeline_promotion_plan,
    validate_canonical_timeline_promotion_plan_consistency,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent


def _plan_validator() -> Draft7Validator:
    schemas = [
        json.loads((PROJECT_ROOT / path).read_text(encoding="utf-8"))
        for path in (
            "schemas/canonical_timeline_promotion_plan.schema.json",
            "schemas/canonical_timeline_review_packet.schema.json",
            "schemas/canonical_timeline.schema.json",
        )
    ]
    registry = Registry().with_resources(
        [(schema["$id"], Resource.from_contents(schema)) for schema in schemas]
    )
    return Draft7Validator(
        schemas[0], registry=registry, format_checker=FormatChecker()
    )


def _episode(number: int) -> dict[str, str]:
    story = f"EVT_TEST_STORY_{number:02d}"
    return {"storyId": story, "episodeId": f"{story}_E01", "storyCategory": "EVT"}


def _decision() -> dict[str, object]:
    return {
        "reviewer": "TEST_REVIEWER",
        "decidedAt": "2099-01-02T00:00:00Z",
        "evidenceSummary": "Synthetic summary.",
        "notes": None,
    }


def _edge(
    key: str, relation: str, status: str, *, decision: bool = False
) -> dict[str, object]:
    source, target = _episode(1), _episode(2)
    return {
        "reviewEdgeKey": key,
        "from": source,
        "to": target,
        "relationState": relation,
        "stateReason": None
        if relation in {"before", "after", "same_time"}
        else "TEST_REASON",
        "reviewStatus": status,
        "candidateProvenance": [
            {
                "candidateId": f"TEST_{key}",
                "sourceEpisode": deepcopy(source),
                "targetEpisode": deepcopy(target),
                "observedRelation": "before",
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
        "humanDecision": _decision() if decision else None,
    }


def _packet(*, expires_at: str = "2099-04-01T00:00:00Z") -> dict[str, object]:
    return {
        "schemaVersion": "0.2",
        "documentType": "canonical_timeline_review_packet",
        "packetId": "ctrp-20990101T000000Z-deadbeef",
        "reviewBatchId": "test-batch-001",
        "classification": "local_internal",
        "commitAllowed": False,
        "scopeStoryCategory": "EVT",
        "visibility": "internal_only",
        "createdAt": "2099-01-01T00:00:00Z",
        "expiresAt": expires_at,
        "storyPair": [
            {"storyId": "EVT_TEST_STORY_01", "storyCategory": "EVT"},
            {"storyId": "EVT_TEST_STORY_02", "storyCategory": "EVT"},
        ],
        "edges": [
            _edge("edge-0003", "same_time", "confirmed", decision=True),
            _edge("edge-0001", "before", "confirmed", decision=True),
            _edge("edge-0002", "after", "pending"),
            _edge("edge-0004", "unknown", "needs_more_context", decision=True),
        ],
    }


def _build(
    packet: dict[str, object], created_at: datetime | None = None
) -> dict[str, object]:
    return build_canonical_timeline_promotion_plan(
        packet, created_at=created_at or datetime(2099, 1, 4, tzinfo=timezone.utc)
    )


def _rules(plan: dict[str, object], packet: dict[str, object]) -> list[str]:
    return [
        item["rule"]
        for item in validate_canonical_timeline_promotion_plan_consistency(plan, packet)
    ]


def test_builder_projects_only_confirmed_known_edges_without_mutating_input() -> None:
    packet = _packet()
    original = deepcopy(packet)

    plan = _build(packet)

    assert packet == original
    assert plan["createdAt"] == "2099-01-04T00:00:00Z"
    assert plan["sourcePacket"]["expiredAtPlanning"] is False
    assert [entry["sourceEdge"]["reviewEdgeKey"] for entry in plan["entries"]] == [
        "edge-0001",
        "edge-0003",
    ]
    assert [entry["planEntryKey"] for entry in plan["entries"]] == [
        "plan-entry-0001",
        "plan-entry-0002",
    ]
    assert plan["entries"][0]["sourceEdge"] == packet["edges"][1]
    assert _rules(plan, packet) == []
    assert list(_plan_validator().iter_errors(plan)) == []


def test_builder_is_deterministic_under_packet_edge_reordering() -> None:
    packet = _packet()
    reordered = deepcopy(packet)
    reordered["edges"].reverse()
    assert _build(packet) == _build(reordered)


def test_builder_requires_v02_eligible_edge_and_aware_created_at() -> None:
    v01 = _packet()
    v01["schemaVersion"] = "0.1"
    with pytest.raises(PromotionPlanBuildError, match="source-packet-v02-required"):
        _build(v01)
    empty = _packet()
    for edge in empty["edges"]:
        edge["reviewStatus"] = "pending"
        edge["humanDecision"] = None
    with pytest.raises(
        PromotionPlanBuildError, match="eligible-confirmed-known-relations-empty"
    ):
        _build(empty)
    with pytest.raises(PromotionPlanBuildError, match="created-at-timezone-required"):
        _build(_packet(), datetime(2099, 1, 4))


def test_expired_packet_is_retained_as_warning_only_status() -> None:
    packet = _packet(expires_at="2099-01-03T00:00:00Z")
    plan = _build(packet)
    assert plan["sourcePacket"]["expiredAtPlanning"] is True
    assert _rules(plan, packet) == []


def test_builder_retains_fractional_seconds_for_expiry_and_plan_identity() -> None:
    packet = _packet(expires_at="2099-01-04T00:00:00Z")
    exact = _build(packet, datetime(2099, 1, 4, tzinfo=timezone.utc))
    after_expiry = _build(
        packet, datetime(2099, 1, 4, 0, 0, 0, 500000, tzinfo=timezone.utc)
    )

    assert exact["sourcePacket"]["expiredAtPlanning"] is False
    assert after_expiry["createdAt"] == "2099-01-04T00:00:00.500000Z"
    assert after_expiry["sourcePacket"]["expiredAtPlanning"] is True
    assert after_expiry["planId"] != exact["planId"]
    assert _rules(after_expiry, packet) == []


def test_builder_rejects_entry_counts_beyond_four_digit_key_capacity() -> None:
    packet = _packet()
    packet["edges"] = [
        _edge(f"edge-{number:04d}", "before", "confirmed", decision=True)
        for number in range(10000)
    ]

    with pytest.raises(
        PromotionPlanBuildError,
        match="eligible-edge-count-exceeds-plan-entry-key-capacity",
    ):
        _build(packet)


def test_validator_detects_source_packet_pair_expiry_and_edge_modifications() -> None:
    packet = _packet()
    plan = _build(packet)
    changed = deepcopy(plan)
    changed["sourcePacket"]["packetId"] = "ctrp-20990101T000000Z-00000000"
    changed["storyPair"].reverse()
    changed["sourcePacket"]["expiredAtPlanning"] = True
    changed["entries"][0]["sourceEdge"]["humanDecision"]["reviewer"] = "TEST_CHANGED"
    rules = _rules(changed, packet)
    assert SOURCE_PACKET_MISMATCH in rules
    assert STORY_PAIR_MISMATCH in rules
    assert EXPIRY_STATUS_MISMATCH in rules
    assert SOURCE_EDGE_MODIFIED in rules


def test_validator_detects_missing_extra_and_duplicate_keys_deterministically() -> None:
    packet = _packet()
    plan = _build(packet)
    changed = deepcopy(plan)
    changed["entries"].pop()
    extra = deepcopy(plan["entries"][0])
    extra["planEntryKey"] = "plan-entry-0099"
    extra["sourceEdge"]["reviewEdgeKey"] = "edge-0099"
    changed["entries"].append(extra)
    duplicate = deepcopy(plan["entries"][0])
    changed["entries"].append(duplicate)
    rules = _rules(changed, packet)
    assert ELIGIBLE_EDGE_MISSING in rules
    assert ELIGIBLE_EDGE_EXTRA in rules
    assert PLAN_ENTRY_KEY_DUPLICATE in rules
    assert REVIEW_EDGE_KEY_DUPLICATE in rules
    reordered = deepcopy(changed)
    reordered["entries"].reverse()
    assert validate_canonical_timeline_promotion_plan_consistency(
        changed, packet
    ) == validate_canonical_timeline_promotion_plan_consistency(reordered, packet)
