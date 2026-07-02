"""
DKB Extractor - Base
Candidate抽出の共通ヘルパー (evidenceIndex構築、識別キー判定) をまとめる。

各Candidate種別のロジックは character.py/location.py/organization.py/
item.py/lore.py/event.py に分割されている。ここに置くのは、それら全てが
共通で使うevidenceIndex関連の処理と、構造化ID優先の同一性判定キーのみ。

docs/architecture/06_AI/Extraction_Pipeline.md
docs/architecture/06_AI/Extraction_Result_Schema.md
"""

from __future__ import annotations

from typing import Any

from .models import DEFAULT_EVIDENCE_CONFIDENCE, EVIDENCE_BLOCK_TYPES, EvidenceRef


def build_evidence_refs(
    episode: dict[str, Any], story_id: str, episode_id: str
) -> list[dict[str, Any]]:
    """dialogue/monologue/narration/choice BlockからEvidenceRefを収集する

    Extraction_Pipeline.md §5.4: 抽出対象として直接読むのは
    dialogue/monologue/narration/choiceの4種。unknownは対象外。
    """
    refs: list[dict[str, Any]] = []
    for scene in episode.get("scenes", []):
        scene_id = scene.get("sceneId")
        for block in scene.get("blocks", []):
            refs.extend(evidence_from_block(block, story_id, episode_id, scene_id))
    return refs


def evidence_from_block(
    block: dict[str, Any],
    story_id: str,
    episode_id: str,
    scene_id: str | None,
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []

    if block.get("type") in EVIDENCE_BLOCK_TYPES:
        confidence = block.get("source", {}).get("confidence")
        if confidence is None:
            confidence = DEFAULT_EVIDENCE_CONFIDENCE

        refs.append(
            EvidenceRef(
                source_id=block["id"],
                story_id=story_id,
                episode_id=episode_id,
                scene_id=scene_id,
                confidence=confidence,
            ).to_dict()
        )

    # choiceのoption内Block (branch内の会話等) も同じ扱いで再帰的に集める
    for option in block.get("options", []):
        for inner_block in option.get("blocks", []):
            refs.extend(
                evidence_from_block(inner_block, story_id, episode_id, scene_id)
            )

    return refs


def merge_evidence_index(
    *ref_lists: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """複数のEvidenceRefリストを、sourceIdをキーにしたevidenceIndexへまとめる

    先に渡されたリストのrefが優先される (最初に登場したものを残す)。
    """
    evidence_index: dict[str, dict[str, Any]] = {}
    for refs in ref_lists:
        for ref in refs:
            evidence_index.setdefault(ref["sourceId"], ref)
    return evidence_index


def structured_identity_key(
    id_value: str | None, name_value: str | None
) -> tuple[str, str] | None:
    """構造化ID優先、無ければ名前文字列で同一性判定するキーを返す

    LocationCandidate/OrganizationCandidate/ItemCandidate/LoreCandidate/
    EventCandidateで共通に使う。
    """
    if id_value:
        return ("id", id_value)
    if name_value:
        return ("name", name_value)
    return None
