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

# LocationCandidate抽出 (Extraction_Result_Schema.md §7) 用の定数。
# Scene.location / stage_direction(background) など構造的な手がかりのみを
# 対象とし、本文の自然文からの場所推定は行わない。
LOCATION_CANDIDATE_TYPE = "location_candidate"
LOCATION_CANDIDATE_SOURCE_TYPE = "script"
LOCATION_CANDIDATE_CONFIDENCE_RESOLVED = 0.9
LOCATION_CANDIDATE_CONFIDENCE_NAME_ONLY = 0.5

# OrganizationCandidate抽出 (Extraction_Result_Schema.md §8) 用の定数。
# 明示的なorganizationId/organizationName/affiliationフィールドのみを対象とし、
# 本文中の固有名詞文字列推定は行わない。
ORGANIZATION_CANDIDATE_TYPE = "organization_candidate"
ORGANIZATION_CANDIDATE_SOURCE_TYPE = "script"
ORGANIZATION_CANDIDATE_CONFIDENCE_RESOLVED = 0.9
ORGANIZATION_CANDIDATE_CONFIDENCE_NAME_ONLY = 0.5

# ItemCandidate抽出 (Extraction_Result_Schema.md §9) 用の定数。
# 明示的なitemId/itemNameフィールドのみを対象とし、本文の自然文からの
# アイテム名推定は行わない。
ITEM_CANDIDATE_TYPE = "item_candidate"
ITEM_CANDIDATE_SOURCE_TYPE = "script"
ITEM_CANDIDATE_CONFIDENCE_RESOLVED = 0.9
ITEM_CANDIDATE_CONFIDENCE_NAME_ONLY = 0.5

# LoreCandidate抽出 (Extraction_Result_Schema.md §10) 用の定数。
# Loreは推定が混ざりやすいため、明示的なloreId/termNameフィールド
# (Block由来のみ) に対象を絞る、最も保守的な抽出とする。
LORE_CANDIDATE_TYPE = "lore_candidate"
LORE_CANDIDATE_SOURCE_TYPE = "script"
LORE_CANDIDATE_CONFIDENCE_RESOLVED = 0.9
LORE_CANDIDATE_CONFIDENCE_NAME_ONLY = 0.5

# EventCandidate抽出 (Extraction_Result_Schema.md §11) 用の定数。
# 明示的なeventId/eventNameフィールドのみを対象とし、会話内容からの
# 出来事推定 (「事件」「戦闘」等) は行わない。
EVENT_CANDIDATE_TYPE = "event_candidate"
EVENT_CANDIDATE_SOURCE_TYPE = "script"
EVENT_CANDIDATE_CONFIDENCE_RESOLVED = 0.9
EVENT_CANDIDATE_CONFIDENCE_NAME_ONLY = 0.5

# RelationshipCandidate抽出 (Extraction_Result_Schema.md §12) 用の定数。
# Block上の明示的なrelationshipType+source/targetペア、または
# speakerAssignmentsの明示的なorganizationId/affiliationのみを対象とし、
# 本文の自然文からの関係推定 (「友人らしい」「敵対しているらしい」等) は行わない。
RELATIONSHIP_CANDIDATE_TYPE = "relationship_candidate"
RELATIONSHIP_CANDIDATE_SOURCE_TYPE = "script"
RELATIONSHIP_CANDIDATE_CONFIDENCE_RESOLVED = 0.9
RELATIONSHIP_CANDIDATE_CONFIDENCE_UNRESOLVED = 0.5
RELATIONSHIP_CANDIDATE_DEFAULT_DIRECTION = "source_to_target"
RELATIONSHIP_CANDIDATE_VALID_DIRECTIONS = frozenset(
    {"source_to_target", "target_to_source", "bidirectional"}
)
# speakerAssignmentsのorganizationId/affiliationから生成する所属候補の
# relationshipType。organizationId (構造化ID) があればMEMBER_OF、
# organizationName/affiliation (名前のみ) の場合はAFFILIATED_WITHとする
# (Extraction_Pipeline.md §4.3)。
RELATIONSHIP_TYPE_MEMBER_OF = "MEMBER_OF"
RELATIONSHIP_TYPE_AFFILIATED_WITH = "AFFILIATED_WITH"


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


@dataclass
class LocationCandidateAccumulator:
    """episode走査中、1場所分の情報を集約する作業用構造体。

    locationId (構造化ID) があれば existingLocationId に使う。
    無ければ locationName (またはstage_directionのコマンド文字列) のみで
    識別する。
    """

    location_id: str | None = None
    name_candidates: list[str] = field(default_factory=list)
    scene_refs: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def add_name(self, name: str | None) -> None:
        if name and name not in self.name_candidates:
            self.name_candidates.append(name)

    def add_scene_ref(self, scene_id: str) -> None:
        if scene_id not in self.scene_refs:
            self.scene_refs.append(scene_id)

    def add_evidence(self, source_id: str) -> None:
        if source_id not in self.evidence_ids:
            self.evidence_ids.append(source_id)


@dataclass
class OrganizationCandidateAccumulator:
    """episode走査中、1組織分の情報を集約する作業用構造体。

    organizationId (構造化ID) があれば existingOrganizationId に使う。
    無ければ organizationName/affiliation のみで識別する。
    """

    organization_id: str | None = None
    name_candidates: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def add_name(self, name: str | None) -> None:
        if name and name not in self.name_candidates:
            self.name_candidates.append(name)

    def add_evidence(self, source_id: str) -> None:
        if source_id not in self.evidence_ids:
            self.evidence_ids.append(source_id)


@dataclass
class ItemCandidateAccumulator:
    """episode走査中、1アイテム分の情報を集約する作業用構造体。

    itemId (構造化ID) があれば existingItemId に使う。
    無ければ itemName のみで識別する。
    """

    item_id: str | None = None
    name_candidates: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def add_name(self, name: str | None) -> None:
        if name and name not in self.name_candidates:
            self.name_candidates.append(name)

    def add_evidence(self, source_id: str) -> None:
        if source_id not in self.evidence_ids:
            self.evidence_ids.append(source_id)


@dataclass
class LoreCandidateAccumulator:
    """episode走査中、1用語分の情報を集約する作業用構造体。

    loreId (構造化ID) があれば existingLoreId に使う。
    無ければ termName のみで識別する。
    """

    lore_id: str | None = None
    term_candidates: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def add_term(self, term: str | None) -> None:
        if term and term not in self.term_candidates:
            self.term_candidates.append(term)

    def add_evidence(self, source_id: str) -> None:
        if source_id not in self.evidence_ids:
            self.evidence_ids.append(source_id)


@dataclass
class EventCandidateAccumulator:
    """episode走査中、1出来事分の情報を集約する作業用構造体。

    eventId (構造化ID) があれば existingEventId に使う。
    無ければ eventName のみで識別する。
    """

    event_id: str | None = None
    name_candidates: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def add_name(self, name: str | None) -> None:
        if name and name not in self.name_candidates:
            self.name_candidates.append(name)

    def add_evidence(self, source_id: str) -> None:
        if source_id not in self.evidence_ids:
            self.evidence_ids.append(source_id)


@dataclass
class RelationshipCandidateAccumulator:
    """episode走査中、1関係 (source+target+relationshipType) 分の情報を
    集約する作業用構造体。

    Block側でrelationshipId (既知Relationship辞書へ解決済み) が明示されて
    いれば existingRelationshipId / 高confidenceに使う。
    """

    source_candidate: str
    target_candidate: str
    relationship_type: str
    direction: str = RELATIONSHIP_CANDIDATE_DEFAULT_DIRECTION
    is_resolved: bool = False
    existing_relationship_id: str | None = None
    evidence_ids: list[str] = field(default_factory=list)

    def add_evidence(self, source_id: str) -> None:
        if source_id not in self.evidence_ids:
            self.evidence_ids.append(source_id)
