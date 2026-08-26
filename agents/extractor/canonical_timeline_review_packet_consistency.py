"""Canonical Timeline review packetの意味整合性を検査する。

schema-validな単一packetを入力として想定し、入力を変更せず、固定ruleと
packet-local reviewEdgeKeyだけを含む決定的findingを返す。
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

REVIEW_EDGE_KEY_DUPLICATE = "canonical_timeline_review_edge_key_duplicate"
EDGE_OUTSIDE_STORY_PAIR = "canonical_timeline_review_edge_outside_story_pair"
SAME_STORY_EDGE = "canonical_timeline_review_same_story_edge"
SELF_EDGE = "canonical_timeline_review_self_edge"
PROVENANCE_ENDPOINT_MISMATCH = "canonical_timeline_review_provenance_endpoint_mismatch"
CONFLICT_PROVENANCE_NOT_CONFLICTING = (
    "canonical_timeline_review_conflict_provenance_not_conflicting"
)
EDGE_RECORD_DUPLICATE = "canonical_timeline_review_edge_record_duplicate"


def _episode_key(value: dict[str, Any]) -> tuple[str, str]:
    return value["storyId"], value["episodeId"]


def _stable_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _edge_record_without_key(edge: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in edge.items() if key != "reviewEdgeKey"}


def _finding(rule: str, edge_key: str, **details: Any) -> dict[str, Any]:
    return {
        "rule": rule,
        "severity": "error",
        "reviewEdgeKey": edge_key,
        **details,
    }


def _normalized_provenance_relation(
    provenance: dict[str, Any], edge: dict[str, Any]
) -> str | None:
    source = _episode_key(provenance["sourceEpisode"])
    target = _episode_key(provenance["targetEpisode"])
    edge_from = _episode_key(edge["from"])
    edge_to = _episode_key(edge["to"])
    relation = provenance["observedRelation"]
    if (source, target) == (edge_from, edge_to):
        return relation
    if (source, target) != (edge_to, edge_from):
        return None
    return {"before": "after", "after": "before", "same_time": "same_time"}[relation]


def _validate_edge(edge: dict[str, Any], story_ids: set[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    edge_key = edge["reviewEdgeKey"]
    edge_from = _episode_key(edge["from"])
    edge_to = _episode_key(edge["to"])
    outside_roles = sorted(
        role
        for role, endpoint in (("from", edge_from), ("to", edge_to))
        if endpoint[0] not in story_ids
    )
    if outside_roles:
        findings.append(
            _finding(
                EDGE_OUTSIDE_STORY_PAIR,
                edge_key,
                endpointRoles=outside_roles,
            )
        )
    if edge_from[0] == edge_to[0]:
        findings.append(_finding(SAME_STORY_EDGE, edge_key))
    if edge_from == edge_to:
        findings.append(_finding(SELF_EDGE, edge_key))

    normalized_relations: set[str] = set()
    mismatch_count = 0
    for provenance in edge["candidateProvenance"]:
        relation = _normalized_provenance_relation(provenance, edge)
        if relation is None:
            mismatch_count += 1
        else:
            normalized_relations.add(relation)
    if mismatch_count:
        findings.append(
            _finding(
                PROVENANCE_ENDPOINT_MISMATCH,
                edge_key,
                mismatchCount=mismatch_count,
            )
        )
    if edge["relationState"] == "conflict" and len(normalized_relations) < 2:
        findings.append(
            _finding(
                CONFLICT_PROVENANCE_NOT_CONFLICTING,
                edge_key,
                normalizedRelations=sorted(normalized_relations),
            )
        )
    return findings


def validate_canonical_timeline_review_packet_consistency(
    packet: dict[str, Any],
) -> list[dict[str, Any]]:
    """schema-valid review packetのcross-element不変則を検査する。"""
    findings: list[dict[str, Any]] = []
    story_ids = {story["storyId"] for story in packet["storyPair"]}
    edges = sorted(packet["edges"], key=_stable_value)

    key_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    record_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        edge_key = edge["reviewEdgeKey"]
        key_groups[edge_key].append(edge)
        record_groups[_stable_value(_edge_record_without_key(edge))].append(edge)
        findings.extend(_validate_edge(edge, story_ids))

    for edge_key, group in sorted(key_groups.items()):
        if len(group) > 1:
            findings.append(
                _finding(REVIEW_EDGE_KEY_DUPLICATE, edge_key, count=len(group))
            )

    for _record, group in sorted(record_groups.items()):
        if len(group) > 1:
            findings.append(
                _finding(
                    EDGE_RECORD_DUPLICATE,
                    group[0]["reviewEdgeKey"],
                    count=len(group),
                    reviewEdgeKeys=sorted(edge["reviewEdgeKey"] for edge in group),
                )
            )

    return sorted(
        findings,
        key=lambda finding: (
            finding["rule"],
            finding["reviewEdgeKey"],
            _stable_value(finding),
        ),
    )
