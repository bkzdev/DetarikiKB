"""Canonical Timelineのpublic projectionを構成する純粋関数。

schema-validなinternal canonical documentと、人間確認済みのEpisode単位
public metadata mappingを入力前提とする。I/O、schema検証、Registry照合、
publish-ready判定、rendererは行わない。
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from copy import deepcopy
from typing import Any

from agents.extractor.canonical_timeline_consistency import (
    validate_canonical_timeline_consistency,
)

BASELINE_INVALID = "canonical_timeline_public_projection_baseline_invalid"
PUBLIC_MAPPING_MISSING = "canonical_timeline_public_projection_mapping_missing"
PUBLIC_MAPPING_INVALID = "canonical_timeline_public_projection_mapping_invalid"
PUBLIC_EPISODE_ID_DUPLICATE = (
    "canonical_timeline_public_projection_public_episode_id_duplicate"
)
PUBLIC_STORY_MAPPING_CONFLICT = (
    "canonical_timeline_public_projection_public_story_mapping_conflict"
)
PUBLIC_STORY_LABEL_CONFLICT = (
    "canonical_timeline_public_projection_public_story_label_conflict"
)
PUBLIC_RELATION_DUPLICATE = (
    "canonical_timeline_public_projection_public_relation_duplicate"
)
COMPONENT_CAPACITY_EXCEEDED = (
    "canonical_timeline_public_projection_component_capacity_exceeded"
)
PROJECTION_MISMATCH = "canonical_timeline_public_projection_mismatch"

_KNOWN_RELATIONS = {"before", "after", "same_time"}
_PUBLIC_MAPPING_FIELDS = {
    "publicStoryId",
    "publicEpisodeId",
    "storyLabel",
    "episodeLabel",
}
_PUBLIC_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_RELATION_LABEL_KEYS = {
    "before": "timeline_before",
    "after": "timeline_after",
    "same_time": "timeline_same_time",
}

EpisodeKey = tuple[str, str]
PublicEpisodeMapping = dict[EpisodeKey, dict[str, str]]


def _stable_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _episode_key(node: dict[str, Any]) -> EpisodeKey:
    return (node["storyId"], node["episodeId"])


def _is_eligible(edge: dict[str, Any]) -> bool:
    return (
        edge["adoptionStatus"] == "canonical"
        and edge["reviewStatus"] == "confirmed"
        and edge["relationState"] in _KNOWN_RELATIONS
    )


def _empty_projection() -> dict[str, Any]:
    return {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_public_projection",
        "visibility": "public",
        "publishStatus": "projection_candidate",
        "scope": "event",
        "purpose": "confirmed_relation_navigation",
        "coverageNoticeKey": "partial_confirmed_relations_only",
        "components": [],
        "unresolvedRelationSummary": None,
    }


def _valid_public_label(value: Any) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 200
        and "\r" not in value
        and "\n" not in value
    )


def _valid_mapping_record(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == _PUBLIC_MAPPING_FIELDS
        and isinstance(value.get("publicStoryId"), str)
        and _PUBLIC_ID_PATTERN.fullmatch(value["publicStoryId"]) is not None
        and isinstance(value.get("publicEpisodeId"), str)
        and _PUBLIC_ID_PATTERN.fullmatch(value["publicEpisodeId"]) is not None
        and _valid_public_label(value.get("storyLabel"))
        and _valid_public_label(value.get("episodeLabel"))
    )


def _mapping_findings(
    node_keys: set[EpisodeKey], mapping: PublicEpisodeMapping
) -> tuple[list[dict[str, Any]], dict[EpisodeKey, dict[str, str]]]:
    missing = 0
    invalid = 0
    valid: dict[EpisodeKey, dict[str, str]] = {}
    for node_key in sorted(node_keys):
        record = mapping.get(node_key)
        if record is None:
            missing += 1
        elif not _valid_mapping_record(record):
            invalid += 1
        else:
            valid[node_key] = record

    findings: list[dict[str, Any]] = []
    if missing:
        findings.append({"rule": PUBLIC_MAPPING_MISSING, "count": missing})
    if invalid:
        findings.append({"rule": PUBLIC_MAPPING_INVALID, "count": invalid})
    if missing or invalid:
        return findings, valid

    return _valid_mapping_consistency_findings(valid), valid


def _valid_mapping_consistency_findings(
    valid: dict[EpisodeKey, dict[str, str]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    episode_groups: dict[str, set[EpisodeKey]] = defaultdict(set)
    internal_story_groups: dict[str, set[str]] = defaultdict(set)
    public_story_groups: dict[str, set[str]] = defaultdict(set)
    public_story_labels: dict[str, set[str]] = defaultdict(set)
    for (story_id, episode_id), record in valid.items():
        episode_groups[record["publicEpisodeId"]].add((story_id, episode_id))
        internal_story_groups[story_id].add(record["publicStoryId"])
        public_story_groups[record["publicStoryId"]].add(story_id)
        public_story_labels[record["publicStoryId"]].add(record["storyLabel"])

    duplicate_public_episodes = sum(
        1 for episode_keys in episode_groups.values() if len(episode_keys) > 1
    )
    if duplicate_public_episodes:
        findings.append(
            {
                "rule": PUBLIC_EPISODE_ID_DUPLICATE,
                "count": duplicate_public_episodes,
            }
        )

    story_conflicts = sum(
        1
        for public_story_ids in internal_story_groups.values()
        if len(public_story_ids) > 1
    ) + sum(1 for story_ids in public_story_groups.values() if len(story_ids) > 1)
    if story_conflicts:
        findings.append(
            {"rule": PUBLIC_STORY_MAPPING_CONFLICT, "count": story_conflicts}
        )
    story_label_conflicts = sum(
        1
        for public_story_id, labels in public_story_labels.items()
        if len(public_story_groups[public_story_id]) == 1 and len(labels) > 1
    )
    if story_label_conflicts:
        findings.append(
            {"rule": PUBLIC_STORY_LABEL_CONFLICT, "count": story_label_conflicts}
        )
    return sorted(findings, key=_stable_value)


def _public_relation_duplicate_count(
    edges: list[dict[str, Any]], mapping: dict[EpisodeKey, dict[str, str]]
) -> int:
    fingerprints = [
        (
            mapping[_episode_key(edge["from"])]["publicEpisodeId"],
            mapping[_episode_key(edge["to"])]["publicEpisodeId"],
            edge["relationState"],
            _RELATION_LABEL_KEYS[edge["relationState"]],
        )
        for edge in edges
    ]
    return len(fingerprints) - len(set(fingerprints))


class _UnionFind:
    def __init__(self, nodes: set[EpisodeKey]) -> None:
        self.parent = {node: node for node in nodes}

    def find(self, node: EpisodeKey) -> EpisodeKey:
        root = node
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[node] != node:
            parent = self.parent[node]
            self.parent[node] = root
            node = parent
        return root

    def union(self, left: EpisodeKey, right: EpisodeKey) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def _build_components(
    edges: list[dict[str, Any]], mapping: dict[EpisodeKey, dict[str, str]]
) -> list[dict[str, Any]]:
    node_keys = {
        _episode_key(endpoint)
        for edge in edges
        for endpoint in (edge["from"], edge["to"])
    }
    union_find = _UnionFind(node_keys)
    for edge in edges:
        union_find.union(_episode_key(edge["from"]), _episode_key(edge["to"]))

    component_nodes: dict[EpisodeKey, set[EpisodeKey]] = defaultdict(set)
    component_edges: dict[EpisodeKey, list[dict[str, Any]]] = defaultdict(list)
    for node_key in node_keys:
        component_nodes[union_find.find(node_key)].add(node_key)
    for edge in edges:
        component_edges[union_find.find(_episode_key(edge["from"]))].append(edge)

    projected: list[dict[str, Any]] = []
    for root, members in component_nodes.items():
        nodes = [deepcopy(mapping[node_key]) for node_key in members]
        nodes.sort(key=_stable_value)
        relations = [
            {
                "fromPublicEpisodeId": mapping[_episode_key(edge["from"])][
                    "publicEpisodeId"
                ],
                "toPublicEpisodeId": mapping[_episode_key(edge["to"])][
                    "publicEpisodeId"
                ],
                "relationState": edge["relationState"],
                "labelKey": _RELATION_LABEL_KEYS[edge["relationState"]],
            }
            for edge in component_edges[root]
        ]
        relations.sort(key=_stable_value)
        projected.append({"nodes": nodes, "relations": relations})

    projected.sort(key=_stable_value)
    return [
        {"componentKey": f"component-{number:04d}", **component}
        for number, component in enumerate(projected, start=1)
    ]


def _report_counts(
    document: dict[str, Any], eligible_edges: list[dict[str, Any]]
) -> dict[str, int]:
    edges = document["edges"]
    return {
        "inputNodeCount": len(document["nodes"]),
        "inputRelationCount": len(edges),
        "eligibleRelationCount": len(eligible_edges),
        "ineligibleKnownRelationCount": sum(
            1
            for edge in edges
            if edge["relationState"] in _KNOWN_RELATIONS and not _is_eligible(edge)
        ),
        "unknownRelationCount": sum(
            edge["relationState"] == "unknown" for edge in edges
        ),
        "conflictRelationCount": sum(
            edge["relationState"] == "conflict" for edge in edges
        ),
        "projectedComponentCount": 0,
        "projectedNodeCount": 0,
        "projectedRelationCount": 0,
    }


def build_canonical_timeline_public_projection(
    document: dict[str, Any],
    public_episode_mapping: PublicEpisodeMapping,
) -> dict[str, Any]:
    """public projection候補と内部IDを含まなsafe aggregate reportを返す。

    baselineやmappingが不正な場合は例外で部分出力せず、空の
    `projection_candidate`と`blocked` reportを返す。入力は変更しない。
    """
    eligible_edges = sorted(
        (edge for edge in document["edges"] if _is_eligible(edge)), key=_stable_value
    )
    counts = _report_counts(document, eligible_edges)
    baseline_findings = validate_canonical_timeline_consistency(document)
    if baseline_findings:
        return {
            "projection": _empty_projection(),
            "report": {
                "status": "blocked",
                "counts": counts,
                "findings": [
                    {"rule": BASELINE_INVALID, "count": len(baseline_findings)}
                ],
            },
        }

    projected_node_keys = {
        _episode_key(endpoint)
        for edge in eligible_edges
        for endpoint in (edge["from"], edge["to"])
    }
    mapping_findings, valid_mapping = _mapping_findings(
        projected_node_keys, public_episode_mapping
    )
    # capacity判定は実component構成と同じ非有向連結で行う。
    component_count = len(_component_roots(eligible_edges))
    if component_count > 9999:
        mapping_findings.append({"rule": COMPONENT_CAPACITY_EXCEEDED, "count": 1})
    if not mapping_findings:
        duplicate_relations = _public_relation_duplicate_count(
            eligible_edges, valid_mapping
        )
        if duplicate_relations:
            mapping_findings.append(
                {"rule": PUBLIC_RELATION_DUPLICATE, "count": duplicate_relations}
            )
    if mapping_findings:
        return {
            "projection": _empty_projection(),
            "report": {
                "status": "blocked",
                "counts": counts,
                "findings": sorted(mapping_findings, key=_stable_value),
            },
        }

    components = _build_components(eligible_edges, valid_mapping)
    counts.update(
        {
            "projectedComponentCount": len(components),
            "projectedNodeCount": sum(len(item["nodes"]) for item in components),
            "projectedRelationCount": sum(
                len(item["relations"]) for item in components
            ),
        }
    )
    projection = _empty_projection()
    projection["components"] = components
    projection["unresolvedRelationSummary"] = {
        "countScope": "canonical_artifact_only",
        "noticeKey": "unresolved_relations_not_shown",
        "unknownCount": counts["unknownRelationCount"],
        "conflictCount": counts["conflictRelationCount"],
    }
    return {
        "projection": projection,
        "report": {"status": "clean", "counts": counts, "findings": []},
    }


def _component_roots(edges: list[dict[str, Any]]) -> set[EpisodeKey]:
    nodes = {
        _episode_key(endpoint)
        for edge in edges
        for endpoint in (edge["from"], edge["to"])
    }
    union_find = _UnionFind(nodes)
    for edge in edges:
        union_find.union(_episode_key(edge["from"]), _episode_key(edge["to"]))
    return {union_find.find(node) for node in nodes}


def validate_canonical_timeline_public_projection_consistency(
    projection: dict[str, Any],
    document: dict[str, Any],
    public_episode_mapping: PublicEpisodeMapping,
) -> list[dict[str, Any]]:
    """source / mappingに対するprojectionの完全一致をsafe findingで返す。"""
    result = build_canonical_timeline_public_projection(
        document, public_episode_mapping
    )
    if result["report"]["status"] == "blocked":
        return deepcopy(result["report"]["findings"])
    if _stable_value(projection) != _stable_value(result["projection"]):
        return [{"rule": PROJECTION_MISMATCH, "count": 1}]
    return []
