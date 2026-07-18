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
module docstring参照): `PROMPT_VERSION`は`episode-summary-v4`
(主語明確化・登場人物リスト注入・本文中evidence ID参照禁止 +
domain context注入対応)、`STORY_SUMMARY_PROMPT_VERSION`は
`story-summary-v3`(全文直接入力方式 + domain context注入対応)へ更新した。
`STORY_SUMMARY_PROMPT_VERSION_FALLBACK`はcontextサイズガード超過時に
使われるv1方式の値。`generate_episode_summary`/`synthesize_story_summary`/
`generate_story_summary_draft`は`refine`引数(既定OFF)で自己推敲パスを
opt-inできる。

domain context注入・本文中evidence ID引用の機械的除去
(`summary-domain-context-injection`、2026-07-19ユーザーレビュー承認済み。
詳細は`agents/summarizer/domain_context.py`/`prompt.py`/`generator.py`の
module docstring参照): `load_domain_context`が
`knowledge/dictionaries/summary_domain_context.yaml`(commit対象、人間
確認済み事実のみ)を読み込み、`generate_episode_summary`等の
`domain_context`引数へ渡すとsystem promptへ注入される
(ファイル未設置/空の場合は従来動作、後方互換)。実際に注入された場合は
`promptVersion`へ`DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX`
(`domain-context-v1`)が追記される。加えて`strip_evidence_id_citations`が
生成text中の括弧書きblockId引用を機械的に除去する(防御の二重化、
`scripts/check_story_summary_drafts.py`の新規quality gate検証が最終
防衛線として残る)。

docs/architecture/06_AI/Story_Summary_Generation_Plan.md
docs/architecture/06_AI/Story_Summary_Design.md
schemas/story_summary.schema.json
"""

from .domain_context import DEFAULT_DOMAIN_CONTEXT_PATH, load_domain_context
from .generator import (
    DEFAULT_VERBATIM_THRESHOLD,
    DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX,
    EVIDENCE_ID_PATTERN,
    EpisodeSummaryGenerationResult,
    GenerationIssue,
    StorySummaryGenerationResult,
    StorySynthesisResult,
    check_verbatim_quotes,
    generate_episode_summary,
    generate_story_summary_draft,
    strip_evidence_id_citations,
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
    DOMAIN_CONTEXT_BLOCK_HEADER,
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
    build_domain_context_block,
    build_episode_summary_prompt,
    build_episode_summary_system_prompt,
    build_refine_prompt,
    build_refine_system_prompt,
    build_story_summary_prompt,
    build_story_summary_prompt_v2,
    build_story_summary_system_prompt,
    build_story_summary_system_prompt_v2,
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
    "DEFAULT_DOMAIN_CONTEXT_PATH",
    "load_domain_context",
    "DOMAIN_CONTEXT_BLOCK_HEADER",
    "DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX",
    "build_domain_context_block",
    "build_episode_summary_system_prompt",
    "build_story_summary_system_prompt",
    "build_story_summary_system_prompt_v2",
    "build_refine_system_prompt",
    "EVIDENCE_ID_PATTERN",
    "strip_evidence_id_citations",
]
