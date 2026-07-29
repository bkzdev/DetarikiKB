"""
DKB Merger - Event Entity Merge
Stage A EventCandidateから Stage B merged event を組み立てる。

merge key優先順位:
1. existingEventId -> canonical IDとして自動merge
2. 無ければ、候補ごとに個別のunresolved entityとする
   (eventNameのみでの自動マージは行わない)

participantCandidates/locationCandidatesは、型別のcandidate ID -> merged
entity ID対応表 (Merged_Knowledge_Design.md §10.2) で解決し、
participantEntityIds/locationEntityIdsへ初出順・重複なしで集約する。
未解決・型違い参照はEvent全体を破棄せずwarningへ元値を保持する。
"""

from __future__ import annotations

from typing import Any

from .entity_base import build_merged_entities

UNRESOLVED_EVENT_REFERENCE_MARKER = (
    "を対応するmerged entityへ解決できなかったためEvent参照から除外しました"
)
EVENT_REFERENCE_TYPE_MISMATCH_MARKER = (
    "は参照先typeが一致しないためEvent参照から除外しました"
)


def _event_merge_key(candidate: dict[str, Any]) -> tuple[str, str]:
    existing_id = candidate.get("existingEventId")
    if existing_id:
        return ("id", existing_id)
    return ("unresolved", candidate["id"])


def _build_reference_index(
    entities: list[dict[str, Any]] | None,
) -> tuple[set[str], dict[str, str]]:
    """同一typeのmerged entity群から、entity ID集合と
    Stage A candidate ID -> merged entity ID対応表を作る。

    participantとlocationで別々に呼び出し、型違いのcandidate IDを
    誤解決しないための境界とする。
    """
    entity_ids: set[str] = set()
    candidate_id_to_entity_id: dict[str, str] = {}

    for entity in entities or []:
        entity_ids.add(entity["id"])
        for source_candidate in entity.get("sourceCandidates", []) or []:
            candidate_id_to_entity_id[source_candidate["candidateId"]] = entity["id"]

    return entity_ids, candidate_id_to_entity_id


def _resolve_reference(
    raw: str | None,
    entity_ids: set[str],
    candidate_id_to_entity_id: dict[str, str],
) -> str | None:
    """candidate IDまたは既に構築済みのtyped entity IDを解決する。"""
    if not raw:
        return None
    if raw in candidate_id_to_entity_id:
        return candidate_id_to_entity_id[raw]
    if raw in entity_ids:
        return raw
    return None


def _reference_exists(raw: str | None, reference_types: dict[str, set[str]]) -> bool:
    return bool(raw and raw in reference_types)


def _build_reference_type_index(
    entities: list[dict[str, Any]] | None,
) -> dict[str, set[str]]:
    """既知entity ID/candidate IDごとのentity type集合を作る。

    expected typeの解決には専用indexを使い、このindexは解決できなかった値が
    他typeに既知かどうかの診断だけに使う。
    """
    reference_types: dict[str, set[str]] = {}
    for entity in entities or []:
        entity_type = entity.get("type", "unknown")
        reference_types.setdefault(entity["id"], set()).add(entity_type)
        for source_candidate in entity.get("sourceCandidates", []) or []:
            reference_types.setdefault(source_candidate["candidateId"], set()).add(
                entity_type
            )
    return reference_types


def _resolve_event_references(
    candidates: list[dict[str, Any]],
    *,
    candidate_field: str,
    expected_type: str,
    entity_ids: set[str],
    candidate_id_to_entity_id: dict[str, str],
    reference_types: dict[str, set[str]],
    episode_by_candidate_id: dict[str, str],
    warnings: list[str],
) -> list[str]:
    """EventCandidate内の参照をtyped merged entity IDへ解決する。

    解決済み参照はcandidateの入力順を維持して重複排除する。未解決または
    別typeにだけ存在する参照は元値付きwarningへ残し、他の正しい参照と
    Event entity自体の生成は継続する。
    """
    resolved_ids: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        candidate_id = candidate["id"]
        episode_id = episode_by_candidate_id.get(candidate_id, "unknown")
        for raw in candidate.get(candidate_field, []) or []:
            resolved = _resolve_reference(raw, entity_ids, candidate_id_to_entity_id)
            if resolved is not None:
                if resolved not in seen:
                    seen.add(resolved)
                    resolved_ids.append(resolved)
                continue

            if _reference_exists(raw, reference_types):
                actual_types = ",".join(sorted(reference_types[raw]))
                warnings.append(
                    f"{episode_id}/{candidate_id}: {candidate_field} reference "
                    f"({raw!r}) {EVENT_REFERENCE_TYPE_MISMATCH_MARKER} "
                    f"(expectedType={expected_type}, actualTypes={actual_types})"
                )
            else:
                warnings.append(
                    f"{episode_id}/{candidate_id}: {candidate_field} reference "
                    f"({raw!r}) {UNRESOLVED_EVENT_REFERENCE_MARKER} "
                    f"(expectedType={expected_type})"
                )

    return resolved_ids


def build_event_entities(
    valid_entries: list[tuple[str, dict[str, Any]]],
    *,
    character_entities: list[dict[str, Any]] | None = None,
    location_entities: list[dict[str, Any]] | None = None,
    known_entities: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
) -> list[dict[str, Any]]:
    """EventCandidateをmerged eventへ変換し、typed参照を解決する。

    戻り値のlist APIは既存callerとの互換性を維持する。MergeEngineは
    character_entities/location_entitiesとwarning collectorを渡し、
    participantCandidates/locationCandidatesを型別に解決する。
    """
    character_entity_ids, character_candidate_map = _build_reference_index(
        character_entities
    )
    location_entity_ids, location_candidate_map = _build_reference_index(
        location_entities
    )
    reference_types = _build_reference_type_index(
        known_entities
        if known_entities is not None
        else [*(character_entities or []), *(location_entities or [])]
    )
    warning_sink = warnings if warnings is not None else []

    episode_by_candidate_id: dict[str, str] = {}
    for _path, document in valid_entries:
        episode_id = document.get("episodeId", "unknown")
        for candidate in document.get("events", []) or []:
            episode_by_candidate_id[candidate["id"]] = episode_id

    def _event_reference_fields(candidates: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "participantEntityIds": _resolve_event_references(
                candidates,
                candidate_field="participantCandidates",
                expected_type="character",
                entity_ids=character_entity_ids,
                candidate_id_to_entity_id=character_candidate_map,
                reference_types=reference_types,
                episode_by_candidate_id=episode_by_candidate_id,
                warnings=warning_sink,
            ),
            "locationEntityIds": _resolve_event_references(
                candidates,
                candidate_field="locationCandidates",
                expected_type="location",
                entity_ids=location_entity_ids,
                candidate_id_to_entity_id=location_candidate_map,
                reference_types=reference_types,
                episode_by_candidate_id=episode_by_candidate_id,
                warnings=warning_sink,
            ),
        }

    return build_merged_entities(
        valid_entries,
        candidate_array_key="events",
        entity_type="event",
        id_prefix="EVENT",
        merge_key_fn=_event_merge_key,
        extra_fields_fn=_event_reference_fields,
    )
