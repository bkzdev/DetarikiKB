"""
tests/parser/test_character_profile_wiki_import.py
agents/parser/character_profile_wiki_import.py のユニットテスト

すべて合成データ (CHAR_TEST_* 等) のみを使う。実キャラクター名・実
プロフィール値・実Wiki本文は一切含まない。
"""

from __future__ import annotations

from agents.parser.character_dictionary import CharacterDictionaryEntry
from agents.parser.character_profile_wiki_import import (
    build_candidate_document,
    build_profile_from_row,
    extract_tables,
    find_member_table,
    match_candidates,
    normalize_header,
    parse_affiliation,
    parse_birthday,
    parse_height_cm,
    parse_profile_highlight,
    parse_reading,
    rows_to_dicts,
)

_SYNTHETIC_TABLE_HTML = """
<html><body>
<table>
<tr><th>キャラ名</th><th>よみがな</th><th>所属</th><th>身長(cm)</th>
<th>誕生日</th><th>血液型</th><th>特記事項</th><th>CV</th><th>実装日</th></tr>
<tr><td>Test Character A</td><td>てすとえー</td><td>Test Team</td>
<td>150cm</td><td>4/23</td><td>A</td><td>【好きなこと】テスト</td>
<td>Test Voice Actor</td><td>2026/01/01</td></tr>
<tr><td>Test Character B</td><td>てすとびー</td><td>Test Team</td>
<td>160</td><td>5/10</td><td>B</td><td>特になし</td><td></td>
<td>2026/01/02</td></tr>
</table>
</body></html>
"""


# ----------------------------------------------------------------
# extract_tables / find_member_table / rows_to_dicts
# ----------------------------------------------------------------


def test_extract_tables_finds_single_table():
    tables = extract_tables(_SYNTHETIC_TABLE_HTML)
    assert len(tables) == 1
    assert len(tables[0]) == 3  # header + 2 data rows


def test_find_member_table_selects_table_with_recognized_headers():
    tables = extract_tables(_SYNTHETIC_TABLE_HTML)
    table = find_member_table(tables)
    assert table is not None
    assert table[0][0] == "キャラ名"


def test_find_member_table_returns_none_when_no_recognized_headers():
    html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
    tables = extract_tables(html)
    assert find_member_table(tables) is None


def test_rows_to_dicts_maps_known_headers_and_ignores_unknown():
    tables = extract_tables(_SYNTHETIC_TABLE_HTML)
    table = find_member_table(tables)
    rows = rows_to_dicts(table)
    assert len(rows) == 2
    assert rows[0]["displayName"] == "Test Character A"
    assert rows[0]["kana"] == "てすとえー"
    # 「実装日」列は対応が無いため無視される
    assert "実装日" not in rows[0]
    assert "unknown_key" not in rows[0]


def test_normalize_header_returns_none_for_unknown_header():
    assert normalize_header("実装日") is None
    assert normalize_header("キャラ名") == "displayName"


# ----------------------------------------------------------------
# フィールドパーサー
# ----------------------------------------------------------------


def test_parse_height_cm_with_unit():
    assert parse_height_cm("150cm") == 150


def test_parse_height_cm_without_unit():
    assert parse_height_cm("160") == 160


def test_parse_height_cm_empty_returns_none():
    assert parse_height_cm("") is None
    assert parse_height_cm(None) is None


def test_parse_birthday_valid():
    assert parse_birthday("4/23") == {"month": 4, "day": 23, "display": "4/23"}


def test_parse_birthday_zero_padded():
    result = parse_birthday("04/23")
    assert result["month"] == 4
    assert result["day"] == 23


def test_parse_birthday_invalid_format_returns_none():
    assert parse_birthday("not a date") is None


def test_parse_birthday_out_of_range_returns_none():
    assert parse_birthday("13/40") is None


def test_parse_birthday_empty_returns_none():
    assert parse_birthday("") is None
    assert parse_birthday(None) is None


def test_parse_profile_highlight_with_label():
    result = parse_profile_highlight("【好きなこと】テストデータ")
    assert result == {"label": "好きなこと", "value": "テストデータ"}


def test_parse_profile_highlight_without_label_uses_default():
    result = parse_profile_highlight("特になし")
    assert result == {"label": "特記事項", "value": "特になし"}


def test_parse_profile_highlight_empty_returns_none():
    assert parse_profile_highlight("") is None
    assert parse_profile_highlight(None) is None


def test_parse_reading_valid():
    assert parse_reading("てすと") == {"kana": "てすと", "romaji": None}


def test_parse_reading_empty_returns_none():
    assert parse_reading("") is None
    assert parse_reading(None) is None


def test_parse_affiliation_valid():
    assert parse_affiliation("Test Team") == ["Test Team"]


def test_parse_affiliation_empty_returns_empty_list():
    assert parse_affiliation("") == []
    assert parse_affiliation(None) == []


# ----------------------------------------------------------------
# build_profile_from_row
# ----------------------------------------------------------------


def test_build_profile_from_row_self_introduction_is_always_none():
    row = {"displayName": "Test Character A", "kana": "てすと"}
    profile = build_profile_from_row(row, source_label="Test source")
    assert profile["selfIntroduction"] is None


def test_build_profile_from_row_source_reflects_label():
    row = {"displayName": "Test Character A"}
    profile = build_profile_from_row(row, source_label="Test source label")
    assert profile["source"]["sourceType"] == "wiki_member_table"
    assert profile["source"]["label"] == "Test source label"


def test_build_profile_from_row_status_is_draft():
    row = {"displayName": "Test Character A"}
    profile = build_profile_from_row(row, source_label="Test source")
    assert profile["status"] == "draft"


# ----------------------------------------------------------------
# match_candidates
# ----------------------------------------------------------------


def _dictionary():
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


def test_match_candidates_matches_confirmed_display_name():
    rows = [{"displayName": "Test Character A"}]
    candidates = match_candidates(rows, _dictionary(), source_label="Test source")
    assert candidates[0]["matchStatus"] == "matched"
    assert candidates[0]["characterId"] == "CHAR_TEST_A"
    assert "profile" in candidates[0]


def test_match_candidates_does_not_match_name_only():
    """name_onlyのキャラクターはdisplayNameが完全一致してもmatchedに
    しないことを確認する (confirmed済みcharacterIdにのみ紐づける方針)。"""
    rows = [{"displayName": "Test Character B"}]
    candidates = match_candidates(rows, _dictionary(), source_label="Test source")
    assert candidates[0]["matchStatus"] == "unmatched"
    assert candidates[0]["characterId"] is None


def test_match_candidates_unknown_character_is_unmatched():
    rows = [{"displayName": "Test Character Unknown"}]
    candidates = match_candidates(rows, _dictionary(), source_label="Test source")
    assert candidates[0]["matchStatus"] == "unmatched"
    assert "reason" in candidates[0]


def test_match_candidates_does_not_generate_character_id():
    """unmatchedエントリにcharacterIdが自動生成されないことを確認する。"""
    rows = [{"displayName": "Test Character Unknown"}]
    candidates = match_candidates(rows, _dictionary(), source_label="Test source")
    assert candidates[0]["characterId"] is None


def test_match_candidates_skips_rows_without_display_name():
    rows = [{"displayName": ""}, {"displayName": "Test Character A"}]
    candidates = match_candidates(rows, _dictionary(), source_label="Test source")
    assert len(candidates) == 1


# ----------------------------------------------------------------
# build_candidate_document
# ----------------------------------------------------------------


def test_build_candidate_document_structure():
    candidates = [{"matchStatus": "unmatched", "characterId": None}]
    document = build_candidate_document(
        candidates,
        source_url="https://example.invalid/test",
        fetched_at="2026-01-01T00:00:00+00:00",
    )
    assert document["schemaVersion"] == "0.1.0"
    assert document["documentType"] == "character_profile_import_candidates"
    assert document["source"]["sourceUrl"] == "https://example.invalid/test"
    assert document["candidates"] == candidates
