"""
DKB Merger - Timeline Entity Merge
Stage A TimelineCandidateから Stage B merged timeline entry を組み立てる。

Timelineは他のCandidate種別と異なり、Stage Bでも「canonical化」は行わない
(Merged_Knowledge_Design.md §7.1: 順序の確定 (canonicalOrderの決定) は
Stage Bでは行わない)。そのため生成されるmerged timeline entryは常に
status: unresolvedとし、idはmerge keyから決定的に組み立てる
(同じ入力なら同じ出力になる、§4.6)。

merge key優先順位 (Merged_Knowledge_Design.md §7.2の踏襲、「迷う場合は
無理に広くmergeしない」原則を適用):
1. sourceTimelineId がある場合、それをmerge keyにする
   (同じtimelineId同士は安全にmergeできるが、label/orderValueが
   食い違う場合はconflictとして記録する)
2. sourceTimelineId が無く、scope + kind + orderValue が明示されている
   場合、その組み合わせをmerge keyにする (orderField間の優先順位付けは
   しない、Extraction_Pipeline.md §4.8の方針を踏襲)
3. どちらも無ければ (temporal_marker等、labelのみの場合)、候補ごとに
   個別のunresolved entryとする。同じlabelだけでの広範な自動mergeはしない

自然文からの時系列推定 (「昔」「その後」「翌日」「回想」等) は行わない。
timeline順序矛盾検出 (contradiction detection) もまだ行わない。
EventCandidateとの高度な接続 (relatedEventIds解決) も行わない。

docs/architecture/06_AI/Merged_Knowledge_Design.md §7
"""

from __future__ import annotations

from typing import Any

from .entity_base import (
    aggregate_name_candidates,
    build_block_type_index,
    build_merged_evidence_refs,
    build_source_candidate,
    sanitize_id_segment,
)

MERGED_ENTITY_SCHEMA_VERSION = "0.1"
_ID_PREFIX = "TL"

_KIND_TIMELINE_ID = "id"
_KIND_UNRESOLVED = "unresolved"


def _format_order_value(order_value: float) -> str:
    if float(order_value).is_integer():
        return str(int(order_value))
    return str(order_value)


def _timeline_merge_key(candidate: dict[str, Any]) -> tuple[str, str]:
    timeline_id = candidate.get("sourceTimelineId")
    if timeline_id:
        return (_KIND_TIMELINE_ID, str(timeline_id))

    scope = candidate.get("scope")
    kind = candidate.get("kind")
    order_value = candidate.get("orderValue")
    if scope and kind and order_value is not None:
        return ("explicit", f"{scope}:{kind}:{_format_order_value(order_value)}")

    return (_KIND_UNRESOLVED, candidate["id"])


def _group_timeline_candidates(
    valid_entries: list[tuple[str, dict[str, Any]]],
) -> tuple[
    dict[tuple[str, str], list[tuple[dict[str, Any], str]]],
    list[tuple[str, str]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any] | None],
]:
    """全valid documentのTimelineCandidateをmerge keyでグルーピングする。"""
    groups: dict[tuple[str, str], list[tuple[dict[str, Any], str]]] = {}
    order: list[tuple[str, str]] = []
    documents_by_episode: dict[str, dict[str, Any]] = {}
    extraction_runs: dict[str, dict[str, Any] | None] = {}

    for _path, document in valid_entries:
        episode_id = document.get("episodeId")
        if episode_id and episode_id not in documents_by_episode:
            documents_by_episode[episode_id] = document
            extraction_runs[episode_id] = document.get("extractionRun")

        for candidate in document.get("timelineCandidates", []) or []:
            key = _timeline_merge_key(candidate)
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append((candidate, episode_id))

    return groups, order, documents_by_episode, extraction_runs


def _detect_order_value_conflict(
    candidates: list[dict[str, Any]],
) -> tuple[float | None, list[dict[str, Any]]]:
    """timelineIdベースのグループ内で、orderValueに食い違いがあれば
    conflictを1件返す (Merged_Knowledge_Design.md §9.8)。

    scope+kind+orderValueベースのグループはorderValue自体がmerge keyの
    一部のため、グループ内で食い違うことは構造的に起こらない
    (このチェックはtimelineIdベースのグループにのみ意味を持つ)。
    代表orderValueは最初に見つかった非null値。
    """
    order_values: list[float] = []
    for candidate in candidates:
        value = candidate.get("orderValue")
        if value is not None and value not in order_values:
            order_values.append(value)

    representative = order_values[0] if order_values else None
    conflicts: list[dict[str, Any]] = []
    if len(order_values) > 1:
        conflicts.append(
            {
                "conflictType": "timeline_conflict",
                "field": "orderValue",
                "values": order_values,
                "sourceCandidateIds": [c["id"] for c in candidates],
                "severity": "warning",
                "resolutionStatus": "unresolved",
                "selectedValue": representative,
            }
        )
    return representative, conflicts


def _resolve_timeline_identity(
    kind: str, key_value: str, unresolved_counter: int
) -> tuple[str, str | None, int]:
    """merge keyのkindから (entity_id, sourceTimelineId, 更新後の
    unresolved_counter) を決定する。

    Timelineは常にstatus: unresolved (Stage Bでは順序を確定しないため)。
    kind==timeline_idの場合のみ、raw sourceTimelineIdをsourceTimelineId
    フィールドへ保持する。
    """
    if kind == _KIND_TIMELINE_ID:
        entity_id = f"UNRESOLVED_{_ID_PREFIX}_ID_{sanitize_id_segment(key_value)}"
        return entity_id, key_value, unresolved_counter

    if kind == _KIND_UNRESOLVED:
        unresolved_counter += 1
        entity_id = f"UNRESOLVED_{_ID_PREFIX}_{unresolved_counter:04d}"
        return entity_id, None, unresolved_counter

    # "explicit" (scope+kind+orderValue): 値から決定的にIDを組み立てる
    entity_id = f"UNRESOLVED_{_ID_PREFIX}_{sanitize_id_segment(key_value)}"
    return entity_id, None, unresolved_counter


def _build_timeline_entity(
    key: tuple[str, str],
    members: list[tuple[dict[str, Any], str]],
    documents_by_episode: dict[str, dict[str, Any]],
    extraction_runs: dict[str, dict[str, Any] | None],
    block_index_cache: dict[str, tuple[dict[str, str], set[str]]],
    unresolved_counter: int,
) -> tuple[dict[str, Any] | None, int]:
    """1つのmerge keyグループからmerged timeline entryを組み立てる。

    Evidenceを1件も持たない場合は (None, unresolved_counter) を返す。
    """
    kind, key_value = key
    candidates = [c for c, _episode_id in members]

    evidence_refs: list[dict[str, Any]] = []
    source_candidates: list[dict[str, Any]] = []
    episode_ids_used: list[str] = []
    source_types: list[str] = []

    for candidate, episode_id in members:
        document = documents_by_episode[episode_id]
        if episode_id not in block_index_cache:
            block_index_cache[episode_id] = build_block_type_index(document)
        block_types, scene_ids = block_index_cache[episode_id]

        evidence_refs.extend(
            build_merged_evidence_refs(
                document,
                candidate.get("evidenceIds", []),
                episode_id,
                block_types,
                scene_ids,
            )
        )
        source_candidates.append(build_source_candidate(candidate, episode_id))

        if episode_id not in episode_ids_used:
            episode_ids_used.append(episode_id)

        source_type = candidate.get("sourceType")
        if source_type and source_type not in source_types:
            source_types.append(source_type)

    if not evidence_refs:
        # Evidenceを1件も持たない候補は出力しない
        # (Extraction_Pipeline.md §6.1と同じ原則)
        return None, unresolved_counter

    confidence = max((c.get("confidence") or 0.0) for c in candidates)
    label, aliases, conflicts = aggregate_name_candidates(
        candidates, conflict_field="label"
    )

    representative = candidates[0]
    order_value = representative.get("orderValue")
    if kind == _KIND_TIMELINE_ID:
        order_value, order_conflicts = _detect_order_value_conflict(candidates)
        conflicts.extend(order_conflicts)

    entity_id, source_timeline_id, unresolved_counter = _resolve_timeline_identity(
        kind, key_value, unresolved_counter
    )

    entity: dict[str, Any] = {
        "schemaVersion": MERGED_ENTITY_SCHEMA_VERSION,
        "id": entity_id,
        "type": "timeline_entry",
        "canonicalId": None,
        "mergedId": entity_id,
        "displayName": label,
        "aliases": aliases,
        "status": "unresolved",
        "kind": representative.get("kind"),
        "scope": representative.get("scope"),
        "orderValue": order_value,
        "orderField": representative.get("orderField"),
        "label": label,
        "markerType": representative.get("markerType"),
        "sourceTimelineId": source_timeline_id,
        "relativeTo": representative.get("relativeTo"),
        "relation": representative.get("relation"),
        "relatedEventIds": [],
        "sourceTypes": source_types,
        "confidence": confidence,
        "evidenceRefs": evidence_refs,
        "sourceCandidates": source_candidates,
        "extractionRunRefs": {
            episode_id: extraction_runs[episode_id]
            for episode_id in episode_ids_used
            if extraction_runs.get(episode_id) is not None
        },
        "fieldValues": {},
        "conflicts": conflicts,
        "manualOverridesApplied": [],
        "mergedFrom": list(episode_ids_used),
        "createdAt": None,
        "updatedAt": None,
    }
    return entity, unresolved_counter


def build_timeline_entities(
    valid_entries: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """複数episode_extractionのTimelineCandidateをmerged timeline entryへ
    変換する。

    Stage Bでは順序の確定 (canonicalization) を行わないため、生成される
    entryは常にstatus: unresolvedとする (Merged_Knowledge_Design.md §7.1)。
    relatedEventIdsの解決 (EventCandidateとの接続) は行わず常に空配列。
    """
    groups, order, documents_by_episode, extraction_runs = _group_timeline_candidates(
        valid_entries
    )

    block_index_cache: dict[str, tuple[dict[str, str], set[str]]] = {}
    entities: list[dict[str, Any]] = []
    unresolved_counter = 0

    for key in order:
        entity, unresolved_counter = _build_timeline_entity(
            key,
            groups[key],
            documents_by_episode,
            extraction_runs,
            block_index_cache,
            unresolved_counter,
        )
        if entity is not None:
            entities.append(entity)

    return entities
