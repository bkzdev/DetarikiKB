"""
tests/parser/test_tokenizer.py
Tokenizer のユニットテスト
"""

import pytest

from agents.parser.tokenizer import (
    TokenType,
    tokenize_text,
)

# ----------------------------------------------------------------
# 基本的なトークン分類
# ----------------------------------------------------------------


class TestBasicTokenTypes:
    def test_empty_line_excluded_by_default(self):
        tokens = tokenize_text("\n\n")
        assert len(tokens) == 0

    def test_empty_line_included_when_keep_empty(self):
        tokens = tokenize_text("\n", keep_empty=True)
        assert any(t.token_type == TokenType.EMPTY for t in tokens)

    def test_comment_excluded_by_default(self):
        tokens = tokenize_text("// これはコメント\n")
        assert len(tokens) == 0

    def test_comment_included_when_keep_comments(self):
        tokens = tokenize_text("// コメント\n", keep_comments=True)
        assert len(tokens) == 1
        assert tokens[0].token_type == TokenType.COMMENT
        assert "コメント" in tokens[0].text

    def test_command_at_prefix(self):
        tokens = tokenize_text("@ChTalk 0\n")
        assert len(tokens) == 1
        assert tokens[0].token_type == TokenType.COMMAND
        assert tokens[0].command == "@ChTalk"
        assert tokens[0].args == ["0"]

    def test_keyword_msg(self):
        tokens = tokenize_text("msg\n")
        assert len(tokens) == 1
        assert tokens[0].token_type == TokenType.KEYWORD
        assert tokens[0].command == "msg"

    def test_keyword_name_with_arg(self):
        tokens = tokenize_text("name レイン\n")
        assert len(tokens) == 1
        assert tokens[0].token_type == TokenType.KEYWORD
        assert tokens[0].command == "name"
        assert tokens[0].text == "レイン"

    def test_japanese_text_is_text_type(self):
        tokens = tokenize_text("ようこそ、異形生物対策班へ。\n")
        assert len(tokens) == 1
        assert tokens[0].token_type == TokenType.TEXT
        assert tokens[0].text == "ようこそ、異形生物対策班へ。"

    def test_hyphen_option_line(self):
        tokens = tokenize_text("- speed 0.1\n")
        assert len(tokens) == 1
        assert tokens[0].token_type == TokenType.HYPHEN_OPTION
        assert tokens[0].command == "-"

    def test_variable_num(self):
        tokens = tokenize_text("$num0 = 26\n")
        assert len(tokens) == 1
        assert tokens[0].token_type == TokenType.VARIABLE
        assert tokens[0].command == "$num0"
        assert tokens[0].args == ["26"]

    def test_variable_value(self):
        tokens = tokenize_text("$value1 = 29\n")
        assert len(tokens) == 1
        assert tokens[0].token_type == TokenType.VARIABLE
        assert tokens[0].command == "$value1"
        assert tokens[0].args == ["29"]

    def test_branch_keyword(self):
        tokens = tokenize_text("branch 選択肢A 選択肢B\n")
        assert len(tokens) == 1
        assert tokens[0].token_type == TokenType.KEYWORD
        assert tokens[0].command == "branch"
        assert "選択肢A" in tokens[0].args
        assert "選択肢B" in tokens[0].args

    def test_if_keyword(self):
        tokens = tokenize_text("#if $branch\n")
        assert len(tokens) == 1
        assert tokens[0].token_type == TokenType.KEYWORD
        assert tokens[0].command == "#if"

    def test_elseif_keyword(self):
        tokens = tokenize_text("#elseif $branch\n")
        assert tokens[0].command == "#elseif"

    def test_else_keyword(self):
        tokens = tokenize_text("#else\n")
        assert tokens[0].command == "#else"

    def test_endif_keyword(self):
        tokens = tokenize_text("#endif\n")
        assert tokens[0].command == "#endif"


# ----------------------------------------------------------------
# 実データdry-run trialで見つかった@なし演出コマンド
# (docs/runbooks/Real_Data_Dry_Run_Result_Template.md §3.2)
# ----------------------------------------------------------------


class TestRealDataStageDirectionKeywords:
    """camera/pos/euler/fov 等の@なし演出コマンドが UNKNOWN ではなく
    KEYWORD として認識されることを確認する (script command coverage改善)。"""

    @pytest.mark.parametrize(
        "line,expected_command",
        [
            ("camera 0\n", "camera"),
            ("pos -7.94,1.4,22.08\n", "pos"),
            ("euler 3.821,141.302,0\n", "euler"),
            ("fov 21\n", "fov"),
            ("ch 1\n", "ch"),
            ("nf 0.3 500\n", "nf"),
            ("wait 0.5\n", "wait"),
            ("ui 0\n", "ui"),
            ("rdraw 1 @,@,@,@ 0,0,0,1\n", "rdraw"),
            ("hide\n", "hide"),
            ("visible false\n", "visible"),
            ("mo idle\n", "mo"),
            ("sound Bgm ca_story_main\n", "sound"),
            ("vo Event/260609_tukasahome/ev_tsukasa_13\n", "vo"),
            ("prefab 1\n", "prefab"),
            ("set 526\n", "set"),
            ("click\n", "click"),
            ("screen\n", "screen"),
            ("scale 1,1,1\n", "scale"),
            ("remove\n", "remove"),
            ("wType 1\n", "wType"),
            ("loading false\n", "loading"),
            ("active tear_mesh true\n", "active"),
            ("color 0,0,0,1\n", "color"),
            ("wset Prefab/Prefab1091 @Prefab1091 2\n", "wset"),
            ("parent Chara 1 RightHand\n", "parent"),
            ("light 0\n", "light"),
            ("image ThumbnailIcon/Script/sin\n", "image"),
            ("distance 1\n", "distance"),
            ("shake 0.5\n", "shake"),
            ("uniq 1\n", "uniq"),
        ],
    )
    def test_known_bare_word_stage_command_is_keyword(self, line, expected_command):
        tokens = tokenize_text(line)
        assert len(tokens) == 1
        assert tokens[0].token_type == TokenType.KEYWORD
        assert tokens[0].command == expected_command

    def test_truly_unknown_bare_word_remains_unknown(self):
        """辞書に無い語は引き続き UNKNOWN として保持される。"""
        tokens = tokenize_text("totallyUnknownCommand123\n")
        assert len(tokens) == 1
        assert tokens[0].token_type == TokenType.UNKNOWN
        assert tokens[0].command == "totallyUnknownCommand123"


# ----------------------------------------------------------------
# 会話コマンド
# ----------------------------------------------------------------


class TestSpeechCommands:
    def test_ch_talk(self):
        tokens = tokenize_text("@ChTalk 0\n")
        t = tokens[0]
        assert t.token_type == TokenType.COMMAND
        assert t.command == "@ChTalk"
        assert t.args == ["0"]
        assert t.is_speech_command

    def test_ch_talk_mono(self):
        tokens = tokenize_text("@ChTalkMono 1\n")
        t = tokens[0]
        assert t.command == "@ChTalkMono"
        assert t.is_speech_command

    def test_ch_talk_sound_off(self):
        tokens = tokenize_text("@ChTalkSoundOff 6\n")
        t = tokens[0]
        assert t.command == "@ChTalkSoundOff"
        assert t.is_speech_command

    def test_ch_talk_sound_off_mono(self):
        tokens = tokenize_text("@ChTalkSoundOffMono 1\n")
        t = tokens[0]
        assert t.command == "@ChTalkSoundOffMono"
        assert t.is_speech_command

    def test_ch_talk_name(self):
        tokens = tokenize_text("@ChTalkName 0 美海＆恵茉 Story/64/m64_1_186\n")
        t = tokens[0]
        assert t.command == "@ChTalkName"
        assert t.args[0] == "0"
        assert t.args[1] == "美海＆恵茉"
        assert t.is_speech_command


# ----------------------------------------------------------------
# @ScenarioCos / @ScenarioCosLoad
# ----------------------------------------------------------------


class TestScenarioCommands:
    def test_scenario_cos(self):
        tokens = tokenize_text("@ScenarioCos 0 26\n")
        t = tokens[0]
        assert t.token_type == TokenType.COMMAND
        assert t.command == "@ScenarioCos"
        assert t.args == ["0", "26"]

    def test_scenario_cos_load(self):
        tokens = tokenize_text("@ScenarioCosLoad 0 $num0\n")
        t = tokens[0]
        assert t.command == "@ScenarioCosLoad"
        assert t.args[1] == "$num0"


# ----------------------------------------------------------------
# 制御文字
# ----------------------------------------------------------------


class TestControlChars:
    def test_control_char_removed(self):
        # \x02 などの制御文字を含む行
        text = "テスト\x02テキスト\n"
        tokens = tokenize_text(text)
        # 制御文字が除去されていること
        assert len(tokens) == 1
        assert "\x02" not in tokens[0].raw
        assert tokens[0].control_chars_removed == 1

    def test_control_char_count(self):
        text = "\x02\x07\x08テキスト\n"
        tokens = tokenize_text(text)
        assert tokens[0].control_chars_removed == 3


# ----------------------------------------------------------------
# 行番号の保持
# ----------------------------------------------------------------


class TestLineNumbers:
    def test_line_numbers_are_correct(self):
        script = "@ChTalk 0\nこんにちは\nmsg\nナレーション\n"
        tokens = tokenize_text(script)
        # コメント・空行を除いた行番号
        line_numbers = [t.line_number for t in tokens]
        assert line_numbers == [1, 2, 3, 4]

    def test_line_number_with_empty_lines(self):
        script = "\n\n@ChTalk 0\n"
        tokens = tokenize_text(script)
        assert tokens[0].line_number == 3


# ----------------------------------------------------------------
# raw 保持
# ----------------------------------------------------------------


class TestRawPreservation:
    def test_raw_line_preserved(self):
        tokens = tokenize_text("@ChTalk 0\n")
        assert tokens[0].raw == "@ChTalk 0"

    def test_japanese_raw_preserved(self):
        line = (
            "というわけで、本日付けで異形生物対策班作戦参謀に任命されましたレインです。"
        )
        tokens = tokenize_text(line + "\n")
        assert tokens[0].text == line
        assert tokens[0].raw == line


# ----------------------------------------------------------------
# 複数行スクリプト統合テスト
# ----------------------------------------------------------------


class TestMultilineScript:
    def test_basic_conversation(self):
        script = """$num0 = 26
@ScenarioCos 1 29
@ChTalk 0
こんにちは。
msg
ナレーションテキスト。
"""
        tokens = tokenize_text(script)
        types = [t.token_type for t in tokens]
        assert TokenType.VARIABLE in types
        assert TokenType.COMMAND in types
        assert TokenType.KEYWORD in types
        assert TokenType.TEXT in types

    def test_is_narration_property(self):
        tokens = tokenize_text("msg\n")
        assert tokens[0].is_narration
