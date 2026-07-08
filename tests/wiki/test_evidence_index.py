"""
tests/wiki/test_evidence_index.py
agents/wiki_generator/evidence_index.py のユニットテスト。

すべて合成データ (EVT_TEST_* 等) のみを使う。実イベント名・実キャラ名・
実あらすじ・実セリフは一切含まない。renderer (agents/wiki_generator/
renderer.py) 統合そのもののテストはtests/wiki/test_wiki_renderer.pyで
行う。ここではloader/validator/lookup系helperのみを対象とする。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agents.wiki_generator.evidence_index import (
    EvidenceIndexCollection,
    EvidenceIndexDocument,
    EvidenceIndexEntry,
    EvidenceIndexLookup,
    RelatedEntity,
    Speaker,
    Visibility,
    build_evidence_id_index,
    build_evidence_index_lookup,
    group_entries_by_episode,
    group_entries_by_public_episode,
    group_entries_by_public_story,
    group_entries_by_story,
    load_evidence_index,
    load_evidence_indexes,
    parse_evidence_index_document,
    resolve_group_public_story_id,
    validate_evidence_index_collection,
    validate_evidence_index_document,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "evidence_index"


def _write_document(tmp_path: Path, filename: str, data: dict) -> Path:
    path = tmp_path / filename
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)
    return path


def _minimal_raw_document(**overrides) -> dict:
    data = {
        "evidenceIndexVersion": 1,
        "generatedFrom": None,
        "entries": [],
        "notes": None,
    }
    data.update(overrides)
    return data


def _raw_entry(**overrides) -> dict:
    entry = {
        "evidenceId": "EVT_TEST_A_E01_DLG0001",
        "evidenceType": "dialogue",
        "storyId": "EVT_TEST_A",
        "publicStoryId": None,
        "episodeId": "EVT_TEST_A_E01",
        "publicEpisodeId": None,
        "publicEvidenceId": None,
        "sceneId": None,
        "blockId": None,
        "speaker": None,
        "relatedEntities": [],
        "referencedBy": None,
        "visibility": {"public": True, "rawTextIncluded": False},
        "notes": None,
    }
    entry.update(overrides)
    return entry


# ----------------------------------------------------------------
# load_evidence_index / load_evidence_indexes
# ----------------------------------------------------------------


def test_load_evidence_index_basic(tmp_path):
    path = _write_document(
        tmp_path,
        "EVT_TEST_A.yaml",
        _minimal_raw_document(entries=[_raw_entry()]),
    )
    document = load_evidence_index(path)
    assert document is not None
    assert len(document.entries) == 1
    assert document.entries[0].evidence_id == "EVT_TEST_A_E01_DLG0001"


def test_load_evidence_index_reads_public_evidence_id(tmp_path):
    path = _write_document(
        tmp_path,
        "EVT_TEST_A.yaml",
        _minimal_raw_document(
            entries=[_raw_entry(publicEvidenceId="EVT_TEST_PUBLIC_A_E01_DLG0001")]
        ),
    )
    document = load_evidence_index(path)
    assert document is not None
    assert document.entries[0].public_evidence_id == "EVT_TEST_PUBLIC_A_E01_DLG0001"


def test_load_evidence_index_public_evidence_id_defaults_to_none(tmp_path):
    path = _write_document(
        tmp_path,
        "EVT_TEST_A.yaml",
        _minimal_raw_document(entries=[_raw_entry()]),
    )
    document = load_evidence_index(path)
    assert document is not None
    assert document.entries[0].public_evidence_id is None


def test_load_evidence_index_missing_file_returns_none(tmp_path):
    assert load_evidence_index(tmp_path / "does_not_exist.yaml") is None


def test_load_evidence_index_empty_file_returns_none(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert load_evidence_index(path) is None


def test_load_evidence_indexes_from_fixtures_directory():
    collection = load_evidence_indexes(FIXTURES_DIR)
    story_ids = {
        entry.story_id for doc in collection.documents for entry in doc.entries
    }
    assert "EVT_TEST_EVIDENCE_ONE" in story_ids
    assert "EVT_TEST_EVIDENCE_TWO" in story_ids
    assert "EVT_TEST_EVIDENCE_THREE" in story_ids
    # 非再帰的走査のため、invalid_examples/配下は含まれない
    assert "EVT_TEST_EVIDENCE_BAD_TEXT" not in story_ids
    assert "EVT_TEST_EVIDENCE_DUP" not in story_ids


def test_load_evidence_indexes_missing_directory_returns_empty(tmp_path):
    collection = load_evidence_indexes(tmp_path / "does_not_exist")
    assert collection.documents == []


# ----------------------------------------------------------------
# build_evidence_id_index / group_entries_by_*
# ----------------------------------------------------------------


def test_build_evidence_id_index():
    collection = load_evidence_indexes(FIXTURES_DIR)
    index = build_evidence_id_index(collection)
    assert "EVT_TEST_EVIDENCE_ONE_E01_DLG0001" in index
    assert (
        index["EVT_TEST_EVIDENCE_ONE_E01_DLG0001"].evidence_id
        == "EVT_TEST_EVIDENCE_ONE_E01_DLG0001"
    )


def test_group_entries_by_story():
    collection = load_evidence_indexes(FIXTURES_DIR)
    groups = group_entries_by_story(collection)
    assert "EVT_TEST_EVIDENCE_ONE" in groups
    assert len(groups["EVT_TEST_EVIDENCE_ONE"]) == 4


def test_group_entries_by_public_story_only_includes_entries_with_public_id():
    collection = load_evidence_indexes(FIXTURES_DIR)
    groups = group_entries_by_public_story(collection)
    assert "EVT_TEST_PUBLIC_EVIDENCE_001" in groups
    assert "EVT_TEST_EVIDENCE_TWO" not in groups


def test_group_entries_by_episode():
    collection = load_evidence_indexes(FIXTURES_DIR)
    groups = group_entries_by_episode(collection)
    assert "EVT_TEST_EVIDENCE_ONE_E01" in groups
    assert len(groups["EVT_TEST_EVIDENCE_ONE_E01"]) == 4


def test_group_entries_by_public_episode_only_includes_entries_with_public_id():
    collection = load_evidence_indexes(FIXTURES_DIR)
    groups = group_entries_by_public_episode(collection)
    assert "EVT_TEST_PUBLIC_EVIDENCE_001_E01" in groups
    for entries in groups.values():
        for entry in entries:
            assert entry.public_episode_id is not None


# ----------------------------------------------------------------
# validate_evidence_index_document
# ----------------------------------------------------------------


def _entry(**overrides) -> EvidenceIndexEntry:
    defaults = {
        "evidence_id": "EVT_TEST_A_E01_DLG0001",
        "evidence_type": "dialogue",
        "story_id": "EVT_TEST_A",
        "episode_id": "EVT_TEST_A_E01",
    }
    defaults.update(overrides)
    return EvidenceIndexEntry(**defaults)


def _document(**overrides) -> EvidenceIndexDocument:
    defaults: dict = {}
    defaults.update(overrides)
    return EvidenceIndexDocument(**defaults)


def test_validate_accepts_minimal_valid_document():
    assert validate_evidence_index_document(_document(entries=[_entry()])) == []


def test_validate_accepts_document_with_public_evidence_id():
    issues = validate_evidence_index_document(
        _document(entries=[_entry(public_evidence_id="EVT_TEST_PUBLIC_A_E01_DLG0001")])
    )
    assert issues == []


def test_validate_rejects_invalid_evidence_id():
    issues = validate_evidence_index_document(
        _document(entries=[_entry(evidence_id="not_valid_id")])
    )
    assert any("形式が不正です" in issue for issue in issues)


def test_validate_rejects_empty_evidence_id():
    issues = validate_evidence_index_document(
        _document(entries=[_entry(evidence_id="")])
    )
    assert any("evidenceIdが空です" in issue for issue in issues)


def test_validate_rejects_unknown_evidence_type():
    issues = validate_evidence_index_document(
        _document(entries=[_entry(evidence_type="not_a_real_type")])
    )
    assert any("未知のevidenceType" in issue for issue in issues)


def test_validate_rejects_empty_story_id():
    issues = validate_evidence_index_document(_document(entries=[_entry(story_id="")]))
    assert any("storyIdが空です" in issue for issue in issues)


def test_validate_rejects_empty_episode_id():
    issues = validate_evidence_index_document(
        _document(entries=[_entry(episode_id="")])
    )
    assert any("episodeIdが空です" in issue for issue in issues)


def test_validate_rejects_unknown_speaker_resolution_status():
    issues = validate_evidence_index_document(
        _document(entries=[_entry(speaker=Speaker(resolution_status="not_a_status"))])
    )
    assert any("未知のspeaker.resolutionStatus" in issue for issue in issues)


def test_validate_accepts_valid_speaker_resolution_statuses():
    for status in ("resolved", "unresolved", "ambiguous", "unknown"):
        issues = validate_evidence_index_document(
            _document(entries=[_entry(speaker=Speaker(resolution_status=status))])
        )
        assert issues == [], f"failed for {status}"


def test_validate_rejects_unknown_related_entity_type():
    issues = validate_evidence_index_document(
        _document(
            entries=[
                _entry(
                    related_entities=[
                        RelatedEntity(entity_type="not_a_type", id="CHAR_TEST_A")
                    ]
                )
            ]
        )
    )
    assert any("未知のrelatedEntities.entityType" in issue for issue in issues)


def test_validate_rejects_raw_text_included_true():
    issues = validate_evidence_index_document(
        _document(entries=[_entry(visibility=Visibility(raw_text_included=True))])
    )
    assert any("rawTextIncluded" in issue for issue in issues)


def test_validate_rejects_public_false():
    issues = validate_evidence_index_document(
        _document(entries=[_entry(visibility=Visibility(public=False))])
    )
    assert any("visibility.publicがfalseです" in issue for issue in issues)


@pytest.mark.parametrize(
    "forbidden",
    [
        ".dec",
        "@ChTalk",
        "@ChTalkMono",
        "@ChTalkName",
        "@Scenario",
        "@ScenarioCos",
        "$num",
        "C:\\",
        "D:\\",
        "/Users/",
        "/home/",
        "<script",
        "</script>",
    ],
)
def test_validate_rejects_forbidden_text_in_notes(forbidden):
    issues = validate_evidence_index_document(
        _document(entries=[_entry(notes=f"問題のある文章 {forbidden} です")])
    )
    assert any("禁止文字列" in issue for issue in issues)


def test_validate_rejects_forbidden_text_in_speaker_display_name():
    issues = validate_evidence_index_document(
        _document(
            entries=[
                _entry(speaker=Speaker(display_name="raw変数 $num1 が混入した名前"))
            ]
        )
    )
    assert any("禁止文字列" in issue for issue in issues)


def test_validate_rejects_forbidden_text_in_related_entity_display_name():
    issues = validate_evidence_index_document(
        _document(
            entries=[
                _entry(
                    related_entities=[
                        RelatedEntity(
                            entity_type="character",
                            id="CHAR_TEST_A",
                            display_name="C:\\Users\\example\\raw.dec",
                        )
                    ]
                )
            ]
        )
    )
    assert any("禁止文字列" in issue for issue in issues)


def test_validate_rejects_forbidden_text_in_document_notes():
    issues = validate_evidence_index_document(
        _document(entries=[_entry()], notes="/Users/example/raw.dec")
    )
    assert any("禁止文字列" in issue for issue in issues)


def test_validate_accepts_clean_document():
    document = _document(
        entries=[
            _entry(
                speaker=Speaker(
                    speaker_id="CHAR_TEST_A",
                    display_name="Synthetic Speaker",
                    resolution_status="resolved",
                ),
                related_entities=[
                    RelatedEntity(
                        entity_type="character",
                        id="CHAR_TEST_A",
                        display_name="Synthetic Speaker",
                    )
                ],
            )
        ]
    )
    assert validate_evidence_index_document(document) == []


# ----------------------------------------------------------------
# validate_evidence_index_collection
# ----------------------------------------------------------------


def test_validate_collection_accepts_fixtures_directory():
    collection = load_evidence_indexes(FIXTURES_DIR)
    assert validate_evidence_index_collection(collection) == []


def test_validate_collection_rejects_duplicate_evidence_id_within_document():
    collection = EvidenceIndexCollection(
        documents=[_document(entries=[_entry(), _entry()])]
    )
    issues = validate_evidence_index_collection(collection)
    assert any("重複しています" in issue for issue in issues)


def test_validate_collection_rejects_duplicate_evidence_id_across_documents():
    collection = EvidenceIndexCollection(
        documents=[
            _document(entries=[_entry(evidence_id="EVT_TEST_DUP_E01_DLG0001")]),
            _document(entries=[_entry(evidence_id="EVT_TEST_DUP_E01_DLG0001")]),
        ]
    )
    issues = validate_evidence_index_collection(collection)
    assert any("重複しています" in issue for issue in issues)


def test_parse_evidence_index_document_from_raw_dict():
    document = parse_evidence_index_document(
        _minimal_raw_document(entries=[_raw_entry()])
    )
    assert len(document.entries) == 1
    assert document.entries[0].evidence_id == "EVT_TEST_A_E01_DLG0001"
    assert document.entries[0].visibility.raw_text_included is False


# ----------------------------------------------------------------
# EvidenceIndexLookup / build_evidence_index_lookup /
# resolve_group_public_story_id (feature/evidence-index-renderer-integration)
# ----------------------------------------------------------------


def test_build_evidence_index_lookup_from_fixtures_directory():
    collection = load_evidence_indexes(FIXTURES_DIR)
    lookup = build_evidence_index_lookup(collection)
    assert isinstance(lookup, EvidenceIndexLookup)
    assert "EVT_TEST_EVIDENCE_ONE_E01_DLG0001" in lookup.by_evidence_id
    assert "EVT_TEST_EVIDENCE_ONE" in lookup.by_story_id
    assert len(lookup.by_story_id["EVT_TEST_EVIDENCE_ONE"]) == 4


def test_resolve_group_public_story_id_returns_first_non_blank():
    entries = [
        _entry(public_story_id=None),
        _entry(public_story_id="PUB_A"),
        _entry(public_story_id="PUB_B"),
    ]
    assert resolve_group_public_story_id(entries) == "PUB_A"


def test_resolve_group_public_story_id_returns_none_when_all_blank():
    entries = [_entry(public_story_id=None), _entry(public_story_id="   ")]
    assert resolve_group_public_story_id(entries) is None


def test_resolve_group_public_story_id_empty_list_returns_none():
    assert resolve_group_public_story_id([]) is None
