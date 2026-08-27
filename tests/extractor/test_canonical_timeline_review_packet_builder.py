"""Canonical Timeline review packet builderの合成fixtureテスト。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from agents.extractor.canonical_timeline_review_packet_builder import (
    PacketBuildError,
    build_canonical_timeline_review_packet,
)
from scripts.validate_canonical_timeline_review_packet import (
    validate_packet_document,
)


def _run() -> dict[str, object]:
    return {
        "extractionVersion": "test-0.1",
        "extractionMethod": "rule_based",
        "modelProvider": None,
        "modelName": None,
        "promptVersion": None,
        "extractedAt": None,
        "parserCompatibilityAtExtraction": "compatible",
    }


def _candidate(
    candidate_id: str,
    relative_to: str,
    relation: str,
) -> dict[str, object]:
    return {
        "id": candidate_id,
        "kind": "relative_order",
        "relativeTo": relative_to,
        "relation": relation,
        "evidenceIds": [f"{candidate_id}_EVIDENCE"],
        "sourceType": "script",
        "confidence": 0.9,
        "extractionRun": _run(),
    }


def _document(
    story_id: str,
    episode_id: str,
    *candidates: dict[str, object],
    category: str = "EVT",
) -> dict[str, object]:
    return {
        "storyId": story_id,
        "episodeId": episode_id,
        "storyCategory": category,
        "extractionRun": _run(),
        "timelineCandidates": list(candidates),
    }


def _build(
    documents: list[tuple[str, dict[str, object]]],
    *,
    story_pair_index: int = 1,
) -> dict[str, object]:
    return build_canonical_timeline_review_packet(
        documents,
        story_pair_index=story_pair_index,
        review_batch_id="test-batch-001",
        created_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )


def test_builder_preserves_direction_relations_and_duplicate_observations() -> None:
    documents = [
        (
            "source-one.json",
            _document(
                "EVT_TEST_A",
                "TEST_A_E01",
                _candidate("TEST_BEFORE", "TEST_B_E01", "before"),
                _candidate("TEST_BEFORE_DUP", "TEST_B_E01", "before"),
                _candidate("TEST_SAME", "TEST_B_E01", "same_time"),
            ),
        ),
        (
            "source-two.json",
            _document(
                "EVT_TEST_B",
                "TEST_B_E01",
                _candidate("TEST_REVERSE", "TEST_A_E01", "after"),
            ),
        ),
        (
            "source-duplicate.json",
            _document(
                "EVT_TEST_A",
                "TEST_A_E01",
                _candidate("TEST_BEFORE", "TEST_B_E01", "before"),
            ),
        ),
    ]
    original = deepcopy(documents)

    packet = _build(documents)

    assert documents == original
    assert packet["schemaVersion"] == "0.2"
    assert packet["createdAt"] == "2099-01-01T00:00:00Z"
    assert packet["expiresAt"] == "2099-04-01T00:00:00Z"
    assert packet["storyPair"] == [
        {"storyId": "EVT_TEST_A", "storyCategory": "EVT"},
        {"storyId": "EVT_TEST_B", "storyCategory": "EVT"},
    ]
    edges = packet["edges"]
    assert [(edge["relationState"], edge["reviewStatus"]) for edge in edges] == [
        ("before", "pending"),
        ("same_time", "pending"),
        ("after", "pending"),
    ]
    assert [len(edge["candidateProvenance"]) for edge in edges] == [3, 1, 1]
    assert [item["candidateId"] for item in edges[0]["candidateProvenance"]].count(
        "TEST_BEFORE"
    ) == 2
    reverse = edges[2]
    assert reverse["from"]["storyId"] == "EVT_TEST_B"
    assert reverse["to"]["storyId"] == "EVT_TEST_A"
    assert reverse["candidateProvenance"][0]["observedRelation"] == "after"
    assert all(edge["humanDecision"] is None for edge in edges)
    assert validate_packet_document(
        packet,
        current_time=datetime(2099, 1, 1, tzinfo=timezone.utc),
    ).is_valid


def test_builder_is_deterministic_and_selects_one_sorted_story_pair() -> None:
    documents = [
        (
            "c.json",
            _document(
                "EVT_TEST_C",
                "TEST_C_E01",
                _candidate("TEST_C_TO_D", "TEST_D_E01", "before"),
            ),
        ),
        ("d.json", _document("EVT_TEST_D", "TEST_D_E01")),
        (
            "a.json",
            _document(
                "EVT_TEST_A",
                "TEST_A_E01",
                _candidate("TEST_A_TO_B", "TEST_B_E01", "after"),
            ),
        ),
        ("b.json", _document("EVT_TEST_B", "TEST_B_E01")),
    ]

    first = _build(documents, story_pair_index=2)
    second = _build(list(reversed(documents)), story_pair_index=2)

    assert first == second
    assert [item["storyId"] for item in first["storyPair"]] == [
        "EVT_TEST_C",
        "EVT_TEST_D",
    ]

    changed = deepcopy(documents)
    changed[0][1]["timelineCandidates"][0]["confidence"] = 0.8
    assert _build(changed, story_pair_index=2)["packetId"] != first["packetId"]


def test_builder_rejects_missing_selection_and_naive_created_at() -> None:
    documents = [("a.json", _document("EVT_TEST_A", "TEST_A_E01"))]
    with pytest.raises(PacketBuildError, match="story-pair-index-unavailable") as error:
        _build(documents)
    assert error.value.available_story_pairs == 0

    with pytest.raises(PacketBuildError, match="created-at-timezone-required"):
        build_canonical_timeline_review_packet(
            documents,
            story_pair_index=1,
            review_batch_id="test-batch-001",
            created_at=datetime(2099, 1, 1),
        )


def test_builder_does_not_add_order_public_or_promotion_fields() -> None:
    packet = _build(
        [
            (
                "a.json",
                _document(
                    "EVT_TEST_A",
                    "TEST_A_E01",
                    _candidate("TEST_A_TO_B", "TEST_B_E01", "before"),
                ),
            ),
            ("b.json", _document("EVT_TEST_B", "TEST_B_E01")),
        ]
    )
    serialized = str(packet)
    for forbidden in (
        "canonicalOrder",
        "releaseOrder",
        "displayOrder",
        "episodeNumber",
        "adoptionStatus",
        "publicUrl",
        "sourcePath",
        "rawText",
    ):
        assert forbidden not in serialized
    created = datetime.fromisoformat(packet["createdAt"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(packet["expiresAt"].replace("Z", "+00:00"))
    assert expires - created == timedelta(days=90)


def test_builder_only_packetizes_unique_cross_event_relative_order() -> None:
    explicit = _candidate("TEST_EXPLICIT", "TEST_C_E01", "before")
    explicit["kind"] = "explicit_order"
    packet = _build(
        [
            (
                "source.json",
                _document(
                    "EVT_TEST_A",
                    "TEST_A_E01",
                    _candidate("TEST_VALID", "TEST_B_E01", "before"),
                    _candidate("TEST_SAME", "TEST_A_E02", "before"),
                    _candidate("TEST_MISSING", "TEST_MISSING_E01", "before"),
                    _candidate("TEST_OUT", "TEST_MAIN_E01", "before"),
                    _candidate("TEST_AMBIGUOUS", "TEST_SHARED_E01", "before"),
                    explicit,
                ),
            ),
            ("target.json", _document("EVT_TEST_B", "TEST_B_E01")),
            ("same.json", _document("EVT_TEST_A", "TEST_A_E02")),
            (
                "out.json",
                _document("MAIN_TEST", "TEST_MAIN_E01", category="MAIN"),
            ),
            ("shared-c.json", _document("EVT_TEST_C", "TEST_SHARED_E01")),
            ("shared-d.json", _document("EVT_TEST_D", "TEST_SHARED_E01")),
        ]
    )

    assert len(packet["edges"]) == 1
    provenance = packet["edges"][0]["candidateProvenance"]
    assert [item["candidateId"] for item in provenance] == ["TEST_VALID"]
