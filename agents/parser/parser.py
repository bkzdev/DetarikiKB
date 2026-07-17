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
        # ch N (表示スロットN指定の裸コマンド) で直近に指定されたスロット番号。
        # 直後 (間に別の ch が現れるまでの範囲) に出現する costume コマンドの
        # スロット再束縛先として参照する (feature/costume-slot-binding-fix)。
        pending_ch_slot: str | None = None

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
                    parser_rule=_speech_parser_rule(
                        block_type,
                        pending_has_voice,
                        pending_speech_command.command
                        if pending_speech_command
                        else None,
                    ),
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

                # @ScenarioCos slot id (数値直接指定) / slot $var (変数経由)
                if cmd == "@ScenarioCos":
                    flush_text()
                    sc_match = SCENARIO_COS_PATTERN.match(token.raw)
                    if sc_match:
                        second_arg = sc_match.group(2)
                        if second_arg.startswith("$"):
                            # @ScenarioCosLoad と同じ意味論: 変数マップからIDを引いて
                            # スロットへ束縛する (第3引数以降は無視)
                            resolver.assign_from_variable(
                                slot=sc_match.group(1),
                                variable_name=second_arg,
                                line_start=token.line_number,
                                raw=token.raw,
                            )
                        else:
                            resolver.assign_character(
                                slot=sc_match.group(1),
                                source_character_id=second_arg,
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

                # @SpineTalk slot_arg voice/textアセット参照path
                # (script-command-dictionary-spinetalk-variant-only-batch)。
                # @ChTalkと同型のセリフコマンドだが、第1引数が数値スロット
                # 直接指定 (@ChTalkと同じ) の場合と $numN 変数参照の場合の
                # 両方が実データに存在する (延べ2,893回中2,891回が$numN形式)。
                # $numN代入時にresolver側でslot=Nへ自動束縛される既存の
                # 意味論 (03_Scope.md §5.2、slot番号==変数indexが約98%一致)
                # を再利用し、$numNからNを抽出してスロット解決する。
                if cmd == "@SpineTalk":
                    flush_text()
                    slot_arg = token.args[0] if token.args else "0"
                    num_var_match = NUM_VAR_PATTERN.match(slot_arg)
                    slot = num_var_match.group(1) if num_var_match else slot_arg
                    pending_speech_type = "dialogue"
                    pending_has_voice = True
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

                # ch N (表示スロットN指定の裸コマンド) → 直後の costume による
                # スロット再束縛のためNを記憶する (feature/costume-slot-binding-fix)。
                # 数値スロット引数を伴わない ch (カメラ演出目的の別用法) は
                # ウィンドウを無効化する (誤ったスロットへ costume を束縛しない
                # ため)。stage_direction ブロック自体は従来どおり生成するため
                # continue はしない (下の stage_direction 分岐へフォールスルー)。
                if kw == "ch":
                    if token.args and token.args[0].isdigit():
                        pending_ch_slot = token.args[0]
                    else:
                        pending_ch_slot = None

                # costume <衣装ID> <キャラID> [ON] → 直前の ch N で記憶した
                # スロットNを、第2引数 (キャラID) で再束縛する
                # (feature/costume-slot-binding-fix、@ScenarioCosと同等の
                # 意味論のスロット再束縛)。ch が無い場合 (pending_ch_slot が
                # None) は従来どおり束縛に使わない。こちらも stage_direction
                # ブロック生成へフォールスルーするため continue はしない。
                elif kw == "costume":
                    if pending_ch_slot is not None and len(token.args) >= 2:
                        resolver.assign_costume_character(
                            slot=pending_ch_slot,
                            second_arg=token.args[1],
                            line_start=token.line_number,
                            raw=token.raw,
                        )

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
        episode.non_speaker_numeric_assignment_ids = (
            resolver.non_speaker_numeric_assignment_ids
        )
        episode.non_literal_speaker_expressions = (
            resolver.non_literal_speaker_expressions
        )

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
