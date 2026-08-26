from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry, Resource

from agents.extractor.canonical_timeline_review_packet_consistency import (
    CONFLICT_PROVENANCE_NOT_CONFLICTING,
    EDGE_OUTSIDE_STORY_PAIR,
    EDGE_RECORD_DUPLICATE,
    PROVENANCE_ENDPOINT_MISMATCH,
    REVIEW_EDGE_KEY_DUPLICATE,
    SAME_STORY_EDGE,
    SELF_EDGE,
    validate_canonical_timeline_review_packet_consistency,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
CANONICAL_SCHEMA = json.loads(
    (PROJECT_ROOT / "schemas" / "canonical_timeline.schema.json").read_text(
        encoding="utf-8"
    )
)
PACKET_SCHEMA = json.loads(
    (
        PROJECT_ROOT / "schemas" / "canonical_timeline_review_packet.schema.json"
    ).read_text(encoding="utf-8")
)
SCHEMA_REGISTRY = Registry().with_resources(
    [
        (CANONICAL_SCHEMA["$id"], Resource.from_contents(CANONICAL_SCHEMA)),
        (PACKET_SCHEMA["$id"], Resource.from_contents(PACKET_SCHEMA)),
    ]
)
PACKET_VALIDATOR = Draft7Validator(
    PACKET_SCHEMA,
    registry=SCHEMA_REGISTRY,
    format_checker=FormatChecker(),
)


def _episode(story: str, suffix: str = "E01") -> dict[str, str]:
    return {
        "storyId": story,
        "episodeId": f"{story}_{suffix}",
        "storyCategory": "EVT",
    }


def _provenance(
    source: dict[str, str],
    target: dict[str, str],
    relation: str = "before",
    candidate_id: str = "TEST_CANDIDATE_001",
) -> dict[str, object]:
    return {
        "candidateId": candidate_id,
        "sourceEpisode": deepcopy(source),
        "targetEpisode": deepcopy(target),
        "observedRelation": relation,
        "evidenceIds": [f"TEST_EVIDENCE_{candidate_id}"],
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


def _decision() -> dict[str, object]:
    return {
        "reviewer": "TEST_REVIEWER",
        "decidedAt": "2099-01-02T00:00:00Z",
        "evidenceSummary": "Synthetic evidence summary.",
        "notes": None,
    }


def _edge(
    key: str = "edge-0001",
    relation: str = "before",
    *,
    source: dict[str, str] | None = None,
    target: dict[str, str] | None = None,
    status: str = "pending",
    provenance: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    source = source or _episode("EVT_TEST_STORY_01")
    target = target or _episode("EVT_TEST_STORY_02")
    if provenance is None:
        observed = (
            relation if relation in {"before", "after", "same_time"} else "before"
        )
        provenance = [_provenance(source, target, observed)]
        if relation == "conflict":
            provenance.append(
                _provenance(source, target, "after", "TEST_CANDIDATE_002")
            )
    return {
        "reviewEdgeKey": key,
        "from": deepcopy(source),
        "to": deepcopy(target),
        "relationState": relation,
        "stateReason": (
            "Synthetic unresolved reason."
            if relation in {"unknown", "conflict"}
            else None
        ),
        "reviewStatus": status,
        "candidateProvenance": provenance,
        "humanDecision": None if status == "pending" else _decision(),
    }


def _packet(*edges: dict[str, object]) -> dict[str, object]:
    return {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_review_packet",
        "packetId": "ctrp-20990101T000000Z-deadbeef",
        "reviewBatchId": "test-batch-001",
        "classification": "local_internal",
        "commitAllowed": False,
        "scopeStoryCategory": "EVT",
        "visibility": "internal_only",
        "createdAt": "2099-01-01T00:00:00Z",
        "storyPair": [
            {"storyId": "EVT_TEST_STORY_01", "storyCategory": "EVT"},
            {"storyId": "EVT_TEST_STORY_02", "storyCategory": "EVT"},
        ],
        "edges": list(edges) or [_edge()],
    }


def _rules(packet: dict[str, object]) -> list[str]:
    assert list(PACKET_VALIDATOR.iter_errors(packet)) == []
    return [
        finding["rule"]
        for finding in validate_canonical_timeline_review_packet_consistency(packet)
    ]


def test_clean_states_and_review_outcomes_have_no_findings() -> None:
    edges = [
        _edge("edge-0001", "before"),
        _edge("edge-0002", "after", status="confirmed"),
        _edge("edge-0003", "same_time", status="rejected"),
        _edge("edge-0004", "unknown", status="needs_more_context"),
        _edge("edge-0005", "conflict"),
    ]
    assert _rules(_packet(*edges)) == []


def test_reports_pair_same_story_self_and_key_or_record_duplicates() -> None:
    first = _edge()
    outside = _edge(
        "edge-0002",
        source=_episode("EVT_TEST_STORY_03"),
        target=_episode("EVT_TEST_STORY_02"),
    )
    same_story = _edge(
        "edge-0003",
        source=_episode("EVT_TEST_STORY_01"),
        target=_episode("EVT_TEST_STORY_01", "E02"),
    )
    self_edge = _edge(
        "edge-0004",
        source=_episode("EVT_TEST_STORY_01"),
        target=_episode("EVT_TEST_STORY_01"),
    )
    rules = _rules(_packet(first, deepcopy(first), outside, same_story, self_edge))
    assert EDGE_OUTSIDE_STORY_PAIR in rules
    assert SAME_STORY_EDGE in rules
    assert SELF_EDGE in rules
    assert REVIEW_EDGE_KEY_DUPLICATE in rules
    assert EDGE_RECORD_DUPLICATE in rules


def test_provenance_endpoints_and_conflict_meaning_are_checked() -> None:
    source = _episode("EVT_TEST_STORY_01")
    target = _episode("EVT_TEST_STORY_02")
    wrong = _episode("EVT_TEST_STORY_03")
    mismatch = _edge(
        provenance=[_provenance(source, wrong)],
    )
    equivalent = _edge(
        "edge-0002",
        "conflict",
        provenance=[
            _provenance(source, target, "before", "TEST_CANDIDATE_010"),
            _provenance(target, source, "after", "TEST_CANDIDATE_011"),
        ],
    )
    rules = _rules(_packet(mismatch, equivalent))
    assert PROVENANCE_ENDPOINT_MISMATCH in rules
    assert CONFLICT_PROVENANCE_NOT_CONFLICTING in rules


def test_reverse_direction_actual_conflict_is_valid() -> None:
    source = _episode("EVT_TEST_STORY_01")
    target = _episode("EVT_TEST_STORY_02")
    edge = _edge(
        relation="conflict",
        provenance=[
            _provenance(source, target, "before", "TEST_CANDIDATE_020"),
            _provenance(target, source, "before", "TEST_CANDIDATE_021"),
        ],
    )
    assert _rules(_packet(edge)) == []


def test_distinct_provenance_is_not_an_exact_record_duplicate() -> None:
    first = _edge("edge-0001")
    second = deepcopy(first)
    second["reviewEdgeKey"] = "edge-0002"
    second["candidateProvenance"][0]["candidateId"] = "TEST_CANDIDATE_DISTINCT"
    rules = _rules(_packet(first, second))
    assert REVIEW_EDGE_KEY_DUPLICATE not in rules
    assert EDGE_RECORD_DUPLICATE not in rules


def test_different_keys_with_otherwise_identical_records_are_duplicates() -> None:
    first = _edge("edge-0001")
    second = deepcopy(first)
    second["reviewEdgeKey"] = "edge-0002"
    rules = _rules(_packet(first, second))
    assert REVIEW_EDGE_KEY_DUPLICATE not in rules
    assert EDGE_RECORD_DUPLICATE in rules


def test_input_is_unchanged_and_findings_ignore_array_order() -> None:
    first = _edge()
    second = deepcopy(first)
    packet = _packet(first, second)
    original = deepcopy(packet)
    reordered = deepcopy(packet)
    reordered["storyPair"].reverse()
    reordered["edges"].reverse()
    for edge in reordered["edges"]:
        edge["candidateProvenance"].reverse()

    findings = validate_canonical_timeline_review_packet_consistency(packet)
    assert packet == original
    assert findings == validate_canonical_timeline_review_packet_consistency(reordered)
