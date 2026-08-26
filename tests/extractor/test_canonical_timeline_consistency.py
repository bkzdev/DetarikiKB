from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft7Validator

from agents.extractor.canonical_timeline_consistency import (
    CANONICAL_CYCLE,
    COMPOSITE_NODE_DUPLICATE,
    CONFLICT_PROVENANCE_ENDPOINT_MISMATCH,
    CONFLICT_PROVENANCE_NOT_CONFLICTING,
    EDGE_DUPLICATE,
    EDGE_ENDPOINT_MISSING,
    SAME_STORY_EDGE,
    SAME_TIME_CONTRADICTION,
    SELF_EDGE,
    validate_canonical_timeline_consistency,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "canonical_timeline.schema.json"
with open(SCHEMA_PATH, encoding="utf-8") as schema_file:
    SCHEMA_VALIDATOR = Draft7Validator(json.load(schema_file))


def _node(story: str, episode: str) -> dict[str, str]:
    return {"storyId": story, "episodeId": episode, "storyCategory": "EVT"}


def _provenance(
    source: dict[str, str], target: dict[str, str], relation: str, candidate_id: str
) -> dict[str, object]:
    return {
        "candidateId": candidate_id,
        "sourceEpisode": source,
        "targetEpisode": target,
        "observedRelation": relation,
        "evidenceIds": [f"TEST_EVIDENCE_{candidate_id}"],
        "sourceType": "manual",
        "confidence": 1.0,
        "extractionRun": {
            "extractionVersion": "TEST_1",
            "extractionMethod": "manual",
            "modelProvider": None,
            "modelName": None,
            "promptVersion": None,
            "extractedAt": None,
            "parserCompatibilityAtExtraction": "compatible",
        },
    }


def _edge(
    source: dict[str, str],
    target: dict[str, str],
    relation: str,
    *,
    canonical: bool = True,
    provenance: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    if provenance is None:
        observed_relation = (
            relation if relation in {"before", "after", "same_time"} else "before"
        )
        provenance = [_provenance(source, target, observed_relation, "TEST_CANDIDATE")]
        if relation == "conflict":
            provenance.append(
                _provenance(source, target, "after", "TEST_CANDIDATE_CONFLICT")
            )
    return {
        "from": source,
        "to": target,
        "relationState": relation,
        "stateReason": None
        if relation in {"before", "after", "same_time"}
        else "TEST_reason",
        "adoptionStatus": "canonical" if canonical else "candidate",
        "reviewStatus": "confirmed" if canonical else "pending",
        "candidateProvenance": provenance,
        "humanDecision": (
            {
                "reviewer": "TEST_REVIEWER",
                "decidedAt": "2026-01-01T00:00:00Z",
                "evidenceSummary": "TEST_summary",
                "notes": None,
            }
            if canonical
            else None
        ),
    }


def _document(
    nodes: list[dict[str, str]], edges: list[dict[str, object]]
) -> dict[str, object]:
    return {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline",
        "scopeStoryCategory": "EVT",
        "visibility": "internal_only",
        "nodes": nodes,
        "edges": edges,
    }


def _rules(document: dict[str, object]) -> list[str]:
    schema_errors = sorted(
        SCHEMA_VALIDATOR.iter_errors(document), key=lambda error: list(error.path)
    )
    assert schema_errors == []
    return [
        finding["rule"] for finding in validate_canonical_timeline_consistency(document)
    ]


def _findings(document: dict[str, object]) -> list[dict[str, object]]:
    schema_errors = sorted(
        SCHEMA_VALIDATOR.iter_errors(document), key=lambda error: list(error.path)
    )
    assert schema_errors == []
    return validate_canonical_timeline_consistency(document)


def test_reports_structural_findings_and_only_exact_duplicate_edges() -> None:
    first = _node("TEST_A", "TEST_A_E01")
    second = _node("TEST_A", "TEST_A_E02")
    absent = _node("TEST_B", "TEST_B_E01")
    duplicate = _edge(first, absent, "before")
    with_distinct_provenance = deepcopy(duplicate)
    with_distinct_provenance["candidateProvenance"][0]["candidateId"] = "TEST_OTHER"
    document = _document(
        [first, first, second],
        [
            duplicate,
            deepcopy(duplicate),
            with_distinct_provenance,
            _edge(first, first, "before"),
        ],
    )

    rules = _rules(document)

    assert COMPOSITE_NODE_DUPLICATE in rules
    assert EDGE_ENDPOINT_MISSING in rules
    assert EDGE_DUPLICATE in rules
    assert SAME_STORY_EDGE in rules
    assert SELF_EDGE in rules
    assert rules.count(EDGE_DUPLICATE) == 1


def test_canonical_graph_detects_cycle_and_transitive_same_time_contradiction() -> None:
    first = _node("TEST_A", "TEST_A_E01")
    second = _node("TEST_B", "TEST_B_E01")
    third = _node("TEST_C", "TEST_C_E01")
    fourth = _node("TEST_D", "TEST_D_E01")
    fifth = _node("TEST_E", "TEST_E_E01")
    sixth = _node("TEST_F", "TEST_F_E01")
    seventh = _node("TEST_G", "TEST_G_E01")
    document = _document(
        [first, second, third, fourth, fifth, sixth, seventh],
        [
            _edge(first, fourth, "same_time"),
            _edge(fourth, third, "same_time"),
            _edge(first, third, "before"),
            _edge(fifth, sixth, "before"),
            _edge(sixth, seventh, "before"),
            _edge(seventh, fifth, "before"),
        ],
    )

    rules = _rules(document)

    assert CANONICAL_CYCLE in rules
    assert SAME_TIME_CONTRADICTION in rules


def test_clean_known_relations_have_no_findings() -> None:
    first = _node("TEST_A", "TEST_A_E01")
    second = _node("TEST_B", "TEST_B_E01")
    third = _node("TEST_C", "TEST_C_E01")
    fourth = _node("TEST_D", "TEST_D_E01")
    fifth = _node("TEST_E", "TEST_E_E01")

    assert (
        _rules(
            _document(
                [first, second, third, fourth, fifth],
                [
                    _edge(first, second, "before"),
                    _edge(second, third, "after"),
                    _edge(fourth, fifth, "same_time"),
                ],
            )
        )
        == []
    )


def test_actual_conflict_provenance_has_no_finding() -> None:
    first = _node("TEST_A", "TEST_A_E01")
    second = _node("TEST_B", "TEST_B_E01")
    conflict = _edge(
        first,
        second,
        "conflict",
        canonical=False,
        provenance=[
            _provenance(first, second, "before", "TEST_BEFORE"),
            _provenance(first, second, "after", "TEST_AFTER"),
        ],
    )

    assert _rules(_document([first, second], [conflict])) == []


def test_canonical_cycle_normalizes_after_relation() -> None:
    first = _node("TEST_A", "TEST_A_E01")
    second = _node("TEST_B", "TEST_B_E01")
    third = _node("TEST_C", "TEST_C_E01")
    document = _document(
        [first, second, third],
        [
            _edge(first, second, "before"),
            _edge(second, third, "before"),
            _edge(first, third, "after"),
        ],
    )

    assert _rules(document) == [CANONICAL_CYCLE]


def test_graph_excludes_all_noncanonical_or_nonconfirmed_states() -> None:
    first = _node("TEST_A", "TEST_A_E01")
    second = _node("TEST_B", "TEST_B_E01")
    reverse_edges: list[dict[str, object]] = []
    for relation, review_status in [
        ("before", "pending"),
        ("before", "rejected"),
        ("before", "needs_more_context"),
        ("before", "confirmed"),
        ("unknown", "pending"),
        ("conflict", "pending"),
    ]:
        edge = _edge(second, first, relation, canonical=False)
        edge["reviewStatus"] = review_status
        if review_status != "pending":
            edge["humanDecision"] = {
                "reviewer": "TEST_REVIEWER",
                "decidedAt": "2026-01-01T00:00:00Z",
                "evidenceSummary": "TEST_summary",
                "notes": None,
            }
        if relation == "conflict":
            edge["candidateProvenance"] = [
                _provenance(second, first, "before", "TEST_CONFLICT_ONE"),
                _provenance(second, first, "after", "TEST_CONFLICT_TWO"),
            ]
        reverse_edges.append(edge)
    document = _document(
        [first, second],
        [_edge(first, second, "before"), *reverse_edges],
    )

    assert _rules(document) == []


def test_direct_and_transitive_same_time_contradictions_are_detected() -> None:
    first = _node("TEST_A", "TEST_A_E01")
    second = _node("TEST_B", "TEST_B_E01")
    third = _node("TEST_C", "TEST_C_E01")
    document = _document(
        [first, second, third],
        [
            _edge(first, second, "same_time"),
            _edge(second, third, "same_time"),
            _edge(first, second, "before"),
            _edge(first, third, "after"),
        ],
    )

    assert _rules(document) == [SAME_TIME_CONTRADICTION, SAME_TIME_CONTRADICTION]


def test_invalid_same_story_and_missing_endpoint_edges_do_not_enter_graph() -> None:
    first = _node("TEST_A", "TEST_A_E01")
    second = _node("TEST_A", "TEST_A_E02")
    third = _node("TEST_B", "TEST_B_E01")
    absent = _node("TEST_C", "TEST_C_E01")
    document = _document(
        [first, second, third],
        [
            _edge(first, second, "same_time"),
            _edge(second, third, "before"),
            _edge(third, first, "before"),
            _edge(third, absent, "before"),
        ],
    )

    assert _rules(document) == [EDGE_ENDPOINT_MISSING, SAME_STORY_EDGE]


def test_conflict_provenance_checks_orientation_and_relation_meaning() -> None:
    first = _node("TEST_A", "TEST_A_E01")
    second = _node("TEST_B", "TEST_B_E01")
    wrong = _node("TEST_C", "TEST_C_E01")
    equivalent = _edge(
        first,
        second,
        "conflict",
        canonical=False,
        provenance=[
            _provenance(first, second, "before", "TEST_ONE"),
            _provenance(second, first, "after", "TEST_TWO"),
        ],
    )
    mismatch = _edge(
        first,
        second,
        "conflict",
        canonical=False,
        provenance=[
            _provenance(first, second, "before", "TEST_THREE"),
            _provenance(first, wrong, "after", "TEST_FOUR"),
        ],
    )
    document = _document([first, second, wrong], [equivalent, mismatch])

    rules = _rules(document)

    assert rules.count(CONFLICT_PROVENANCE_NOT_CONFLICTING) == 2
    assert CONFLICT_PROVENANCE_ENDPOINT_MISMATCH in rules


def test_does_not_mutate_input_and_is_deterministic_under_array_reordering() -> None:
    first = _node("TEST_A", "TEST_A_E01")
    second = _node("TEST_B", "TEST_B_E01")
    third = _node("TEST_C", "TEST_C_E01")
    document = _document(
        [third, first, second, first],
        [
            _edge(first, second, "before"),
            _edge(second, first, "before"),
            _edge(first, third, "before"),
        ],
    )
    original = deepcopy(document)
    reordered = deepcopy(document)
    reordered["nodes"].reverse()
    reordered["edges"].reverse()

    findings = _findings(document)

    assert document == original
    assert findings == _findings(reordered)


def test_large_canonical_chain_uses_no_recursion() -> None:
    nodes = [
        _node(f"TEST_{index:04d}", f"TEST_{index:04d}_E01") for index in range(1500)
    ]
    edges = [
        _edge(nodes[index], nodes[index + 1], "before")
        for index in range(len(nodes) - 1)
    ]

    assert _findings(_document(nodes, edges)) == []
