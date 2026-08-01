"""Stage A TimelineCandidate 群の横断順序整合性を検査する。

現行のrule-based extractorはrelative_orderを生成しないが、schema上許容される
手動・将来のAI由来candidateを、merge前のprovenanceを保持したまま検査する。
数値順序やsame_timeの意味は確定していないため、このmoduleはbefore/afterの
有向循環だけを対象とする。
"""

from __future__ import annotations

from typing import Any

FINDING_RULE = "timeline_relative_order_cycle"

IGNORE_MISSING_RELATIVE_TO = "missing_relative_to"
IGNORE_MISSING_RELATION = "missing_relation"
IGNORE_SAME_TIME = "same_time_not_checked"
IGNORE_TARGET_NOT_LOADED = "target_not_loaded"
IGNORE_UNSUPPORTED_RELATION = "unsupported_relation"


def _candidate_ref(
    source_path: str, episode_id: str, candidate: dict[str, Any]
) -> dict[str, Any]:
    return {
        "sourcePath": source_path,
        "episodeId": episode_id,
        "candidateId": candidate.get("id"),
        "evidenceIds": list(candidate.get("evidenceIds", []) or []),
    }


def _ignored_candidate(
    candidate_ref: dict[str, Any],
    candidate: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "reason": reason,
        "sourcePath": candidate_ref["sourcePath"],
        "episodeId": candidate_ref["episodeId"],
        "candidateId": candidate_ref["candidateId"],
        "evidenceIds": candidate_ref["evidenceIds"],
        "relativeTo": candidate.get("relativeTo"),
        "relation": candidate.get("relation"),
    }


def _build_finish_order(nodes: list[str], adjacency: dict[str, list[str]]) -> list[str]:
    visited: set[str] = set()
    finish_order: list[str] = []
    for start in nodes:
        if start in visited:
            continue
        visited.add(start)
        stack: list[tuple[str, int]] = [(start, 0)]
        while stack:
            node, next_neighbor = stack[-1]
            if next_neighbor < len(adjacency[node]):
                target = adjacency[node][next_neighbor]
                stack[-1] = (node, next_neighbor + 1)
                if target not in visited:
                    visited.add(target)
                    stack.append((target, 0))
                continue
            finish_order.append(node)
            stack.pop()
    return finish_order


def _reverse_adjacency(
    nodes: list[str], adjacency: dict[str, list[str]]
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {node: [] for node in nodes}
    for source in nodes:
        for target in adjacency[source]:
            result[target].append(source)
    return result


def _collect_reverse_component(
    start: str,
    reverse_adjacency: dict[str, list[str]],
    assigned: set[str],
) -> list[str]:
    assigned.add(start)
    component: list[str] = []
    stack: list[tuple[str, int]] = [(start, 0)]
    while stack:
        node, next_neighbor = stack[-1]
        if next_neighbor == 0:
            component.append(node)
        if next_neighbor < len(reverse_adjacency[node]):
            target = reverse_adjacency[node][next_neighbor]
            stack[-1] = (node, next_neighbor + 1)
            if target not in assigned:
                assigned.add(target)
                stack.append((target, 0))
            continue
        stack.pop()
    return component


def _strongly_connected_components(
    nodes: list[str], adjacency: dict[str, list[str]]
) -> list[list[str]]:
    """反復Kosaraju法で、再帰上限に依存せずSCCを返す。"""
    finish_order = _build_finish_order(nodes, adjacency)
    reverse_adjacency = _reverse_adjacency(nodes, adjacency)

    assigned: set[str] = set()
    components: list[list[str]] = []
    for start in reversed(finish_order):
        if start in assigned:
            continue
        components.append(
            _collect_reverse_component(start, reverse_adjacency, assigned)
        )

    return components


def _normalize_relative_candidate(
    source_path: str,
    episode_id: str,
    candidate: dict[str, Any],
    known_episode_ids: set[str],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    candidate_ref = _candidate_ref(source_path, episode_id, candidate)
    relative_to = candidate.get("relativeTo")
    relation = candidate.get("relation")

    if not isinstance(relative_to, str) or not relative_to:
        reason = IGNORE_MISSING_RELATIVE_TO
    elif relation is None:
        reason = IGNORE_MISSING_RELATION
    elif relation == "same_time":
        reason = IGNORE_SAME_TIME
    elif relation not in {"before", "after"}:
        reason = IGNORE_UNSUPPORTED_RELATION
    elif relative_to not in known_episode_ids:
        reason = IGNORE_TARGET_NOT_LOADED
    else:
        reason = None

    if reason is not None:
        return None, _ignored_candidate(candidate_ref, candidate, reason)

    if relation == "before":
        from_episode_id, to_episode_id = episode_id, relative_to
    else:
        from_episode_id, to_episode_id = relative_to, episode_id

    return (
        {
            "fromEpisodeId": from_episode_id,
            "toEpisodeId": to_episode_id,
            "sourceEpisodeId": episode_id,
            "relativeTo": relative_to,
            "relation": relation,
            "sourcePath": source_path,
            "candidateId": candidate.get("id"),
            "evidenceIds": list(candidate.get("evidenceIds", []) or []),
        },
        None,
    )


def _collect_graph(
    documents: list[tuple[str, dict[str, Any]]],
    nodes: list[str],
    known_episode_ids: set[str],
) -> tuple[
    dict[str, list[str]],
    set[tuple[str, str]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    int,
    int,
]:
    adjacency: dict[str, list[str]] = {node: [] for node in nodes}
    distinct_edges: set[tuple[str, str]] = set()
    edge_observations: list[dict[str, Any]] = []
    ignored_candidates: list[dict[str, Any]] = []
    timeline_candidate_count = 0
    relative_order_candidate_count = 0

    for source_path, document in documents:
        episode_id = document.get("episodeId")
        if not isinstance(episode_id, str):
            continue
        for candidate in document.get("timelineCandidates", []) or []:
            timeline_candidate_count += 1
            if candidate.get("kind") != "relative_order":
                continue

            relative_order_candidate_count += 1
            observation, ignored = _normalize_relative_candidate(
                source_path, episode_id, candidate, known_episode_ids
            )
            if ignored is not None:
                ignored_candidates.append(ignored)
                continue
            assert observation is not None
            edge_observations.append(observation)

            edge = (observation["fromEpisodeId"], observation["toEpisodeId"])
            if edge not in distinct_edges:
                distinct_edges.add(edge)
                adjacency[edge[0]].append(edge[1])

    return (
        adjacency,
        distinct_edges,
        edge_observations,
        ignored_candidates,
        timeline_candidate_count,
        relative_order_candidate_count,
    )


def _build_findings(
    nodes: list[str],
    adjacency: dict[str, list[str]],
    distinct_edges: set[tuple[str, str]],
    edge_observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    node_order = {node: index for index, node in enumerate(nodes)}
    finding_parts: list[tuple[int, dict[str, Any]]] = []

    for component in _strongly_connected_components(nodes, adjacency):
        component_set = set(component)
        is_self_loop = (
            len(component) == 1 and (component[0], component[0]) in distinct_edges
        )
        if len(component) == 1 and not is_self_loop:
            continue

        indexed_internal_edges = [
            (index, edge)
            for index, edge in enumerate(edge_observations)
            if edge["fromEpisodeId"] in component_set
            and edge["toEpisodeId"] in component_set
        ]
        if not indexed_internal_edges:
            continue
        internal_edges = [edge for _index, edge in indexed_internal_edges]

        candidate_refs: list[dict[str, Any]] = []
        seen_candidates: set[tuple[str, str | None]] = set()
        for edge in internal_edges:
            candidate_key = (edge["sourcePath"], edge["candidateId"])
            if candidate_key in seen_candidates:
                continue
            seen_candidates.add(candidate_key)
            candidate_refs.append(
                {
                    "sourcePath": edge["sourcePath"],
                    "episodeId": edge["sourceEpisodeId"],
                    "candidateId": edge["candidateId"],
                    "evidenceIds": list(edge["evidenceIds"]),
                }
            )

        finding_parts.append(
            (
                indexed_internal_edges[0][0],
                {
                    "rule": FINDING_RULE,
                    "severity": "warning",
                    "episodeIds": sorted(component_set, key=node_order.__getitem__),
                    "candidateRefs": candidate_refs,
                    "edges": internal_edges,
                },
            )
        )

    return [finding for _index, finding in sorted(finding_parts)]


def analyze_timeline_consistency(
    documents: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """検証済みepisode_extraction群からrelative_order循環を検出する。

    beforeはsource episodeからrelativeToへの辺、afterはその逆辺へ正規化する。
    参照先episodeが入力集合に無いcandidateは部分batchで正当になりうるため、
    矛盾にはせずignoredCandidatesへprovenance付きで保持する。
    """
    nodes: list[str] = []
    known_episode_ids: set[str] = set()
    for _source_path, document in documents:
        episode_id = document.get("episodeId")
        if isinstance(episode_id, str) and episode_id not in known_episode_ids:
            known_episode_ids.add(episode_id)
            nodes.append(episode_id)

    (
        adjacency,
        distinct_edges,
        edge_observations,
        ignored_candidates,
        timeline_candidate_count,
        relative_order_candidate_count,
    ) = _collect_graph(documents, nodes, known_episode_ids)
    findings = _build_findings(nodes, adjacency, distinct_edges, edge_observations)
    return {
        "timelineCandidateCount": timeline_candidate_count,
        "relativeOrderCandidateCount": relative_order_candidate_count,
        "checkedCandidateCount": len(edge_observations),
        "distinctEdgeCount": len(distinct_edges),
        "ignoredCandidateCount": len(ignored_candidates),
        "ignoredCandidates": ignored_candidates,
        "findingCount": len(findings),
        "findings": findings,
    }
