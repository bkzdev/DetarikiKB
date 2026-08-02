"""canonical timelineのreview準備状況監査テスト。"""

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


def _order(candidate_id: str, value: int | float, field: str = "canonicalOrder"):
    return {
        "id": candidate_id,
        "kind": "explicit_order",
        "scope": "episode",
        "orderField": field,
        "orderValue": value,
        "evidenceIds": [f"{candidate_id}_EVD"],
        "extractionRun": _extraction_run(),
    }


def _relative(candidate_id: str, target: str, relation: str):
    return {
        "id": candidate_id,
        "kind": "relative_order",
        "relativeTo": target,
        "relation": relation,
        "evidenceIds": [],
        "extractionRun": _extraction_run(),
    }


def _document(story_id: str, episode_id: str, candidates: list[dict[str, Any]]):
    return {
        "storyId": story_id,
        "episodeId": episode_id,
        "timelineCandidates": candidates,
    }


def _analyze(*documents: dict[str, Any]) -> dict[str, Any]:
    return analyze_timeline_consistency(
        [(f"input-{index}.json", document) for index, document in enumerate(documents)]
    )


def test_story_is_ready_when_every_loaded_episode_has_one_canonical_value():
    report = _analyze(
        _document("STORY01", "EP02", [_order("EP02_CAND_TL001", 5)]),
        _document("STORY01", "EP01", [_order("EP01_CAND_TL001", 1)]),
    )

    assert report["canonicalReadinessStoryCount"] == 1
    assert report["canonicalReadyStoryCount"] == 1
    story = report["canonicalReadinessStories"][0]
    assert story["episodeIds"] == ["EP02", "EP01"]
    assert story["comparableEpisodeIds"] == ["EP02", "EP01"]
    assert story["missingEpisodeIds"] == []
    assert story["ambiguousEpisodes"] == []
    assert [bucket["orderValue"] for bucket in story["observedOrderBuckets"]] == [
        1,
        5,
    ]
    assert story["canonicalConstraintFindingCount"] == 0
    assert story["readyForCanonicalReview"] is True


def test_equal_values_form_an_observed_bucket_without_inferred_same_time():
    report = _analyze(
        _document("STORY01", "EP01", [_order("EP01_CAND_TL001", 1)]),
        _document("STORY01", "EP02", [_order("EP02_CAND_TL001", 1)]),
    )

    story = report["canonicalReadinessStories"][0]
    assert story["readyForCanonicalReview"] is True
    assert story["observedOrderBuckets"][0]["episodeIds"] == ["EP01", "EP02"]
    assert report["checkedSameTimeCandidateCount"] == 0


def test_missing_canonical_value_is_not_filled_from_other_order_fields():
    report = _analyze(
        _document(
            "STORY01",
            "EP01",
            [
                _order("EP01_CAND_TL001", 1, "releaseOrder"),
                _order("EP01_CAND_TL002", 1, "displayOrder"),
            ],
        )
    )

    story = report["canonicalReadinessStories"][0]
    assert story["comparableEpisodeIds"] == []
    assert story["missingEpisodeIds"] == ["EP01"]
    assert story["observedOrderBuckets"] == []
    assert story["readyForCanonicalReview"] is False


def test_ambiguous_values_retain_all_observations_without_winner_selection():
    report = _analyze(
        _document(
            "STORY01",
            "EP01",
            [
                _order("EP01_CAND_TL001", 2),
                _order("EP01_CAND_TL002", 1),
                _order("EP01_CAND_TL003", 2),
            ],
        )
    )

    story = report["canonicalReadinessStories"][0]
    assert story["comparableEpisodeIds"] == []
    assert story["ambiguousEpisodes"][0]["values"] == [2, 1]
    assert len(story["ambiguousEpisodes"][0]["observations"]) == 3
    assert [bucket["orderValue"] for bucket in story["observedOrderBuckets"]] == [
        1,
        2,
    ]
    assert story["readyForCanonicalReview"] is False


def test_duplicate_equal_observations_remain_comparable_and_are_all_retained():
    report = _analyze(
        _document("STORY01", "EP01", [_order("EP01_CAND_TL001", 1)]),
        _document("STORY01", "EP01", [_order("EP01_CAND_TL002", 1)]),
    )

    story = report["canonicalReadinessStories"][0]
    assert story["episodeIds"] == ["EP01"]
    assert story["comparableEpisodeIds"] == ["EP01"]
    assert len(story["observedOrderBuckets"][0]["observations"]) == 2
    assert story["readyForCanonicalReview"] is True


def test_constraint_finding_blocks_readiness_even_with_full_canonical_coverage():
    report = _analyze(
        _document(
            "STORY01",
            "EP01",
            [
                _order("EP01_CAND_TL001", 2),
                _relative("EP01_CAND_TL002", "EP02", "before"),
            ],
        ),
        _document("STORY01", "EP02", [_order("EP02_CAND_TL001", 1)]),
    )

    story = report["canonicalReadinessStories"][0]
    assert story["canonicalConstraintFindingCount"] == 1
    assert story["readyForCanonicalReview"] is False
    assert report["canonicalReadyStoryCount"] == 0


def test_story_results_preserve_first_seen_order_and_count_ready_stories():
    report = _analyze(
        _document("STORY_B", "EP_B", []),
        _document("STORY_A", "EP_A", [_order("EP_A_CAND_TL001", 1)]),
    )

    assert report["canonicalReadinessStoryCount"] == 2
    assert report["canonicalReadyStoryCount"] == 1
    assert [story["storyId"] for story in report["canonicalReadinessStories"]] == [
        "STORY_B",
        "STORY_A",
    ]


def test_large_equal_value_bucket_preserves_all_episode_ids():
    documents = [
        _document(
            "STORY01",
            f"EP{index:04d}",
            [_order(f"EP{index:04d}_CAND_TL001", 1)],
        )
        for index in range(1500)
    ]

    report = _analyze(*documents)

    story = report["canonicalReadinessStories"][0]
    assert len(story["episodeIds"]) == 1500
    assert len(story["observedOrderBuckets"][0]["episodeIds"]) == 1500
    assert story["readyForCanonicalReview"] is True


def test_large_ambiguous_episode_preserves_distinct_values_in_first_seen_order():
    values = [*range(1499, -1, -1), 1.0]
    candidates = [
        _order(f"EP01_CAND_TL{index:04d}", value) for index, value in enumerate(values)
    ]

    report = _analyze(_document("STORY01", "EP01", candidates))

    ambiguous = report["canonicalReadinessStories"][0]["ambiguousEpisodes"][0]
    assert ambiguous["values"] == list(range(1499, -1, -1))
    assert len(ambiguous["observations"]) == 1501
