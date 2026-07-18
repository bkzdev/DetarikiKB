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

品質改善v2/v3・自己推敲パス (`summary-generation-quality-v2`、RAID small
batchの人間レビューで確認された品質問題2点への対策、2026-07-18ユーザー
承認済み。実promptの設計理由は`agents/summarizer/prompt.py`のmodule
docstring参照):
- **story-summary-v2**: `synthesize_story_summary`のStory Summary合成を、
  Episode Summary群の再要約(v1)から全episode本文の直接入力(v2、既定)へ
  変更した。`episodes`(元episode dict一覧)が与えられ、入力の概算トークン数
  (`estimate_token_count`) が`max_context_tokens`以下であればv2を使う。
  超過時、または`episodes`が与えられない/対応する元episode dictが見つから
  ない場合はv1へフォールバックする(失敗にしない。フォールバック時のみ
  非blocking issue `story-synthesis-context-fallback`を記録する)。実際に
  使われた方式は`StorySynthesisResult.prompt_version`に記録され、
  `_build_provenance`がdraft全体の`source.promptVersion`へ反映する
- **episode-summary-v3**: `generate_episode_summary`自体のロジックは
  不変。`agents/summarizer/prompt.py`の`PROMPT_VERSION`更新
  (主語明確化指示・登場人物リスト注入・本文中evidence ID参照禁止指示) が
  反映される
- **自己推敲パス (`refine`引数、既定OFF)**: `generate_episode_summary`/
  `synthesize_story_summary`両方に`refine`引数を追加した。`True`の場合、
  生成成功後に`_refine_episode_draft`/`_refine_story_text`で同モデルへの
  推敲呼び出しを1周追加実行する。推敲呼び出し自体の失敗・応答parse失敗は
  非blocking issueとして記録し、元のtextを維持する(draftを潰さない)。
  使用時は`_build_provenance`が`promptVersion`へ`refine-v1`を追記する

domain context注入・本文中evidence ID引用の機械的除去
(`summary-domain-context-injection`、2026-07-19ユーザーレビューで確認
された「話者不明モノローグ(班長=主人公)の近くの名前付きキャラクターへの
誤帰属」対策、実promptの設計理由は`agents/summarizer/prompt.py`のmodule
docstring参照):
- **domain context注入**: `generate_episode_summary`/
  `synthesize_story_summary`/`generate_story_summary_draft`いずれも
  `domain_context: list[str] | None = None`引数を追加した。
  `agents/summarizer/domain_context.py`の`load_domain_context`が返す
  人間確認済みドメイン前提のlistをそのまま各system prompt (episode/
  story v1/v2/refine全て) へ渡す。Noneまたは空リストの場合は既存の
  system prompt文字列を一切変更しない (後方互換)。非空のdomain_contextが
  実際に渡された場合のみ、`_build_provenance`が`promptVersion`へ
  `DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX` (`domain-context-v1`) を追記する
  (`PROMPT_VERSION`のバージョン番号自体はdomain contextファイルの有無に
  関わらず同じ値であるため、実際に注入されたかどうかはこの追記の有無で
  provenanceから判別する設計)
- **本文中evidence ID引用の機械的除去 (防御の二重化)**:
  `strip_evidence_id_citations`/`EVIDENCE_ID_PATTERN`を追加した。LLM
  応答から得たtext (episode summary/story summary/推敲後textいずれも)
  に対し、括弧書き (半角/全角丸括弧・角括弧・隅付き括弧) で囲まれた
  blockId引用を機械的に除去してから既存の禁止文字列scan・verbatim検出
  へ渡す。除去した場合は非blocking issue `evidence-id-citation-stripped`
  として件数を記録する (`_strip_evidence_id_citations_with_issue`)。
  除去によりtextが空になってしまう場合は元のtextを維持し、非blocking
  issue `evidence-id-citation-strip-would-empty-text`を記録する。
  `scripts/check_story_summary_drafts.py`の新規quality gate検証
  (`summary-domain-context-injection`で追加) が、このstripが除去し損ねた
  ケース (括弧を伴わない裸のID出現等) を最終防衛線として引き続き検出する
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from agents.wiki_generator.story_summaries import FORBIDDEN_TEXT_PATTERNS

from .models import EpisodeSummaryDraft, StorySummaryDraft, SummaryProvenance
from .prompt import (
    DEFAULT_MAX_CONTEXT_TOKENS,
    DEFAULT_MAX_INPUT_CHARACTERS,
    PROMPT_VERSION,
    REFINE_PROMPT_VERSION_SUFFIX,
    STORY_SUMMARY_PROMPT_VERSION,
    STORY_SUMMARY_PROMPT_VERSION_FALLBACK,
    EpisodeBlocksInput,
    EpisodeSummaryInput,
    ExtractedBlock,
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
    render_blocks_text,
    render_episode_summaries_text,
    render_story_full_text,
)
from .provider import LLMProviderError, SummaryLLMProvider

# 長文verbatim引用検出の既定閾値 (文字数、Plan §6.3。「短い一文引用程度」を
# 超える連続一致を検出対象とする目安として30文字を既定値とする。CLI側の
# `--verbatim-threshold`で変更可能)。
DEFAULT_VERBATIM_THRESHOLD = 30

_VERBATIM_QUOTE_PREVIEW_LENGTH = 40

# domain contextが実際に注入された (非空list) 場合にprovenanceの
# `promptVersion`へ追記するmarker (`summary-domain-context-injection`)。
# `PROMPT_VERSION`/`STORY_SUMMARY_PROMPT_VERSION`自体はdomain context注入に
# 対応したprompt実装のversionを表すのみで、ファイル未設置/空の場合でも
# 同じ値になる。実際に注入されたかどうかをprovenanceから判別できるように、
# このmarkerを別途追記する (`_build_provenance`)。
DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX = "domain-context-v1"

# ----------------------------------------------------------------
# 本文中evidence/block ID引用の機械的除去 (`summary-domain-context-
# injection`、防御の二重化)
#
# `scripts/check_story_summary_drafts.py`のquality gateが検出する
# パターンと同じID正規表現を使い、括弧書き (半角/全角括弧・角括弧・
# 隅付き括弧) で囲まれたID引用を生成text後処理で機械的に除去する。
# gate側の検出は「防御の最終防衛線」として引き続き有効なまま残す
# (このstripが除去し損ねたケース、括弧を伴わない裸のID出現等を拾う)。
# ----------------------------------------------------------------

# `[A-Z][A-Z0-9_]*_(DLG|MONO|NAR|CHOICE|STAGE|SC)数字` 形式のblockId
# (`agents/parser/normalizer.py`の`IdGenerator`が発番するblockId形式)。
EVIDENCE_ID_PATTERN = re.compile(r"[A-Z][A-Z0-9_]*_(?:DLG|MONO|NAR|CHOICE|STAGE|SC)\d+")

_BRACKET_CHARS = "()（）[]【】"
_EVIDENCE_ID_CITATION_PATTERN = re.compile(
    r"[\(（\[【][^()\[\]（）【】]*"
    + EVIDENCE_ID_PATTERN.pattern
    + r"[^()\[\]（）【】]*[\)）\]】]"
)


def strip_evidence_id_citations(text: str) -> tuple[str, int]:
    """`text`中の括弧書きevidence/block ID引用を機械的に除去する。

    戻り値: (除去後のtext, 除去した件数)。括弧 (半角/全角丸括弧・角括弧・
    隅付き括弧) の中に`EVIDENCE_ID_PATTERN`に一致する文字列を含む場合、
    その括弧書き全体を除去する。除去後に生じた連続空白は単一の半角
    スペースへ畳み、前後の空白をtrimする。一致が無ければ`text`をそのまま
    返す (件数0)。
    """
    if not text:
        return text, 0
    stripped, count = _EVIDENCE_ID_CITATION_PATTERN.subn("", text)
    if count:
        stripped = re.sub(r"[ 　]{2,}", " ", stripped).strip()
    return stripped, count


def _strip_evidence_id_citations_with_issue(
    text: str,
) -> tuple[str, list[GenerationIssue]]:
    """`strip_evidence_id_citations`を実行し、除去件数を`GenerationIssue`
    (非blocking) として記録する。除去の結果textが空/空白のみになって
    しまう場合は元のtextを維持し、人間レビューを促すissueへ切り替える
    (draftが空textのまま生成される事態を避ける安全弁)。
    """
    stripped, count = strip_evidence_id_citations(text)
    if count == 0:
        return text, []
    if not stripped:
        return text, [
            GenerationIssue(
                "evidence-id-citation-strip-would-empty-text",
                "括弧書きevidence/block ID引用の除去によりtextが空になるため、"
                "元のtextを維持しました (人間レビューが必要です)",
            )
        ]
    return stripped, [
        GenerationIssue(
            "evidence-id-citation-stripped",
            f"生成textから括弧書きのevidence/block ID引用を{count}件、"
            "機械的に除去しました",
        )
    ]


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

    `prompt_version`は実際に使われたprompt方式を表す
    (`summary-generation-quality-v2`)。全文直接入力(v2)が成立した場合は
    `STORY_SUMMARY_PROMPT_VERSION` (`story-summary-v2`)、contextサイズ
    ガードで超過した場合・全episode本文を用意できなかった場合は
    `STORY_SUMMARY_PROMPT_VERSION_FALLBACK` (`story-summary-v1-fallback`)。
    `story_text`がNoneの場合 (合成が成立しなかった場合) は`None`のまま。
    """

    story_text: str | None
    evidence_refs: list[str] = field(default_factory=list)
    issues: list[GenerationIssue] = field(default_factory=list)
    model_provider: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None

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
    refine: bool = False,
    domain_context: list[str] | None = None,
) -> EpisodeSummaryGenerationResult:
    """1 episode分のEpisode Summary draftを生成する。

    入力抽出 (`extract_episode_blocks`) -> prompt構築
    (`build_episode_summary_prompt`) -> LLM呼び出し
    (`provider.generate(..., format_json=True)`) -> 応答parse -> 後処理
    (hallucination対策) -> `EpisodeSummaryDraft`組み立て、の順で処理する。

    `refine=True` (既定OFF、`summary-generation-quality-v2`) の場合、
    draft組み立て後にさらに自己推敲パスを1周実行し (`_refine_episode_draft`、
    同モデルで`build_refine_prompt`呼び出し)、`draft.text`を推敲後のtextへ
    差し替える。推敲パス自体が失敗した場合は元のtextを維持し、非blocking
    issueを追加するのみとする (draft自体は必ず生成される設計を維持)。

    `domain_context` (既定None、`summary-domain-context-injection`) は
    `agents/summarizer/domain_context.py`の`load_domain_context`が返す
    人間確認済みドメイン前提のlistで、system promptへそのまま注入される
    (`build_episode_summary_system_prompt`)。Noneまたは空リストの場合は
    system promptを一切変更しない (後方互換)。
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
    system_prompt = build_episode_summary_system_prompt(domain_context)
    try:
        completion = provider.generate(prompt, system=system_prompt, format_json=True)
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

    text, citation_issues = _strip_evidence_id_citations_with_issue(parsed["text"])
    valid_block_ids = frozenset(block.block_id for block in blocks)
    issues: list[GenerationIssue] = list(parse_issues)
    issues.extend(citation_issues)
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

    if refine:
        issues.extend(
            _refine_episode_draft(
                draft,
                blocks,
                provider=provider,
                verbatim_threshold=verbatim_threshold,
                domain_context=domain_context,
            )
        )

    return EpisodeSummaryGenerationResult(
        episode_id=episode_id,
        draft=draft,
        issues=issues,
        model_provider=completion.provider_name,
        model_name=completion.model_name,
    )


# ----------------------------------------------------------------
# 自己推敲パス (`--refine`、既定OFF、`summary-generation-quality-v2`)
# ----------------------------------------------------------------


def _refine_episode_draft(
    draft: EpisodeSummaryDraft,
    blocks: list[ExtractedBlock],
    *,
    provider: SummaryLLMProvider,
    verbatim_threshold: int,
    domain_context: list[str] | None = None,
) -> list[GenerationIssue]:
    """`draft.text`へ自己推敲パスを1周適用する (in-place)。

    推敲呼び出し自体の失敗・応答parse失敗の場合は元のtextを維持し、
    非blockingのissueを記録するのみとする (推敲は既に成立しているdraftへの
    追加処理であり、失敗させてdraft自体を潰さない)。推敲成功時は、推敲後の
    textに対して括弧書きevidence ID引用の除去・禁止文字列scan・長文
    verbatim引用検出を再実行する。`domain_context`は`build_refine_system_
    prompt`へそのまま渡す (`summary-domain-context-injection`)。
    """
    prompt = build_refine_prompt(draft.text)
    system_prompt = build_refine_system_prompt(domain_context)
    try:
        completion = provider.generate(prompt, system=system_prompt, format_json=True)
    except LLMProviderError as exc:
        return [
            GenerationIssue(
                "refine-llm-provider-error",
                f"推敲パスのLLM呼び出しに失敗しました(元のtextを維持しました): {exc}",
            )
        ]

    refined_text, parse_issues = _parse_refine_response(completion.text)
    if refined_text is None:
        return [
            GenerationIssue(
                issue.code,
                f"推敲応答のparseに失敗したため元のtextを維持しました: {issue.message}",
            )
            for issue in parse_issues
        ]

    refined_text, citation_issues = _strip_evidence_id_citations_with_issue(
        refined_text
    )
    draft.text = refined_text
    issues = list(citation_issues)
    issues.extend(_check_forbidden_text(refined_text))
    issues.extend(
        check_verbatim_quotes(refined_text, blocks, threshold=verbatim_threshold)
    )
    return issues


def _refine_story_text(
    text: str, *, provider: SummaryLLMProvider, domain_context: list[str] | None = None
) -> tuple[str, list[GenerationIssue]]:
    """story_textへ自己推敲パスを1周適用する。

    `_refine_episode_draft`と同じ方針: 推敲呼び出し自体の失敗・応答parse
    失敗時は元のtextを維持し、非blocking issueを記録するのみとする。
    story合成は元々verbatim引用検出を行わない設計のため
    (`synthesize_story_summary`のdocstring参照)、推敲後のtextに対しては
    括弧書きevidence ID引用の除去・禁止文字列scanのみ再実行する。
    `domain_context`は`build_refine_system_prompt`へそのまま渡す。
    """
    prompt = build_refine_prompt(text)
    system_prompt = build_refine_system_prompt(domain_context)
    try:
        completion = provider.generate(prompt, system=system_prompt, format_json=True)
    except LLMProviderError as exc:
        return text, [
            GenerationIssue(
                "refine-llm-provider-error",
                f"推敲パスのLLM呼び出しに失敗しました(元のtextを維持しました): {exc}",
            )
        ]

    refined_text, parse_issues = _parse_refine_response(completion.text)
    if refined_text is None:
        return text, [
            GenerationIssue(
                issue.code,
                f"推敲応答のparseに失敗したため元のtextを維持しました: {issue.message}",
            )
            for issue in parse_issues
        ]

    refined_text, citation_issues = _strip_evidence_id_citations_with_issue(
        refined_text
    )
    issues = list(citation_issues)
    issues.extend(_check_forbidden_text(refined_text))
    return refined_text, issues


# ----------------------------------------------------------------
# Story Summary合成 (Episode Summary群 -> Story Summary、Plan §11)
# ----------------------------------------------------------------


def _parse_single_text_field_response(
    raw_text: str,
    *,
    not_json_code: str,
    not_object_code: str,
    missing_key_code: str,
) -> tuple[str | None, list[GenerationIssue]]:
    """`{"text": "..."}`のみを期待する応答を共通parseするヘルパー。

    story合成 (`_parse_story_summary_response`) と自己推敲パス
    (`_parse_refine_response`) の両方から使う (`summary-generation-
    quality-v2`でのリファクタ、issue codeは呼び出し側が指定する)。
    parse失敗・object以外・`text`キー欠落/空はいずれもblocking issueとして
    扱う (blocking扱いをどう解釈するかは呼び出し側の責務。自己推敲パスの
    呼び出し元は失敗時に元のtextを維持し非blocking issueへ読み替える)。
    """
    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        return None, [
            GenerationIssue(
                not_json_code,
                f"LLM応答のJSON parseに失敗しました: {exc}",
                blocking=True,
            )
        ]

    if not isinstance(parsed, dict):
        return None, [
            GenerationIssue(
                not_object_code,
                f"LLM応答がJSON objectではありません (got {type(parsed).__name__})",
                blocking=True,
            )
        ]

    text_value = parsed.get("text")
    if not isinstance(text_value, str) or not text_value.strip():
        return None, [
            GenerationIssue(
                missing_key_code,
                "LLM応答に非空の'text'キーがありません",
                blocking=True,
            )
        ]

    return text_value.strip(), []


def _parse_story_summary_response(
    raw_text: str,
) -> tuple[str | None, list[GenerationIssue]]:
    """story合成LLM応答テキストをparseし、`text`を取り出す。

    episode側の`_parse_llm_response`と異なり、story-level出力は
    `{"text": "..."}`のみを期待する (`evidenceRefs`はLLMに求めない、Plan
    §11)。parse失敗・object以外・`text`キー欠落/空はいずれもblocking issue
    として扱う。v1方式(Episode Summary群の再要約)・v2方式(全文直接入力)の
    いずれの合成呼び出しからも共用する (出力formatはv1/v2で同一)。
    """
    return _parse_single_text_field_response(
        raw_text,
        not_json_code="response-not-json",
        not_object_code="response-not-object",
        missing_key_code="missing-text-key",
    )


def _parse_refine_response(
    raw_text: str,
) -> tuple[str | None, list[GenerationIssue]]:
    """自己推敲パスのLLM応答テキストをparseし、`text`を取り出す
    (`summary-generation-quality-v2`)。出力formatはstory合成応答と同じ
    `{"text": "..."}`。issue codeは`refine-`prefixで区別する (呼び出し側は
    parse失敗時、blockingフラグを無視して元のtextを維持し非blocking issue
    として記録する)。
    """
    return _parse_single_text_field_response(
        raw_text,
        not_json_code="refine-response-not-json",
        not_object_code="refine-response-not-object",
        missing_key_code="refine-missing-text-key",
    )


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


_SynthesisAttempt = tuple[str | None, list[GenerationIssue], str | None, str | None]


def _build_full_text_items(
    ordered_episode_drafts: list[EpisodeSummaryDraft],
    episodes: list[dict[str, Any]],
) -> list[EpisodeBlocksInput]:
    """story-summary-v2 (全文直接入力方式) 用に、`ordered_episode_drafts`の
    各episodeに対応する元episode dictから`extract_episode_blocks`で本文を
    再抽出し、`EpisodeBlocksInput`一覧を組み立てる (`summary-generation-
    quality-v2`)。

    いずれかのdraftに対応する元episode dictが`episodes`中に見つからない
    場合は、全体を空リストで返す (部分的な全文入力は作らない安全側の判断。
    呼び出し側`synthesize_story_summary`はこれをv1方式へのフォールバック
    条件として扱う)。
    """
    episodes_by_id = {ep.get("episodeId"): ep for ep in episodes if ep.get("episodeId")}
    items: list[EpisodeBlocksInput] = []
    for draft in ordered_episode_drafts:
        episode = episodes_by_id.get(draft.episode_id)
        if episode is None:
            return []
        items.append(
            EpisodeBlocksInput(
                episode_number=draft.episode_number,
                blocks=extract_episode_blocks(episode),
            )
        )
    return items


def _synthesize_story_summary_full_text(
    full_text_items: list[EpisodeBlocksInput],
    provider: SummaryLLMProvider,
    domain_context: list[str] | None = None,
) -> _SynthesisAttempt:
    """story-summary-v2 (全文直接入力方式) でのLLM呼び出し + 後処理。

    戻り値: `(text, issues, model_provider, model_name)`。`text`が`None`の
    場合は合成が成立しなかった(blocking issueが`issues`にある)ことを表す。
    """
    prompt = build_story_summary_prompt_v2(full_text_items)
    system_prompt = build_story_summary_system_prompt_v2(domain_context)
    try:
        completion = provider.generate(prompt, system=system_prompt, format_json=True)
    except LLMProviderError as exc:
        return (
            None,
            [
                GenerationIssue(
                    "llm-provider-error",
                    f"LLM呼び出しに失敗しました: {exc}",
                    blocking=True,
                )
            ],
            None,
            None,
        )

    text, parse_issues = _parse_story_summary_response(completion.text)
    if text is None:
        return None, parse_issues, completion.provider_name, completion.model_name

    text, citation_issues = _strip_evidence_id_citations_with_issue(text)
    issues = list(parse_issues)
    issues.extend(citation_issues)
    issues.extend(_check_forbidden_text(text))
    return text, issues, completion.provider_name, completion.model_name


def _synthesize_story_summary_from_episode_summaries(
    ordered_episode_drafts: list[EpisodeSummaryDraft],
    provider: SummaryLLMProvider,
    max_input_characters: int,
    domain_context: list[str] | None = None,
) -> _SynthesisAttempt:
    """story-summary-v1 (Episode Summary群の再要約方式) でのLLM呼び出し +
    後処理。story-summary-v2のcontextサイズガード超過時のフォールバック、
    および全文入力を組み立てられない場合 (`episodes`未指定等) に使う。

    戻り値: `(text, issues, model_provider, model_name)`。`text`が`None`の
    場合は合成が成立しなかった(blocking issueが`issues`にある)ことを表す。
    """
    inputs = [
        EpisodeSummaryInput(episode_number=draft.episode_number, text=draft.text)
        for draft in ordered_episode_drafts
    ]
    rendered_text = render_episode_summaries_text(inputs)
    if len(rendered_text) > max_input_characters:
        return (
            None,
            [
                GenerationIssue(
                    "input-too-long",
                    f"入力テキスト(Episode Summary群)が{len(rendered_text)}"
                    f"文字で、上限{max_input_characters}文字を超えています "
                    "(chunk分割は未実装、Story Summary合成をskipしました)",
                    blocking=True,
                )
            ],
            None,
            None,
        )

    prompt = build_story_summary_prompt(inputs)
    system_prompt = build_story_summary_system_prompt(domain_context)
    try:
        completion = provider.generate(prompt, system=system_prompt, format_json=True)
    except LLMProviderError as exc:
        return (
            None,
            [
                GenerationIssue(
                    "llm-provider-error",
                    f"LLM呼び出しに失敗しました: {exc}",
                    blocking=True,
                )
            ],
            None,
            None,
        )

    text, parse_issues = _parse_story_summary_response(completion.text)
    if text is None:
        return None, parse_issues, completion.provider_name, completion.model_name

    text, citation_issues = _strip_evidence_id_citations_with_issue(text)
    issues = list(parse_issues)
    issues.extend(citation_issues)
    issues.extend(_check_forbidden_text(text))
    return text, issues, completion.provider_name, completion.model_name


def synthesize_story_summary(
    episode_drafts: list[EpisodeSummaryDraft],
    *,
    provider: SummaryLLMProvider,
    max_input_characters: int = DEFAULT_MAX_INPUT_CHARACTERS,
    episodes_with_issues: list[str] | None = None,
    episodes: list[dict[str, Any]] | None = None,
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    refine: bool = False,
    domain_context: list[str] | None = None,
) -> StorySynthesisResult:
    """生成済みEpisode Summary群からStory Summaryを合成する (Plan §11、
    `summary-generation-quality-v2`で入力方式をv2 (全文直接入力) へ変更)。

    - `episode_drafts`が空の場合は合成不能としてblocking issueを立てて
      skipする (LLM呼び出しは行わない)
    - **story-summary-v2 (既定)**: `episodes` (元episode dict一覧、通常は
      `generate_story_summary_draft`が`document["episodes"]`をそのまま渡す)
      が与えられ、全episode分の元episode dictが解決できる場合、全episode
      本文をepisodeNumber順の時系列で直接入力しstory全体を要約する
      (`build_story_summary_prompt_v2`)。入力の概算トークン数
      (`estimate_token_count`) が`max_context_tokens`を超える場合は
      **story-summary-v1 (Episode Summary群の再要約) へフォールバックし、
      非blocking issue `story-synthesis-context-fallback`を記録する
      (失敗にはしない)**
    - `episodes`が与えられない、または対応する元episode dictが見つからない
      場合も同様にv1方式へフォールバックする (この場合はissueを追加しない。
      呼び出し側が意図的にv1相当のみを使うケースを含むため)
    - v1方式では、入力テキスト (episodeNumber順に整形したEpisode Summary
      text群) の合計文字数が`max_input_characters`を超える場合もblocking
      issueを立ててskipする (episode側と同じ安全弁パターン、chunk分割は
      未実装)
    - LLM呼び出し失敗・応答parse失敗・`text`キー欠落/空はいずれもblocking
      (v1/v2共通)
    - 禁止文字列scanは非blocking (`FORBIDDEN_TEXT_PATTERNS`再利用)。
      **verbatim引用検出は行わない** (v1: 入力が既にsafeなepisode summary
      のため。v2: story全体の粒度でのverbatim検出は対象外とする方針を
      踏襲、Plan §11)
    - `episodes_with_issues` (episode-level issueを持つepisodeIdのlist) が
      非空の場合、合成自体は行った上で非blocking issue
      `source-episode-has-issues`として記録する (Plan §11)
    - `evidence_refs`はLLM出力からではなく、`_union_evidence_refs`による
      機械的unionを設定する (v1/v2いずれの方式でも共通、合成成功時のみ、
      skip時は空リスト)
    - `refine=True` (既定OFF) の場合、合成成功後にさらに自己推敲パスを1周
      実行する (`_refine_story_text`)。推敲自体の失敗は元のtextを維持し
      非blocking issueを記録するのみとする
    - `domain_context` (既定None、`summary-domain-context-injection`) は
      v1/v2いずれのsystem promptにもそのまま注入される
      (`build_story_summary_system_prompt`/`_v2`)
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

    full_text_items = _build_full_text_items(ordered, episodes) if episodes else []
    context_fallback_issue: GenerationIssue | None = None

    if full_text_items:
        full_text = render_story_full_text(full_text_items)
        estimated_tokens = estimate_token_count(full_text)
        if estimated_tokens <= max_context_tokens:
            text, issues, model_provider, model_name = (
                _synthesize_story_summary_full_text(
                    full_text_items, provider, domain_context
                )
            )
            prompt_version = STORY_SUMMARY_PROMPT_VERSION
        else:
            context_fallback_issue = GenerationIssue(
                "story-synthesis-context-fallback",
                f"全episode本文の概算トークン数({estimated_tokens})が上限"
                f"({max_context_tokens})を超えたため、story-summary-v1方式"
                "(Episode Summary群の再要約) へフォールバックしました",
            )
            text, issues, model_provider, model_name = (
                _synthesize_story_summary_from_episode_summaries(
                    ordered, provider, max_input_characters, domain_context
                )
            )
            prompt_version = STORY_SUMMARY_PROMPT_VERSION_FALLBACK
    else:
        text, issues, model_provider, model_name = (
            _synthesize_story_summary_from_episode_summaries(
                ordered, provider, max_input_characters, domain_context
            )
        )
        prompt_version = STORY_SUMMARY_PROMPT_VERSION_FALLBACK

    if text is None:
        return StorySynthesisResult(
            story_text=None,
            issues=issues,
            model_provider=model_provider,
            model_name=model_name,
            prompt_version=prompt_version,
        )

    if context_fallback_issue is not None:
        issues.append(context_fallback_issue)

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

    if refine:
        text, refine_issues = _refine_story_text(
            text, provider=provider, domain_context=domain_context
        )
        issues.extend(refine_issues)

    return StorySynthesisResult(
        story_text=text,
        evidence_refs=_union_evidence_refs(ordered),
        issues=issues,
        model_provider=model_provider,
        model_name=model_name,
        prompt_version=prompt_version,
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
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    refine: bool = False,
    domain_context: list[str] | None = None,
) -> StorySummaryGenerationResult:
    """Normalized Story JSON 1 story分から、Episode Summary群のdraftと
    (既定で) 合成済みStory Summaryを含む`StorySummaryDraft`を組み立てる。

    `synthesize_story=False`の場合、Story Summary合成自体を行わない
    (`draft.story_text`は常に`None`、`story_synthesis`は`None`のまま)。
    既定は`True` (Plan §11「story合成は既定で有効」)。

    `max_context_tokens`はstory-summary-v2 (全文直接入力方式) の
    contextサイズガード (`summary-generation-quality-v2`、
    `synthesize_story_summary`参照)。`refine=True` (既定OFF) の場合、
    episode/story summaryいずれの生成にも自己推敲パスを1周適用する。

    `domain_context` (既定None、`summary-domain-context-injection`) は
    `agents/summarizer/domain_context.py`の`load_domain_context`が返す
    人間確認済みドメイン前提のlist。episode生成・story合成・(有効な場合)
    自己推敲パスの全system promptへそのまま渡す。Noneまたは空リストの
    場合は従来通りdomain context注入なしで動作する (後方互換)。実際に
    非空のdomain_contextが渡された場合、`_build_provenance`が
    `promptVersion`へ`DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX`を追記する。
    """
    story_id = document.get("storyId")
    episodes = document.get("episodes", []) or []

    episode_results = [
        generate_episode_summary(
            episode,
            provider=provider,
            max_input_characters=max_input_characters,
            verbatim_threshold=verbatim_threshold,
            refine=refine,
            domain_context=domain_context,
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
            episodes=episodes,
            max_context_tokens=max_context_tokens,
            refine=refine,
            domain_context=domain_context,
        )

    provenance = _build_provenance(
        episode_results,
        story_synthesis,
        refine=refine,
        domain_context_injected=bool(domain_context),
    )

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
    *,
    refine: bool = False,
    domain_context_injected: bool = False,
) -> SummaryProvenance:
    """成功した最初のepisode結果からmodel provenanceを引き継ぐ
    (episode側が全て失敗している場合は、成功したstory synthesisの値で
    補完する)。

    `prompt_version`は、story synthesisが実際にstory_textを生成できた
    場合のみ、episode用`PROMPT_VERSION`にstory synthesisで実際に使われた
    方式 (`story_synthesis.prompt_version`、v2成功時は
    `STORY_SUMMARY_PROMPT_VERSION`、v1フォールバック時は
    `STORY_SUMMARY_PROMPT_VERSION_FALLBACK`) をカンマ区切りで併記する
    (schema上`source.promptVersion`は単一文字列のため、
    `summary-generation-quality-v2`でどちらの方式が実際に使われたかを
    provenanceから判別できるようにした)。`domain_context_injected=True`の
    場合はさらに`DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX`
    (`domain-context-v1`) を追記する (`summary-domain-context-injection`。
    `PROMPT_VERSION`/`STORY_SUMMARY_PROMPT_VERSION`自体はdomain context
    ファイルの有無に関わらず同じ値になるため、実際に注入されたかどうかは
    この追記の有無でprovenanceから判別する)。`refine=True`の場合はさらに
    `REFINE_PROMPT_VERSION_SUFFIX` (`refine-v2`) を追記する。
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
        prompt_versions.append(
            story_synthesis.prompt_version or STORY_SUMMARY_PROMPT_VERSION
        )
    if domain_context_injected:
        prompt_versions.append(DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX)
    if refine:
        prompt_versions.append(REFINE_PROMPT_VERSION_SUFFIX)

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
