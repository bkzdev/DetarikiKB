"""
tests/parser/test_normalizer_compatibility_report.py
agents/parser/normalizer.py の _build_compatibility_report のユニットテスト

feature/compatibility-check-consistency: Normalizerが
commands_config_path経由でconfig/script_commands.yaml相当のヒントを
使い、newSpeechCommands / parserCompatibility ステータスを実際に
判定するようになったことを検証する。すべて合成データのみ使用する。
"""

from __future__ import annotations

import yaml

from agents.parser.normalizer import Normalizer
from agents.parser.parser import StoryParser


def _write_commands_config(tmp_path, hints):
    path = tmp_path / "script_commands.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "speech": ["@ChTalk", "@ChTalkMono"],
                "new_speech_detection_hints": {"name_contains": hints},
            },
            f,
        )
    return path


def test_compatibility_report_without_config_path_is_backward_compatible():
    """commands_config_path未指定時は、従来通りnewSpeechCommandsが
    空配列のままであること (既存呼び出し元との後方互換)。"""
    script = """@UnknownTalkVariant 1
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(story_id="TEST_NO_CONFIG", story_category="OTHER")
    story_json = normalizer.normalize(parse_result)

    report = story_json["compatibilityReport"]
    assert report["newSpeechCommands"] == []


def test_compatibility_report_detects_new_speech_command(tmp_path):
    config_path = _write_commands_config(tmp_path, ["Talk", "Voice"])
    script = """@UnknownTalkVariant 1
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_WITH_CONFIG",
        story_category="OTHER",
        commands_config_path=config_path,
    )
    story_json = normalizer.normalize(parse_result)

    report = story_json["compatibilityReport"]
    assert report["newSpeechCommands"] == [
        {
            "command": "@UnknownTalkVariant",
            "reason": "Command name contains speech-related keyword.",
            "severity": "high",
            "suggestedType": "dialogue",
        }
    ]
    assert report["parserCompatibility"] == "needs_update"


def test_compatibility_report_no_false_positive_for_non_speech_unknown(tmp_path):
    config_path = _write_commands_config(tmp_path, ["Talk", "Voice"])
    script = """@TotallyUnrelatedUnknownCommand 1
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_NO_FALSE_POSITIVE",
        story_category="OTHER",
        commands_config_path=config_path,
    )
    story_json = normalizer.normalize(parse_result)

    report = story_json["compatibilityReport"]
    assert report["newSpeechCommands"] == []
    assert report["parserCompatibility"] == "warning"
    assert report["unknownCommands"] == [
        {"command": "@TotallyUnrelatedUnknownCommand", "count": 1}
    ]


def test_compatibility_report_compatible_when_all_known(tmp_path):
    config_path = _write_commands_config(tmp_path, ["Talk"])
    # sourceCharacterIdの割り当てを行わない (未登録キャラクターID扱いに
    # なるとparserCompatibilityがwarningになってしまうため、既知コマンド
    # のみでcompatibleになる最小ケースにする)
    script = """@ChTalk 0
こんにちは
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_COMPATIBLE",
        story_category="OTHER",
        commands_config_path=config_path,
    )
    story_json = normalizer.normalize(parse_result)

    report = story_json["compatibilityReport"]
    assert report["parserCompatibility"] == "compatible"
    assert report["unknownCommands"] == []
    assert report["newSpeechCommands"] == []


# ----------------------------------------------------------------
# 消費文脈ベースの未登録キャラクターID分類
# (feature/resolver-consumption-context-report、
# scripts/check_script_compatibility.pyの#141と対称化)
# ----------------------------------------------------------------


def test_compatibility_report_classifies_speaker_consumed_unknown_character_id():
    """$numX代入 -> @ChTalkで実際に話者として消費された未登録キャラクター
    IDはunknownCharacterIdsへ入り、parserCompatibilityがwarningになること。"""
    script = """$num0 = 555
@ChTalk 0
セリフ
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(story_id="TEST_CONSUMED_UNKNOWN_ID", story_category="OTHER")
    story_json = normalizer.normalize(parse_result)

    report = story_json["compatibilityReport"]
    assert report["unknownCharacterIds"] == [{"sourceCharacterId": "555"}]
    assert report["nonSpeakerNumericAssignments"] == []
    assert report["parserCompatibility"] == "warning"


def test_compatibility_report_classifies_non_speaker_numeric_assignment():
    """$numX代入のみで話者スロットとして一度も消費されなかった未登録IDは
    nonSpeakerNumericAssignmentsへ入り、parserCompatibilityには影響しない
    (costumeのみに使われる非話者引数のケース)。"""
    script = """$num1 = 666
costume 1
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(story_id="TEST_NON_SPEAKER_NUMERIC", story_category="OTHER")
    story_json = normalizer.normalize(parse_result)

    report = story_json["compatibilityReport"]
    assert report["unknownCharacterIds"] == []
    assert report["nonSpeakerNumericAssignments"] == [{"sourceCharacterId": "666"}]
    assert report["parserCompatibility"] == "compatible"


def test_compatibility_report_classifies_completely_unconsumed_assignment():
    """$numX代入のみで以降どのコマンドからも一切参照されない (完全未消費)
    未登録IDも、costume専用消費と同じnonSpeakerNumericAssignmentsバケット
    へ分類されること (checker側と同じ粒度、不破棄不変則)。"""
    script = """$num0 = 999
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_COMPLETELY_UNCONSUMED", story_category="OTHER"
    )
    story_json = normalizer.normalize(parse_result)

    report = story_json["compatibilityReport"]
    assert report["unknownCharacterIds"] == []
    assert report["nonSpeakerNumericAssignments"] == [{"sourceCharacterId": "999"}]
    assert report["parserCompatibility"] == "compatible"


def test_compatibility_report_mixed_speaker_and_non_speaker_ids():
    """話者消費あり・話者消費なしの未登録IDが混在する場合、それぞれ
    正しいバケットへ分類され、registered済みIDはどちらにも現れないこと
    (無回帰の統合確認)。"""
    from agents.parser.resolver import CharacterDictionary

    char_dict = CharacterDictionary()
    char_dict._name_map = {"26": "レイン"}
    char_dict._id_map = {"26": "CHAR_RAIN"}

    script = """$num0 = 26
@ChTalk 0
登録済みキャラクターのセリフ
$num1 = 555
@ChTalk 1
未登録・話者消費ありのセリフ
$num2 = 666
costume 2
"""
    parser = StoryParser(char_dict=char_dict)
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(story_id="TEST_MIXED_IDS", story_category="OTHER")
    story_json = normalizer.normalize(parse_result)

    report = story_json["compatibilityReport"]
    assert report["unknownCharacterIds"] == [{"sourceCharacterId": "555"}]
    assert report["nonSpeakerNumericAssignments"] == [{"sourceCharacterId": "666"}]
    assert report["parserCompatibility"] == "warning"


# ----------------------------------------------------------------
# ID形式でない (非リテラル) sourceCharacterId文字列の分離
# (feature/non-literal-character-id-handling、
# Character_Story_ID_Manifest_Design.md §9.1.2発見③の解消)
# ----------------------------------------------------------------


def test_compatibility_report_classifies_non_literal_function_call_expression():
    """$numX = $split(...) のような未評価の関数呼び出し式が話者消費された
    場合、unknownCharacterIdsへは入らずnonLiteralSpeakerExpressionsへ
    consumedAsSpeaker=trueで分類され、parserCompatibilityへは影響しない
    こと。再現条件: data/raw/character配下のH_scene系で確認した
    `$num1 = $split(0,$value11)` -> `@ScenarioCosLoad 1 $num1 ... ON` ->
    `@ChTalk 1 ...`のパターン。"""
    script = """$num1 = $split(0,$value11)
@ScenarioCosLoad 1 $num1
@ChTalk 1
セリフ
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_NON_LITERAL_FUNCTION_CALL", story_category="OTHER"
    )
    story_json = normalizer.normalize(parse_result)

    report = story_json["compatibilityReport"]
    assert report["unknownCharacterIds"] == []
    assert report["nonSpeakerNumericAssignments"] == []
    assert report["nonLiteralSpeakerExpressions"] == [
        {"sourceCharacterId": "$split(0,$value11)", "consumedAsSpeaker": True}
    ]
    assert report["parserCompatibility"] == "compatible"


def test_compatibility_report_classifies_non_literal_coordinate_like_expression():
    """$valueX = 11.2,-7.7,-24 のような座標様の数値列も同様に
    nonLiteralSpeakerExpressionsへ分類されること。再現条件: data/raw/
    character配下で確認した`$value0 = 11.2,-7.7,-24` (num系が一切無い
    ファイルでの自動slot 0束縛) -> `@ChTalk 0 ...`のパターン。"""
    script = """$value0 = 11.2,-7.7,-24
@ChTalk 0
セリフ
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_NON_LITERAL_COORDINATE", story_category="OTHER"
    )
    story_json = normalizer.normalize(parse_result)

    report = story_json["compatibilityReport"]
    assert report["unknownCharacterIds"] == []
    assert report["nonSpeakerNumericAssignments"] == []
    assert report["nonLiteralSpeakerExpressions"] == [
        {"sourceCharacterId": "11.2,-7.7,-24", "consumedAsSpeaker": True}
    ]
    assert report["parserCompatibility"] == "compatible"


def test_compatibility_report_non_literal_expression_not_consumed_as_speaker():
    """非リテラル式が代入されただけで話者スロットとして消費されない場合は
    consumedAsSpeaker=falseで記録され、parserCompatibilityには影響しない
    こと。"""
    script = """$value1 = 1.5,-2.5,-3.5
costume 1
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_NON_LITERAL_NOT_CONSUMED", story_category="OTHER"
    )
    story_json = normalizer.normalize(parse_result)

    report = story_json["compatibilityReport"]
    assert report["unknownCharacterIds"] == []
    assert report["nonSpeakerNumericAssignments"] == []
    assert report["nonLiteralSpeakerExpressions"] == [
        {"sourceCharacterId": "1.5,-2.5,-3.5", "consumedAsSpeaker": False}
    ]
    assert report["parserCompatibility"] == "compatible"


def test_compatibility_report_numeric_id_regression_unaffected_by_non_literal_split():
    """数値ID経路 (既存の消費文脈ベース分類、unknownCharacterIds/
    nonSpeakerNumericAssignments) は、非リテラル式の分離ロジック追加に
    よって一切影響を受けないこと (無回帰)。"""
    script = """$num0 = 40286
@ChTalk 0
セリフ
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_NUMERIC_ID_REGRESSION", story_category="OTHER"
    )
    story_json = normalizer.normalize(parse_result)

    report = story_json["compatibilityReport"]
    assert report["unknownCharacterIds"] == [{"sourceCharacterId": "40286"}]
    assert report["nonSpeakerNumericAssignments"] == []
    assert report["nonLiteralSpeakerExpressions"] == []
    assert report["parserCompatibility"] == "warning"


def test_compatibility_report_missing_config_file_falls_back_gracefully(tmp_path):
    """指定したcommands_config_pathが存在しない場合でも例外を投げず、
    newSpeechCommandsは空 (hints無し) のまま処理を継続する。"""
    script = """@UnknownTalkVariant 1
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(
        story_id="TEST_MISSING_CONFIG",
        story_category="OTHER",
        commands_config_path=tmp_path / "does_not_exist.yaml",
    )
    story_json = normalizer.normalize(parse_result)

    report = story_json["compatibilityReport"]
    assert report["newSpeechCommands"] == []
    assert report["parserCompatibility"] == "warning"
