"""
DKB Summarizer - Prompt
Episode Summary生成promptの構築
(docs/architecture/06_AI/Story_Summary_Generation_Plan.md §6 / §9
 `summary-generation-prompt-implementation`)。

ユーザーが2026-07-13にsummarizer系のprompt実装を明示的に解禁したことを受けて
実装する（`AI_CONTEXT.md` §4。`agents/extractor/`は引き続き未解禁のまま）。

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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# LLMへの指示文言・出力formatを変更した場合はこの値も更新する
# (draft.source.promptVersionへ格納される、Plan §6.2)。
PROMPT_VERSION = "episode-summary-v1"

# 抽出対象のBlock type (Plan §6.1、Evidence Indexの`--policy public-default`
# と同じ対象type。stage_direction/unknownは対象外)。
INCLUDED_BLOCK_TYPES: frozenset[str] = frozenset(
    {"dialogue", "monologue", "narration", "choice"}
)

# 長文episodeのchunk分割は本PRでは実装しない (Plan §6.4)。この文字数を
# 超える入力は、agents/summarizer/generator.py側でissueを立てて生成を
# skipする安全弁として扱う (常識的な既定値、実装側で確定)。
DEFAULT_MAX_INPUT_CHARACTERS = 50_000

EPISODE_SUMMARY_SYSTEM_PROMPT = (
    "あなたはゲームシナリオの正規化済みテキストから、"
    "明示された事実のみに基づく簡潔なあらすじを作成するアシスタントです。"
    "考察・推測・伏線解釈・キャラクター関係の推測・fan theoryは一切書かず、"
    "入力に明記された内容のみを要約してください。"
    "出力は指示されたJSON形式のみとし、それ以外の文章は一切出力しないで"
    "ください。"
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
    speaker = block.get("speaker")
    if not isinstance(speaker, dict):
        return None
    name = speaker.get("speakerName")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return None


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
