"""
DKB Merger - Relationship Entity Merge
Stage A RelationshipCandidateから Stage B merged relationship を組み立てる。

Character/Location/Organization/Item/Lore/Eventのentity_base.pyパターン
(build_merged_entities) とは異なり、Relationshipは専用実装とする。理由:
- merge keyが単一値ではなくsource/target/type/sourceType/directionの5値組であること
- sourceTypeとdirectionをmerge keyへ含め、fact/inferenceや方向矛盾を
  自動的に混ぜないこと
- source/targetの解決に、既に構築済みの他entityのsourceCandidates/idを
  参照する必要があること (candidate ID -> merged entity ID解決)
- 解決できない候補はmerged entityにせず、根拠付きreview recordへ保持すること

自然文からの関係推定は行わない。relationshipTypeは自由文字列のまま扱い、
公開v1 taxonomy (docs/architecture/04_Knowledge_Graph/Relationships.md) に従う。
表記ゆれ (大文字小文字・区切り文字) だけを
relationship_taxonomy.pyのnormalize_relationship_typeでmerge key用に
正規化する。entity.relationshipType自体は元の表記を保持し、正規化結果は
fieldValuesへ追加情報として持たせるのみ (§6.3)。

docs/architecture/06_AI/Merged_Knowledge_Design.md §6
"""

from __future__ import annotations

from typing import Any

from agents.extractor.models import RELATIONSHIP_CANDIDATE_VALID_DIRECTIONS

from .entity_base import (
    build_block_type_index,
    build_merged_evidence_refs,
    build_source_candidate,
    sanitize_id_segment,
)
from .relationship_taxonomy import (
    FORMAL_V1_RELATIONSHIP_TYPES,
    TAXONOMY_PROVISIONAL,
    TAXONOMY_UNRECOGNIZED,
    NormalizedRelationshipType,
    normalize_relationship_type,
)

MERGED_ENTITY_SCHEMA_VERSION = "0.1"
_UNRESOLVED_PREFIX = "UNRESOLVED_"
_FIXED_SOURCE_TO_TARGET_TYPES = frozenset({"member_of", "affiliated_with"})
_PUBLIC_SOURCE_TYPES = frozenset({"script", "manual"})
PUBLICATION_ELIGIBLE = "eligible"
PUBLICATION_REVIEW_REQUIRED = "review_required"

# source/targetのどちらかを解決できずrelationship mergeをskipした際の警告文言
# に必ず含まれるマーカー文字列。report.warningCounts.unresolvedRelationships
# (agents/merger/engine.py) の集計で、この文字列を含む警告だけを数えるために
# 公開する (文言自体は変更しない。既存warningsのテキストと完全一致させる)。
UNRESOLVED_ENDPOINT_MARKER = (
    "をmerged entityへ解決できなかったためrelationship mergeをskipしました"
)
INVALID_DIRECTION_MARKER = "は未対応のdirectionのためrelationship mergeをskipしました"
FIXED_DIRECTION_MARKER = (
    "はsource_to_target固定のrelationshipTypeに反するため"
    "relationshipをreview対象として保持しました"
)


def _build_reference_index(
    known_entities: list[dict[str, Any]],
) -> tuple[set[str], dict[str, str], dict[str, str | None]]:
    """既存merged entity群 (Character/Location/Organization/Item/Lore/Event)
    から、既知entity idの集合とStage A candidate id -> merged entity id
    の対応表を作る (Merged_Knowledge_Design.md §10.2 candidate対応表の簡易版)。
    """
    entity_ids: set[str] = set()
    candidate_id_to_entity_id: dict[str, str] = {}
    entity_types: dict[str, str | None] = {}

    for entity in known_entities:
        entity_ids.add(entity["id"])
        entity_types[entity["id"]] = entity.get("type")
        for source_candidate in entity.get("sourceCandidates", []):
            candidate_id_to_entity_id[source_candidate["candidateId"]] = entity["id"]

    return entity_ids, candidate_id_to_entity_id, entity_types


def _append_review_record(
    review_records: list[dict[str, Any]] | None,
    *,
    candidate: dict[str, Any],
    episode_id: str | None,
    normalized: NormalizedRelationshipType | None,
    reasons: list[str],
    source_entity_id: str | None = None,
    target_entity_id: str | None = None,
    source_entity_type: str | None = None,
    target_entity_type: str | None = None,
) -> None:
    """RelationshipCandidateを、重複理由をまとめたreview recordへ保持する。"""
    if review_records is None:
        return
    review_records.append(
        {
            "episodeId": episode_id,
            "candidateId": candidate.get("id"),
            "reasons": list(dict.fromkeys(reasons)),
            "relationshipType": candidate.get("relationshipType"),
            "normalizedRelationshipType": (
                normalized.normalized_value if normalized is not None else None
            ),
            "taxonomyState": (
                normalized.taxonomy_state if normalized is not None else None
            ),
            "suggestedType": (
                normalized.suggested_type if normalized is not None else None
            ),
            "direction": candidate.get("direction"),
            "sourceType": candidate.get("sourceType"),
            "confidence": candidate.get("confidence"),
            "sourceCandidate": candidate.get("sourceCandidate"),
            "targetCandidate": candidate.get("targetCandidate"),
            "sourceEntityId": source_entity_id,
            "targetEntityId": target_entity_id,
            "sourceEntityType": source_entity_type,
            "targetEntityType": target_entity_type,
            "evidenceIds": list(candidate.get("evidenceIds", [])),
            "extractionRun": candidate.get("extractionRun"),
        }
    )


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


def _record_endpoint_conflicts(
    entities: list[dict[str, Any]],
    review_records: list[dict[str, Any]] | None,
) -> None:
    """同一 (sourceEntityId, targetEntityId) に対して異なる
    (relationshipType, direction) の組み合わせが複数観測された場合、
    各entityのconflictsへwarningとして記録する (Merged_Knowledge_Design.md
    §9.7)。同一normalized relationshipType内のdirection競合はentity構築時に
    1件へ統合済みなので、ここでは主にtype違いのentity間競合を扱う。
    高度な自動解決 (どのrelationshipTypeが正しいかの判定) は行わない。
    """
    pairs: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entity in entities:
        pair_key = (entity["sourceEntityId"], entity["targetEntityId"])
        pairs.setdefault(pair_key, []).append(entity)

    for group_entities in pairs.values():
        if len(group_entities) <= 1:
            continue
        distinct_combos = sorted(
            {(e["normalizedRelationshipType"], e["direction"]) for e in group_entities}
        )
        if len(distinct_combos) <= 1:
            continue

        distinct_types = {item[0] for item in distinct_combos}
        distinct_directions = {item[1] for item in distinct_combos}
        conflict_field = "direction" if len(distinct_types) == 1 else "relationshipType"
        review_reason = (
            "direction_conflict"
            if len(distinct_types) == 1 and len(distinct_directions) > 1
            else "endpoint_relationship_conflict"
        )
        all_candidate_ids = [
            sc["candidateId"]
            for e in group_entities
            for sc in e.get("sourceCandidates", [])
        ]
        for entity in group_entities:
            entity["publicationStatus"] = PUBLICATION_REVIEW_REQUIRED
            selected_value = f"{entity['relationshipType']}/{entity['direction']}"
            entity["conflicts"].append(
                {
                    "conflictType": "relationship_conflict",
                    "field": conflict_field,
                    "values": [f"{t}/{d}" for t, d in distinct_combos],
                    "sourceCandidateIds": all_candidate_ids,
                    "severity": "warning",
                    "resolutionStatus": "unresolved",
                    "selectedValue": selected_value,
                }
            )
            if review_records is not None:
                for source_candidate in entity.get("sourceCandidates", []):
                    episode_id = source_candidate.get("episodeId")
                    review_records.append(
                        {
                            "episodeId": episode_id,
                            "candidateId": source_candidate.get("candidateId"),
                            "reasons": [review_reason],
                            "relationshipType": entity.get("relationshipType"),
                            "normalizedRelationshipType": entity.get(
                                "normalizedRelationshipType"
                            ),
                            "taxonomyState": entity.get("taxonomyState"),
                            "suggestedType": None,
                            "direction": entity.get("direction"),
                            "sourceType": entity.get("sourceType"),
                            "confidence": source_candidate.get("confidence"),
                            "sourceCandidate": None,
                            "targetCandidate": None,
                            "sourceEntityId": entity.get("sourceEntityId"),
                            "targetEntityId": entity.get("targetEntityId"),
                            "sourceEntityType": entity.get("sourceEntityType"),
                            "targetEntityType": entity.get("targetEntityType"),
                            "evidenceIds": list(
                                source_candidate.get("evidenceIds", [])
                            ),
                            "extractionRun": entity.get("extractionRunRefs", {}).get(
                                episode_id
                            ),
                        }
                    )


def _classify_candidate_for_review(
    *,
    candidate: dict[str, Any],
    episode_id: str | None,
    normalized: NormalizedRelationshipType | None,
    source_entity_id: str | None,
    target_entity_id: str | None,
    source_entity_type: str | None,
    target_entity_type: str | None,
) -> tuple[list[str], list[str]]:
    """公開v1契約に照らしたreview理由と互換用warningを返す。"""
    candidate_id = candidate.get("id")
    relationship_type = candidate.get("relationshipType")
    direction = candidate.get("direction")
    reasons: list[str] = []
    warnings: list[str] = []

    if (
        not isinstance(direction, str)
        or direction not in RELATIONSHIP_CANDIDATE_VALID_DIRECTIONS
    ):
        reasons.append("invalid_direction")
        warnings.append(
            f"{episode_id}/{candidate_id}: direction ({direction!r}) "
            f"{INVALID_DIRECTION_MARKER}"
        )
    if normalized is None:
        reasons.append("empty_relationship_type")
        warnings.append(
            f"{episode_id}/{candidate_id}: relationshipTypeが空のため"
            "relationship mergeをskipしました"
        )
    else:
        if normalized.taxonomy_state == TAXONOMY_PROVISIONAL:
            reasons.append("provisional_type")
        elif normalized.taxonomy_state == TAXONOMY_UNRECOGNIZED:
            reasons.append("unrecognized_type")
        if normalized.suggested_type is not None:
            reasons.append("semantic_alias")
        if (
            normalized.normalized_value in _FIXED_SOURCE_TO_TARGET_TYPES
            and direction != "source_to_target"
        ):
            reasons.append("invalid_formal_direction")
            warnings.append(
                f"{episode_id}/{candidate_id}: {relationship_type} direction "
                f"({direction!r}) {FIXED_DIRECTION_MARKER}"
            )
        if (
            normalized.normalized_value in FORMAL_V1_RELATIONSHIP_TYPES
            and source_entity_id is not None
            and target_entity_id is not None
            and (
                source_entity_type != "character"
                or target_entity_type != "organization"
            )
        ):
            reasons.append("endpoint_type_mismatch")

    if source_entity_id is None or target_entity_id is None:
        reasons.append("unresolved_endpoint")
        unresolved_field = (
            "sourceCandidate" if source_entity_id is None else "targetCandidate"
        )
        unresolved_value = candidate.get(unresolved_field)
        warnings.append(
            f"{episode_id}/{candidate_id}: {unresolved_field} "
            f"('{unresolved_value}') {UNRESOLVED_ENDPOINT_MARKER}"
        )
    if candidate.get("sourceType") not in _PUBLIC_SOURCE_TYPES:
        reasons.append("non_public_source_type")

    return reasons, warnings


def _group_relationship_candidates(
    valid_entries: list[tuple[str, dict[str, Any]]],
    entity_ids: set[str],
    candidate_id_to_entity_id: dict[str, str],
    entity_types: dict[str, str | None],
    review_records: list[dict[str, Any]] | None,
) -> tuple[
    dict[
        tuple[str, str, str, str, str],
        list[tuple[dict[str, Any], str, NormalizedRelationshipType]],
    ],
    list[tuple[str, str, str, str, str]],
    list[str],
]:
    """候補をsourceType・directionを分離した安全なmerge keyへまとめる。"""
    groups: dict[
        tuple[str, str, str, str, str],
        list[tuple[dict[str, Any], str, NormalizedRelationshipType]],
    ] = {}
    order: list[tuple[str, str, str, str, str]] = []
    warnings: list[str] = []

    for _path, document in valid_entries:
        episode_id = document.get("episodeId")
        for candidate in document.get("relationships", []) or []:
            relationship_type = candidate.get("relationshipType")
            direction = candidate.get("direction")
            source_type = candidate.get("sourceType")
            reasons: list[str] = []

            normalized = (
                normalize_relationship_type(relationship_type)
                if isinstance(relationship_type, str) and relationship_type.strip()
                else None
            )

            source_ref = candidate.get("sourceCandidate")
            target_ref = candidate.get("targetCandidate")
            source_entity_id = _resolve_reference(
                source_ref, entity_ids, candidate_id_to_entity_id
            )
            target_entity_id = _resolve_reference(
                target_ref, entity_ids, candidate_id_to_entity_id
            )
            source_entity_type = entity_types.get(source_entity_id)
            target_entity_type = entity_types.get(target_entity_id)

            reasons, candidate_warnings = _classify_candidate_for_review(
                candidate=candidate,
                episode_id=episode_id,
                normalized=normalized,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                source_entity_type=source_entity_type,
                target_entity_type=target_entity_type,
            )
            warnings.extend(candidate_warnings)

            _append_review_record(
                review_records,
                candidate=candidate,
                episode_id=episode_id,
                normalized=normalized,
                reasons=reasons,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                source_entity_type=source_entity_type,
                target_entity_type=target_entity_type,
            )

            if (
                normalized is None
                or source_entity_id is None
                or target_entity_id is None
                or not isinstance(direction, str)
                or direction not in RELATIONSHIP_CANDIDATE_VALID_DIRECTIONS
            ):
                continue

            key = (
                source_entity_id,
                target_entity_id,
                normalized.normalized_value,
                source_type,
                direction,
            )
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append((candidate, episode_id, normalized))

    return groups, order, warnings


def _build_relationship_entity(
    key: tuple[str, str, str, str, str],
    members: list[tuple[dict[str, Any], str, NormalizedRelationshipType]],
    documents_by_episode: dict[str, dict[str, Any]],
    extraction_runs: dict[str, dict[str, Any] | None],
    block_index_cache: dict[str, tuple[dict[str, str], set[str]]],
    entity_types: dict[str, str | None],
) -> dict[str, Any] | None:
    """1つのmerge keyグループからmerged relationship entityを組み立てる。

    Evidenceを1件も持たない場合はNoneを返す (呼び出し側で出力しない)。

    entity.relationshipTypeは、グループ内で最初に観測された元の表記
    (originalValue) をそのまま保持する (自由文字列として書き換えない、
    §6.3の既存方針・既存テストとの互換性を優先)。merge keyに使った
    正規化後の値 (normalizedValue) と、グループ内で観測された全ての
    元表記は fieldValues.relationshipTypeNormalization /
    fieldValues.originalRelationshipTypes へ保持する。

    sourceTypeとdirectionはmerge keyに含まれるため、異なる分類や方向の根拠を
    1 entityへ混ぜない。
    """
    (
        source_entity_id,
        target_entity_id,
        normalized_relationship_type,
        source_type,
        direction,
    ) = key
    candidates = [c for c, _episode_id, _normalized in members]

    evidence_refs: list[dict[str, Any]] = []
    source_candidates: list[dict[str, Any]] = []
    episode_ids_used: list[str] = []
    original_relationship_types: list[str] = []
    normalization_warnings: list[str] = []

    for candidate, episode_id, normalized in members:
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

        if normalized.original_value not in original_relationship_types:
            original_relationship_types.append(normalized.original_value)
        for warning in normalized.warnings:
            if warning not in normalization_warnings:
                normalization_warnings.append(warning)

    if not evidence_refs:
        # Evidenceを1件も持たない候補は出力しない
        # (Extraction_Pipeline.md §6.1と同じ原則)
        return None

    confidence = max((c.get("confidence") or 0.0) for c in candidates)
    # グループ内の全candidateは同じmerge key (=同じnormalized_value) を
    # 共有するため、isKnownもグループ内で一貫している。代表値として先頭を使う。
    normalization = members[0][2]
    is_known = normalization.is_known
    taxonomy_state = normalization.taxonomy_state
    representative_relationship_type = original_relationship_types[0]
    source_entity_type = entity_types.get(source_entity_id)
    target_entity_type = entity_types.get(target_entity_id)

    is_canonical = not source_entity_id.startswith(
        _UNRESOLVED_PREFIX
    ) and not target_entity_id.startswith(_UNRESOLVED_PREFIX)
    type_segment = sanitize_id_segment(normalized_relationship_type)
    source_type_segment = sanitize_id_segment(source_type)
    direction_segment = sanitize_id_segment(direction)
    entity_id = (
        f"REL_{source_entity_id}_{type_segment}_{target_entity_id}_"
        f"{source_type_segment}_{direction_segment}"
    )
    canonical_id = entity_id if is_canonical else None
    merged_id = None if is_canonical else entity_id
    status = "merged" if is_canonical else "unresolved"
    publication_status = (
        PUBLICATION_ELIGIBLE
        if taxonomy_state == "formal_v1"
        and source_type in _PUBLIC_SOURCE_TYPES
        and direction == "source_to_target"
        and source_entity_type == "character"
        and target_entity_type == "organization"
        else PUBLICATION_REVIEW_REQUIRED
    )

    entity = {
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
        "sourceEntityType": source_entity_type,
        "targetEntityType": target_entity_type,
        "relationshipType": representative_relationship_type,
        "normalizedRelationshipType": normalized_relationship_type,
        "taxonomyState": taxonomy_state,
        "direction": direction,
        "sourceType": source_type,
        "publicationStatus": publication_status,
        "temporalNote": None,
        "sourceTypes": [source_type],
        "confidence": confidence,
        "evidenceRefs": evidence_refs,
        "sourceCandidates": source_candidates,
        "extractionRunRefs": {
            episode_id: extraction_runs[episode_id]
            for episode_id in episode_ids_used
            if extraction_runs.get(episode_id) is not None
        },
        "fieldValues": {
            "originalRelationshipTypes": {
                "value": original_relationship_types,
                "sourceType": source_type,
                "confidence": confidence,
            },
            "relationshipTypeNormalization": {
                "value": {
                    "normalizedValue": normalized_relationship_type,
                    "isKnown": is_known,
                    "taxonomyState": taxonomy_state,
                    "suggestedType": normalization.suggested_type,
                    "warnings": normalization_warnings,
                },
                "sourceType": source_type,
                "confidence": confidence,
            },
        },
        "conflicts": [],
        "manualOverridesApplied": [],
        "mergedFrom": list(episode_ids_used),
        "createdAt": None,
        "updatedAt": None,
    }
    return entity


def build_relationship_entities(
    valid_entries: list[tuple[str, dict[str, Any]]],
    known_entities: list[dict[str, Any]],
    review_records: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """複数episode_extractionのRelationshipCandidateをmerged relationshipへ
    変換する。

    known_entitiesは、既にmerge済みのCharacter/Location/Organization/Item/
    Lore/Eventのentity一覧 (source/target解決の参照元。呼び出し側で先に
    構築しておく必要がある)。

    戻り値: (merged relationshipのリスト, 互換用warning一覧)。
    review_recordsを渡した場合、公開不可・要確認候補を根拠付きで追記する。
    source/targetのどちらかが解決できない候補、relationshipTypeが空の候補は
    relationshipを生成せず、警告として記録する
    (Merged_Knowledge_Design.md §6.1: 両端解決済みのみ昇格)。
    """
    entity_ids, candidate_id_to_entity_id, entity_types = _build_reference_index(
        known_entities
    )

    documents_by_episode: dict[str, dict[str, Any]] = {}
    extraction_runs: dict[str, dict[str, Any] | None] = {}
    for _path, document in valid_entries:
        episode_id = document.get("episodeId")
        if episode_id and episode_id not in documents_by_episode:
            documents_by_episode[episode_id] = document
            extraction_runs[episode_id] = document.get("extractionRun")

    groups, order, warnings = _group_relationship_candidates(
        valid_entries,
        entity_ids,
        candidate_id_to_entity_id,
        entity_types,
        review_records,
    )

    block_index_cache: dict[str, tuple[dict[str, str], set[str]]] = {}
    entities: list[dict[str, Any]] = []

    for key in order:
        entity = _build_relationship_entity(
            key,
            groups[key],
            documents_by_episode,
            extraction_runs,
            block_index_cache,
            entity_types,
        )
        if entity is not None:
            entities.append(entity)

    _record_endpoint_conflicts(entities, review_records)

    if review_records is not None:
        deduplicated: dict[tuple[Any, Any], dict[str, Any]] = {}
        order_keys: list[tuple[Any, Any]] = []
        for record in review_records:
            record_key = (record.get("episodeId"), record.get("candidateId"))
            if record_key not in deduplicated:
                deduplicated[record_key] = record
                order_keys.append(record_key)
                continue
            existing = deduplicated[record_key]
            existing["reasons"] = list(
                dict.fromkeys([*existing["reasons"], *record["reasons"]])
            )
        review_records[:] = [
            deduplicated[key] for key in order_keys if deduplicated[key]["reasons"]
        ]

    return entities, warnings
