"""
tests/wiki/test_story_summaries.py
agents/wiki_generator/story_summaries.py のユニットテスト。

すべて合成データ (EVT_TEST_* 等) のみを使う。実イベント名・実キャラ名・
実あらすじ・実セリフは一切含まない。renderer統合はまだ実装していないため、
loader/validatorのみを対象とする。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agents.wiki_generator.story_summaries import (
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_REVIEWED,
    REVIEW_STATUS_UNREVIEWED,
    EpisodeSummaryEntry,
    StorySummaryCollection,
    StorySummaryDocument,
    SummaryReview,
    build_public_story_summary_index,
    build_story_summary_index,
    find_episode_summary,
    find_episode_summary_by_public_id,
    is_displayable_summary,
    load_story_summaries,
    load_story_summary,
    parse_story_summary_document,
    validate_story_summary_collection,
    validate_story_summary_document,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "story_summaries"


def _write_document(tmp_path: Path, filename: str, data: dict) -> Path:
    path = tmp_path / filename
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)
    return path


def _minimal_raw_document(**overrides) -> dict:
    data = {
        "schemaVersion": "0.1.0",
        "documentType": "story_summary",
        "storyId": "EVT_TEST_A",
        "publicStoryId": None,
        "language": "ja",
        "generationStatus": "generated",
        "storySummary": None,
        "episodeSummaries": [],
        "source": {
            "sourceType": "manual",
            "model": None,
            "promptVersion": None,
            "generatedAt": None,
            "inputRefs": [],
        },
        "review": {
            "status": "reviewed",
            "reviewer": None,
            "reviewedAt": None,
            "notes": None,
        },
        "notes": None,
    }
    data.update(overrides)
    return data


# ----------------------------------------------------------------
# load_story_summary / load_story_summaries
# ----------------------------------------------------------------


def test_load_story_summary_basic(tmp_path):
    path = _write_document(
        tmp_path,
        "EVT_TEST_A.yaml",
        _minimal_raw_document(
            storySummary={"text": "合成要約", "confidence": 0.7, "evidenceRefs": []},
            episodeSummaries=[
                {
                    "episodeId": "EVT_TEST_A_E01",
                    "publicEpisodeId": "PUB_A_E01",
                    "episodeNumber": 1,
                    "text": "合成episode要約",
                    "confidence": 0.5,
                    "evidenceRefs": ["EVT_TEST_A_E01_DLG0001"],
                }
            ],
        ),
    )
    document = load_story_summary(path)
    assert document is not None
    assert document.story_id == "EVT_TEST_A"
    assert document.story_summary.text == "合成要約"
    assert len(document.episode_summaries) == 1
    assert document.episode_summaries[0].episode_id == "EVT_TEST_A_E01"
    assert document.episode_summaries[0].public_episode_id == "PUB_A_E01"


def test_load_story_summary_missing_file_returns_none(tmp_path):
    assert load_story_summary(tmp_path / "does_not_exist.yaml") is None


def test_load_story_summary_empty_file_returns_none(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert load_story_summary(path) is None


def test_load_story_summaries_from_fixtures_directory():
    collection = load_story_summaries(FIXTURES_DIR)
    story_ids = {doc.story_id for doc in collection.documents}
    assert "EVT_TEST_SUMMARY_ONE" in story_ids
    assert "EVT_TEST_SUMMARY_TWO" in story_ids
    assert "EVT_TEST_SUMMARY_THREE" in story_ids
    # 非再帰的走査のため、invalid_examples/配下は含まれない
    assert "EVT_TEST_SUMMARY_BAD_TEXT" not in story_ids
    assert "EVT_TEST_SUMMARY_DUP" not in story_ids


def test_load_story_summaries_missing_directory_returns_empty(tmp_path):
    collection = load_story_summaries(tmp_path / "does_not_exist")
    assert collection.documents == []


# ----------------------------------------------------------------
# build_story_summary_index / build_public_story_summary_index
# ----------------------------------------------------------------


def test_build_story_summary_index():
    collection = load_story_summaries(FIXTURES_DIR)
    index = build_story_summary_index(collection)
    assert "EVT_TEST_SUMMARY_ONE" in index
    assert index["EVT_TEST_SUMMARY_ONE"].story_id == "EVT_TEST_SUMMARY_ONE"


def test_build_public_story_summary_index_only_includes_documents_with_public_id():
    collection = load_story_summaries(FIXTURES_DIR)
    index = build_public_story_summary_index(collection)
    assert "EVT_TEST_PUBLIC_001" in index
    # EVT_TEST_SUMMARY_TWO/THREEはpublicStoryId未設定のため索引に含まれない
    assert len(index) == 1


# ----------------------------------------------------------------
# find_episode_summary / find_episode_summary_by_public_id
# ----------------------------------------------------------------


def test_find_episode_summary_by_episode_id():
    document = load_story_summary(FIXTURES_DIR / "valid_story_summary.yaml")
    entry = find_episode_summary(document, "EVT_TEST_SUMMARY_ONE_E01")
    assert entry is not None
    assert entry.episode_id == "EVT_TEST_SUMMARY_ONE_E01"


def test_find_episode_summary_not_found_returns_none():
    document = load_story_summary(FIXTURES_DIR / "valid_story_summary.yaml")
    assert find_episode_summary(document, "EVT_NOT_FOUND") is None


def test_find_episode_summary_by_public_id():
    document = load_story_summary(FIXTURES_DIR / "valid_story_summary.yaml")
    entry = find_episode_summary_by_public_id(document, "EVT_TEST_PUBLIC_001_E01")
    assert entry is not None
    assert entry.episode_id == "EVT_TEST_SUMMARY_ONE_E01"


def test_find_episode_summary_by_public_id_not_found_returns_none():
    document = load_story_summary(FIXTURES_DIR / "valid_story_summary.yaml")
    # episode 2はpublicEpisodeId未設定
    assert (
        find_episode_summary_by_public_id(document, "EVT_TEST_PUBLIC_001_E02") is None
    )


# ----------------------------------------------------------------
# is_displayable_summary
# ----------------------------------------------------------------


@pytest.mark.parametrize(
    "status,expected",
    [
        (REVIEW_STATUS_REVIEWED, True),
        (REVIEW_STATUS_APPROVED, True),
        (REVIEW_STATUS_UNREVIEWED, False),
        ("rejected", False),
        ("needs_revision", False),
    ],
)
def test_is_displayable_summary(status, expected):
    assert is_displayable_summary(SummaryReview(status=status)) is expected


# ----------------------------------------------------------------
# validate_story_summary_document
# ----------------------------------------------------------------


def _document(**overrides) -> StorySummaryDocument:
    defaults = {"story_id": "EVT_TEST_A"}
    defaults.update(overrides)
    return StorySummaryDocument(**defaults)


def test_validate_accepts_minimal_valid_document():
    assert validate_story_summary_document(_document()) == []


def test_validate_rejects_invalid_story_id():
    issues = validate_story_summary_document(_document(story_id="not_valid_id"))
    assert any("形式が不正です" in issue for issue in issues)


def test_validate_rejects_empty_story_id():
    issues = validate_story_summary_document(_document(story_id=""))
    assert any("storyIdが空です" in issue for issue in issues)


def test_validate_rejects_unknown_generation_status():
    issues = validate_story_summary_document(
        _document(generation_status="not_a_status")
    )
    assert any("未知のgenerationStatus" in issue for issue in issues)


def test_validate_rejects_unknown_review_status():
    issues = validate_story_summary_document(
        _document(review=SummaryReview(status="not_a_status"))
    )
    assert any("未知のreview.status" in issue for issue in issues)


def test_validate_rejects_unknown_source_type():
    from agents.wiki_generator.story_summaries import SummarySource

    issues = validate_story_summary_document(
        _document(source=SummarySource(source_type="not_a_type"))
    )
    assert any("未知のsource.sourceType" in issue for issue in issues)


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
    ],
)
def test_validate_rejects_forbidden_text_in_story_summary(forbidden):
    from agents.wiki_generator.story_summaries import StorySummaryEntry

    document = _document(
        story_summary=StorySummaryEntry(text=f"問題のある文章 {forbidden} です")
    )
    issues = validate_story_summary_document(document)
    assert any("禁止文字列" in issue for issue in issues)


def test_validate_rejects_forbidden_text_in_episode_summary():
    document = _document(
        episode_summaries=[
            EpisodeSummaryEntry(
                episode_id="EVT_TEST_A_E01", text="raw変数 $num1 が混入"
            )
        ]
    )
    issues = validate_story_summary_document(document)
    assert any("禁止文字列" in issue for issue in issues)


def test_validate_rejects_forbidden_text_in_notes():
    document = _document(notes="C:\\Users\\example\\raw.dec")
    issues = validate_story_summary_document(document)
    assert any("禁止文字列" in issue for issue in issues)


def test_validate_accepts_clean_text():
    from agents.wiki_generator.story_summaries import StorySummaryEntry

    document = _document(
        story_summary=StorySummaryEntry(text="明示された事実の簡潔なあらすじです。")
    )
    assert validate_story_summary_document(document) == []


def test_validate_rejects_duplicate_episode_id_within_story():
    document = _document(
        episode_summaries=[
            EpisodeSummaryEntry(episode_id="EVT_TEST_A_E01", text="1件目"),
            EpisodeSummaryEntry(episode_id="EVT_TEST_A_E01", text="2件目"),
        ]
    )
    issues = validate_story_summary_document(document)
    assert any("重複しています" in issue for issue in issues)


def test_validate_rejects_duplicate_public_episode_id_within_story():
    document = _document(
        episode_summaries=[
            EpisodeSummaryEntry(
                episode_id="EVT_TEST_A_E01", text="1件目", public_episode_id="PUB_E01"
            ),
            EpisodeSummaryEntry(
                episode_id="EVT_TEST_A_E02", text="2件目", public_episode_id="PUB_E01"
            ),
        ]
    )
    issues = validate_story_summary_document(document)
    assert any(
        "publicEpisodeId 'PUB_E01'" in issue and "重複しています" in issue
        for issue in issues
    )


def test_validate_rejects_invalid_evidence_ref_format():
    from agents.wiki_generator.story_summaries import StorySummaryEntry

    document = _document(
        story_summary=StorySummaryEntry(
            text="有効な要約文です。", evidence_refs=["not valid id!"]
        )
    )
    issues = validate_story_summary_document(document)
    assert any("evidenceRefの形式が不正です" in issue for issue in issues)


def test_validate_accepts_valid_evidence_ref_format():
    from agents.wiki_generator.story_summaries import StorySummaryEntry

    document = _document(
        story_summary=StorySummaryEntry(
            text="有効な要約文です。", evidence_refs=["EVT_TEST_A_E01_DLG0001"]
        )
    )
    assert validate_story_summary_document(document) == []


def test_validate_evidence_refs_not_required():
    """evidenceRefsは必須ではない (空リストで問題ない)。"""
    from agents.wiki_generator.story_summaries import StorySummaryEntry

    document = _document(
        story_summary=StorySummaryEntry(text="根拠なしでも有効な要約文です。")
    )
    assert validate_story_summary_document(document) == []


# ----------------------------------------------------------------
# validate_story_summary_collection
# ----------------------------------------------------------------


def test_validate_collection_accepts_fixtures_directory():
    collection = load_story_summaries(FIXTURES_DIR)
    assert validate_story_summary_collection(collection) == []


def test_validate_collection_rejects_duplicate_story_id():
    collection = StorySummaryCollection(
        documents=[
            _document(story_id="EVT_TEST_DUP"),
            _document(story_id="EVT_TEST_DUP"),
        ]
    )
    issues = validate_story_summary_collection(collection)
    assert any("重複しています" in issue for issue in issues)


def test_validate_collection_rejects_duplicate_public_story_id():
    collection = StorySummaryCollection(
        documents=[
            _document(story_id="EVT_TEST_A", public_story_id="PUB_DUP"),
            _document(story_id="EVT_TEST_B", public_story_id="PUB_DUP"),
        ]
    )
    issues = validate_story_summary_collection(collection)
    assert any(
        "publicStoryId 'PUB_DUP'" in issue and "重複しています" in issue
        for issue in issues
    )


def test_parse_story_summary_document_from_raw_dict():
    document = parse_story_summary_document(_minimal_raw_document())
    assert document.story_id == "EVT_TEST_A"
    assert document.review.status == "reviewed"
