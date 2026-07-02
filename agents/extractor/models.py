"""
DKB Extractor - Models
Extraction Phase Stage A (episode_extraction) の出力に使う定数・データ構造。

docs/architecture/06_AI/Extraction_Pipeline.md
docs/architecture/06_AI/Extraction_Result_Schema.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "0.1"
DOCUMENT_TYPE = "episode_extraction"
EXTRACTOR_VERSION = "0.1.0"

# Extraction_Pipeline.md §5.4: 抽出対象として直接読むBlock種別
# (stage_directionは補助的手がかりに留め、unknownは対象外)
EVIDENCE_BLOCK_TYPES = frozenset({"dialogue", "monologue", "narration", "choice"})

# BlockのsourceにconfidenceがないときのEvidenceRef既定値
DEFAULT_EVIDENCE_CONFIDENCE = 1.0

# CharacterCandidate抽出 (Extraction_Result_Schema.md §6) 用の定数。
# ルールベース抽出のため sourceType は "script"
# (Extraction_Pipeline.md §7.1: 本文中に明記された情報の抽出に使う区分)。
CHARACTER_CANDIDATE_TYPE = "character_candidate"
CHARACTER_CANDIDATE_SOURCE_TYPE = "script"
# speakerId (既知キャラクター辞書へ解決済み) がある場合は高め、
# speakerName/sourceCharacterIdのみ (未解決) の場合はやや低めのconfidenceにする。
CHARACTER_CANDIDATE_CONFIDENCE_RESOLVED = 0.9
CHARACTER_CANDIDATE_CONFIDENCE_UNRESOLVED = 0.5


@dataclass
class ExtractionRunInfo:
    """extractionRun (Extraction_Result_Schema.md §3.2)。

    LLM呼び出しはまだ実装していないため、extraction_methodの既定値は
    "rule_based" とし、model_provider/model_name/prompt_version/
    extracted_at は常にNoneのまま出力する。
    """

    parser_compatibility_at_extraction: str
    extraction_version: str = EXTRACTOR_VERSION
    extraction_method: str = "rule_based"
    model_provider: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    extracted_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "extractionVersion": self.extraction_version,
            "extractionMethod": self.extraction_method,
            "modelProvider": self.model_provider,
            "modelName": self.model_name,
            "promptVersion": self.prompt_version,
            "extractedAt": self.extracted_at,
            "parserCompatibilityAtExtraction": self.parser_compatibility_at_extraction,
        }


@dataclass
class EvidenceRef:
    """EvidenceRef (Extraction_Result_Schema.md §5.1)。evidenceIndexの1エントリ。"""

    source_id: str
    story_id: str
    episode_id: str
    scene_id: str | None
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourceId": self.source_id,
            "storyId": self.story_id,
            "episodeId": self.episode_id,
            "sceneId": self.scene_id,
            "confidence": self.confidence,
        }


@dataclass
class CharacterCandidateAccumulator:
    """episode走査中、1キャラクター分の情報を集約する作業用構造体。

    speakerId (解決済みcanonical Character ID) があれば existingCharacterId
    に使う。なければ sourceCharacterId、それも無ければ speakerName のみで
    識別する (未解決キャラクター)。
    """

    speaker_id: str | None = None
    source_character_id: str | None = None
    name_candidates: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def add_name(self, name: str | None) -> None:
        if name and name not in self.name_candidates:
            self.name_candidates.append(name)

    def add_evidence(self, block_id: str) -> None:
        if block_id not in self.evidence_ids:
            self.evidence_ids.append(block_id)
