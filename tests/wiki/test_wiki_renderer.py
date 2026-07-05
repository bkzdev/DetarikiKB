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

from agents.parser.character_profiles import (
    build_character_profile_index,
    load_character_profiles,
)
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

CHARACTER_PROFILES_FIXTURE_PATH = (
    Path(__file__).parent.parent
    / "fixtures"
    / "character_profiles"
    / "synthetic_character_profiles.yaml"
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


@pytest.fixture
def character_profiles_index() -> dict:
    """CHAR_TEST_RAIN（confirmed、selfIntroduction/profileHighlightあり）と
    CHAR_TEST_MINIMAL（draft、selfIntroduction/profileHighlight等がnull）
    を持つ合成プロフィール索引。CHAR_TEST_CONFLICTはあえて含めない
    (「プロフィール未登録」表示の確認用)。実WIKI由来データは含まない。"""
    profiles = load_character_profiles(CHARACTER_PROFILES_FIXTURE_PATH)
    return build_character_profile_index(profiles)


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
# render_character_page - 基本プロフィールsection
# (feature/character-profile-renderer-section)
# 合成fixture (tests/fixtures/character_profiles/synthetic_character_profiles.yaml)
# のみを使う。実WIKI由来candidate・raw HTML・実自己紹介文は一切含まない。
# ----------------------------------------------------------------


def test_render_character_page_without_profiles_shows_placeholder(resolved_character):
    """character_profilesを渡さない場合 (--character-profiles未指定相当) でも
    既存の出力を壊さず、基本プロフィールsectionは「プロフィール未登録」表示に
    なることを確認する。"""
    page = render_character_page(resolved_character)
    assert "## 基本プロフィール" in page
    assert "プロフィール未登録" in page


def test_render_character_page_shows_basic_profile_when_matched(
    resolved_character, character_profiles_index
):
    """CHAR_TEST_RAINはcanonicalIdが合成プロフィール索引のcharacterIdと
    一致するため、基本プロフィールsectionに各フィールドが表示される。"""
    page = render_character_page(resolved_character, character_profiles_index)
    assert "## 基本プロフィール" in page
    assert "| ふりがな | てすとれいん |" in page
    assert "| ローマ字 | Tesuto Rein |" in page
    assert "| 所属 | Test Team Alpha |" in page
    assert "| 血液型 | A |" in page
    assert "| CV | Test Voice Actor |" in page
    assert "| 出典 | Synthetic test fixture |" in page


def test_render_character_page_formats_height_cm(
    resolved_character, character_profiles_index
):
    page = render_character_page(resolved_character, character_profiles_index)
    assert "| 身長 | 150cm |" in page


def test_render_character_page_shows_birthday_display(
    resolved_character, character_profiles_index
):
    page = render_character_page(resolved_character, character_profiles_index)
    assert "| 誕生日 | 4/23 |" in page


def test_render_character_page_shows_profile_highlight(
    resolved_character, character_profiles_index
):
    page = render_character_page(resolved_character, character_profiles_index)
    assert "### キャラ別特記事項" in page
    assert "好きなこと: テストデータの整理" in page


def test_render_character_page_shows_self_introduction_multiline(
    resolved_character, character_profiles_index
):
    """selfIntroductionが複数行の場合、そのまま本文として表示される
    ことを確認する。"""
    page = render_character_page(resolved_character, character_profiles_index)
    assert "### 自己紹介" in page
    assert "こんにちは、これはテスト用の合成自己紹介文です。" in page
    assert "複数行の表示を確認するためのダミーテキストです。" in page


def test_render_character_page_no_matching_profile_shows_unregistered(
    conflict_character, character_profiles_index
):
    """CHAR_TEST_CONFLICTは合成プロフィール索引に存在しないため、
    「プロフィール未登録」と表示されCharacter page自体は生成が継続する
    ことを確認する。"""
    page = render_character_page(conflict_character, character_profiles_index)
    assert "## 基本プロフィール" in page
    assert "プロフィール未登録" in page
    assert "Test Character Conflict" in page


def test_render_character_page_self_introduction_null_shows_unregistered_message(
    character_profiles_index,
):
    """CHAR_TEST_MINIMALはselfIntroduction/profileHighlightがnullの合成
    プロフィール。selfIntroductionは「未登録」ではなく専用の未登録メッセージ、
    profileHighlightも専用の未登録メッセージで表示されることを確認する。"""
    entity = {
        "id": "CHAR_TEST_MINIMAL_ENTITY",
        "canonicalId": "CHAR_TEST_MINIMAL",
        "displayName": "Test Character Minimal",
        "status": "merged",
        "sourceTypes": ["script"],
        "confidence": 0.6,
    }
    page = render_character_page(entity, character_profiles_index)
    assert "## 基本プロフィール" in page
    assert "自己紹介は登録されていません。" in page
    assert "特記事項は登録されていません。" in page
    assert "| ふりがな | 未登録 |" in page
    assert "| 身長 | 未登録 |" in page


def test_render_character_page_no_canonical_id_shows_unregistered(
    character_profiles_index,
):
    """canonicalIdが無いentity (通常はis_page_eligibleがFalseで呼ばれない
    想定だが、防御的に落ちないことを確認する)。"""
    entity = {"id": "CHAR_TEST_NO_CANONICAL", "displayName": "No Canonical"}
    page = render_character_page(entity, character_profiles_index)
    assert "プロフィール未登録" in page


def test_build_pages_passes_character_profiles_through(
    synthetic_collection, character_profiles_index
):
    """build_pagesにcharacter_profilesを渡すと、対応するCharacter pageに
    反映されることを確認する。"""
    pages = build_pages(synthetic_collection, character_profiles_index)
    rain_page = pages["characters/CHAR_TEST_RAIN.md"]
    assert "| CV | Test Voice Actor |" in rain_page


def test_build_pages_without_character_profiles_keeps_existing_output(
    synthetic_collection,
):
    """character_profiles省略時もbuild_pagesが従来通り動作することを
    確認する (後方互換性)。"""
    pages = build_pages(synthetic_collection)
    assert "characters/CHAR_TEST_RAIN.md" in pages
    assert "プロフィール未登録" in pages["characters/CHAR_TEST_RAIN.md"]


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


def test_render_unresolved_report_lists_unresolved_relationship(synthetic_collection):
    """REL_TEST_UNKNOWN (canonicalId未確定のrelationship) が
    Relationshipセクションに列挙されることを確認する。"""
    report = render_unresolved_report(synthetic_collection)
    assert "## relationship (1 件)" in report
    assert "REL_TEST_UNKNOWN" in report


def test_render_unresolved_report_lists_unresolved_timeline_entry(
    synthetic_collection,
):
    """TL_TEST_UNKNOWN (canonicalId未確定のtimeline entry) が
    timeline_entryセクションに列挙されることを確認する。"""
    report = render_unresolved_report(synthetic_collection)
    assert "## timeline_entry (1 件)" in report
    assert "TL_TEST_UNKNOWN" in report


def test_render_unresolved_report_excludes_resolved_character(synthetic_collection):
    report = render_unresolved_report(synthetic_collection)
    assert "CHAR_TEST_RAIN" not in report


def test_render_unresolved_report_excludes_merged_character_with_canonical_id(
    synthetic_collection,
):
    """canonicalId確定 + status: mergedのCHAR_TEST_CONFLICTは、conflictsが
    あってもUnresolved reportには出さない (is_page_eligibleがTrueのため、
    別途Character pageで扱う)。"""
    report = render_unresolved_report(synthetic_collection)
    assert "CHAR_TEST_CONFLICT" not in report


def test_render_unresolved_report_includes_character_without_canonical_id(
    synthetic_collection,
):
    report = render_unresolved_report(synthetic_collection)
    assert "UNRESOLVED_CHAR_TEST_0001" in report


def test_render_unresolved_report_includes_non_merged_status_character(
    synthetic_collection,
):
    """CHAR_TEST_DEPRECATEDはcanonicalIdが確定しているがstatusが
    mergedでないため、is_page_eligibleがFalseとなりUnresolved reportに
    Canonical ID付きで列挙されることを確認する。"""
    report = render_unresolved_report(synthetic_collection)
    assert "CHAR_TEST_DEPRECATED" in report
    assert (
        "| CHAR_TEST_DEPRECATED | Test Character Deprecated | deprecated "
        "| CHAR_TEST_DEPRECATED |" in report
    )


def test_render_unresolved_report_has_front_matter(synthetic_collection):
    report = render_unresolved_report(synthetic_collection)
    assert report.startswith("---\n")
    assert "Unresolved Entities Report" in report


def test_render_unresolved_report_overview_section(synthetic_collection):
    report = render_unresolved_report(synthetic_collection)
    assert "## Overview" in report
    assert "| Total unresolved entities | 5 |" in report
    assert "| Total conflicts | 1 |" in report
    assert "| Total warnings | 1 |" in report
    assert "| Invalid canonical IDs | 1 |" in report
    assert "| Duplicate canonical IDs | 0 |" in report


def test_render_unresolved_report_entity_table_columns(synthetic_collection):
    report = render_unresolved_report(synthetic_collection)
    assert (
        "| Entity ID | Display Name | Status | Canonical ID "
        "| Evidence | Source Candidates |" in report
    )
    # canonicalId未確定の場合は "-" が表示される
    assert (
        "| UNRESOLVED_CHAR_TEST_0001 | Test Character Unknown "
        "| unresolved | - | 1 | 1 |" in report
    )


def test_render_unresolved_report_conflict_summary(synthetic_collection):
    report = render_unresolved_report(synthetic_collection)
    assert "## Conflict Summary" in report
    assert "| Severity | warning | 1 |" in report
    assert "| Type | name_conflict | 1 |" in report
    assert "| Entity Type | characters | 1 |" in report


def test_render_unresolved_report_warning_summary(synthetic_collection):
    report = render_unresolved_report(synthetic_collection)
    assert "## Warning Summary" in report
    assert "| Total | 1 |" in report
    assert "EP_TEST_002: サンプルwarningメッセージ" in report


def test_render_unresolved_report_canonical_id_summary(synthetic_collection):
    report = render_unresolved_report(synthetic_collection)
    assert "## Canonical ID Summary" in report
    assert "| Total Assigned | 2 |" in report
    assert "| Invalid Count | 1 |" in report
    assert "TEST_CANONICAL_ID_BAD" in report


def test_render_unresolved_report_relationship_type_summary_unknown_types(
    synthetic_collection,
):
    """relationshipTypeSummary.unknownTypesは自動修正せず、目立つ見出し
    付きで一覧表示されることを確認する。"""
    report = render_unresolved_report(synthetic_collection)
    assert "## Relationship Type Summary" in report
    assert "| Unknown Types | 1 |" in report
    assert "MYSTERIOUS_BOND_TEST" in report


def test_render_unresolved_report_evidence_shown_as_count_only(synthetic_collection):
    """entity種別別テーブルのEvidence列は件数のみで、evidenceIdや本文は
    出さないことを確認する (元セリフ全文を出さない方針)。"""
    report = render_unresolved_report(synthetic_collection)
    assert "textExcerpt" not in report
    assert "EP_TEST_001_DLG0002" not in report


def test_render_unresolved_report_source_candidates_shown_as_count_only(
    synthetic_collection,
):
    """entity種別別テーブルのSource Candidates列は件数のみで、
    candidateIdやraw payloadは出さないことを確認する。"""
    report = render_unresolved_report(synthetic_collection)
    assert "EP_TEST_001_CAND_CHAR002" not in report


# ----------------------------------------------------------------
# render_index_page / render_story_index_page / render_episode_page
# ----------------------------------------------------------------


def test_render_index_page_has_summary(synthetic_collection):
    page = render_index_page(synthetic_collection)
    assert page.startswith("---\n")
    assert "サマリー" in page
    assert "[Unresolved report](reports/unresolved.md)" in page


def test_render_story_index_page_links_to_episode(synthetic_collection):
    """stories/index.md自身がstories/配下にあるため、リンク先は
    ファイル名のみ (stories/プレフィックス無し) であることを確認する
    (feature/mkdocs-material-minimal-siteでの相対リンク切れ修正)。"""
    page = render_story_index_page(synthetic_collection)
    assert "TEST_S01_C01" in page
    assert "[EP_TEST_001](EP_TEST_001.md)" in page
    assert "(stories/EP_TEST_001.md)" not in page


def test_render_story_index_page_lists_all_episodes(synthetic_collection):
    """合成fixtureは2件のsourceDocuments (EP_TEST_001/EP_TEST_002) を持つ。
    両方がdocumentId・candidate合計・statusつきで一覧に出ることを確認する。"""
    page = render_story_index_page(synthetic_collection)
    assert "[EP_TEST_002](EP_TEST_002.md)" in page
    assert "EP_TEST_001" in page and "EP_TEST_002" in page
    # candidate合計 (EP_TEST_001: characters4+locations1+relationships1
    # +timelineCandidates1=7) が表示される
    assert "| 7 " in page
    # inputResultsのstatusが表示される
    assert "valid" in page


def test_render_episode_page_has_front_matter_and_basic_info(synthetic_collection):
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document, synthetic_collection)
    assert page.startswith("---\n")
    assert 'page_type: "episode"' in page
    assert 'episode_id: "EP_TEST_001"' in page
    assert 'story_id: "TEST_S01_C01"' in page
    assert 'document_id: "EP_TEST_001"' in page
    assert "EP_TEST_001" in page
    assert "TEST_S01_C01" in page
    assert "本文セリフはこのページに掲載しません" in page


def test_render_episode_page_candidate_counts_table(synthetic_collection):
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document, synthetic_collection)
    assert "## Candidate Counts" in page
    assert "| Characters | 4 |" in page
    assert "| Locations | 1 |" in page
    assert "| Timeline | 1 |" in page


def test_render_episode_page_related_characters_summary(synthetic_collection):
    """EP_TEST_001にはCHAR_TEST_RAIN(canonicalIdあり)・
    CHAR_TEST_CONFLICT(canonicalIdあり)・UNRESOLVED_CHAR_TEST_0001
    (canonicalIdなし) が関連する。resolvedはcanonicalId、unresolvedは
    内部IDと"unresolved"表記で列挙されることを確認する。"""
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document, synthetic_collection)
    assert "## Related Characters" in page
    assert "Test Character Rain" in page
    assert "`CHAR_TEST_RAIN`" in page
    assert "Test Character Unknown" in page
    assert "`UNRESOLVED_CHAR_TEST_0001`, unresolved" in page


def test_render_episode_page_related_characters_link_to_character_page(
    synthetic_collection,
):
    """resolvedなrelated characterには、Episode page (stories/{episodeId}.md)
    からCharacter page (characters/{canonicalId}.md) への相対リンクが
    張られることを確認する (MkDocsプレビューでクリックできるようにするため、
    feature/mkdocs-material-minimal-site)。unresolvedにはページが無いため
    リンクを張らない。"""
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document, synthetic_collection)
    assert "[`CHAR_TEST_RAIN`](../characters/CHAR_TEST_RAIN.md)" in page
    assert "](../characters/UNRESOLVED_CHAR_TEST_0001.md)" not in page


def test_render_episode_page_no_related_characters_message(synthetic_collection):
    """EP_TEST_002には関連するcharacterが無い合成fixture。"""
    source_document = synthetic_collection["sourceDocuments"][1]
    page = render_episode_page(source_document, synthetic_collection)
    assert "関連するキャラクターは記録されていません。" in page


def test_render_episode_page_validation_section_when_available(synthetic_collection):
    """EP_TEST_002はwarningsが1件あるinputResultを持つ合成fixture。"""
    source_document = synthetic_collection["sourceDocuments"][1]
    page = render_episode_page(source_document, synthetic_collection)
    assert "## Validation" in page
    assert "| Input status | valid |" in page
    assert "| Warnings | 1 |" in page


def test_render_episode_page_does_not_include_full_dialogue_text(
    synthetic_collection,
):
    """evidenceRefsにtextExcerptが無い合成fixtureのため、本文らしき文字列が
    出力に含まれないことを確認する。"""
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document, synthetic_collection)
    assert "textExcerpt" not in page


# ----------------------------------------------------------------
# build_pages / write_pages (統合)
# ----------------------------------------------------------------


def test_build_pages_generates_expected_paths(synthetic_collection):
    pages = build_pages(synthetic_collection)
    assert "index.md" in pages
    assert "stories/index.md" in pages
    assert "stories/EP_TEST_001.md" in pages
    assert "stories/EP_TEST_002.md" in pages
    assert "characters/CHAR_TEST_RAIN.md" in pages
    assert "characters/CHAR_TEST_CONFLICT.md" in pages
    assert "reports/unresolved.md" in pages
    # canonicalIdが無いキャラクターの個別ページは生成されない
    assert "characters/UNRESOLVED_CHAR_TEST_0001.md" not in pages
    # canonicalIdはあるがstatus: mergedでないキャラクターも生成されない
    assert "characters/CHAR_TEST_DEPRECATED.md" not in pages


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


# ----------------------------------------------------------------
# 縮退input（optional field欠落・空配列等）でのrenderer堅牢性
# (feature/real-data-wiki-render-dry-runで見つかった、実データで
# 起こり得る縮退パターンの回帰テスト。すべて合成fixtureのみを使う)
# ----------------------------------------------------------------

MINIMAL_FIXTURE_PATH = (
    Path(__file__).parent.parent
    / "fixtures"
    / "wiki"
    / "synthetic_minimal_collection.json"
)


@pytest.fixture
def minimal_collection() -> dict:
    """sourceDocumentsが空配列、report.canonicalIdSummary/
    relationshipTypeSummaryが存在せず、entityのdisplayName等の任意
    フィールドが欠落した縮退collection。"""
    with open(MINIMAL_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_build_pages_does_not_crash_on_empty_source_documents(minimal_collection):
    """sourceDocumentsが空配列でもbuild_pagesが例外を送出しないことを
    確認する。"""
    pages = build_pages(minimal_collection)
    assert "index.md" in pages
    assert "stories/index.md" in pages
    assert "reports/unresolved.md" in pages
    # sourceDocumentsが空なのでepisode pageは1件も生成されない
    assert not any(
        path.startswith("stories/") and path != "stories/index.md" for path in pages
    )


def test_render_character_page_does_not_crash_on_missing_optional_fields(
    minimal_collection,
):
    """aliases/mergedId/conflicts等の任意フィールドが欠落したentityでも
    render_character_pageが例外を送出しないことを確認する。"""
    resolved = minimal_collection["entities"]["characters"][0]
    page = render_character_page(resolved)
    assert "CHAR_MIN_RESOLVED" in page
    assert "別名は登録されていません。" in page
    assert "記録されている矛盾はありません" in page


def test_render_unresolved_report_does_not_crash_without_optional_report_fields(
    minimal_collection,
):
    """report.canonicalIdSummary/relationshipTypeSummaryが存在しない
    collectionでも、render_unresolved_reportが例外を送出せず、該当
    セクションを省略することを確認する。"""
    report = render_unresolved_report(minimal_collection)
    assert "## Overview" in report
    assert "## Canonical ID Summary" not in report
    assert "## Relationship Type Summary" not in report


def test_render_unresolved_report_truncates_long_warning_message(minimal_collection):
    """report.warningsに200文字を超える長いメッセージが含まれる場合、
    切り詰められて表示されることを確認する (実データ由来の長い引用が
    混入しても丸ごと転載しない安全策)。"""
    report = render_unresolved_report(minimal_collection)
    long_message = minimal_collection["report"]["warnings"][0]
    assert len(long_message) > 200
    assert long_message not in report
    assert "...(省略)" in report


def test_render_story_index_page_shows_no_episodes_message_for_empty_source_documents(
    minimal_collection,
):
    page = render_story_index_page(minimal_collection)
    assert "収録されているエピソードはありません。" in page


def test_write_pages_does_not_crash_on_minimal_collection(minimal_collection, tmp_path):
    """縮退collectionでもwrite_pagesまで一通り実行できることを確認する
    (CLI経由のdry-runと同じ経路)。"""
    pages = build_pages(minimal_collection)
    written = write_pages(pages, tmp_path)
    assert len(written) == len(pages)
    for relative_path in pages:
        assert (tmp_path / relative_path).is_file()
