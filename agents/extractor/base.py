"""
DKB Extractor - Base
Candidate抽出の共通ヘルパー (evidenceIndex構築、識別キー判定) をまとめる。

各Candidate種別のロジックは個別moduleに分割されている。ここに置くのは、
複数種別が共通で使うevidenceIndex関連の処理と、構造化ID優先の
同一性判定キーのみ。

docs/architecture/06_AI/Extraction_Pipeline.md
docs/architecture/06_AI/Extraction_Result_Schema.md
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from .models import DEFAULT_EVIDENCE_CONFIDENCE, EVIDENCE_BLOCK_TYPES, EvidenceRef


def as_non_empty_string(value: Any) -> str | None:
    """非空のstringだけを返し、それ以外は構造化fieldとして扱わない。"""
    if isinstance(value, str) and value.strip():
        return value
    return None


def iter_blocks_recursive(
    blocks: list[dict[str, Any]],
) -> Iterator[dict[str, Any]]:
    """Block列をchoice option内までdepth-first preorderで走査する。

    choice Block自身を先に返し、その後options配列順・各blocks配列順で
    任意階層の子Blockを返す。Candidate抽出ではEvidence対象外の
    stage_directionも手がかりになりうるため、typeによるfilterは行わない。
    """
    for block in blocks:
        yield block
        for option in block.get("options", []) or []:
            yield from iter_blocks_recursive(option.get("blocks", []) or [])


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


def add_block_evidence_if_needed(
    extra_evidence: dict[str, dict[str, Any]],
    block: dict[str, Any],
    *,
    story_id: str,
    episode_id: str,
    scene_id: str | None,
) -> None:
    """標準Evidence対象外のBlockをextra evidenceへfirst-winsで追加する。

    dialogue/monologue/narration/choiceはbuild_evidence_refsで既に収集される
    ため追加しない。stage_direction等だけを対象とし、source confidenceが
    明示されていれば0.0を含めて保持、未指定時だけ既定値を使う。
    """
    if block.get("type") in EVIDENCE_BLOCK_TYPES:
        return

    block_id = block["id"]
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


def add_scene_evidence_if_needed(
    extra_evidence: dict[str, dict[str, Any]],
    *,
    scene_id: str | None,
    story_id: str,
    episode_id: str,
) -> None:
    """Scene単位の構造化情報を根拠としてfirst-winsで追加する。"""
    if scene_id is None:
        return

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
