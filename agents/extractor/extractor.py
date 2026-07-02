"""
DKB Extractor - Extractor
Normalized Story JSON (schemas/story.schema.json) から
episode_extraction (schemas/extraction.schema.json) の最小構造を生成する。

LLM呼び出し・OpenAI/Anthropic/Ollama連携・prompt作成はまだ実装しない。
候補配列 (characters/organizations/locations/items/lore/events/relationships/
timelineCandidates) は空のまま出力する。

docs/architecture/06_AI/Extraction_Pipeline.md
docs/architecture/06_AI/Extraction_Result_Schema.md
"""

from __future__ import annotations

from typing import Any

from .models import (
    CHARACTER_CANDIDATE_CONFIDENCE_RESOLVED,
    CHARACTER_CANDIDATE_CONFIDENCE_UNRESOLVED,
    CHARACTER_CANDIDATE_SOURCE_TYPE,
    CHARACTER_CANDIDATE_TYPE,
    DEFAULT_EVIDENCE_CONFIDENCE,
    DOCUMENT_TYPE,
    EVIDENCE_BLOCK_TYPES,
    SCHEMA_VERSION,
    CharacterCandidateAccumulator,
    EvidenceRef,
    ExtractionRunInfo,
)

# CharacterCandidate抽出の対象とするBlock種別 (Extraction_Pipeline.md §5.4)。
# choice内の話者は今回のスコープでは対象外とする。
CHARACTER_SOURCE_BLOCK_TYPES = frozenset({"dialogue", "monologue"})


class Extractor:
    """Normalized Story JSONからepisode_extractionの最小構造を生成する。"""

    def extract_story(self, story_json: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalized Story JSON内の全EpisodeについてepisodeExtractionを生成する

        Extraction_Pipeline.md §2.2: 1エピソードJSON = 1回の抽出実行の最小入力単位
        """
        story_id = story_json["storyId"]
        story_category = story_json["storyCategory"]
        parser_compatibility = story_json.get("compatibilityReport", {}).get(
            "parserCompatibility", "compatible"
        )

        return [
            self.extract_episode(
                episode,
                story_id=story_id,
                story_category=story_category,
                parser_compatibility=parser_compatibility,
            )
            for episode in story_json.get("episodes", [])
        ]

    def extract_episode(
        self,
        episode: dict[str, Any],
        story_id: str,
        story_category: str,
        parser_compatibility: str = "compatible",
    ) -> dict[str, Any]:
        """1エピソード分のepisode_extraction (Extraction_Result_Schema.md §3.2)"""
        episode_id = episode["episodeId"]

        evidence_refs = self._build_evidence_refs(episode, story_id, episode_id)
        extraction_run = ExtractionRunInfo(
            parser_compatibility_at_extraction=parser_compatibility
        )
        extraction_run_dict = extraction_run.to_dict()

        characters = self._build_character_candidates(
            episode, episode_id, extraction_run_dict
        )

        return {
            "schemaVersion": SCHEMA_VERSION,
            "documentType": DOCUMENT_TYPE,
            "episodeId": episode_id,
            "storyId": story_id,
            "storyCategory": story_category,
            "extractionRun": extraction_run_dict,
            "evidenceIndex": {ref["sourceId"]: ref for ref in evidence_refs},
            "characters": characters,
            "organizations": [],
            "locations": [],
            "items": [],
            "lore": [],
            "events": [],
            "relationships": [],
            "timelineCandidates": [],
            "extractionErrors": [],
        }

    # ----------------------------------------------------------------
    # evidenceIndex
    # ----------------------------------------------------------------

    def _build_evidence_refs(
        self, episode: dict[str, Any], story_id: str, episode_id: str
    ) -> list[dict[str, Any]]:
        """dialogue/monologue/narration/choice BlockからEvidenceRefを収集する

        Extraction_Pipeline.md §5.4: 抽出対象として直接読むのは
        dialogue/monologue/narration/choiceの4種。unknownは対象外。
        """
        refs: list[dict[str, Any]] = []
        for scene in episode.get("scenes", []):
            scene_id = scene.get("sceneId")
            for block in scene.get("blocks", []):
                refs.extend(
                    self._evidence_from_block(block, story_id, episode_id, scene_id)
                )
        return refs

    def _evidence_from_block(
        self,
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
                    self._evidence_from_block(
                        inner_block, story_id, episode_id, scene_id
                    )
                )

        return refs

    # ----------------------------------------------------------------
    # CharacterCandidate (rule-based, LLM不使用)
    # ----------------------------------------------------------------

    def _build_character_candidates(
        self,
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
        slot_lookup = self._build_slot_lookup(episode)

        accumulators: dict[tuple[str, str], CharacterCandidateAccumulator] = {}
        order: list[tuple[str, str]] = []

        for scene in episode.get("scenes", []):
            for block in scene.get("blocks", []):
                if block.get("type") not in CHARACTER_SOURCE_BLOCK_TYPES:
                    continue

                speaker = self._resolve_speaker(block.get("speaker"), slot_lookup)
                if speaker is None:
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

    def _build_slot_lookup(self, episode: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """episode.speakerAssignmentsを slot -> assignment のdictへ変換する"""
        lookup: dict[str, dict[str, Any]] = {}
        for assignment in episode.get("speakerAssignments", []) or []:
            slot = assignment.get("slot")
            if slot is None:
                continue
            lookup[str(slot)] = assignment
        return lookup

    def _resolve_speaker(
        self,
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
