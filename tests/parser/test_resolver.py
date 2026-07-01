"""
tests/parser/test_resolver.py
SpeakerResolver のユニットテスト
"""

import pytest
from agents.parser.resolver import (
    CharacterDictionary,
    Speaker,
    SpeakerResolver,
)

@pytest.fixture
def char_dict():
    cd = CharacterDictionary()
    # テスト用の直接モック
    cd._name_map = {
        "26": "レイン",
        "29": "レイヴェル",
        "1": "赤城陽菜"
    }
    cd._id_map = {
        "26": "CHAR_RAIN",
        "29": "CHAR_REIVEL",
        "1": "CHAR_AKAGI_HINA"
    }
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
        variable_name="$num0",
        source_character_id="26",
        num_index=0
    )
    
    assert speaker.is_resolved is True
    assert resolver.resolve_slot("0").speaker_name == "レイン"

def test_assign_variable_value(char_dict):
    resolver = SpeakerResolver(char_dict)
    # まず $num0 = 26 があるとする
    resolver.assign_variable(
        variable_name="$num0",
        source_character_id="26",
        num_index=0
    )
    
    # $value1 = 29 -> max_num_index(=0) + 1 + 1 = slot "2"
    speaker = resolver.assign_variable(
        variable_name="$value1",
        source_character_id="29",
        value_index=1
    )
    
    assert resolver.resolve_slot("2").speaker_name == "レイヴェル"

def test_scenario_cos_load(char_dict):
    resolver = SpeakerResolver(char_dict)
    # まず変数にセットする (slotには直接割り当てない想定だか内部的に$numXとして処理される)
    resolver.assign_variable(
        variable_name="$num0",
        source_character_id="26",
        num_index=0
    )
    
    # @ScenarioCosLoad 5 $num0 -> slot "5" にレイン
    speaker = resolver.assign_from_variable(slot="5", variable_name="$num0")
    assert speaker.is_resolved is True
    assert resolver.resolve_slot("5").speaker_name == "レイン"

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
