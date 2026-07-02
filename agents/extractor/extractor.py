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
    DEFAULT_EVIDENCE_CONFIDENCE,
    DOCUMENT_TYPE,
    EVIDENCE_BLOCK_TYPES,
    SCHEMA_VERSION,
    EvidenceRef,
    ExtractionRunInfo,
)


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

        return {
            "schemaVersion": SCHEMA_VERSION,
            "documentType": DOCUMENT_TYPE,
            "episodeId": episode_id,
            "storyId": story_id,
            "storyCategory": story_category,
            "extractionRun": extraction_run.to_dict(),
            "evidenceIndex": {ref["sourceId"]: ref for ref in evidence_refs},
            "characters": [],
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
