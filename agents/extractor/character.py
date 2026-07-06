"""
DKB Extractor - CharacterCandidate
speakerAssignments/dialogue/monologue Blockからrule-baseで
CharacterCandidateの最小構造を生成する。

docs/architecture/06_AI/Extraction_Result_Schema.md §6
"""

from __future__ import annotations

from typing import Any

from agents.parser.speaker_labels import is_special_label_type

from .models import (
    CHARACTER_CANDIDATE_CONFIDENCE_RESOLVED,
    CHARACTER_CANDIDATE_CONFIDENCE_UNRESOLVED,
    CHARACTER_CANDIDATE_SOURCE_TYPE,
    CHARACTER_CANDIDATE_TYPE,
    SPECIAL_SPEAKER_LABEL_CANDIDATE_TYPE,
    SPECIAL_SPEAKER_LABEL_CONFIDENCE,
    SPECIAL_SPEAKER_LABEL_SOURCE_TYPE,
    CharacterCandidateAccumulator,
    SpecialSpeakerLabelAccumulator,
)

# CharacterCandidate抽出の対象とするBlock種別 (Extraction_Pipeline.md §5.4)。
# choice内の話者は今回のスコープでは対象外とする。
CHARACTER_SOURCE_BLOCK_TYPES = frozenset({"dialogue", "monologue"})


def _speaker_label_analysis(speaker: dict[str, Any]) -> dict[str, Any] | None:
    return speaker.get("labelAnalysis")


def build_character_candidates(
    episode: dict[str, Any],
    episode_id: str,
    extraction_run: dict[str, Any],
) -> list[dict[str, Any]]:
    """speakerAssignments/dialogue/monologue Blockからrule-baseで
    CharacterCandidateの最小構造を生成する。

    同一speakerId (無ければsourceCharacterId、それも無ければ
    speakerName) を持つ話者は1件のcandidateへ統合し、発言した
    Block IDをすべてevidenceIdsへ集める。choice内の話者は今回の
    スコープでは対象外とする (Extraction_Pipeline.md §5.4)。
    """
    slot_lookup = _build_slot_lookup(episode)

    accumulators: dict[tuple[str, str], CharacterCandidateAccumulator] = {}
    order: list[tuple[str, str]] = []

    for scene in episode.get("scenes", []):
        for block in scene.get("blocks", []):
            if block.get("type") not in CHARACTER_SOURCE_BLOCK_TYPES:
                continue

            speaker = _resolve_speaker(block.get("speaker"), slot_lookup)
            if speaker is None:
                continue

            label_analysis = _speaker_label_analysis(speaker)
            if label_analysis and is_special_label_type(
                label_analysis.get("labelType", "")
            ):
                # name command/@ChTalkName由来のspeaker group/modifier付き/
                # generic表記等は、通常のCharacterCandidateには混ぜない
                # (build_special_speaker_label_candidatesで別途扱う)。
                continue

            key = _character_identity_key(speaker)
            if key is None:
                continue

            if key not in accumulators:
                accumulators[key] = CharacterCandidateAccumulator(
                    speaker_id=speaker.get("speakerId"),
                    source_character_id=speaker.get("sourceCharacterId"),
                )
                order.append(key)

            accumulator = accumulators[key]
            accumulator.add_name(speaker.get("speakerName"))
            accumulator.add_evidence(block["id"])

    candidates: list[dict[str, Any]] = []
    for index, key in enumerate(order, start=1):
        accumulator = accumulators[key]
        if not accumulator.name_candidates or not accumulator.evidence_ids:
            # Evidenceや名前候補が1件も無い推測は出力しない
            # (Extraction_Pipeline.md §6.1)
            continue

        is_resolved = accumulator.speaker_id is not None
        candidates.append(
            {
                "id": f"{episode_id}_CAND_CHAR{index:03d}",
                "type": CHARACTER_CANDIDATE_TYPE,
                "sourceType": CHARACTER_CANDIDATE_SOURCE_TYPE,
                "confidence": (
                    CHARACTER_CANDIDATE_CONFIDENCE_RESOLVED
                    if is_resolved
                    else CHARACTER_CANDIDATE_CONFIDENCE_UNRESOLVED
                ),
                "evidenceIds": list(accumulator.evidence_ids),
                "extractionRun": extraction_run,
                "existingCharacterId": accumulator.speaker_id,
                "sourceCharacterId": accumulator.source_character_id,
                "nameCandidates": list(accumulator.name_candidates),
                "fields": {},
            }
        )
    return candidates


def _build_slot_lookup(episode: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """episode.speakerAssignmentsを slot -> assignment のdictへ変換する"""
    lookup: dict[str, dict[str, Any]] = {}
    for assignment in episode.get("speakerAssignments", []) or []:
        slot = assignment.get("slot")
        if slot is None:
            continue
        lookup[str(slot)] = assignment
    return lookup


def _resolve_speaker(
    speaker: dict[str, Any] | None,
    slot_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Blockのspeakerに、同じslotのspeakerAssignmentsの情報を補完する

    Block自体のspeakerが未解決 (speakerId/speakerName/sourceCharacterId
    が欠けている) でも、episode.speakerAssignmentsに同じslotの
    割り当て記録があればそこから補う。
    """
    if speaker is None:
        return None

    resolved = dict(speaker)
    slot = resolved.get("slot")
    if slot is not None:
        assignment = slot_lookup.get(str(slot))
        if assignment:
            for field_name in ("speakerId", "speakerName", "sourceCharacterId"):
                if not resolved.get(field_name):
                    resolved[field_name] = assignment.get(field_name)
    return resolved


def _character_identity_key(speaker: dict[str, Any]) -> tuple[str, str] | None:
    """話者の同一性判定キーを返す

    優先順位: speakerId > sourceCharacterId > speakerName
    """
    speaker_id = speaker.get("speakerId")
    if speaker_id:
        return ("speakerId", speaker_id)

    source_character_id = speaker.get("sourceCharacterId")
    if source_character_id:
        return ("sourceCharacterId", source_character_id)

    speaker_name = speaker.get("speakerName")
    if speaker_name:
        return ("speakerName", speaker_name)

    return None


def build_special_speaker_label_candidates(
    episode: dict[str, Any],
    episode_id: str,
    extraction_run: dict[str, Any],
) -> list[dict[str, Any]]:
    """dialogue/monologue Blockのうち、name command/@ChTalkName由来の
    speaker labelでspeaker_labels.is_special_label_typeがTrueのものから、
    SpecialSpeakerLabelCandidateを生成する。

    通常のCharacterCandidateとは別配列 (episode_extraction.
    specialSpeakerLabelCandidates) に出力し、自動でconfirmed character
    解決は行わない。同一rawLabelを持つ発話は1件のcandidateへ統合し、
    発言したBlock IDをすべてevidenceIdsへ集める。
    """
    slot_lookup = _build_slot_lookup(episode)

    accumulators: dict[str, SpecialSpeakerLabelAccumulator] = {}
    order: list[str] = []

    for scene in episode.get("scenes", []):
        for block in scene.get("blocks", []):
            if block.get("type") not in CHARACTER_SOURCE_BLOCK_TYPES:
                continue

            speaker = _resolve_speaker(block.get("speaker"), slot_lookup)
            if speaker is None:
                continue

            label_analysis = _speaker_label_analysis(speaker)
            if not label_analysis or not is_special_label_type(
                label_analysis.get("labelType", "")
            ):
                continue

            raw_label = label_analysis.get("rawLabel") or speaker.get("speakerName")
            if not raw_label:
                continue

            if raw_label not in accumulators:
                accumulators[raw_label] = SpecialSpeakerLabelAccumulator(
                    label_analysis=label_analysis
                )
                order.append(raw_label)

            accumulators[raw_label].add_evidence(block["id"])

    candidates: list[dict[str, Any]] = []
    for index, raw_label in enumerate(order, start=1):
        accumulator = accumulators[raw_label]
        if not accumulator.evidence_ids:
            # Evidenceを1件も持たない推測は出力しない (Extraction_Pipeline.md §6.1)
            continue

        analysis = accumulator.label_analysis
        candidates.append(
            {
                "id": f"{episode_id}_CAND_SSL{index:03d}",
                "type": SPECIAL_SPEAKER_LABEL_CANDIDATE_TYPE,
                "sourceType": SPECIAL_SPEAKER_LABEL_SOURCE_TYPE,
                "confidence": SPECIAL_SPEAKER_LABEL_CONFIDENCE,
                "evidenceIds": list(accumulator.evidence_ids),
                "extractionRun": extraction_run,
                "rawLabel": analysis.get("rawLabel"),
                "labelSource": analysis.get("source"),
                "labelType": analysis.get("labelType"),
                "components": list(analysis.get("components", []) or []),
                "modifier": analysis.get("modifier"),
                "baseLabel": analysis.get("baseLabel"),
                "inferredSpeakers": list(analysis.get("inferredSpeakers", []) or []),
                "resolutionStatus": analysis.get("resolutionStatus"),
            }
        )
    return candidates
