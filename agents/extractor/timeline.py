"""
DKB Extractor - TimelineCandidate
Normalized Story JSON内で構造的に表現されている時系列・順序情報から、rule-baseで
TimelineCandidateの最小構造を生成する。

docs/architecture/06_AI/Extraction_Result_Schema.md §13
"""

from __future__ import annotations

from typing import Any

from .base import (
    add_block_evidence_if_needed,
    add_scene_evidence_if_needed,
    as_non_empty_string,
)
from .models import (
    DEFAULT_EVIDENCE_CONFIDENCE,
    EPISODE_ORDER_METADATA_FIELDS,
    TIMELINE_CANDIDATE_CONFIDENCE_MARKER,
    TIMELINE_CANDIDATE_CONFIDENCE_RESOLVED,
    TIMELINE_CANDIDATE_CONFIDENCE_UNRESOLVED,
    TIMELINE_CANDIDATE_SOURCE_TYPE,
    TIMELINE_CANDIDATE_TYPE,
    TIMELINE_KIND_EXPLICIT_ORDER,
    TIMELINE_KIND_TEMPORAL_MARKER,
    TIMELINE_MARKER_FIELDS,
    TIMELINE_SCOPE_BLOCK,
    TIMELINE_SCOPE_EPISODE,
    TIMELINE_SCOPE_SCENE,
    EvidenceRef,
    TimelineCandidateAccumulator,
)

# TimelineCandidate抽出の対象とするBlock種別。stage_directionも構造マーカー
# (flashback等) の手がかりとして含める (Extraction_Pipeline.md §5.4の
# stage_direction「補助的手がかり」扱いと同じ前提)。
TIMELINE_SOURCE_BLOCK_TYPES = frozenset(
    {"dialogue", "monologue", "narration", "choice", "stage_direction"}
)

# bool は int のサブクラスのため、明示的に除外して数値のみを順序値として扱う。
_NUMERIC_TYPES = (int, float)


def _as_order_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, _NUMERIC_TYPES):
        return value
    return None


def build_timeline_candidates(
    episode: dict[str, Any],
    story_id: str,
    episode_id: str,
    extraction_run: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalized Story JSON内で構造的に表現されている時系列・順序情報から
    TimelineCandidateを生成する。

    今回対象とする手がかりは以下の3種類のみ。本文の自然文から「昔」「その後」
    「翌日」「回想」等を推定する処理は一切行わない。

    - episode.metadataに明示された canonicalOrder/releaseOrder/displayOrder
      (EpisodeMetadataはadditionalPropertiesを許容するため、将来Parserが
      付与しうる拡張フィールドを想定する)
    - Scene直下またはdialogue/monologue/narration/choice/stage_direction
      Blockに明示された
      timelineId/timelineLabel/timePosition/orderValue
    - 同じ入力単位に明示された flashback/flashforward/dayChange/timeShift/
      sceneTime構造フィールド (値の中身までは解釈しない)

    Scene由来候補はsceneIdをidentityへ含め、別Sceneの値をStage Aで混ぜない。
    同じsourceTimelineIdの横断統合と値の食い違い検出はStage Bへ委ねる。
    """
    accumulators: dict[tuple[str, ...], TimelineCandidateAccumulator] = {}
    order: list[tuple[str, ...]] = []
    extra_evidence: dict[str, dict[str, Any]] = {}

    _record_episode_metadata_order(
        accumulators, order, extra_evidence, episode, story_id, episode_id
    )

    for scene in episode.get("scenes", []):
        scene_id = scene.get("sceneId")
        _record_scene_order(
            accumulators,
            order,
            extra_evidence,
            scene,
            scene_id,
            story_id,
            episode_id,
        )
        _record_scene_marker(
            accumulators,
            order,
            extra_evidence,
            scene,
            scene_id,
            story_id,
            episode_id,
        )
        for block in scene.get("blocks", []):
            _record_block_order(
                accumulators,
                order,
                extra_evidence,
                block,
                scene_id,
                story_id,
                episode_id,
            )
            _record_block_marker(
                accumulators,
                order,
                extra_evidence,
                block,
                scene_id,
                story_id,
                episode_id,
            )

    candidates = _finalize_timeline_candidates(
        accumulators, order, episode_id, extraction_run
    )
    return candidates, list(extra_evidence.values())


def _record_episode_metadata_order(
    accumulators: dict[tuple[str, ...], TimelineCandidateAccumulator],
    order: list[tuple[str, ...]],
    extra_evidence: dict[str, dict[str, Any]],
    episode: dict[str, Any],
    story_id: str,
    episode_id: str,
) -> None:
    """episode.metadataの明示的なcanonicalOrder/releaseOrder/displayOrderを記録する

    speakerAssignmentsはEpisode直下の構造でBlock IDを持たないため、
    Episode ID自体をevidenceとして使う (OrganizationCandidateと同じ扱い)。
    存在するフィールドごとに個別のcandidateを生成し、優先順位付けはしない。
    """
    metadata = episode.get("metadata", {}) or {}
    metadata_sources = metadata.get("metadataSources", {}) or {}
    if not isinstance(metadata_sources, dict):
        metadata_sources = {}
    for field_name in EPISODE_ORDER_METADATA_FIELDS:
        order_value = _as_order_value(metadata.get(field_name))
        if order_value is None:
            continue

        key = ("episode_order", episode_id, field_name)
        source = metadata_sources.get(field_name, {}) or {}
        if not isinstance(source, dict):
            source = {}
        source_type = source.get("sourceType")
        if source_type not in {
            "official",
            "script",
            "ai_extracted",
            "ai_inferred",
            "manual",
            "unknown",
        }:
            source_type = None
        source_confidence = source.get("confidence")
        if (
            not isinstance(source_confidence, (int, float))
            or isinstance(source_confidence, bool)
            or not 0 <= source_confidence <= 1
        ):
            source_confidence = None

        accumulators[key] = TimelineCandidateAccumulator(
            kind=TIMELINE_KIND_EXPLICIT_ORDER,
            scope=TIMELINE_SCOPE_EPISODE,
            order_value=order_value,
            order_field=field_name,
            is_resolved=True,
            source_type=source_type,
            confidence=source_confidence,
        )
        order.append(key)
        accumulators[key].add_evidence(episode_id)
        extra_evidence.setdefault(
            episode_id,
            EvidenceRef(
                source_id=episode_id,
                story_id=story_id,
                episode_id=episode_id,
                scene_id=None,
                confidence=DEFAULT_EVIDENCE_CONFIDENCE,
            ).to_dict(),
        )


def _timeline_block_order_key(
    timeline_id: str | None, order_value: float | None, name: str | None
) -> tuple[str, ...] | None:
    """timelineId優先、無ければorder_value、それも無ければnameで同一性判定する"""
    if timeline_id:
        return (TIMELINE_SCOPE_BLOCK, "id", timeline_id)
    if order_value is not None:
        return (TIMELINE_SCOPE_BLOCK, "order", str(order_value))
    if name:
        return (TIMELINE_SCOPE_BLOCK, "name", name)
    return None


def _timeline_scene_order_key(
    scene_id: str,
    timeline_id: str | None,
    order_value: float | None,
    name: str | None,
) -> tuple[str, ...] | None:
    """Scene由来候補は値を失わないよう常にScene単位に分離する。"""
    if timeline_id:
        return (TIMELINE_SCOPE_SCENE, scene_id, "id", timeline_id)
    if order_value is not None:
        return (TIMELINE_SCOPE_SCENE, scene_id, "order", str(order_value))
    if name:
        return (TIMELINE_SCOPE_SCENE, scene_id, "name", name)
    return None


def _record_scene_order(
    accumulators: dict[tuple[str, ...], TimelineCandidateAccumulator],
    order: list[tuple[str, ...]],
    extra_evidence: dict[str, dict[str, Any]],
    scene: dict[str, Any],
    scene_id: str | None,
    story_id: str,
    episode_id: str,
) -> None:
    """Scene直下のtimelineId/timelineLabel/timePosition/orderValueを記録する。"""
    if scene_id is None:
        return

    timeline_id = as_non_empty_string(scene.get("timelineId"))
    order_value = _as_order_value(scene.get("orderValue"))
    order_field = "orderValue" if order_value is not None else None
    if order_value is None:
        order_value = _as_order_value(scene.get("timePosition"))
        if order_value is not None:
            order_field = "timePosition"

    name = as_non_empty_string(scene.get("timelineLabel"))
    if name is None:
        name = as_non_empty_string(scene.get("timePosition"))

    key = _timeline_scene_order_key(scene_id, timeline_id, order_value, name)
    if key is None:
        return

    is_resolved = timeline_id is not None or order_value is not None
    if key not in accumulators:
        accumulators[key] = TimelineCandidateAccumulator(
            kind=TIMELINE_KIND_EXPLICIT_ORDER,
            scope=TIMELINE_SCOPE_SCENE,
            source_timeline_id=timeline_id,
            order_value=order_value,
            order_field=order_field,
            is_resolved=is_resolved,
        )
        order.append(key)

    accumulator = accumulators[key]
    accumulator.add_name(name)
    accumulator.is_resolved = accumulator.is_resolved or is_resolved
    if accumulator.source_timeline_id is None:
        accumulator.source_timeline_id = timeline_id
    if accumulator.order_value is None:
        accumulator.order_value = order_value
        accumulator.order_field = order_field
    accumulator.add_scene_ref(scene_id)
    accumulator.add_evidence(scene_id)
    add_scene_evidence_if_needed(
        extra_evidence,
        scene_id=scene_id,
        story_id=story_id,
        episode_id=episode_id,
    )


def _record_scene_marker(
    accumulators: dict[tuple[str, ...], TimelineCandidateAccumulator],
    order: list[tuple[str, ...]],
    extra_evidence: dict[str, dict[str, Any]],
    scene: dict[str, Any],
    scene_id: str | None,
    story_id: str,
    episode_id: str,
) -> None:
    """Scene直下の明示的な時間軸マーカーをScene単位で記録する。"""
    if scene_id is None:
        return

    for field_name, marker_type in TIMELINE_MARKER_FIELDS:
        if not scene.get(field_name):
            continue

        key = (TIMELINE_SCOPE_SCENE, scene_id, "marker", marker_type)
        accumulators[key] = TimelineCandidateAccumulator(
            kind=TIMELINE_KIND_TEMPORAL_MARKER,
            scope=TIMELINE_SCOPE_SCENE,
            marker_type=marker_type,
        )
        order.append(key)
        accumulator = accumulators[key]
        accumulator.add_scene_ref(scene_id)
        accumulator.add_evidence(scene_id)
        add_scene_evidence_if_needed(
            extra_evidence,
            scene_id=scene_id,
            story_id=story_id,
            episode_id=episode_id,
        )


def _record_block_order(
    accumulators: dict[tuple[str, ...], TimelineCandidateAccumulator],
    order: list[tuple[str, ...]],
    extra_evidence: dict[str, dict[str, Any]],
    block: dict[str, Any],
    scene_id: str | None,
    story_id: str,
    episode_id: str,
) -> None:
    """Blockに明示されたtimelineId/timelineLabel/timePosition/orderValueを記録する"""
    if block.get("type") not in TIMELINE_SOURCE_BLOCK_TYPES:
        return

    timeline_id = block.get("timelineId")

    order_value = _as_order_value(block.get("orderValue"))
    order_field = "orderValue" if order_value is not None else None
    if order_value is None:
        order_value = _as_order_value(block.get("timePosition"))
        if order_value is not None:
            order_field = "timePosition"

    name = block.get("timelineLabel")
    if name is None and isinstance(block.get("timePosition"), str):
        name = block["timePosition"]

    key = _timeline_block_order_key(timeline_id, order_value, name)
    if key is None:
        return

    is_resolved = timeline_id is not None or order_value is not None

    if key not in accumulators:
        accumulators[key] = TimelineCandidateAccumulator(
            kind=TIMELINE_KIND_EXPLICIT_ORDER,
            scope=TIMELINE_SCOPE_BLOCK,
            source_timeline_id=timeline_id,
            order_value=order_value,
            order_field=order_field,
            is_resolved=is_resolved,
        )
        order.append(key)

    accumulator = accumulators[key]
    accumulator.add_name(name)
    accumulator.is_resolved = accumulator.is_resolved or is_resolved
    if accumulator.source_timeline_id is None:
        accumulator.source_timeline_id = timeline_id
    if accumulator.order_value is None:
        accumulator.order_value = order_value
        accumulator.order_field = order_field
    if scene_id is not None:
        accumulator.add_scene_ref(scene_id)
    accumulator.add_evidence(block["id"])

    add_block_evidence_if_needed(
        extra_evidence,
        block,
        story_id=story_id,
        episode_id=episode_id,
        scene_id=scene_id,
    )


def _record_block_marker(
    accumulators: dict[tuple[str, ...], TimelineCandidateAccumulator],
    order: list[tuple[str, ...]],
    extra_evidence: dict[str, dict[str, Any]],
    block: dict[str, Any],
    scene_id: str | None,
    story_id: str,
    episode_id: str,
) -> None:
    """Blockに明示されたflashback/flashforward/dayChange/timeShift/sceneTime
    構造フィールドを記録する。値の中身は解釈せず、フィールドの真偽のみを見る。
    """
    if block.get("type") not in TIMELINE_SOURCE_BLOCK_TYPES:
        return

    for field_name, marker_type in TIMELINE_MARKER_FIELDS:
        if not block.get(field_name):
            continue

        key = ("marker", marker_type, "")
        if key not in accumulators:
            accumulators[key] = TimelineCandidateAccumulator(
                kind=TIMELINE_KIND_TEMPORAL_MARKER,
                scope=TIMELINE_SCOPE_BLOCK,
                marker_type=marker_type,
            )
            order.append(key)
        if scene_id is not None:
            accumulators[key].add_scene_ref(scene_id)
        accumulators[key].add_evidence(block["id"])
        add_block_evidence_if_needed(
            extra_evidence,
            block,
            story_id=story_id,
            episode_id=episode_id,
            scene_id=scene_id,
        )


def _finalize_timeline_candidates(
    accumulators: dict[tuple[str, ...], TimelineCandidateAccumulator],
    order: list[tuple[str, ...]],
    episode_id: str,
    extraction_run: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in order:
        accumulator = accumulators[key]
        if not accumulator.evidence_ids:
            # Evidenceが1件も無い推測は出力しない (Extraction_Pipeline.md §6.1)
            continue

        index = len(candidates) + 1
        if accumulator.confidence is not None:
            confidence = accumulator.confidence
        elif accumulator.kind == TIMELINE_KIND_TEMPORAL_MARKER:
            confidence = TIMELINE_CANDIDATE_CONFIDENCE_MARKER
        elif accumulator.is_resolved:
            confidence = TIMELINE_CANDIDATE_CONFIDENCE_RESOLVED
        else:
            confidence = TIMELINE_CANDIDATE_CONFIDENCE_UNRESOLVED

        candidates.append(
            {
                "id": f"{episode_id}_CAND_TL{index:03d}",
                "type": TIMELINE_CANDIDATE_TYPE,
                "sourceType": accumulator.source_type or TIMELINE_CANDIDATE_SOURCE_TYPE,
                "confidence": confidence,
                "evidenceIds": list(accumulator.evidence_ids),
                "extractionRun": extraction_run,
                "kind": accumulator.kind,
                "scope": accumulator.scope,
                "relativeTo": None,
                "relation": None,
                "sourceTimelineId": accumulator.source_timeline_id,
                "nameCandidates": list(accumulator.name_candidates),
                "sceneRefs": list(accumulator.scene_refs),
                "orderValue": accumulator.order_value,
                "orderField": accumulator.order_field,
                "markerType": accumulator.marker_type,
                "fields": {},
            }
        )
    return candidates
