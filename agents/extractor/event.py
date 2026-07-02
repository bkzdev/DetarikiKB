"""
DKB Extractor - EventCandidate
明示的なeventId/eventNameからrule-baseでEventCandidateの最小構造を生成する。

docs/architecture/06_AI/Extraction_Result_Schema.md §11
"""

from __future__ import annotations

from typing import Any

from .base import structured_identity_key
from .models import (
    DEFAULT_EVIDENCE_CONFIDENCE,
    EVENT_CANDIDATE_CONFIDENCE_NAME_ONLY,
    EVENT_CANDIDATE_CONFIDENCE_RESOLVED,
    EVENT_CANDIDATE_SOURCE_TYPE,
    EVENT_CANDIDATE_TYPE,
    EVIDENCE_BLOCK_TYPES,
    EventCandidateAccumulator,
    EvidenceRef,
)


def build_event_candidates(
    episode: dict[str, Any],
    story_id: str,
    episode_id: str,
    extraction_run: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """明示的なeventId/eventNameからEventCandidateを生成する

    会話内容から「事件」「戦闘」「移動」等を推定する処理は行わず、以下の
    構造的な手がかりのみを対象とする。
    - dialogue/monologue/narration/choice Blockに明示された
      eventId/eventName
    - stage_direction Blockに明示された eventId/eventName
      (イベント発火・演出イベントを示す拡張フィールドを想定する)

    Sceneはschema上additionalPropertiesを許容しないため、scene metadata
    からのEvent抽出は今回のスコープ外とする (ItemCandidateと同じ理由)。
    """
    accumulators: dict[tuple[str, str], EventCandidateAccumulator] = {}
    order: list[tuple[str, str]] = []
    extra_evidence: dict[str, dict[str, Any]] = {}

    for scene in episode.get("scenes", []):
        scene_id = scene.get("sceneId")
        for block in scene.get("blocks", []):
            _record_block_event(
                accumulators,
                order,
                extra_evidence,
                block,
                scene_id,
                story_id,
                episode_id,
            )

    candidates = _finalize_event_candidates(
        accumulators, order, episode_id, extraction_run
    )
    return candidates, list(extra_evidence.values())


def _record_block_event(
    accumulators: dict[tuple[str, str], EventCandidateAccumulator],
    order: list[tuple[str, str]],
    extra_evidence: dict[str, dict[str, Any]],
    block: dict[str, Any],
    scene_id: str | None,
    story_id: str,
    episode_id: str,
) -> None:
    """Blockに明示されたeventId/eventNameを記録する"""
    key = structured_identity_key(block.get("eventId"), block.get("eventName"))
    if key is None:
        return

    if key not in accumulators:
        accumulators[key] = EventCandidateAccumulator(event_id=block.get("eventId"))
        order.append(key)
    accumulator = accumulators[key]
    accumulator.add_name(block.get("eventName"))

    block_id = block["id"]
    accumulator.add_evidence(block_id)

    if block.get("type") not in EVIDENCE_BLOCK_TYPES:
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


def _finalize_event_candidates(
    accumulators: dict[tuple[str, str], EventCandidateAccumulator],
    order: list[tuple[str, str]],
    episode_id: str,
    extraction_run: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, key in enumerate(order, start=1):
        accumulator = accumulators[key]
        if not accumulator.name_candidates or not accumulator.evidence_ids:
            continue

        is_resolved = accumulator.event_id is not None
        candidates.append(
            {
                "id": f"{episode_id}_CAND_EVENT{index:03d}",
                "type": EVENT_CANDIDATE_TYPE,
                "sourceType": EVENT_CANDIDATE_SOURCE_TYPE,
                "confidence": (
                    EVENT_CANDIDATE_CONFIDENCE_RESOLVED
                    if is_resolved
                    else EVENT_CANDIDATE_CONFIDENCE_NAME_ONLY
                ),
                "evidenceIds": list(accumulator.evidence_ids),
                "extractionRun": extraction_run,
                "existingEventId": accumulator.event_id,
                "nameCandidates": list(accumulator.name_candidates),
                "fields": {},
            }
        )
    return candidates
