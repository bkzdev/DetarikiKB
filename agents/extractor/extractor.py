"""
DKB Extractor - Extractor
Normalized Story JSON (schemas/story.schema.json) から
episode_extraction (schemas/extraction.schema.json) の最小構造を生成する。

LLM呼び出し・OpenAI/Anthropic/Ollama連携・prompt作成はまだ実装しない。
rule-baseで生成するのはcharacters/locations/organizations/items/lore/events/
relationships/timelineCandidates全て。

Candidate種別ごとの抽出ロジックは character.py/location.py/organization.py/
item.py/lore.py/event.py/relationship.py/timeline.py に分割されている。
本ファイルは、各モジュールのbuild_*_candidates() を呼び出して
episode_extraction 1件分を組み立てるオーケストレーションのみを担う。

docs/architecture/06_AI/Extraction_Pipeline.md
docs/architecture/06_AI/Extraction_Result_Schema.md
"""

from __future__ import annotations

from typing import Any

from .base import build_evidence_refs, merge_evidence_index
from .character import (
    build_character_candidates,
    build_special_speaker_label_candidates,
)
from .event import build_event_candidates
from .item import build_item_candidates
from .location import build_location_candidates
from .lore import build_lore_candidates
from .models import DOCUMENT_TYPE, SCHEMA_VERSION, ExtractionRunInfo
from .organization import build_organization_candidates
from .relationship import build_relationship_candidates
from .timeline import build_timeline_candidates


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
        story_title = story_json.get("metadata", {}).get("storyTitle")

        return [
            self.extract_episode(
                episode,
                story_id=story_id,
                story_category=story_category,
                parser_compatibility=parser_compatibility,
                story_title=story_title,
            )
            for episode in story_json.get("episodes", [])
        ]

    def extract_episode(
        self,
        episode: dict[str, Any],
        story_id: str,
        story_category: str,
        parser_compatibility: str = "compatible",
        story_title: str | None = None,
    ) -> dict[str, Any]:
        """1エピソード分のepisode_extraction (Extraction_Result_Schema.md §3.2)

        story_titleおよびepisode["metadata"]のepisodeSubtitle/displayTitle/
        metadataStatusは、story_manifest.yaml経由でNormalized Story JSONへ
        既に反映済みの値をそのまま転記するのみで、DEC本文からの推測は
        行わない (Story_Manifest_Design.md §11.1、§14)。
        """
        episode_id = episode["episodeId"]
        episode_metadata = episode.get("metadata") or {}

        evidence_refs = build_evidence_refs(episode, story_id, episode_id)
        extraction_run = ExtractionRunInfo(
            parser_compatibility_at_extraction=parser_compatibility
        )
        extraction_run_dict = extraction_run.to_dict()

        characters = build_character_candidates(
            episode, episode_id, extraction_run_dict
        )
        special_speaker_labels = build_special_speaker_label_candidates(
            episode, episode_id, extraction_run_dict
        )
        locations, location_evidence_refs = build_location_candidates(
            episode, story_id, episode_id, extraction_run_dict
        )
        organizations, organization_evidence_refs = build_organization_candidates(
            episode, story_id, episode_id, extraction_run_dict
        )
        items, item_evidence_refs = build_item_candidates(
            episode, story_id, episode_id, extraction_run_dict
        )
        lore = build_lore_candidates(episode, episode_id, extraction_run_dict)
        events, event_evidence_refs = build_event_candidates(
            episode, story_id, episode_id, extraction_run_dict
        )
        relationships, relationship_evidence_refs = build_relationship_candidates(
            episode, story_id, episode_id, extraction_run_dict
        )
        timeline_candidates, timeline_evidence_refs = build_timeline_candidates(
            episode, story_id, episode_id, extraction_run_dict
        )

        evidence_index = merge_evidence_index(
            evidence_refs,
            location_evidence_refs,
            organization_evidence_refs,
            item_evidence_refs,
            event_evidence_refs,
            relationship_evidence_refs,
            timeline_evidence_refs,
        )

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
            "items": items,
            "lore": lore,
            "events": events,
            "relationships": relationships,
            "timelineCandidates": timeline_candidates,
            "specialSpeakerLabelCandidates": special_speaker_labels,
            "extractionErrors": [],
            "storyTitle": story_title,
            "episodeSubtitle": episode_metadata.get("episodeSubtitle"),
            "displayTitle": episode_metadata.get("displayTitle"),
            "metadataStatus": episode_metadata.get("metadataStatus"),
        }
