"""
DKB Wiki Generator - Evidence Index loader
`knowledge/evidence/stories/{storyId}.yaml`（Public Evidence Index）を
読み込み・検証する。

`docs/architecture/06_AI/Evidence_Index_Design.md`で決定した設計をそのまま
実装する。**このモジュールはrenderer統合を行わない**（Evidence page生成・
Story Summary/Episode SummaryのevidenceRefsリンク化は後続PR
`evidence-index-renderer-integration`）。Normalized Story JSON/Extraction
ResultからのEvidence Index自動生成もこのモジュールの対象外
（`evidence-index-generation-dry-run`）。

Internal Review Evidence Packet（raw textを含みうる内部review用データ）は
このモジュールの対象外。Public Evidence Indexのみを扱う。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

EVIDENCE_TYPE_DIALOGUE = "dialogue"
EVIDENCE_TYPE_MONOLOGUE = "monologue"
EVIDENCE_TYPE_NARRATION = "narration"
EVIDENCE_TYPE_CHOICE = "choice"
EVIDENCE_TYPE_STAGE_DIRECTION = "stage_direction"
EVIDENCE_TYPE_SPEAKER_LABEL = "speaker_label"
EVIDENCE_TYPE_SCENE = "scene"
EVIDENCE_TYPE_EPISODE = "episode"
EVIDENCE_TYPE_STORY = "story"
EVIDENCE_TYPE_UNKNOWN = "unknown"

VALID_EVIDENCE_TYPES = frozenset(
    {
        EVIDENCE_TYPE_DIALOGUE,
        EVIDENCE_TYPE_MONOLOGUE,
        EVIDENCE_TYPE_NARRATION,
        EVIDENCE_TYPE_CHOICE,
        EVIDENCE_TYPE_STAGE_DIRECTION,
        EVIDENCE_TYPE_SPEAKER_LABEL,
        EVIDENCE_TYPE_SCENE,
        EVIDENCE_TYPE_EPISODE,
        EVIDENCE_TYPE_STORY,
        EVIDENCE_TYPE_UNKNOWN,
    }
)

RESOLUTION_STATUS_RESOLVED = "resolved"
RESOLUTION_STATUS_UNRESOLVED = "unresolved"
RESOLUTION_STATUS_AMBIGUOUS = "ambiguous"
RESOLUTION_STATUS_UNKNOWN = "unknown"

VALID_RESOLUTION_STATUSES = frozenset(
    {
        RESOLUTION_STATUS_RESOLVED,
        RESOLUTION_STATUS_UNRESOLVED,
        RESOLUTION_STATUS_AMBIGUOUS,
        RESOLUTION_STATUS_UNKNOWN,
    }
)

VALID_ENTITY_TYPES = frozenset(
    {
        "character",
        "location",
        "organization",
        "item",
        "lore",
        "event",
        "relationship",
    }
)

VALID_SUMMARY_TYPES = frozenset({"story", "episode"})

ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

# raw text / source text禁止文字列 (Evidence_Index_Design.md §6、
# agents/wiki_generator/story_summaries.pyのFORBIDDEN_TEXT_PATTERNSと
# 同じ方針に、HTML/scriptタグ混入検出を加えたもの)。
FORBIDDEN_TEXT_PATTERNS: tuple[str, ...] = (
    ".dec",
    "@ChTalk",
    "@ChTalkMono",
    "@ChTalkName",
    "@Scenario",
    "@ScenarioCos",
    "$num",
    "C:\\",
    "D:\\",
    "/Users/",
    "/home/",
    "<script",
    "</script>",
)


@dataclass
class NormalizedStoryRef:
    story_id: str
    episode_id: str | None = None


@dataclass
class GeneratedFrom:
    normalized_story_refs: list[NormalizedStoryRef] = field(default_factory=list)
    extraction_refs: list[str] = field(default_factory=list)


@dataclass
class Speaker:
    speaker_id: str | None = None
    display_name: str | None = None
    resolution_status: str = RESOLUTION_STATUS_UNKNOWN


@dataclass
class RelatedEntity:
    entity_type: str
    id: str
    display_name: str | None = None


@dataclass
class SummaryReference:
    story_id: str
    summary_type: str
    episode_id: str | None = None


@dataclass
class CandidateReference:
    candidate_id: str
    entity_type: str


@dataclass
class ReferencedBy:
    summaries: list[SummaryReference] = field(default_factory=list)
    candidates: list[CandidateReference] = field(default_factory=list)


@dataclass
class Visibility:
    public: bool = True
    raw_text_included: bool = False


@dataclass
class EvidenceIndexEntry:
    evidence_id: str
    evidence_type: str
    story_id: str
    episode_id: str
    visibility: Visibility = field(default_factory=Visibility)
    public_story_id: str | None = None
    public_episode_id: str | None = None
    public_evidence_id: str | None = None
    scene_id: str | None = None
    block_id: str | None = None
    speaker: Speaker | None = None
    related_entities: list[RelatedEntity] = field(default_factory=list)
    referenced_by: ReferencedBy | None = None
    notes: str | None = None


@dataclass
class EvidenceIndexDocument:
    """`knowledge/evidence/stories/{storyId}.yaml` 1ファイル分。"""

    evidence_index_version: int = 1
    generated_from: GeneratedFrom | None = None
    entries: list[EvidenceIndexEntry] = field(default_factory=list)
    notes: str | None = None


@dataclass
class EvidenceIndexCollection:
    """複数のEvidenceIndexDocumentをまとめたコンテナ (directory loadの結果)。"""

    documents: list[EvidenceIndexDocument] = field(default_factory=list)


def _parse_normalized_story_ref(raw: dict[str, Any]) -> NormalizedStoryRef:
    return NormalizedStoryRef(
        story_id=raw.get("storyId", ""), episode_id=raw.get("episodeId")
    )


def _parse_generated_from(raw: dict[str, Any] | None) -> GeneratedFrom | None:
    if raw is None:
        return None
    return GeneratedFrom(
        normalized_story_refs=[
            _parse_normalized_story_ref(r)
            for r in raw.get("normalizedStoryRefs", []) or []
        ],
        extraction_refs=list(raw.get("extractionRefs", []) or []),
    )


def _parse_speaker(raw: dict[str, Any] | None) -> Speaker | None:
    if raw is None:
        return None
    return Speaker(
        speaker_id=raw.get("speakerId"),
        display_name=raw.get("displayName"),
        resolution_status=raw.get("resolutionStatus", RESOLUTION_STATUS_UNKNOWN),
    )


def _parse_related_entity(raw: dict[str, Any]) -> RelatedEntity:
    return RelatedEntity(
        entity_type=raw.get("entityType", ""),
        id=raw.get("id", ""),
        display_name=raw.get("displayName"),
    )


def _parse_summary_reference(raw: dict[str, Any]) -> SummaryReference:
    return SummaryReference(
        story_id=raw.get("storyId", ""),
        summary_type=raw.get("summaryType", ""),
        episode_id=raw.get("episodeId"),
    )


def _parse_candidate_reference(raw: dict[str, Any]) -> CandidateReference:
    return CandidateReference(
        candidate_id=raw.get("candidateId", ""),
        entity_type=raw.get("entityType", ""),
    )


def _parse_referenced_by(raw: dict[str, Any] | None) -> ReferencedBy | None:
    if raw is None:
        return None
    return ReferencedBy(
        summaries=[_parse_summary_reference(r) for r in raw.get("summaries", []) or []],
        candidates=[
            _parse_candidate_reference(r) for r in raw.get("candidates", []) or []
        ],
    )


def _parse_visibility(raw: dict[str, Any] | None) -> Visibility:
    if raw is None:
        return Visibility()
    return Visibility(
        public=raw.get("public", True),
        raw_text_included=raw.get("rawTextIncluded", False),
    )


def _parse_entry(raw: dict[str, Any]) -> EvidenceIndexEntry:
    return EvidenceIndexEntry(
        evidence_id=raw.get("evidenceId", ""),
        evidence_type=raw.get("evidenceType", ""),
        story_id=raw.get("storyId", ""),
        episode_id=raw.get("episodeId", ""),
        visibility=_parse_visibility(raw.get("visibility")),
        public_story_id=raw.get("publicStoryId"),
        public_episode_id=raw.get("publicEpisodeId"),
        public_evidence_id=raw.get("publicEvidenceId"),
        scene_id=raw.get("sceneId"),
        block_id=raw.get("blockId"),
        speaker=_parse_speaker(raw.get("speaker")),
        related_entities=[
            _parse_related_entity(r) for r in raw.get("relatedEntities", []) or []
        ],
        referenced_by=_parse_referenced_by(raw.get("referencedBy")),
        notes=raw.get("notes"),
    )


def parse_evidence_index_document(raw: dict[str, Any]) -> EvidenceIndexDocument:
    """辞書 (YAML/JSONをloadした結果) から`EvidenceIndexDocument`を組み立てる。"""
    return EvidenceIndexDocument(
        evidence_index_version=raw.get("evidenceIndexVersion", 1),
        generated_from=_parse_generated_from(raw.get("generatedFrom")),
        entries=[_parse_entry(e) for e in raw.get("entries", []) or []],
        notes=raw.get("notes"),
    )


def load_evidence_index(path: str | Path) -> EvidenceIndexDocument | None:
    """`knowledge/evidence/stories/{storyId}.yaml`相当の1ファイルを読み込む。

    ファイルが存在しない場合はNoneを返す (呼び出し側で例外を投げない)。
    """
    p = Path(path)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not data:
        return None
    return parse_evidence_index_document(data)


def load_evidence_indexes(path: str | Path) -> EvidenceIndexCollection:
    """directory配下の`*.yaml`/`*.yml`をすべて読み込む。

    directoryが存在しない場合は空のcollectionを返す
    (`agents/wiki_generator/story_summaries.py`と同じ「存在しなければ空」方針)。
    """
    p = Path(path)
    if not p.is_dir():
        return EvidenceIndexCollection(documents=[])

    documents: list[EvidenceIndexDocument] = []
    for file_path in sorted(p.glob("*.yaml")) + sorted(p.glob("*.yml")):
        document = load_evidence_index(file_path)
        if document is not None:
            documents.append(document)
    return EvidenceIndexCollection(documents=documents)


def build_evidence_id_index(
    collection: EvidenceIndexCollection,
) -> dict[str, EvidenceIndexEntry]:
    """evidenceId -> EvidenceIndexEntry の索引を組み立てる。

    複数documentにまたがって重複するevidenceIdがある場合、後勝ちとする
    (重複自体はvalidatorで検出する、renderer/loader側では単純化する)。
    """
    index: dict[str, EvidenceIndexEntry] = {}
    for document in collection.documents:
        for entry in document.entries:
            if entry.evidence_id:
                index[entry.evidence_id] = entry
    return index


def group_entries_by_story(
    collection: EvidenceIndexCollection,
) -> dict[str, list[EvidenceIndexEntry]]:
    """storyId -> EvidenceIndexEntryのリスト、の索引を組み立てる
    (Story別Evidence page実装 `evidence-index-renderer-integration` に
    備えたhelper)。"""
    groups: dict[str, list[EvidenceIndexEntry]] = {}
    for document in collection.documents:
        for entry in document.entries:
            if entry.story_id:
                groups.setdefault(entry.story_id, []).append(entry)
    return groups


def group_entries_by_public_story(
    collection: EvidenceIndexCollection,
) -> dict[str, list[EvidenceIndexEntry]]:
    """publicStoryId -> EvidenceIndexEntryのリスト、の索引を組み立てる
    (publicStoryIdが設定されているentryのみ)。"""
    groups: dict[str, list[EvidenceIndexEntry]] = {}
    for document in collection.documents:
        for entry in document.entries:
            if entry.public_story_id:
                groups.setdefault(entry.public_story_id, []).append(entry)
    return groups


def group_entries_by_episode(
    collection: EvidenceIndexCollection,
) -> dict[str, list[EvidenceIndexEntry]]:
    """episodeId -> EvidenceIndexEntryのリスト、の索引を組み立てる。"""
    groups: dict[str, list[EvidenceIndexEntry]] = {}
    for document in collection.documents:
        for entry in document.entries:
            if entry.episode_id:
                groups.setdefault(entry.episode_id, []).append(entry)
    return groups


def group_entries_by_public_episode(
    collection: EvidenceIndexCollection,
) -> dict[str, list[EvidenceIndexEntry]]:
    """publicEpisodeId -> EvidenceIndexEntryのリスト、の索引を組み立てる
    (publicEpisodeIdが設定されているentryのみ)。"""
    groups: dict[str, list[EvidenceIndexEntry]] = {}
    for document in collection.documents:
        for entry in document.entries:
            if entry.public_episode_id:
                groups.setdefault(entry.public_episode_id, []).append(entry)
    return groups


@dataclass
class EvidenceIndexLookup:
    """renderer統合で使う索引一式をまとめたコンテナ
    (`agents.wiki_generator.story_summaries.StorySummaryLookup`と同じ
    パターン、feature/evidence-index-renderer-integration)。"""

    by_evidence_id: dict[str, EvidenceIndexEntry] = field(default_factory=dict)
    by_story_id: dict[str, list[EvidenceIndexEntry]] = field(default_factory=dict)


def build_evidence_index_lookup(
    collection: EvidenceIndexCollection,
) -> EvidenceIndexLookup:
    """`EvidenceIndexCollection`から`EvidenceIndexLookup`を組み立てる。"""
    return EvidenceIndexLookup(
        by_evidence_id=build_evidence_id_index(collection),
        by_story_id=group_entries_by_story(collection),
    )


def resolve_group_public_story_id(entries: list[EvidenceIndexEntry]) -> str | None:
    """story内のentry群から`publicStoryId`を解決する。

    複数entryにまたがって`publicStoryId`が混在する場合は、最初に見つかった
    非空の値を採用する（`agents.wiki_generator.renderer.
    _resolve_group_public_story_id`と同じ「複雑なconflict処理はしない」
    方針、`Evidence_Index_Design.md` §7 grouping方針）。
    """
    for entry in entries:
        if isinstance(entry.public_story_id, str) and entry.public_story_id.strip():
            return entry.public_story_id.strip()
    return None


# ----------------------------------------------------------------
# Validation
# ----------------------------------------------------------------


def _collect_strings(value: Any) -> list[str]:
    """任意の値 (dict/list/dataclassではないraw値) から、含まれる文字列を
    再帰的に集める (raw text禁止文字列検出用)。"""
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            strings.extend(_collect_strings(v))
    elif isinstance(value, list):
        for v in value:
            strings.extend(_collect_strings(v))
    return strings


def _detect_forbidden_text(label: str, value: Any) -> list[str]:
    """raw DEC text/rawコマンド/ローカル絶対パス/scriptタグ等の禁止文字列を
    再帰的に検出する。

    完全自動での「元セリフ全文」検出はできないため、最低限明確に危険な
    文字列パターンのみを対象とする（誤検出の可能性は
    `docs/architecture/06_AI/Evidence_Index_Design.md` §6に記載する）。
    """
    issues: list[str] = []
    for text in _collect_strings(value):
        for pattern in FORBIDDEN_TEXT_PATTERNS:
            if pattern in text:
                issues.append(f"{label}: 禁止文字列 '{pattern}' が含まれています")
    return issues


def _validate_visibility(label: str, visibility: Visibility) -> list[str]:
    issues: list[str] = []
    if visibility.raw_text_included is not False:
        issues.append(
            f"{label}: visibility.rawTextIncludedはPublic Evidence Indexでは"
            "falseである必要があります"
        )
    if visibility.public is not True:
        issues.append(
            f"{label}: visibility.publicがfalseです "
            "(Public Evidence Index内のentryはpublic: trueである必要があります)"
        )
    return issues


def _validate_entry_ids_and_type(label: str, entry: EvidenceIndexEntry) -> list[str]:
    issues: list[str] = []
    if not entry.evidence_id:
        issues.append("entries: evidenceIdが空です")
    elif not ID_PATTERN.match(entry.evidence_id):
        issues.append(f"{label}: evidenceIdの形式が不正です")

    if entry.evidence_type not in VALID_EVIDENCE_TYPES:
        issues.append(f"{label}: 未知のevidenceType '{entry.evidence_type}'")

    if not entry.story_id:
        issues.append(f"{label}: storyIdが空です")
    if not entry.episode_id:
        issues.append(f"{label}: episodeIdが空です")
    return issues


def _validate_entry_enums(label: str, entry: EvidenceIndexEntry) -> list[str]:
    issues: list[str] = []
    if (
        entry.speaker is not None
        and entry.speaker.resolution_status not in VALID_RESOLUTION_STATUSES
    ):
        issues.append(
            f"{label}: 未知のspeaker.resolutionStatus "
            f"'{entry.speaker.resolution_status}'"
        )

    for related in entry.related_entities:
        if related.entity_type not in VALID_ENTITY_TYPES:
            issues.append(
                f"{label}: 未知のrelatedEntities.entityType '{related.entity_type}'"
            )

    if entry.referenced_by is not None:
        for summary_ref in entry.referenced_by.summaries:
            if summary_ref.summary_type not in VALID_SUMMARY_TYPES:
                issues.append(
                    f"{label}: 未知のreferencedBy.summaries.summaryType "
                    f"'{summary_ref.summary_type}'"
                )
    return issues


def _validate_entry_forbidden_text(label: str, entry: EvidenceIndexEntry) -> list[str]:
    issues: list[str] = []
    issues.extend(_detect_forbidden_text(f"{label}.notes", entry.notes))
    if entry.speaker is not None:
        issues.extend(
            _detect_forbidden_text(f"{label}.speaker", entry.speaker.display_name)
        )
    for related in entry.related_entities:
        issues.extend(
            _detect_forbidden_text(f"{label}.relatedEntities", related.display_name)
        )
    return issues


def _validate_entry(entry: EvidenceIndexEntry) -> list[str]:
    label = f"evidenceId={entry.evidence_id!r}"
    issues: list[str] = []
    issues.extend(_validate_entry_ids_and_type(label, entry))
    issues.extend(_validate_entry_enums(label, entry))
    issues.extend(_validate_visibility(label, entry.visibility))
    issues.extend(_validate_entry_forbidden_text(label, entry))
    return issues


def validate_evidence_index_document(document: EvidenceIndexDocument) -> list[str]:
    """1つのEvidenceIndexDocumentの整合性を検証する (schema検証とは別の
    Python側validation。raw text禁止・enum等)。duplicate evidenceId検出は
    `validate_evidence_index_collection`側で行う (1ファイル=1documentの
    collectionとして呼び出せば単一ファイルでも同じ検証を受けられる)。

    戻り値: 問題を説明する人間可読な文字列のリスト (空なら問題無し)。
    """
    issues: list[str] = []
    for entry in document.entries:
        issues.extend(_validate_entry(entry))
    issues.extend(_detect_forbidden_text("notes", document.notes))
    if document.generated_from is not None:
        issues.extend(
            _detect_forbidden_text(
                "generatedFrom", document.generated_from.extraction_refs
            )
        )
    return issues


def validate_evidence_index_collection(
    collection: EvidenceIndexCollection,
) -> list[str]:
    """collection全体 (1件以上のドキュメント) の整合性を検証する。

    個々のドキュメント検証に加え、ドキュメントをまたいだduplicate
    evidenceId（同一ファイル内の重複も含む）を検出する。
    """
    issues: list[str] = []
    for document in collection.documents:
        issues.extend(validate_evidence_index_document(document))

    all_entries = [
        entry for document in collection.documents for entry in document.entries
    ]
    seen: dict[str, int] = {}
    for entry in all_entries:
        if entry.evidence_id:
            seen[entry.evidence_id] = seen.get(entry.evidence_id, 0) + 1
    for evidence_id, count in seen.items():
        if count > 1:
            issues.append(f"evidenceId '{evidence_id}' が{count}件重複しています")

    return issues
