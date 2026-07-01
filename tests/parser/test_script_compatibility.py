"""
tests/parser/test_script_compatibility.py
互換性チェックのユニットテスト
"""

import pytest
from pathlib import Path
from scripts.check_script_compatibility import (
    check_file,
    FileCompatibilityResult,
)

@pytest.fixture
def dummy_config():
    return {
        "speech_commands": {"@ChTalk", "@ChTalkMono", "@ChTalkSoundOff", "@ChTalkSoundOffMono", "@ChTalkName"},
        "known_commands": {
            "@ChTalk", "@ChTalkMono", "@ChTalkSoundOff", "@ChTalkSoundOffMono", "@ChTalkName",
            "@ScenarioCos", "@ScenarioCosLoad",
            "msg", "name", "branch", "#if", "#elseif", "#else", "#endif",
            "bg", "bgm", "se", "@Visible", "@VisibleOff"
        },
        "case_variants_map": {
            "@Visibleoff": "@VisibleOff"
        },
        "speech_hints": ["Talk", "Mono", "Name"],
        "char_map": {
            "26": "レイン",
            "29": "レイヴェル",
            "1": "赤城陽菜"
        }
    }

def test_basic_compatibility(dummy_config, tmp_path):
    # テスト用スクリプトの作成
    script_content = """$num0 = 26
@ScenarioCos 1 29
@ChTalk 0
こんにちは。
msg
ナレーションテキスト。
branch A B
#if $branch
@ChTalk 0
選択肢Aのセリフ
#else
@ChTalk 0
選択肢Bのセリフ
#endif
"""
    script_path = tmp_path / "basic.dec"
    script_path.write_text(script_content, encoding="utf-8")

    result = check_file(
        file_path=script_path,
        known_commands=dummy_config["known_commands"],
        speech_commands=dummy_config["speech_commands"],
        case_variants_map=dummy_config["case_variants_map"],
        speech_hints=dummy_config["speech_hints"],
        char_map=dummy_config["char_map"]
    )

    assert result.parser_compatibility == "compatible"
    assert len(result.unknown_commands) == 0
    assert len(result.unknown_character_ids) == 0
    assert len(result.new_speech_commands) == 0
    assert len(result.branch_issues) == 0

def test_unknown_command_and_char(dummy_config, tmp_path):
    # 未知コマンド、未登録キャラクターIDを含むスクリプト
    script_content = """$num0 = 999
@UnknownCommand 1 2 3
@ChTalk 0
セリフ
"""
    script_path = tmp_path / "unknown.dec"
    script_path.write_text(script_content, encoding="utf-8")

    result = check_file(
        file_path=script_path,
        known_commands=dummy_config["known_commands"],
        speech_commands=dummy_config["speech_commands"],
        case_variants_map=dummy_config["case_variants_map"],
        speech_hints=dummy_config["speech_hints"],
        char_map=dummy_config["char_map"]
    )

    # warningになるはず
    assert result.parser_compatibility == "warning"
    assert "@UnknownCommand" in result.unknown_commands
    assert "999" in result.unknown_character_ids

def test_new_speech_command(dummy_config, tmp_path):
    # 新規会話コマンド候補を含むスクリプト
    script_content = """@NewTalkCommand 0
新しい会話コマンドのテスト。
"""
    script_path = tmp_path / "new_speech.dec"
    script_path.write_text(script_content, encoding="utf-8")

    result = check_file(
        file_path=script_path,
        known_commands=dummy_config["known_commands"],
        speech_commands=dummy_config["speech_commands"],
        case_variants_map=dummy_config["case_variants_map"],
        speech_hints=dummy_config["speech_hints"],
        char_map=dummy_config["char_map"]
    )

    # needs_updateになるはず
    assert result.parser_compatibility == "needs_update"
    assert any(c["command"] == "@NewTalkCommand" for c in result.new_speech_commands)

def test_branch_issues(dummy_config, tmp_path):
    # 分岐構文に異常があるスクリプト
    script_content = """branch A B
#if $branch
@ChTalk 0
テキスト
"""
    script_path = tmp_path / "branch_err.dec"
    script_path.write_text(script_content, encoding="utf-8")

    result = check_file(
        file_path=script_path,
        known_commands=dummy_config["known_commands"],
        speech_commands=dummy_config["speech_commands"],
        case_variants_map=dummy_config["case_variants_map"],
        speech_hints=dummy_config["speech_hints"],
        char_map=dummy_config["char_map"]
    )

    # needs_update になるか確認（branch_issues の severity によるが、通常 high 以上）
    assert result.parser_compatibility in ("needs_update", "blocked")
    assert any(issue["type"] == "missing_endif" for issue in result.branch_issues)
