"""canonical Timeline v0.1 schema contract tests using synthetic data only."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "canonical_timeline.schema.json"


def _load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as file:
        return json.load(file)


def _validate(document: dict) -> list[str]:
    errors = sorted(
        Draft7Validator(_load_schema()).iter_errors(document),
        key=lambda error: list(error.path),
    )
    return [f"{list(error.path)}: {error.message}" for error in errors]


def _episode_ref(number: int) -> dict:
    return {
        "storyId": f"EVT_TEST_STORY_{number:02d}",
        "episodeId": f"EVT_TEST_STORY_{number:02d}_E01",
        "storyCategory": "EVT",
    }


def _provenance(**overrides) -> dict:
    provenance = {
        "candidateId": "TEST_CANDIDATE_001",
        "sourceEpisode": _episode_ref(1),
        "targetEpisode": _episode_ref(2),
        "observedRelation": "before",
        "evidenceIds": ["TEST_EVIDENCE_001"],
        "sourceType": "ai_inferred",
        "confidence": 0.75,
        "extractionRun": {
            "extractionVersion": "test-0.1",
            "extractionMethod": "rule_based",
            "modelProvider": None,
            "modelName": None,
            "promptVersion": None,
            "extractedAt": "2099-01-01T00:00:00Z",
            "parserCompatibilityAtExtraction": "compatible",
        },
    }
    provenance.update(overrides)
    return provenance


def _human_decision() -> dict:
    return {
        "reviewer": "TEST_REVIEWER",
        "decidedAt": "2099-01-02T00:00:00Z",
        "evidenceSummary": "Synthetic evidence supports this review decision.",
        "notes": None,
    }


def _edge(relation_state: str = "before", **overrides) -> dict:
    edge = {
        "from": _episode_ref(1),
        "to": _episode_ref(2),
        "relationState": relation_state,
        "stateReason": None,
        "adoptionStatus": "candidate",
        "reviewStatus": "pending",
        "candidateProvenance": [_provenance()],
        "humanDecision": None,
    }
    if relation_state in {"unknown", "conflict"}:
        edge["stateReason"] = "Synthetic reason retained for the unresolved state."
    if relation_state == "conflict":
        edge["candidateProvenance"].append(
            _provenance(
                candidateId="TEST_CANDIDATE_002",
                observedRelation="after",
            )
        )
    edge.update(overrides)
    return edge


def _document(*edges: dict, **overrides) -> dict:
    document = {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline",
        "scopeStoryCategory": "EVT",
        "visibility": "internal_only",
        "nodes": [_episode_ref(1), _episode_ref(2)],
        "edges": list(edges),
    }
    document.update(overrides)
    return document


def test_schema_file_is_valid_draft7_schema():
    Draft7Validator.check_schema(_load_schema())


@pytest.mark.parametrize(
    "relation_state",
    ("before", "after", "same_time", "unknown", "conflict"),
)
def test_all_relation_states_have_valid_synthetic_representation(relation_state):
    assert _validate(_document(_edge(relation_state))) == []


def test_confirmed_known_relation_requires_human_decision():
    edge = _edge(
        "before",
        adoptionStatus="canonical",
        reviewStatus="confirmed",
        humanDecision=None,
    )
    assert _validate(_document(edge)) != []


def test_confirmed_known_relation_with_minimal_human_decision_is_canonical():
    edge = _edge(
        "same_time",
        adoptionStatus="canonical",
        reviewStatus="confirmed",
        humanDecision=_human_decision(),
    )
    assert _validate(_document(edge)) == []


def test_human_decision_rejects_invalid_datetime_format():
    decision = _human_decision()
    decision["decidedAt"] = "not-a-date"
    edge = _edge(
        "before",
        reviewStatus="confirmed",
        humanDecision=decision,
    )
    assert _validate(_document(edge)) != []


def test_confirmed_known_relation_can_remain_candidate_before_promotion():
    edge = _edge(
        "before",
        adoptionStatus="candidate",
        reviewStatus="confirmed",
        humanDecision=_human_decision(),
    )
    assert _validate(_document(edge)) == []


@pytest.mark.parametrize("review_status", ("pending", "rejected", "needs_more_context"))
def test_non_confirmed_review_status_cannot_be_canonical(review_status):
    edge = _edge(
        "after",
        adoptionStatus="canonical",
        reviewStatus=review_status,
        humanDecision=_human_decision(),
    )
    assert _validate(_document(edge)) != []


def test_pending_review_status_rejects_human_decision():
    edge = _edge("before", reviewStatus="pending", humanDecision=_human_decision())
    assert _validate(_document(edge)) != []


@pytest.mark.parametrize("review_status", ("rejected", "needs_more_context"))
def test_decision_statuses_require_human_decision(review_status):
    edge = _edge("before", reviewStatus=review_status, humanDecision=None)
    assert _validate(_document(edge)) != []

    edge["humanDecision"] = _human_decision()
    assert _validate(_document(edge)) == []


@pytest.mark.parametrize("relation_state", ("unknown", "conflict"))
def test_unknown_and_conflict_cannot_be_confirmed_or_canonical(relation_state):
    edge = _edge(
        relation_state,
        reviewStatus="confirmed",
        humanDecision=_human_decision(),
    )
    assert _validate(_document(edge)) != []

    edge = _edge(
        relation_state,
        adoptionStatus="canonical",
        reviewStatus="rejected",
        humanDecision=_human_decision(),
    )
    assert _validate(_document(edge)) != []


@pytest.mark.parametrize("relation_state", ("unknown", "conflict"))
def test_unknown_and_conflict_require_reason_and_provenance(relation_state):
    edge = _edge(relation_state, stateReason=None)
    assert _validate(_document(edge)) != []

    edge = _edge(relation_state, candidateProvenance=[])
    assert _validate(_document(edge)) != []


def test_conflict_requires_two_candidate_provenance_records():
    edge = _edge("conflict", candidateProvenance=[_provenance()])
    assert _validate(_document(edge)) != []


def test_candidate_provenance_requires_directional_episode_references():
    provenance = _provenance()
    del provenance["sourceEpisode"]
    assert _validate(_document(_edge(candidateProvenance=[provenance]))) != []


def test_same_story_non_self_edge_is_reserved_for_semantic_validation():
    edge = _edge()
    edge["to"] = {
        "storyId": edge["from"]["storyId"],
        "episodeId": "EVT_TEST_STORY_01_E02",
        "storyCategory": "EVT",
    }

    # Draft 7 cannot compare dynamic storyId values. A future semantic validator
    # must reject this same-story edge before it enters the cross-story graph.
    assert _validate(_document(edge)) == []

    provenance = _provenance(observedRelation="unknown")
    assert _validate(_document(_edge(candidateProvenance=[provenance]))) != []


def test_event_scope_is_enforced_at_document_and_node_levels():
    document = _document(scopeStoryCategory="MAIN")
    assert _validate(document) != []


def test_episode_refs_follow_existing_id_character_contract():
    document = _document()
    document["nodes"][0]["storyId"] = "EVT-TEST_STORY"
    document["nodes"][0]["episodeId"] = "EVT-TEST_STORY_E01"
    assert _validate(document) == []

    document["nodes"][0]["episodeId"] = "invalid id"
    assert _validate(document) != []

    document = _document()
    document["nodes"][0]["storyCategory"] = "MAIN"
    assert _validate(document) != []


@pytest.mark.parametrize(
    "forbidden_field",
    (
        "globalOrder",
        "sequence",
        "canonicalOrder",
        "releaseOrder",
        "displayOrder",
        "episodeNumber",
    ),
)
def test_node_rejects_order_fields_and_schema_defines_none(forbidden_field):
    document = _document()
    document["nodes"][0][forbidden_field] = 1
    assert _validate(document) != []

    schema_properties = json.dumps(_load_schema()["definitions"])
    assert f'"{forbidden_field}"' not in schema_properties


def test_rejects_additional_fields_and_public_visibility():
    document = _document(unexpectedField="not allowed")
    assert _validate(document) != []

    document = _document(visibility="public")
    assert _validate(document) != []

    edge = copy.deepcopy(_edge())
    edge["unexpectedField"] = "not allowed"
    assert _validate(_document(edge)) != []
