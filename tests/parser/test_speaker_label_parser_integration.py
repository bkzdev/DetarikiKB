"""
tests/parser/test_speaker_label_parser_integration.py
StoryParserが name コマンド / @ChTalkName 由来のspeaker labelに、
rawLabel/labelSource/speaker label analysisを正しく付与することを確認する。

合成スクリプトのみを使う (実データは使わない)。
"""

from agents.parser.parser import StoryParser
from agents.parser.speaker_labels import (
    LABEL_TYPE_GENERIC_SPEAKER,
    LABEL_TYPE_SINGLE_SPEAKER,
    LABEL_TYPE_SPEAKER_GROUP,
    LABEL_TYPE_SPEAKER_WITH_MODIFIER,
    SOURCE_CH_TALK_NAME,
    SOURCE_NAME_COMMAND,
)


def _first_dialogue_speaker(script: str):
    parser = StoryParser()
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]
    return scene.blocks[0].speaker


def test_name_command_speaker_group_gets_label_analysis():
    script = "name セイナ＆イヴ\n@ChTalk 0\n一緒に頑張るよ！\n"
    speaker = _first_dialogue_speaker(script)

    assert speaker.speaker_name == "セイナ＆イヴ"
    assert speaker.is_resolved is False
    assert speaker.label_source == SOURCE_NAME_COMMAND
    assert speaker.label_analysis is not None
    assert speaker.label_analysis.label_type == LABEL_TYPE_SPEAKER_GROUP
    assert speaker.label_analysis.components == ["セイナ", "イヴ"]
    assert speaker.label_analysis.raw_label == "セイナ＆イヴ"


def test_name_command_speaker_with_modifier_gets_label_analysis():
    script = "name 紬（小声）\n@ChTalk 0\n静かにね……\n"
    speaker = _first_dialogue_speaker(script)

    assert speaker.label_source == SOURCE_NAME_COMMAND
    assert speaker.label_analysis.label_type == LABEL_TYPE_SPEAKER_WITH_MODIFIER
    assert speaker.label_analysis.base_label == "紬"
    assert speaker.label_analysis.modifier == "小声"


def test_name_command_generic_speaker_gets_label_analysis():
    script = "name 謎の声\n@ChTalk 0\n聞こえますか。\n"
    speaker = _first_dialogue_speaker(script)

    assert speaker.label_source == SOURCE_NAME_COMMAND
    assert speaker.label_analysis.label_type == LABEL_TYPE_GENERIC_SPEAKER


def test_name_command_plain_single_name_is_not_special():
    script = "name レイン\n@ChTalk 0\nこんにちは\n"
    speaker = _first_dialogue_speaker(script)

    assert speaker.label_source == SOURCE_NAME_COMMAND
    assert speaker.label_analysis.label_type == LABEL_TYPE_SINGLE_SPEAKER
    assert speaker.label_analysis.is_special is False


def test_ch_talk_name_speaker_group_gets_label_analysis():
    script = "@ChTalkName 0 美海＆恵茉 Story/64/m64_1_186\nジャマー召喚！\n"
    speaker = _first_dialogue_speaker(script)

    assert speaker.speaker_name == "美海＆恵茉"
    assert speaker.label_source == SOURCE_CH_TALK_NAME
    assert speaker.label_analysis.label_type == LABEL_TYPE_SPEAKER_GROUP
    assert speaker.label_analysis.components == ["美海", "恵茉"]


def test_speaker_id_resolved_via_character_id_has_no_label_source():
    from agents.parser.resolver import CharacterDictionary

    char_dict = CharacterDictionary()
    char_dict._name_map = {"26": "レイン"}
    char_dict._id_map = {"26": "CHAR_RAIN"}

    script = "@ScenarioCos 0 26\n@ChTalk 0\nこんにちは、レインです。\n"
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)
    speaker = result.episodes[0].scenes[0].blocks[0].speaker

    assert speaker.speaker_name == "レイン"
    assert speaker.label_source is None
    assert speaker.label_analysis is None


def test_speaker_to_dict_omits_label_fields_when_absent():
    from agents.parser.resolver import CharacterDictionary

    char_dict = CharacterDictionary()
    char_dict._name_map = {"26": "レイン"}
    char_dict._id_map = {"26": "CHAR_RAIN"}

    script = "@ScenarioCos 0 26\n@ChTalk 0\nこんにちは、レインです。\n"
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)
    speaker_dict = result.episodes[0].scenes[0].blocks[0].speaker.to_dict()

    assert "labelSource" not in speaker_dict
    assert "labelAnalysis" not in speaker_dict


def test_speaker_to_dict_includes_label_fields_when_present():
    script = "name セイナ＆イヴ\n@ChTalk 0\n一緒に頑張るよ！\n"
    speaker = _first_dialogue_speaker(script)
    speaker_dict = speaker.to_dict()

    assert speaker_dict["labelSource"] == SOURCE_NAME_COMMAND
    assert speaker_dict["labelAnalysis"]["labelType"] == LABEL_TYPE_SPEAKER_GROUP
    assert speaker_dict["labelAnalysis"]["rawLabel"] == "セイナ＆イヴ"
