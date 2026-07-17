"""
tests/parser/test_resolver.py
SpeakerResolver のユニットテスト
"""

import pytest

from agents.parser.resolver import (
    CharacterDictionary,
    SpeakerResolver,
)


@pytest.fixture
def char_dict():
    cd = CharacterDictionary()
    # テスト用の直接モック
    cd._name_map = {"26": "レイン", "29": "レイヴェル", "1": "赤城陽菜"}
    cd._id_map = {"26": "CHAR_RAIN", "29": "CHAR_REIVEL", "1": "CHAR_AKAGI_HINA"}
    return cd


def test_resolve_known_character(char_dict):
    resolver = SpeakerResolver(char_dict)
    speaker = resolver.assign_character(slot="0", source_character_id="26")

    assert speaker.is_resolved is True
    assert speaker.speaker_name == "レイン"
    assert speaker.speaker_id == "CHAR_RAIN"

    resolved = resolver.resolve_slot("0")
    assert resolved.speaker_name == "レイン"


def test_resolve_unknown_character(char_dict):
    resolver = SpeakerResolver(char_dict)
    speaker = resolver.assign_character(slot="1", source_character_id="999")

    assert speaker.is_resolved is False
    assert speaker.speaker_id is None
    assert "999" in speaker.speaker_name

    assert "999" in resolver.unresolved_character_ids


def test_assign_variable_num(char_dict):
    resolver = SpeakerResolver(char_dict)
    # $num0 = 26 -> slot="0" になるはず
    speaker = resolver.assign_variable(
        variable_name="$num0", source_character_id="26", num_index=0
    )

    assert speaker.is_resolved is True
    assert resolver.resolve_slot("0").speaker_name == "レイン"


def test_assign_variable_value(char_dict):
    resolver = SpeakerResolver(char_dict)
    # まず $num0 = 26 があるとする
    resolver.assign_variable(
        variable_name="$num0", source_character_id="26", num_index=0
    )

    # $value1 = 29 -> max_num_index(=0) + 1 + 1 = slot "2"
    resolver.assign_variable(
        variable_name="$value1", source_character_id="29", value_index=1
    )

    assert resolver.resolve_slot("2").speaker_name == "レイヴェル"


def test_scenario_cos_load(char_dict):
    resolver = SpeakerResolver(char_dict)
    # まず変数にセットする
    # (slotには直接割り当てない想定だが内部的に$numXとして処理される)
    resolver.assign_variable(
        variable_name="$num0", source_character_id="26", num_index=0
    )

    # @ScenarioCosLoad 5 $num0 -> slot "5" にレイン
    speaker = resolver.assign_from_variable(slot="5", variable_name="$num0")
    assert speaker.is_resolved is True
    assert resolver.resolve_slot("5").speaker_name == "レイン"


# ----------------------------------------------------------------
# 消費文脈ベースの未登録キャラクターID分類
# (feature/resolver-consumption-context-report、
# scripts/check_script_compatibility.pyの#141と対称化)
# ----------------------------------------------------------------


def test_consumption_speaker_bucket_via_num_assignment_and_resolve_slot(char_dict):
    """$numX代入だけではunresolved_character_idsへ入らず、その後
    resolve_slot (実際の@ChTalk等の話者消費に相当) されて初めて
    unresolved_character_idsへ入ること。"""
    resolver = SpeakerResolver(char_dict)
    resolver.assign_variable(
        variable_name="$num0", source_character_id="555", num_index=0
    )
    assert "555" not in resolver.unresolved_character_ids
    assert "555" in resolver.non_speaker_numeric_assignment_ids

    resolver.resolve_slot("0")

    assert "555" in resolver.unresolved_character_ids
    assert "555" not in resolver.non_speaker_numeric_assignment_ids


def test_consumption_non_speaker_bucket_when_never_resolved(char_dict):
    """$numX代入のみで一度もresolve_slotされない (costume/mo/fa等の非話者
    引数としてのみ消費される場合・完全未消費の場合の両方を含む) 未登録IDは
    non_speaker_numeric_assignment_idsへ入り、unresolved_character_idsには
    入らないこと。"""
    resolver = SpeakerResolver(char_dict)
    resolver.assign_variable(
        variable_name="$num1", source_character_id="666", num_index=1
    )

    assert "666" not in resolver.unresolved_character_ids
    assert "666" in resolver.non_speaker_numeric_assignment_ids


def test_consumption_registered_id_never_recorded_in_either_bucket(char_dict):
    """登録済みIDは消費有無に関わらずどちらのバケットにも入らないこと
    (無回帰)。"""
    resolver = SpeakerResolver(char_dict)
    resolver.assign_variable(
        variable_name="$num0", source_character_id="26", num_index=0
    )
    resolver.resolve_slot("0")

    assert "26" not in resolver.unresolved_character_ids
    assert "26" not in resolver.non_speaker_numeric_assignment_ids


def test_consumption_slot_rebinding_does_not_misclassify_overwritten_id(char_dict):
    """同じスロットへ2回代入した後にresolve_slotされた場合、最終的に
    バインドされているIDのみが話者消費ありと分類され、上書きされた以前の
    IDは非話者バケットに残ったままになること (スロット再束縛時の誤分類
    回帰防止)。"""
    resolver = SpeakerResolver(char_dict)
    resolver.assign_variable(
        variable_name="$num0", source_character_id="111", num_index=0
    )
    resolver.assign_variable(
        variable_name="$num0", source_character_id="222", num_index=0
    )
    resolver.resolve_slot("0")

    assert "222" in resolver.unresolved_character_ids
    assert "111" not in resolver.unresolved_character_ids
    assert "111" in resolver.non_speaker_numeric_assignment_ids
    assert "222" not in resolver.non_speaker_numeric_assignment_ids


def test_consumption_direct_scenario_cos_assignment_is_immediate_speaker(char_dict):
    """@ScenarioCos直接指定 (assign_character) は、resolve_slot呼び出しを
    待たずに即時話者消費ありと分類される (checker側`_apply_scenario_cos`
    のdirect-id分岐と同じ意味論)。"""
    resolver = SpeakerResolver(char_dict)
    resolver.assign_character(slot="0", source_character_id="777")

    assert "777" in resolver.unresolved_character_ids
    assert "777" not in resolver.non_speaker_numeric_assignment_ids


def test_consumption_scenario_cos_load_promotes_existing_occurrence_to_speaker(
    char_dict,
):
    """@ScenarioCosLoad (assign_from_variable) は、対応する変数が既に
    $numX等で未登録IDとして代入済みの場合、そのIDを即時話者消費ありへ
    昇格させる (checker側`_apply_scenario_cos_load`と同じ意味論)。"""
    resolver = SpeakerResolver(char_dict)
    resolver.assign_variable(
        variable_name="$num0", source_character_id="888", num_index=0
    )
    assert "888" in resolver.non_speaker_numeric_assignment_ids

    resolver.assign_from_variable(slot="5", variable_name="$num0")

    assert "888" in resolver.unresolved_character_ids
    assert "888" not in resolver.non_speaker_numeric_assignment_ids


def test_forced_name(char_dict):
    resolver = SpeakerResolver(char_dict)
    resolver.set_forced_name("謎の声")

    assert resolver.has_forced_name() is True
    name = resolver.consume_forced_name()
    assert name == "謎の声"
    assert resolver.has_forced_name() is False


def test_resolve_from_command_name():
    resolver = SpeakerResolver(CharacterDictionary())
    speaker = resolver.resolve_from_command_name("美海＆恵茉", slot="0")

    assert speaker.is_resolved is False
    assert speaker.speaker_name == "美海＆恵茉"
    assert speaker.slot == "0"


# ----------------------------------------------------------------
# CharacterDictionary.load_from_dictionary_yaml / load
# (knowledge/dictionaries/characters.yaml 相当の人手管理辞書、合成データのみ)
# ----------------------------------------------------------------


def _write_yaml_dictionary(tmp_path, characters):
    import yaml

    path = tmp_path / "characters.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"schemaVersion": "0.1", "characters": characters}, f)
    return path


def test_load_from_dictionary_yaml_populates_name_and_id_for_confirmed(tmp_path):
    path = _write_yaml_dictionary(
        tmp_path,
        [
            {
                "sourceCharacterId": "9001",
                "characterId": "CHAR_TEST_A",
                "displayName": "Test Character A",
                "aliases": [],
                "status": "confirmed",
            }
        ],
    )
    cd = CharacterDictionary()
    cd.load_from_dictionary_yaml(path)

    assert cd.get_name("9001") == "Test Character A"
    assert cd.get_speaker_id("9001") == "CHAR_TEST_A"
    assert cd.is_known("9001") is True


def test_load_from_dictionary_yaml_name_only_has_no_speaker_id(tmp_path):
    """characterId未設定 (status: name_only) のエントリは、表示名は
    分かるがspeakerId (canonical ID) は設定されない。名前一致だけで
    resolvedにしない方針を辞書ロード経路でも維持する。"""
    path = _write_yaml_dictionary(
        tmp_path,
        [
            {
                "sourceCharacterId": "9002",
                "characterId": None,
                "displayName": "Test Character B",
                "aliases": [],
                "status": "name_only",
            }
        ],
    )
    cd = CharacterDictionary()
    cd.load_from_dictionary_yaml(path)

    assert cd.get_name("9002") == "Test Character B"
    assert cd.get_speaker_id("9002") is None


def test_load_from_dictionary_yaml_end_to_end_resolution(tmp_path):
    """confirmedエントリはSpeakerResolver経由でis_resolved=Trueかつ
    speaker_idが設定され、name_onlyエントリはspeaker_idがNoneのまま
    (is_resolvedはTrueだが構造化canonical IDは無い) になることを確認する。"""
    path = _write_yaml_dictionary(
        tmp_path,
        [
            {
                "sourceCharacterId": "9001",
                "characterId": "CHAR_TEST_A",
                "displayName": "Test Character A",
                "aliases": [],
                "status": "confirmed",
            },
            {
                "sourceCharacterId": "9002",
                "characterId": None,
                "displayName": "Test Character B",
                "aliases": [],
                "status": "name_only",
            },
        ],
    )
    cd = CharacterDictionary()
    cd.load_from_dictionary_yaml(path)
    resolver = SpeakerResolver(cd)

    confirmed = resolver.assign_character(slot="0", source_character_id="9001")
    assert confirmed.is_resolved is True
    assert confirmed.speaker_id == "CHAR_TEST_A"

    name_only = resolver.assign_character(slot="1", source_character_id="9002")
    assert name_only.is_resolved is True
    assert name_only.speaker_id is None

    unknown = resolver.assign_character(slot="2", source_character_id="9999")
    assert unknown.is_resolved is False
    assert "9999" in resolver.unresolved_character_ids


def test_load_dispatches_by_extension_yaml(tmp_path):
    path = _write_yaml_dictionary(
        tmp_path,
        [
            {
                "sourceCharacterId": "9001",
                "characterId": "CHAR_TEST_A",
                "displayName": "Test Character A",
                "aliases": [],
                "status": "confirmed",
            }
        ],
    )
    cd = CharacterDictionary()
    cd.load(path)
    assert cd.get_speaker_id("9001") == "CHAR_TEST_A"


def test_load_dispatches_by_extension_json(tmp_path):
    import json

    path = tmp_path / "characters.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"9001": "Test Character A"}, f)

    cd = CharacterDictionary()
    cd.load(path)
    assert cd.get_name("9001") == "Test Character A"
    # レガシーJSON形式はcharacterId (canonical ID) を持たない
    assert cd.get_speaker_id("9001") is None
