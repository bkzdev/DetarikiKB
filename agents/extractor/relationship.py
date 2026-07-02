"""
DKB Extractor - RelationshipCandidate
Normalized Story JSON内で構造的に表現されている関係情報から、rule-baseで
RelationshipCandidateの最小構造を生成する。

docs/architecture/06_AI/Extraction_Result_Schema.md §12
"""

from __future__ import annotations

from typing import Any

from .models import (
    DEFAULT_EVIDENCE_CONFIDENCE,
    RELATIONSHIP_CANDIDATE_CONFIDENCE_RESOLVED,
    RELATIONSHIP_CANDIDATE_CONFIDENCE_UNRESOLVED,
    RELATIONSHIP_CANDIDATE_DEFAULT_DIRECTION,
    RELATIONSHIP_CANDIDATE_SOURCE_TYPE,
    RELATIONSHIP_CANDIDATE_TYPE,
    RELATIONSHIP_CANDIDATE_VALID_DIRECTIONS,
    RELATIONSHIP_TYPE_AFFILIATED_WITH,
    RELATIONSHIP_TYPE_MEMBER_OF,
    EvidenceRef,
    RelationshipCandidateAccumulator,
)

# RelationshipCandidate抽出の対象とするBlock種別 (Extraction_Pipeline.md §5.4)。
RELATIONSHIP_SOURCE_BLOCK_TYPES = frozenset(
    {"dialogue", "monologue", "narration", "choice"}
)


def build_relationship_candidates(
    episode: dict[str, Any],
    story_id: str,
    episode_id: str,
    extraction_run: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalized Story JSON内で構造的に表現されている関係情報から
    RelationshipCandidateを生成する。

    今回対象とする手がかりは以下の2種類のみ。本文の自然文からの関係推定
    (「友人らしい」「敵対しているらしい」「同じ組織らしい」等) は一切行わない。

    - dialogue/monologue/narration/choice Blockに明示された
      relationshipType + (sourceCandidate/targetCandidate または
      subjectId/objectId) のペア (BlockCommonはadditionalPropertiesを
      許容するため、将来Parserが付与しうる拡張フィールドを想定する。
      OrganizationCandidate等の既存モジュールと同じ前提)
    - episode.speakerAssignments に明示された organizationId/affiliation
      (Character -> Organization の所属候補。organizationId (構造化ID)
      があればMEMBER_OF、organizationName/affiliation (名前のみ) なら
      AFFILIATED_WITHとする)

    同一 source + target + relationshipType の組み合わせは1件に統合し、
    evidenceIdsを集約する。自己参照 (source == target) は生成しない。
    """
    accumulators: dict[tuple[str, str, str], RelationshipCandidateAccumulator] = {}
    order: list[tuple[str, str, str]] = []
    extra_evidence: dict[str, dict[str, Any]] = {}

    for scene in episode.get("scenes", []):
        for block in scene.get("blocks", []):
            _record_block_relationship(accumulators, order, block)

    for assignment in episode.get("speakerAssignments", []) or []:
        _record_assignment_membership(
            accumulators, order, extra_evidence, assignment, story_id, episode_id
        )

    candidates = _finalize_relationship_candidates(
        accumulators, order, episode_id, extraction_run
    )
    return candidates, list(extra_evidence.values())


def _normalize_direction(value: Any) -> str:
    if value in RELATIONSHIP_CANDIDATE_VALID_DIRECTIONS:
        return value
    return RELATIONSHIP_CANDIDATE_DEFAULT_DIRECTION


def _record_block_relationship(
    accumulators: dict[tuple[str, str, str], RelationshipCandidateAccumulator],
    order: list[tuple[str, str, str]],
    block: dict[str, Any],
) -> None:
    """Blockに明示されたrelationshipType + source/targetペアを記録する

    block["id"]はRELATIONSHIP_SOURCE_BLOCK_TYPES (dialogue/monologue/
    narration/choice) であれば常にEVIDENCE_BLOCK_TYPESに含まれるため、
    追加のevidence refは不要。
    """
    if block.get("type") not in RELATIONSHIP_SOURCE_BLOCK_TYPES:
        return

    relationship_type = block.get("relationshipType")
    source = block.get("sourceCandidate") or block.get("subjectId")
    target = block.get("targetCandidate") or block.get("objectId")
    if not relationship_type or not source or not target:
        return
    if source == target:
        # 自己参照Relationshipは生成しない
        return

    key = (source, target, relationship_type)
    existing_relationship_id = block.get("relationshipId")
    direction = _normalize_direction(block.get("direction"))

    if key not in accumulators:
        accumulators[key] = RelationshipCandidateAccumulator(
            source_candidate=source,
            target_candidate=target,
            relationship_type=relationship_type,
            direction=direction,
            is_resolved=bool(existing_relationship_id),
            existing_relationship_id=existing_relationship_id,
        )
        order.append(key)

    accumulator = accumulators[key]
    if existing_relationship_id and not accumulator.existing_relationship_id:
        accumulator.existing_relationship_id = existing_relationship_id
        accumulator.is_resolved = True
    accumulator.add_evidence(block["id"])


def _record_assignment_membership(
    accumulators: dict[tuple[str, str, str], RelationshipCandidateAccumulator],
    order: list[tuple[str, str, str]],
    extra_evidence: dict[str, dict[str, Any]],
    assignment: dict[str, Any],
    story_id: str,
    episode_id: str,
) -> None:
    """speakerAssignmentsに明示されたorganizationId/affiliationから
    Character -> Organization の所属候補を記録する

    speakerAssignmentsはEpisode直下の構造でBlock IDを持たないため、
    Episode ID自体をevidenceとして使う (OrganizationCandidateと同じ扱い)。
    """
    character = (
        assignment.get("speakerId")
        or assignment.get("sourceCharacterId")
        or assignment.get("speakerName")
    )
    organization_id = assignment.get("organizationId")
    organization = (
        organization_id
        or assignment.get("organizationName")
        or assignment.get("affiliation")
    )
    if not character or not organization or character == organization:
        return

    relationship_type = (
        RELATIONSHIP_TYPE_MEMBER_OF
        if organization_id
        else RELATIONSHIP_TYPE_AFFILIATED_WITH
    )
    is_resolved = bool(assignment.get("speakerId")) and bool(organization_id)

    key = (character, organization, relationship_type)
    if key not in accumulators:
        accumulators[key] = RelationshipCandidateAccumulator(
            source_candidate=character,
            target_candidate=organization,
            relationship_type=relationship_type,
            is_resolved=is_resolved,
        )
        order.append(key)

    accumulator = accumulators[key]
    accumulator.is_resolved = accumulator.is_resolved or is_resolved
    accumulator.add_evidence(episode_id)
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


def _finalize_relationship_candidates(
    accumulators: dict[tuple[str, str, str], RelationshipCandidateAccumulator],
    order: list[tuple[str, str, str]],
    episode_id: str,
    extraction_run: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, key in enumerate(order, start=1):
        accumulator = accumulators[key]
        if not accumulator.evidence_ids:
            # Evidenceが1件も無い推測は出力しない (Extraction_Pipeline.md §6.1)
            continue

        candidates.append(
            {
                "id": f"{episode_id}_CAND_REL{index:03d}",
                "type": RELATIONSHIP_CANDIDATE_TYPE,
                "sourceType": RELATIONSHIP_CANDIDATE_SOURCE_TYPE,
                "confidence": (
                    RELATIONSHIP_CANDIDATE_CONFIDENCE_RESOLVED
                    if accumulator.is_resolved
                    else RELATIONSHIP_CANDIDATE_CONFIDENCE_UNRESOLVED
                ),
                "evidenceIds": list(accumulator.evidence_ids),
                "extractionRun": extraction_run,
                "existingRelationshipId": accumulator.existing_relationship_id,
                "sourceCandidate": accumulator.source_candidate,
                "targetCandidate": accumulator.target_candidate,
                "relationshipType": accumulator.relationship_type,
                "direction": accumulator.direction,
                "temporalNote": None,
                "fields": {},
            }
        )
    return candidates
