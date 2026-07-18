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
        check_verbatim_quotes,
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

`check_verbatim_quotes`は`generate_episode_summary`内部のhallucination
対策 (§6.3項目4) から使う非公開名`_check_verbatim_quotes`を、
`scripts/check_story_summary_drafts.py` (`summary-generation-quality-gate`)
がdraftのquality gate検証で再利用できるよう公開名へ最小限リファクタした
ものである (挙動・既定閾値は変更していない)。

品質改善v2/v3・自己推敲パス (`summary-generation-quality-v2`、2026-07-18
ユーザー承認済み。詳細は`agents/summarizer/prompt.py`/`generator.py`の
module docstring参照): `PROMPT_VERSION`は`episode-summary-v3`
(主語明確化・登場人物リスト注入・本文中evidence ID参照禁止)、
`STORY_SUMMARY_PROMPT_VERSION`は`story-summary-v2`(全文直接入力方式)へ
更新した。`STORY_SUMMARY_PROMPT_VERSION_FALLBACK`はcontextサイズガード
超過時に使われるv1方式の値。`generate_episode_summary`/
`synthesize_story_summary`/`generate_story_summary_draft`は`refine`引数
(既定OFF) で自己推敲パスをopt-inできる。

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
    check_verbatim_quotes,
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
    CHARACTERS_PER_TOKEN_ESTIMATE,
    DEFAULT_MAX_CONTEXT_TOKENS,
    DEFAULT_MAX_INPUT_CHARACTERS,
    EPISODE_SUMMARY_SYSTEM_PROMPT,
    INCLUDED_BLOCK_TYPES,
    PROMPT_VERSION,
    REFINE_PROMPT_VERSION_SUFFIX,
    REFINE_SYSTEM_PROMPT,
    STORY_SUMMARY_PROMPT_VERSION,
    STORY_SUMMARY_PROMPT_VERSION_FALLBACK,
    STORY_SUMMARY_SYSTEM_PROMPT,
    STORY_SUMMARY_SYSTEM_PROMPT_V2,
    EpisodeBlocksInput,
    EpisodeSummaryInput,
    ExtractedBlock,
    build_episode_summary_prompt,
    build_refine_prompt,
    build_story_summary_prompt,
    build_story_summary_prompt_v2,
    estimate_token_count,
    extract_episode_blocks,
    extract_speaker_names,
    format_block_line,
    format_episode_summary_line,
    render_blocks_text,
    render_episode_summaries_text,
    render_story_full_text,
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
    "STORY_SUMMARY_PROMPT_VERSION_FALLBACK",
    "EPISODE_SUMMARY_SYSTEM_PROMPT",
    "STORY_SUMMARY_SYSTEM_PROMPT",
    "STORY_SUMMARY_SYSTEM_PROMPT_V2",
    "INCLUDED_BLOCK_TYPES",
    "DEFAULT_MAX_INPUT_CHARACTERS",
    "DEFAULT_MAX_CONTEXT_TOKENS",
    "CHARACTERS_PER_TOKEN_ESTIMATE",
    "REFINE_PROMPT_VERSION_SUFFIX",
    "REFINE_SYSTEM_PROMPT",
    "ExtractedBlock",
    "EpisodeSummaryInput",
    "EpisodeBlocksInput",
    "extract_episode_blocks",
    "extract_speaker_names",
    "format_block_line",
    "format_episode_summary_line",
    "render_blocks_text",
    "render_episode_summaries_text",
    "render_story_full_text",
    "build_episode_summary_prompt",
    "build_story_summary_prompt",
    "build_story_summary_prompt_v2",
    "build_refine_prompt",
    "estimate_token_count",
    "GenerationIssue",
    "EpisodeSummaryGenerationResult",
    "StorySummaryGenerationResult",
    "StorySynthesisResult",
    "DEFAULT_VERBATIM_THRESHOLD",
    "generate_episode_summary",
    "generate_story_summary_draft",
    "synthesize_story_summary",
    "check_verbatim_quotes",
]
