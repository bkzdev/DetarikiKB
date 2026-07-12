"""
DKB Summarizer - Models
Story/Episode Summary AI生成パイプラインのdraft段階で使う最小限のデータ構造。

LLM呼び出し・provider抽象・prompt実装はまだ含まない
(docs/architecture/06_AI/Story_Summary_Generation_Plan.md §9
 `summary-generation-skeleton`のスコープ)。

docs/architecture/06_AI/Story_Summary_Generation_Plan.md
docs/architecture/06_AI/Story_Summary_Design.md
schemas/story_summary.schema.json
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# schemas/story_summary.schema.json / docs/templates/story_summary_template.yaml
# が使う現行のschemaVersion値に合わせる。
SCHEMA_VERSION = "0.1.0"
DOCUMENT_TYPE = "story_summary"

# to_document_dict()が出力するdraft文書の固定値。
# Story_Summary_Generation_Plan.md §3: draft段階の生成物は常にこの状態で
# workspace/summary_drafts/へ保存し、人間レビュー前にreviewed/approvedへ
# 昇格させることはない。
DRAFT_GENERATION_STATUS = "draft"
DRAFT_SOURCE_TYPE = "ai_generated"
DRAFT_REVIEW_STATUS = "unreviewed"
DRAFT_LANGUAGE = "ja"


@dataclass
class EpisodeSummaryDraft:
    """Episode Summaryのdraft (Story_Summary_Design.md §8.4相当)。

    evidenceRefsはこの段階では内部blockId参照のままでよい
    (Story_Summary_Generation_Plan.md §4.3.3。publicEvidenceIdへの変換は
    将来のprojection PRのスコープ)。
    """

    episode_id: str
    text: str
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float | None = None
    public_episode_id: str | None = None
    episode_number: int | None = None

    def to_entry_dict(self) -> dict[str, Any]:
        """schemas/story_summary.schema.json EpisodeSummaryEntry相当のdictへ変換する。"""  # noqa: E501
        return {
            "episodeId": self.episode_id,
            "publicEpisodeId": self.public_episode_id,
            "episodeNumber": self.episode_number,
            "text": self.text,
            "confidence": self.confidence,
            "evidenceRefs": list(self.evidence_refs),
        }


@dataclass
class SummaryProvenance:
    """Summary生成のprovenance情報。

    agents/extractor/models.py の ExtractionRunInfo と同じ命名・型慣例
    (model_provider/model_name/prompt_version は常にNoneでもよい文字列
    フィールド、input_refsは監査用のID一覧)。LLM呼び出し本体はまだ実装
    していないため、このdataclass自体はどの値も明示的な既定値を持たない。
    """

    model_provider: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    generated_at: str | None = None
    input_refs: list[str] = field(default_factory=list)

    def model_label(self) -> str | None:
        """schemas/story_summary.schema.json Source.model (単一文字列)へ
        model_provider/model_nameをまとめる。両方あれば'provider/name'、
        片方のみならその値、どちらも無ければNone。"""
        if self.model_provider and self.model_name:
            return f"{self.model_provider}/{self.model_name}"
        return self.model_name or self.model_provider


@dataclass
class StorySummaryDraft:
    """Story Summary + Episode Summary群のdraft (Story_Summary_Design.md §8.1相当)。

    draft出力先はworkspace/summary_drafts/ (.gitignore済み)。languageは既定'ja'
    (Story_Summary_Generation_Plan.md §3)。
    """

    story_id: str
    public_story_id: str | None = None
    language: str = DRAFT_LANGUAGE
    story_text: str | None = None
    story_evidence_refs: list[str] = field(default_factory=list)
    episode_summaries: list[EpisodeSummaryDraft] = field(default_factory=list)
    notes: str | None = None

    def to_document_dict(self, provenance: SummaryProvenance) -> dict[str, Any]:
        """schemas/story_summary.schema.json に適合するdraft文書dictを返す。

        generationStatusは常に"draft"、source.sourceTypeは常に"ai_generated"、
        review.statusは常に"unreviewed"とする (draft段階のtemplate値)。
        storySummaryはstory_textがNoneならnull。
        """
        story_summary_entry: dict[str, Any] | None
        if self.story_text is None:
            story_summary_entry = None
        else:
            story_summary_entry = {
                "text": self.story_text,
                "confidence": None,
                "evidenceRefs": list(self.story_evidence_refs),
            }

        return {
            "schemaVersion": SCHEMA_VERSION,
            "documentType": DOCUMENT_TYPE,
            "storyId": self.story_id,
            "publicStoryId": self.public_story_id,
            "language": self.language,
            "generationStatus": DRAFT_GENERATION_STATUS,
            "storySummary": story_summary_entry,
            "episodeSummaries": [
                episode.to_entry_dict() for episode in self.episode_summaries
            ],
            "source": {
                "sourceType": DRAFT_SOURCE_TYPE,
                "model": provenance.model_label(),
                "promptVersion": provenance.prompt_version,
                "generatedAt": provenance.generated_at,
                "inputRefs": list(provenance.input_refs),
            },
            "review": {
                "status": DRAFT_REVIEW_STATUS,
                "reviewer": None,
                "reviewedAt": None,
                "notes": None,
            },
            "notes": self.notes,
        }
