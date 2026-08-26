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
    # script-command-dictionary-expansion-batch-001 dry-run で見つかった
    # 演出コマンド (config/script_commands.yaml の stage_direction と対で追加)。
    "@ChBlueMan/BlueMan2": "character_display",
    # script-command-dictionary-expansion-batch-002: 実データ全量scan
    # (本編系2,301件)で見つかったunique172種のうち、演出コマンド84種
    # (config/script_commands.yaml の stage_direction と対で追加)。
    # --- ChEye2/ChEye 系 (character_display) ---
    "@ChEye2Off": "character_display",
    "@ChEye2Right": "character_display",
    "@ChEye2Left": "character_display",
    "@ChEye2RightLow": "character_display",
    "@ChEye2LeftLow": "character_display",
    "@ChEye2LeftHigh": "character_display",
    "@ChEye2RightHigh": "character_display",
    "@ChEye2Low": "character_display",
    "@ChEye2High": "character_display",
    "@ChEyeHigh": "character_display",
    "@ChEyeLow": "character_display",
    # --- ChHead 系 (character_display) ---
    "@ChHeadOff": "character_display",
    "@ChHeadRight": "character_display",
    "@ChHeadLeft": "character_display",
    "@ChHeadRightLow": "character_display",
    "@ChHeadLeftLow": "character_display",
    "@ChHeadHigh": "character_display",
    "@ChHeadLow": "character_display",
    "@ChHeadLeftHigh": "character_display",
    "@ChHeadRightHigh": "character_display",
    # --- motion 系 ---
    "@MotionWaitU": "motion",
    "@MotionWaitS": "motion",
    "@SynchroMotion": "motion",
    "@ChBlueMan/SynchroMotion": "motion",
    "@MotionCache": "motion",
    # --- TalkPos 系 (ui) ---
    "@TalkPosRR": "ui",
    "@TalkPosLL": "ui",
    "@TalkPosZoomLori": "ui",
    "@TalkPosZoom": "ui",
    "@TalkPosLori": "ui",
    # --- ChChara (character_display) ---
    "@ChChara": "character_display",
    # --- ChTere 系 (character_display) ---
    "@ChTere2": "character_display",
    "@ChTere1": "character_display",
    "@ChTereOff": "character_display",
    "@ChTere3": "character_display",
    # --- Bg_ 系 (background) ---
    "@Bg_Default": "background",
    "@Bg_SunsetLight": "background",
    "@Bg_NightCity": "background",
    "@Bg_Night": "background",
    "@Bg_Dark": "background",
    "@Bg_Sunset": "background",
    "@Bg/43": "background",
    # --- ChColor (character_display) ---
    "@ChColor": "character_display",
    # --- ChangePos 系 (character_display) ---
    "@ChangePos": "character_display",
    "@ChangePosL": "character_display",
    "@ChangePosR": "character_display",
    "@ChangeWait": "character_display",
    # --- Fade/screen 系 ---
    "@FadeIn": "screen",
    "@FadeOut": "screen",
    "@TalkFadeOut": "screen",
    "@BlackOut": "screen",
    # --- LookPos 系 (camera) ---
    "@LookPos": "camera",
    "@LookPosOff": "camera",
    # --- PostProcess 系 (screen) ---
    "@PostProcess": "screen",
    "@PostProcessGrain": "screen",
    "@PostProcessGrainOff": "screen",
    # --- Timeline 系 (system) ---
    "@Timeline/Play": "system",
    "@Timeline/LoadW": "system",
    "@Timeline/Load": "system",
    "@Timeline/Stop": "system",
    "@Timeline/PlayChange": "system",
    # --- Image 系 (system) ---
    "@ImageLoad": "system",
    "@ImageWhite": "system",
    # --- TalkCamera 系 (camera) ---
    "@TalkCamera5": "camera",
    "@TalkCamera": "camera",
    "@TalkCamera2": "camera",
    "@TalkCameraZoom": "camera",
    # --- misc camera/system/character_display ---
    "@Shadow": "character_display",
    "@CameraNoise": "camera",
    "@H_Window": "system",
    "@Towel_Reset": "system",
    "@ScaleReset": "character_display",
    "@ChUniqEye": "character_display",
    "@ChUniqEyeOff": "character_display",
    "@ChUruuruOn": "character_display",
    "@ChUruuruOff": "character_display",
    # --- BlueMan 系 (character_display) ---
    "@BlueMan": "character_display",
    "@BlueMan_Boy": "character_display",
    "@ChBlueMan/BlueMan": "character_display",
    # --- speech-command-likeだが安全側でstage_direction化 ---
    "@ChTalkSoundOffmono": "character_display",
    "@ChTalkSoundoff": "character_display",
    "@ChTalkmono": "character_display",
    "@ChTalkname": "character_display",
    "@Chtalkname": "character_display",
    # evidence-index-stage2-batch-promotion: Stage 2 batch5 storyのnormalize
    # で見つかった未登録コマンド3種 (config/script_commands.yaml の
    # stage_direction、agents/parser/tokenizer.py の KEYWORD_TOKENS と対で追加)。
    "vol": "sound",  # BGM/SE音量制御 ("sound Bgm ..."直後の "vol 0"/"vol 1")
    "{": "character_display",  # 複数chスロットへのstage direction同時グループ化 (開始)
    "}": "character_display",  # 複数chスロットへのstage direction同時グループ化 (終了)
    # script-command-dictionary-h-scene-parse-target-batch: character/配下の
    # パース対象ファイル(H_sceneN本体・H_scene_s・episodeN/episode_EX)で
    # 見つかった新規演出コマンド8種 (config/script_commands.yaml の
    # stage_direction と対で追加)。
    "@ShadowOff": "character_display",
    "@ChBlueMan/SynchroMotionMirror": "motion",
    "@Cache": "system",
    "@SpringBone/BreastTouchRemoveCollider": "motion",
    "@Spine/EyeRight": "character_display",
    "@Spine/EyeLeft": "character_display",
    "@Spine/EyeCenter": "character_display",
    "@ChBlueMan/BlueManSuimedo": "character_display",
    # script-command-dictionary-spinetalk-variant-only-batch: character/配下の
    # variant-onlyファイル(パース対象外の`_n`/`_VR`/`_spine`/`#N`変種、および
    # camera/finish/episode_bgm等の純コマンド演出ファイル)にのみ出現する
    # 新規演出コマンド6種 (config/script_commands.yaml の stage_direction と
    # 対で追加)。
    "@ToCloud": "screen",
    "@VR/VRSelect": "system",
    "@SpringBone/BreastTouchAddCollider": "motion",
    "@WebParsonal": "system",
    "@Spine/EyeDown": "character_display",
    "@ChMotionGree": "motion",
    # bare-word-parameter-token-registration: character/配下の`_spine`系
    # ファイルに出現する、@接頭辞を持たない継続パラメータ行
    # (Character_Story_ID_Manifest_Design.md §9.1.2の1、実測32種のうち
    # カメラ/ポストエフェクト系と機械分類できた14種)。実データ確認の結果、
    # postProcess/depth/bloom/enable/volumeは既存の"@PostProcess"直後に
    # 現れる継続パラメータ (postProcess自体がscreen分類のため揃える)、
    # analogGlitch/retroGlitch/digitalGlitch/mozaiku/fadeは画面全体の
    # 視覚効果トグル、mask/layer/duplication/shadowは"camera N"直後に
    # 現れるカメラレイヤー/シャドウ設定であることを確認した
    # (agents/parser/tokenizer.py の KEYWORD_TOKENS と対で追加)。
    "postProcess": "screen",
    "depth": "screen",
    "bloom": "screen",
    "enable": "screen",
    "volume": "screen",
    "analogGlitch": "screen",
    "retroGlitch": "screen",
    "digitalGlitch": "screen",
    "mozaiku": "screen",
    "fade": "screen",
    "mask": "camera",
    "layer": "camera",
    "duplication": "camera",
    "shadow": "camera",
    # bare-word-parameter-token-batch-002: 上記14種+表記ゆれ1種の登録では
    # 機械分類できず「要判断」のまま残っていた残り17種 (Character_Story_ID_
    # Manifest_Design.md §9.1.2の1、実測32種の残部)。Fable決定(2026-07-17)
    # によりカメラ/screen系との断定を待たず全種を安全側でstage_directionへ
    # 登録し、direction_typeはPR #153の前例(分類が割れるものは安全側)を
    # 適用して機械的に割り当てた: spine/eye/hlookは常に隣接して出現する
    # Spine rig視線パラメータ (character_display)、timeScale/springEnable/
    # add/moPartはアニメーション再生速度・spring boneコライダー・
    # アニメーションレイヤートグル・モーションパーツ速度と実データで確認
    # できたモーション/物理系 (motion、既存の"@SpringBone/*"="motion"等と
    # 揃える)、残りは"func"(ui_camera/ui_massage等が同一トークンに混在する
    # 汎用ディスパッチャ)・"log"(デバッグ出力)・"init"(postProcess/非カメラ
    # 文脈の両方に出現し一意に分類不能)を含め、文脈依存または判断に迷う
    # ものとして安全側デフォルトのsystemへ分類した
    # (agents/parser/tokenizer.py の KEYWORD_TOKENS と対で追加)。
    "spine": "character_display",
    "eye": "character_display",
    "hlook": "character_display",
    "timeScale": "motion",
    "springEnable": "motion",
    "add": "motion",
    "moPart": "motion",
    "func": "system",
    "log": "system",
    "init": "system",
    "setup": "system",
    "skin": "system",
    "segment": "system",
    "cset": "system",
    "rdrawMat": "system",
    "acc": "system",
    "oneAuto": "system",
}

# 表記ゆれ → 正規化
CASE_VARIANTS_MAP: dict[str, str] = {
    "@Visibleoff": "@VisibleOff",
    "@ChCameraoff": "@ChCameraOff",
    "@ChCharaEyeoff": "@ChCharaEyeOff",
    "@Smartphoneoff": "@SmartphoneOff",
    # config/script_commands.yamlで既に管理しているvariable typo。
    # compatibilityReportの観測にだけ使い、変数評価・束縛の意味は変えない。
    "$vaule0": "$value0",
    # script-command-dictionary-expansion-batch-002: 実データ全量scanで
    # 見つかった表記ゆれ80種 (config/script_commands.yaml の
    # case_variants と対で追加)。
    "@CHEye2Off": "@ChEye2Off",
    "@CHEye2Right": "@ChEye2Right",
    "@ChEYe2Right": "@ChEye2Right",
    "@ChEye2OFf": "@ChEye2Off",
    "@ChEye2off": "@ChEye2Off",
    "@cheye2Left": "@ChEye2Left",
    "@cheye2LeftLow": "@ChEye2LeftLow",
    "@cheye2Off": "@ChEye2Off",
    "@cheye2RightLow": "@ChEye2RightLow",
    "@cheye2left": "@ChEye2Left",
    "@cheye2leftLow": "@ChEye2LeftLow",
    "@cheye2off": "@ChEye2Off",
    "@cheye2right": "@ChEye2Right",
    "@ChHeadOFF": "@ChHeadOff",
    "@ChHeadoff": "@ChHeadOff",
    "@ChHeadRIght": "@ChHeadRight",
    "@ChheadLeft": "@ChHeadLeft",
    "@ChheadOff": "@ChHeadOff",
    "@ChheadRight": "@ChHeadRight",
    "@Chheadoff": "@ChHeadOff",
    "@chheadOff": "@ChHeadOff",
    "@chheadleft": "@ChHeadLeft",
    "@chheadleftLow": "@ChHeadLeftLow",
    "@chheadleftlow": "@ChHeadLeftLow",
    "@chheadlow": "@ChHeadLow",
    "@chheadoff": "@ChHeadOff",
    "@chheadright": "@ChHeadRight",
    "@chheadrighthigh": "@ChHeadRightHigh",
    "@chheadrightlow": "@ChHeadRightLow",
    "@motionwait": "@MotionWait",
    "@Motionwait": "@MotionWait",
    "@MotioNWait": "@MotionWait",
    "@motionreset": "@MotionReset",
    "@motionReset": "@MotionReset",
    "@facelow": "@FaceLow",
    "@Facelow": "@FaceLow",
    "@faceLow": "@FaceLow",
    "@visible": "@Visible",
    "@visibleoff": "@VisibleOff",
    "@visibleOff": "@VisibleOff",
    "@visibleOFF": "@VisibleOff",
    "@VisibleOFF": "@VisibleOff",
    "@VisibleOFf": "@VisibleOff",
    "@talkpos": "@TalkPos",
    "@talkposL": "@TalkPosL",
    "@talkposR": "@TalkPosR",
    "@talkposLL": "@TalkPosLL",
    "@talkposRR": "@TalkPosRR",
    "@talkposLLL": "@TalkPosLLL",
    "@talkposRRR": "@TalkPosRRR",
    "@TalKPos": "@TalkPos",
    "@chcamera": "@ChCamera",
    "@chCamera": "@ChCamera",
    "@Chcamera": "@ChCamera",
    "@chcameraoff": "@ChCameraOff",
    "@chCameraoff": "@ChCameraOff",
    "@chcameraOff": "@ChCameraOff",
    "@ChCameraOFF": "@ChCameraOff",
    "@ChcameraOff": "@ChCameraOff",
    "@Chcameraoff": "@ChCameraOff",
    "@chCameraOff": "@ChCameraOff",
    "@ChcameraOFF": "@ChCameraOff",
    "@chChara": "@ChChara",
    "@chchara": "@ChChara",
    "@chtere2": "@ChTere2",
    "@chtereoff": "@ChTereOff",
    "@bg_nightcity": "@Bg_NightCity",
    "@Bg_night": "@Bg_Night",
    "@bg_sunset": "@Bg_Sunset",
    "@ChColor2Off": "@ChColor2off",
    "@chcolor2": "@ChColor2",
    "@chcolor2off": "@ChColor2off",
    "@Chcolor2": "@ChColor2",
    "@talkfadein": "@TalkFadeIn",
    "@fadeoutblack": "@FadeOutBlack",
    "@talkcamera3": "@TalkCamera3",
    "@talkcamera5": "@TalkCamera5",
    "@talkcamera4": "@TalkCamera4",
    "@Talkcamera4": "@TalkCamera4",
    "@isloading": "@IsLoading",
    # script-command-dictionary-h-scene-parse-target-batch: character/配下の
    # パース対象ファイル(H_sceneN本体・H_scene_s・episodeN/episode_EX)で
    # 見つかった表記ゆれ7種 (config/script_commands.yaml の case_variants
    # と対で追加)。
    "@motionwaitU": "@MotionWaitU",
    "@ChEYe2RightLow": "@ChEye2RightLow",
    "@ChEye2RIghtLow": "@ChEye2RightLow",
    "@ChEye2LeftlOW": "@ChEye2LeftLow",
    "@ChEYe2RightHigh": "@ChEye2RightHigh",
    "@MotioNReset": "@MotionReset",
    "@Shadowoff": "@ShadowOff",
    # script-command-dictionary-spinetalk-variant-only-batch: character/配下の
    # variant-onlyファイルで見つかった表記ゆれ2種 (config/script_commands.yaml
    # の case_variants と対で追加)。
    "@motionWait": "@MotionWait",
    "@FadeOutblack": "@FadeOutBlack",
    # bare-word-parameter-token-registration: character/配下の`_spine`系
    # ファイルで見つかった表記ゆれ1種 ("caemra"、"camera"のtypo、実データで
    # 唯一の出現1件がpos/euler/fovのカメラ設定triadと同じ配置で確認できた)。
    # agents/parser/tokenizer.py の KEYWORD_TOKENS と対で追加。
    "caemra": "camera",
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

# @ScenarioCos (第2引数は数値の直接指定、または $numX/$valueX 等の変数指定のいずれか)
SCENARIO_COS_PATTERN = re.compile(r"^@ScenarioCos\s+(\d+)\s+(\d+|\$[\w\d]+)")
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
    # 話者スロットとして一度も消費されなかった未登録の数値代入
    # (feature/resolver-consumption-context-report、SpeakerResolver.
    # non_speaker_numeric_assignment_idsから転記。#141のcheckerと同じ
    # 消費文脈ベース分類の(b)側。判定には影響しない情報保持用)
    non_speaker_numeric_assignment_ids: set[str] = field(default_factory=set)
    # ID形式でない (非リテラル) sourceCharacterId文字列
    # (feature/non-literal-character-id-handling、SpeakerResolver.
    # non_literal_speaker_expressionsから転記。sourceCharacterId ->
    # 話者スロットとして実消費されたか。§9.1.2発見③の解消)
    non_literal_speaker_expressions: dict[str, bool] = field(default_factory=dict)
    scenes: list[SceneData] = field(default_factory=list)


@dataclass
class ParseResult:
    """Parser 全体の出力"""

    episodes: list[EpisodeData] = field(default_factory=list)
    control_chars_removed: int = 0
    unknown_commands: dict[str, int] = field(default_factory=dict)
    new_speech_commands: list[str] = field(default_factory=list)
    # normalized command -> distinct raw variants。出現回数ではなく、
    # standalone compatibility checkerと同じ表記集合を不破棄で保持する。
    case_variants: dict[str, set[str]] = field(default_factory=dict)


@dataclass
class _ParseState:
    """1回のparse呼び出しに閉じた可変状態。"""

    result: ParseResult
    resolver: SpeakerResolver
    episode: EpisodeData
    scene: SceneData
    source_file: str
    pending_speech_command: ScriptToken | None = None
    pending_speech_type: str | None = None
    pending_has_voice: bool | None = None
    pending_speaker: Speaker | None = None
    forced_name_override: str | None = None
    forced_name_label_analysis: SpeakerLabelAnalysis | None = None
    # `ch N` と後続 `costume` の組を、間に stage direction があっても結び付ける。
    # 新しい `ch` が現れた場合は last-wins でスロットを更新する。
    pending_ch_slot: str | None = None
    current_choice: BlockData | None = None
    current_option_idx: int = 0
    # nested branch の終了時に、外側 choice と option index の両方を復元する。
    branch_stack: list[tuple[BlockData | None, int]] = field(default_factory=list)
    text_lines: list[str] = field(default_factory=list)
    text_line_start: int | None = None
    text_line_end: int | None = None

    def add_block(self, block: BlockData) -> None:
        _add_block(
            self.scene,
            self.current_choice,
            self.current_option_idx,
            block,
        )

    def flush_text(self) -> None:
        """蓄積した本文行をBlockへ変換し、parse状態を更新する。"""
        if not self.text_lines:
            return

        raw_text = "\n".join(self.text_lines)
        clean_text = _clean_text(raw_text)

        if (
            self.pending_speech_command is not None
            or self.pending_speech_type is not None
        ):
            block_type = self.pending_speech_type or "dialogue"
            speaker = self._resolve_pending_speaker()
            block = BlockData(
                block_type=block_type,
                text=clean_text,
                raw_text=raw_text,
                speaker=speaker,
                has_voice=self.pending_has_voice,
                source_file=self.source_file,
                line_start=self.text_line_start,
                line_end=self.text_line_end,
                raw_line=(
                    self.pending_speech_command.raw
                    if self.pending_speech_command
                    else None
                ),
                parser_rule=_speech_parser_rule(
                    block_type,
                    self.pending_has_voice,
                    (
                        self.pending_speech_command.command
                        if self.pending_speech_command
                        else None
                    ),
                ),
                confidence=1.0,
            )
            self.add_block(block)
            self.pending_speech_command = None
            self.pending_speech_type = None
            self.pending_has_voice = None
            self.pending_speaker = None

        self.text_lines = []
        self.text_line_start = None
        self.text_line_end = None

    def _resolve_pending_speaker(self) -> Speaker:
        if self.forced_name_override is not None:
            speaker = Speaker(
                speaker_id=None,
                speaker_name=self.forced_name_override,
                source_character_id=None,
                slot=None,
                is_resolved=False,
                label_source=SOURCE_NAME_COMMAND,
                label_analysis=self.forced_name_label_analysis,
            )
            self.forced_name_override = None
            self.forced_name_label_analysis = None
            return speaker
        if self.pending_speaker is not None:
            return self.pending_speaker
        return Speaker.unknown()

    def finalize_episode(self) -> None:
        """resolverが保持した診断情報をepisodeへ転記する。"""
        self.episode.speaker_assignments = self.resolver.assignment_records
        self.episode.unresolved_character_ids = self.resolver.unresolved_character_ids
        self.episode.non_speaker_numeric_assignment_ids = (
            self.resolver.non_speaker_numeric_assignment_ids
        )
        self.episode.non_literal_speaker_expressions = (
            self.resolver.non_literal_speaker_expressions
        )


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

    def _parse_tokens(
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

        state = _ParseState(
            result=result,
            resolver=resolver,
            episode=episode,
            scene=scene,
            source_file=source_file,
        )

        for token in tokens:
            self._handle_token(state, token)

        # 最後の蓄積テキストをフラッシュ
        state.flush_text()
        state.finalize_episode()

        return result

    def _handle_token(self, state: _ParseState, token: ScriptToken) -> None:
        """token種別ごとのhandlerへ処理を委譲する。"""
        command = token.command or ""
        normalized = CASE_VARIANTS_MAP.get(command)
        if normalized is not None and normalized != command:
            state.result.case_variants.setdefault(normalized, set()).add(command)

        handlers = {
            TokenType.VARIABLE: self._handle_variable,
            TokenType.COMMAND: self._handle_command,
            TokenType.KEYWORD: self._handle_keyword,
            TokenType.TEXT: self._handle_text,
            TokenType.HYPHEN_OPTION: self._handle_hyphen_option,
            TokenType.UNKNOWN: self._handle_unknown,
        }
        handler = handlers.get(token.token_type)
        if handler is not None:
            handler(state, token)

    def _handle_variable(self, state: _ParseState, token: ScriptToken) -> None:
        state.flush_text()
        command = token.command or ""
        num_match = NUM_VAR_PATTERN.match(command)
        value_match = VALUE_VAR_PATTERN.match(command)

        if num_match and token.args:
            state.resolver.assign_variable(
                variable_name=command,
                source_character_id=token.args[0],
                num_index=int(num_match.group(1)),
                line_start=token.line_number,
                raw=token.raw,
            )
        elif value_match and token.args:
            state.resolver.assign_variable(
                variable_name=command,
                source_character_id=token.args[0],
                value_index=int(value_match.group(1)),
                line_start=token.line_number,
                raw=token.raw,
            )

    def _handle_command(self, state: _ParseState, token: ScriptToken) -> None:
        command = token.command or ""
        normalized_command = CASE_VARIANTS_MAP.get(command, command)

        if command == "@ScenarioCos":
            self._handle_scenario_cos(state, token)
            return
        if command == "@ScenarioCosLoad":
            self._handle_scenario_cos_load(state, token)
            return
        if command in {"@ChTalk", "@ChTalkSoundOff", "@ChTalkName"}:
            self._start_dialogue(state, token)
            return
        if command in {"@ChTalkMono", "@ChTalkSoundOffMono"}:
            self._start_monologue(state, token)
            return
        if command == "@SpineTalk":
            self._start_spine_dialogue(state, token)
            return
        if (
            normalized_command in STAGE_DIRECTION_COMMANDS
            or command in STAGE_DIRECTION_COMMANDS
        ):
            self._add_stage_direction(
                state,
                token,
                raw_command=command,
                normalized_command=normalized_command,
            )
            return
        if self.preserve_unknown:
            state.flush_text()
            state.result.unknown_commands[command] = (
                state.result.unknown_commands.get(command, 0) + 1
            )
            state.add_block(
                self._unknown_block(
                    state,
                    token,
                    parser_rule="unknown_command",
                    note=f"Unknown command: {command}",
                )
            )

    def _handle_scenario_cos(self, state: _ParseState, token: ScriptToken) -> None:
        state.flush_text()
        match = SCENARIO_COS_PATTERN.match(token.raw)
        if match is None:
            return
        slot = match.group(1)
        second_arg = match.group(2)
        if second_arg.startswith("$"):
            state.resolver.assign_from_variable(
                slot=slot,
                variable_name=second_arg,
                line_start=token.line_number,
                raw=token.raw,
            )
            return
        state.resolver.assign_character(
            slot=slot,
            source_character_id=second_arg,
            line_start=token.line_number,
            raw=token.raw,
        )

    def _handle_scenario_cos_load(self, state: _ParseState, token: ScriptToken) -> None:
        state.flush_text()
        match = SCENARIO_COS_LOAD_PATTERN.match(token.raw)
        if match is None:
            return
        state.resolver.assign_from_variable(
            slot=match.group(1),
            variable_name=match.group(2),
            line_start=token.line_number,
            raw=token.raw,
        )

    def _start_dialogue(self, state: _ParseState, token: ScriptToken) -> None:
        state.flush_text()
        command = token.command or ""
        slot = token.args[0] if token.args else "0"
        state.pending_speech_type = "dialogue"
        state.pending_has_voice = command == "@ChTalk"
        if command == "@ChTalkName":
            speaker_name = token.args[1] if len(token.args) > 1 else None
            if speaker_name:
                label_analysis = analyze_speaker_label(
                    speaker_name,
                    source=SOURCE_CH_TALK_NAME,
                )
                attach_inferred_speakers(label_analysis, self._char_dict)
                state.pending_speaker = state.resolver.resolve_from_command_name(
                    speaker_name,
                    slot,
                    label_source=SOURCE_CH_TALK_NAME,
                    label_analysis=label_analysis,
                )
            else:
                state.pending_speaker = state.resolver.resolve_slot(slot)
            state.pending_has_voice = None
        else:
            state.pending_speaker = state.resolver.resolve_slot(slot)
        state.pending_speech_command = token

    def _start_monologue(self, state: _ParseState, token: ScriptToken) -> None:
        state.flush_text()
        command = token.command or ""
        slot = token.args[0] if token.args else "0"
        state.pending_speech_type = "monologue"
        state.pending_has_voice = command == "@ChTalkMono"
        state.pending_speaker = state.resolver.resolve_slot(slot)
        state.pending_speech_command = token

    def _start_spine_dialogue(self, state: _ParseState, token: ScriptToken) -> None:
        state.flush_text()
        slot_arg = token.args[0] if token.args else "0"
        # @SpineTalk の `$numN` は変数の値ではなく、既存実装どおり slot N を指す。
        num_var_match = NUM_VAR_PATTERN.match(slot_arg)
        slot = num_var_match.group(1) if num_var_match else slot_arg
        state.pending_speech_type = "dialogue"
        state.pending_has_voice = True
        state.pending_speaker = state.resolver.resolve_slot(slot)
        state.pending_speech_command = token

    def _handle_keyword(self, state: _ParseState, token: ScriptToken) -> None:
        keyword = token.command or ""
        self._apply_keyword_slot_binding(state, token, keyword)

        handlers = {
            "msg": self._start_narration,
            "name": self._set_forced_name,
            "branch": self._start_branch,
            "#if": self._start_branch_condition,
            "#elseif": self._advance_branch_option,
            "#else": self._advance_branch_option,
            "#endif": self._end_branch,
        }
        handler = handlers.get(keyword)
        if handler is not None:
            handler(state, token)
            return
        if keyword.startswith("#"):
            state.flush_text()
            return

        normalized_keyword = CASE_VARIANTS_MAP.get(keyword, keyword)
        if (
            keyword in STAGE_DIRECTION_COMMANDS
            or normalized_keyword in STAGE_DIRECTION_COMMANDS
        ):
            self._add_stage_direction(
                state,
                token,
                raw_command=keyword,
                normalized_command=normalized_keyword,
            )
            return
        if self.preserve_unknown:
            state.flush_text()
            state.add_block(
                self._unknown_block(
                    state,
                    token,
                    parser_rule="unknown_keyword",
                    note=f"Unknown keyword: {keyword}",
                )
            )

    @staticmethod
    def _apply_keyword_slot_binding(
        state: _ParseState,
        token: ScriptToken,
        keyword: str,
    ) -> None:
        if keyword == "ch":
            state.pending_ch_slot = (
                token.args[0] if token.args and token.args[0].isdigit() else None
            )
        elif (
            keyword == "costume"
            and state.pending_ch_slot is not None
            and len(token.args) >= 2
        ):
            state.resolver.assign_costume_character(
                slot=state.pending_ch_slot,
                second_arg=token.args[1],
                line_start=token.line_number,
                raw=token.raw,
            )

    @staticmethod
    def _start_narration(
        state: _ParseState,
        token: ScriptToken,
    ) -> None:
        state.flush_text()
        state.pending_speech_type = "narration"
        state.pending_speech_command = token

    def _set_forced_name(
        self,
        state: _ParseState,
        token: ScriptToken,
    ) -> None:
        state.flush_text()
        forced_name = token.text or " ".join(token.args)
        state.forced_name_override = forced_name if forced_name else None
        if state.forced_name_override is not None:
            state.forced_name_label_analysis = analyze_speaker_label(
                state.forced_name_override,
                source=SOURCE_NAME_COMMAND,
            )
            attach_inferred_speakers(
                state.forced_name_label_analysis,
                self._char_dict,
            )
        else:
            state.forced_name_label_analysis = None
        state.resolver.set_forced_name(state.forced_name_override or "")

    @staticmethod
    def _start_branch(
        state: _ParseState,
        token: ScriptToken,
    ) -> None:
        state.flush_text()
        outer_choice = state.current_choice
        outer_option_idx = state.current_option_idx
        state.branch_stack.append((outer_choice, outer_option_idx))
        new_choice = BlockData(
            block_type="choice",
            source_file=state.source_file,
            line_start=token.line_number,
            line_end=token.line_number,
            raw_line=token.raw,
            parser_rule="branch_choice",
        )
        for option_text in token.args or []:
            new_choice.options.append(
                {
                    "optionText": option_text,
                    "blocks": [],
                }
            )
        _add_block(state.scene, outer_choice, outer_option_idx, new_choice)
        state.current_choice = new_choice
        state.current_option_idx = 0

    @staticmethod
    def _start_branch_condition(
        state: _ParseState,
        _token: ScriptToken,
    ) -> None:
        state.flush_text()
        state.current_option_idx = 0

    @staticmethod
    def _advance_branch_option(
        state: _ParseState,
        _token: ScriptToken,
    ) -> None:
        state.flush_text()
        state.current_option_idx += 1

    @staticmethod
    def _end_branch(
        state: _ParseState,
        _token: ScriptToken,
    ) -> None:
        state.flush_text()
        if state.branch_stack:
            state.current_choice, state.current_option_idx = state.branch_stack.pop()
        else:
            state.current_choice = None
            state.current_option_idx = 0

    def _add_stage_direction(
        self,
        state: _ParseState,
        token: ScriptToken,
        *,
        raw_command: str,
        normalized_command: str,
    ) -> None:
        state.flush_text()
        if not self.preserve_stage_directions:
            return
        direction_type = DIRECTION_TYPE_MAP.get(
            normalized_command,
            DIRECTION_TYPE_MAP.get(raw_command, "unknown"),
        )
        state.add_block(
            BlockData(
                block_type="stage_direction",
                direction_type=direction_type,
                raw_command=raw_command,
                normalized_command=normalized_command,
                command_args=token.args,
                source_file=state.source_file,
                line_start=token.line_number,
                line_end=token.line_number,
                raw_line=token.raw,
                parser_rule="stage_direction",
            )
        )

    def _handle_text(self, state: _ParseState, token: ScriptToken) -> None:
        if state.pending_speech_type == "narration":
            state.flush_text()
            state.add_block(
                BlockData(
                    block_type="narration",
                    text=_clean_text(token.raw),
                    raw_text=token.raw,
                    narration_type=_guess_narration_type(token.raw),
                    source_file=state.source_file,
                    line_start=token.line_number,
                    line_end=token.line_number,
                    raw_line=token.raw,
                    parser_rule="msg_narration",
                    confidence=1.0,
                )
            )
            state.pending_speech_type = None
            state.pending_speech_command = None
            return

        if state.text_line_start is None:
            state.text_line_start = token.line_number
        state.text_line_end = token.line_number
        state.text_lines.append(token.raw)

    def _handle_hyphen_option(self, state: _ParseState, token: ScriptToken) -> None:
        state.flush_text()
        if not self.preserve_stage_directions:
            return
        state.add_block(
            BlockData(
                block_type="stage_direction",
                direction_type="system",
                raw_command="-",
                normalized_command="-",
                command_args=token.args,
                source_file=state.source_file,
                line_start=token.line_number,
                line_end=token.line_number,
                raw_line=token.raw,
                parser_rule="hyphen_option",
            )
        )

    def _handle_unknown(self, state: _ParseState, token: ScriptToken) -> None:
        state.flush_text()
        if not self.preserve_unknown:
            return
        unknown_key = token.command or token.raw[:30]
        state.result.unknown_commands[unknown_key] = (
            state.result.unknown_commands.get(unknown_key, 0) + 1
        )
        state.add_block(
            self._unknown_block(
                state,
                token,
                parser_rule="unknown_line",
                note="Parser could not classify this line.",
            )
        )

    @staticmethod
    def _unknown_block(
        state: _ParseState,
        token: ScriptToken,
        *,
        parser_rule: str,
        note: str,
    ) -> BlockData:
        return BlockData(
            block_type="unknown",
            raw_text=token.raw,
            source_file=state.source_file,
            line_start=token.line_number,
            line_end=token.line_number,
            raw_line=token.raw,
            parser_rule=parser_rule,
            notes=[note],
        )


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


def _speech_parser_rule(
    block_type: str, has_voice: bool | None, command: str | None = None
) -> str:
    """Parser ルール名を返す"""
    if command == "@SpineTalk":
        # script-command-dictionary-spinetalk-variant-only-batch: @ChTalkと
        # 同型だが、証跡 (source.raw) だけでなくparserRule単体からも
        # @SpineTalk由来のブロックだと判別できるよう専用ルール名を返す
        # (PR D の動的部分集合判定がこの区別を利用する想定)。
        return "spine_talk_dialogue"
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
