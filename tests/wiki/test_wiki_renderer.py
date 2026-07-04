"""
tests/wiki/test_wiki_renderer.py
agents/wiki_generator/ のrenderer skeletonのユニットテスト。

すべて合成fixture (tests/fixtures/wiki/synthetic_merged_collection.json、
CHAR_TEST_RAIN等の架空ID・架空名) のみを使う。実データ由来のキャラクター
名・セリフ・ID・merged knowledge collectionは一切含まない。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.wiki_generator import (
    build_front_matter,
    build_pages,
    character_page_path,
    episode_page_path,
    is_page_eligible,
    render_character_page,
    render_episode_page,
    render_index_page,
    render_story_index_page,
    render_unresolved_report,
    write_pages,
)

FIXTURE_PATH = (
    Path(__file__).parent.parent
    / "fixtures"
    / "wiki"
    / "synthetic_merged_collection.json"
)


@pytest.fixture
def synthetic_collection() -> dict:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def resolved_character(synthetic_collection) -> dict:
    return synthetic_collection["entities"]["characters"][0]


@pytest.fixture
def conflict_character(synthetic_collection) -> dict:
    return synthetic_collection["entities"]["characters"][1]


@pytest.fixture
def unresolved_character(synthetic_collection) -> dict:
    return synthetic_collection["entities"]["characters"][2]


# ----------------------------------------------------------------
# build_front_matter
# ----------------------------------------------------------------


def test_build_front_matter_basic():
    front_matter = build_front_matter(
        {
            "title": "Test Character Rain",
            "entity_type": "character",
            "entity_id": "CHAR_TEST_RAIN",
            "canonical_id": "CHAR_TEST_RAIN",
            "status": "merged",
            "generated_from": "merged_knowledge_collection",
        }
    )
    assert front_matter.startswith("---\n")
    assert front_matter.rstrip().endswith("---")
    assert 'title: "Test Character Rain"' in front_matter
    assert 'generated_from: "merged_knowledge_collection"' in front_matter


def test_build_front_matter_omits_none_values():
    front_matter = build_front_matter(
        {"title": "X", "generated_from": "merged_knowledge_collection", "status": None}
    )
    assert "status:" not in front_matter


def test_build_front_matter_escapes_double_quotes():
    front_matter = build_front_matter(
        {"title": 'Test "Quoted" Name', "generated_from": "merged_knowledge_collection"}
    )
    assert '\\"Quoted\\"' in front_matter


# ----------------------------------------------------------------
# is_page_eligible / paths
# ----------------------------------------------------------------


def test_is_page_eligible_true_for_resolved_character(resolved_character):
    assert is_page_eligible(resolved_character) is True


def test_is_page_eligible_true_for_merged_character_with_conflicts(conflict_character):
    """conflictsが記録されていても、canonicalIdが確定しstatus: mergedで
    あれば通常ページを生成する (conflictsの有無はページ生成可否に影響
    しない、Wiki_Output_Design.md §5)。"""
    assert is_page_eligible(conflict_character) is True


def test_is_page_eligible_false_for_unresolved_character(unresolved_character):
    assert is_page_eligible(unresolved_character) is False


def test_character_page_path_uses_canonical_id(resolved_character):
    assert character_page_path(resolved_character) == "characters/CHAR_TEST_RAIN.md"


def test_character_page_path_none_for_unresolved(unresolved_character):
    assert character_page_path(unresolved_character) is None


def test_episode_page_path_uses_episode_id():
    source_document = {"episodeId": "EP_TEST_001", "documentId": "EP_TEST_001"}
    assert episode_page_path(source_document) == "stories/EP_TEST_001.md"


# ----------------------------------------------------------------
# render_character_page
# ----------------------------------------------------------------


def test_render_character_page_contains_front_matter_and_fields(resolved_character):
    page = render_character_page(resolved_character)
    assert page.startswith("---\n")
    assert 'title: "Test Character Rain"' in page
    assert 'entity_type: "character"' in page
    assert 'entity_id: "CHAR_TEST_RAIN"' in page
    assert 'canonical_id: "CHAR_TEST_RAIN"' in page
    assert 'status: "merged"' in page
    assert "Test Character Rain" in page
    assert "Rain-chan" in page


def test_render_character_page_shows_all_aliases(resolved_character):
    """合成fixtureのCHAR_TEST_RAINは2件のaliasesを持つ。両方が
    ## Aliasesセクションに列挙されることを確認する。"""
    page = render_character_page(resolved_character)
    assert "## Aliases" in page
    assert "- Rain-chan" in page
    assert "- Test Alias Rain" in page


def test_render_character_page_no_aliases_message(conflict_character):
    """CHAR_TEST_CONFLICTはaliasesが空の合成fixture。プレースホルダー
    メッセージが表示されることを確認する。"""
    page = render_character_page(conflict_character)
    assert "別名は登録されていません。" in page


def test_render_character_page_shows_source_types(resolved_character):
    page = render_character_page(resolved_character)
    assert "| Source types | script |" in page
    assert 'source_types: "script"' in page


def test_render_character_page_shows_confidence(resolved_character):
    page = render_character_page(resolved_character)
    assert "| Confidence | 0.9 |" in page
    assert 'confidence: "0.9"' in page


def test_render_character_page_evidence_is_reference_only(resolved_character):
    page = render_character_page(resolved_character)
    assert "evidenceId: EP_TEST_001_DLG0001" in page
    assert "episodeId: EP_TEST_001" in page
    assert "sceneId: EP_TEST_001_SC001" in page
    assert "blockId: EP_TEST_001_DLG0001" in page


def test_render_character_page_evidence_summary_lists_all_refs(resolved_character):
    """合成fixtureのCHAR_TEST_RAINは2件のevidenceRefsを持つ。両方が
    参照情報として列挙されることを確認する。"""
    page = render_character_page(resolved_character)
    assert "2 件の参照:" in page
    assert "evidenceId: EP_TEST_001_DLG0001" in page
    assert "evidenceId: EP_TEST_001_DLG0003" in page


def test_render_character_page_does_not_include_full_dialogue_text(
    resolved_character,
):
    """evidenceRefsにtextExcerptが無い合成fixtureのため、本文らしき文字列が
    出力に含まれないことを確認する (evidenceはID参照のみで構成される)。"""
    page = render_character_page(resolved_character)
    assert "textExcerpt" not in page


def test_render_character_page_source_candidates_summary(resolved_character):
    """合成fixtureのCHAR_TEST_RAINは2件のsourceCandidatesを持つ。
    candidateId/candidateType/episodeId等のsummaryが列挙され、
    元candidateのraw payloadは含まれないことを確認する。"""
    page = render_character_page(resolved_character)
    assert "## Source Candidates" in page
    assert "candidateId: EP_TEST_001_CAND_CHAR001" in page
    assert "candidateId: EP_TEST_001_CAND_CHAR003" in page
    assert "candidateType: character_candidate" in page
    assert "evidenceIds件数: 1" in page


def test_render_character_page_conflicts_section_when_empty(resolved_character):
    page = render_character_page(resolved_character)
    assert "記録されている矛盾はありません" in page


def test_render_character_page_conflicts_section_when_present(conflict_character):
    """CHAR_TEST_CONFLICTはconflictsが1件ある合成fixture。
    conflictType/field/severity/resolutionStatusが表示されることを
    確認する (高度な自動解決はしない)。"""
    page = render_character_page(conflict_character)
    assert "1 件の矛盾が記録されています" in page
    assert "name_conflict" in page
    assert "field: displayName" in page
    assert "severity: warning" in page
    assert "unresolved" in page
    assert "記録されている矛盾はありません" not in page


# ----------------------------------------------------------------
# render_unresolved_report
# ----------------------------------------------------------------


def test_render_unresolved_report_lists_unresolved_character(synthetic_collection):
    report = render_unresolved_report(synthetic_collection)
    assert "UNRESOLVED_CHAR_TEST_0001" in report
    assert "Test Character Unknown" in report


def test_render_unresolved_report_lists_unresolved_location(synthetic_collection):
    report = render_unresolved_report(synthetic_collection)
    assert "UNRESOLVED_LOC_TEST_0001" in report
    assert "Test Location Unknown" in report


def test_render_unresolved_report_excludes_resolved_character(synthetic_collection):
    report = render_unresolved_report(synthetic_collection)
    assert "CHAR_TEST_RAIN" not in report


def test_render_unresolved_report_has_front_matter(synthetic_collection):
    report = render_unresolved_report(synthetic_collection)
    assert report.startswith("---\n")
    assert "Unresolved Entities Report" in report


# ----------------------------------------------------------------
# render_index_page / render_story_index_page / render_episode_page
# ----------------------------------------------------------------


def test_render_index_page_has_summary(synthetic_collection):
    page = render_index_page(synthetic_collection)
    assert page.startswith("---\n")
    assert "サマリー" in page
    assert "[Unresolved report](reports/unresolved.md)" in page


def test_render_story_index_page_links_to_episode(synthetic_collection):
    page = render_story_index_page(synthetic_collection)
    assert "TEST_S01_C01" in page
    assert "[EP_TEST_001](stories/EP_TEST_001.md)" in page


def test_render_episode_page_has_basic_info_no_dialogue(synthetic_collection):
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document)
    assert "EP_TEST_001" in page
    assert "TEST_S01_C01" in page
    assert "本文セリフはこのページに掲載しません" in page


# ----------------------------------------------------------------
# build_pages / write_pages (統合)
# ----------------------------------------------------------------


def test_build_pages_generates_expected_paths(synthetic_collection):
    pages = build_pages(synthetic_collection)
    assert "index.md" in pages
    assert "stories/index.md" in pages
    assert "stories/EP_TEST_001.md" in pages
    assert "characters/CHAR_TEST_RAIN.md" in pages
    assert "characters/CHAR_TEST_CONFLICT.md" in pages
    assert "reports/unresolved.md" in pages
    # canonicalIdが無いキャラクターの個別ページは生成されない
    assert "characters/UNRESOLVED_CHAR_TEST_0001.md" not in pages


def test_write_pages_creates_files_under_tmp_path(synthetic_collection, tmp_path):
    pages = build_pages(synthetic_collection)
    written = write_pages(pages, tmp_path)

    assert len(written) == len(pages)
    for relative_path in pages:
        assert (tmp_path / relative_path).is_file()

    character_page = (tmp_path / "characters" / "CHAR_TEST_RAIN.md").read_text(
        encoding="utf-8"
    )
    assert "Test Character Rain" in character_page


def test_write_pages_clean_removes_existing_output(synthetic_collection, tmp_path):
    stale_file = tmp_path / "stale.md"
    tmp_path.mkdir(parents=True, exist_ok=True)
    stale_file.write_text("stale content", encoding="utf-8")

    pages = build_pages(synthetic_collection)
    write_pages(pages, tmp_path, clean=True)

    assert not stale_file.exists()
    assert (tmp_path / "index.md").is_file()
