"""
DKB Summarizer Package

Usage:
    from agents.summarizer import (
        EpisodeSummaryDraft,
        StorySummaryDraft,
        SummaryProvenance,
        LLMCompletion,
        LLMProviderError,
        OllamaProvider,
        SummaryLLMProvider,
    )

Story Summary / Episode Summary AI生成パイプラインの骨格
(Story_Summary_Generation_Plan.md §9 `summary-generation-skeleton`)に、
Ollama provider呼び出し本体を追加した
(`summary-generation-provider-implementation`、ユーザー明示指示
2026-07-13によりsummarizer系のLLM provider実装を解禁済み、`AI_CONTEXT.md` §4)。
prompt実装・要約生成ロジック自体は次PR
`summary-generation-prompt-implementation`のスコープでまだ含まない。

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
from .provider import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_TIMEOUT_SECONDS,
    LLMCompletion,
    LLMProviderError,
    OllamaProvider,
    SummaryLLMProvider,
    resolve_ollama_host,
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
    "LLMCompletion",
    "LLMProviderError",
    "OllamaProvider",
    "SummaryLLMProvider",
    "resolve_ollama_host",
    "DEFAULT_OLLAMA_HOST",
    "DEFAULT_TIMEOUT_SECONDS",
]
