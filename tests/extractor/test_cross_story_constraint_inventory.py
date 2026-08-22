"""cross-story constraint inventoryの合成fixtureテスト。"""

from __future__ import annotations

from typing import Any

from agents.extractor.cross_story_constraint_inventory import (
    build_cross_story_constraint_inventory,
)


def _candidate(
    candidate_id: str,
    relative_to: str | None,
    relation: str | None,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "kind": "relative_order",
        "relativeTo": relative_to,
        "relation": relation,
        "evidenceIds": [f"{candidate_id}_EVD"],
        "sourceType": "script",
        "confidence": 0.9,
        "extractionRun": {"runId": "RUN01"},
        **extra,
    }


def _document(
    story_id: str,
    episode_id: str,
    candidates: list[dict[str, Any]] | None = None,
    *,
    category: str = "EVT",
) -> dict[str, Any]:
    return {
        "storyId": story_id,
        "episodeId": episode_id,
        "storyCategory": category,
        "extractionRun": {"documentRun": story_id},
        "timelineCandidates": candidates or [],
    }


def _inventory(*documents: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    return build_cross_story_constraint_inventory(list(documents))


def test_groups_all_relations_and_keeps_reverse_and_duplicate_observations():
    report = _inventory(
        ("b.json", _document("EVT_B", "B1")),
        (
            "a.json",
            _document(
                "EVT_A",
                "A1",
                [
                    _candidate("A_BEFORE", "B1", "before"),
                    _candidate("A_BEFORE_DUP", "B1", "before"),
                    _candidate("A_SAME", "B1", "same_time"),
                ],
            ),
        ),
        (
            "c.json",
            _document("EVT_B", "B2", [_candidate("B_AFTER", "A1", "after")]),
        ),
    )

    assert report["relativeOrderCandidateCount"] == 4
    assert report["crossStoryCandidateObservationCount"] == 4
    assert report["distinctStoryPairCount"] == 1
    pair = report["storyPairs"][0]
    assert pair["storyIds"] == ["EVT_A", "EVT_B"]
    assert pair["relationCounts"] == {"after": 1, "before": 2, "same_time": 1}
    assert {candidate["candidateId"] for candidate in pair["candidates"]} == {
        "A_BEFORE",
        "A_BEFORE_DUP",
        "A_SAME",
        "B_AFTER",
    }
    reverse = next(
        item for item in pair["candidates"] if item["candidateId"] == "B_AFTER"
    )
    assert reverse["sourceStoryId"] == "EVT_B"
    assert reverse["relativeTo"] == "A1"
    assert reverse["relation"] == "after"


def test_keeps_duplicate_observations_with_the_same_candidate_id():
    duplicate = _candidate("DUPLICATE", "B1", "before")
    report = _inventory(
        ("source-one.json", _document("EVT_A", "A1", [duplicate])),
        ("source-two.json", _document("EVT_A", "A1", [duplicate])),
        ("target.json", _document("EVT_B", "B1")),
    )

    candidates = report["storyPairs"][0]["candidates"]
    assert report["crossStoryCandidateObservationCount"] == 2
    assert [candidate["candidateId"] for candidate in candidates] == [
        "DUPLICATE",
        "DUPLICATE",
    ]
    assert [candidate["sourcePath"] for candidate in candidates] == [
        "source-one.json",
        "source-two.json",
    ]


def test_classifies_same_missing_out_of_scope_ambiguous_and_invalid_candidates():
    report = _inventory(
        (
            "source.json",
            _document(
                "EVT_A",
                "A1",
                [
                    _candidate("SAME", "A2", "before"),
                    _candidate("MISSING_TARGET", "NOPE", "before"),
                    _candidate("OUT_SCOPE", "MAIN1", "after"),
                    _candidate("AMBIGUOUS", "SHARED", "same_time"),
                    _candidate("NO_TARGET", None, "before"),
                    _candidate("NO_RELATION", "A2", None),
                    _candidate("BAD_RELATION", "A2", "during"),
                ],
            ),
        ),
        ("same.json", _document("EVT_A", "A2")),
        ("main.json", _document("MAIN_A", "MAIN1", category="MAIN")),
        ("shared-a.json", _document("EVT_A", "SHARED")),
        ("shared-b.json", _document("EVT_C", "SHARED")),
    )

    assert report["sameStoryCandidateCount"] == 1
    assert report["unresolvedTargetCount"] == 2
    assert [item["reason"] for item in report["unresolvedTargets"]] == [
        "target_not_loaded",
        "target_out_of_scope",
    ]
    assert report["ambiguousTargetStoryCount"] == 1
    ambiguous = report["ambiguousTargetStories"][0]
    assert ambiguous["reason"] == "ambiguous_target_story"
    assert {
        reference["storyId"]
        for reference in ambiguous["candidate"]["targetDocumentRefs"]
    } == {"EVT_A", "EVT_C"}
    assert report["invalidRelativeCandidateCount"] == 3
    assert {item["reason"] for item in report["invalidRelativeCandidates"]} == {
        "missing_relative_to",
        "missing_relation",
        "unsupported_relation",
    }
    assert report["outOfScopeDocumentRefs"] == [
        {
            "sourcePath": "main.json",
            "storyId": "MAIN_A",
            "episodeId": "MAIN1",
            "storyCategory": "MAIN",
            "extractionRun": {"documentRun": "MAIN_A"},
        }
    ]


def test_same_story_target_stays_same_story_when_category_duplicate_is_loaded():
    report = _inventory(
        (
            "source.json",
            _document(
                "EVT_A",
                "A1",
                [_candidate("SAME_WITH_CATEGORY_DUP", "SHARED", "before")],
            ),
        ),
        ("target-evt.json", _document("EVT_A", "SHARED")),
        ("target-main.json", _document("EVT_A", "SHARED", category="MAIN")),
    )

    assert report["sameStoryCandidateCount"] == 1
    assert report["crossStoryCandidateObservationCount"] == 0
    assert report["ambiguousTargetStoryCount"] == 0
    assert report["unresolvedTargetCount"] == 0
    assert len(report["outOfScopeDocumentRefs"]) == 1


def test_preserves_provenance_is_input_order_independent_and_ignores_order_values():
    source = _document(
        "EVT_A",
        "A1",
        [
            _candidate(
                "A_TO_B",
                "B1",
                "before",
                canonicalOrder=99,
                releaseOrder=88,
                displayOrder=77,
            )
        ],
    )
    target = _document("EVT_B", "B1")
    first = _inventory(("source.json", source), ("target.json", target))
    second = _inventory(("target.json", target), ("source.json", source))

    assert first == second
    candidate = first["storyPairs"][0]["candidates"][0]
    assert candidate["sourcePath"] == "source.json"
    assert candidate["evidenceIds"] == ["A_TO_B_EVD"]
    assert candidate["sourceType"] == "script"
    assert candidate["confidence"] == 0.9
    assert candidate["extractionRun"] == {"runId": "RUN01"}
    assert candidate["targetDocumentRefs"] == [
        {
            "sourcePath": "target.json",
            "storyId": "EVT_B",
            "episodeId": "B1",
            "storyCategory": "EVT",
            "extractionRun": {"documentRun": "EVT_B"},
        }
    ]
    assert "canonicalOrder" not in str(first)
    assert "releaseOrder" not in str(first)
    assert "displayOrder" not in str(first)


def test_empty_inventory_has_the_fixed_evt_scope_shape():
    assert build_cross_story_constraint_inventory([]) == {
        "scopeStoryCategory": "EVT",
        "inScopeDocumentCount": 0,
        "outOfScopeDocumentRefs": [],
        "relativeOrderCandidateCount": 0,
        "crossStoryCandidateObservationCount": 0,
        "distinctStoryPairCount": 0,
        "sameStoryCandidateCount": 0,
        "unresolvedTargetCount": 0,
        "ambiguousTargetStoryCount": 0,
        "invalidRelativeCandidateCount": 0,
        "storyPairs": [],
        "invalidRelativeCandidates": [],
        "unresolvedTargets": [],
        "ambiguousTargetStories": [],
    }
