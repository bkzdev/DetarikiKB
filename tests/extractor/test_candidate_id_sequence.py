"""Candidate finalizerが出力候補だけを欠番なく採番することを検証する。"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from agents.extractor.character import build_character_candidates
from agents.extractor.event import _finalize_event_candidates
from agents.extractor.item import _finalize_item_candidates
from agents.extractor.location import _finalize_location_candidates
from agents.extractor.lore import _finalize_lore_candidates
from agents.extractor.models import (
    EventCandidateAccumulator,
    ItemCandidateAccumulator,
    LocationCandidateAccumulator,
    LoreCandidateAccumulator,
    OrganizationCandidateAccumulator,
    RelationshipCandidateAccumulator,
    TimelineCandidateAccumulator,
)
from agents.extractor.organization import _finalize_organization_candidates
from agents.extractor.relationship import _finalize_relationship_candidates
from agents.extractor.timeline import _finalize_timeline_candidates

EPISODE_ID = "TEST_SEQUENCE_E01"
EXTRACTION_RUN = {"extractionMethod": "rule_based"}


def _finalizer_case(
    finalizer: Callable,
    invalid,
    valid,
    prefix: str,
) -> tuple[Callable[[], list[dict]], str]:
    keys = [("invalid",), ("valid",)]
    accumulators = dict(zip(keys, (invalid, valid), strict=True))
    return (
        lambda: finalizer(accumulators, keys, EPISODE_ID, EXTRACTION_RUN),
        prefix,
    )


@pytest.mark.parametrize(
    ("run_finalizer", "prefix"),
    [
        _finalizer_case(
            _finalize_location_candidates,
            LocationCandidateAccumulator(
                location_id="INVALID",
                scene_refs=["SC001"],
                evidence_ids=["SC001"],
            ),
            LocationCandidateAccumulator(
                location_id="VALID",
                name_candidates=["valid"],
                scene_refs=["SC002"],
                evidence_ids=["SC002"],
            ),
            "LOC",
        ),
        _finalizer_case(
            _finalize_organization_candidates,
            OrganizationCandidateAccumulator(
                organization_id="INVALID", evidence_ids=["EV001"]
            ),
            OrganizationCandidateAccumulator(
                organization_id="VALID",
                name_candidates=["valid"],
                evidence_ids=["EV002"],
            ),
            "ORG",
        ),
        _finalizer_case(
            _finalize_item_candidates,
            ItemCandidateAccumulator(item_id="INVALID", evidence_ids=["EV001"]),
            ItemCandidateAccumulator(
                item_id="VALID",
                name_candidates=["valid"],
                evidence_ids=["EV002"],
            ),
            "ITEM",
        ),
        _finalizer_case(
            _finalize_lore_candidates,
            LoreCandidateAccumulator(lore_id="INVALID", evidence_ids=["EV001"]),
            LoreCandidateAccumulator(
                lore_id="VALID",
                term_candidates=["valid"],
                evidence_ids=["EV002"],
            ),
            "LORE",
        ),
        _finalizer_case(
            _finalize_event_candidates,
            EventCandidateAccumulator(event_id="INVALID", evidence_ids=["EV001"]),
            EventCandidateAccumulator(
                event_id="VALID",
                name_candidates=["valid"],
                evidence_ids=["EV002"],
            ),
            "EVENT",
        ),
        _finalizer_case(
            _finalize_relationship_candidates,
            RelationshipCandidateAccumulator("A", "B", "KNOWS"),
            RelationshipCandidateAccumulator("C", "D", "KNOWS", evidence_ids=["EV002"]),
            "REL",
        ),
        _finalizer_case(
            _finalize_timeline_candidates,
            TimelineCandidateAccumulator(kind="relative_order"),
            TimelineCandidateAccumulator(kind="relative_order", evidence_ids=["EV002"]),
            "TL",
        ),
    ],
)
def test_finalizers_number_only_emitted_candidates_without_gaps(
    run_finalizer: Callable[[], list[dict]], prefix: str
):
    candidates = run_finalizer()

    assert [candidate["id"] for candidate in candidates] == [
        f"{EPISODE_ID}_CAND_{prefix}001"
    ]


def test_character_candidates_number_only_emitted_candidates_without_gaps():
    episode = {
        "speakerAssignments": [],
        "scenes": [
            {
                "blocks": [
                    {
                        "id": "TEST_SEQUENCE_E01_DLG0001",
                        "type": "dialogue",
                        "speaker": {
                            "speakerId": "INVALID",
                            "speakerName": None,
                        },
                    },
                    {
                        "id": "TEST_SEQUENCE_E01_DLG0002",
                        "type": "dialogue",
                        "speaker": {
                            "speakerId": "VALID",
                            "speakerName": "valid",
                        },
                    },
                ]
            }
        ],
    }

    candidates = build_character_candidates(episode, EPISODE_ID, EXTRACTION_RUN)

    assert [candidate["id"] for candidate in candidates] == [
        f"{EPISODE_ID}_CAND_CHAR001"
    ]
