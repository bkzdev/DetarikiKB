"""
DKB Extractor - ItemCandidate
明示的なitemId/itemNameからrule-baseでItemCandidateの最小構造を生成する。

docs/architecture/06_AI/Extraction_Result_Schema.md §9
"""

from __future__ import annotations

from typing import Any

from .base import structured_identity_key
from .models import (
    DEFAULT_EVIDENCE_CONFIDENCE,
    EVIDENCE_BLOCK_TYPES,
    ITEM_CANDIDATE_CONFIDENCE_NAME_ONLY,
    ITEM_CANDIDATE_CONFIDENCE_RESOLVED,
    ITEM_CANDIDATE_SOURCE_TYPE,
    ITEM_CANDIDATE_TYPE,
    EvidenceRef,
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
    - dialogue/monologue/narration/choice Blockに明示された
      itemId/itemName
    - stage_direction Blockに明示された itemId/itemName
      (item/prop/object相当の演出情報。BlockCommonはadditionalProperties
      を許容するため、将来Parserが付与しうる拡張フィールドを想定する)

    Sceneはschema上additionalPropertiesを許容しない
    (schemas/story.schema.json Scene定義) ため、scene metadataからの
    Item抽出は今回のスコープ外とする。
    """
    accumulators: dict[tuple[str, str], ItemCandidateAccumulator] = {}
    order: list[tuple[str, str]] = []
    extra_evidence: dict[str, dict[str, Any]] = {}

    for scene in episode.get("scenes", []):
        scene_id = scene.get("sceneId")
        for block in scene.get("blocks", []):
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


def _finalize_item_candidates(
    accumulators: dict[tuple[str, str], ItemCandidateAccumulator],
    order: list[tuple[str, str]],
    episode_id: str,
    extraction_run: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, key in enumerate(order, start=1):
        accumulator = accumulators[key]
        if not accumulator.name_candidates or not accumulator.evidence_ids:
            continue

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
