"""
DKB Merger - Relationship Entity Merge
Stage A RelationshipCandidateから Stage B merged relationship を組み立てる。

Character/Location/Organization/Item/Lore/Eventのentity_base.pyパターン
(build_merged_entities) とは異なり、Relationshipは専用実装とする。理由:
- merge keyが単一値ではなく (sourceEntityId, targetEntityId,
  relationshipType, direction) の4値組であること
- source/targetの解決に、既に構築済みの他entityのsourceCandidates/idを
  参照する必要があること (candidate ID -> merged entity ID解決)
- 解決できない候補は「個別unresolved entity」にせず、そもそも生成しない
  こと (Merged_Knowledge_Design.md §6.1: 両端解決済みのみ昇格させる方針を
  踏襲。ファイルベースの_unresolved/への振り分けはまだ実装しないため、
  未解決分はreport.warningsへ記録するのみ)

自然文からの関係推定は行わない。relationshipTypeは自由文字列のまま扱い、
taxonomyの最終確定 (docs/architecture/04_Knowledge_Graph/Relationships.md)
もまだ行わない。

docs/architecture/06_AI/Merged_Knowledge_Design.md §6
"""

from __future__ import annotations

import re
from typing import Any

from .entity_base import (
    build_block_type_index,
    build_merged_evidence_refs,
    build_source_candidate,
)

MERGED_ENTITY_SCHEMA_VERSION = "0.1"
_UNRESOLVED_PREFIX = "UNRESOLVED_"


def _sanitize_id_segment(text: str) -> str:
    """relationshipType等の自由文字列を、IdStringパターン
    (^[A-Z][A-Z0-9_-]+$) に沿うID断片へ変換する。relationshipTypeフィールド
    自体は自由文字列のまま保持し、ID組み立てにのみ使う。
    """
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()
    return sanitized or "UNKNOWN"


def _build_reference_index(
    known_entities: list[dict[str, Any]],
) -> tuple[set[str], dict[str, str]]:
    """既存merged entity群 (Character/Location/Organization/Item/Lore/Event)
    から、既知entity idの集合とStage A candidate id -> merged entity id
    の対応表を作る (Merged_Knowledge_Design.md §10.2 candidate対応表の簡易版)。
    """
    entity_ids: set[str] = set()
    candidate_id_to_entity_id: dict[str, str] = {}

    for entity in known_entities:
        entity_ids.add(entity["id"])
        for source_candidate in entity.get("sourceCandidates", []):
            candidate_id_to_entity_id[source_candidate["candidateId"]] = entity["id"]

    return entity_ids, candidate_id_to_entity_id


def _resolve_reference(
    raw: str | None,
    entity_ids: set[str],
    candidate_id_to_entity_id: dict[str, str],
) -> str | None:
    """RelationshipCandidateのsourceCandidate/targetCandidateをmerged
    entity IDへ解決する。

    優先順位:
    1. Stage A candidate id (sourceCandidates経由で解決済みのentityへ)
    2. 既にmerged entity idそのもの (構造化ID解決結果と一致する値)
    解決できなければNoneを返す (名前だけの場合等、無理に確定しない)。
    """
    if not raw:
        return None
    if raw in candidate_id_to_entity_id:
        return candidate_id_to_entity_id[raw]
    if raw in entity_ids:
        return raw
    return None


def _record_endpoint_conflicts(entities: list[dict[str, Any]]) -> None:
    """同一 (sourceEntityId, targetEntityId) に対して異なる
    (relationshipType, direction) の組み合わせが複数観測された場合、
    各entityのconflictsへwarningとして記録する (Merged_Knowledge_Design.md
    §9.7)。高度な自動解決 (どちらが正しいかの判定) は行わない。
    """
    pairs: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entity in entities:
        pair_key = (entity["sourceEntityId"], entity["targetEntityId"])
        pairs.setdefault(pair_key, []).append(entity)

    for group_entities in pairs.values():
        if len(group_entities) <= 1:
            continue
        distinct_combos = sorted(
            {(e["relationshipType"], e["direction"]) for e in group_entities}
        )
        if len(distinct_combos) <= 1:
            continue

        all_candidate_ids = [
            sc["candidateId"]
            for e in group_entities
            for sc in e.get("sourceCandidates", [])
        ]
        for entity in group_entities:
            selected_value = f"{entity['relationshipType']}/{entity['direction']}"
            entity["conflicts"].append(
                {
                    "conflictType": "relationship_conflict",
                    "field": "relationshipType",
                    "values": [f"{t}/{d}" for t, d in distinct_combos],
                    "sourceCandidateIds": all_candidate_ids,
                    "severity": "warning",
                    "resolutionStatus": "unresolved",
                    "selectedValue": selected_value,
                }
            )


def _group_relationship_candidates(
    valid_entries: list[tuple[str, dict[str, Any]]],
    entity_ids: set[str],
    candidate_id_to_entity_id: dict[str, str],
) -> tuple[
    dict[tuple[str, str, str, str], list[tuple[dict[str, Any], str]]],
    list[tuple[str, str, str, str]],
    list[str],
]:
    """全valid documentのRelationshipCandidateを、(sourceEntityId,
    targetEntityId, relationshipType, direction) のmerge keyでグルーピングする。

    relationshipTypeが空の候補、source/targetを解決できない候補は
    グルーピングせず、warningsへ理由を記録する (無理に確定しない)。
    """
    groups: dict[tuple[str, str, str, str], list[tuple[dict[str, Any], str]]] = {}
    order: list[tuple[str, str, str, str]] = []
    warnings: list[str] = []

    for _path, document in valid_entries:
        episode_id = document.get("episodeId")
        for candidate in document.get("relationships", []) or []:
            candidate_id = candidate.get("id")
            relationship_type = candidate.get("relationshipType")
            direction = candidate.get("direction")

            if not relationship_type or not relationship_type.strip():
                warnings.append(
                    f"{episode_id}/{candidate_id}: relationshipTypeが空のため"
                    "relationship mergeをskipしました"
                )
                continue

            source_ref = candidate.get("sourceCandidate")
            target_ref = candidate.get("targetCandidate")
            source_entity_id = _resolve_reference(
                source_ref, entity_ids, candidate_id_to_entity_id
            )
            target_entity_id = _resolve_reference(
                target_ref, entity_ids, candidate_id_to_entity_id
            )

            if source_entity_id is None or target_entity_id is None:
                unresolved_field = (
                    "sourceCandidate" if source_entity_id is None else "targetCandidate"
                )
                unresolved_value = (
                    source_ref if source_entity_id is None else target_ref
                )
                warnings.append(
                    f"{episode_id}/{candidate_id}: {unresolved_field} "
                    f"('{unresolved_value}') をmerged entityへ解決できなかった"
                    "ためrelationship mergeをskipしました"
                )
                continue

            key = (source_entity_id, target_entity_id, relationship_type, direction)
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append((candidate, episode_id))

    return groups, order, warnings


def _build_relationship_entity(
    key: tuple[str, str, str, str],
    members: list[tuple[dict[str, Any], str]],
    documents_by_episode: dict[str, dict[str, Any]],
    extraction_runs: dict[str, dict[str, Any] | None],
    block_index_cache: dict[str, tuple[dict[str, str], set[str]]],
) -> dict[str, Any] | None:
    """1つのmerge keyグループからmerged relationship entityを組み立てる。

    Evidenceを1件も持たない場合はNoneを返す (呼び出し側で出力しない)。
    """
    source_entity_id, target_entity_id, relationship_type, direction = key
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
        return None

    confidence = max((c.get("confidence") or 0.0) for c in candidates)

    is_canonical = not source_entity_id.startswith(
        _UNRESOLVED_PREFIX
    ) and not target_entity_id.startswith(_UNRESOLVED_PREFIX)
    type_segment = _sanitize_id_segment(relationship_type)
    entity_id = f"REL_{source_entity_id}_{type_segment}_{target_entity_id}"
    canonical_id = entity_id if is_canonical else None
    merged_id = None if is_canonical else entity_id
    status = "merged" if is_canonical else "unresolved"

    return {
        "schemaVersion": MERGED_ENTITY_SCHEMA_VERSION,
        "id": entity_id,
        "type": "relationship",
        "canonicalId": canonical_id,
        "mergedId": merged_id,
        "displayName": None,
        "aliases": [],
        "status": status,
        "sourceEntityId": source_entity_id,
        "targetEntityId": target_entity_id,
        "relationshipType": relationship_type,
        "direction": direction,
        "temporalNote": None,
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
        "conflicts": [],
        "manualOverridesApplied": [],
        "mergedFrom": list(episode_ids_used),
        "createdAt": None,
        "updatedAt": None,
    }


def build_relationship_entities(
    valid_entries: list[tuple[str, dict[str, Any]]],
    known_entities: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """複数episode_extractionのRelationshipCandidateをmerged relationshipへ
    変換する。

    known_entitiesは、既にmerge済みのCharacter/Location/Organization/Item/
    Lore/Eventのentity一覧 (source/target解決の参照元。呼び出し側で先に
    構築しておく必要がある)。

    戻り値: (merged relationshipのリスト, 解決できなかった候補の警告一覧)。
    source/targetのどちらかが解決できない候補、relationshipTypeが空の候補は
    relationshipを生成せず、警告として記録する
    (Merged_Knowledge_Design.md §6.1: 両端解決済みのみ昇格)。
    """
    entity_ids, candidate_id_to_entity_id = _build_reference_index(known_entities)

    documents_by_episode: dict[str, dict[str, Any]] = {}
    extraction_runs: dict[str, dict[str, Any] | None] = {}
    for _path, document in valid_entries:
        episode_id = document.get("episodeId")
        if episode_id and episode_id not in documents_by_episode:
            documents_by_episode[episode_id] = document
            extraction_runs[episode_id] = document.get("extractionRun")

    groups, order, warnings = _group_relationship_candidates(
        valid_entries, entity_ids, candidate_id_to_entity_id
    )

    block_index_cache: dict[str, tuple[dict[str, str], set[str]]] = {}
    entities: list[dict[str, Any]] = []

    for key in order:
        entity = _build_relationship_entity(
            key, groups[key], documents_by_episode, extraction_runs, block_index_cache
        )
        if entity is not None:
            entities.append(entity)

    _record_endpoint_conflicts(entities)

    return entities, warnings
