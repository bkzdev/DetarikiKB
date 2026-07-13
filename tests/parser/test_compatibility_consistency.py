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
