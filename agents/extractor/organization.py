"""
DKB Extractor - OrganizationCandidate
明示的なorganizationId/organizationName/affiliationからrule-baseで
OrganizationCandidateの最小構造を生成する。

docs/architecture/06_AI/Extraction_Result_Schema.md §8
"""

from __future__ import annotations

from typing import Any

from .base import structured_identity_key
from .models import (
    DEFAULT_EVIDENCE_CONFIDENCE,
    EVIDENCE_BLOCK_TYPES,
    ORGANIZATION_CANDIDATE_CONFIDENCE_NAME_ONLY,
    ORGANIZATION_CANDIDATE_CONFIDENCE_RESOLVED,
    ORGANIZATION_CANDIDATE_SOURCE_TYPE,
    ORGANIZATION_CANDIDATE_TYPE,
    EvidenceRef,
    OrganizationCandidateAccumulator,
)


def build_organization_candidates(
    episode: dict[str, Any],
    story_id: str,
    episode_id: str,
    extraction_run: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """明示的なorganizationId/organizationName/affiliationからOrganizationCandidateを生成する

    本文中の固有名詞 (「○○隊」等) の文字列推定は行わず、以下の構造的な
    手がかりのみを対象とする。
    - dialogue/monologue/narration/choice Blockに明示された
      organizationId/organizationName (BlockCommonはadditionalProperties
      を許容するため、将来Parserが付与しうる拡張フィールドを想定する)
    - episode.speakerAssignments に明示された
      organizationId/organizationName/affiliation
      (speakerAssignmentsはEpisode直下の構造のため、Episode IDを
      evidenceとして使う)

    story/episode metadataのrelatedOrganizations相当は今回のスコープ外
    (Extraction_Pipeline.md的には妥当な手がかりだが、evidence粒度が
    Story/Episode単位のみとなり検証が難しいため、まずはBlock/Episode単位
    で根拠が取れるものに限定する)。
    """
    accumulators: dict[tuple[str, str], OrganizationCandidateAccumulator] = {}
    order: list[tuple[str, str]] = []
    extra_evidence: dict[str, dict[str, Any]] = {}

    for scene in episode.get("scenes", []):
        for block in scene.get("blocks", []):
            _record_block_organization(accumulators, order, block)

    for assignment in episode.get("speakerAssignments", []) or []:
        _record_assignment_organization(
            accumulators, order, extra_evidence, assignment, story_id, episode_id
        )

    candidates = _finalize_organization_candidates(
        accumulators, order, episode_id, extraction_run
    )
    return candidates, list(extra_evidence.values())


def _record_block_organization(
    accumulators: dict[tuple[str, str], OrganizationCandidateAccumulator],
    order: list[tuple[str, str]],
    block: dict[str, Any],
) -> None:
    """Blockに明示されたorganizationId/organizationNameを記録する

    block["id"]はEVIDENCE_BLOCK_TYPES (dialogue/monologue/narration/choice)
    であれば既にevidenceIndexに含まれるため、追加のevidence refは不要。
    """
    if block.get("type") not in EVIDENCE_BLOCK_TYPES:
        return

    key = structured_identity_key(
        block.get("organizationId"), block.get("organizationName")
    )
    if key is None:
        return

    if key not in accumulators:
        accumulators[key] = OrganizationCandidateAccumulator(
            organization_id=block.get("organizationId")
        )
        order.append(key)
    accumulator = accumulators[key]
    accumulator.add_name(block.get("organizationName"))
    accumulator.add_evidence(block["id"])


def _record_assignment_organization(
    accumulators: dict[tuple[str, str], OrganizationCandidateAccumulator],
    order: list[tuple[str, str]],
    extra_evidence: dict[str, dict[str, Any]],
    assignment: dict[str, Any],
    story_id: str,
    episode_id: str,
) -> None:
    """speakerAssignmentsに明示されたorganizationId/organizationName/affiliationを記録する

    speakerAssignmentsはEpisode直下の構造でBlock IDを持たないため、
    Episode ID自体をevidenceとして使う。
    """
    org_id = assignment.get("organizationId")
    org_name = assignment.get("organizationName") or assignment.get("affiliation")
    key = structured_identity_key(org_id, org_name)
    if key is None:
        return

    if key not in accumulators:
        accumulators[key] = OrganizationCandidateAccumulator(organization_id=org_id)
        order.append(key)
    accumulator = accumulators[key]
    accumulator.add_name(org_name)
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


def _finalize_organization_candidates(
    accumulators: dict[tuple[str, str], OrganizationCandidateAccumulator],
    order: list[tuple[str, str]],
    episode_id: str,
    extraction_run: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, key in enumerate(order, start=1):
        accumulator = accumulators[key]
        if not accumulator.name_candidates or not accumulator.evidence_ids:
            continue

        is_resolved = accumulator.organization_id is not None
        candidates.append(
            {
                "id": f"{episode_id}_CAND_ORG{index:03d}",
                "type": ORGANIZATION_CANDIDATE_TYPE,
                "sourceType": ORGANIZATION_CANDIDATE_SOURCE_TYPE,
                "confidence": (
                    ORGANIZATION_CANDIDATE_CONFIDENCE_RESOLVED
                    if is_resolved
                    else ORGANIZATION_CANDIDATE_CONFIDENCE_NAME_ONLY
                ),
                "evidenceIds": list(accumulator.evidence_ids),
                "extractionRun": extraction_run,
                "existingOrganizationId": accumulator.organization_id,
                "nameCandidates": list(accumulator.name_candidates),
                "fields": {},
            }
        )
    return candidates
