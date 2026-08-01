"""Stage A relative_order候補の横断循環検出テスト。"""

from __future__ import annotations

from typing import Any

from agents.extractor.timeline_consistency import analyze_timeline_consistency


def _candidate(
    candidate_id: str,
    *,
    relative_to: str | None,
    relation: str | None,
    evidence_ids: list[str] | None = None,
    kind: str = "relative_order",
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "kind": kind,
        "relativeTo": relative_to,
        "relation": relation,
        "evidenceIds": evidence_ids or [],
    }


def _document(
    episode_id: str, candidates: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "episodeId": episode_id,
        "timelineCandidates": candidates or [],
    }


def _analyze(*documents: dict[str, Any]) -> dict[str, Any]:
    return analyze_timeline_consistency(
        [(f"input-{index}.json", document) for index, document in enumerate(documents)]
    )


def test_no_relative_order_candidates_passes_without_findings():
    report = _analyze(
        _document(
            "EP01",
            [
                _candidate(
                    "EP01_CAND_TL001",
                    relative_to=None,
                    relation=None,
                    kind="explicit_order",
                )
            ],
        )
    )

    assert report["timelineCandidateCount"] == 1
    assert report["relativeOrderCandidateCount"] == 0
    assert report["checkedCandidateCount"] == 0
    assert report["findings"] == []


def test_before_and_after_are_normalized_into_an_acyclic_graph():
    report = _analyze(
        _document(
            "EP01",
            [_candidate("EP01_CAND_TL001", relative_to="EP02", relation="before")],
        ),
        _document(
            "EP02",
            [_candidate("EP02_CAND_TL001", relative_to="EP03", relation="before")],
        ),
        _document(
            "EP03",
            [_candidate("EP03_CAND_TL001", relative_to="EP02", relation="after")],
        ),
    )

    assert report["checkedCandidateCount"] == 3
    assert report["distinctEdgeCount"] == 2
    assert report["findingCount"] == 0


def test_two_episode_cycle_retains_candidate_and_evidence_provenance():
    report = _analyze(
        _document(
            "EP01",
            [
                _candidate(
                    "EP01_CAND_TL001",
                    relative_to="EP02",
                    relation="before",
                    evidence_ids=["EP01_EVD001"],
                )
            ],
        ),
        _document(
            "EP02",
            [
                _candidate(
                    "EP02_CAND_TL001",
                    relative_to="EP01",
                    relation="before",
                    evidence_ids=["EP02_EVD001"],
                )
            ],
        ),
    )

    assert report["findingCount"] == 1
    finding = report["findings"][0]
    assert finding["rule"] == "timeline_relative_order_cycle"
    assert finding["episodeIds"] == ["EP01", "EP02"]
    assert [ref["candidateId"] for ref in finding["candidateRefs"]] == [
        "EP01_CAND_TL001",
        "EP02_CAND_TL001",
    ]
    assert [ref["evidenceIds"] for ref in finding["candidateRefs"]] == [
        ["EP01_EVD001"],
        ["EP02_EVD001"],
    ]


def test_three_episode_cycle_is_one_deterministic_finding():
    report = _analyze(
        _document(
            "EP01",
            [_candidate("EP01_CAND_TL001", relative_to="EP02", relation="before")],
        ),
        _document(
            "EP02",
            [_candidate("EP02_CAND_TL001", relative_to="EP03", relation="before")],
        ),
        _document(
            "EP03",
            [_candidate("EP03_CAND_TL001", relative_to="EP01", relation="before")],
        ),
    )

    assert report["findingCount"] == 1
    assert report["findings"][0]["episodeIds"] == ["EP01", "EP02", "EP03"]
    assert [edge["fromEpisodeId"] for edge in report["findings"][0]["edges"]] == [
        "EP01",
        "EP02",
        "EP03",
    ]


def test_self_loop_is_reported():
    report = _analyze(
        _document(
            "EP01",
            [_candidate("EP01_CAND_TL001", relative_to="EP01", relation="after")],
        )
    )

    assert report["findingCount"] == 1
    assert report["findings"][0]["episodeIds"] == ["EP01"]


def test_duplicate_edges_keep_observations_but_not_graph_duplicates():
    report = _analyze(
        _document(
            "EP01",
            [
                _candidate("EP01_CAND_TL001", relative_to="EP02", relation="before"),
                _candidate("EP01_CAND_TL002", relative_to="EP02", relation="before"),
            ],
        ),
        _document("EP02"),
    )

    assert report["checkedCandidateCount"] == 2
    assert report["distinctEdgeCount"] == 1
    assert report["findingCount"] == 0


def test_duplicate_cycle_edges_keep_every_candidate_observation():
    report = _analyze(
        _document(
            "EP01",
            [
                _candidate(
                    "EP01_CAND_TL001",
                    relative_to="EP02",
                    relation="before",
                    evidence_ids=["EP01_EVD001"],
                ),
                _candidate(
                    "EP01_CAND_TL002",
                    relative_to="EP02",
                    relation="before",
                    evidence_ids=["EP01_EVD002"],
                ),
            ],
        ),
        _document(
            "EP02",
            [_candidate("EP02_CAND_TL001", relative_to="EP01", relation="before")],
        ),
    )

    assert report["distinctEdgeCount"] == 2
    finding = report["findings"][0]
    assert [edge["candidateId"] for edge in finding["edges"]] == [
        "EP01_CAND_TL001",
        "EP01_CAND_TL002",
        "EP02_CAND_TL001",
    ]
    assert [ref["candidateId"] for ref in finding["candidateRefs"]] == [
        "EP01_CAND_TL001",
        "EP01_CAND_TL002",
        "EP02_CAND_TL001",
    ]


def test_multiple_cycles_follow_first_observation_and_input_episode_order():
    report = _analyze(
        _document(
            "EP03",
            [_candidate("EP03_CAND_TL001", relative_to="EP04", relation="before")],
        ),
        _document(
            "EP01",
            [_candidate("EP01_CAND_TL001", relative_to="EP02", relation="before")],
        ),
        _document(
            "EP04",
            [_candidate("EP04_CAND_TL001", relative_to="EP03", relation="before")],
        ),
        _document(
            "EP02",
            [_candidate("EP02_CAND_TL001", relative_to="EP01", relation="before")],
        ),
    )

    assert [finding["episodeIds"] for finding in report["findings"]] == [
        ["EP03", "EP04"],
        ["EP01", "EP02"],
    ]


def test_unusable_relative_orders_are_retained_as_ignored_candidates():
    report = _analyze(
        _document(
            "EP01",
            [
                _candidate("EP01_CAND_TL001", relative_to=None, relation="before"),
                _candidate("EP01_CAND_TL002", relative_to="EP02", relation=None),
                _candidate("EP01_CAND_TL003", relative_to="EP01", relation="same_time"),
                _candidate("EP01_CAND_TL004", relative_to="EP99", relation="before"),
                _candidate("EP01_CAND_TL005", relative_to="EP01", relation="unknown"),
            ],
        ),
        _document("EP02"),
    )

    assert report["checkedCandidateCount"] == 0
    assert report["ignoredCandidateCount"] == 5
    assert [candidate["reason"] for candidate in report["ignoredCandidates"]] == [
        "missing_relative_to",
        "missing_relation",
        "same_time_not_checked",
        "target_not_loaded",
        "unsupported_relation",
    ]


def test_large_acyclic_graph_does_not_depend_on_python_recursion_limit():
    documents = []
    for index in range(1500):
        episode_id = f"EP{index:04d}"
        candidates = []
        if index < 1499:
            candidates.append(
                _candidate(
                    f"{episode_id}_CAND_TL001",
                    relative_to=f"EP{index + 1:04d}",
                    relation="before",
                )
            )
        documents.append(_document(episode_id, candidates))

    report = _analyze(*documents)

    assert report["checkedCandidateCount"] == 1499
    assert report["findingCount"] == 0
