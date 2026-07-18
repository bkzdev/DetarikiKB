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

品質改善v2/v3・自己推敲パス (`summary-generation-quality-v2`、RAID small
batch (`workspace/summary_drafts/raid_batch_001/`) の人間レビューで確認
された品質問題2点への対策、2026-07-18ユーザー承認済み):
- **episode-summary-v3**: episode要約promptへ、(a) 各文の主語(人物名)を
  明示し代名詞・曖昧な指示語を避ける指示、(b) 解決済みspeaker displayName
  から機械抽出した「登場人物」一覧の注入 (`extract_speaker_names`、未解決
  話者は含めない)、(c) 本文中にblockIdや括弧書きの参照を書かない指示、の
  3点を追加した (`PROMPT_VERSION = "episode-summary-v3"`)。
- **story-summary-v2**: Story Summary合成の入力を、Episode Summary群の
  再要約(v1)から全episode本文の直接入力(v2)へ変更した
  (`build_story_summary_prompt_v2`/`render_story_full_text`)。story-level
  evidenceRefsは引き続き機械的union方式のまま(LLMに選ばせない)。入力の
  概算トークン数(`estimate_token_count`、実tokenizerは使わない単純な
  文字数概算)が`DEFAULT_MAX_CONTEXT_TOKENS`を超える場合、
  `agents/summarizer/generator.py`側でv1方式(`STORY_SUMMARY_PROMPT_VERSION`
  = `story-summary-v2`ではなく`STORY_SUMMARY_PROMPT_VERSION_FALLBACK`
  = `story-summary-v1-fallback`)へフォールバックする(失敗にしない)。
- **自己推敲パス (`--refine`、既定OFF)**: 生成済みのepisode/story summary
  textに対し、同モデルで`build_refine_prompt`による推敲を1周実行する
  オプション機能。推敲呼び出し自体の失敗・parse失敗時は元のtextを維持し
  非blocking issueを記録するのみとする(`agents/summarizer/generator.py`の
  `_refine_episode_draft`/`_refine_story_text`)。使用時はprovenanceの
  `promptVersion`へ`REFINE_PROMPT_VERSION_SUFFIX` (`refine-v1`) を追記する。

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
# v3: 主語明確化指示・登場人物リスト注入・本文中evidence ID参照禁止指示の
# 3点を追加 (`summary-generation-quality-v2`、RAID small batchレビューで
# 確認された品質問題への対策)。
# v4: domain context注入に対応 (`summary-domain-context-injection`)。
# system promptの構築を`EPISODE_SUMMARY_SYSTEM_PROMPT`固定値から
# `build_episode_summary_system_prompt(domain_context)`関数経由に変更した。
# domain contextが実際に注入されたかどうかはprovenance側で別途
# `DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX`として判別できるようにしており
# (`agents/summarizer/generator.py`の`_build_provenance`)、この値自体は
# 「domain context注入に対応したprompt実装のversion」を表す
# (ファイル未設置/空でも動作するコード変更のみでバージョンを上げている)。
PROMPT_VERSION = "episode-summary-v4"

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
    "各文の主語(人物名)を明示し、代名詞(彼・彼女・それ等)や『何か』のような"
    "曖昧な指示語で人物・物事を指さないでください。userプロンプトに示された"
    "「登場人物」一覧を参考にしてください。"
    "あらすじ本文中に、blockIdや括弧書きの参照・出典表記を書かないで"
    "ください（blockIdの引用はevidenceRefsフィールドのみで行ってください）。"
    "出力は指示されたJSON形式のみとし、それ以外の文章は一切出力しないで"
    "ください。"
    "「話者不明」という表記は話者が特定できていないことを示すラベルであり、"
    "実在の人物名・キャラクター名ではありません。あらすじ本文中でこれを"
    "人物名として扱わないでください。"
)


# ----------------------------------------------------------------
# Domain context注入 (`summary-domain-context-injection`)
#
# `agents/summarizer/domain_context.py`の`load_domain_context`が読み込んだ
# `knowledge/dictionaries/summary_domain_context.yaml`由来の人間確認済み事実
# (list[str]) を、各system promptの末尾へ追記する。domain_contextが空/None
# の場合は元のsystem prompt文字列を一切変更しない (後方互換)。
# ----------------------------------------------------------------

DOMAIN_CONTEXT_BLOCK_HEADER = (
    "以下はこの作品のドメイン前提です。人間が事実として確認済みの情報として"
    "扱い、要約作成時に必ず踏まえてください。"
)


def build_domain_context_block(domain_context: list[str] | None) -> str:
    """`domain_context`をsystem prompt末尾へ追記するテキストブロックへ
    整形する。空/Noneの場合は空文字列を返す (呼び出し側の`build_*_system_
    prompt`系関数はこれをそのまま元のsystem prompt文字列へ連結すればよく、
    注入なし時は元の文字列を一切変更しない)。
    """
    if not domain_context:
        return ""
    lines = "\n".join(f"- {line}" for line in domain_context)
    return f"\n\n{DOMAIN_CONTEXT_BLOCK_HEADER}\n{lines}"


def build_episode_summary_system_prompt(
    domain_context: list[str] | None = None,
) -> str:
    """Episode Summary生成用のsystem promptを組み立てる。

    `EPISODE_SUMMARY_SYSTEM_PROMPT`固定値に、`domain_context`があれば
    `build_domain_context_block`で整形したブロックを追記する。
    """
    return EPISODE_SUMMARY_SYSTEM_PROMPT + build_domain_context_block(domain_context)


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


def extract_speaker_names(blocks: list[ExtractedBlock]) -> list[str]:
    """episode中の解決済み話者displayNameを、初出順・重複排除で抽出する
    (v3「登場人物」リスト注入、`summary-generation-quality-v2`)。

    未解決話者 (`UNRESOLVED_SPEAKER_LABEL`、`speaker_name`が`None`のBlockも
    含む) は含めない。`ExtractedBlock.speaker_name`は`_speaker_name`により
    既にunresolved placeholder名を`UNRESOLVED_SPEAKER_LABEL`へ置換済みの
    ため、ここでは単純な文字列比較で判定できる。
    """
    seen: set[str] = set()
    names: list[str] = []
    for block in blocks:
        name = block.speaker_name
        if not name or name == UNRESOLVED_SPEAKER_LABEL:
            continue
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


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
    - v3 (`summary-generation-quality-v2`): 解決済みspeaker displayNameの
      「登場人物」一覧を注入し (`extract_speaker_names`)、主語明確化・
      本文中evidence ID参照禁止の指示を追加する

    呼び出し側 (`agents/summarizer/generator.py`) が空リストで呼ぶことは
    想定しない (入力Blockが無いepisodeは生成自体をskipする設計)。
    """
    blocks_text = render_blocks_text(blocks)
    speaker_names = extract_speaker_names(blocks)
    speaker_line = (
        "、".join(speaker_names) if speaker_names else "(解決済みの登場人物なし)"
    )
    return (
        "以下は、あるepisodeの正規化済みシナリオテキストです。"
        "各行は `[blockId] 話者名: 本文` または `[blockId] 本文` の形式で、"
        "blockIdはそのセリフ・地の文・選択肢の一意な識別子です。\n"
        "\n"
        f"登場人物: {speaker_line}\n"
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
        "3. 各文の主語(人物名)を明示してください。代名詞(彼・彼女・それ等)や"
        "『何か』のような曖昧な指示語は避け、上記「登場人物」一覧の名前や"
        "本文中の具体的な名称を使ってください。\n"
        "4. あらすじの各文につき、根拠となるblockIdを最低1つ引用してください"
        "（例: 文末に blockId を対応付けられるように書く）。ただし、"
        "あらすじ本文中にblockIdや括弧書きの参照・出典表記を書かないで"
        "ください。blockIdの引用は`evidenceRefs`フィールドのみで行って"
        "ください。\n"
        "5. 出力は次のJSON形式のみとし、それ以外の説明文・前置き・"
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
# v2 (`summary-generation-quality-v2`): 合成方式を「Episode Summary群の
# 再要約」から「全episode本文の直接入力」へ変更した (`build_story_summary_
# prompt_v2`)。contextサイズガードでフォールバックした場合は
# `STORY_SUMMARY_PROMPT_VERSION_FALLBACK`をprovenanceへ記録する
# (`agents/summarizer/generator.py`側の責務、このモジュールは定数のみ提供)。
# v3 (`summary-domain-context-injection`): domain context注入に対応
# (PROMPT_VERSIONのv4と同じ理由、system promptの構築を`STORY_SUMMARY_
# SYSTEM_PROMPT_V2`固定値から`build_story_summary_system_prompt_v2`
# 関数経由に変更した)。
STORY_SUMMARY_PROMPT_VERSION = "story-summary-v3"

# story-summary-v2のcontextサイズガード発動時 (入力の概算トークン数が
# `DEFAULT_MAX_CONTEXT_TOKENS`を超えた場合)、または呼び出し側が全episode
# 本文を用意できなかった場合に、実際に使われるprompt方式 (v1、Episode
# Summary群の再要約) を表す値。`agents/summarizer/generator.py`の
# `StorySynthesisResult.prompt_version`へ格納される。
STORY_SUMMARY_PROMPT_VERSION_FALLBACK = "story-summary-v1-fallback"

STORY_SUMMARY_SYSTEM_PROMPT = (
    "あなたはゲームシナリオのepisodeごとのあらすじ (Episode Summary) の"
    "集まりから、story全体を通した簡潔なあらすじを作成するアシスタントです。"
    "考察・推測・伏線解釈・キャラクター関係の推測・fan theoryは一切書かず、"
    "入力に明記された内容のみを要約してください。"
    "出力は指示されたJSON形式のみとし、それ以外の文章は一切出力しないで"
    "ください。"
)

# story-summary-v2 (全文直接入力方式) 用のsystem prompt。入力がepisode
# summary群ではなく生のdialogue/monologue/narration/choice本文であるため、
# episode用system promptと同様に主語明確化・未解決話者placeholderの扱いを
# 明示する (`summary-generation-quality-v2`)。
STORY_SUMMARY_SYSTEM_PROMPT_V2 = (
    "あなたはゲームシナリオの正規化済みテキスト (story全体の全episode本文) "
    "から、明示された事実のみに基づくstory全体の簡潔なあらすじを作成する"
    "アシスタントです。"
    "考察・推測・伏線解釈・キャラクター関係の推測・fan theoryは一切書かず、"
    "入力に明記された内容のみを要約してください。"
    "各文の主語(人物名)を明示し、代名詞(彼・彼女・それ等)や『何か』のような"
    "曖昧な指示語で人物・物事を指さないでください。"
    "あらすじ本文中に、blockIdや括弧書きの参照・出典表記を書かないで"
    "ください。"
    "出力は指示されたJSON形式のみとし、それ以外の文章は一切出力しないで"
    "ください。"
    "「話者不明」という表記は話者が特定できていないことを示すラベルであり、"
    "実在の人物名・キャラクター名ではありません。あらすじ本文中でこれを"
    "人物名として扱わないでください。"
)


def build_story_summary_system_prompt(domain_context: list[str] | None = None) -> str:
    """Story Summary合成 (v1、Episode Summary群の再要約方式) 用の
    system promptを組み立てる (`summary-domain-context-injection`、
    `build_episode_summary_system_prompt`と同じ方針)。"""
    return STORY_SUMMARY_SYSTEM_PROMPT + build_domain_context_block(domain_context)


def build_story_summary_system_prompt_v2(
    domain_context: list[str] | None = None,
) -> str:
    """Story Summary合成 (v2、全文直接入力方式) 用のsystem promptを
    組み立てる (`summary-domain-context-injection`)。"""
    return STORY_SUMMARY_SYSTEM_PROMPT_V2 + build_domain_context_block(domain_context)


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


# ----------------------------------------------------------------
# Story Summary合成 v2: 全文直接入力方式 (`summary-generation-quality-v2`)
#
# Episode Summary群の再要約 (v1、上記) ではなく、全episodeの本文
# (dialogue/monologue/narration/choice Blockのみ、blockId付き) を
# episodeNumber順の時系列でそのまま入力しstory全体を要約させる。
# story-level evidenceRefsは引き続きLLMに求めない (機械的union方式を維持、
# `agents/summarizer/generator.py`の`_union_evidence_refs`)。
# ----------------------------------------------------------------


@dataclass(frozen=True)
class EpisodeBlocksInput:
    """story-summary-v2入力用の1 episode分のBlock群表現。

    `agents/summarizer/generator.py`が、生成済み`EpisodeSummaryDraft`に
    対応する元episode dictから`extract_episode_blocks`で再抽出した
    `ExtractedBlock`一覧を保持する (Episode Summary textではなく、episode
    本文そのものを使うのがv1との違い)。
    """

    episode_number: int | None
    blocks: list[ExtractedBlock]


def render_story_full_text(items: list[EpisodeBlocksInput]) -> str:
    """story-summary-v2入力用に、各episodeの本文をepisodeNumber順の時系列で
    整形した1つのテキストへ変換する。

    Episode境界を`=== Episode {episodeNumber} ===`見出しで区切る。呼び出し
    側 (`agents/summarizer/generator.py`) がepisodeNumber順に並べたitemsを
    渡すこと (並び替え自体はこの関数の責務ではない)。
    """
    parts: list[str] = []
    for item in items:
        number_label = item.episode_number if item.episode_number is not None else "?"
        parts.append(f"=== Episode {number_label} ===")
        parts.append(render_blocks_text(item.blocks))
    return "\n".join(parts)


def build_story_summary_prompt_v2(items: list[EpisodeBlocksInput]) -> str:
    """Story Summary合成 (v2、全文直接入力方式) 用のuser prompt本文を
    組み立てる (`summary-generation-quality-v2`)。

    - 全episodeの本文をepisodeNumber順の時系列でそのまま埋め込む (v1の
      「Episode Summary群の再要約」との違い)
    - story-level textにblockId引用は求めない (evidenceRefsは
      `agents/summarizer/generator.py`側で機械的union方式のまま決める)
    - 出力は`{"text": "..."}`形式のJSONのみとする (v1と同じ出力形式)
    - 主語明確化・本文中evidence ID参照禁止の指示を含む (episode-summary-v3
      と同じ品質改善方針)

    呼び出し側が空リストで呼ぶことは想定しない (全文入力が組み立てられない
    場合はv1方式へフォールバックする設計、`generator.py`の責務)。
    """
    full_text = render_story_full_text(items)
    return (
        "以下は、あるstoryを構成する全episodeの正規化済み本文です。"
        "各行は `[blockId] 話者名: 本文` または `[blockId] 本文` の形式で、"
        "`=== Episode 番号 ===` の見出しでepisode境界を区切り、"
        "episodeNumber順の時系列で並んでいます。\n"
        "\n"
        "--- story本文 (全episode、時系列順) ---\n"
        f"{full_text}\n"
        "--- story本文ここまで ---\n"
        "\n"
        "この内容から、story全体を通した明示された事実のみに基づく簡潔な"
        "あらすじを日本語で作成してください。以下のルールを厳守してください。\n"
        "\n"
        "1. 本文に明記された内容のみを使い、story全体の流れが分かるように"
        "まとめてください。考察・推測・伏線解釈・キャラクター関係の推測・"
        "fan theoryは一切書かないでください。\n"
        "2. 元の台詞・地の文を長文でそのまま引用しないでください。\n"
        "3. 各文の主語(人物名)を明示してください。代名詞(彼・彼女・それ等)や"
        "『何か』のような曖昧な指示語は避けてください。\n"
        "4. あらすじ本文中に、blockIdや括弧書きの参照・出典表記を書かないで"
        "ください。\n"
        "5. 出力は次のJSON形式のみとし、それ以外の説明文・前置き・"
        "Markdown装飾は一切出力しないでください。\n"
        "\n"
        '{"text": "story全体のあらすじ本文"}\n'
    )


# story-summary-v2のcontextサイズガード。実tokenizerは導入しない (新規
# ランタイム依存を追加しない方針、`agents/summarizer/provider.py`参照)。
# 日本語主体のテキストを想定し、保守的に1token≒2文字という経験則で概算する
# (実際のtokenizerより少なめの文字数/tokenで見積もることで、context超過を
# 早期に検出する安全側の概算)。
CHARACTERS_PER_TOKEN_ESTIMATE = 2

# story-summary-v2入力の概算トークン数上限の既定値。ローカルLLM (Ollama) の
# 保守的なcontext window目安 (8192 tokens前後) を踏まえた値。超過時は
# `agents/summarizer/generator.py`側でv1方式(Episode Summary群の再要約)へ
# フォールバックする (CLI `--story-synthesis-max-context-tokens`で変更可)。
DEFAULT_MAX_CONTEXT_TOKENS = 8_000


def estimate_token_count(text: str) -> int:
    """テキストの概算トークン数を返す。

    `CHARACTERS_PER_TOKEN_ESTIMATE`文字ごとに1tokenという単純な概算のみを
    行う (実tokenizerは使わない)。空文字列は0を返す。
    """
    if not text:
        return 0
    return -(-len(text) // CHARACTERS_PER_TOKEN_ESTIMATE)


# ----------------------------------------------------------------
# 自己推敲パス (`--refine`、既定OFF、`summary-generation-quality-v2`)
#
# 生成済みのepisode/story summary textに対し、同モデルで1周だけ推敲させる
# オプション機能。入力に無い事実の追加・大幅な長さの変更を禁止する。
# ----------------------------------------------------------------

# 推敲使用時にprovenanceの`promptVersion`へ追記するsuffix
# (`agents/summarizer/generator.py`の`_build_provenance`が使う)。
# v2 (`summary-domain-context-injection`): domain context注入に対応
# (PROMPT_VERSIONのv4と同じ理由)。
REFINE_PROMPT_VERSION_SUFFIX = "refine-v2"

REFINE_SYSTEM_PROMPT = (
    "あなたは日本語のあらすじ文章を推敲するアシスタントです。"
    "主語が曖昧な文・論理の飛躍・不自然な係り受けを修正してください。"
    "入力に無い事実を追加しないでください。長さは元の本文と同程度を"
    "保ってください。"
    "出力は指示されたJSON形式のみとし、それ以外の文章は一切出力しないで"
    "ください。"
)


def build_refine_system_prompt(domain_context: list[str] | None = None) -> str:
    """自己推敲パス用のsystem promptを組み立てる
    (`summary-domain-context-injection`、`build_episode_summary_system_
    prompt`と同じ方針)。"""
    return REFINE_SYSTEM_PROMPT + build_domain_context_block(domain_context)


def build_refine_prompt(text: str) -> str:
    """自己推敲パス用のuser prompt本文を組み立てる。

    生成済みのepisode/story summary textを入力とし、同モデルで1周だけ
    推敲させる。出力は`{"text": "..."}`形式のJSONのみとする (episode
    summary/story summaryいずれの推敲呼び出しにも共用できる形式)。
    """
    return (
        "以下は、既に生成されたゲームシナリオのあらすじ本文です。\n"
        "\n"
        "--- 推敲対象の本文 ---\n"
        f"{text}\n"
        "--- 推敲対象の本文ここまで ---\n"
        "\n"
        "この本文について、以下のルールを厳守して推敲してください。\n"
        "\n"
        "1. 主語が曖昧な文・論理の飛躍・不自然な係り受けを修正してください。\n"
        "2. 入力に無い事実を追加しないでください。\n"
        "3. 長さは元の本文と同程度を保ってください。\n"
        "4. 出力は次のJSON形式のみとし、それ以外の説明文・前置き・"
        "Markdown装飾は一切出力しないでください。\n"
        "\n"
        '{"text": "推敲後の本文"}\n'
    )
