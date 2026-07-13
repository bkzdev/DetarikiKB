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
        STORY_SUMMARY_PROMPT_VERSION,
        extract_episode_blocks,
        build_episode_summary_prompt,
        build_story_summary_prompt,
        generate_episode_summary,
        generate_story_summary_draft,
        synthesize_story_summary,
    )

Story Summary / Episode Summary AI生成パイプラインの骨格
(Story_Summary_Generation_Plan.md §9 `summary-generation-skeleton`)に、
Ollama provider呼び出し本体 (`summary-generation-provider-implementation`)、
Episode Summary生成prompt・hallucination対策の後処理
(`summary-generation-prompt-implementation`)、Episode Summary群からの
Story Summary合成 (`summary-generation-story-synthesis`) を追加した。
ユーザー明示指示2026-07-13によりsummarizer系のLLM provider/prompt実装を
解禁済み (`AI_CONTEXT.md` §4、`agents/extractor/`は引き続き未解禁のまま)。

Story Summary合成 (Plan §11): 生成済みEpisode Summary群のtext
(episodeNumber順) をLLMに再要約させ (`format_json=True`、出力は
`{"text": "..."}`のみ)、story-level evidenceRefsはepisode-level
evidenceRefsの重複排除unionとして機械的に決める。
`generate_story_summary_draft`は既定でStory Summary合成まで行う
(`synthesize_story=False`で無効化可能)。

docs/architecture/06_AI/Story_Summary_Generation_Plan.md
docs/architecture/06_AI/Story_Summary_Design.md
schemas/story_summary.schema.json
"""

from .generator import (
    DEFAULT_VERBATIM_THRESHOLD,
    EpisodeSummaryGenerationResult,
    GenerationIssue,
    StorySummaryGenerationResult,
    StorySynthesisResult,
    generate_episode_summary,
    generate_story_summary_draft,
    synthesize_story_summary,
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
    STORY_SUMMARY_PROMPT_VERSION,
    STORY_SUMMARY_SYSTEM_PROMPT,
    EpisodeSummaryInput,
    ExtractedBlock,
    build_episode_summary_prompt,
    build_story_summary_prompt,
    extract_episode_blocks,
    format_block_line,
    format_episode_summary_line,
    render_blocks_text,
    render_episode_summaries_text,
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
    "STORY_SUMMARY_PROMPT_VERSION",
    "EPISODE_SUMMARY_SYSTEM_PROMPT",
    "STORY_SUMMARY_SYSTEM_PROMPT",
    "INCLUDED_BLOCK_TYPES",
    "DEFAULT_MAX_INPUT_CHARACTERS",
    "ExtractedBlock",
    "EpisodeSummaryInput",
    "extract_episode_blocks",
    "format_block_line",
    "format_episode_summary_line",
    "render_blocks_text",
    "render_episode_summaries_text",
    "build_episode_summary_prompt",
    "build_story_summary_prompt",
    "GenerationIssue",
    "EpisodeSummaryGenerationResult",
    "StorySummaryGenerationResult",
    "StorySynthesisResult",
    "DEFAULT_VERBATIM_THRESHOLD",
    "generate_episode_summary",
    "generate_story_summary_draft",
    "synthesize_story_summary",
]
