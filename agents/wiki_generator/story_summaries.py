"""
DKB Wiki Generator - Story Summary loader
`knowledge/summaries/stories/{storyId}.yaml`（Story Summary/Episode Summary、
1ファイル=1story）を読み込み・検証する。

`docs/architecture/06_AI/Story_Summary_Design.md`で決定した設計をそのまま
実装する。**このモジュールはrenderer統合を行わない**（Story page/Episode
pageへの表示差し替えは後続PR `story-summary-renderer-integration`）。
AI要約生成・LLM呼び出しもこのモジュールの対象外。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

GENERATION_STATUS_MISSING = "missing"
"""Summary未生成。通常は永続化しない
(該当エントリが存在しないこと自体がmissingを表す)。"""

GENERATION_STATUS_DRAFT = "draft"
GENERATION_STATUS_GENERATED = "generated"
GENERATION_STATUS_DEPRECATED = "deprecated"

VALID_GENERATION_STATUSES = frozenset(
    {
        GENERATION_STATUS_MISSING,
        GENERATION_STATUS_DRAFT,
        GENERATION_STATUS_GENERATED,
        GENERATION_STATUS_DEPRECATED,
    }
)

REVIEW_STATUS_UNREVIEWED = "unreviewed"
REVIEW_STATUS_REVIEWED = "reviewed"
REVIEW_STATUS_APPROVED = "approved"
REVIEW_STATUS_REJECTED = "rejected"
REVIEW_STATUS_NEEDS_REVISION = "needs_revision"

VALID_REVIEW_STATUSES = frozenset(
    {
        REVIEW_STATUS_UNREVIEWED,
        REVIEW_STATUS_REVIEWED,
        REVIEW_STATUS_APPROVED,
        REVIEW_STATUS_REJECTED,
        REVIEW_STATUS_NEEDS_REVISION,
    }
)

DISPLAYABLE_REVIEW_STATUSES = frozenset(
    {REVIEW_STATUS_REVIEWED, REVIEW_STATUS_APPROVED}
)
"""review.statusがこの集合に含まれるSummaryのみ、将来Wiki表示・
knowledge/summaries/へのcommit対象とする (Story_Summary_Design.md §6.3)。"""

VALID_SOURCE_TYPES = frozenset({"manual", "ai_generated", "imported", "unknown"})

STORY_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
EVIDENCE_REF_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

# raw text / source text禁止文字列 (Story_Summary_Design.md §7.3、本PRで
# validatorとして実装する最低限の危険文字列チェック。完全自動検出はできない
# ため、実セリフ全文の検出は人間レビューで補う前提)。
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
)


@dataclass
class EvidenceRefList:
    """evidenceRefsをそのままラップするだけの軽量コンテナ (型を明示するため)。"""

    values: list[str] = field(default_factory=list)


@dataclass
class StorySummaryEntry:
    text: str
    confidence: float | None = None
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class EpisodeSummaryEntry:
    episode_id: str
    text: str
    public_episode_id: str | None = None
    episode_number: int | None = None
    confidence: float | None = None
    evidence_refs: list[str] = field(default_factory=list)


@dataclass
class SummarySource:
    source_type: str = "unknown"
    model: str | None = None
    prompt_version: str | None = None
    generated_at: str | None = None
    input_refs: list[str] = field(default_factory=list)


@dataclass
class SummaryReview:
    status: str = REVIEW_STATUS_UNREVIEWED
    reviewer: str | None = None
    reviewed_at: str | None = None
    notes: str | None = None


@dataclass
class StorySummaryDocument:
    """`knowledge/summaries/stories/{storyId}.yaml` 1ファイル分。"""

    story_id: str
    language: str = "ja"
    generation_status: str = GENERATION_STATUS_MISSING
    public_story_id: str | None = None
    story_summary: StorySummaryEntry | None = None
    episode_summaries: list[EpisodeSummaryEntry] = field(default_factory=list)
    source: SummarySource = field(default_factory=SummarySource)
    review: SummaryReview = field(default_factory=SummaryReview)
    notes: str | None = None


@dataclass
class StorySummaryCollection:
    """複数のStorySummaryDocumentをまとめたコンテナ (directory loadの結果)。"""

    documents: list[StorySummaryDocument] = field(default_factory=list)


def _parse_story_summary_entry(raw: dict[str, Any] | None) -> StorySummaryEntry | None:
    if raw is None:
        return None
    return StorySummaryEntry(
        text=raw.get("text", ""),
        confidence=raw.get("confidence"),
        evidence_refs=list(raw.get("evidenceRefs", []) or []),
    )


def _parse_episode_summary_entry(raw: dict[str, Any]) -> EpisodeSummaryEntry:
    return EpisodeSummaryEntry(
        episode_id=raw.get("episodeId", ""),
        text=raw.get("text", ""),
        public_episode_id=raw.get("publicEpisodeId"),
        episode_number=raw.get("episodeNumber"),
        confidence=raw.get("confidence"),
        evidence_refs=list(raw.get("evidenceRefs", []) or []),
    )


def _parse_source(raw: dict[str, Any] | None) -> SummarySource:
    if raw is None:
        return SummarySource()
    return SummarySource(
        source_type=raw.get("sourceType", "unknown"),
        model=raw.get("model"),
        prompt_version=raw.get("promptVersion"),
        generated_at=raw.get("generatedAt"),
        input_refs=list(raw.get("inputRefs", []) or []),
    )


def _parse_review(raw: dict[str, Any] | None) -> SummaryReview:
    if raw is None:
        return SummaryReview()
    return SummaryReview(
        status=raw.get("status", REVIEW_STATUS_UNREVIEWED),
        reviewer=raw.get("reviewer"),
        reviewed_at=raw.get("reviewedAt"),
        notes=raw.get("notes"),
    )


def parse_story_summary_document(raw: dict[str, Any]) -> StorySummaryDocument:
    """辞書 (YAML/JSONをloadした結果) から`StorySummaryDocument`を組み立てる。"""
    return StorySummaryDocument(
        story_id=raw.get("storyId", ""),
        language=raw.get("language", "ja"),
        generation_status=raw.get("generationStatus", GENERATION_STATUS_MISSING),
        public_story_id=raw.get("publicStoryId"),
        story_summary=_parse_story_summary_entry(raw.get("storySummary")),
        episode_summaries=[
            _parse_episode_summary_entry(entry)
            for entry in raw.get("episodeSummaries", []) or []
        ],
        source=_parse_source(raw.get("source")),
        review=_parse_review(raw.get("review")),
        notes=raw.get("notes"),
    )


def load_story_summary(path: str | Path) -> StorySummaryDocument | None:
    """`knowledge/summaries/stories/{storyId}.yaml`相当の1ファイルを読み込む。

    ファイルが存在しない場合はNoneを返す (呼び出し側で「未生成」として
    扱えるように、例外は投げない)。
    """
    p = Path(path)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not data:
        return None
    return parse_story_summary_document(data)


def load_story_summaries(path: str | Path) -> StorySummaryCollection:
    """directory配下の`*.yaml`/`*.yml`をすべて読み込む。

    directoryが存在しない場合は空のcollectionを返す
    (`agents/parser/character_dictionary.py`と同じ「存在しなければ空」方針)。
    """
    p = Path(path)
    if not p.is_dir():
        return StorySummaryCollection(documents=[])

    documents: list[StorySummaryDocument] = []
    for file_path in sorted(p.glob("*.yaml")) + sorted(p.glob("*.yml")):
        document = load_story_summary(file_path)
        if document is not None:
            documents.append(document)
    return StorySummaryCollection(documents=documents)


def build_story_summary_index(
    collection: StorySummaryCollection,
) -> dict[str, StorySummaryDocument]:
    """storyId -> StorySummaryDocument の索引を組み立てる。"""
    return {doc.story_id: doc for doc in collection.documents if doc.story_id}


def build_public_story_summary_index(
    collection: StorySummaryCollection,
) -> dict[str, StorySummaryDocument]:
    """publicStoryId -> StorySummaryDocument の索引を組み立てる
    (publicStoryIdが設定されているドキュメントのみ)。"""
    return {
        doc.public_story_id: doc for doc in collection.documents if doc.public_story_id
    }


def find_episode_summary(
    document: StorySummaryDocument, episode_id: str
) -> EpisodeSummaryEntry | None:
    """episodeIdでEpisode Summaryを1件取得する (無ければNone)。"""
    for entry in document.episode_summaries:
        if entry.episode_id == episode_id:
            return entry
    return None


def find_episode_summary_by_public_id(
    document: StorySummaryDocument, public_episode_id: str
) -> EpisodeSummaryEntry | None:
    """publicEpisodeIdでEpisode Summaryを1件取得する (無ければNone)。"""
    for entry in document.episode_summaries:
        if entry.public_episode_id == public_episode_id:
            return entry
    return None


def is_displayable_summary(review: SummaryReview) -> bool:
    """review.statusが`reviewed`/`approved`かどうかを判定する
    (Story_Summary_Design.md §6.3、renderer統合はまだ実装しないが、
    後続PRで使うための判定helperだけ先に用意する)。"""
    return review.status in DISPLAYABLE_REVIEW_STATUSES


# ----------------------------------------------------------------
# Validation
# ----------------------------------------------------------------


def _validate_evidence_refs(label: str, evidence_refs: list[str]) -> list[str]:
    issues: list[str] = []
    for ref in evidence_refs:
        if not isinstance(ref, str) or not EVIDENCE_REF_PATTERN.match(ref):
            issues.append(f"{label}: evidenceRefの形式が不正です ('{ref}')")
    return issues


def _detect_forbidden_text(label: str, text: str | None) -> list[str]:
    """raw DEC text/rawコマンド/ローカル絶対パス等の禁止文字列を検出する。

    完全自動での「元セリフ全文」検出はできないため、ここでは明確に危険な
    文字列パターンのみを対象とする最低限のチェックに留める。誤検出の
    可能性 (例: 要約文中に偶然'$num'という語が現れる等) は
    `docs/architecture/06_AI/Story_Summary_Design.md` §7.3に記載する。
    実セリフ全文そのものの検出は人間レビューで補う。
    """
    if not text:
        return []
    issues: list[str] = []
    for pattern in FORBIDDEN_TEXT_PATTERNS:
        if pattern in text:
            issues.append(f"{label}: 禁止文字列 '{pattern}' が含まれています")
    return issues


def _validate_story_summary_entry(entry: StorySummaryEntry | None) -> list[str]:
    if entry is None:
        return []
    issues: list[str] = []
    if not entry.text:
        issues.append("storySummary.textが空です")
    issues.extend(_detect_forbidden_text("storySummary.text", entry.text))
    issues.extend(
        _validate_evidence_refs("storySummary.evidenceRefs", entry.evidence_refs)
    )
    return issues


def _validate_single_episode_summary_entry(entry: EpisodeSummaryEntry) -> list[str]:
    label = f"episodeSummaries[episodeId={entry.episode_id!r}]"
    issues: list[str] = []
    if not entry.episode_id:
        issues.append("episodeSummaries: episodeIdが空です")
    elif not STORY_ID_PATTERN.match(entry.episode_id):
        issues.append(f"{label}: episodeIdの形式が不正です")
    if not entry.text:
        issues.append(f"{label}: textが空です")
    issues.extend(_detect_forbidden_text(f"{label}.text", entry.text))
    issues.extend(_validate_evidence_refs(f"{label}.evidenceRefs", entry.evidence_refs))
    return issues


def _validate_episode_summary_duplicates(
    entries: list[EpisodeSummaryEntry],
) -> list[str]:
    issues: list[str] = []
    seen_episode_ids: dict[str, int] = {}
    seen_public_episode_ids: dict[str, int] = {}

    for entry in entries:
        if entry.episode_id:
            seen_episode_ids[entry.episode_id] = (
                seen_episode_ids.get(entry.episode_id, 0) + 1
            )
        if entry.public_episode_id:
            seen_public_episode_ids[entry.public_episode_id] = (
                seen_public_episode_ids.get(entry.public_episode_id, 0) + 1
            )

    for episode_id, count in seen_episode_ids.items():
        if count > 1:
            issues.append(
                f"episodeId '{episode_id}' がepisodeSummaries内で"
                f"{count}件重複しています"
            )
    for public_episode_id, count in seen_public_episode_ids.items():
        if count > 1:
            issues.append(
                f"publicEpisodeId '{public_episode_id}' がepisodeSummaries内で"
                f"{count}件重複しています"
            )
    return issues


def _validate_episode_summary_entries(
    entries: list[EpisodeSummaryEntry],
) -> list[str]:
    issues: list[str] = []
    for entry in entries:
        issues.extend(_validate_single_episode_summary_entry(entry))
    issues.extend(_validate_episode_summary_duplicates(entries))
    return issues


def validate_story_summary_document(document: StorySummaryDocument) -> list[str]:
    """1つのStorySummaryDocumentの整合性を検証する (schema検証とは別の
    Python側validation。raw text禁止・duplicate episodeId等)。

    戻り値: 問題を説明する人間可読な文字列のリスト (空なら問題無し)。
    """
    issues: list[str] = []

    if not document.story_id:
        issues.append("storyIdが空です")
    elif not STORY_ID_PATTERN.match(document.story_id):
        issues.append(f"storyId '{document.story_id}': 形式が不正です")

    if document.public_story_id and not STORY_ID_PATTERN.match(
        document.public_story_id
    ):
        issues.append(f"publicStoryId '{document.public_story_id}': 形式が不正です")

    if document.generation_status not in VALID_GENERATION_STATUSES:
        issues.append(
            f"storyId '{document.story_id}': 未知のgenerationStatus "
            f"'{document.generation_status}'"
        )

    if document.source.source_type not in VALID_SOURCE_TYPES:
        issues.append(
            f"storyId '{document.story_id}': 未知のsource.sourceType "
            f"'{document.source.source_type}'"
        )

    if document.review.status not in VALID_REVIEW_STATUSES:
        issues.append(
            f"storyId '{document.story_id}': 未知のreview.status "
            f"'{document.review.status}'"
        )

    issues.extend(_validate_story_summary_entry(document.story_summary))
    issues.extend(_validate_episode_summary_entries(document.episode_summaries))
    issues.extend(_detect_forbidden_text("notes", document.notes))
    issues.extend(_detect_forbidden_text("review.notes", document.review.notes))

    return issues


def validate_story_summary_collection(
    collection: StorySummaryCollection,
) -> list[str]:
    """collection全体 (複数ドキュメント) の整合性を検証する。

    個々のドキュメント検証に加え、ドキュメント間のduplicate storyId/
    publicStoryIdも検出する。
    """
    issues: list[str] = []
    for document in collection.documents:
        issues.extend(validate_story_summary_document(document))

    seen_story_ids: dict[str, int] = {}
    seen_public_story_ids: dict[str, int] = {}
    for document in collection.documents:
        if document.story_id:
            seen_story_ids[document.story_id] = (
                seen_story_ids.get(document.story_id, 0) + 1
            )
        if document.public_story_id:
            seen_public_story_ids[document.public_story_id] = (
                seen_public_story_ids.get(document.public_story_id, 0) + 1
            )

    for story_id, count in seen_story_ids.items():
        if count > 1:
            issues.append(f"storyId '{story_id}' が{count}ファイルで重複しています")
    for public_story_id, count in seen_public_story_ids.items():
        if count > 1:
            issues.append(
                f"publicStoryId '{public_story_id}' が{count}ファイルで重複しています"
            )

    return issues
