"""
DKB Summarizer Package

Usage:
    from agents.summarizer import (
        EpisodeSummaryDraft,
        StorySummaryDraft,
        SummaryProvenance,
    )

Story Summary / Episode Summary AI生成パイプラインの最小限の骨格
(Story_Summary_Generation_Plan.md §9 `summary-generation-skeleton`)。
LLM呼び出し本体・provider抽象・prompt実装は含まない
(`AI_CONTEXT.md` §4と同じ制約)。

docs/architecture/06_AI/Story_Summary_Generation_Plan.md
docs/architecture/06_AI/Story_Summary_Design.md
schemas/story_summary.schema.json
"""

from .models import (
    DOCUMENT_TYPE,
    DRAFT_GENERATION_STATUS,
    DRAFT_LANGUAGE,
    DRAFT_REVIEW_STATUS,
    DRAFT_SOURCE_TYPE,
    SCHEMA_VERSION,
    EpisodeSummaryDraft,
    StorySummaryDraft,
    SummaryProvenance,
)

__all__ = [
    "EpisodeSummaryDraft",
    "StorySummaryDraft",
    "SummaryProvenance",
    "SCHEMA_VERSION",
    "DOCUMENT_TYPE",
    "DRAFT_GENERATION_STATUS",
    "DRAFT_SOURCE_TYPE",
    "DRAFT_REVIEW_STATUS",
    "DRAFT_LANGUAGE",
]
