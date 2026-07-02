"""
DKB Extractor - LoreCandidate
明示的なloreId/termNameからrule-baseでLoreCandidateの最小構造を生成する。
Loreは推定が混ざりやすいため、最も保守的な抽出とする。

docs/architecture/06_AI/Extraction_Result_Schema.md §10
"""

from __future__ import annotations

from typing import Any

from .base import structured_identity_key
from .models import (
    EVIDENCE_BLOCK_TYPES,
    LORE_CANDIDATE_CONFIDENCE_NAME_ONLY,
    LORE_CANDIDATE_CONFIDENCE_RESOLVED,
    LORE_CANDIDATE_SOURCE_TYPE,
    LORE_CANDIDATE_TYPE,
    LoreCandidateAccumulator,
)


def build_lore_candidates(
    episode: dict[str, Any],
    episode_id: str,
    extraction_run: dict[str, Any],
) -> list[dict[str, Any]]:
    """明示的なloreId/termNameからLoreCandidateを生成する

    Loreは推定が混ざりやすいため、対象をdialogue/monologue/narration/choice
    Blockに明示されたloreId/termNameのみに限定する (stage_directionや
    speakerAssignments経由の抽出は行わない、最も保守的な抽出)。
    本文中の専門用語らしき文字列の自然文推定は行わない。
    """
    accumulators: dict[tuple[str, str], LoreCandidateAccumulator] = {}
    order: list[tuple[str, str]] = []

    for scene in episode.get("scenes", []):
        for block in scene.get("blocks", []):
            _record_block_lore(accumulators, order, block)

    return _finalize_lore_candidates(accumulators, order, episode_id, extraction_run)


def _record_block_lore(
    accumulators: dict[tuple[str, str], LoreCandidateAccumulator],
    order: list[tuple[str, str]],
    block: dict[str, Any],
) -> None:
    if block.get("type") not in EVIDENCE_BLOCK_TYPES:
        return

    key = structured_identity_key(block.get("loreId"), block.get("termName"))
    if key is None:
        return

    if key not in accumulators:
        accumulators[key] = LoreCandidateAccumulator(lore_id=block.get("loreId"))
        order.append(key)
    accumulator = accumulators[key]
    accumulator.add_term(block.get("termName"))
    accumulator.add_evidence(block["id"])


def _finalize_lore_candidates(
    accumulators: dict[tuple[str, str], LoreCandidateAccumulator],
    order: list[tuple[str, str]],
    episode_id: str,
    extraction_run: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, key in enumerate(order, start=1):
        accumulator = accumulators[key]
        if not accumulator.term_candidates or not accumulator.evidence_ids:
            continue

        is_resolved = accumulator.lore_id is not None
        candidates.append(
            {
                "id": f"{episode_id}_CAND_LORE{index:03d}",
                "type": LORE_CANDIDATE_TYPE,
                "sourceType": LORE_CANDIDATE_SOURCE_TYPE,
                "confidence": (
                    LORE_CANDIDATE_CONFIDENCE_RESOLVED
                    if is_resolved
                    else LORE_CANDIDATE_CONFIDENCE_NAME_ONLY
                ),
                "evidenceIds": list(accumulator.evidence_ids),
                "extractionRun": extraction_run,
                "existingLoreId": accumulator.lore_id,
                "termCandidates": list(accumulator.term_candidates),
                "fields": {},
            }
        )
    return candidates
