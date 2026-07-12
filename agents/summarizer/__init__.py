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
        PROMPT_VERSION,
        extract_episode_blocks,
        build_episode_summary_prompt,
        generate_episode_summary,
        generate_story_summary_draft,
    )

Story Summary / Episode Summary AI生成パイプラインの骨格
(Story_Summary_Generation_Plan.md §9 `summary-generation-skeleton`)に、
Ollama provider呼び出し本体 (`summary-generation-provider-implementation`)、
Episode Summary生成prompt・hallucination対策の後処理
(`summary-generation-prompt-implementation`)を追加した。ユーザー明示指示
2026-07-13によりsummarizer系のLLM provider/prompt実装を解禁済み
(`AI_CONTEXT.md` §4、`agents/extractor/`は引き続き未解禁のまま)。

Story Summary合成 (Episode Summary群 -> Story Summary) は次PR
`summary-generation-story-synthesis`のスコープでまだ含まない
(`generate_story_summary_draft`の`draft.storySummary`は常にnull)。

docs/architecture/06_AI/Story_Summary_Generation_Plan.md
docs/architecture/06_AI/Story_Summary_Design.md
schemas/story_summary.schema.json
"""

from .generator import (
    DEFAULT_VERBATIM_THRESHOLD,
    EpisodeSummaryGenerationResult,
    GenerationIssue,
    StorySummaryGenerationResult,
    generate_episode_summary,
    generate_story_summary_draft,
)
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
from .prompt import (
    DEFAULT_MAX_INPUT_CHARACTERS,
    EPISODE_SUMMARY_SYSTEM_PROMPT,
    INCLUDED_BLOCK_TYPES,
    PROMPT_VERSION,
    ExtractedBlock,
    build_episode_summary_prompt,
    extract_episode_blocks,
    format_block_line,
    render_blocks_text,
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
    "PROMPT_VERSION",
    "EPISODE_SUMMARY_SYSTEM_PROMPT",
    "INCLUDED_BLOCK_TYPES",
    "DEFAULT_MAX_INPUT_CHARACTERS",
    "ExtractedBlock",
    "extract_episode_blocks",
    "format_block_line",
    "render_blocks_text",
    "build_episode_summary_prompt",
    "GenerationIssue",
    "EpisodeSummaryGenerationResult",
    "StorySummaryGenerationResult",
    "DEFAULT_VERBATIM_THRESHOLD",
    "generate_episode_summary",
    "generate_story_summary_draft",
]
