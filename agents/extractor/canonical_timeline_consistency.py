"""Canonical Timeline の合成fixture向け意味整合性検査。

JSON Schema を通過した単一documentだけを受け取り、入力を変更せずに
決定的な finding を返す。I/O、schema 検証、採用判断は行わない。
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

COMPOSITE_NODE_DUPLICATE = "canonical_timeline_composite_node_duplicate"
EDGE_ENDPOINT_MISSING = "canonical_timeline_edge_endpoint_missing"
SAME_STORY_EDGE = "canonical_timeline_same_story_edge"
SELF_EDGE = "canonical_timeline_self_edge"
EDGE_DUPLICATE = "canonical_timeline_edge_duplicate"
CANONICAL_CYCLE = "canonical_timeline_canonical_cycle"
SAME_TIME_CONTRADICTION = "canonical_timeline_same_time_contradiction"
CONFLICT_PROVENANCE_ENDPOINT_MISMATCH = (
    "canonical_timeline_conflict_provenance_endpoint_mismatch"
)
CONFLICT_PROVENANCE_NOT_CONFLICTING = (
    "canonical_timeline_conflict_provenance_not_conflicting"
)

_KNOWN_RELATIONS = {"before", "after", "same_time"}


def _node_key(node: dict[str, Any]) -> tuple[str, str]:
    return (node["storyId"], node["episodeId"])


def _node_ref(node: dict[str, Any]) -> dict[str, str]:
    return {
        "storyId": node["storyId"],
        "episodeId": node["episodeId"],
        "storyCategory": node["storyCategory"],
    }


def _stable_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _edge_ref(edge: dict[str, Any]) -> dict[str, Any]:
    """finding に載せる、配列順に依存しない edge 参照。"""
    return {
        "from": _node_ref(edge["from"]),
        "to": _node_ref(edge["to"]),
        "relationState": edge["relationState"],
        "adoptionStatus": edge["adoptionStatus"],
        "reviewStatus": edge["reviewStatus"],
        "record": _stable_value(edge),
    }


class _UnionFind:
    def __init__(self, nodes: list[tuple[str, str]]) -> None:
        self.parent = {node: node for node in nodes}

    def find(self, node: tuple[str, str]) -> tuple[str, str]:
        root = node
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[node] != node:
            parent = self.parent[node]
            self.parent[node] = root
            node = parent
        return root

    def union(self, left: tuple[str, str], right: tuple[str, str]) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            # key順を代表元にして、入力配列順を結果へ持ち込まない。
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def _canonical_known(edge: dict[str, Any]) -> bool:
    return (
        edge["adoptionStatus"] == "canonical"
        and edge["reviewStatus"] == "confirmed"
        and edge["relationState"] in _KNOWN_RELATIONS
    )


def _sccs(  # noqa: C901
    nodes: list[tuple[str, str]],
    adjacency: dict[tuple[str, str], list[tuple[str, str]]],
) -> list[list[tuple[str, str]]]:
    """再帰を使わない Kosaraju の強連結成分。"""
    visited: set[tuple[str, str]] = set()
    finish: list[tuple[str, str]] = []
    for start in nodes:
        if start in visited:
            continue
        visited.add(start)
        stack: list[tuple[tuple[str, str], int]] = [(start, 0)]
        while stack:
            node, position = stack[-1]
            neighbors = adjacency[node]
            if position == len(neighbors):
                finish.append(node)
                stack.pop()
                continue
            target = neighbors[position]
            stack[-1] = (node, position + 1)
            if target not in visited:
                visited.add(target)
                stack.append((target, 0))

    reverse: dict[tuple[str, str], list[tuple[str, str]]] = {node: [] for node in nodes}
    for source in nodes:
        for target in adjacency[source]:
            reverse[target].append(source)
    for neighbors in reverse.values():
        neighbors.sort()

    components: list[list[tuple[str, str]]] = []
    assigned: set[tuple[str, str]] = set()
    for start in reversed(finish):
        if start in assigned:
            continue
        component: list[tuple[str, str]] = []
        assigned.add(start)
        stack = [start]
        while stack:
            node = stack.pop()
            component.append(node)
            for target in reverse[node]:
                if target not in assigned:
                    assigned.add(target)
                    stack.append(target)
        components.append(sorted(component))
    return sorted(components, key=lambda component: component[0])


def _normalized_provenance_relation(
    provenance: dict[str, Any], edge: dict[str, Any]
) -> str | None:
    source, target = (
        _node_key(provenance["sourceEpisode"]),
        _node_key(provenance["targetEpisode"]),
    )
    edge_from, edge_to = _node_key(edge["from"]), _node_key(edge["to"])
    if (source, target) == (edge_from, edge_to):
        return provenance["observedRelation"]
    if (source, target) != (edge_to, edge_from):
        return None
    relation = provenance["observedRelation"]
    return {"before": "after", "after": "before", "same_time": "same_time"}[relation]


def validate_canonical_timeline_consistency(  # noqa: C901
    document: dict[str, Any],
) -> list[dict[str, Any]]:
    """schema-valid canonical Timeline の横断的な意味矛盾を返す。"""
    nodes = document["nodes"]
    edges = document["edges"]
    findings: list[dict[str, Any]] = []

    node_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        node_groups[_node_key(node)].append(node)
    for _key, group in sorted(node_groups.items()):
        if len(group) > 1:
            findings.append(
                {
                    "rule": COMPOSITE_NODE_DUPLICATE,
                    "severity": "error",
                    "node": _node_ref(group[0]),
                    "count": len(group),
                }
            )

    node_keys = set(node_groups)
    sorted_edges = sorted(edges, key=_stable_value)
    edge_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in sorted_edges:
        edge_groups[_stable_value(edge)].append(edge)
        edge_from, edge_to = _node_key(edge["from"]), _node_key(edge["to"])
        missing = [key for key in (edge_from, edge_to) if key not in node_keys]
        if missing:
            findings.append(
                {
                    "rule": EDGE_ENDPOINT_MISSING,
                    "severity": "error",
                    "edge": _edge_ref(edge),
                    "missingNodes": [
                        {"storyId": story_id, "episodeId": episode_id}
                        for story_id, episode_id in sorted(set(missing))
                    ],
                }
            )
        if edge_from[0] == edge_to[0]:
            findings.append(
                {
                    "rule": SAME_STORY_EDGE,
                    "severity": "error",
                    "edge": _edge_ref(edge),
                }
            )
        if edge_from == edge_to:
            findings.append(
                {"rule": SELF_EDGE, "severity": "error", "edge": _edge_ref(edge)}
            )
        if edge["relationState"] == "conflict":
            normalized_relations: set[str] = set()
            mismatches: list[dict[str, Any]] = []
            for provenance in edge["candidateProvenance"]:
                relation = _normalized_provenance_relation(provenance, edge)
                if relation is None:
                    mismatches.append(
                        {
                            "candidateId": provenance["candidateId"],
                            "sourceEpisode": _node_ref(provenance["sourceEpisode"]),
                            "targetEpisode": _node_ref(provenance["targetEpisode"]),
                        }
                    )
                else:
                    normalized_relations.add(relation)
            if mismatches:
                findings.append(
                    {
                        "rule": CONFLICT_PROVENANCE_ENDPOINT_MISMATCH,
                        "severity": "error",
                        "edge": _edge_ref(edge),
                        "provenance": sorted(
                            mismatches, key=lambda item: _stable_value(item)
                        ),
                    }
                )
            if len(normalized_relations) < 2:
                findings.append(
                    {
                        "rule": CONFLICT_PROVENANCE_NOT_CONFLICTING,
                        "severity": "error",
                        "edge": _edge_ref(edge),
                        "normalizedRelations": sorted(normalized_relations),
                    }
                )

    for _record, group in sorted(edge_groups.items()):
        if len(group) > 1:
            findings.append(
                {
                    "rule": EDGE_DUPLICATE,
                    "severity": "error",
                    "edge": _edge_ref(group[0]),
                    "count": len(group),
                }
            )

    graph_nodes = sorted(node_keys)
    canonical_edges = [
        edge
        for edge in sorted_edges
        if _canonical_known(edge)
        and _node_key(edge["from"]) in node_keys
        and _node_key(edge["to"]) in node_keys
        and edge["from"]["storyId"] != edge["to"]["storyId"]
    ]
    union_find = _UnionFind(graph_nodes)
    for edge in canonical_edges:
        if edge["relationState"] == "same_time":
            edge_from, edge_to = _node_key(edge["from"]), _node_key(edge["to"])
            if edge_from in node_keys and edge_to in node_keys:
                union_find.union(edge_from, edge_to)

    class_members: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for node in graph_nodes:
        class_members[union_find.find(node)].append(node)
    for members in class_members.values():
        members.sort()

    class_adjacency: dict[tuple[str, str], list[tuple[str, str]]] = {
        root: [] for root in class_members
    }
    contracted_edges: list[tuple[tuple[str, str], tuple[str, str], dict[str, Any]]] = []
    for edge in canonical_edges:
        relation = edge["relationState"]
        if relation == "same_time":
            continue
        edge_from, edge_to = _node_key(edge["from"]), _node_key(edge["to"])
        if edge_from not in node_keys or edge_to not in node_keys:
            continue
        if relation == "after":
            edge_from, edge_to = edge_to, edge_from
        source, target = union_find.find(edge_from), union_find.find(edge_to)
        if source == target:
            findings.append(
                {
                    "rule": SAME_TIME_CONTRADICTION,
                    "severity": "error",
                    "edge": _edge_ref(edge),
                    "sameTimeClass": [
                        {"storyId": story_id, "episodeId": episode_id}
                        for story_id, episode_id in class_members[source]
                    ],
                }
            )
            continue
        class_adjacency[source].append(target)
        contracted_edges.append((source, target, edge))
    for neighbors in class_adjacency.values():
        neighbors.sort()

    for component in _sccs(sorted(class_adjacency), class_adjacency):
        component_set = set(component)
        component_edges = [
            edge
            for source, target, edge in contracted_edges
            if source in component_set and target in component_set
        ]
        if len(component) > 1 or any(
            source == target for source, target, _ in contracted_edges
        ):
            if component_edges:
                findings.append(
                    {
                        "rule": CANONICAL_CYCLE,
                        "severity": "error",
                        "sameTimeClasses": [
                            [
                                {"storyId": story_id, "episodeId": episode_id}
                                for story_id, episode_id in class_members[root]
                            ]
                            for root in component
                        ],
                        "edges": [
                            _edge_ref(edge)
                            for edge in sorted(component_edges, key=_stable_value)
                        ],
                    }
                )

    return sorted(
        findings, key=lambda finding: (finding["rule"], _stable_value(finding))
    )
