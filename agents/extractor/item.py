"""
DKB Extractor - ItemCandidate
明示的なitemId/itemNameからrule-baseでItemCandidateの最小構造を生成する。

docs/architecture/06_AI/Extraction_Result_Schema.md §9
"""

from __future__ import annotations

from typing import Any

from .base import (
    add_block_evidence_if_needed,
    add_scene_evidence_if_needed,
    as_non_empty_string,
    iter_blocks_recursive,
    structured_identity_key,
)
from .models import (
    ITEM_CANDIDATE_CONFIDENCE_NAME_ONLY,
    ITEM_CANDIDATE_CONFIDENCE_RESOLVED,
    ITEM_CANDIDATE_SOURCE_TYPE,
    ITEM_CANDIDATE_TYPE,
    ItemCandidateAccumulator,
)


def build_item_candidates(
    episode: dict[str, Any],
    story_id: str,
    episode_id: str,
    extraction_run: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """明示的なitemId/itemNameからItemCandidateを生成する

    本文の自然文から「アイテム名かもしれない」推定は行わず、以下の
    構造的な手がかりのみを対象とする。
    - Scene直下に明示された itemId/itemName
    - dialogue/monologue/narration/choice Blockに明示された
      itemId/itemName
    - stage_direction Blockに明示された itemId/itemName
      (item/prop/object相当の演出情報。BlockCommonはadditionalProperties
      を許容するため、将来Parserが付与しうる拡張フィールドを想定する)

    Scene由来の候補はBlock単位の根拠を持たないため、Scene ID自体を
    evidenceとして使う。
    """
    accumulators: dict[tuple[str, str], ItemCandidateAccumulator] = {}
    order: list[tuple[str, str]] = []
    extra_evidence: dict[str, dict[str, Any]] = {}

    for scene in episode.get("scenes", []):
        scene_id = scene.get("sceneId")
        _record_scene_item(
            accumulators,
            order,
            extra_evidence,
            scene,
            scene_id,
            story_id,
            episode_id,
        )
        for block in iter_blocks_recursive(scene.get("blocks", [])):
            _record_block_item(
                accumulators,
                order,
                extra_evidence,
                block,
                scene_id,
                story_id,
                episode_id,
            )

    candidates = _finalize_item_candidates(
        accumulators, order, episode_id, extraction_run
    )
    return candidates, list(extra_evidence.values())


def _record_scene_item(
    accumulators: dict[tuple[str, str], ItemCandidateAccumulator],
    order: list[tuple[str, str]],
    extra_evidence: dict[str, dict[str, Any]],
    scene: dict[str, Any],
    scene_id: str | None,
    story_id: str,
    episode_id: str,
) -> None:
    """Scene直下に明示されたitemId/itemNameを記録する。"""
    item_id = as_non_empty_string(scene.get("itemId"))
    item_name = as_non_empty_string(scene.get("itemName"))
    if item_name is None or scene_id is None:
        return
    key = structured_identity_key(item_id, item_name)
    if key is None:
        return

    if key not in accumulators:
        accumulators[key] = ItemCandidateAccumulator(item_id=item_id)
        order.append(key)
    accumulator = accumulators[key]
    accumulator.add_name(item_name)
    accumulator.add_evidence(scene_id)

    add_scene_evidence_if_needed(
        extra_evidence,
        scene_id=scene_id,
        story_id=story_id,
        episode_id=episode_id,
    )


def _record_block_item(
    accumulators: dict[tuple[str, str], ItemCandidateAccumulator],
    order: list[tuple[str, str]],
    extra_evidence: dict[str, dict[str, Any]],
    block: dict[str, Any],
    scene_id: str | None,
    story_id: str,
    episode_id: str,
) -> None:
    """Blockに明示されたitemId/itemNameを記録する

    block["id"]がEVIDENCE_BLOCK_TYPESであれば既にevidenceIndexに含まれる。
    stage_directionなど対象外の場合のみevidence refを追加する。
    """
    key = structured_identity_key(block.get("itemId"), block.get("itemName"))
    if key is None:
        return

    if key not in accumulators:
        accumulators[key] = ItemCandidateAccumulator(item_id=block.get("itemId"))
        order.append(key)
    accumulator = accumulators[key]
    accumulator.add_name(block.get("itemName"))

    block_id = block["id"]
    accumulator.add_evidence(block_id)

    add_block_evidence_if_needed(
        extra_evidence,
        block,
        story_id=story_id,
        episode_id=episode_id,
        scene_id=scene_id,
    )


def _finalize_item_candidates(
    accumulators: dict[tuple[str, str], ItemCandidateAccumulator],
    order: list[tuple[str, str]],
    episode_id: str,
    extraction_run: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in order:
        accumulator = accumulators[key]
        if not accumulator.name_candidates or not accumulator.evidence_ids:
            continue

        index = len(candidates) + 1
        is_resolved = accumulator.item_id is not None
        candidates.append(
            {
                "id": f"{episode_id}_CAND_ITEM{index:03d}",
                "type": ITEM_CANDIDATE_TYPE,
                "sourceType": ITEM_CANDIDATE_SOURCE_TYPE,
                "confidence": (
                    ITEM_CANDIDATE_CONFIDENCE_RESOLVED
                    if is_resolved
                    else ITEM_CANDIDATE_CONFIDENCE_NAME_ONLY
                ),
                "evidenceIds": list(accumulator.evidence_ids),
                "extractionRun": extraction_run,
                "existingItemId": accumulator.item_id,
                "nameCandidates": list(accumulator.name_candidates),
                "fields": {},
            }
        )
    return candidates
