"""
tests/parser/test_parser_basic.py
StoryParser の基本動作テスト
"""

import pytest

from agents.parser.parser import StoryParser
from agents.parser.resolver import CharacterDictionary


@pytest.fixture
def char_dict():
    cd = CharacterDictionary()
    cd._name_map = {"26": "レイン", "1": "赤城陽菜"}
    cd._id_map = {"26": "CHAR_RAIN", "1": "CHAR_AKAGI_HINA"}
    return cd


def test_basic_dialogue(char_dict):
    script = """$num0 = 26
@ChTalk 0
こんにちは、レインです。
"""
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)

    assert len(result.episodes) == 1
    scene = result.episodes[0].scenes[0]

    # blocks: 1(dialogue)
    # $num0 は変数割り当てなのでブロックにはならない
    assert len(scene.blocks) == 1

    dlg = scene.blocks[0]
    assert dlg.block_type == "dialogue"
    assert dlg.text == "こんにちは、レインです。"
    assert dlg.speaker.speaker_name == "レイン"
    assert dlg.has_voice is True


def test_sound_off_and_mono(char_dict):
    script = """$num0 = 1
@ChTalkSoundOff 0
声に出さないセリフ
@ChTalkMono 0
（モノローグ）
"""
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 2

    b1 = scene.blocks[0]
    assert b1.block_type == "dialogue"
    assert b1.has_voice is False
    assert b1.text == "声に出さないセリフ"

    b2 = scene.blocks[1]
    assert b2.block_type == "monologue"
    assert b2.has_voice is True
    assert b2.text == "（モノローグ）"


def test_chtalk_name():
    script = """@ChTalkName 0 美海＆恵茉 Story/64/m64_1_186
ジャマー召喚！
"""
    parser = StoryParser()
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    b = scene.blocks[0]
    assert b.block_type == "dialogue"
    assert b.speaker.speaker_name == "美海＆恵茉"
    assert b.speaker.is_resolved is False
    assert b.text == "ジャマー召喚！"


def test_forced_name():
    script = """name 謎の声
@ChTalk 0
聞こえますか。
"""
    parser = StoryParser()
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    b = scene.blocks[0]
    assert b.block_type == "dialogue"
    assert b.speaker.speaker_name == "謎の声"
    assert b.speaker.is_resolved is False


def test_empty_name_line_does_not_blank_resolved_speaker(char_dict):
    """
    実スクリプトでは、話者名を解除するための空の `name` 行が単独で
    現れることがある (例: CAB-csl_script_charastory_character234-episode1.dec)。
    これが直後のスロット解決済み話者を空文字名で潰さないことを確認する。
    """
    script = """$num0 = 26
@ScenarioCosLoad 0 $num0
name
@ChTalkSoundOff 0
スロットで解決された話者のはずのセリフ
"""
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    dlg = scene.blocks[0]
    assert dlg.block_type == "dialogue"
    assert dlg.speaker.speaker_name == "レイン"
    assert dlg.speaker.speaker_name != ""


def test_narration():
    script = """msg
異形生物対策班　本部
"""
    parser = StoryParser()
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    b = scene.blocks[0]
    assert b.block_type == "narration"
    assert b.text == "異形生物対策班　本部"
    assert b.narration_type == "plain"


def test_choice_branch():
    script = """branch 選択肢A 選択肢B
#if $branch
@ChTalk 0
ルートA
#elseif $branch
@ChTalk 0
ルートB
#endif
"""
    parser = StoryParser()
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 1
    choice = scene.blocks[0]
    assert choice.block_type == "choice"

    assert len(choice.options) == 2
    assert choice.options[0]["optionText"] == "選択肢A"
    assert len(choice.options[0]["blocks"]) == 1
    assert choice.options[0]["blocks"][0].text == "ルートA"

    assert choice.options[1]["optionText"] == "選択肢B"
    assert len(choice.options[1]["blocks"]) == 1
    assert choice.options[1]["blocks"][0].text == "ルートB"


def test_stage_direction():
    script = """bg 1 1002
@Visibleoff 1 0.5
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 2

    bg = scene.blocks[0]
    assert bg.block_type == "stage_direction"
    assert bg.direction_type == "background"
    assert bg.raw_command == "bg"

    vis = scene.blocks[1]
    assert vis.block_type == "stage_direction"
    assert vis.direction_type == "character_display"
    assert vis.raw_command == "@Visibleoff"
    assert vis.normalized_command == "@VisibleOff"
