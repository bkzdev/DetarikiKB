"""
DKB Summarizer - Prompt
Episode Summary生成prompt、およびStory Summary合成promptの構築
(docs/architecture/06_AI/Story_Summary_Generation_Plan.md §6 / §9
 `summary-generation-prompt-implementation` / `summary-generation-story-
 synthesis`)。

ユーザーが2026-07-13にsummarizer系のprompt実装を明示的に解禁したことを受けて
実装する（`AI_CONTEXT.md` §4。`agents/extractor/`は引き続き未解禁のまま）。

未解決話者のprompt表記 (Stage 1 small batchの人間レビューで実測された対策):
- `agents/parser/resolver.py`の`Speaker.unknown`が付与する
  `不明人物(ID:NNN)`形式のplaceholder speakerNameは、内部IDの断片を
  含んだままLLMへ渡すとLLMが人物名として要約本文に書いてしまう問題が
  あった。`schemas/story.schema.json`の`Speaker.isResolved`
  (`agents/parser/resolver.py`の`is_resolved`) を正とし、
  未解決話者のBlockは話者部分を固定表記「話者不明」に置き換えてprompt
  へ渡す (`_speaker_name`)。`isResolved`が取得できない場合のみ、
  `不明人物`プレフィックスの文字列判定にfallbackする。
- system promptに「話者不明」はplaceholderであり人物名として要約に
  書かないことを明示する一文を追加した (`EPISODE_SUMMARY_SYSTEM_PROMPT`)。

入力構造（Plan §6.1）:
- Episode単位のNormalized Story JSON (`schemas/story.schema.json`) から、
  `dialogue`/`monologue`/`narration`/`choice`のBlockのみを再帰的に抽出する
  (`stage_direction`/`unknown`は対象外。choice optionの中にnestされた
  dialogue/monologue/narration/choice Blockも同様に対象とする)
- 各Blockに内部blockIdを付与したテキスト表現
  (`[{blockId}] {話者名}: {text}` 形式相当) をpromptへ埋め込む
- raw演出コマンド・変数・rawテキストはLLMに渡さない
  (`AI_CONTEXT.md` §3.1どおり、既に正規化済みのテキストのみを渡す)

出力構造（Plan §6.2）:
- `{"text": "...", "evidenceRefs": ["BLOCKID", ...]}` 形式のJSONのみを
  返すよう指示する（`format_json=True`でのLLM呼び出しと組み合わせる想定、
  応答のparse・検証自体は`agents/summarizer/generator.py`の責務）

長文episodeの安全弁（Plan §6.4）:
- chunk分割2段階要約は本PRでは実装しない。入力テキストが
  `DEFAULT_MAX_INPUT_CHARACTERS`を超える場合は、
  `agents/summarizer/generator.py`側でissueを立てて生成をskipする
  （このモジュール自体は文字数チェックを行わない、上限値の定義のみ）

Story Summary合成（`summary-generation-story-synthesis`、Plan §11で確定）:
- 合成方式はLLM再要約とする。生成済みEpisode Summary群のtext
  (episodeNumber順) を入力とし、story全体の簡潔なあらすじを再度LLMに
  生成させる（`format_json=True`、出力は`{"text": "..."}`のみ。story-level
  textにblockId引用は求めない）
- story-level evidenceRefsはLLM出力からではなく、
  `agents/summarizer/generator.py`側でepisode-level evidenceRefsの
  重複排除unionとして機械的に決める (監査可能性を保ちつつLLM引用の
  不確実性を避ける、Plan §11)
- system promptはepisode用と同じ制約 (明示された事実のみ・考察禁止・
  JSON出力のみ) を、入力がepisode summary群であることに合わせて言い換えた
  `STORY_SUMMARY_SYSTEM_PROMPT`を別途定義する
- 長文episodeと同じ安全弁として、入力Episode Summary群の合計文字数が
  `DEFAULT_MAX_INPUT_CHARACTERS`を超える場合は
  `agents/summarizer/generator.py`側で合成をskipする (このモジュールは
  文字数チェックを行わない)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# LLMへの指示文言・出力formatを変更した場合はこの値も更新する
# (draft.source.promptVersionへ格納される、Plan §6.2)。
# v2: 未解決話者placeholderの「話者不明」統一表記化・system prompt指示追加
# (Stage 1 small batchレビューで実測された問題への対策)。
PROMPT_VERSION = "episode-summary-v2"

# 抽出対象のBlock type (Plan §6.1、Evidence Indexの`--policy public-default`
# と同じ対象type。stage_direction/unknownは対象外)。
INCLUDED_BLOCK_TYPES: frozenset[str] = frozenset(
    {"dialogue", "monologue", "narration", "choice"}
)

# 長文episodeのchunk分割は本PRでは実装しない (Plan §6.4)。この文字数を
# 超える入力は、agents/summarizer/generator.py側でissueを立てて生成を
# skipする安全弁として扱う (常識的な既定値、実装側で確定)。
DEFAULT_MAX_INPUT_CHARACTERS = 50_000

# 未解決話者 (`schemas/story.schema.json` Speaker.isResolved=false) のBlockを
# promptへ渡す際に話者部分へ用いる固定表記。`不明人物(ID:NNN)`のような
# 内部ID断片をLLMへ見せない (Stage 1 small batchレビューで実測された対策)。
UNRESOLVED_SPEAKER_LABEL = "話者不明"

# isResolvedフラグが取得できない場合のfallback判定に使う、
# `agents/parser/resolver.py` `Speaker.unknown`が付与するplaceholder名の
# プレフィックス。フラグ判定が確実な場合はこちらは使わない。
UNRESOLVED_SPEAKER_NAME_PREFIX = "不明人物"

EPISODE_SUMMARY_SYSTEM_PROMPT = (
    "あなたはゲームシナリオの正規化済みテキストから、"
    "明示された事実のみに基づく簡潔なあらすじを作成するアシスタントです。"
    "考察・推測・伏線解釈・キャラクター関係の推測・fan theoryは一切書かず、"
    "入力に明記された内容のみを要約してください。"
    "出力は指示されたJSON形式のみとし、それ以外の文章は一切出力しないで"
    "ください。"
    "「話者不明」という表記は話者が特定できていないことを示すラベルであり、"
    "実在の人物名・キャラクター名ではありません。あらすじ本文中でこれを"
    "人物名として扱わないでください。"
)


@dataclass(frozen=True)
class ExtractedBlock:
    """prompt入力用に抽出した1 Block分のテキスト表現。"""

    block_id: str
    block_type: str
    speaker_name: str | None
    text: str


def extract_episode_blocks(episode: dict[str, Any]) -> list[ExtractedBlock]:
    """Episode dict (Normalized Story JSON `episodes[]`要素) から、
    `dialogue`/`monologue`/`narration`/`choice`のBlockのみを再帰的に
    抽出する (Plan §6.1)。

    - `stage_direction`/`unknown`は対象外
    - choice option内にnestされたBlockも、対象typeであれば抽出する
      (`agents/parser/normalizer.py`の`choice.options[].blocks`構造)
    - `id`が無いBlock、本文が空/whitespaceのみのBlockはskipする
    """
    extracted: list[ExtractedBlock] = []
    for scene in episode.get("scenes", []) or []:
        for block in scene.get("blocks", []) or []:
            extracted.extend(_extract_block_recursive(block))
    return extracted


def _extract_block_recursive(block: dict[str, Any]) -> list[ExtractedBlock]:
    results: list[ExtractedBlock] = []
    block_type = block.get("type")
    block_id = block.get("id")

    if block_type in INCLUDED_BLOCK_TYPES and block_id:
        text = _block_text(block, block_type)
        if text is not None:
            results.append(
                ExtractedBlock(
                    block_id=block_id,
                    block_type=block_type,
                    speaker_name=_speaker_name(block),
                    text=text,
                )
            )

    if block_type == "choice":
        for option in block.get("options", []) or []:
            for inner_block in option.get("blocks", []) or []:
                results.extend(_extract_block_recursive(inner_block))

    return results


def _block_text(block: dict[str, Any], block_type: str) -> str | None:
    """block typeに応じた本文フィールドを読み取る。

    dialogue/monologue/narrationは`text`、choiceは`choiceText`
    (`agents/parser/normalizer.py`の`_normalize_choice_block`参照、
    choiceブロック自体は`text`フィールドを持たない)。
    """
    raw_value = block.get("choiceText") if block_type == "choice" else block.get("text")
    if isinstance(raw_value, str) and raw_value.strip():
        return raw_value.strip()
    return None


def _speaker_name(block: dict[str, Any]) -> str | None:
    """Blockのspeaker情報から、prompt埋め込み用の話者名を返す。

    未解決話者 (`Speaker.isResolved is False`) の場合は、
    `不明人物(ID:NNN)`のような内部ID断片を含むplaceholder名をそのまま
    返さず、固定表記`UNRESOLVED_SPEAKER_LABEL` ("話者不明") に置き換える。
    """
    speaker = block.get("speaker")
    if not isinstance(speaker, dict):
        return None
    name = speaker.get("speakerName")
    if not isinstance(name, str) or not name.strip():
        return None
    name = name.strip()
    if _is_unresolved_speaker(speaker, name):
        return UNRESOLVED_SPEAKER_LABEL
    return name


def _is_unresolved_speaker(speaker: dict[str, Any], name: str) -> bool:
    """話者が未解決 (placeholder) かどうかを判定する。

    `isResolved`が真偽値として取得できる場合はそちらを正とする
    (`schemas/story.schema.json` Speaker.isResolved / 「背景・確定事項」の
    指示通り、文字列パターンより優先)。取得できない場合のみ、
    `不明人物`プレフィックスの文字列判定にfallbackする。
    """
    is_resolved = speaker.get("isResolved")
    if isinstance(is_resolved, bool):
        return not is_resolved
    return name.startswith(UNRESOLVED_SPEAKER_NAME_PREFIX)


def format_block_line(block: ExtractedBlock) -> str:
    """`[{blockId}] {話者名}: {text}` 形式相当のテキスト表現を返す。

    話者名が無いBlock (narration/choice等) は話者部分を省略する。
    """
    if block.speaker_name:
        return f"[{block.block_id}] {block.speaker_name}: {block.text}"
    return f"[{block.block_id}] {block.text}"


def render_blocks_text(blocks: list[ExtractedBlock]) -> str:
    """抽出済みBlock一覧を、prompt埋め込み用の複数行テキストへ変換する。"""
    return "\n".join(format_block_line(block) for block in blocks)


def build_episode_summary_prompt(blocks: list[ExtractedBlock]) -> str:
    """Episode Summary生成用のuser prompt本文を組み立てる (Plan §6.2/§6.3)。

    - 各文につき最低1つのblockId引用を求める (引用強制、Plan §6.3)
    - 元セリフの長文引用禁止・簡潔なあらすじのみを要求する
      (`Story_Summary_Design.md` §7.1/§7.2)
    - 出力は`{"text": "...", "evidenceRefs": ["BLOCKID", ...]}`形式の
      JSONのみとする (Plan §6.2)

    呼び出し側 (`agents/summarizer/generator.py`) が空リストで呼ぶことは
    想定しない (入力Blockが無いepisodeは生成自体をskipする設計)。
    """
    blocks_text = render_blocks_text(blocks)
    return (
        "以下は、あるepisodeの正規化済みシナリオテキストです。"
        "各行は `[blockId] 話者名: 本文` または `[blockId] 本文` の形式で、"
        "blockIdはそのセリフ・地の文・選択肢の一意な識別子です。\n"
        "\n"
        "--- episode本文 ---\n"
        f"{blocks_text}\n"
        "--- episode本文ここまで ---\n"
        "\n"
        "この内容から、明示された事実のみに基づく簡潔なあらすじを日本語で"
        "作成してください。以下のルールを厳守してください。\n"
        "\n"
        "1. このepisodeで実際に起きたこと・主要登場人物・主要イベントのみを"
        "書いてください。考察・推測・伏線解釈・キャラクター関係の推測・"
        "fan theoryは一切書かないでください。\n"
        "2. 元のセリフ・地の文を長文でそのまま引用しないでください。短い"
        "一文引用程度に留めてください。\n"
        "3. あらすじの各文につき、根拠となるblockIdを最低1つ引用してください"
        "（例: 文末に blockId を対応付けられるように書く）。\n"
        "4. 出力は次のJSON形式のみとし、それ以外の説明文・前置き・"
        "Markdown装飾は一切出力しないでください。\n"
        "\n"
        '{"text": "あらすじ本文", "evidenceRefs": ["引用したblockIdの配列"]}\n'
        "\n"
        "evidenceRefsには、textの根拠として引用した実在のblockId（上記"
        "episode本文中に現れるblockIdのみ）を重複なく列挙してください。"
    )


# ----------------------------------------------------------------
# Story Summary合成 (Episode Summary群 -> Story Summary、Plan §11)
# ----------------------------------------------------------------

# story合成promptの指示文言・出力formatを変更した場合はこの値も更新する
# (draft.source.promptVersionへ、episode用PROMPT_VERSIONと併せて格納される)。
STORY_SUMMARY_PROMPT_VERSION = "story-summary-v1"

STORY_SUMMARY_SYSTEM_PROMPT = (
    "あなたはゲームシナリオのepisodeごとのあらすじ (Episode Summary) の"
    "集まりから、story全体を通した簡潔なあらすじを作成するアシスタントです。"
    "考察・推測・伏線解釈・キャラクター関係の推測・fan theoryは一切書かず、"
    "入力に明記された内容のみを要約してください。"
    "出力は指示されたJSON形式のみとし、それ以外の文章は一切出力しないで"
    "ください。"
)


@dataclass(frozen=True)
class EpisodeSummaryInput:
    """story合成prompt入力用の1 episode分のEpisode Summaryテキスト表現。

    `agents/summarizer/models.py`の`EpisodeSummaryDraft`から
    `episode_number`/`text`のみを取り出した軽量表現 (このモジュールを
    modelsに依存させないための分離)。
    """

    episode_number: int | None
    text: str


def format_episode_summary_line(item: EpisodeSummaryInput) -> str:
    """`[Episode {episodeNumber}] {text}` 形式相当のテキスト表現を返す。

    episodeNumberが無い場合は`?`を用いる (実運用では常に埋まっている想定だが、
    欠落時も入力自体は落とさない)。
    """
    number_label = item.episode_number if item.episode_number is not None else "?"
    return f"[Episode {number_label}] {item.text}"


def render_episode_summaries_text(items: list[EpisodeSummaryInput]) -> str:
    """抽出済みEpisode Summary入力一覧を、prompt埋め込み用の複数行テキストへ
    変換する。呼び出し側 (`agents/summarizer/generator.py`) が渡す順序で
    そのまま整形する (episodeNumber順への並び替えは呼び出し側の責務)。"""
    return "\n".join(format_episode_summary_line(item) for item in items)


def build_story_summary_prompt(items: list[EpisodeSummaryInput]) -> str:
    """Story Summary合成用のuser prompt本文を組み立てる (Plan §11)。

    - 各episodeのEpisode Summary textを`items`が渡す順序 (episodeNumber順を
      想定、呼び出し側が保証する) のまま埋め込む
    - story-level textにblockId引用は求めない (evidenceRefsは
      `agents/summarizer/generator.py`側で機械的に決めるため)
    - 出力は`{"text": "..."}`形式のJSONのみとする

    呼び出し側が空リストで呼ぶことは想定しない (Episode Summaryが1件も
    無い場合は合成自体をskipする設計、`generator.py`の責務)。
    """
    summaries_text = render_episode_summaries_text(items)
    return (
        "以下は、あるstoryを構成する各episodeのあらすじ (Episode Summary) "
        "です。各行は `[Episode 番号] あらすじ本文` の形式で、episodeNumber順に"
        "並んでいます。\n"
        "\n"
        "--- episode summary一覧 (episodeNumber順) ---\n"
        f"{summaries_text}\n"
        "--- episode summary一覧ここまで ---\n"
        "\n"
        "この内容から、story全体を通した明示された事実のみに基づく簡潔な"
        "あらすじを日本語で作成してください。以下のルールを厳守してください。\n"
        "\n"
        "1. 各episodeのあらすじに明記された内容のみを使い、story全体の"
        "流れが分かるようにまとめてください。考察・推測・伏線解釈・"
        "キャラクター関係の推測・fan theoryは一切書かないでください。\n"
        "2. 個々のepisodeのあらすじ本文を長文でそのまま引用しないで"
        "ください。\n"
        "3. 出力は次のJSON形式のみとし、それ以外の説明文・前置き・"
        "Markdown装飾は一切出力しないでください。\n"
        "\n"
        '{"text": "story全体のあらすじ本文"}\n'
    )
