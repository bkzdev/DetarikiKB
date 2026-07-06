"""
tests/parser/test_speaker_labels.py
agents/parser/speaker_labels.py の構造化ロジックのテスト。

name コマンド / @ChTalkName 由来のspeaker labelを、通常のunresolved
characterとは区別してspeaker_group/speaker_with_modifier/generic_speaker等へ
分類できることを確認する。自動でconfirmed character解決をしないことも
あわせて確認する。合成データのみを使う。
"""

from agents.parser.resolver import CharacterDictionary
from agents.parser.speaker_labels import (
    LABEL_TYPE_AMBIGUOUS_SPEAKER,
    LABEL_TYPE_GENERIC_SPEAKER,
    LABEL_TYPE_SINGLE_SPEAKER,
    LABEL_TYPE_SPEAKER_GROUP,
    LABEL_TYPE_SPEAKER_GROUP_WITH_MODIFIER,
    LABEL_TYPE_SPEAKER_WITH_MODIFIER,
    LABEL_TYPE_UNKNOWN,
    RESOLUTION_STATUS_INFERRED,
    RESOLUTION_STATUS_NEEDS_REVIEW,
    RESOLUTION_STATUS_NOT_APPLICABLE,
    SOURCE_NAME_COMMAND,
    analyze_speaker_label,
    attach_inferred_speakers,
    classify_speaker_label,
    extract_trailing_modifier,
    is_special_label_type,
    split_speaker_group,
)

# ----------------------------------------------------------------
# extract_trailing_modifier
# ----------------------------------------------------------------


def test_extract_trailing_modifier_full_width_parens():
    base, modifier = extract_trailing_modifier("紬（小声）")
    assert base == "紬"
    assert modifier == "小声"


def test_extract_trailing_modifier_half_width_parens():
    base, modifier = extract_trailing_modifier("紬(小声)")
    assert base == "紬"
    assert modifier == "小声"


def test_extract_trailing_modifier_no_parens():
    base, modifier = extract_trailing_modifier("レイン")
    assert base == "レイン"
    assert modifier is None


def test_extract_trailing_modifier_parens_only_keeps_whole_label():
    # base部分が空になる場合はmodifier無し扱い (呼び出し側でunknown判定)
    base, modifier = extract_trailing_modifier("（小声）")
    assert base == "（小声）"
    assert modifier is None


# ----------------------------------------------------------------
# split_speaker_group
# ----------------------------------------------------------------


def test_split_speaker_group_full_width_ampersand():
    assert split_speaker_group("セイナ＆イヴ") == ["セイナ", "イヴ"]


def test_split_speaker_group_half_width_ampersand():
    assert split_speaker_group("セイナ&イヴ") == ["セイナ", "イヴ"]


def test_split_speaker_group_full_width_slash():
    assert split_speaker_group("セイナ／イヴ") == ["セイナ", "イヴ"]


def test_split_speaker_group_half_width_slash():
    assert split_speaker_group("セイナ/イヴ") == ["セイナ", "イヴ"]


def test_split_speaker_group_japanese_comma():
    assert split_speaker_group("セイナ、イヴ") == ["セイナ", "イヴ"]


def test_split_speaker_group_middle_dot_not_treated_as_delimiter():
    # 「・」は誤検出しやすいためspeaker_group側では扱わない
    assert split_speaker_group("イヴ・セイナ") == []


def test_split_speaker_group_single_name_returns_empty():
    assert split_speaker_group("レイン") == []


# ----------------------------------------------------------------
# classify_speaker_label / analyze_speaker_label
# ----------------------------------------------------------------


def test_speaker_group_ampersand_full_width():
    assert classify_speaker_label("セイナ＆イヴ") == LABEL_TYPE_SPEAKER_GROUP


def test_speaker_group_ampersand_half_width():
    assert classify_speaker_label("セイナ&イヴ") == LABEL_TYPE_SPEAKER_GROUP


def test_speaker_with_modifier_full_width_parens():
    assert classify_speaker_label("紬（小声）") == LABEL_TYPE_SPEAKER_WITH_MODIFIER


def test_speaker_with_modifier_half_width_parens():
    assert classify_speaker_label("紬(小声)") == LABEL_TYPE_SPEAKER_WITH_MODIFIER


def test_speaker_group_with_modifier():
    assert (
        classify_speaker_label("セイナ＆イヴ（小声）")
        == LABEL_TYPE_SPEAKER_GROUP_WITH_MODIFIER
    )


def test_generic_speaker_question_marks():
    assert classify_speaker_label("？？？") in (
        LABEL_TYPE_GENERIC_SPEAKER,
        LABEL_TYPE_AMBIGUOUS_SPEAKER,
    )


def test_generic_speaker_mysterious_voice():
    assert classify_speaker_label("謎の声") == LABEL_TYPE_GENERIC_SPEAKER


def test_single_speaker_normal_name():
    assert classify_speaker_label("レイン") == LABEL_TYPE_SINGLE_SPEAKER


def test_ambiguous_speaker_middle_dot():
    analysis = analyze_speaker_label("イヴ・セイナ", source=SOURCE_NAME_COMMAND)
    assert analysis.label_type == LABEL_TYPE_AMBIGUOUS_SPEAKER
    assert analysis.components == ["イヴ", "セイナ"]
    assert analysis.resolution_status == RESOLUTION_STATUS_NEEDS_REVIEW


def test_unknown_label_type_for_empty_label():
    analysis = analyze_speaker_label("", source=SOURCE_NAME_COMMAND)
    assert analysis.label_type == LABEL_TYPE_UNKNOWN
    assert analysis.resolution_status == RESOLUTION_STATUS_NEEDS_REVIEW


def test_analyze_speaker_label_preserves_raw_label_and_source():
    analysis = analyze_speaker_label("セイナ＆イヴ", source=SOURCE_NAME_COMMAND)
    assert analysis.raw_label == "セイナ＆イヴ"
    assert analysis.source == SOURCE_NAME_COMMAND


def test_analyze_speaker_label_single_speaker_resolution_status():
    analysis = analyze_speaker_label("レイン", source=SOURCE_NAME_COMMAND)
    assert analysis.label_type == LABEL_TYPE_SINGLE_SPEAKER
    assert analysis.resolution_status == RESOLUTION_STATUS_NOT_APPLICABLE


def test_analyze_speaker_label_group_resolution_status_is_inferred():
    analysis = analyze_speaker_label("セイナ＆イヴ", source=SOURCE_NAME_COMMAND)
    assert analysis.resolution_status == RESOLUTION_STATUS_INFERRED
    # confirmedは自動では絶対に付与しない
    assert analysis.resolution_status != "confirmed"


# ----------------------------------------------------------------
# is_special_label_type
# ----------------------------------------------------------------


def test_single_speaker_is_not_special():
    assert is_special_label_type(LABEL_TYPE_SINGLE_SPEAKER) is False


def test_speaker_group_is_special():
    assert is_special_label_type(LABEL_TYPE_SPEAKER_GROUP) is True


def test_generic_speaker_is_special():
    assert is_special_label_type(LABEL_TYPE_GENERIC_SPEAKER) is True


# ----------------------------------------------------------------
# attach_inferred_speakers (自動confirmed禁止の確認を含む)
# ----------------------------------------------------------------


def _build_char_dict() -> CharacterDictionary:
    cd = CharacterDictionary()
    cd._name_map = {"201": "セイナ", "202": "イヴ", "203": "紬"}
    cd._id_map = {"201": "CHAR_TEST_SEINA", "202": "CHAR_TEST_EVE"}
    cd._confirmed_name_to_id = {
        "セイナ": "CHAR_TEST_SEINA",
        "イヴ": "CHAR_TEST_EVE",
    }
    cd._known_names = {"セイナ", "イヴ", "紬"}
    return cd


def test_attach_inferred_speakers_confirmed_match():
    char_dict = _build_char_dict()
    analysis = analyze_speaker_label("セイナ＆イヴ", source=SOURCE_NAME_COMMAND)
    attach_inferred_speakers(analysis, char_dict)

    assert len(analysis.inferred_speakers) == 2
    matched_names = {s["matchedName"] for s in analysis.inferred_speakers}
    assert matched_names == {"セイナ", "イヴ"}
    for speaker in analysis.inferred_speakers:
        assert speaker["characterId"] in {"CHAR_TEST_SEINA", "CHAR_TEST_EVE"}
        assert speaker["matchStatus"] == "dictionary_confirmed"

    # 自動でconfirmed characterへ解決したことにはならない
    assert analysis.resolution_status == RESOLUTION_STATUS_INFERRED
    assert analysis.resolution_status != "confirmed"


def test_attach_inferred_speakers_name_only_match_has_no_character_id():
    char_dict = _build_char_dict()
    analysis = analyze_speaker_label("紬（小声）", source=SOURCE_NAME_COMMAND)
    attach_inferred_speakers(analysis, char_dict)

    assert len(analysis.inferred_speakers) == 1
    speaker = analysis.inferred_speakers[0]
    assert speaker["matchedName"] == "紬"
    assert speaker["characterId"] is None
    assert speaker["matchStatus"] == "dictionary_name_only"
    assert speaker["confidence"] == "low"


def test_attach_inferred_speakers_no_match_leaves_empty_list():
    char_dict = _build_char_dict()
    analysis = analyze_speaker_label("？？？", source=SOURCE_NAME_COMMAND)
    attach_inferred_speakers(analysis, char_dict)
    assert analysis.inferred_speakers == []


def test_attach_inferred_speakers_none_dict_is_noop():
    analysis = analyze_speaker_label("セイナ＆イヴ", source=SOURCE_NAME_COMMAND)
    attach_inferred_speakers(analysis, None)
    assert analysis.inferred_speakers == []


# ----------------------------------------------------------------
# to_dict
# ----------------------------------------------------------------


def test_to_dict_shape():
    analysis = analyze_speaker_label("セイナ＆イヴ", source=SOURCE_NAME_COMMAND)
    data = analysis.to_dict()
    assert data["rawLabel"] == "セイナ＆イヴ"
    assert data["source"] == SOURCE_NAME_COMMAND
    assert data["labelType"] == LABEL_TYPE_SPEAKER_GROUP
    assert data["components"] == ["セイナ", "イヴ"]
    assert data["modifier"] is None
    assert data["baseLabel"] is None
    assert data["inferredSpeakers"] == []
    assert data["resolutionStatus"] == RESOLUTION_STATUS_INFERRED
