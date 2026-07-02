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
    LOCATION_CANDIDATE_CONFIDENCE_NAME_ONLY,
    LOCATION_CANDIDATE_CONFIDENCE_RESOLVED,
    LOCATION_CANDIDATE_SOURCE_TYPE,
    LOCATION_CANDIDATE_TYPE,
    ORGANIZATION_CANDIDATE_CONFIDENCE_NAME_ONLY,
    ORGANIZATION_CANDIDATE_CONFIDENCE_RESOLVED,
    ORGANIZATION_CANDIDATE_SOURCE_TYPE,
    ORGANIZATION_CANDIDATE_TYPE,
    SCHEMA_VERSION,
    CharacterCandidateAccumulator,
    EvidenceRef,
    ExtractionRunInfo,
    LocationCandidateAccumulator,
    OrganizationCandidateAccumulator,
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
        locations, location_evidence_refs = self._build_location_candidates(
            episode, story_id, episode_id, extraction_run_dict
        )
        organizations, organization_evidence_refs = self._build_organization_candidates(
            episode, story_id, episode_id, extraction_run_dict
        )

        evidence_index: dict[str, dict[str, Any]] = {}
        for ref in (
            *evidence_refs,
            *location_evidence_refs,
            *organization_evidence_refs,
        ):
            evidence_index.setdefault(ref["sourceId"], ref)

        return {
            "schemaVersion": SCHEMA_VERSION,
            "documentType": DOCUMENT_TYPE,
            "episodeId": episode_id,
            "storyId": story_id,
            "storyCategory": story_category,
            "extractionRun": extraction_run_dict,
            "evidenceIndex": evidence_index,
            "characters": characters,
            "organizations": organizations,
            "locations": locations,
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

    # ----------------------------------------------------------------
    # LocationCandidate (rule-based, 構造的な手がかりのみ)
    # ----------------------------------------------------------------

    def _build_location_candidates(
        self,
        episode: dict[str, Any],
        story_id: str,
        episode_id: str,
        extraction_run: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Scene.locationとstage_direction(background)からLocationCandidateを生成する

        本文の自然文からの場所推定は行わず、以下の構造的な手がかりのみを対象とする。
        - Scene.location (locationId/locationName)
        - directionType: "background" のstage_direction Block
          (locationId/locationNameが明示されていればそれを使い、無ければ
          normalizedCommand/rawCommandをそのまま識別子として使う)

        Scene.location由来の候補はBlock単位の根拠を持たないため、Scene ID自体を
        evidenceとして使う (Extraction_Pipeline.md §6.1のsourceId段階的
        フォールバック)。stage_directionはEVIDENCE_BLOCK_TYPESに含まれないため、
        こちらもBlock IDをevidenceIndexへ追加する必要がある。戻り値の2要素目
        (extra evidence refs) がその追加分。
        """
        accumulators: dict[tuple[str, str], LocationCandidateAccumulator] = {}
        order: list[tuple[str, str]] = []
        extra_evidence: dict[str, dict[str, Any]] = {}

        for scene in episode.get("scenes", []):
            scene_id = scene.get("sceneId")

            self._record_scene_location(
                accumulators,
                order,
                extra_evidence,
                scene,
                scene_id,
                story_id,
                episode_id,
            )

            for block in scene.get("blocks", []):
                self._record_background_location(
                    accumulators,
                    order,
                    extra_evidence,
                    block,
                    scene_id,
                    story_id,
                    episode_id,
                )

        candidates = self._finalize_location_candidates(
            accumulators, order, episode_id, extraction_run
        )
        return candidates, list(extra_evidence.values())

    def _record_scene_location(
        self,
        accumulators: dict[tuple[str, str], LocationCandidateAccumulator],
        order: list[tuple[str, str]],
        extra_evidence: dict[str, dict[str, Any]],
        scene: dict[str, Any],
        scene_id: str | None,
        story_id: str,
        episode_id: str,
    ) -> None:
        """Scene.locationを1件の場所出現として記録する"""
        location = scene.get("location") or {}
        key = _structured_identity_key(
            location.get("locationId"), location.get("locationName")
        )
        if key is None or scene_id is None:
            return

        if key not in accumulators:
            accumulators[key] = LocationCandidateAccumulator(
                location_id=location.get("locationId")
            )
            order.append(key)
        accumulator = accumulators[key]
        accumulator.add_name(location.get("locationName"))
        accumulator.add_scene_ref(scene_id)
        accumulator.add_evidence(scene_id)
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

    def _record_background_location(
        self,
        accumulators: dict[tuple[str, str], LocationCandidateAccumulator],
        order: list[tuple[str, str]],
        extra_evidence: dict[str, dict[str, Any]],
        block: dict[str, Any],
        scene_id: str | None,
        story_id: str,
        episode_id: str,
    ) -> None:
        """directionType: backgroundのstage_direction Blockを場所出現として記録する"""
        if (
            block.get("type") != "stage_direction"
            or block.get("directionType") != "background"
        ):
            return

        bg_location_id = block.get("locationId")
        bg_location_name = (
            block.get("locationName")
            or block.get("normalizedCommand")
            or block.get("rawCommand")
        )
        key = _structured_identity_key(bg_location_id, bg_location_name)
        if key is None:
            return

        if key not in accumulators:
            accumulators[key] = LocationCandidateAccumulator(location_id=bg_location_id)
            order.append(key)
        accumulator = accumulators[key]
        accumulator.add_name(bg_location_name)
        if scene_id is not None:
            accumulator.add_scene_ref(scene_id)

        block_id = block["id"]
        accumulator.add_evidence(block_id)

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

    def _finalize_location_candidates(
        self,
        accumulators: dict[tuple[str, str], LocationCandidateAccumulator],
        order: list[tuple[str, str]],
        episode_id: str,
        extraction_run: dict[str, Any],
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for index, key in enumerate(order, start=1):
            accumulator = accumulators[key]
            if (
                not accumulator.name_candidates
                or not accumulator.evidence_ids
                or not accumulator.scene_refs
            ):
                continue

            is_resolved = accumulator.location_id is not None
            candidates.append(
                {
                    "id": f"{episode_id}_CAND_LOC{index:03d}",
                    "type": LOCATION_CANDIDATE_TYPE,
                    "sourceType": LOCATION_CANDIDATE_SOURCE_TYPE,
                    "confidence": (
                        LOCATION_CANDIDATE_CONFIDENCE_RESOLVED
                        if is_resolved
                        else LOCATION_CANDIDATE_CONFIDENCE_NAME_ONLY
                    ),
                    "evidenceIds": list(accumulator.evidence_ids),
                    "extractionRun": extraction_run,
                    "existingLocationId": accumulator.location_id,
                    "nameCandidates": list(accumulator.name_candidates),
                    "sceneRefs": list(accumulator.scene_refs),
                    "fields": {},
                }
            )
        return candidates

    # ----------------------------------------------------------------
    # OrganizationCandidate (rule-based, 構造的な手がかりのみ)
    # ----------------------------------------------------------------

    def _build_organization_candidates(
        self,
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
                self._record_block_organization(accumulators, order, block)

        for assignment in episode.get("speakerAssignments", []) or []:
            self._record_assignment_organization(
                accumulators, order, extra_evidence, assignment, story_id, episode_id
            )

        candidates = self._finalize_organization_candidates(
            accumulators, order, episode_id, extraction_run
        )
        return candidates, list(extra_evidence.values())

    def _record_block_organization(
        self,
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

        key = _structured_identity_key(
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
        self,
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
        key = _structured_identity_key(org_id, org_name)
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
        self,
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


def _structured_identity_key(
    id_value: str | None, name_value: str | None
) -> tuple[str, str] | None:
    """構造化ID優先、無ければ名前文字列で同一性判定するキーを返す

    LocationCandidate/OrganizationCandidateで共通に使う。
    """
    if id_value:
        return ("id", id_value)
    if name_value:
        return ("name", name_value)
    return None
