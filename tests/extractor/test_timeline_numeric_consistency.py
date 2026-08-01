"""Episode metadata由来の明示的順序値の横断整合性テスト。"""

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


def _candidate(
    candidate_id: str,
    *,
    scope: str | None = "episode",
    order_field: str | None = "canonicalOrder",
    order_value: int | float | None = 1,
    evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "kind": "explicit_order",
        "scope": scope,
        "orderField": order_field,
        "orderValue": order_value,
        "evidenceIds": evidence_ids or [],
        "extractionRun": _extraction_run(),
    }


def _document(
    episode_id: str,
    candidates: list[dict[str, Any]],
    *,
    story_id: str = "STORY01",
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


def test_same_episode_field_and_value_is_one_group_without_conflict():
    report = _analyze(
        _document("EP01", [_candidate("EP01_CAND_TL001", order_value=3)]),
        _document("EP01", [_candidate("EP01_CAND_TL002", order_value=3.0)]),
    )

    assert report["explicitOrderCandidateCount"] == 2
    assert report["numericEpisodeObservationCount"] == 2
    assert report["numericEpisodeOrderGroupCount"] == 1
    assert report["numericFindingCount"] == 0


def test_distinct_values_preserve_every_observation_and_provenance():
    report = _analyze(
        _document(
            "EP01",
            [
                _candidate(
                    "EP01_CAND_TL001",
                    order_value=2,
                    evidence_ids=["EP01_EVD001"],
                )
            ],
        ),
        _document(
            "EP01",
            [
                _candidate(
                    "EP01_CAND_TL002",
                    order_value=1,
                    evidence_ids=["EP01_EVD002"],
                ),
                _candidate("EP01_CAND_TL003", order_value=2),
            ],
        ),
    )

    assert report["numericFindingCount"] == 1
    finding = report["numericFindings"][0]
    assert finding["rule"] == "timeline_episode_order_field_value_conflict"
    assert finding["episodeId"] == "EP01"
    assert finding["orderField"] == "canonicalOrder"
    assert finding["values"] == [2, 1]
    assert [item["sourcePath"] for item in finding["observations"]] == [
        "input-0.json",
        "input-1.json",
        "input-1.json",
    ]
    assert [item["candidateId"] for item in finding["observations"]] == [
        "EP01_CAND_TL001",
        "EP01_CAND_TL002",
        "EP01_CAND_TL003",
    ]
    assert finding["observations"][0]["evidenceIds"] == ["EP01_EVD001"]
    assert finding["observations"][0]["extractionRun"] == _extraction_run()


def test_different_fields_or_episodes_are_not_compared():
    report = _analyze(
        _document(
            "EP01",
            [
                _candidate("EP01_CAND_TL001", order_value=1),
                _candidate(
                    "EP01_CAND_TL002",
                    order_field="releaseOrder",
                    order_value=2,
                ),
            ],
        ),
        _document("EP02", [_candidate("EP02_CAND_TL001", order_value=3)]),
    )

    assert report["numericEpisodeOrderGroupCount"] == 3
    assert report["numericFindingCount"] == 0


def test_unsupported_or_incomplete_observations_are_retained_with_reason():
    report = _analyze(
        _document(
            "EP01",
            [
                _candidate("EP01_CAND_TL001", scope="scene"),
                _candidate("EP01_CAND_TL002", order_field=None),
                _candidate("EP01_CAND_TL003", order_field="orderValue"),
                _candidate("EP01_CAND_TL004", order_value=None),
            ],
        )
    )

    assert report["explicitOrderCandidateCount"] == 4
    assert report["numericEpisodeObservationCount"] == 0
    assert report["numericIgnoredObservationCount"] == 4
    assert [item["reason"] for item in report["numericIgnoredObservations"]] == [
        "unsupported_scope",
        "missing_order_field",
        "unsupported_order_field",
        "missing_order_value",
    ]
    assert [item["candidateId"] for item in report["numericIgnoredObservations"]] == [
        "EP01_CAND_TL001",
        "EP01_CAND_TL002",
        "EP01_CAND_TL003",
        "EP01_CAND_TL004",
    ]
    assert all(
        item["extractionRun"] == _extraction_run()
        for item in report["numericIgnoredObservations"]
    )
