"""canonicalOrderとrelative_orderの同一story整合性テスト。"""

from __future__ import annotations

from typing import Any

from agents.extractor.timeline_consistency import analyze_timeline_consistency


def _extraction_run() -> dict[str, Any]:
    return {
        "extractionVersion": "0.1.0",
        "extractionMethod": "rule_based",
        "modelProvider": None,
        "modelName": None,
        "promptVersion": None,
        "extractedAt": None,
        "parserCompatibilityAtExtraction": "compatible",
    }


def _order_candidate(
    candidate_id: str,
    value: int | float,
    *,
    field: str = "canonicalOrder",
    evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "kind": "explicit_order",
        "scope": "episode",
        "orderField": field,
        "orderValue": value,
        "evidenceIds": evidence_ids or [],
        "extractionRun": _extraction_run(),
    }


def _relative_candidate(
    candidate_id: str,
    target: str,
    relation: str,
    *,
    evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "kind": "relative_order",
        "relativeTo": target,
        "relation": relation,
        "evidenceIds": evidence_ids or [],
        "extractionRun": _extraction_run(),
    }


def _document(
    story_id: str,
    episode_id: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "storyId": story_id,
        "episodeId": episode_id,
        "timelineCandidates": candidates,
    }


def _analyze(*documents: dict[str, Any]) -> dict[str, Any]:
    return analyze_timeline_consistency(
        [(f"input-{index}.json", document) for index, document in enumerate(documents)]
    )


def test_supported_relations_pass_when_canonical_orders_satisfy_them():
    report = _analyze(
        _document(
            "STORY01",
            "EP01",
            [
                _order_candidate("EP01_CAND_TL001", 1),
                _relative_candidate("EP01_CAND_TL002", "EP02", "before"),
                _relative_candidate("EP01_CAND_TL003", "EP03", "after"),
                _relative_candidate("EP01_CAND_TL004", "EP04", "same_time"),
            ],
        ),
        _document("STORY01", "EP02", [_order_candidate("EP02_CAND_TL001", 2)]),
        _document("STORY01", "EP03", [_order_candidate("EP03_CAND_TL001", 0)]),
        _document("STORY01", "EP04", [_order_candidate("EP04_CAND_TL001", 1)]),
    )

    assert report["canonicalOrderObservationCount"] == 4
    assert report["canonicalConstraintCandidateCount"] == 3
    assert report["canonicalConstraintCheckedCount"] == 3
    assert report["canonicalConstraintIgnoredCount"] == 0
    assert report["canonicalConstraintFindingCount"] == 0


def test_each_violated_relation_retains_constraint_and_order_provenance():
    report = _analyze(
        _document(
            "STORY01",
            "EP01",
            [
                _order_candidate("EP01_CAND_TL001", 2, evidence_ids=["EP01_EVD001"]),
                _relative_candidate(
                    "EP01_CAND_TL002",
                    "EP02",
                    "before",
                    evidence_ids=["EP01_EVD002"],
                ),
                _relative_candidate("EP01_CAND_TL003", "EP03", "after"),
                _relative_candidate("EP01_CAND_TL004", "EP04", "same_time"),
            ],
        ),
        _document("STORY01", "EP02", [_order_candidate("EP02_CAND_TL001", 1)]),
        _document("STORY01", "EP03", [_order_candidate("EP03_CAND_TL001", 3)]),
        _document("STORY01", "EP04", [_order_candidate("EP04_CAND_TL001", 4)]),
    )

    assert report["canonicalConstraintCheckedCount"] == 3
    assert report["canonicalConstraintFindingCount"] == 3
    assert [
        finding["constraint"]["relation"]
        for finding in report["canonicalConstraintFindings"]
    ] == ["before", "after", "same_time"]
    finding = report["canonicalConstraintFindings"][0]
    assert finding["rule"] == ("timeline_canonical_order_relative_constraint_conflict")
    assert finding["storyId"] == "STORY01"
    assert finding["sourceCanonicalOrder"] == 2
    assert finding["targetCanonicalOrder"] == 1
    assert finding["constraint"]["candidateId"] == "EP01_CAND_TL002"
    assert finding["constraint"]["evidenceIds"] == ["EP01_EVD002"]
    assert finding["constraint"]["extractionRun"] == _extraction_run()
    assert finding["sourceOrderObservations"][0]["evidenceIds"] == ["EP01_EVD001"]


def test_ambiguous_and_missing_orders_are_retained_without_winner_selection():
    report = _analyze(
        _document(
            "STORY01",
            "EP01",
            [
                _order_candidate("EP01_CAND_TL001", 1),
                _order_candidate("EP01_CAND_TL002", 2),
                _relative_candidate("EP01_CAND_TL003", "EP02", "before"),
            ],
        ),
        _document("STORY01", "EP02", []),
    )

    assert report["numericFindingCount"] == 1
    assert report["canonicalConstraintCheckedCount"] == 0
    assert report["canonicalConstraintFindingCount"] == 0
    assert report["canonicalConstraintIgnoredCount"] == 1
    ignored = report["canonicalConstraintIgnoredCandidates"][0]
    assert ignored["reasons"] == [
        "ambiguous_source_canonical_order",
        "missing_target_canonical_order",
    ]
    assert [item["orderValue"] for item in ignored["sourceOrderObservations"]] == [
        1,
        2,
    ]
    assert ignored["targetOrderObservations"] == []


def test_release_and_display_orders_never_substitute_for_canonical_order():
    report = _analyze(
        _document(
            "STORY01",
            "EP01",
            [
                _order_candidate("EP01_CAND_TL001", 1, field="releaseOrder"),
                _relative_candidate("EP01_CAND_TL002", "EP02", "before"),
            ],
        ),
        _document(
            "STORY01",
            "EP02",
            [_order_candidate("EP02_CAND_TL001", 2, field="displayOrder")],
        ),
    )

    ignored = report["canonicalConstraintIgnoredCandidates"][0]
    assert ignored["reasons"] == [
        "missing_source_canonical_order",
        "missing_target_canonical_order",
    ]
    assert report["canonicalOrderObservationCount"] == 0
    assert report["canonicalConstraintFindingCount"] == 0


def test_cross_story_constraint_is_not_compared_and_retains_target_observation():
    report = _analyze(
        _document(
            "STORY01",
            "EP01",
            [
                _order_candidate("EP01_CAND_TL001", 1),
                _relative_candidate("EP01_CAND_TL002", "EP02", "before"),
            ],
        ),
        _document("STORY02", "EP02", [_order_candidate("EP02_CAND_TL001", 2)]),
    )

    assert report["canonicalConstraintCheckedCount"] == 0
    ignored = report["canonicalConstraintIgnoredCandidates"][0]
    assert ignored["reasons"] == ["cross_story_constraint"]
    assert ignored["constraint"]["storyId"] == "STORY01"
    assert ignored["targetOrderObservations"][0]["storyId"] == "STORY02"


def test_duplicate_equal_orders_are_comparable_and_all_observations_are_retained():
    report = _analyze(
        _document(
            "STORY01",
            "EP01",
            [
                _order_candidate("EP01_CAND_TL001", 2),
                _order_candidate("EP01_CAND_TL002", 2.0),
                _relative_candidate("EP01_CAND_TL003", "EP02", "before"),
            ],
        ),
        _document(
            "STORY01",
            "EP02",
            [
                _order_candidate("EP02_CAND_TL001", 1),
                _order_candidate("EP02_CAND_TL002", 1),
            ],
        ),
    )

    finding = report["canonicalConstraintFindings"][0]
    assert len(finding["sourceOrderObservations"]) == 2
    assert len(finding["targetOrderObservations"]) == 2
    assert report["canonicalConstraintCheckedCount"] == 1
    assert report["canonicalConstraintFindingCount"] == 1


def test_self_same_time_passes_but_self_before_is_a_conflict():
    report = _analyze(
        _document(
            "STORY01",
            "EP01",
            [
                _order_candidate("EP01_CAND_TL001", 1),
                _relative_candidate("EP01_CAND_TL002", "EP01", "same_time"),
                _relative_candidate("EP01_CAND_TL003", "EP01", "before"),
            ],
        )
    )

    assert report["canonicalConstraintCheckedCount"] == 2
    assert report["canonicalConstraintFindingCount"] == 1
    assert report["canonicalConstraintFindings"][0]["constraint"]["relation"] == (
        "before"
    )
