"""canonical Timeline review packet schema contract tests using synthetic data only."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from referencing import Registry, Resource

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "canonical_timeline_review_packet.schema.json"
CANONICAL_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "canonical_timeline.schema.json"


def _load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator() -> Draft7Validator:
    packet_schema = _load_schema(SCHEMA_PATH)
    canonical_schema = _load_schema(CANONICAL_SCHEMA_PATH)
    registry = Registry().with_resources(
        [
            (packet_schema["$id"], Resource.from_contents(packet_schema)),
            (canonical_schema["$id"], Resource.from_contents(canonical_schema)),
        ]
    )
    return Draft7Validator(packet_schema, registry=registry)


def _errors(document: dict) -> list[str]:
    return [
        error.message
        for error in sorted(
            _validator().iter_errors(document), key=lambda error: list(error.path)
        )
    ]


def _episode_ref(number: int) -> dict:
    return {
        "storyId": f"EVT_TEST_STORY_{number:02d}",
        "episodeId": f"EVT_TEST_STORY_{number:02d}_E01",
        "storyCategory": "EVT",
    }


def _provenance(**overrides: object) -> dict:
    provenance = {
        "candidateId": "TEST_CANDIDATE_001",
        "sourceEpisode": _episode_ref(1),
        "targetEpisode": _episode_ref(2),
        "observedRelation": "before",
        "evidenceIds": ["TEST_EVIDENCE_001"],
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
    provenance.update(overrides)
    return provenance


def _decision() -> dict:
    return {
        "reviewer": "TEST_REVIEWER",
        "decidedAt": "2099-01-02T00:00:00Z",
        "evidenceSummary": "Synthetic evidence supports the decision.",
        "notes": None,
    }


def _edge(relation_state: str = "before", **overrides: object) -> dict:
    edge = {
        "reviewEdgeKey": "edge-0001",
        "from": _episode_ref(1),
        "to": _episode_ref(2),
        "relationState": relation_state,
        "stateReason": None,
        "reviewStatus": "pending",
        "candidateProvenance": [_provenance()],
        "humanDecision": None,
    }
    if relation_state in {"unknown", "conflict"}:
        edge["stateReason"] = "Synthetic unresolved state is retained."
    if relation_state == "conflict":
        edge["candidateProvenance"].append(
            _provenance(candidateId="TEST_CANDIDATE_002", observedRelation="after")
        )
    edge.update(overrides)
    return edge


def _packet(*edges: dict, **overrides: object) -> dict:
    packet = {
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
    packet.update(overrides)
    return packet


def _packet_v2(*edges: dict, **overrides: object) -> dict:
    packet = _packet(*edges)
    packet.update(
        {
            "schemaVersion": "0.2",
            "expiresAt": "2099-04-01T00:00:00Z",
        }
    )
    packet.update(overrides)
    return packet


def test_schema_is_valid_draft7_and_external_refs_resolve_offline():
    Draft7Validator.check_schema(_load_schema(SCHEMA_PATH))
    assert _errors(_packet()) == []
    assert _errors(_packet_v2()) == []


def test_schema_versions_keep_v01_compatible_and_require_v02_expiration():
    assert _errors(_packet(expiresAt="2099-04-01T00:00:00Z")) != []
    assert _errors(_packet(schemaVersion="0.2")) != []
    assert _errors(_packet_v2(expiresAt="not-a-date")) != []


def test_minimal_pending_known_edge_is_valid_and_not_promoted():
    edge = _edge()
    assert "adoptionStatus" not in edge
    assert _errors(_packet(edge)) == []


@pytest.mark.parametrize(
    "relation_state", ("before", "after", "same_time", "unknown", "conflict")
)
def test_all_relation_states_have_valid_synthetic_representation(relation_state: str):
    assert _errors(_packet(_edge(relation_state))) == []


@pytest.mark.parametrize(
    "review_status", ("pending", "confirmed", "rejected", "needs_more_context")
)
def test_review_status_and_human_decision_conditionals(review_status: str):
    decision = None if review_status == "pending" else _decision()
    assert (
        _errors(_packet(_edge(reviewStatus=review_status, humanDecision=decision)))
        == []
    )

    invalid = _edge(reviewStatus=review_status, humanDecision=_decision())
    if review_status != "pending":
        invalid["humanDecision"] = None
    assert _errors(_packet(invalid)) != []


def test_confirmed_requires_known_relation_and_human_decision():
    assert (
        _errors(_packet(_edge(reviewStatus="confirmed", humanDecision=_decision())))
        == []
    )
    assert _errors(_packet(_edge(reviewStatus="confirmed", humanDecision=None))) != []
    assert (
        _errors(
            _packet(
                _edge("unknown", reviewStatus="confirmed", humanDecision=_decision())
            )
        )
        != []
    )
    assert (
        _errors(
            _packet(
                _edge("conflict", reviewStatus="confirmed", humanDecision=_decision())
            )
        )
        != []
    )


@pytest.mark.parametrize("relation_state", ("unknown", "conflict"))
def test_unresolved_states_require_reason_and_retain_nonconfirmed_outcomes(
    relation_state: str,
):
    assert (
        _errors(
            _packet(
                _edge(
                    relation_state, reviewStatus="rejected", humanDecision=_decision()
                )
            )
        )
        == []
    )
    assert (
        _errors(
            _packet(
                _edge(
                    relation_state,
                    reviewStatus="needs_more_context",
                    humanDecision=_decision(),
                )
            )
        )
        == []
    )
    assert _errors(_packet(_edge(relation_state, stateReason=None))) != []

    if relation_state == "conflict":
        assert (
            _errors(_packet(_edge(relation_state, candidateProvenance=[_provenance()])))
            != []
        )
    else:
        assert _errors(_packet(_edge(relation_state, candidateProvenance=[]))) != []


def test_story_pair_is_exactly_two_distinct_event_story_refs():
    packet = _packet(
        storyPair=[{"storyId": "EVT_TEST_STORY_01", "storyCategory": "EVT"}]
    )
    assert _errors(packet) != []

    packet = _packet(
        storyPair=[
            {"storyId": "EVT_TEST_STORY_01", "storyCategory": "EVT"},
            {"storyId": "EVT_TEST_STORY_02", "storyCategory": "EVT"},
            {"storyId": "EVT_TEST_STORY_03", "storyCategory": "EVT"},
        ]
    )
    assert _errors(packet) != []

    packet = _packet(
        storyPair=[
            {"storyId": "EVT_TEST_STORY_01", "storyCategory": "EVT"},
            {"storyId": "EVT_TEST_STORY_01", "storyCategory": "EVT"},
        ]
    )
    assert _errors(packet) != []

    packet = _packet(
        storyPair=[
            {"storyId": "EVT_TEST_STORY_01", "storyCategory": "MAIN"},
            {"storyId": "EVT_TEST_STORY_02", "storyCategory": "EVT"},
        ]
    )
    assert _errors(packet) != []


def test_event_internal_and_no_commit_constants_are_enforced():
    for field, value in (
        ("schemaVersion", "0.3"),
        ("documentType", "canonical_timeline"),
        ("classification", "public"),
        ("scopeStoryCategory", "MAIN"),
        ("visibility", "public"),
        ("commitAllowed", True),
    ):
        assert _errors(_packet(**{field: value})) != []


def test_review_edge_key_uniqueness_is_a_semantic_validator_boundary():
    second = _edge(reviewEdgeKey="edge-0001")
    second["relationState"] = "after"
    # Draft 7では異なるobject配列内の特定property一意性を表現できない。
    # このruleは後続のsemantic validatorが担当する。
    packet = _packet(_edge(), second)
    assert _errors(packet) == []


@pytest.mark.parametrize(
    "forbidden_field",
    (
        "rawText",
        "path",
        "sourcePath",
        "publicUrl",
        "publicId",
        "canonicalOrder",
        "releaseOrder",
        "displayOrder",
        "episodeNumber",
        "globalOrder",
        "totalOrder",
        "sequence",
        "adoptionStatus",
        "edgeId",
    ),
)
def test_forbidden_raw_public_and_promotion_fields_are_rejected(forbidden_field: str):
    edge = copy.deepcopy(_edge())
    edge[forbidden_field] = "TEST_FORBIDDEN"
    assert _errors(_packet(edge)) != []


def test_pair_membership_and_cross_story_endpoints_are_semantic_validator_boundary():
    edge = _edge()
    edge["to"] = _episode_ref(3)
    # Draft 7ではendpointのstoryIdとstoryPairを動的比較できない。
    # pair外endpointおよび同一story edgeは後続semantic validatorが拒否する。
    assert _errors(_packet(edge)) == []

    edge["to"] = {
        "storyId": "EVT_TEST_STORY_01",
        "episodeId": "EVT_TEST_STORY_01_E02",
        "storyCategory": "EVT",
    }
    assert _errors(_packet(edge)) == []

    edge = _edge()
    edge["candidateProvenance"] = [_provenance(targetEpisode=_episode_ref(3))]
    # provenanceのepisode参照とstoryPair / edge両端の動的照合も後続責務。
    assert _errors(_packet(edge)) == []


def test_packet_requires_at_least_one_edge_and_valid_created_at():
    assert _errors(_packet(edges=[])) != []
    assert _errors(_packet(createdAt="not-a-date")) != []


def test_existing_canonical_schema_is_not_modified():
    canonical_schema = _load_schema(CANONICAL_SCHEMA_PATH)
    assert (
        canonical_schema["$id"]
        == "https://detariki-kb/schemas/canonical_timeline.schema.json"
    )
    assert "ReviewEdge" not in canonical_schema["definitions"]
