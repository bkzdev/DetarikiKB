"""
DKB Story Parser - Parser Core
Token 列から Normalized Story の中間構造を作る。

Phase 6 (Parser_Implementation_Plan.md)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .resolver import (
    CharacterDictionary,
    Speaker,
    SpeakerAssignmentRecord,
    SpeakerResolver,
)
from .speaker_labels import (
    SOURCE_CH_TALK_NAME,
    SOURCE_NAME_COMMAND,
    SpeakerLabelAnalysis,
    analyze_speaker_label,
    attach_inferred_speakers,
)
from .tokenizer import ScriptToken, Tokenizer, TokenType

# ----------------------------------------------------------------
# Stage Direction 分類マップ
# ----------------------------------------------------------------

DIRECTION_TYPE_MAP: dict[str, str] = {
    "bg": "background",
    "bgm": "sound",
    "se": "sound",
    "@FaceLow": "character_display",
    "@Visible": "character_display",
    "@VisibleOff": "character_display",
    "@Visibleoff": "character_display",
    "@ChCamera": "camera",
    "@ChCameraOff": "camera",
    "@ChCameraoff": "camera",
    "@MotionReset": "motion",
    "@TalkPos": "ui",
    "@TalkPosLLL": "ui",
    "@TalkPosRRR": "ui",
    "@ChCharaEye": "character_display",
    "@ChCharaEyeOff": "character_display",
    "@ChCharaEyeoff": "character_display",
    "@Smartphone": "ui",
    "@SmartphoneOff": "ui",
    "@Smartphoneoff": "ui",
    "@VideoLoad": "video",
    "@VideoPlay": "video",
    "segmentCorrection": "system",
    "visibleAccessory": "character_display",
    # 実データdry-run trialで見つかった演出コマンド群
    # (docs/runbooks/Real_Data_Dry_Run_Result_Template.md §3.2)。
    # 意味を完全解析せず、既存カテゴリ (camera/motion/sound/ui/
    # character_display/system) へ機械的に振り分ける。既存カテゴリに
    # 収まらない画面全体の演出 (フェード等) のみ "screen" を新設する。
    "ch": "camera",
    "pos": "camera",
    "euler": "camera",
    "fov": "camera",
    "camera": "camera",
    "nf": "camera",
    "light": "camera",
    "@TalkCamera3": "camera",
    "@TalkCamera4": "camera",
    "mo": "motion",
    "@MotionWait": "motion",
    "sound": "sound",
    "vo": "sound",
    "ui": "ui",
    "wType": "ui",
    "wset": "ui",
    "click": "ui",
    "hide": "character_display",
    "visible": "character_display",
    "scale": "character_display",
    "color": "character_display",
    "active": "character_display",
    "parent": "character_display",
    "@ChColor2": "character_display",
    "@ChColor2off": "character_display",
    "rdraw": "screen",
    "screen": "screen",
    "@FadeOutWhite": "screen",
    "@TalkFadeIn": "screen",
    "@DoubleScreen": "screen",
    "uniq": "system",
    "set": "system",
    "prefab": "system",
    "remove": "system",
    "loading": "system",
    "wait": "system",
    "@IsLoading": "system",
    "image": "system",
    "distance": "camera",
    "shake": "camera",
    # branch/choice included dry-run (feature/branch-choice-dry-run) で
    # 見つかった演出コマンド群。意味を完全解析せず既存カテゴリへ機械的に
    # 振り分ける (config/script_commands.yaml の stage_direction と対で追加)。
    "costume": "character_display",
    "fa": "character_display",
    "@TalkPosR": "ui",
    "@TalkPosL": "ui",
    "@ChEyeOff": "character_display",
    "@VisibleS": "character_display",
    "@FadeOutBlack": "screen",
}

# 表記ゆれ → 正規化
CASE_VARIANTS_MAP: dict[str, str] = {
    "@Visibleoff": "@VisibleOff",
    "@ChCameraoff": "@ChCameraOff",
    "@ChCharaEyeoff": "@ChCharaEyeOff",
    "@Smartphoneoff": "@SmartphoneOff",
}

# 既知の stage_direction コマンドセット
STAGE_DIRECTION_COMMANDS: frozenset[str] = frozenset(
    DIRECTION_TYPE_MAP.keys()
) | frozenset(CASE_VARIANTS_MAP.keys())

# 既知の speaker_assignment コマンドセット
SPEAKER_ASSIGNMENT_COMMANDS: frozenset[str] = frozenset(
    {
        "@ScenarioCos",
        "@ScenarioCosLoad",
    }
)

# $numX パターン
NUM_VAR_PATTERN = re.compile(r"^\$num(\d+)$")
# $valueX パターン
VALUE_VAR_PATTERN = re.compile(r"^\$value(\d+)$")

# @ScenarioCos
SCENARIO_COS_PATTERN = re.compile(r"^@ScenarioCos\s+(\d+)\s+(\d+)")
# @ScenarioCosLoad
SCENARIO_COS_LOAD_PATTERN = re.compile(r"^@ScenarioCosLoad\s+(\d+)\s+(\$[\w\d]+)")


# ----------------------------------------------------------------
# 中間ブロック構造
# ----------------------------------------------------------------


@dataclass
class BlockData:
    """Parser が生成する中間ブロック (Normalizer が最終 JSON へ変換する)"""

    block_type: str
    """dialogue / monologue / narration / choice / stage_direction / unknown"""

    text: str | None = None
    """正規化済み本文"""

    raw_text: str | None = None
    """元テキスト (複数行をそのまま結合)"""

    speaker: Speaker | None = None
    """話者情報 (dialogue / monologue のみ)"""

    has_voice: bool | None = None
    """音声有無 (dialogue / monologue のみ)"""

    # narration
    narration_type: str | None = None

    # choice
    choice_text: str | None = None
    options: list[dict] = field(default_factory=list)

    # stage_direction
    direction_type: str | None = None
    raw_command: str | None = None
    normalized_command: str | None = None
    command_args: list[str] = field(default_factory=list)

    # source / evidence
    source_file: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    raw_line: str | None = None
    parser_rule: str | None = None
    confidence: float | None = None

    # notes
    notes: list[str] = field(default_factory=list)


@dataclass
class SceneData:
    """Parser が生成する中間シーン"""

    scene_number: int
    location_name: str | None = None
    blocks: list[BlockData] = field(default_factory=list)


@dataclass
class EpisodeData:
    """Parser が生成する中間エピソード"""

    episode_number: int
    speaker_assignments: list[SpeakerAssignmentRecord] = field(default_factory=list)
    unresolved_character_ids: set[str] = field(default_factory=set)
    scenes: list[SceneData] = field(default_factory=list)


@dataclass
class ParseResult:
    """Parser 全体の出力"""

    episodes: list[EpisodeData] = field(default_factory=list)
    control_chars_removed: int = 0
    unknown_commands: dict[str, int] = field(default_factory=dict)
    new_speech_commands: list[str] = field(default_factory=list)


# ----------------------------------------------------------------
# Parser
# ----------------------------------------------------------------


class StoryParser:
    """
    Tokenizer の出力 (ScriptToken リスト) から ParseResult を生成する。

    1エピソードを1ファイルとして扱う。
    """

    def __init__(
        self,
        char_dict: CharacterDictionary | None = None,
        preserve_stage_directions: bool = True,
        preserve_unknown: bool = True,
        source_file: str | None = None,
    ) -> None:
        self.preserve_stage_directions = preserve_stage_directions
        self.preserve_unknown = preserve_unknown
        self.source_file = source_file
        self._char_dict = char_dict or CharacterDictionary()

    def parse_file(self, file_path: str | Path) -> ParseResult:
        """ファイルを読み込んで ParseResult を返す"""
        path = Path(file_path)
        tokenizer = Tokenizer(strip_control_chars=True)
        tokens = tokenizer.tokenize_file(path)
        control_chars_removed = sum(t.control_chars_removed for t in tokens)
        source_file = self.source_file or path.stem
        return self._parse_tokens(tokens, control_chars_removed, source_file)

    def parse_text(self, text: str, source_file: str = "inline") -> ParseResult:
        """テキストを解析して ParseResult を返す"""
        tokenizer = Tokenizer(strip_control_chars=True)
        tokens = tokenizer.tokenize_text(text)
        control_chars_removed = sum(t.control_chars_removed for t in tokens)
        return self._parse_tokens(tokens, control_chars_removed, source_file)

    def parse_tokens(
        self, tokens: list[ScriptToken], source_file: str = "inline"
    ) -> ParseResult:
        """トークンリストを受け取って ParseResult を返す"""
        control_chars_removed = sum(t.control_chars_removed for t in tokens)
        return self._parse_tokens(tokens, control_chars_removed, source_file)

    # ----------------------------------------------------------------
    # Internal parsing
    # ----------------------------------------------------------------

    def _parse_tokens(  # noqa: C901 -- parse state dataclass refactorまでの暫定抑制。TASKS.md Known Issues参照
        self,
        tokens: list[ScriptToken],
        control_chars_removed: int,
        source_file: str,
    ) -> ParseResult:
        result = ParseResult(control_chars_removed=control_chars_removed)

        resolver = SpeakerResolver(self._char_dict)

        # エピソード・シーンは Phase 1 では 1 エピソード / 1 シーン
        episode = EpisodeData(episode_number=1)
        scene = SceneData(scene_number=1)
        result.episodes.append(episode)
        episode.scenes.append(scene)

        # 状態
        pending_speech_command: ScriptToken | None = None
        pending_speech_type: str | None = None  # dialogue / monologue
        pending_has_voice: bool | None = None
        pending_speaker: Speaker | None = None
        forced_name_override: str | None = None  # name コマンド
        forced_name_label_analysis: SpeakerLabelAnalysis | None = None

        # 選択肢状態
        current_choice: BlockData | None = None
        current_option_idx: int = 0
        branch_options: list[str] = []
        # branchごとに、その直前の (current_choice, current_option_idx)
        # (ネストしたbranchなら外側のchoiceとそのoption位置、トップレベル
        # ならNone/0) を退避するスタック。#endifで必ずpopして両方を戻す
        # (current_option_idxだけ戻し忘れると、ネストしたbranch終了後に
        # 外側choiceの誤ったoptionへブロックが混入する不具合になる。
        # real data dry-run trialで発見、feature/branch-choice-dry-run)。
        branch_stack: list[tuple[BlockData | None, int]] = []

        text_lines: list[str] = []
        text_line_start: int | None = None
        text_line_end: int | None = None

        def flush_text() -> None:
            """蓄積した本文行を Block に変換してシーンへ追加する"""
            nonlocal pending_speech_command, pending_speech_type, pending_has_voice
            nonlocal pending_speaker, forced_name_override, forced_name_label_analysis
            nonlocal text_lines, text_line_start, text_line_end

            if not text_lines:
                return

            raw_t = "\n".join(text_lines)
            clean_t = _clean_text(raw_t)

            if pending_speech_command is not None or pending_speech_type is not None:
                # 会話ブロック
                block_type = pending_speech_type or "dialogue"

                # 話者決定: forced_name_override → pending_speaker の順
                if forced_name_override is not None:
                    speaker = Speaker(
                        speaker_id=None,
                        speaker_name=forced_name_override,
                        source_character_id=None,
                        slot=None,
                        is_resolved=False,
                        label_source=SOURCE_NAME_COMMAND,
                        label_analysis=forced_name_label_analysis,
                    )
                    forced_name_override = None
                    forced_name_label_analysis = None
                elif pending_speaker is not None:
                    speaker = pending_speaker
                else:
                    speaker = Speaker.unknown()

                block = BlockData(
                    block_type=block_type,
                    text=clean_t,
                    raw_text=raw_t,
                    speaker=speaker,
                    has_voice=pending_has_voice,
                    source_file=source_file,
                    line_start=text_line_start,
                    line_end=text_line_end,
                    raw_line=pending_speech_command.raw
                    if pending_speech_command
                    else None,
                    parser_rule=_speech_parser_rule(block_type, pending_has_voice),
                    confidence=1.0,
                )

                _add_block(scene, current_choice, current_option_idx, block)

                pending_speech_command = None
                pending_speech_type = None
                pending_has_voice = None
                pending_speaker = None

            elif pending_speech_type == "narration" or (
                pending_speaker is None and pending_speech_command is None
            ):
                pass  # narration は _handle_narration で処理

            # テキストリストをリセット
            text_lines = []
            text_line_start = None
            text_line_end = None

        for token in tokens:
            # ----------------------------------------------------------------
            # VARIABLE ($numX / $valueX)
            # ----------------------------------------------------------------
            if token.token_type == TokenType.VARIABLE:
                flush_text()
                cmd = token.command or ""
                num_match = NUM_VAR_PATTERN.match(cmd)
                val_match = VALUE_VAR_PATTERN.match(cmd)

                if num_match and token.args:
                    idx = int(num_match.group(1))
                    char_id = token.args[0]
                    resolver.assign_variable(
                        variable_name=cmd,
                        source_character_id=char_id,
                        num_index=idx,
                        line_start=token.line_number,
                        raw=token.raw,
                    )
                elif val_match and token.args:
                    idx = int(val_match.group(1))
                    char_id = token.args[0]
                    resolver.assign_variable(
                        variable_name=cmd,
                        source_character_id=char_id,
                        value_index=idx,
                        line_start=token.line_number,
                        raw=token.raw,
                    )
                continue

            # ----------------------------------------------------------------
            # COMMAND (@ChTalk, @ScenarioCos など)
            # ----------------------------------------------------------------
            if token.token_type == TokenType.COMMAND:
                cmd = token.command or ""
                normalized_cmd = CASE_VARIANTS_MAP.get(cmd, cmd)

                # @ScenarioCos slot id
                if cmd == "@ScenarioCos":
                    flush_text()
                    sc_match = SCENARIO_COS_PATTERN.match(token.raw)
                    if sc_match:
                        resolver.assign_character(
                            slot=sc_match.group(1),
                            source_character_id=sc_match.group(2),
                            line_start=token.line_number,
                            raw=token.raw,
                        )
                    continue

                # @ScenarioCosLoad slot variable
                if cmd == "@ScenarioCosLoad":
                    flush_text()
                    sc_load_match = SCENARIO_COS_LOAD_PATTERN.match(token.raw)
                    if sc_load_match:
                        resolver.assign_from_variable(
                            slot=sc_load_match.group(1),
                            variable_name=sc_load_match.group(2),
                            line_start=token.line_number,
                            raw=token.raw,
                        )
                    continue

                # 会話コマンド
                if cmd in {"@ChTalk", "@ChTalkSoundOff", "@ChTalkName"}:
                    flush_text()
                    slot = token.args[0] if token.args else "0"
                    pending_speech_type = "dialogue"
                    pending_has_voice = cmd == "@ChTalk"
                    if cmd == "@ChTalkName":
                        # @ChTalkName slot speakerName path
                        speaker_name = token.args[1] if len(token.args) > 1 else None
                        if speaker_name:
                            label_analysis = analyze_speaker_label(
                                speaker_name, source=SOURCE_CH_TALK_NAME
                            )
                            attach_inferred_speakers(label_analysis, self._char_dict)
                            pending_speaker = resolver.resolve_from_command_name(
                                speaker_name,
                                slot,
                                label_source=SOURCE_CH_TALK_NAME,
                                label_analysis=label_analysis,
                            )
                        else:
                            pending_speaker = resolver.resolve_slot(slot)
                        pending_has_voice = None  # unknown
                    else:
                        pending_speaker = resolver.resolve_slot(slot)
                    pending_speech_command = token
                    continue

                if cmd in {"@ChTalkMono", "@ChTalkSoundOffMono"}:
                    flush_text()
                    slot = token.args[0] if token.args else "0"
                    pending_speech_type = "monologue"
                    pending_has_voice = cmd == "@ChTalkMono"
                    pending_speaker = resolver.resolve_slot(slot)
                    pending_speech_command = token
                    continue

                # stage_direction (既知)
                if (
                    normalized_cmd in STAGE_DIRECTION_COMMANDS
                    or cmd in STAGE_DIRECTION_COMMANDS
                ):
                    flush_text()
                    if self.preserve_stage_directions:
                        direction_type = DIRECTION_TYPE_MAP.get(
                            normalized_cmd, DIRECTION_TYPE_MAP.get(cmd, "unknown")
                        )
                        block = BlockData(
                            block_type="stage_direction",
                            direction_type=direction_type,
                            raw_command=cmd,
                            normalized_command=normalized_cmd
                            if normalized_cmd != cmd
                            else cmd,
                            command_args=token.args,
                            source_file=source_file,
                            line_start=token.line_number,
                            line_end=token.line_number,
                            raw_line=token.raw,
                            parser_rule="stage_direction",
                        )
                        _add_block(scene, current_choice, current_option_idx, block)
                    continue

                # 未知コマンド
                if self.preserve_unknown:
                    flush_text()
                    result.unknown_commands[cmd] = (
                        result.unknown_commands.get(cmd, 0) + 1
                    )
                    block = BlockData(
                        block_type="unknown",
                        raw_text=token.raw,
                        source_file=source_file,
                        line_start=token.line_number,
                        line_end=token.line_number,
                        raw_line=token.raw,
                        parser_rule="unknown_command",
                        notes=[f"Unknown command: {cmd}"],
                    )
                    _add_block(scene, current_choice, current_option_idx, block)
                continue

            # ----------------------------------------------------------------
            # KEYWORD
            # ----------------------------------------------------------------
            if token.token_type == TokenType.KEYWORD:
                kw = token.command or ""

                # msg → narration
                if kw == "msg":
                    flush_text()
                    pending_speech_type = "narration"
                    pending_speech_command = token
                    # narration は次の TEXT ラインで確定させる
                    # ここでは pending だけ立てて continue
                    continue

                # name → 強制話者名
                if kw == "name":
                    flush_text()
                    forced_name = token.text or " ".join(token.args)
                    # 空の name 行は強制話者名の解除を意味する (flush_text は
                    # forced_name_override を None 判定で有効化するため、
                    # 空文字列のまま代入すると解決済みスロット話者を空名で潰してしまう)
                    forced_name_override = forced_name if forced_name else None
                    if forced_name_override is not None:
                        forced_name_label_analysis = analyze_speaker_label(
                            forced_name_override, source=SOURCE_NAME_COMMAND
                        )
                        attach_inferred_speakers(
                            forced_name_label_analysis, self._char_dict
                        )
                    else:
                        forced_name_label_analysis = None
                    resolver.set_forced_name(forced_name_override or "")
                    continue

                # branch → 選択肢定義
                if kw == "branch":
                    flush_text()
                    branch_options = token.args or []
                    # 現在の current_choice/current_option_idx (ネストした
                    # branchの場合は外側のchoiceとそのoption位置、
                    # トップレベルのbranchならNone/0) を退避してから
                    # 新しいchoiceへ切り替える。#endifで必ずここへ戻ることで、
                    # 対応する#endif以降のブロックが直前の選択肢の中に
                    # 閉じ込められる不具合を防ぐ
                    # (real data dry-run trialで発見、feature/branch-choice-dry-run)。
                    outer_choice = current_choice
                    outer_option_idx = current_option_idx
                    branch_stack.append((outer_choice, outer_option_idx))
                    # 新しい choice ブロックを作成
                    new_choice = BlockData(
                        block_type="choice",
                        source_file=source_file,
                        line_start=token.line_number,
                        line_end=token.line_number,
                        raw_line=token.raw,
                        parser_rule="branch_choice",
                    )
                    for opt_text in branch_options:
                        new_choice.options.append(
                            {
                                "optionText": opt_text,
                                "blocks": [],
                            }
                        )
                    # 新しいchoice自体を、外側の文脈 (シーン直下、または
                    # ネストしている場合は外側choiceの現在のoption) へ配置
                    # してからcurrent_choiceを切り替える
                    _add_block(scene, outer_choice, outer_option_idx, new_choice)
                    current_choice = new_choice
                    current_option_idx = 0
                    continue

                # #if → 分岐開始 (選択肢インデックスのリセットのみ。
                # push/popはbranch/#endif側が担う)
                if kw == "#if":
                    flush_text()
                    current_option_idx = 0
                    continue

                # #elseif / #else → 次の選択肢へ
                if kw in {"#elseif", "#else"}:
                    flush_text()
                    current_option_idx += 1
                    continue

                # #endif → 分岐終了。branchで退避した外側の
                # (current_choice, current_option_idx) (トップレベルなら
                # None/0) へ必ず両方戻す
                if kw == "#endif":
                    flush_text()
                    if branch_stack:
                        current_choice, current_option_idx = branch_stack.pop()
                    else:
                        current_choice = None
                        current_option_idx = 0
                    continue

                # その他の # 系
                if kw.startswith("#"):
                    flush_text()
                    continue

                # bg / bgm / se などの stage_direction キーワード
                normalized_kw = CASE_VARIANTS_MAP.get(kw, kw)
                if (
                    kw in STAGE_DIRECTION_COMMANDS
                    or normalized_kw in STAGE_DIRECTION_COMMANDS
                ):
                    flush_text()
                    if self.preserve_stage_directions:
                        direction_type = DIRECTION_TYPE_MAP.get(
                            normalized_kw, DIRECTION_TYPE_MAP.get(kw, "unknown")
                        )
                        block = BlockData(
                            block_type="stage_direction",
                            direction_type=direction_type,
                            raw_command=kw,
                            normalized_command=normalized_kw,
                            command_args=token.args,
                            source_file=source_file,
                            line_start=token.line_number,
                            line_end=token.line_number,
                            raw_line=token.raw,
                            parser_rule="stage_direction",
                        )
                        _add_block(scene, current_choice, current_option_idx, block)
                    continue

                # 未知キーワード
                if self.preserve_unknown:
                    flush_text()
                    block = BlockData(
                        block_type="unknown",
                        raw_text=token.raw,
                        source_file=source_file,
                        line_start=token.line_number,
                        line_end=token.line_number,
                        raw_line=token.raw,
                        parser_rule="unknown_keyword",
                        notes=[f"Unknown keyword: {kw}"],
                    )
                    _add_block(scene, current_choice, current_option_idx, block)
                continue

            # ----------------------------------------------------------------
            # TEXT (本文行)
            # ----------------------------------------------------------------
            if token.token_type == TokenType.TEXT:
                if pending_speech_type == "narration":
                    # narration: TEXT ラインを直接 narration ブロックにする
                    flush_text()
                    block = BlockData(
                        block_type="narration",
                        text=_clean_text(token.raw),
                        raw_text=token.raw,
                        narration_type=_guess_narration_type(token.raw),
                        source_file=source_file,
                        line_start=token.line_number,
                        line_end=token.line_number,
                        raw_line=token.raw,
                        parser_rule="msg_narration",
                        confidence=1.0,
                    )
                    _add_block(scene, current_choice, current_option_idx, block)
                    pending_speech_type = None
                    pending_speech_command = None
                    continue

                # 通常の本文行 (会話コマンド待機中)
                if text_line_start is None:
                    text_line_start = token.line_number
                text_line_end = token.line_number
                text_lines.append(token.raw)
                continue

            # ----------------------------------------------------------------
            # HYPHEN_OPTION (演出補助行)
            # ----------------------------------------------------------------
            if token.token_type == TokenType.HYPHEN_OPTION:
                flush_text()
                if self.preserve_stage_directions:
                    block = BlockData(
                        block_type="stage_direction",
                        direction_type="system",
                        raw_command="-",
                        normalized_command="-",
                        command_args=token.args,
                        source_file=source_file,
                        line_start=token.line_number,
                        line_end=token.line_number,
                        raw_line=token.raw,
                        parser_rule="hyphen_option",
                    )
                    _add_block(scene, current_choice, current_option_idx, block)
                continue

            # ----------------------------------------------------------------
            # UNKNOWN
            # ----------------------------------------------------------------
            if token.token_type == TokenType.UNKNOWN:
                flush_text()
                if self.preserve_unknown:
                    # キーは先頭コマンド語のみ (token.command) を使う。
                    # unknown_commandsの他の登録箇所 (@コマンド/keyword)
                    # およびscripts/check_script_compatibility.pyの
                    # unknownCommands集計 (first_tokenのみ) とキー形式を
                    # 揃えるため、生の行全体 (raw[:30]) は使わない。
                    unknown_key = token.command or token.raw[:30]
                    result.unknown_commands[unknown_key] = (
                        result.unknown_commands.get(unknown_key, 0) + 1
                    )
                    block = BlockData(
                        block_type="unknown",
                        raw_text=token.raw,
                        source_file=source_file,
                        line_start=token.line_number,
                        line_end=token.line_number,
                        raw_line=token.raw,
                        parser_rule="unknown_line",
                        notes=["Parser could not classify this line."],
                    )
                    _add_block(scene, current_choice, current_option_idx, block)
                continue

        # 最後の蓄積テキストをフラッシュ
        flush_text()

        # 話者割り当て記録を episode に格納
        episode.speaker_assignments = resolver.assignment_records
        episode.unresolved_character_ids = resolver.unresolved_character_ids

        return result


# ----------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------


def _add_block(
    scene: SceneData,
    current_choice: BlockData | None,
    option_idx: int,
    block: BlockData,
) -> None:
    """ブロックを適切な場所 (scene or choice option) に追加する"""
    if current_choice is not None and current_choice.options:
        idx = min(option_idx, len(current_choice.options) - 1)
        current_choice.options[idx]["blocks"].append(block)
    else:
        scene.blocks.append(block)


def _clean_text(text: str) -> str:
    """本文の正規化: 改行を除去し、タブをスペースへ変換する"""
    # 複数行を1行に統合 (\\n → 改行なし)
    lines = [line.strip() for line in text.splitlines()]
    return "".join(lines)


def _speech_parser_rule(block_type: str, has_voice: bool | None) -> str:
    """Parser ルール名を返す"""
    if block_type == "dialogue":
        if has_voice is True:
            return "ch_talk_dialogue"
        elif has_voice is False:
            return "ch_talk_sound_off_dialogue"
        else:
            return "ch_talk_name_dialogue"
    elif block_type == "monologue":
        if has_voice is True:
            return "ch_talk_mono"
        else:
            return "ch_talk_sound_off_mono"
    return "unknown_speech"


def _guess_narration_type(text: str) -> str:
    """本文からナレーション種別を推定する"""
    stripped = text.strip()
    if re.match(r"^[・・・…]+$", stripped):
        return "ellipsis"
    if "【" in stripped and "】" in stripped:
        return "location_label"
    if re.match(r"^[（(].*[)）]$", stripped):
        return "system"
    return "plain"
