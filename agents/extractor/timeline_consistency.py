"""Stage A TimelineCandidate群の横断順序整合性を検査する。

relative_orderのsame_timeを同値関係として縮約した後、before/afterの
同値class内矛盾とclass間循環を、candidate provenanceを保持して検出する。
同一episode/fieldの値競合と、同一story内の一意なcanonicalOrderに対する
relative constraint違反も検出するが、値の選択やcanonical timeline確定は行わない。
"""

from __future__ import annotations

from typing import Any

FINDING_RULE = "timeline_relative_order_cycle"
SAME_TIME_FINDING_RULE = "timeline_relative_order_within_same_time_class"
NUMERIC_FINDING_RULE = "timeline_episode_order_field_value_conflict"
CANONICAL_CONSTRAINT_FINDING_RULE = (
    "timeline_canonical_order_relative_constraint_conflict"
)

IGNORE_MISSING_RELATIVE_TO = "missing_relative_to"
IGNORE_MISSING_RELATION = "missing_relation"
IGNORE_TARGET_NOT_LOADED = "target_not_loaded"
IGNORE_UNSUPPORTED_RELATION = "unsupported_relation"

_SUPPORTED_RELATIONS = {"before", "after", "same_time"}
_EPISODE_ORDER_FIELDS = {"canonicalOrder", "releaseOrder", "displayOrder"}
_PRIVATE_OBSERVATION_FIELDS = {"_observationIndex", "_storyId", "_extractionRun"}


class _UnionFind:
    """入力episode初出順を代表元の決定規則に使うUnion-Find。"""

    def __init__(self, nodes: list[str]) -> None:
        self._parent = {node: node for node in nodes}
        self._node_order = {node: index for index, node in enumerate(nodes)}

    def find(self, node: str) -> str:
        root = node
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[node] != node:
            parent = self._parent[node]
            self._parent[node] = root
            node = parent
        return root

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self._node_order[left_root] <= self._node_order[right_root]:
            self._parent[right_root] = left_root
        else:
            self._parent[left_root] = right_root


def _candidate_ref(
    source_path: str, episode_id: str, candidate: dict[str, Any]
) -> dict[str, Any]:
    return {
        "sourcePath": source_path,
        "episodeId": episode_id,
        "candidateId": candidate.get("id"),
        "evidenceIds": list(candidate.get("evidenceIds", []) or []),
    }


def _observation_candidate_ref(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourcePath": observation["sourcePath"],
        "episodeId": observation["sourceEpisodeId"],
        "candidateId": observation["candidateId"],
        "evidenceIds": list(observation["evidenceIds"]),
    }


def _public_observation(observation: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in observation.items()
        if key not in _PRIVATE_OBSERVATION_FIELDS
    }


def _candidate_refs(
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for observation in sorted(observations, key=lambda item: item["_observationIndex"]):
        key = (observation["sourcePath"], observation["candidateId"])
        if key in seen:
            continue
        seen.add(key)
        refs.append(_observation_candidate_ref(observation))
    return refs


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
    story_id: str,
    episode_id: str,
    candidate: dict[str, Any],
    known_episode_ids: set[str],
    observation_index: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    candidate_ref = _candidate_ref(source_path, episode_id, candidate)
    relative_to = candidate.get("relativeTo")
    relation = candidate.get("relation")

    if not isinstance(relative_to, str) or not relative_to:
        reason = IGNORE_MISSING_RELATIVE_TO
    elif relation is None:
        reason = IGNORE_MISSING_RELATION
    elif relation not in _SUPPORTED_RELATIONS:
        reason = IGNORE_UNSUPPORTED_RELATION
    elif relative_to not in known_episode_ids:
        reason = IGNORE_TARGET_NOT_LOADED
    else:
        reason = None

    if reason is not None:
        return None, _ignored_candidate(candidate_ref, candidate, reason)

    observation = {
        "sourceEpisodeId": episode_id,
        "relativeTo": relative_to,
        "relation": relation,
        "sourcePath": source_path,
        "candidateId": candidate.get("id"),
        "evidenceIds": list(candidate.get("evidenceIds", []) or []),
        "_storyId": story_id,
        "_extractionRun": dict(candidate.get("extractionRun") or {}),
        "_observationIndex": observation_index,
    }
    if relation == "same_time":
        return observation, None

    if relation == "before":
        from_episode_id, to_episode_id = episode_id, relative_to
    else:
        from_episode_id, to_episode_id = relative_to, episode_id
    observation["fromEpisodeId"] = from_episode_id
    observation["toEpisodeId"] = to_episode_id
    return observation, None


def _collect_observations(
    documents: list[tuple[str, dict[str, Any]]],
    known_episode_ids: set[str],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    int,
    int,
]:
    edge_observations: list[dict[str, Any]] = []
    same_time_observations: list[dict[str, Any]] = []
    ignored_candidates: list[dict[str, Any]] = []
    timeline_candidate_count = 0
    relative_order_candidate_count = 0

    for source_path, document in documents:
        story_id = document.get("storyId")
        episode_id = document.get("episodeId")
        if not isinstance(story_id, str) or not isinstance(episode_id, str):
            continue
        for candidate in document.get("timelineCandidates", []) or []:
            timeline_candidate_count += 1
            if candidate.get("kind") != "relative_order":
                continue
            observation_index = relative_order_candidate_count
            relative_order_candidate_count += 1
            observation, ignored = _normalize_relative_candidate(
                source_path,
                story_id,
                episode_id,
                candidate,
                known_episode_ids,
                observation_index,
            )
            if ignored is not None:
                ignored_candidates.append(ignored)
            elif observation is not None and observation["relation"] == "same_time":
                same_time_observations.append(observation)
            elif observation is not None:
                edge_observations.append(observation)

    return (
        edge_observations,
        same_time_observations,
        ignored_candidates,
        timeline_candidate_count,
        relative_order_candidate_count,
    )


def _build_same_time_classes(
    nodes: list[str], same_time_observations: list[dict[str, Any]]
) -> tuple[dict[str, str], list[str], dict[str, list[str]]]:
    union_find = _UnionFind(nodes)
    for observation in same_time_observations:
        union_find.union(observation["sourceEpisodeId"], observation["relativeTo"])

    class_by_episode = {node: union_find.find(node) for node in nodes}
    class_members: dict[str, list[str]] = {}
    for node in nodes:
        class_members.setdefault(class_by_episode[node], []).append(node)
    class_nodes = list(class_members)
    return class_by_episode, class_nodes, class_members


def _relevant_same_time_observations(
    class_roots: set[str],
    class_by_episode: dict[str, str],
    class_members: dict[str, list[str]],
    same_time_observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    nontrivial_roots = {root for root in class_roots if len(class_members[root]) > 1}
    return [
        observation
        for observation in same_time_observations
        if class_by_episode[observation["sourceEpisodeId"]] in nontrivial_roots
    ]


def _same_time_class_episode_ids(
    class_roots: set[str],
    class_nodes: list[str],
    class_members: dict[str, list[str]],
) -> list[list[str]]:
    return [
        list(class_members[root])
        for root in class_nodes
        if root in class_roots and len(class_members[root]) > 1
    ]


def _finding(
    *,
    rule: str,
    class_roots: set[str],
    nodes: list[str],
    class_nodes: list[str],
    class_by_episode: dict[str, str],
    class_members: dict[str, list[str]],
    edges: list[dict[str, Any]],
    same_time_observations: list[dict[str, Any]],
) -> dict[str, Any]:
    same_time_edges = _relevant_same_time_observations(
        class_roots,
        class_by_episode,
        class_members,
        same_time_observations,
    )
    return {
        "rule": rule,
        "severity": "warning",
        "episodeIds": [node for node in nodes if class_by_episode[node] in class_roots],
        "candidateRefs": _candidate_refs([*edges, *same_time_edges]),
        "edges": [_public_observation(edge) for edge in edges],
        "sameTimeEdges": [
            _public_observation(observation) for observation in same_time_edges
        ],
        "sameTimeClassEpisodeIds": _same_time_class_episode_ids(
            class_roots, class_nodes, class_members
        ),
    }


def _build_contracted_graph(
    class_nodes: list[str],
    class_by_episode: dict[str, str],
    class_members: dict[str, list[str]],
    edge_observations: list[dict[str, Any]],
) -> tuple[
    dict[str, list[str]],
    set[tuple[str, str]],
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
]:
    adjacency: dict[str, list[str]] = {node: [] for node in class_nodes}
    distinct_class_edges: set[tuple[str, str]] = set()
    within_same_time_edges: dict[str, list[dict[str, Any]]] = {}
    graph_edge_observations: list[dict[str, Any]] = []

    for observation in edge_observations:
        source_root = class_by_episode[observation["fromEpisodeId"]]
        target_root = class_by_episode[observation["toEpisodeId"]]
        if source_root == target_root and len(class_members[source_root]) > 1:
            within_same_time_edges.setdefault(source_root, []).append(observation)
            continue

        graph_edge_observations.append(observation)
        class_edge = (source_root, target_root)
        if class_edge not in distinct_class_edges:
            distinct_class_edges.add(class_edge)
            adjacency[source_root].append(target_root)

    return (
        adjacency,
        distinct_class_edges,
        within_same_time_edges,
        graph_edge_observations,
    )


def _build_findings(
    *,
    nodes: list[str],
    class_nodes: list[str],
    class_by_episode: dict[str, str],
    class_members: dict[str, list[str]],
    adjacency: dict[str, list[str]],
    distinct_class_edges: set[tuple[str, str]],
    within_same_time_edges: dict[str, list[dict[str, Any]]],
    graph_edge_observations: list[dict[str, Any]],
    same_time_observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    finding_parts: list[tuple[int, dict[str, Any]]] = []

    for root in class_nodes:
        edges = within_same_time_edges.get(root, [])
        if edges:
            finding_parts.append(
                (
                    edges[0]["_observationIndex"],
                    _finding(
                        rule=SAME_TIME_FINDING_RULE,
                        class_roots={root},
                        nodes=nodes,
                        class_nodes=class_nodes,
                        class_by_episode=class_by_episode,
                        class_members=class_members,
                        edges=edges,
                        same_time_observations=same_time_observations,
                    ),
                )
            )

    for component in _strongly_connected_components(class_nodes, adjacency):
        component_set = set(component)
        is_self_loop = (
            len(component) == 1 and (component[0], component[0]) in distinct_class_edges
        )
        if len(component) == 1 and not is_self_loop:
            continue
        edges = [
            observation
            for observation in graph_edge_observations
            if class_by_episode[observation["fromEpisodeId"]] in component_set
            and class_by_episode[observation["toEpisodeId"]] in component_set
        ]
        if not edges:
            continue
        finding_parts.append(
            (
                edges[0]["_observationIndex"],
                _finding(
                    rule=FINDING_RULE,
                    class_roots=component_set,
                    nodes=nodes,
                    class_nodes=class_nodes,
                    class_by_episode=class_by_episode,
                    class_members=class_members,
                    edges=edges,
                    same_time_observations=same_time_observations,
                ),
            )
        )

    return [
        finding for _index, finding in sorted(finding_parts, key=lambda item: item[0])
    ]


def _numeric_observation(
    source_path: str,
    episode_id: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "sourcePath": source_path,
        "episodeId": episode_id,
        "candidateId": candidate.get("id"),
        "evidenceIds": list(candidate.get("evidenceIds", []) or []),
        "scope": candidate.get("scope"),
        "orderField": candidate.get("orderField"),
        "orderValue": candidate.get("orderValue"),
        "extractionRun": dict(candidate.get("extractionRun") or {}),
    }


def _numeric_ignore_reason(candidate: dict[str, Any]) -> str | None:
    if candidate.get("scope") != "episode":
        return "unsupported_scope"
    order_field = candidate.get("orderField")
    if not isinstance(order_field, str) or not order_field:
        return "missing_order_field"
    if order_field not in _EPISODE_ORDER_FIELDS:
        return "unsupported_order_field"
    if candidate.get("orderValue") is None:
        return "missing_order_value"
    return None


def _append_distinct_value(values: list[int | float], value: int | float) -> None:
    if not any(value == existing for existing in values):
        values.append(value)


def _analyze_numeric_episode_orders(
    documents: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    ignored_observations: list[dict[str, Any]] = []
    explicit_order_candidate_count = 0
    observation_count = 0

    for source_path, document in documents:
        episode_id = document.get("episodeId")
        if not isinstance(episode_id, str):
            continue
        for candidate in document.get("timelineCandidates", []) or []:
            if candidate.get("kind") != "explicit_order":
                continue
            explicit_order_candidate_count += 1
            observation = _numeric_observation(source_path, episode_id, candidate)
            reason = _numeric_ignore_reason(candidate)
            if reason is not None:
                ignored_observations.append({"reason": reason, **observation})
                continue
            observation_count += 1
            order_field = observation["orderField"]
            assert isinstance(order_field, str)
            groups.setdefault((episode_id, order_field), []).append(observation)

    findings: list[dict[str, Any]] = []
    for (episode_id, order_field), observations in groups.items():
        values: list[int | float] = []
        for observation in observations:
            value = observation["orderValue"]
            assert isinstance(value, int | float) and not isinstance(value, bool)
            _append_distinct_value(values, value)
        if len(values) < 2:
            continue
        findings.append(
            {
                "rule": NUMERIC_FINDING_RULE,
                "severity": "warning",
                "episodeId": episode_id,
                "orderField": order_field,
                "values": values,
                "observations": observations,
            }
        )

    return {
        "explicitOrderCandidateCount": explicit_order_candidate_count,
        "numericEpisodeObservationCount": observation_count,
        "numericEpisodeOrderGroupCount": len(groups),
        "numericIgnoredObservationCount": len(ignored_observations),
        "numericIgnoredObservations": ignored_observations,
        "numericFindingCount": len(findings),
        "numericFindings": findings,
    }


def _canonical_order_observation(
    source_path: str,
    story_id: str,
    episode_id: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "sourcePath": source_path,
        "storyId": story_id,
        "episodeId": episode_id,
        "candidateId": candidate.get("id"),
        "evidenceIds": list(candidate.get("evidenceIds", []) or []),
        "orderValue": candidate.get("orderValue"),
        "extractionRun": dict(candidate.get("extractionRun") or {}),
    }


def _relative_constraint_observation(
    observation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "sourcePath": observation["sourcePath"],
        "storyId": observation["_storyId"],
        "sourceEpisodeId": observation["sourceEpisodeId"],
        "relativeTo": observation["relativeTo"],
        "relation": observation["relation"],
        "candidateId": observation["candidateId"],
        "evidenceIds": list(observation["evidenceIds"]),
        "extractionRun": dict(observation["_extractionRun"]),
    }


def _distinct_order_values(
    observations: list[dict[str, Any]],
) -> list[int | float]:
    values: list[int | float] = []
    for observation in observations:
        value = observation["orderValue"]
        assert isinstance(value, int | float) and not isinstance(value, bool)
        _append_distinct_value(values, value)
    return values


def _constraint_ignore_reasons(
    source_values: list[int | float],
    target_values: list[int | float],
) -> list[str]:
    reasons: list[str] = []
    if not source_values:
        reasons.append("missing_source_canonical_order")
    elif len(source_values) > 1:
        reasons.append("ambiguous_source_canonical_order")
    if not target_values:
        reasons.append("missing_target_canonical_order")
    elif len(target_values) > 1:
        reasons.append("ambiguous_target_canonical_order")
    return reasons


def _constraint_is_satisfied(
    relation: str,
    source_value: int | float,
    target_value: int | float,
) -> bool:
    if relation == "same_time":
        return source_value == target_value
    if relation == "before":
        return source_value < target_value
    assert relation == "after"
    return source_value > target_value


def _analyze_canonical_constraints(
    documents: list[tuple[str, dict[str, Any]]],
    relative_observations: list[dict[str, Any]],
) -> dict[str, Any]:
    episode_story_ids: dict[str, set[str]] = {}
    canonical_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    canonical_orders_by_episode: dict[str, list[dict[str, Any]]] = {}
    canonical_observation_count = 0

    for source_path, document in documents:
        story_id = document.get("storyId")
        episode_id = document.get("episodeId")
        if not isinstance(story_id, str) or not isinstance(episode_id, str):
            continue
        episode_story_ids.setdefault(episode_id, set()).add(story_id)
        for candidate in document.get("timelineCandidates", []) or []:
            if (
                candidate.get("kind") != "explicit_order"
                or candidate.get("scope") != "episode"
                or candidate.get("orderField") != "canonicalOrder"
                or candidate.get("orderValue") is None
            ):
                continue
            canonical_observation_count += 1
            order_observation = _canonical_order_observation(
                source_path, story_id, episode_id, candidate
            )
            canonical_groups.setdefault((story_id, episode_id), []).append(
                order_observation
            )
            canonical_orders_by_episode.setdefault(episode_id, []).append(
                order_observation
            )

    ignored_candidates: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    cross_story_order_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}
    checked_count = 0
    sorted_relative_observations = sorted(
        relative_observations, key=lambda item: item["_observationIndex"]
    )

    for observation in sorted_relative_observations:
        story_id = observation["_storyId"]
        source_episode_id = observation["sourceEpisodeId"]
        target_episode_id = observation["relativeTo"]
        constraint = _relative_constraint_observation(observation)
        source_orders = list(canonical_groups.get((story_id, source_episode_id), []))
        same_story_target_loaded = story_id in episode_story_ids.get(
            target_episode_id, set()
        )
        if not same_story_target_loaded:
            cache_key = (story_id, target_episode_id)
            if cache_key not in cross_story_order_cache:
                cross_story_order_cache[cache_key] = [
                    order
                    for order in canonical_orders_by_episode.get(target_episode_id, [])
                    if order["storyId"] != story_id
                ]
            target_orders = list(cross_story_order_cache[cache_key])
            ignored_candidates.append(
                {
                    "reasons": ["cross_story_constraint"],
                    "constraint": constraint,
                    "sourceOrderObservations": source_orders,
                    "targetOrderObservations": target_orders,
                }
            )
            continue

        target_orders = list(canonical_groups.get((story_id, target_episode_id), []))
        source_values = _distinct_order_values(source_orders)
        target_values = _distinct_order_values(target_orders)
        reasons = _constraint_ignore_reasons(source_values, target_values)
        if reasons:
            ignored_candidates.append(
                {
                    "reasons": reasons,
                    "constraint": constraint,
                    "sourceOrderObservations": source_orders,
                    "targetOrderObservations": target_orders,
                }
            )
            continue

        checked_count += 1
        source_value = source_values[0]
        target_value = target_values[0]
        if _constraint_is_satisfied(
            observation["relation"], source_value, target_value
        ):
            continue
        findings.append(
            {
                "rule": CANONICAL_CONSTRAINT_FINDING_RULE,
                "severity": "warning",
                "storyId": story_id,
                "constraint": constraint,
                "sourceCanonicalOrder": source_value,
                "targetCanonicalOrder": target_value,
                "sourceOrderObservations": source_orders,
                "targetOrderObservations": target_orders,
            }
        )

    return {
        "canonicalOrderObservationCount": canonical_observation_count,
        "canonicalConstraintCandidateCount": len(sorted_relative_observations),
        "canonicalConstraintCheckedCount": checked_count,
        "canonicalConstraintIgnoredCount": len(ignored_candidates),
        "canonicalConstraintIgnoredCandidates": ignored_candidates,
        "canonicalConstraintFindingCount": len(findings),
        "canonicalConstraintFindings": findings,
    }


def analyze_timeline_consistency(
    documents: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """検証済みepisode_extraction群のrelative_order矛盾を検出する。"""
    nodes: list[str] = []
    known_episode_ids: set[str] = set()
    for _source_path, document in documents:
        episode_id = document.get("episodeId")
        if isinstance(episode_id, str) and episode_id not in known_episode_ids:
            known_episode_ids.add(episode_id)
            nodes.append(episode_id)

    (
        edge_observations,
        same_time_observations,
        ignored_candidates,
        timeline_candidate_count,
        relative_order_candidate_count,
    ) = _collect_observations(documents, known_episode_ids)
    class_by_episode, class_nodes, class_members = _build_same_time_classes(
        nodes, same_time_observations
    )
    (
        adjacency,
        distinct_class_edges,
        within_same_time_edges,
        graph_edge_observations,
    ) = _build_contracted_graph(
        class_nodes,
        class_by_episode,
        class_members,
        edge_observations,
    )
    distinct_edges = {
        (observation["fromEpisodeId"], observation["toEpisodeId"])
        for observation in edge_observations
    }
    node_order = {node: index for index, node in enumerate(nodes)}
    distinct_same_time_edges = {
        tuple(
            sorted(
                (observation["sourceEpisodeId"], observation["relativeTo"]),
                key=node_order.__getitem__,
            )
        )
        for observation in same_time_observations
    }
    findings = _build_findings(
        nodes=nodes,
        class_nodes=class_nodes,
        class_by_episode=class_by_episode,
        class_members=class_members,
        adjacency=adjacency,
        distinct_class_edges=distinct_class_edges,
        within_same_time_edges=within_same_time_edges,
        graph_edge_observations=graph_edge_observations,
        same_time_observations=same_time_observations,
    )
    numeric_analysis = _analyze_numeric_episode_orders(documents)
    canonical_constraint_analysis = _analyze_canonical_constraints(
        documents, [*edge_observations, *same_time_observations]
    )
    return {
        "timelineCandidateCount": timeline_candidate_count,
        "relativeOrderCandidateCount": relative_order_candidate_count,
        "checkedCandidateCount": len(edge_observations),
        "distinctEdgeCount": len(distinct_edges),
        "checkedSameTimeCandidateCount": len(same_time_observations),
        "distinctSameTimeEdgeCount": len(distinct_same_time_edges),
        "sameTimeClassCount": sum(
            len(members) > 1 for members in class_members.values()
        ),
        "distinctClassEdgeCount": len(distinct_class_edges),
        "ignoredCandidateCount": len(ignored_candidates),
        "ignoredCandidates": ignored_candidates,
        "findingCount": len(findings),
        "findings": findings,
        **numeric_analysis,
        **canonical_constraint_analysis,
    }
