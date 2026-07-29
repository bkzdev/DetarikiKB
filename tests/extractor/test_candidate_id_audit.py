"""Candidate ID運用監査の合成テスト。"""

from __future__ import annotations

import json

import pytest

from agents.extractor.candidate_id_audit import (
    CANDIDATE_ARRAY_SPECS,
    audit_candidate_ids,
    parse_candidate_id,
)
from agents.extractor.organization import build_organization_candidates
from agents.extractor.relationship import build_relationship_candidates

EPISODE_ID = "SENSITIVE_EPISODE_SENTINEL"


def _normalized() -> dict:
    return {
        "storyId": "SENSITIVE_STORY_SENTINEL",
        "episodes": [
            {
                "episodeId": EPISODE_ID,
                "scenes": [
                    {
                        "sceneId": "SENSITIVE_SCENE_SENTINEL",
                        "blocks": [
                            {"id": "SENSITIVE_TOP_SENTINEL", "type": "dialogue"},
                            {
                                "id": "SENSITIVE_CHOICE_SENTINEL",
                                "type": "choice",
                                "options": [
                                    {
                                        "blocks": [
                                            {
                                                "id": "SENSITIVE_NESTED_SENTINEL",
                                                "type": "dialogue",
                                            }
                                        ]
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        ],
    }


def _candidate(
    number: int,
    evidence_ids: list[str],
    *,
    prefix: str = "CHAR",
    candidate_type: str = "character_candidate",
) -> dict:
    return {
        "id": f"{EPISODE_ID}_CAND_{prefix}{number:03d}",
        "type": candidate_type,
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": evidence_ids,
        "extractionRun": {"extractionMethod": "rule_based"},
        "nameCandidates": ["SENSITIVE_NAME_SENTINEL"],
    }


def _extraction(characters: list[dict] | None = None) -> dict:
    return {
        "episodeId": EPISODE_ID,
        "extractionRun": {"extractionMethod": "rule_based", "runAt": "first"},
        "characters": characters or [],
        "organizations": [],
        "locations": [],
        "items": [],
        "lore": [],
        "events": [],
        "relationships": [],
        "timelineCandidates": [],
        "specialSpeakerLabelCandidates": [],
    }


def test_valid_ids_preorder_nested_evidence_and_comparison_are_aggregated():
    primary = _extraction(
        [
            _candidate(
                1,
                ["SENSITIVE_TOP_SENTINEL", "SENSITIVE_NESTED_SENTINEL"],
            ),
            _candidate(2, ["SENSITIVE_NESTED_SENTINEL"]),
        ]
    )
    comparison = json.loads(json.dumps(primary))
    comparison["extractionRun"]["runAt"] = "second"
    for candidate in comparison["characters"]:
        candidate["extractionRun"]["runAt"] = "second"

    report = audit_candidate_ids([primary], [_normalized()], [comparison])

    assert report["status"] == "pass"
    assert report["errorCount"] == 0
    assert report["candidateCountsByType"]["CHAR"] == 2
    assert report["evidenceObservations"] == {
        "nestedEvidenceReferenceCount": 2,
        "candidatesWithNestedEvidence": 2,
        "candidatesWithTopAndNestedEvidence": 1,
        "sameTypeMultiCandidateEvidenceGroupCount": 1,
        "maxSameTypeEvidenceFanout": 2,
    }
    assert report["comparison"]["stableProjectionMismatchDocuments"] == 0


def test_contract_violations_are_reported_only_as_counts():
    candidates = [
        _candidate(2, ["SENSITIVE_NESTED_SENTINEL", "SENSITIVE_TOP_SENTINEL"]),
        _candidate(2, ["SENSITIVE_NESTED_SENTINEL"]),
    ]
    candidates[0]["type"] = "location_candidate"
    candidates[1]["id"] = candidates[0]["id"]
    report = audit_candidate_ids(
        [_extraction(candidates)],
        [_normalized()],
        [_extraction([])],
    )

    assert report["status"] == "fail"
    assert report["errorCountsByRule"]["candidateArrayTypeMismatch"] == 1
    assert report["errorCountsByRule"]["candidateIdDuplicate"] == 1
    assert report["errorCountsByRule"]["ruleBasedCandidateSequence"] == 1
    assert report["errorCountsByRule"]["ruleBasedEvidencePreorder"] == 1
    assert report["comparison"]["stableProjectionMismatchDocuments"] == 1

    serialized = json.dumps(report, ensure_ascii=False)
    for sentinel in (
        EPISODE_ID,
        "SENSITIVE_TOP_SENTINEL",
        "SENSITIVE_NESTED_SENTINEL",
        "SENSITIVE_SCENE_SENTINEL",
        "SENSITIVE_STORY_SENTINEL",
        "SENSITIVE_NAME_SENTINEL",
    ):
        assert sentinel not in serialized


def test_candidate_number_format_accepts_four_digits_without_extra_zero():
    assert parse_candidate_id(f"{EPISODE_ID}_CAND_CHAR1000", EPISODE_ID) == (
        "CHAR",
        1000,
        True,
    )
    assert parse_candidate_id(f"{EPISODE_ID}_CAND_CHAR0001", EPISODE_ID) == (
        "CHAR",
        1,
        False,
    )
    assert parse_candidate_id(f"{EPISODE_ID}_CAND_UNKNOWN001", EPISODE_ID) is None


@pytest.mark.parametrize(
    ("array_key", "candidate_type", "prefix"),
    [
        (array_key, candidate_type, prefix)
        for array_key, (candidate_type, prefix) in CANDIDATE_ARRAY_SPECS.items()
    ],
)
def test_every_candidate_array_accepts_its_defined_type_and_prefix(
    array_key: str, candidate_type: str, prefix: str
):
    extraction = _extraction()
    extraction[array_key] = [
        _candidate(
            1,
            ["SENSITIVE_TOP_SENTINEL"],
            prefix=prefix,
            candidate_type=candidate_type,
        )
    ]

    report = audit_candidate_ids([extraction], [_normalized()])

    assert report["status"] == "pass"
    assert report["candidateCountsByType"][prefix] == 1


def test_scene_evidence_participates_in_candidate_preorder():
    extraction = _extraction()
    extraction["locations"] = [
        _candidate(
            1,
            ["SENSITIVE_SCENE_SENTINEL", "SENSITIVE_NESTED_SENTINEL"],
            prefix="LOC",
            candidate_type="location_candidate",
        ),
        _candidate(
            2,
            ["SENSITIVE_TOP_SENTINEL"],
            prefix="LOC",
            candidate_type="location_candidate",
        ),
    ]

    report = audit_candidate_ids([extraction], [_normalized()])

    assert report["status"] == "pass"
    assert (
        report["evidenceObservations"]["sameTypeMultiCandidateEvidenceGroupCount"] == 0
    )

    extraction["locations"].reverse()
    for number, candidate in enumerate(extraction["locations"], start=1):
        candidate["id"] = f"{EPISODE_ID}_CAND_LOC{number:03d}"
    report = audit_candidate_ids([extraction], [_normalized()])

    assert report["errorCountsByRule"]["ruleBasedCandidatePreorder"] == 1


def test_evidence_missing_from_normalized_story_is_rejected_anonymously():
    extraction = _extraction([_candidate(1, ["SENSITIVE_MISSING_EVIDENCE_SENTINEL"])])

    report = audit_candidate_ids([extraction], [_normalized()])

    assert report["status"] == "fail"
    assert report["errorCountsByRule"]["candidateEvidenceNotInNormalized"] == 1
    assert "SENSITIVE_MISSING_EVIDENCE_SENTINEL" not in json.dumps(report)


def test_story_evidence_is_allowed_without_entering_scene_block_preorder():
    extraction = _extraction([_candidate(1, ["SENSITIVE_STORY_SENTINEL"])])

    report = audit_candidate_ids([extraction], [_normalized()])

    assert report["status"] == "pass"


def test_block_then_episode_evidence_from_current_extractors_is_valid():
    normalized = _normalized()
    episode = normalized["episodes"][0]
    episode["speakerAssignments"] = [
        {
            "speakerId": "CHAR_SYNTHETIC",
            "organizationId": "ORG_SYNTHETIC",
            "organizationName": "synthetic",
        }
    ]
    block = episode["scenes"][0]["blocks"][0]
    block.update(
        {
            "organizationId": "ORG_SYNTHETIC",
            "organizationName": "synthetic",
            "relationshipType": "MEMBER_OF",
            "sourceCandidate": "CHAR_SYNTHETIC",
            "targetCandidate": "ORG_SYNTHETIC",
        }
    )
    extraction_run = {"extractionMethod": "rule_based"}
    organizations, _ = build_organization_candidates(
        episode,
        normalized["storyId"],
        EPISODE_ID,
        extraction_run,
    )
    relationships, _ = build_relationship_candidates(
        episode,
        normalized["storyId"],
        EPISODE_ID,
        extraction_run,
    )
    extraction = _extraction()
    extraction["organizations"] = organizations
    extraction["relationships"] = relationships

    report = audit_candidate_ids([extraction], [normalized])

    assert organizations[0]["evidenceIds"] == [
        "SENSITIVE_TOP_SENTINEL",
        EPISODE_ID,
    ]
    assert relationships[0]["evidenceIds"] == [
        "SENSITIVE_TOP_SENTINEL",
        EPISODE_ID,
    ]
    assert report["status"] == "pass"


def test_unknown_extraction_method_is_rejected_without_copying_its_value():
    extraction = _extraction()
    extraction["extractionRun"]["extractionMethod"] = "SENSITIVE_METHOD_SENTINEL"

    report = audit_candidate_ids([extraction], [_normalized()])

    assert report["status"] == "fail"
    assert report["errorCountsByRule"]["extractionMethodInvalid"] == 1
    assert "SENSITIVE_METHOD_SENTINEL" not in json.dumps(report)


def test_all_extraction_methods_reject_zero_candidate_number():
    for method in ("rule_based", "llm", "manual", "hybrid"):
        candidate = _candidate(1, ["SENSITIVE_TOP_SENTINEL"])
        candidate["id"] = f"{EPISODE_ID}_CAND_CHAR000"
        extraction = _extraction([candidate])
        extraction["extractionRun"]["extractionMethod"] = method

        report = audit_candidate_ids([extraction], [_normalized()])

        assert report["status"] == "fail"
        assert report["errorCountsByRule"]["candidateIdNumberNonPositive"] == 1


def test_non_rule_based_documents_skip_sequence_contract():
    extraction = _extraction([_candidate(2, ["SENSITIVE_TOP_SENTINEL"])])
    extraction["extractionRun"]["extractionMethod"] = "manual"

    report = audit_candidate_ids([extraction], [_normalized()])

    assert report["status"] == "pass"
    assert report["observationCounts"]["nonRuleBasedSequenceChecksSkipped"] == 9
