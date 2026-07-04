"""
tests/parser/test_character_dictionary.py
agents/parser/character_dictionary.py のユニットテスト

すべて合成データ (CHAR_TEST_* 等) のみを使う。実データ由来の
sourceCharacterId・displayName・fixtureは一切含まない。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agents.parser.character_dictionary import (
    CHARACTER_ID_PATTERN,
    STATUS_CONFIRMED,
    STATUS_NAME_ONLY,
    CharacterDictionaryEntry,
    build_character_dictionary_coverage_report,
    build_character_review_packet,
    build_review_candidates,
    load_character_dictionary,
    resolve_character_by_name,
    resolve_character_by_source_id,
    validate_character_dictionary,
)


def _write_dictionary(tmp_path: Path, characters: list[dict]) -> Path:
    path = tmp_path / "characters.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"schemaVersion": "0.1", "characters": characters}, f)
    return path


# ----------------------------------------------------------------
# load_character_dictionary
# ----------------------------------------------------------------


def test_load_character_dictionary_basic(tmp_path):
    path = _write_dictionary(
        tmp_path,
        [
            {
                "sourceCharacterId": "9001",
                "characterId": "CHAR_TEST_A",
                "displayName": "Test Character A",
                "aliases": ["TCA"],
                "status": "confirmed",
                "notes": "synthetic test entry",
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

    entries = load_character_dictionary(path)
    assert len(entries) == 2

    a, b = entries
    assert a.source_character_id == "9001"
    assert a.character_id == "CHAR_TEST_A"
    assert a.display_name == "Test Character A"
    assert a.aliases == ["TCA"]
    assert a.status == STATUS_CONFIRMED
    assert a.notes == "synthetic test entry"

    assert b.source_character_id == "9002"
    assert b.character_id is None
    assert b.status == STATUS_NAME_ONLY


def test_load_character_dictionary_missing_file_returns_empty(tmp_path):
    entries = load_character_dictionary(tmp_path / "does_not_exist.yaml")
    assert entries == []


def test_load_character_dictionary_empty_characters_key(tmp_path):
    path = tmp_path / "characters.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"schemaVersion": "0.1"}, f)
    entries = load_character_dictionary(path)
    assert entries == []


# ----------------------------------------------------------------
# validate_character_dictionary
# ----------------------------------------------------------------


def test_validate_accepts_valid_entries():
    entries = [
        CharacterDictionaryEntry(
            source_character_id="9001",
            display_name="Test Character A",
            character_id="CHAR_TEST_A",
            status=STATUS_CONFIRMED,
        ),
        CharacterDictionaryEntry(
            source_character_id="9002",
            display_name="Test Character B",
            status=STATUS_NAME_ONLY,
        ),
    ]
    assert validate_character_dictionary(entries) == []


def test_validate_rejects_duplicate_source_character_id():
    entries = [
        CharacterDictionaryEntry(source_character_id="9001", display_name="A"),
        CharacterDictionaryEntry(source_character_id="9001", display_name="A2"),
    ]
    issues = validate_character_dictionary(entries)
    assert any("重複" in issue for issue in issues)


def test_validate_rejects_duplicate_character_id():
    entries = [
        CharacterDictionaryEntry(
            source_character_id="9001",
            display_name="A",
            character_id="CHAR_TEST_DUP",
            status=STATUS_CONFIRMED,
        ),
        CharacterDictionaryEntry(
            source_character_id="9002",
            display_name="B",
            character_id="CHAR_TEST_DUP",
            status=STATUS_CONFIRMED,
        ),
    ]
    issues = validate_character_dictionary(entries)
    assert any("characterId 'CHAR_TEST_DUP'" in issue for issue in issues)


def test_validate_rejects_invalid_character_id_format():
    entries = [
        CharacterDictionaryEntry(
            source_character_id="9001",
            display_name="A",
            character_id="not-a-valid-id",
            status=STATUS_CONFIRMED,
        )
    ]
    issues = validate_character_dictionary(entries)
    assert any("形式が不正" in issue for issue in issues)


def test_validate_rejects_confirmed_status_without_character_id():
    entries = [
        CharacterDictionaryEntry(
            source_character_id="9001", display_name="A", status=STATUS_CONFIRMED
        )
    ]
    issues = validate_character_dictionary(entries)
    assert any(
        "characterId" in issue and "設定されていません" in issue for issue in issues
    )


def test_validate_rejects_character_id_with_non_confirmed_status():
    entries = [
        CharacterDictionaryEntry(
            source_character_id="9001",
            display_name="A",
            character_id="CHAR_TEST_A",
            status=STATUS_NAME_ONLY,
        )
    ]
    issues = validate_character_dictionary(entries)
    assert any("status が" in issue for issue in issues)


def test_validate_rejects_unknown_status():
    entries = [
        CharacterDictionaryEntry(
            source_character_id="9001", display_name="A", status="totally_made_up"
        )
    ]
    issues = validate_character_dictionary(entries)
    assert any("未知のstatus" in issue for issue in issues)


def test_validate_rejects_empty_display_name():
    entries = [CharacterDictionaryEntry(source_character_id="9001", display_name="")]
    issues = validate_character_dictionary(entries)
    assert any("displayNameが空" in issue for issue in issues)


def test_validate_rejects_duplicate_alias_within_entry():
    entries = [
        CharacterDictionaryEntry(
            source_character_id="9001",
            display_name="A",
            aliases=["Ace", "Ace"],
        )
    ]
    issues = validate_character_dictionary(entries)
    assert any("aliasesに重複した値があります" in issue for issue in issues)


def test_validate_rejects_alias_shared_across_entries():
    entries = [
        CharacterDictionaryEntry(
            source_character_id="9001", display_name="A", aliases=["Shared"]
        ),
        CharacterDictionaryEntry(
            source_character_id="9002", display_name="B", aliases=["Shared"]
        ),
    ]
    issues = validate_character_dictionary(entries)
    assert any(
        "alias 'Shared'" in issue and "9001" in issue and "9002" in issue
        for issue in issues
    )


def test_validate_accepts_unique_aliases():
    entries = [
        CharacterDictionaryEntry(
            source_character_id="9001", display_name="A", aliases=["Ace"]
        ),
        CharacterDictionaryEntry(
            source_character_id="9002", display_name="B", aliases=["Bee"]
        ),
    ]
    assert validate_character_dictionary(entries) == []


def test_character_id_pattern_accepts_expected_format():
    assert CHARACTER_ID_PATTERN.match("CHAR_TEST_A")
    assert CHARACTER_ID_PATTERN.match("CHAR_RAIN")
    assert not CHARACTER_ID_PATTERN.match("char_test_a")
    assert not CHARACTER_ID_PATTERN.match("TEST_A")


# ----------------------------------------------------------------
# resolve_character_by_source_id / resolve_character_by_name
# ----------------------------------------------------------------


@pytest.fixture
def sample_entries():
    return [
        CharacterDictionaryEntry(
            source_character_id="9001",
            display_name="Test Character A",
            character_id="CHAR_TEST_A",
            aliases=["TCA", "テストA"],
            status=STATUS_CONFIRMED,
        ),
        CharacterDictionaryEntry(
            source_character_id="9002",
            display_name="Test Character B",
            status=STATUS_NAME_ONLY,
        ),
    ]


def test_resolve_character_by_source_id_found(sample_entries):
    entry = resolve_character_by_source_id(sample_entries, "9001")
    assert entry is not None
    assert entry.character_id == "CHAR_TEST_A"


def test_resolve_character_by_source_id_not_found(sample_entries):
    assert resolve_character_by_source_id(sample_entries, "9999") is None


def test_resolve_character_by_name_matches_display_name(sample_entries):
    entry = resolve_character_by_name(sample_entries, "Test Character B")
    assert entry is not None
    assert entry.source_character_id == "9002"


def test_resolve_character_by_name_matches_alias(sample_entries):
    entry = resolve_character_by_name(sample_entries, "テストA")
    assert entry is not None
    assert entry.source_character_id == "9001"


def test_resolve_character_by_name_no_match_returns_none(sample_entries):
    assert resolve_character_by_name(sample_entries, "Nobody") is None


# ----------------------------------------------------------------
# build_character_dictionary_coverage_report
# ----------------------------------------------------------------


def test_coverage_report_basic(sample_entries):
    observed = {"9001": 5, "9002": 3, "9999": 2, "8888": 1}
    report = build_character_dictionary_coverage_report(sample_entries, observed)

    assert report["observedCount"] == 4
    assert report["knownCount"] == 2
    assert report["unknownCount"] == 2
    assert report["coveragePercentage"] == 50.0

    top_ids = {item["sourceCharacterId"] for item in report["topUnknownIds"]}
    assert top_ids == {"9999", "8888"}
    # 出現回数の降順であること
    assert report["topUnknownIds"][0]["sourceCharacterId"] == "9999"


def test_coverage_report_distinguishes_confirmed_and_name_only(sample_entries):
    """9001はconfirmed、9002はname_onlyという sample_entries の前提のもと、
    知っている(known)側の内訳がconfirmed/name_onlyで分かれて出ることを
    確認する（confirmedとname_onlyでは意味が違うため、混同しないこと）。"""
    observed = {"9001": 5, "9002": 3, "9999": 2, "8888": 1}
    report = build_character_dictionary_coverage_report(sample_entries, observed)

    assert report["confirmedObservedCount"] == 1
    assert report["nameOnlyObservedCount"] == 1
    assert report["confirmedCoveragePercentage"] == 25.0
    assert report["nameOnlyCoveragePercentage"] == 25.0
    assert report["dictionaryTotalCount"] == 2
    assert report["dictionaryConfirmedCount"] == 1
    assert report["dictionaryNameOnlyCount"] == 1


def test_coverage_report_no_observed_ids_is_full_coverage(sample_entries):
    report = build_character_dictionary_coverage_report(sample_entries, {})
    assert report["observedCount"] == 0
    assert report["coveragePercentage"] == 100.0
    assert report["topUnknownIds"] == []


def test_coverage_report_top_unknown_capped_at_20(sample_entries):
    observed = {str(i): 1 for i in range(30)}
    report = build_character_dictionary_coverage_report(sample_entries, observed)
    assert len(report["topUnknownIds"]) == 20


# ----------------------------------------------------------------
# build_review_candidates
# ----------------------------------------------------------------


def test_build_review_candidates_lists_unknown_ids_only():
    observed = {"9001": 5, "9999": 2, "8888": 7}
    known_ids = {"9001"}
    candidates = build_review_candidates(observed, known_ids)

    ids = {c["sourceCharacterId"] for c in candidates}
    assert ids == {"9999", "8888"}
    # 出現回数の降順であること
    assert candidates[0]["sourceCharacterId"] == "8888"
    assert candidates[0]["observedCount"] == 7


def test_build_review_candidates_contains_no_real_data_content():
    """候補エントリはID・出現回数のみで、displayName等の実データ内容を
    一切含まないプレースホルダーのみで構成されること。"""
    candidates = build_review_candidates({"9999": 1}, known_ids=set())
    assert candidates == [
        {
            "sourceCharacterId": "9999",
            "observedCount": 1,
            "suggestedDisplayName": None,
            "confirmedCharacterId": None,
            "status": STATUS_NAME_ONLY,
            "reviewerNotes": None,
        }
    ]


def test_build_review_candidates_empty_when_all_known():
    assert build_review_candidates({"9001": 1}, known_ids={"9001"}) == []


# ----------------------------------------------------------------
# build_character_review_packet
# ----------------------------------------------------------------


@pytest.fixture
def review_packet_dictionary_entries():
    return [
        CharacterDictionaryEntry(
            source_character_id="9001",
            display_name="Test Character A",
            character_id="CHAR_TEST_A",
            status=STATUS_CONFIRMED,
        ),
        CharacterDictionaryEntry(
            source_character_id="9002",
            display_name="Test Character B",
            aliases=["TCB"],
            status=STATUS_NAME_ONLY,
        ),
    ]


@pytest.fixture
def review_packet_collection():
    return {
        "entities": {
            "characters": [
                {
                    "id": "CHAR_TEST_RESOLVED",
                    "status": "merged",
                    "canonicalId": "CHAR_TEST_A",
                    "displayName": "Test Character A",
                    "sourceCharacterIds": ["9001"],
                    "evidenceRefs": [
                        {"episodeId": "EP_TEST_001", "sourceDocumentId": "EP_TEST_001"}
                    ],
                },
                {
                    "id": "UNRESOLVED_CHAR_TEST_NAMEONLY",
                    "status": "unresolved",
                    "displayName": "Test Character B",
                    "sourceCharacterIds": ["9002"],
                    "evidenceRefs": [
                        {
                            "episodeId": "EP_TEST_001",
                            "sourceDocumentId": "EP_TEST_001",
                        },
                        {
                            "episodeId": "EP_TEST_002",
                            "sourceDocumentId": "EP_TEST_002",
                        },
                    ],
                },
                {
                    "id": "UNRESOLVED_CHAR_TEST_UNKNOWN",
                    "status": "unresolved",
                    "displayName": "Test Character Unknown",
                    "sourceCharacterIds": ["9999"],
                    "evidenceRefs": [
                        {"episodeId": "EP_TEST_001", "sourceDocumentId": "EP_TEST_001"}
                    ],
                },
                {
                    "id": "UNRESOLVED_CHAR_TEST_NO_SOURCE_ID",
                    "status": "unresolved",
                    "displayName": "Test Character No Source ID",
                    "sourceCharacterIds": [],
                    "evidenceRefs": [{"episodeId": "EP_TEST_001"}],
                },
            ]
        }
    }


def test_build_character_review_packet_excludes_confirmed_merged_entity(
    review_packet_collection, review_packet_dictionary_entries
):
    """辞書でconfirmed済み(9001)、かつentity自体もstatus: mergedの場合は
    再レビュー不要のため、packetに含めない。"""
    packet = build_character_review_packet(
        review_packet_collection, review_packet_dictionary_entries
    )
    source_ids = {entry["sourceCharacterId"] for entry in packet}
    assert "9001" not in source_ids


def test_build_character_review_packet_includes_name_only_with_dictionary_metadata(
    review_packet_collection, review_packet_dictionary_entries
):
    packet = build_character_review_packet(
        review_packet_collection, review_packet_dictionary_entries
    )
    entry = next(e for e in packet if e["sourceCharacterId"] == "9002")
    assert entry["existingDictionaryStatus"] == STATUS_NAME_ONLY
    assert entry["existingCharacterId"] is None
    assert entry["aliases"] == ["TCB"]
    assert entry["observedCount"] == 2
    assert entry["appearedEpisodeCount"] == 2
    assert entry["sourceDocumentCount"] == 2


def test_build_character_review_packet_includes_unknown_entity(
    review_packet_collection, review_packet_dictionary_entries
):
    packet = build_character_review_packet(
        review_packet_collection, review_packet_dictionary_entries
    )
    entry = next(e for e in packet if e["sourceCharacterId"] == "9999")
    assert entry["existingDictionaryStatus"] == "unknown"
    assert entry["existingCharacterId"] is None
    assert entry["aliases"] == []


def test_build_character_review_packet_skips_entities_without_source_character_id(
    review_packet_collection, review_packet_dictionary_entries
):
    packet = build_character_review_packet(
        review_packet_collection, review_packet_dictionary_entries
    )
    source_ids = {entry["sourceCharacterId"] for entry in packet}
    assert source_ids == {"9002", "9999"}


def test_build_character_review_packet_sorted_by_observed_count_desc(
    review_packet_collection, review_packet_dictionary_entries
):
    packet = build_character_review_packet(
        review_packet_collection, review_packet_dictionary_entries
    )
    assert [entry["sourceCharacterId"] for entry in packet] == ["9002", "9999"]


def test_build_character_review_packet_human_review_fields_initialized(
    review_packet_collection, review_packet_dictionary_entries
):
    """humanReviewStatus/humanConfirmedCharacterId/notesは、AI推測による
    埋め込みをせず常に空のプレースホルダーで初期化されることを確認する。"""
    packet = build_character_review_packet(
        review_packet_collection, review_packet_dictionary_entries
    )
    for entry in packet:
        assert entry["humanReviewStatus"] == "pending"
        assert entry["humanConfirmedCharacterId"] is None
        assert entry["notes"] == ""


def test_build_character_review_packet_does_not_include_raw_evidence_content(
    review_packet_collection, review_packet_dictionary_entries
):
    """packetの各エントリは既定のキー集合のみで構成され、evidenceRefsや
    textExcerpt等の生データをそのまま含まないことを確認する。"""
    packet = build_character_review_packet(
        review_packet_collection, review_packet_dictionary_entries
    )
    expected_keys = {
        "sourceCharacterId",
        "displayName",
        "existingDictionaryStatus",
        "existingCharacterId",
        "aliases",
        "observedCount",
        "appearedEpisodeCount",
        "sourceDocumentCount",
        "humanReviewStatus",
        "humanConfirmedCharacterId",
        "notes",
    }
    for entry in packet:
        assert set(entry.keys()) == expected_keys
