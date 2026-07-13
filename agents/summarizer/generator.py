"""
DKB Summarizer - Generator
Episode Summary生成: 入力抽出 -> LLM呼び出し -> hallucination対策の後処理 ->
draft組み立て。加えて、Episode Summary群からStory Summaryを合成するロジック
(docs/architecture/06_AI/Story_Summary_Generation_Plan.md §6 / §9 / §11
 `summary-generation-prompt-implementation` / `summary-generation-story-
 synthesis`)。

ユーザーが2026-07-13にsummarizer系のprompt実装を明示的に解禁したことを受けて
実装する（`AI_CONTEXT.md` §4。`agents/extractor/`は引き続き未解禁のまま）。

Story Summary合成 (Plan §11で確定):
- 合成方式はLLM再要約。生成済みEpisode Summary群のtext (episodeNumber順)
  を入力とし、story全体の簡潔なあらすじを再度LLMに生成させる
  (`format_json=True`、出力は`{"text": "..."}`のみ)
- story-level evidenceRefsはLLM出力からではなく、episode-level
  evidenceRefsの重複排除union (episodeNumber順 -> episode内出現順で安定
  ソート) を後処理で機械的に設定する (`_union_evidence_refs`)
- 後処理は応答JSON parse失敗・`text`キー欠落・空text (いずれもblocking)・
  禁止文字列scan (非blocking) のみ。**verbatim引用検出は行わない**
  (入力が既にsafeなepisode summaryであり、生のセリフ本文ではないため)
- 入力Episode Summary群の合計文字数が`max_input_characters`を超える場合は
  issueを立てて合成をskipする (episode側と同じ安全弁パターン)
- issueを持つepisode (実在しないblockId引用等) が1つでもある場合でも
  合成自体は行うが、非blocking issue `source-episode-has-issues`として
  記録する (人間レビューで判断、Plan §11)

hallucination対策の後処理（Plan §6.3、§8.1）:
1. 実在blockId検証: 引用blockIdがそのepisodeの入力Block集合に実在するか
2. 禁止文字列scan: `agents/wiki_generator/story_summaries.py`の
   `FORBIDDEN_TEXT_PATTERNS`をそのままimportして再利用する
3. 長文verbatim引用検出: 生成textと各入力Block本文との連続一致部分列を
   検出する (既定閾値`DEFAULT_VERBATIM_THRESHOLD`文字、呼び出し側で変更可)

**重要**: 上記いずれの検出も自動rejectはしない。検出結果は`GenerationIssue`
として記録するのみで、draft自体は生成される
(`generationStatus: "draft"`のまま人間レビュー待ち、Plan §6.3)。
draftが生成されない (`draft is None`) のは、以下の「生成自体が成立しない」
致命的なケースのみ:

- episodeに入力Block (dialogue/monologue/narration/choice) が1件も無い
- 入力テキストが`max_input_characters`を超える (Plan §6.4の安全弁、
  chunk分割は本PRでは未実装)
- LLM呼び出し自体が失敗した (`LLMProviderError`)
- LLM応答がJSONとしてparseできない、または必須キー`text`が無い/空

`evidenceRefs`キー自体が無い、または不正な要素を含む場合は、後処理issueを
記録した上で空リスト/フィルタ済みリストとして扱う（`text`さえ得られれば
draftは生成される）。

長文episodeの2段階chunk分割要約 (Plan §6.4) は本PRのスコープ外。
`max_input_characters`超過時は生成をskipするのみで、分割・再統合は
実装しない (PoC後の必要性判断に委ねる)。
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from agents.wiki_generator.story_summaries import FORBIDDEN_TEXT_PATTERNS

from .models import EpisodeSummaryDraft, StorySummaryDraft, SummaryProvenance
from .prompt import (
    DEFAULT_MAX_INPUT_CHARACTERS,
    EPISODE_SUMMARY_SYSTEM_PROMPT,
    PROMPT_VERSION,
    STORY_SUMMARY_PROMPT_VERSION,
    STORY_SUMMARY_SYSTEM_PROMPT,
    EpisodeSummaryInput,
    ExtractedBlock,
    build_episode_summary_prompt,
    build_story_summary_prompt,
    extract_episode_blocks,
    render_blocks_text,
    render_episode_summaries_text,
)
from .provider import LLMProviderError, SummaryLLMProvider

# 長文verbatim引用検出の既定閾値 (文字数、Plan §6.3。「短い一文引用程度」を
# 超える連続一致を検出対象とする目安として30文字を既定値とする。CLI側の
# `--verbatim-threshold`で変更可能)。
DEFAULT_VERBATIM_THRESHOLD = 30

_VERBATIM_QUOTE_PREVIEW_LENGTH = 40


@dataclass(frozen=True)
class GenerationIssue:
    """hallucination対策後処理、またはLLM呼び出し自体で検出された問題。

    `code`はテスト・reportで機械的に集計できるようkebab-caseの短い識別子と
    する。`blocking`が`True`のissueはdraft自体を生成できない致命的な
    ケース (LLM呼び出し失敗・応答parse失敗・必須キー欠落・入力Block無し・
    入力長超過) を表す。`blocking=False`のissueはhallucination対策の
    検出結果であり、draftは生成された上でこのissueが付随する。
    """

    code: str
    message: str
    blocking: bool = False


@dataclass
class EpisodeSummaryGenerationResult:
    """1 episode分の生成結果。"""

    episode_id: str | None
    draft: EpisodeSummaryDraft | None
    issues: list[GenerationIssue] = field(default_factory=list)
    model_provider: str | None = None
    model_name: str | None = None

    @property
    def skipped(self) -> bool:
        return self.draft is None


@dataclass
class StorySynthesisResult:
    """Story Summary合成 (Episode Summary群 -> Story Summary) の結果
    (`synthesize_story_summary`の戻り値、Plan §11)。

    `story_text`が`None`の場合は合成が成立しなかった (skip) ことを表す。
    `evidence_refs`はLLM出力からではなく、`_union_evidence_refs`による
    episode-level evidenceRefsの機械的unionである (`story_text`がNoneの
    場合は常に空リスト)。
    """

    story_text: str | None
    evidence_refs: list[str] = field(default_factory=list)
    issues: list[GenerationIssue] = field(default_factory=list)
    model_provider: str | None = None
    model_name: str | None = None

    @property
    def skipped(self) -> bool:
        return self.story_text is None


@dataclass
class StorySummaryGenerationResult:
    """1 story分の生成結果 (Episode Summary群 + Story Summary合成 +
    組み立て済みdraft)。

    `story_synthesis`は`generate_story_summary_draft`の`synthesize_story`
    引数が`False`の場合は`None`のまま (合成自体を行っていないことを表す。
    合成を試みたが成立しなかった場合は`StorySynthesisResult(story_text=
    None, ...)`になる、`None`とは区別される)。

    `provenance`は`draft.to_document_dict(provenance)`を呼び出す際に
    そのまま渡せる`SummaryProvenance`である
    (`promptVersion`/`generatedAt`/`inputRefs`はここで確定済み、
    `model_provider`/`model_name`は成功したepisode結果、無ければstory
    synthesis結果から引き継ぐ)。
    """

    story_id: str | None
    draft: StorySummaryDraft
    provenance: SummaryProvenance
    episode_results: list[EpisodeSummaryGenerationResult] = field(default_factory=list)
    story_synthesis: StorySynthesisResult | None = None

    @property
    def has_issues(self) -> bool:
        episode_issues = any(result.issues for result in self.episode_results)
        story_issues = bool(self.story_synthesis and self.story_synthesis.issues)
        return episode_issues or story_issues

    @property
    def total_issue_count(self) -> int:
        episode_count = sum(len(result.issues) for result in self.episode_results)
        story_count = len(self.story_synthesis.issues) if self.story_synthesis else 0
        return episode_count + story_count

    def to_document_dict(self) -> dict[str, Any]:
        """`draft.to_document_dict(self.provenance)`のショートカット。"""
        return self.draft.to_document_dict(self.provenance)


def _current_timestamp() -> str:
    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


# ----------------------------------------------------------------
# LLM応答のparse (Plan §6.2: {"text": "...", "evidenceRefs": [...]})
# ----------------------------------------------------------------


def _parse_llm_response(
    raw_text: str,
) -> tuple[dict[str, Any] | None, list[GenerationIssue]]:
    """LLM応答テキストをparseし、`{"text": str, "evidenceRefs": list[str]}`
    形へ正規化する。

    parse失敗、または`text`キーが無い/空の場合は致命的issueとして扱い
    (戻り値の辞書はNone)、それ以外のevidenceRefs関連の問題は非致命的issueと
    して記録する (Plan §6.2「応答JSONのparse失敗・必須キー欠落は後処理issue
    として扱う」)。
    """
    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        return None, [
            GenerationIssue(
                "response-not-json",
                f"LLM応答のJSON parseに失敗しました: {exc}",
                blocking=True,
            )
        ]

    if not isinstance(parsed, dict):
        return None, [
            GenerationIssue(
                "response-not-object",
                f"LLM応答がJSON objectではありません (got {type(parsed).__name__})",
                blocking=True,
            )
        ]

    text_value = parsed.get("text")
    if not isinstance(text_value, str) or not text_value.strip():
        return None, [
            GenerationIssue(
                "missing-text-key",
                "LLM応答に非空の'text'キーがありません",
                blocking=True,
            )
        ]

    issues: list[GenerationIssue] = []
    raw_refs = parsed.get("evidenceRefs")
    evidence_refs: list[str] = []
    if raw_refs is None:
        issues.append(
            GenerationIssue(
                "missing-evidence-refs-key",
                "LLM応答に'evidenceRefs'キーがありません (空配列として扱います)",
            )
        )
    elif not isinstance(raw_refs, list):
        issues.append(
            GenerationIssue(
                "invalid-evidence-refs-type",
                "LLM応答の'evidenceRefs'がlistではありません (空配列として扱います)",
            )
        )
    else:
        for ref in raw_refs:
            if isinstance(ref, str) and ref.strip():
                evidence_refs.append(ref.strip())
            else:
                issues.append(
                    GenerationIssue(
                        "invalid-evidence-ref-item",
                        f"evidenceRefsに不正な要素があります: {ref!r} (除外しました)",
                    )
                )

    return {"text": text_value.strip(), "evidenceRefs": evidence_refs}, issues


# ----------------------------------------------------------------
# hallucination対策の後処理チェック (Plan §6.3)
# ----------------------------------------------------------------


def _check_evidence_refs_exist(
    evidence_refs: list[str], valid_block_ids: frozenset[str]
) -> list[GenerationIssue]:
    """実在blockId検証 (Plan §6.3項目2)。"""
    return [
        GenerationIssue(
            "unknown-evidence-ref",
            f"引用blockId '{ref}' はこのepisodeの入力Blockに実在しません",
        )
        for ref in evidence_refs
        if ref not in valid_block_ids
    ]


def _check_forbidden_text(text: str) -> list[GenerationIssue]:
    """禁止文字列scan (Plan §6.3項目3、
    `agents.wiki_generator.story_summaries.FORBIDDEN_TEXT_PATTERNS`を
    そのまま再利用する)。"""
    return [
        GenerationIssue(
            "forbidden-text-pattern",
            f"生成textに禁止文字列 '{pattern}' が含まれています",
        )
        for pattern in FORBIDDEN_TEXT_PATTERNS
        if pattern in text
    ]


def check_verbatim_quotes(
    text: str, blocks: list[ExtractedBlock], *, threshold: int
) -> list[GenerationIssue]:
    """長文verbatim引用検出 (Plan §6.3項目4)。

    生成textと各入力Blockの本文との、最長連続一致部分列 (contiguous
    matching substring) を`difflib.SequenceMatcher.find_longest_match`で
    検出し、`threshold`文字以上一致するBlockがあればissueとして記録する。

    公開関数 (アンダースコアなし): `scripts/check_story_summary_drafts.py`
    (`summary-generation-quality-gate`) が、draft (episode summaryのtext)
    とNormalized Story JSON由来のBlockとの verbatim検出に再利用するため、
    このモジュール外からimportできる名前にしている
    (`summary-generation-prompt-implementation`時点では
    `_check_verbatim_quotes`という非公開名だった)。
    """
    issues: list[GenerationIssue] = []
    for block in blocks:
        matcher = difflib.SequenceMatcher(None, text, block.text, autojunk=False)
        match = matcher.find_longest_match(0, len(text), 0, len(block.text))
        if match.size < threshold:
            continue
        quoted = text[match.a : match.a + match.size]
        preview = (
            quoted
            if len(quoted) <= _VERBATIM_QUOTE_PREVIEW_LENGTH
            else quoted[:_VERBATIM_QUOTE_PREVIEW_LENGTH] + "..."
        )
        issues.append(
            GenerationIssue(
                "verbatim-quote",
                f"生成textが{block.block_id}の本文と{match.size}文字の"
                f"連続一致を含んでいます (閾値{threshold}文字): '{preview}'",
            )
        )
    return issues


# ----------------------------------------------------------------
# Episode単位の生成
# ----------------------------------------------------------------


def generate_episode_summary(
    episode: dict[str, Any],
    *,
    provider: SummaryLLMProvider,
    max_input_characters: int = DEFAULT_MAX_INPUT_CHARACTERS,
    verbatim_threshold: int = DEFAULT_VERBATIM_THRESHOLD,
) -> EpisodeSummaryGenerationResult:
    """1 episode分のEpisode Summary draftを生成する。

    入力抽出 (`extract_episode_blocks`) -> prompt構築
    (`build_episode_summary_prompt`) -> LLM呼び出し
    (`provider.generate(..., format_json=True)`) -> 応答parse -> 後処理
    (hallucination対策) -> `EpisodeSummaryDraft`組み立て、の順で処理する。
    """
    episode_id = episode.get("episodeId")

    blocks = extract_episode_blocks(episode)
    if not blocks:
        return EpisodeSummaryGenerationResult(
            episode_id=episode_id,
            draft=None,
            issues=[
                GenerationIssue(
                    "no-input-blocks",
                    "dialogue/monologue/narration/choiceのBlockが"
                    "1件もありません (stage_direction/unknownのみ、"
                    "または空episode)",
                    blocking=True,
                )
            ],
        )

    rendered_text = render_blocks_text(blocks)
    if len(rendered_text) > max_input_characters:
        return EpisodeSummaryGenerationResult(
            episode_id=episode_id,
            draft=None,
            issues=[
                GenerationIssue(
                    "input-too-long",
                    f"入力テキストが{len(rendered_text)}文字で、"
                    f"上限{max_input_characters}文字を超えています "
                    "(chunk分割2段階要約は本PRでは未実装、Plan §6.4の"
                    "安全弁として生成をskipしました)",
                    blocking=True,
                )
            ],
        )

    prompt = build_episode_summary_prompt(blocks)
    try:
        completion = provider.generate(
            prompt, system=EPISODE_SUMMARY_SYSTEM_PROMPT, format_json=True
        )
    except LLMProviderError as exc:
        return EpisodeSummaryGenerationResult(
            episode_id=episode_id,
            draft=None,
            issues=[
                GenerationIssue(
                    "llm-provider-error",
                    f"LLM呼び出しに失敗しました: {exc}",
                    blocking=True,
                )
            ],
        )

    parsed, parse_issues = _parse_llm_response(completion.text)
    if parsed is None:
        return EpisodeSummaryGenerationResult(
            episode_id=episode_id,
            draft=None,
            issues=parse_issues,
            model_provider=completion.provider_name,
            model_name=completion.model_name,
        )

    text = parsed["text"]
    valid_block_ids = frozenset(block.block_id for block in blocks)
    issues: list[GenerationIssue] = list(parse_issues)
    issues.extend(_check_evidence_refs_exist(parsed["evidenceRefs"], valid_block_ids))
    issues.extend(_check_forbidden_text(text))
    issues.extend(check_verbatim_quotes(text, blocks, threshold=verbatim_threshold))

    draft = EpisodeSummaryDraft(
        episode_id=episode_id,
        text=text,
        evidence_refs=parsed["evidenceRefs"],
        public_episode_id=(episode.get("metadata") or {}).get("publicEpisodeId"),
        episode_number=episode.get("episodeNumber"),
    )

    return EpisodeSummaryGenerationResult(
        episode_id=episode_id,
        draft=draft,
        issues=issues,
        model_provider=completion.provider_name,
        model_name=completion.model_name,
    )


# ----------------------------------------------------------------
# Story Summary合成 (Episode Summary群 -> Story Summary、Plan §11)
# ----------------------------------------------------------------


def _parse_story_summary_response(
    raw_text: str,
) -> tuple[str | None, list[GenerationIssue]]:
    """story合成LLM応答テキストをparseし、`text`を取り出す。

    episode側の`_parse_llm_response`と異なり、story-level出力は
    `{"text": "..."}`のみを期待する (`evidenceRefs`はLLMに求めない、Plan
    §11)。parse失敗・object以外・`text`キー欠落/空はいずれもblocking issue
    として扱う。
    """
    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        return None, [
            GenerationIssue(
                "response-not-json",
                f"LLM応答のJSON parseに失敗しました: {exc}",
                blocking=True,
            )
        ]

    if not isinstance(parsed, dict):
        return None, [
            GenerationIssue(
                "response-not-object",
                f"LLM応答がJSON objectではありません (got {type(parsed).__name__})",
                blocking=True,
            )
        ]

    text_value = parsed.get("text")
    if not isinstance(text_value, str) or not text_value.strip():
        return None, [
            GenerationIssue(
                "missing-text-key",
                "LLM応答に非空の'text'キーがありません",
                blocking=True,
            )
        ]

    return text_value.strip(), []


def _order_episode_drafts_by_number(
    episode_drafts: list[EpisodeSummaryDraft],
) -> list[EpisodeSummaryDraft]:
    """`episode_number`昇順 (Noneは末尾) に安定sortする (Plan §11
    「episodeNumber順」)。同順位・None同士は元の並び順を保つ (stable sort)。
    """
    return sorted(
        episode_drafts,
        key=lambda draft: (draft.episode_number is None, draft.episode_number or 0),
    )


def _union_evidence_refs(
    ordered_episode_drafts: list[EpisodeSummaryDraft],
) -> list[str]:
    """episode-level evidenceRefsの重複排除union
    (episodeNumber順 -> episode内出現順で安定ソート、Plan §11)。

    呼び出し側は`_order_episode_drafts_by_number`済みのlistを渡すこと。
    """
    seen: set[str] = set()
    result: list[str] = []
    for draft in ordered_episode_drafts:
        for ref in draft.evidence_refs:
            if ref not in seen:
                seen.add(ref)
                result.append(ref)
    return result


def synthesize_story_summary(
    episode_drafts: list[EpisodeSummaryDraft],
    *,
    provider: SummaryLLMProvider,
    max_input_characters: int = DEFAULT_MAX_INPUT_CHARACTERS,
    episodes_with_issues: list[str] | None = None,
) -> StorySynthesisResult:
    """生成済みEpisode Summary群からStory Summaryを合成する (Plan §11)。

    - `episode_drafts`が空の場合は合成不能としてblocking issueを立てて
      skipする (LLM呼び出しは行わない)
    - 入力テキスト (episodeNumber順に整形したEpisode Summary text群) の
      合計文字数が`max_input_characters`を超える場合もblocking issueを
      立ててskipする (episode側と同じ安全弁パターン、chunk分割は未実装)
    - LLM呼び出し失敗・応答parse失敗・`text`キー欠落/空はblocking
    - 禁止文字列scanは非blocking (`FORBIDDEN_TEXT_PATTERNS`再利用)。
      **verbatim引用検出は行わない** (入力が既にsafeなepisode summaryの
      ため、Plan §11)
    - `episodes_with_issues` (episode-level issueを持つepisodeIdのlist) が
      非空の場合、合成自体は行った上で非blocking issue
      `source-episode-has-issues`として記録する (Plan §11)
    - `evidence_refs`はLLM出力からではなく、`_union_evidence_refs`による
      機械的unionを設定する (合成成功時のみ、skip時は空リスト)
    """
    if not episode_drafts:
        return StorySynthesisResult(
            story_text=None,
            issues=[
                GenerationIssue(
                    "no-episode-summaries",
                    "Episode Summaryが1件も生成されていないため、"
                    "Story Summary合成をskipしました",
                    blocking=True,
                )
            ],
        )

    ordered = _order_episode_drafts_by_number(episode_drafts)
    inputs = [
        EpisodeSummaryInput(episode_number=draft.episode_number, text=draft.text)
        for draft in ordered
    ]
    rendered_text = render_episode_summaries_text(inputs)
    if len(rendered_text) > max_input_characters:
        return StorySynthesisResult(
            story_text=None,
            issues=[
                GenerationIssue(
                    "input-too-long",
                    f"入力テキスト(Episode Summary群)が{len(rendered_text)}"
                    f"文字で、上限{max_input_characters}文字を超えています "
                    "(chunk分割は未実装、Story Summary合成をskipしました)",
                    blocking=True,
                )
            ],
        )

    prompt = build_story_summary_prompt(inputs)
    try:
        completion = provider.generate(
            prompt, system=STORY_SUMMARY_SYSTEM_PROMPT, format_json=True
        )
    except LLMProviderError as exc:
        return StorySynthesisResult(
            story_text=None,
            issues=[
                GenerationIssue(
                    "llm-provider-error",
                    f"LLM呼び出しに失敗しました: {exc}",
                    blocking=True,
                )
            ],
        )

    text, parse_issues = _parse_story_summary_response(completion.text)
    if text is None:
        return StorySynthesisResult(
            story_text=None,
            issues=parse_issues,
            model_provider=completion.provider_name,
            model_name=completion.model_name,
        )

    issues: list[GenerationIssue] = list(parse_issues)
    issues.extend(_check_forbidden_text(text))
    if episodes_with_issues:
        joined = ", ".join(str(episode_id) for episode_id in episodes_with_issues)
        issues.append(
            GenerationIssue(
                "source-episode-has-issues",
                f"合成に使用した{len(episodes_with_issues)}件のEpisode "
                f"Summaryにgeneration issueがあります (人間レビューで判断"
                f"してください): {joined}",
            )
        )

    return StorySynthesisResult(
        story_text=text,
        evidence_refs=_union_evidence_refs(ordered),
        issues=issues,
        model_provider=completion.provider_name,
        model_name=completion.model_name,
    )


# ----------------------------------------------------------------
# Story単位の生成 (Episode Summary群のdraft組み立て + Story Summary合成)
# ----------------------------------------------------------------


def generate_story_summary_draft(
    document: dict[str, Any],
    *,
    provider: SummaryLLMProvider,
    max_input_characters: int = DEFAULT_MAX_INPUT_CHARACTERS,
    verbatim_threshold: int = DEFAULT_VERBATIM_THRESHOLD,
    synthesize_story: bool = True,
) -> StorySummaryGenerationResult:
    """Normalized Story JSON 1 story分から、Episode Summary群のdraftと
    (既定で) 合成済みStory Summaryを含む`StorySummaryDraft`を組み立てる。

    `synthesize_story=False`の場合、Story Summary合成自体を行わない
    (`draft.story_text`は常に`None`、`story_synthesis`は`None`のまま)。
    既定は`True` (Plan §11「story合成は既定で有効」)。
    """
    story_id = document.get("storyId")
    episodes = document.get("episodes", []) or []

    episode_results = [
        generate_episode_summary(
            episode,
            provider=provider,
            max_input_characters=max_input_characters,
            verbatim_threshold=verbatim_threshold,
        )
        for episode in episodes
    ]

    episode_drafts = [
        result.draft for result in episode_results if result.draft is not None
    ]

    story_synthesis: StorySynthesisResult | None = None
    if synthesize_story:
        episodes_with_issues = [
            result.episode_id
            for result in episode_results
            if result.issues and result.episode_id
        ]
        story_synthesis = synthesize_story_summary(
            episode_drafts,
            provider=provider,
            max_input_characters=max_input_characters,
            episodes_with_issues=episodes_with_issues,
        )

    provenance = _build_provenance(episode_results, story_synthesis)

    notes = _build_notes(episode_results, story_synthesis)

    draft = StorySummaryDraft(
        story_id=story_id,
        public_story_id=(document.get("metadata") or {}).get("publicStoryId"),
        story_text=story_synthesis.story_text if story_synthesis else None,
        story_evidence_refs=(
            story_synthesis.evidence_refs
            if story_synthesis is not None and story_synthesis.story_text is not None
            else []
        ),
        episode_summaries=episode_drafts,
        notes=notes,
    )

    return StorySummaryGenerationResult(
        story_id=story_id,
        draft=draft,
        provenance=provenance,
        episode_results=episode_results,
        story_synthesis=story_synthesis,
    )


def _build_provenance(
    episode_results: list[EpisodeSummaryGenerationResult],
    story_synthesis: StorySynthesisResult | None = None,
) -> SummaryProvenance:
    """成功した最初のepisode結果からmodel provenanceを引き継ぐ
    (episode側が全て失敗している場合は、成功したstory synthesisの値で
    補完する)。

    `prompt_version`は、story synthesisが実際にstory_textを生成できた
    場合のみ、episode用`PROMPT_VERSION`にstory用
    `STORY_SUMMARY_PROMPT_VERSION`をカンマ区切りで併記する
    (schema上`source.promptVersion`は単一文字列のため)。
    """
    model_provider: str | None = None
    model_name: str | None = None
    for result in episode_results:
        if result.model_provider or result.model_name:
            model_provider = result.model_provider
            model_name = result.model_name
            break
    if model_provider is None and model_name is None and story_synthesis is not None:
        model_provider = story_synthesis.model_provider
        model_name = story_synthesis.model_name

    prompt_versions = [PROMPT_VERSION]
    if story_synthesis is not None and story_synthesis.story_text is not None:
        prompt_versions.append(STORY_SUMMARY_PROMPT_VERSION)

    return SummaryProvenance(
        model_provider=model_provider,
        model_name=model_name,
        prompt_version=",".join(prompt_versions),
        generated_at=_current_timestamp(),
        input_refs=[
            result.episode_id for result in episode_results if result.episode_id
        ],
    )


def _build_notes(
    episode_results: list[EpisodeSummaryGenerationResult],
    story_synthesis: StorySynthesisResult | None = None,
) -> str | None:
    """issueがあるepisode、およびstory synthesis issueを、YAML `notes`欄に
    要約として記録する (詳細な内訳はCLI側のreport.mdに記載する、Playbook
    実装指示どおり)。"""
    parts: list[str] = []

    episode_ids_with_issues = [
        result.episode_id for result in episode_results if result.issues
    ]
    if episode_ids_with_issues:
        joined = ", ".join(str(episode_id) for episode_id in episode_ids_with_issues)
        parts.append(
            f"{len(episode_ids_with_issues)} episode(s) have generation issues "
            f"(see report): {joined}"
        )

    if story_synthesis is not None and story_synthesis.issues:
        codes = ", ".join(issue.code for issue in story_synthesis.issues)
        parts.append(f"story synthesis has issues (see report): {codes}")

    if not parts:
        return None
    return " / ".join(parts)
