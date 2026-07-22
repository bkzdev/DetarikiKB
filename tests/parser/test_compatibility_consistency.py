"""
tests/parser/test_compatibility_consistency.py
scripts/check_script_compatibility.py単体実行とnormalize_story.py
--check-compat経由 (agents/parser/normalizer.py) の互換性判定が一致する
ことを確認する統合テスト (feature/compatibility-check-consistency)。

config/script_commands.yaml自体はプロジェクト設定であり実データではない
ため、実ファイルをそのまま読み込んで使う。スクリプト本文はすべて合成
(短い自作のコマンド列) であり、実データ由来のfixtureは使わない。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from agents.parser.compatibility import DEFAULT_COMMANDS_CONFIG
from agents.parser.normalizer import Normalizer
from agents.parser.parser import StoryParser

PROJECT_ROOT = Path(__file__).parent.parent.parent
CHECK_SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_script_compatibility.py"


def _load_check_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_script_compatibility", CHECK_SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_both_paths(tmp_path: Path, script: str) -> tuple[dict, dict]:
    """同じスクリプト内容に対して、check_script_compatibility.py単体実行
    相当の結果と、StoryParser+NormalizerのcompatibilityReportを両方作る。"""
    script_path = tmp_path / "synthetic.dec"
    script_path.write_text(script, encoding="utf-8")

    mod = _load_check_script_module()
    config = mod.load_command_config(DEFAULT_COMMANDS_CONFIG)
    known_commands = mod.build_known_command_set(config)
    speech_commands = mod.get_speech_commands(config)
    case_variants_map = mod.build_case_variants_map(config)
    speech_hints = mod.get_new_speech_hints(config)

    standalone_result = mod.check_file(
        script_path,
        known_commands,
        speech_commands,
        case_variants_map,
        speech_hints,
        char_map={},
    )
    standalone = {
        "unknownCommands": set(standalone_result.unknown_commands.keys()),
        "newSpeechCommands": {
            e["command"] for e in standalone_result.new_speech_commands
        },
        "status": standalone_result.parser_compatibility,
    }

    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_CONSISTENCY",
        story_category="OTHER",
        commands_config_path=DEFAULT_COMMANDS_CONFIG,
    )
    story_json = normalizer.normalize(parse_result)
    report = story_json["compatibilityReport"]
    embedded = {
        "unknownCommands": {c["command"] for c in report["unknownCommands"]},
        "newSpeechCommands": {c["command"] for c in report["newSpeechCommands"]},
        "status": report["parserCompatibility"],
    }

    return standalone, embedded


def test_known_speech_commands_produce_compatible_on_both_paths(tmp_path):
    script = """$num0 = 26
@ChTalk 0
セリフ1
@ChTalkMono 0
セリフ2
@ChTalkSoundOff 0
セリフ3
@ChTalkSoundOffMono 0
セリフ4
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()
    assert standalone["newSpeechCommands"] == set()
    assert embedded["newSpeechCommands"] == set()


def test_pr30_stage_direction_commands_not_unknown_on_either_path(tmp_path):
    """PR #30で追加したcamera/pos/euler/fov/screen等が、
    どちらの経路でもunknownCommandsに現れないこと。"""
    script = """camera 0
pos -7.94,1.4,22.08
euler 3.821,141.302,0
fov 21
screen
rdraw 1 @,@,@,@ 0,0,0,1
wait 0.5
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()


def test_branch_choice_dry_run_commands_not_unknown_on_either_path(tmp_path):
    """branch/choice included dry-runで見つかったcostume/fa/@TalkPosR/
    @TalkPosL/@ChEyeOff/@VisibleS/@FadeOutBlackが、
    どちらの経路でもunknownCommandsに現れないこと。"""
    script = """costume 1 2
fa 3
@TalkPosR
@TalkPosL
@ChEyeOff 0
@VisibleS 1
@FadeOutBlack 1
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()
    assert standalone["newSpeechCommands"] == set()
    assert embedded["newSpeechCommands"] == set()


def test_dict_expansion_batch_001_command_not_unknown_on_either_path(tmp_path):
    """script-command-dictionary-expansion-batch-001 dry-runで見つかった
    @ChBlueMan/BlueMan2が、どちらの経路でもunknownCommandsに現れないこと。"""
    script = """@ChBlueMan/BlueMan2 0 1 22
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()


def test_dict_expansion_batch_002_commands_not_unknown_on_either_path(tmp_path):
    """script-command-dictionary-expansion-batch-002 (実データ全量scan、
    本編系2,301件) で見つかった未知コマンド172種のうち、代表的な新規
    stage_directionコマンド・表記ゆれが、どちらの経路でもunknownCommands
    に現れないことを確認する。"""
    script = """@ChEye2Off
@cheye2off
@Bg_Default
@bg_nightcity
@Timeline/Play 0 0 False
@TalkPosRR
@talkposRR
@chcamera
@ChTalkname 8 ? Event/example
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()
    assert standalone["newSpeechCommands"] == set()
    assert embedded["newSpeechCommands"] == set()


def test_dict_expansion_batch_002_variable_indices_not_unknown_on_standalone_path(
    tmp_path,
):
    """script-command-dictionary-expansion-batch-002で見つかった、
    値がcharacter_id(数字)ではなくモーションクリップ名や$state()呼び出しに
    なっている$numX/$valueXの個別インデックス (+ typoである$vaule0) が、
    standalone checker側でもunknownCommandsに現れないことを確認する。
    実parser側はVARIABLEトークンとして正規表現ベースで既に汎用対応済み
    (unknown_commandsに元々計上されない) のため、standalone側のみ確認する。"""
    script = """$value1 = c_idle_8
$num0 = $random(4,4)
$vaule0 = 55070
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()


def test_dict_h_scene_batch_variable_indices_not_unknown_on_standalone_path(
    tmp_path,
):
    """script-command-dictionary-h-scene-parse-target-batch (character/配下の
    パース対象ファイルで見つかった24種のうち) で見つかった$numX/$valueXの
    個別インデックス8種+$common0が、standalone checker側でも
    unknownCommandsに現れないことを確認する。実parser側はVARIABLEトークン
    として正規表現ベースで既に汎用対応済み(unknown_commandsに元々計上
    されない)のため、standalone側のみ確認する。"""
    script = """$num1 = $split(0,$value11)
$num2 = $split(1,$value11)
$num3 = $split(2,$value11)
$num4 = $split(3,$value11)
$num5 = $split(4,$value11)
$num6 = $split(5,$value11)
$value7 = $state(HighGraphicsFlag)
$value10 = $value11
$common0 = 1.6
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()


def test_dict_h_scene_parse_target_batch_commands_not_unknown_on_either_path(
    tmp_path,
):
    """script-command-dictionary-h-scene-parse-target-batchで見つかった
    新規stage_directionコマンド8種・表記ゆれ7種が、どちらの経路でも
    unknownCommandsに現れないことを確認する。"""
    script = """@ShadowOff
@Shadowoff
@ChBlueMan/SynchroMotionMirror 1 h_03_09_05 0 BlueMan/h_03_09_05_ 0.2
@Cache Motion Human/h_04_05_00
@SpringBone/BreastTouchRemoveCollider 2 1 1 2
@Spine/EyeRight
@Spine/EyeLeft
@Spine/EyeCenter
@ChBlueMan/BlueManSuimedo 0 0 17
@motionwaitU h_02_01_016_
@ChEYe2RightLow
@ChEye2RIghtLow
@ChEye2LeftlOW
@ChEYe2RightHigh
@MotioNReset
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()
    assert standalone["newSpeechCommands"] == set()
    assert embedded["newSpeechCommands"] == set()


def test_talk_camera_commands_not_misdetected_as_speech(tmp_path):
    """@TalkCamera3/@TalkCamera4はPR #30で既知コマンド化されているため、
    どちらの経路でも新規会話コマンド候補として誤検出されないこと。"""
    script = """@TalkCamera3 0
@TalkCamera4 0
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()
    assert standalone["newSpeechCommands"] == set()
    assert embedded["newSpeechCommands"] == set()


def test_truly_unknown_speech_like_command_matches_on_both_paths(tmp_path):
    """未登録のTalk系コマンドは両経路でunknownCommands・
    newSpeechCommands・statusが一致すること。"""
    script = """@BrandNewTalkVariant 1 2 3
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone == embedded
    assert standalone["unknownCommands"] == {"@BrandNewTalkVariant"}
    assert standalone["newSpeechCommands"] == {"@BrandNewTalkVariant"}
    assert standalone["status"] == "needs_update"


def test_truly_unknown_non_speech_command_matches_on_both_paths(tmp_path):
    """本当に未知の (会話ヒントに合致しない) コマンドは両経路で
    unknownとして残り、newSpeechCommandsには含まれないこと。"""
    script = """@BrandNewUnrelatedCommand 1 2 3
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone == embedded
    assert standalone["unknownCommands"] == {"@BrandNewUnrelatedCommand"}
    assert standalone["newSpeechCommands"] == set()
    assert standalone["status"] == "warning"


def test_mixed_known_and_unknown_commands_match_on_both_paths(tmp_path):
    script = """$num0 = 26
@ChTalk 0
セリフ
camera 0
pos 1,2,3
@TalkCamera3 0
@BrandNewTalkVariant 1
@BrandNewUnrelatedCommand 2
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone == embedded
    assert standalone["unknownCommands"] == {
        "@BrandNewTalkVariant",
        "@BrandNewUnrelatedCommand",
    }
    assert standalone["newSpeechCommands"] == {"@BrandNewTalkVariant"}
    assert standalone["status"] == "needs_update"


def test_chtalk_family_still_dialogue_monologue_regardless_of_compat_report(
    tmp_path,
):
    """互換性判定ロジックの共通化・変更後も、@ChTalk系コマンドの
    dialogue/monologue分類自体には一切影響しないことを確認する。"""
    script = """$num0 = 26
@ChTalk 0
通常セリフ
@ChTalkMono 0
モノローグ
@ChTalkSoundOff 0
音声なしセリフ
@ChTalkSoundOffMono 0
音声なしモノローグ
@ChTalkName 0 話者名 dummy/path
名前付きセリフ
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_CHTALK_UNAFFECTED",
        story_category="OTHER",
        commands_config_path=DEFAULT_COMMANDS_CONFIG,
    )
    story_json = normalizer.normalize(parse_result)

    blocks = story_json["episodes"][0]["scenes"][0]["blocks"]
    block_types = [b["type"] for b in blocks]
    assert block_types == [
        "dialogue",
        "monologue",
        "dialogue",
        "monologue",
        "dialogue",
    ]
    assert story_json["compatibilityReport"]["unknownCommands"] == []


def test_spinetalk_known_as_speech_not_new_speech_command_on_either_path(tmp_path):
    """script-command-dictionary-spinetalk-variant-only-batchで
    speechカテゴリへ登録した@SpineTalkが、既知speechコマンドとして
    認識され、newSpeechCommands(新規会話コマンド候補)には現れないこと。
    両経路(standalone checker / StoryParser+Normalizerのcompatibility
    Report)の一貫性を確認する。

    statusまでの完全一致は確認しない: 話者に使われた未登録character_id
    ("26")の扱いが standalone(消費文脈ベース、fix/checker-unregistered-
    character-id-consumption-basedで修正済み) と embedded(resolver.pyが
    代入時に即時解決するため常に未登録記録) で異なりstatusが分岐しうる
    (このPRのスコープ外、既存の test_known_speech_commands_produce_
    compatible_on_both_pathsも同じ理由でstatus比較を避けている)。"""
    script = """$num2 = 26
@SpineTalk $num2 H_scene/1/1_h14_42
セリフ本文
@SpineTalk 1 H_scene/217/217_h12_57
数値スロット直接指定
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()
    assert standalone["newSpeechCommands"] == set()
    assert embedded["newSpeechCommands"] == set()


def test_dict_spinetalk_variant_only_batch_commands_not_unknown_on_either_path(
    tmp_path,
):
    """script-command-dictionary-spinetalk-variant-only-batchで見つかった
    variant-only新規stage_directionコマンド6種・表記ゆれ2種が、どちらの
    経路でもunknownCommandsに現れないことを確認する。"""
    script = """@ToCloud
@VR/VRSelect
@SpringBone/BreastTouchAddCollider 2 1 1 2
@WebParsonal $value10 $arg3
@Spine/EyeDown
@ChMotionGree 0
@motionWait sg_standup_sigh4
@FadeOutblack
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()
    assert standalone["newSpeechCommands"] == set()
    assert embedded["newSpeechCommands"] == set()


def test_dict_spinetalk_batch_variable_tokens_not_unknown_on_standalone_path(
    tmp_path,
):
    """script-command-dictionary-spinetalk-variant-only-batchで見つかった
    $valueX個別インデックス3種+$common/$common1〜3+$returnが、standalone
    checker側でもunknownCommandsに現れないことを確認する。実parser側は
    $valueXを正規表現ベースで既に汎用対応済み、$common/$common1〜3/$return
    はVARIABLEトークンとして消費されるだけ(unknown_commandsに元々計上
    されない)のため、standalone側のみ確認する。"""
    script = """$value4 = 414970
$value9 = $state(Name,$value10)
$value11 = 0
$common = 0
$common1 = 1
$common2 = 2
$common3 = 3
$return = $state(HighGraphicsFlag)
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()


def test_bare_word_parameter_token_registration_not_unknown_on_either_path(tmp_path):
    """bare-word-parameter-token-registration (Character_Story_ID_Manifest_
    Design.md §9.1.2の1) で見つかった裸単語パラメータトークン14種+
    表記ゆれ1種("caemra")が、どちらの経路でもunknownCommandsに現れない
    こと (両経路の対称性) を確認する。"""
    script = """postProcess 1
depth length 33
bloom intensity 2
enable 0 false
volume enable true
analogGlitch
retroGlitch
digitalGlitch
mozaiku koyuki_9 0.018 cutoff
fade\t0\t0
mask SET CAMERA0
layer CAMERA1 true
duplication true
shadow type None
caemra 0
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()
    assert standalone["newSpeechCommands"] == set()
    assert embedded["newSpeechCommands"] == set()


def test_bare_word_parameter_token_batch_002_not_unknown_on_either_path(tmp_path):
    """bare-word-parameter-token-batch-002 (Character_Story_ID_Manifest_
    Design.md §9.1.2の1) で「要判断」のまま未登録だった残り17種が、
    登録後はどちらの経路でもunknownCommandsに現れないこと (両経路の
    対称性) を確認する。"""
    script = """spine 0
eye 0,0
hlook false
timeScale -1 1.2
springEnable\tF_L_ribbon\tfalse
add 0 animation3 true 0
moPart speed $common0
func ui_massage breast1
log --------------------HighGraphicsFlag:$value7
init
setup 0
skin normal face/H02
segment\tEye\ttrue $target(Unique,0,Head)
cset\ti 999 neck\t1,1,1\tmind\t2\ttall\t4\theadBlueMan30/hair30\t-
rdrawMat tatoo1 keep_alpha 0 @,@,@,@\t@,@,@,1
acc\t1\twset\tChara/Parts/Accessory/body564_0_acc\t@body564_0_acc\tbody564_0_acc_0
oneAuto
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone["unknownCommands"] == set()
    assert embedded["unknownCommands"] == set()
    assert standalone["newSpeechCommands"] == set()
    assert embedded["newSpeechCommands"] == set()


def test_bare_word_parameter_tokens_left_unregistered_still_unknown_on_embedded_path(
    tmp_path,
):
    """PR #153・本PRいずれの登録対象にも含まれない合成裸単語行
    (実データ由来ではない) が、実parser側では引き続きunknownCommandsに
    現れること (不破棄不変則) の無回帰を確認する。

    standalone checker側は既存の非対称性 (is_command_lineが@/$接頭辞
    または既知コマンド集合のみを対象とするため、未登録の裸単語行自体を
    コマンド行として検出しない) により、これらの行を報告しない。この
    既存の非対称性自体は本PRのスコープ外 (TASKS.md Known Issues参照)
    であり、embedded側の不破棄不変則のみを確認する。"""
    script = """synthUnregisteredBareWordAlpha 0
synthUnregisteredBareWordBeta true
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_BARE_WORD_UNREGISTERED",
        story_category="OTHER",
        commands_config_path=DEFAULT_COMMANDS_CONFIG,
    )
    story_json = normalizer.normalize(parse_result)
    report = story_json["compatibilityReport"]

    assert {c["command"] for c in report["unknownCommands"]} == {
        "synthUnregisteredBareWordAlpha",
        "synthUnregisteredBareWordBeta",
    }


def test_consumption_context_unknown_character_ids_match_on_both_paths(tmp_path):
    """feature/resolver-consumption-context-report: 実parser
    (agents/parser/resolver.py SpeakerResolver) がstandalone checkerの#141
    (feature/checker-consumption-context-fix) と同じ消費文脈ベースで
    unknownCharacterIds/nonSpeakerNumericAssignmentsを分類するように
    なったことを確認する。$numX代入 + 実際の@ChTalk消費 (話者消費あり) /
    costumeのみでの消費 (話者消費なし) の両方を含むスクリプトで、両経路の
    分類・parserCompatibilityが完全一致すること
    (@SpineTalkの$numN特別扱い等、別の既知の非対称性が絡まない
    最小構成のスクリプトを使う)。"""
    script = """$num0 = 555
@ChTalk 0
セリフ
$num1 = 666
costume 1
"""
    script_path = tmp_path / "synthetic.dec"
    script_path.write_text(script, encoding="utf-8")

    mod = _load_check_script_module()
    config = mod.load_command_config(DEFAULT_COMMANDS_CONFIG)
    known_commands = mod.build_known_command_set(config)
    speech_commands = mod.get_speech_commands(config)
    case_variants_map = mod.build_case_variants_map(config)
    speech_hints = mod.get_new_speech_hints(config)

    standalone_result = mod.check_file(
        script_path,
        known_commands,
        speech_commands,
        case_variants_map,
        speech_hints,
        char_map={},
    )

    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_CONSUMPTION_CONTEXT",
        story_category="OTHER",
        commands_config_path=DEFAULT_COMMANDS_CONFIG,
    )
    story_json = normalizer.normalize(parse_result)
    report = story_json["compatibilityReport"]

    standalone_unknown_ids = set(standalone_result.unknown_character_ids.keys())
    standalone_non_speaker_ids = set(
        standalone_result.non_speaker_numeric_assignments.keys()
    )
    embedded_unknown_ids = {
        e["sourceCharacterId"] for e in report["unknownCharacterIds"]
    }
    embedded_non_speaker_ids = {
        e["sourceCharacterId"] for e in report["nonSpeakerNumericAssignments"]
    }

    assert standalone_unknown_ids == embedded_unknown_ids == {"555"}
    assert standalone_non_speaker_ids == embedded_non_speaker_ids == {"666"}
    assert (
        standalone_result.parser_compatibility
        == report["parserCompatibility"]
        == "warning"
    )


def test_non_literal_speaker_expression_absent_from_unknown_ids_on_both_paths(
    tmp_path,
):
    """feature/non-literal-character-id-handling
    (Character_Story_ID_Manifest_Design.md §9.1.2発見③): `$split(...)`
    (未評価の関数呼び出し式) や座標様数値列がsourceCharacterIdに混入しても、
    standalone checker側は元々RHSを`\\d+`/`$変数名`に限定する正規表現
    (NUM_VAR_PATTERN/VALUE_VAR_PATTERN/SCENARIO_COS_PATTERN) のため、
    `$`始まりのRHSはそもそも未登録キャラクターID候補として検出しない
    (対称化の必要が無いことの確認)。embedded (Normalizer) 側も、本PRの
    修正によりunknownCharacterIds/nonSpeakerNumericAssignmentsへは計上せず
    nonLiteralSpeakerExpressionsへ分離することを確認する。

    数字始まりの非リテラル値を先頭整数で部分一致する旧checkerの不具合は、
    `codex/checker-variable-assignment-exact-match`で解消済み。"""
    script = """$value0 = 11.2,-7.7,-24
@ChTalk 0
セリフ
$num1 = $split(0,$value11)
@ScenarioCosLoad 1 $num1
@ChTalk 1
セリフ
$value1 = $split(1,$value11)
costume 1
"""
    script_path = tmp_path / "synthetic.dec"
    script_path.write_text(script, encoding="utf-8")

    mod = _load_check_script_module()
    config = mod.load_command_config(DEFAULT_COMMANDS_CONFIG)
    known_commands = mod.build_known_command_set(config)
    speech_commands = mod.get_speech_commands(config)
    case_variants_map = mod.build_case_variants_map(config)
    speech_hints = mod.get_new_speech_hints(config)

    standalone_result = mod.check_file(
        script_path,
        known_commands,
        speech_commands,
        case_variants_map,
        speech_hints,
        char_map={},
    )

    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_NON_LITERAL_SYMMETRY",
        story_category="OTHER",
        commands_config_path=DEFAULT_COMMANDS_CONFIG,
    )
    story_json = normalizer.normalize(parse_result)
    report = story_json["compatibilityReport"]

    assert standalone_result.unknown_character_ids == {}
    assert standalone_result.non_speaker_numeric_assignments == {}
    assert report["unknownCharacterIds"] == []
    assert report["nonSpeakerNumericAssignments"] == []
    assert {e["sourceCharacterId"] for e in report["nonLiteralSpeakerExpressions"]} == {
        "11.2,-7.7,-24",
        "$split(0,$value11)",
        "$split(1,$value11)",
    }
    assert standalone_result.parser_compatibility == "compatible"
    assert report["parserCompatibility"] == "compatible"


def test_branch_choice_script_matches_on_both_paths(tmp_path):
    """branch/#if/#else/#endifを含むスクリプトでも、check_script_
    compatibility.py単体実行とNormalizerのcompatibilityReportが一致する
    ことを確認する (feature/branch-choice-dry-run)。branch/choiceの
    ブロック構造そのものはcheck_script_compatibility.pyの管轄外だが、
    unknownCommands/newSpeechCommands/statusの判定には影響しないこと。
    """
    script = """branch 選択肢A 選択肢B
#if $branch
@ChTalk 0
ルートA
#else
@ChTalk 0
ルートB
#endif
@ChTalk 0
分岐後のセリフ
"""
    standalone, embedded = _run_both_paths(tmp_path, script)

    assert standalone == embedded
    assert standalone["unknownCommands"] == set()
    assert standalone["newSpeechCommands"] == set()
    assert standalone["status"] == "compatible"


# ----------------------------------------------------------------
# ch N + costume スロット再束縛 (feature/costume-slot-binding-fix)
# ----------------------------------------------------------------


def _run_consumption_context_paths(tmp_path: Path, script: str, name: str):
    """`_run_both_paths`の消費文脈版。unknownCharacterIds/
    nonSpeakerNumericAssignments/dialogueの話者sourceCharacterIdまで
    比較するテストで使う共通セットアップ。"""
    script_path = tmp_path / "synthetic.dec"
    script_path.write_text(script, encoding="utf-8")

    mod = _load_check_script_module()
    config = mod.load_command_config(DEFAULT_COMMANDS_CONFIG)
    known_commands = mod.build_known_command_set(config)
    speech_commands = mod.get_speech_commands(config)
    case_variants_map = mod.build_case_variants_map(config)
    speech_hints = mod.get_new_speech_hints(config)

    standalone_result = mod.check_file(
        script_path,
        known_commands,
        speech_commands,
        case_variants_map,
        speech_hints,
        char_map={},
    )

    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id=name,
        story_category="OTHER",
        commands_config_path=DEFAULT_COMMANDS_CONFIG,
    )
    story_json = normalizer.normalize(parse_result)
    report = story_json["compatibilityReport"]
    return standalone_result, parse_result, report


def test_ch_costume_slot_binding_matches_on_both_paths(tmp_path):
    """feature/costume-slot-binding-fix: `ch N`+`costume $numY $numX ON`
    形式によるスロット再束縛が、standalone checkerとembedded (Normalizer)
    の両経路で対称に分類されること。真の話者ID (26、costumeの第2引数) は
    unknownCharacterIds (話者消費あり) へ、衣装ID (999、$num1自体の値) は
    nonSpeakerNumericAssignments (話者消費なし) へ分類される。"""
    script = """$num0 = 26
$num1 = 999
ch 1
costume $num1 $num0 ON
@ChTalk 1
セリフ
"""
    standalone_result, parse_result, report = _run_consumption_context_paths(
        tmp_path, script, "TEST_CH_COSTUME_BINDING"
    )

    standalone_unknown_ids = set(standalone_result.unknown_character_ids.keys())
    standalone_non_speaker_ids = set(
        standalone_result.non_speaker_numeric_assignments.keys()
    )
    embedded_unknown_ids = {
        e["sourceCharacterId"] for e in report["unknownCharacterIds"]
    }
    embedded_non_speaker_ids = {
        e["sourceCharacterId"] for e in report["nonSpeakerNumericAssignments"]
    }

    assert standalone_unknown_ids == embedded_unknown_ids == {"26"}
    assert standalone_non_speaker_ids == embedded_non_speaker_ids == {"999"}
    assert (
        standalone_result.parser_compatibility
        == report["parserCompatibility"]
        == "warning"
    )

    # dialogueブロックの話者も衣装ID (999) ではなくキャラID (26) であること
    dlg = parse_result.episodes[0].scenes[0].blocks[-1]
    assert dlg.speaker.source_character_id == "26"


def test_ch_costume_direct_numeric_matches_on_both_paths(tmp_path):
    """costumeの引数が数値直接指定 (`costume 999 26`形式) の場合も、
    両経路で対称に分類されること (衣装ID999は代入行として一度も検出
    されないため、どちらのバケットにも入らない)。"""
    script = """ch 3
costume 999 26
@ChTalk 3
セリフ
"""
    standalone_result, parse_result, report = _run_consumption_context_paths(
        tmp_path, script, "TEST_CH_COSTUME_DIRECT_NUMERIC"
    )

    standalone_unknown_ids = set(standalone_result.unknown_character_ids.keys())
    embedded_unknown_ids = {
        e["sourceCharacterId"] for e in report["unknownCharacterIds"]
    }

    assert standalone_unknown_ids == embedded_unknown_ids == {"26"}
    assert standalone_result.non_speaker_numeric_assignments == {}
    assert report["nonSpeakerNumericAssignments"] == []
    assert (
        standalone_result.parser_compatibility
        == report["parserCompatibility"]
        == "warning"
    )


def test_costume_without_preceding_ch_matches_on_both_paths(tmp_path):
    """chが先行しない場合、costumeはスロット束縛に使われず、従来どおりの
    分類 (costumeの引数は一切追跡されない) が両経路で一致すること。"""
    script = """$num1 = 26
costume 5 6
@ChTalk 1
セリフ
"""
    standalone_result, parse_result, report = _run_consumption_context_paths(
        tmp_path, script, "TEST_COSTUME_WITHOUT_CH"
    )

    standalone_unknown_ids = set(standalone_result.unknown_character_ids.keys())
    embedded_unknown_ids = {
        e["sourceCharacterId"] for e in report["unknownCharacterIds"]
    }

    assert standalone_unknown_ids == embedded_unknown_ids == {"26"}
    assert standalone_result.non_speaker_numeric_assignments == {}
    assert report["nonSpeakerNumericAssignments"] == []
