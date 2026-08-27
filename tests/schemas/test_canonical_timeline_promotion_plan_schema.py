"""Canonical Timeline promotion plan schemaの合成契約テスト。"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry, Resource

PROJECT_ROOT = Path(__file__).parent.parent.parent
PLAN_SCHEMA_PATH = (
    PROJECT_ROOT / "schemas" / "canonical_timeline_promotion_plan.schema.json"
)
PACKET_SCHEMA_PATH = (
    PROJECT_ROOT / "schemas" / "canonical_timeline_review_packet.schema.json"
)
TIMELINE_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "canonical_timeline.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator() -> Draft7Validator:
    schemas = [
        _load(path)
        for path in (PLAN_SCHEMA_PATH, PACKET_SCHEMA_PATH, TIMELINE_SCHEMA_PATH)
    ]
    registry = Registry().with_resources(
        [(schema["$id"], Resource.from_contents(schema)) for schema in schemas]
    )
    return Draft7Validator(
        schemas[0],
        registry=registry,
        format_checker=FormatChecker(),
    )


def _errors(document: dict) -> list[str]:
    return [
        error.message
        for error in sorted(
            _validator().iter_errors(document), key=lambda error: list(error.path)
        )
    ]


def _episode(number: int) -> dict[str, str]:
    return {
        "storyId": f"EVT_TEST_STORY_{number:02d}",
        "episodeId": f"EVT_TEST_STORY_{number:02d}_E01",
        "storyCategory": "EVT",
    }


def _provenance() -> dict:
    return {
        "candidateId": "TEST_CANDIDATE_001",
        "sourceEpisode": _episode(1),
        "targetEpisode": _episode(2),
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
            "extractedAt": "2099-01-02T00:00:00Z",
            "parserCompatibilityAtExtraction": "compatible",
        },
    }


def _decision() -> dict:
    return {
        "reviewer": "TEST_REVIEWER",
        "decidedAt": "2099-01-03T00:00:00Z",
        "evidenceSummary": "Synthetic evidence supports the relation.",
        "notes": None,
    }


def _edge(relation: str = "before", **overrides: object) -> dict:
    edge = {
        "reviewEdgeKey": "edge-0001",
        "from": _episode(1),
        "to": _episode(2),
        "relationState": relation,
        "stateReason": None,
        "reviewStatus": "confirmed",
        "candidateProvenance": [_provenance()],
        "humanDecision": _decision(),
    }
    edge.update(overrides)
    return edge


def _plan(**overrides: object) -> dict:
    plan = {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_promotion_plan",
        "planId": "ctpp-20990104T000000Z-deadbeef",
        "classification": "local_internal",
        "commitAllowed": False,
        "scopeStoryCategory": "EVT",
        "visibility": "internal_only",
        "executionMode": "plan_only",
        "createdAt": "2099-01-04T00:00:00Z",
        "sourcePacket": {
            "packetId": "ctrp-20990101T000000Z-deadbeef",
            "reviewBatchId": "test-batch-001",
            "schemaVersion": "0.2",
            "createdAt": "2099-01-01T00:00:00Z",
            "expiresAt": "2099-04-01T00:00:00Z",
            "expiredAtPlanning": False,
        },
        "storyPair": [
            {"storyId": "EVT_TEST_STORY_01", "storyCategory": "EVT"},
            {"storyId": "EVT_TEST_STORY_02", "storyCategory": "EVT"},
        ],
        "entries": [
            {
                "planEntryKey": "plan-entry-0001",
                "proposedAction": "proposed_canonical_edge",
                "executionStatus": "not_executed",
                "sourceEdge": _edge(),
            }
        ],
    }
    plan.update(overrides)
    return plan


def test_schema_is_draft7_valid_and_resolves_all_refs_offline() -> None:
    Draft7Validator.check_schema(_load(PLAN_SCHEMA_PATH))
    assert _errors(_plan()) == []


@pytest.mark.parametrize("relation", ("before", "after", "same_time"))
def test_only_confirmed_known_relations_are_valid_plan_entries(relation: str) -> None:
    plan = _plan()
    plan["entries"][0]["sourceEdge"] = _edge(relation)
    assert _errors(plan) == []


@pytest.mark.parametrize(
    "relation,status,decision",
    (
        ("before", "pending", None),
        ("before", "rejected", _decision()),
        ("before", "needs_more_context", _decision()),
        ("unknown", "needs_more_context", _decision()),
        ("conflict", "rejected", _decision()),
    ),
)
def test_nonconfirmed_or_unresolved_edges_cannot_enter_plan(
    relation: str,
    status: str,
    decision: dict | None,
) -> None:
    plan = _plan()
    state_reason = None if relation == "before" else "Synthetic unresolved state."
    provenance = (
        [_provenance(), _provenance()] if relation == "conflict" else [_provenance()]
    )
    plan["entries"][0]["sourceEdge"] = _edge(
        relation,
        stateReason=state_reason,
        reviewStatus=status,
        humanDecision=decision,
        candidateProvenance=provenance,
    )
    assert _errors(plan) != []


def test_expired_source_packet_is_representable_but_v01_is_not() -> None:
    expired = _plan()
    expired["sourcePacket"]["expiredAtPlanning"] = True
    assert _errors(expired) == []

    old_packet = _plan()
    old_packet["sourcePacket"]["schemaVersion"] = "0.1"
    assert _errors(old_packet) != []


def test_plan_is_internal_nonexecuting_and_does_not_promote() -> None:
    plan = _plan()
    entry = plan["entries"][0]
    assert entry["proposedAction"] == "proposed_canonical_edge"
    assert entry["executionStatus"] == "not_executed"
    assert "adoptionStatus" not in str(plan)

    for field, value in (
        ("classification", "public"),
        ("commitAllowed", True),
        ("scopeStoryCategory", "MAIN"),
        ("visibility", "public"),
        ("executionMode", "execute"),
    ):
        assert _errors(_plan(**{field: value})) != []


@pytest.mark.parametrize(
    "forbidden_field",
    (
        "canonicalOrder",
        "globalOrder",
        "totalOrder",
        "releaseOrder",
        "displayOrder",
        "episodeNumber",
        "rawText",
        "sourcePath",
        "publicUrl",
        "adoptionStatus",
    ),
)
def test_order_raw_path_public_and_adoption_fields_are_rejected(
    forbidden_field: str,
) -> None:
    plan = copy.deepcopy(_plan())
    plan["entries"][0][forbidden_field] = "TEST_FORBIDDEN"
    assert _errors(plan) != []


def test_cross_document_and_uniqueness_checks_remain_future_semantic_boundaries() -> (
    None
):
    plan = _plan()
    plan["entries"].append(copy.deepcopy(plan["entries"][0]))
    plan["entries"][1]["sourceEdge"]["to"] = _episode(3)
    # Draft 7はsource packetとのcross-document照合、pair membership、
    # planEntryKey一意性を表現できない。将来のplanner/validatorが拒否する。
    assert _errors(plan) == []
