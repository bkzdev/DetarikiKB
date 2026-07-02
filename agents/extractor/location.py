"""
DKB Extractor - LocationCandidate
Scene.locationとstage_direction(background)からrule-baseで
LocationCandidateの最小構造を生成する。

docs/architecture/06_AI/Extraction_Result_Schema.md §7
"""

from __future__ import annotations

from typing import Any

from .base import structured_identity_key
from .models import (
    DEFAULT_EVIDENCE_CONFIDENCE,
    LOCATION_CANDIDATE_CONFIDENCE_NAME_ONLY,
    LOCATION_CANDIDATE_CONFIDENCE_RESOLVED,
    LOCATION_CANDIDATE_SOURCE_TYPE,
    LOCATION_CANDIDATE_TYPE,
    EvidenceRef,
    LocationCandidateAccumulator,
)


def build_location_candidates(
    episode: dict[str, Any],
    story_id: str,
    episode_id: str,
    extraction_run: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Scene.locationとstage_direction(background)からLocationCandidateを生成する

    本文の自然文からの場所推定は行わず、以下の構造的な手がかりのみを対象とする。
    - Scene.location (locationId/locationName)
    - directionType: "background" のstage_direction Block
      (locationId/locationNameが明示されていればそれを使い、無ければ
      normalizedCommand/rawCommandをそのまま識別子として使う)

    Scene.location由来の候補はBlock単位の根拠を持たないため、Scene ID自体を
    evidenceとして使う (Extraction_Pipeline.md §6.1のsourceId段階的
    フォールバック)。stage_directionはEVIDENCE_BLOCK_TYPESに含まれないため、
    こちらもBlock IDをevidenceIndexへ追加する必要がある。戻り値の2要素目
    (extra evidence refs) がその追加分。
    """
    accumulators: dict[tuple[str, str], LocationCandidateAccumulator] = {}
    order: list[tuple[str, str]] = []
    extra_evidence: dict[str, dict[str, Any]] = {}

    for scene in episode.get("scenes", []):
        scene_id = scene.get("sceneId")

        _record_scene_location(
            accumulators, order, extra_evidence, scene, scene_id, story_id, episode_id
        )

        for block in scene.get("blocks", []):
            _record_background_location(
                accumulators,
                order,
                extra_evidence,
                block,
                scene_id,
                story_id,
                episode_id,
            )

    candidates = _finalize_location_candidates(
        accumulators, order, episode_id, extraction_run
    )
    return candidates, list(extra_evidence.values())


def _record_scene_location(
    accumulators: dict[tuple[str, str], LocationCandidateAccumulator],
    order: list[tuple[str, str]],
    extra_evidence: dict[str, dict[str, Any]],
    scene: dict[str, Any],
    scene_id: str | None,
    story_id: str,
    episode_id: str,
) -> None:
    """Scene.locationを1件の場所出現として記録する"""
    location = scene.get("location") or {}
    key = structured_identity_key(
        location.get("locationId"), location.get("locationName")
    )
    if key is None or scene_id is None:
        return

    if key not in accumulators:
        accumulators[key] = LocationCandidateAccumulator(
            location_id=location.get("locationId")
        )
        order.append(key)
    accumulator = accumulators[key]
    accumulator.add_name(location.get("locationName"))
    accumulator.add_scene_ref(scene_id)
    accumulator.add_evidence(scene_id)
    extra_evidence.setdefault(
        scene_id,
        EvidenceRef(
            source_id=scene_id,
            story_id=story_id,
            episode_id=episode_id,
            scene_id=scene_id,
            confidence=DEFAULT_EVIDENCE_CONFIDENCE,
        ).to_dict(),
    )


def _record_background_location(
    accumulators: dict[tuple[str, str], LocationCandidateAccumulator],
    order: list[tuple[str, str]],
    extra_evidence: dict[str, dict[str, Any]],
    block: dict[str, Any],
    scene_id: str | None,
    story_id: str,
    episode_id: str,
) -> None:
    """directionType: backgroundのstage_direction Blockを場所出現として記録する"""
    if (
        block.get("type") != "stage_direction"
        or block.get("directionType") != "background"
    ):
        return

    bg_location_id = block.get("locationId")
    bg_location_name = (
        block.get("locationName")
        or block.get("normalizedCommand")
        or block.get("rawCommand")
    )
    key = structured_identity_key(bg_location_id, bg_location_name)
    if key is None:
        return

    if key not in accumulators:
        accumulators[key] = LocationCandidateAccumulator(location_id=bg_location_id)
        order.append(key)
    accumulator = accumulators[key]
    accumulator.add_name(bg_location_name)
    if scene_id is not None:
        accumulator.add_scene_ref(scene_id)

    block_id = block["id"]
    accumulator.add_evidence(block_id)

    confidence = block.get("source", {}).get("confidence")
    if confidence is None:
        confidence = DEFAULT_EVIDENCE_CONFIDENCE
    extra_evidence.setdefault(
        block_id,
        EvidenceRef(
            source_id=block_id,
            story_id=story_id,
            episode_id=episode_id,
            scene_id=scene_id,
            confidence=confidence,
        ).to_dict(),
    )


def _finalize_location_candidates(
    accumulators: dict[tuple[str, str], LocationCandidateAccumulator],
    order: list[tuple[str, str]],
    episode_id: str,
    extraction_run: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, key in enumerate(order, start=1):
        accumulator = accumulators[key]
        if (
            not accumulator.name_candidates
            or not accumulator.evidence_ids
            or not accumulator.scene_refs
        ):
            continue

        is_resolved = accumulator.location_id is not None
        candidates.append(
            {
                "id": f"{episode_id}_CAND_LOC{index:03d}",
                "type": LOCATION_CANDIDATE_TYPE,
                "sourceType": LOCATION_CANDIDATE_SOURCE_TYPE,
                "confidence": (
                    LOCATION_CANDIDATE_CONFIDENCE_RESOLVED
                    if is_resolved
                    else LOCATION_CANDIDATE_CONFIDENCE_NAME_ONLY
                ),
                "evidenceIds": list(accumulator.evidence_ids),
                "extractionRun": extraction_run,
                "existingLocationId": accumulator.location_id,
                "nameCandidates": list(accumulator.name_candidates),
                "sceneRefs": list(accumulator.scene_refs),
                "fields": {},
            }
        )
    return candidates
