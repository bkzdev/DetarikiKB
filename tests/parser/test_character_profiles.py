"""
tests/parser/test_character_profiles.py
agents/parser/character_profiles.py のユニットテスト

すべて合成データ (CHAR_TEST_* 等) のみを使う。実キャラクター名・実
プロフィール本文・実自己紹介文は一切含まない。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agents.parser.character_dictionary import CharacterDictionaryEntry
from agents.parser.character_profiles import (
    STATUS_CONFIRMED,
    Birthday,
    CharacterProfile,
    ProfileHighlight,
    Reading,
    build_character_profile_index,
    get_character_profile,
    load_character_profiles,
    validate_character_profiles,
)


def _write_profiles(tmp_path: Path, profiles: list[dict]) -> Path:
    path = tmp_path / "character_profiles.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "schemaVersion": "0.1.0",
                "documentType": "character_profiles",
                "profiles": profiles,
            },
            f,
            allow_unicode=True,
        )
    return path


# ----------------------------------------------------------------
# load_character_profiles
# ----------------------------------------------------------------


def test_load_character_profiles_basic(tmp_path):
    path = _write_profiles(
        tmp_path,
        [
            {
                "characterId": "CHAR_TEST_A",
                "displayName": "Test Character A",
                "status": "confirmed",
                "reading": {"kana": "てすと", "romaji": "Test"},
                "affiliation": ["Test Team"],
                "heightCm": 150,
                "birthday": {"month": 1, "day": 1, "display": "1/1"},
                "bloodType": "A",
                "cv": "Test Voice Actor",
                "profileHighlight": {"label": "好きなこと", "value": "テスト"},
                "selfIntroduction": "テスト自己紹介。",
                "source": {
                    "sourceType": "official_profile",
                    "label": "Test source",
                    "referenceId": None,
                    "notes": None,
                },
                "notes": "test note",
            }
        ],
    )
    profiles = load_character_profiles(path)
    assert len(profiles) == 1
    p = profiles[0]
    assert p.character_id == "CHAR_TEST_A"
    assert p.display_name == "Test Character A"
    assert p.status == "confirmed"
    assert p.reading == Reading(kana="てすと", romaji="Test")
    assert p.affiliation == ["Test Team"]
    assert p.height_cm == 150
    assert p.birthday == Birthday(month=1, day=1, display="1/1")
    assert p.blood_type == "A"
    assert p.cv == "Test Voice Actor"
    assert p.profile_highlight == ProfileHighlight(label="好きなこと", value="テスト")
    assert p.self_introduction == "テスト自己紹介。"
    assert p.source.source_type == "official_profile"


def test_load_character_profiles_missing_file_returns_empty(tmp_path):
    assert load_character_profiles(tmp_path / "does_not_exist.yaml") == []


def test_load_character_profiles_empty_profiles_key(tmp_path):
    path = tmp_path / "character_profiles.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"schemaVersion": "0.1.0", "documentType": "character_profiles"}, f
        )
    assert load_character_profiles(path) == []


def test_load_character_profiles_optional_fields_default_to_none(tmp_path):
    path = _write_profiles(
        tmp_path,
        [
            {
                "characterId": "CHAR_TEST_B",
                "displayName": "Test Character B",
                "status": "draft",
            }
        ],
    )
    profiles = load_character_profiles(path)
    p = profiles[0]
    assert p.reading is None
    assert p.affiliation == []
    assert p.height_cm is None
    assert p.birthday is None
    assert p.blood_type is None
    assert p.cv is None
    assert p.profile_highlight is None
    assert p.self_introduction is None
    assert p.source is None
    assert p.notes is None


# ----------------------------------------------------------------
# validate_character_profiles
# ----------------------------------------------------------------


def _profile(**overrides) -> CharacterProfile:
    defaults = {
        "character_id": "CHAR_TEST_A",
        "display_name": "Test Character A",
        "status": STATUS_CONFIRMED,
    }
    defaults.update(overrides)
    return CharacterProfile(**defaults)


def test_validate_accepts_minimal_valid_profile():
    assert validate_character_profiles([_profile()]) == []


def test_validate_rejects_invalid_character_id_pattern():
    issues = validate_character_profiles([_profile(character_id="not_char_prefixed")])
    assert any("形式が不正" in issue for issue in issues)


def test_validate_rejects_empty_character_id():
    issues = validate_character_profiles([_profile(character_id="")])
    assert any("characterIdが空です" in issue for issue in issues)


def test_validate_rejects_empty_display_name():
    issues = validate_character_profiles([_profile(display_name="")])
    assert any("displayNameが空です" in issue for issue in issues)


def test_validate_rejects_unknown_status():
    issues = validate_character_profiles([_profile(status="unknown_status")])
    assert any("未知のstatus" in issue for issue in issues)


def test_validate_rejects_duplicate_character_id():
    issues = validate_character_profiles([_profile(), _profile()])
    assert any("重複しています" in issue for issue in issues)


def test_validate_rejects_non_integer_height_cm():
    profile = _profile()
    profile.height_cm = "150cm"  # 意図的に不正な型
    issues = validate_character_profiles([profile])
    assert any("heightCmは整数である必要があります" in issue for issue in issues)


def test_validate_accepts_valid_height_cm():
    profile = _profile(height_cm=150)
    assert validate_character_profiles([profile]) == []


def test_validate_rejects_birthday_month_out_of_range():
    profile = _profile(birthday=Birthday(month=13, day=1))
    issues = validate_character_profiles([profile])
    assert any("birthday.monthが範囲外です" in issue for issue in issues)


def test_validate_rejects_birthday_day_out_of_range():
    profile = _profile(birthday=Birthday(month=1, day=32))
    issues = validate_character_profiles([profile])
    assert any("birthday.dayが範囲外です" in issue for issue in issues)


def test_validate_accepts_valid_birthday():
    profile = _profile(birthday=Birthday(month=4, day=23, display="4/23"))
    assert validate_character_profiles([profile]) == []


def test_validate_rejects_profile_highlight_empty_label_or_value():
    profile = _profile(profile_highlight=ProfileHighlight(label="", value="something"))
    issues = validate_character_profiles([profile])
    assert any(
        "profileHighlightのlabel/valueは空にできません" in issue for issue in issues
    )


def test_validate_rejects_profile_highlight_value_too_long():
    profile = _profile(
        profile_highlight=ProfileHighlight(label="好きなこと", value="あ" * 201)
    )
    issues = validate_character_profiles([profile])
    assert any("profileHighlight.valueが" in issue for issue in issues)


def test_validate_rejects_self_introduction_over_500_chars():
    profile = _profile(self_introduction="あ" * 501)
    issues = validate_character_profiles([profile])
    assert any("selfIntroductionが500文字を超えています" in issue for issue in issues)


def test_validate_accepts_self_introduction_multiline_under_limit():
    """自己紹介文は複数行を許可し、500字以内であれば問題ないことを確認する。"""
    multiline = "1行目です。\n2行目です。\n3行目です。"
    profile = _profile(self_introduction=multiline)
    assert validate_character_profiles([profile]) == []


def test_validate_empty_profiles_list_is_valid():
    assert validate_character_profiles([]) == []


# ----------------------------------------------------------------
# validate_character_profiles + characters.yaml (character_dictionary)整合性
# ----------------------------------------------------------------


@pytest.fixture
def sample_character_dictionary():
    return [
        CharacterDictionaryEntry(
            source_character_id="9001",
            display_name="Test Character A",
            character_id="CHAR_TEST_A",
            status="confirmed",
        ),
        CharacterDictionaryEntry(
            source_character_id="9002",
            display_name="Test Character B",
            status="name_only",
        ),
    ]


def test_validate_accepts_profile_for_confirmed_character_id(
    sample_character_dictionary,
):
    issues = validate_character_profiles([_profile()], sample_character_dictionary)
    assert issues == []


def test_validate_rejects_profile_for_missing_character_id(sample_character_dictionary):
    profile = _profile(character_id="CHAR_TEST_UNKNOWN")
    issues = validate_character_profiles([profile], sample_character_dictionary)
    assert any(
        "knowledge/dictionaries/characters.yamlに存在しません" in issue
        for issue in issues
    )


def test_validate_rejects_profile_for_name_only_character_id(
    sample_character_dictionary,
):
    """characters.yaml上でstatus: name_onlyのcharacterIdにプロフィールを
    紐づけようとした場合、confirmed済みではないことをエラーにする
    (Character_Profile_Dictionary_Design.md §4)。"""
    profile = _profile(character_id="CHAR_TEST_B")
    # CHAR_TEST_Bはsample_character_dictionaryのstatus: name_onlyエントリには
    # characterIdが無い (null) ため、直接characterIdでの検索は失敗する。
    # ここではname_onlyだがcharacterIdが設定されているケースを別途用意する。
    dictionary_with_name_only_character_id = [
        CharacterDictionaryEntry(
            source_character_id="9002",
            display_name="Test Character B",
            character_id="CHAR_TEST_B",
            status="name_only",
        ),
    ]
    issues = validate_character_profiles(
        [profile], dictionary_with_name_only_character_id
    )
    assert any("confirmedではありません" in issue for issue in issues)


# ----------------------------------------------------------------
# build_character_profile_index / get_character_profile
# ----------------------------------------------------------------


def test_build_character_profile_index_and_get():
    profiles = [_profile(), _profile(character_id="CHAR_TEST_C")]
    index = build_character_profile_index(profiles)
    assert set(index.keys()) == {"CHAR_TEST_A", "CHAR_TEST_C"}
    assert get_character_profile(index, "CHAR_TEST_A") is not None
    assert get_character_profile(index, "CHAR_TEST_NOT_FOUND") is None
