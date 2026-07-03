"""
DKB Merger - Entity Merge Base
Stage A CharacterCandidate/LocationCandidate/OrganizationCandidateから
Stage B merged entityを組み立てる際に、3種で共通する処理をまとめる。

merge keyがcanonical ID (existing*Id) に解決できるcandidate群のみ自動で
1つのmerged entityへ統合する。それ以外 (名前のみ等) は候補ごとに個別の
unresolved entityとして扱い、名前一致だけで同一エンティティと確定しない
(Merged_Knowledge_Design.md §4.1 原則2)。

docs/architecture/06_AI/Merged_Knowledge_Design.md §4, §5, §9, §10
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

MERGED_ENTITY_SCHEMA_VERSION = "0.1"

STATUS_MERGED = "merged"
STATUS_UNRESOLVED = "unresolved"

# merge_key_fnが返すkindのうち、構造化ID (canonical) として扱うもの。
# それ以外 ("unresolved"含む全て) はcanonical化しない (§4.4)。
_KIND_RESOLVED = "id"
_KIND_UNRESOLVED = "unresolved"


def _build_block_type_index(
    document: dict[str, Any],
) -> tuple[dict[str, str], set[str]]:
    """episode内のBlock ID -> type、Scene IDの集合を作る (evidenceType判定用)。

    choiceのoption内Blockも再帰的に含める (agents/extractor/base.pyの
    evidence_from_blockと同じ走査方針)。
    """
    block_types: dict[str, str] = {}
    scene_ids: set[str] = set()

    def _walk_block(block: dict[str, Any]) -> None:
        block_id = block.get("id")
        if block_id:
            block_types[block_id] = block.get("type")
        for option in block.get("options", []) or []:
            for inner in option.get("blocks", []) or []:
                _walk_block(inner)

    for scene in document.get("scenes", []) or []:
        scene_id = scene.get("sceneId")
        if scene_id:
            scene_ids.add(scene_id)
        for block in scene.get("blocks", []) or []:
            _walk_block(block)

    return block_types, scene_ids


def build_merged_evidence_refs(
    document: dict[str, Any],
    evidence_ids: list[str],
    episode_id: str,
    block_types: dict[str, str],
    scene_ids: set[str],
) -> list[dict[str, Any]]:
    """candidateのevidenceIdsを、documentのevidenceIndexから解決して
    MergedEvidenceRefへ変換する (Merged_Knowledge_Design.md §10.1)。

    evidenceIndexに存在しないevidenceIdは無視する (schema検証済み入力を
    前提とするため通常は発生しない)。evidenceを失わないことが目的のため、
    ここでフィルタするのはevidenceIndex側の欠落のみに留める。
    """
    evidence_index = document.get("evidenceIndex", {}) or {}
    refs: list[dict[str, Any]] = []

    for evidence_id in evidence_ids:
        ref = evidence_index.get(evidence_id)
        if ref is None:
            continue

        source_id = ref.get("sourceId", evidence_id)
        scene_id = ref.get("sceneId")

        if source_id == episode_id:
            evidence_type: str | None = "episode"
            block_id: str | None = None
        elif scene_id is not None and source_id == scene_id:
            evidence_type = "scene"
            block_id = None
        elif source_id in block_types:
            evidence_type = block_types[source_id]
            block_id = source_id
        else:
            # Block IDらしき値だが、走査済みscenes内に見つからない場合
            # (呼び出し側がscenesを省略した最小fixture等)。IDそのものは
            # 失わずblockIdとして保持し、種別のみ不明とする。
            evidence_type = None
            block_id = source_id

        refs.append(
            {
                "evidenceId": source_id,
                "storyId": ref.get("storyId"),
                "episodeId": ref.get("episodeId", episode_id),
                "sceneId": scene_id,
                "blockId": block_id,
                "sourceDocumentId": episode_id,
                "evidenceType": evidence_type,
                "confidence": ref.get("confidence"),
            }
        )

    return refs


def build_source_candidate(
    candidate: dict[str, Any], episode_id: str
) -> dict[str, Any]:
    """Stage A candidateからSourceCandidateを組み立てる
    (Merged_Knowledge_Design.md §10.2)。candidate ID・evidenceIds・
    extractionRun参照を失わないための中核。
    """
    return {
        "candidateId": candidate["id"],
        "candidateType": candidate["type"],
        "sourceDocumentId": episode_id,
        "episodeId": episode_id,
        "evidenceIds": list(candidate.get("evidenceIds", [])),
        "extractionRunRef": episode_id,
        "sourceType": candidate.get("sourceType"),
        "confidence": candidate.get("confidence"),
    }


def aggregate_name_candidates(
    group: list[dict[str, Any]],
) -> tuple[str | None, list[str], list[dict[str, Any]]]:
    """グループ内のnameCandidatesを集約し、(displayName, aliases, conflicts) を返す。

    表記揺れがある場合は全表記をaliasesへ保持しつつ、conflictsへ
    field_value_conflict (severity: warning, resolutionStatus: unresolved)
    を記録する (Merged_Knowledge_Design.md §9.1)。高度な自動解決は行わない。
    """
    names: list[str] = []
    for candidate in group:
        for name in candidate.get("nameCandidates", []) or []:
            if name not in names:
                names.append(name)

    display_name = names[0] if names else None
    aliases = names[1:]

    conflicts: list[dict[str, Any]] = []
    if len(names) > 1:
        conflicts.append(
            {
                "conflictType": "field_value_conflict",
                "field": "displayName",
                "values": list(names),
                "sourceCandidateIds": [c["id"] for c in group],
                "severity": "warning",
                "resolutionStatus": "unresolved",
                "selectedValue": display_name,
            }
        )

    return display_name, aliases, conflicts


def _group_candidates(
    valid_entries: list[tuple[str, dict[str, Any]]],
    candidate_array_key: str,
    merge_key_fn: Callable[[dict[str, Any]], tuple[str, str]],
) -> tuple[
    dict[tuple[str, str], list[tuple[dict[str, Any], str]]],
    list[tuple[str, str]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any] | None],
]:
    """全valid documentのcandidateをmerge keyでグルーピングする。

    戻り値: (key -> [(candidate, episodeId), ...], キーの出現順, episodeId ->
    document, episodeId -> extractionRun)。
    """
    groups: dict[tuple[str, str], list[tuple[dict[str, Any], str]]] = {}
    order: list[tuple[str, str]] = []
    documents_by_episode: dict[str, dict[str, Any]] = {}
    extraction_runs: dict[str, dict[str, Any] | None] = {}

    for _path, document in valid_entries:
        episode_id = document.get("episodeId")
        if episode_id and episode_id not in documents_by_episode:
            documents_by_episode[episode_id] = document
            extraction_runs[episode_id] = document.get("extractionRun")

        for candidate in document.get(candidate_array_key, []) or []:
            key = merge_key_fn(candidate)
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append((candidate, episode_id))

    return groups, order, documents_by_episode, extraction_runs


def _resolve_entity_identity(
    kind: str, key_value: str, id_prefix: str, unresolved_counter: int
) -> tuple[str, str | None, str | None, str, int]:
    """merge keyのkindから (entity_id, canonicalId, mergedId, status,
    更新後のunresolved_counter) を決定する。

    kind == "id" のみcanonical ID (Merged_Knowledge_Design.md §5.1〜§5.3の
    existing*Id) として扱う。それ以外は名前一致だけで自動マージしない方針
    (§4.1原則2) に従い、canonical化しない (status: unresolved)。
    "unresolved" (名前のみ等、candidate単位) は連番、それ以外の構造化
    キー (例: sourceCharacterId) はkey_valueから決定的にIDを組み立てる
    (同じ入力なら同じ出力になる、§4.6)。
    """
    if kind == _KIND_RESOLVED:
        return key_value, key_value, None, STATUS_MERGED, unresolved_counter

    if kind == _KIND_UNRESOLVED:
        unresolved_counter += 1
        entity_id = f"UNRESOLVED_{id_prefix}_{unresolved_counter:04d}"
        return entity_id, None, entity_id, STATUS_UNRESOLVED, unresolved_counter

    entity_id = f"UNRESOLVED_{id_prefix}_{key_value}"
    return entity_id, None, entity_id, STATUS_UNRESOLVED, unresolved_counter


def _build_entity_for_group(
    members: list[tuple[dict[str, Any], str]],
    documents_by_episode: dict[str, dict[str, Any]],
    extraction_runs: dict[str, dict[str, Any] | None],
    block_index_cache: dict[str, tuple[dict[str, str], set[str]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str], list[str], float]:
    """1つのmerge keyグループから、evidenceRefs/sourceCandidates/
    episodeIds/sourceTypes/confidenceを組み立てる。
    """
    candidates = [c for c, _episode_id in members]

    evidence_refs: list[dict[str, Any]] = []
    source_candidates: list[dict[str, Any]] = []
    episode_ids_used: list[str] = []
    source_types: list[str] = []

    for candidate, episode_id in members:
        document = documents_by_episode[episode_id]
        if episode_id not in block_index_cache:
            block_index_cache[episode_id] = _build_block_type_index(document)
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

    confidence = max((c.get("confidence") or 0.0) for c in candidates)
    return evidence_refs, source_candidates, episode_ids_used, source_types, confidence


def build_merged_entities(
    valid_entries: list[tuple[str, dict[str, Any]]],
    candidate_array_key: str,
    entity_type: str,
    id_prefix: str,
    merge_key_fn: Callable[[dict[str, Any]], tuple[str, str]],
    extra_fields_fn: Callable[[list[dict[str, Any]]], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Character/Location/Organizationで共通のmerge処理。

    merge_key_fnが ("id", 値) を返すcandidate群は、値をcanonical ID
    としてそのまま採用し1つのmerged entityへ統合する (status: merged)。
    ("unresolved", candidateId) を返すcandidateは1候補=1 merged entityと
    して個別に扱う (status: unresolved、名前一致だけでは自動マージしない、
    Merged_Knowledge_Design.md §4.1原則2)。それ以外のkind (例:
    sourceCharacterIdのような「構造化されているがまだcanonicalではない」
    キー) は、同じ値を持つcandidate同士は安全にmerge対象としつつ、
    canonical IDへは解決しない (status: unresolved、id/mergedIdはkindの
    値から決定的に組み立てる)。
    """
    groups, order, documents_by_episode, extraction_runs = _group_candidates(
        valid_entries, candidate_array_key, merge_key_fn
    )

    block_index_cache: dict[str, tuple[dict[str, str], set[str]]] = {}
    entities: list[dict[str, Any]] = []
    unresolved_counter = 0

    for key in order:
        kind, key_value = key
        members = groups[key]
        candidates = [c for c, _episode_id in members]

        display_name, aliases, conflicts = aggregate_name_candidates(candidates)
        evidence_refs, source_candidates, episode_ids_used, source_types, confidence = (
            _build_entity_for_group(
                members, documents_by_episode, extraction_runs, block_index_cache
            )
        )

        if not evidence_refs:
            # Evidenceを1件も持たない候補は出力しない
            # (Extraction_Pipeline.md §6.1と同じ原則)
            continue

        entity_id, canonical_id, merged_id, status, unresolved_counter = (
            _resolve_entity_identity(kind, key_value, id_prefix, unresolved_counter)
        )

        entity: dict[str, Any] = {
            "schemaVersion": MERGED_ENTITY_SCHEMA_VERSION,
            "id": entity_id,
            "type": entity_type,
            "canonicalId": canonical_id,
            "mergedId": merged_id,
            "displayName": display_name,
            "aliases": aliases,
            "status": status,
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

        if extra_fields_fn is not None:
            entity.update(extra_fields_fn(candidates))

        entities.append(entity)

    return entities
