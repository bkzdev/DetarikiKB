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
    CharacterProfile,
    ProfileHighlight,
    build_character_profile_index,
    load_character_profiles,
)
from agents.wiki_generator import (
    build_front_matter,
    build_pages,
    character_page_path,
    episode_page_path,
    evidence_page_path,
    is_page_eligible,
    render_character_index_page,
    render_character_page,
    render_episode_page,
    render_evidence_page,
    render_index_page,
    render_story_index_page,
    render_story_page,
    render_unresolved_report,
    story_page_path,
    write_pages,
)
from agents.wiki_generator.evidence_index import (
    EvidenceIndexCollection,
    EvidenceIndexLookup,
    build_evidence_index_lookup,
    parse_evidence_index_document,
)
from agents.wiki_generator.story_summaries import (
    StorySummaryCollection,
    StorySummaryLookup,
    build_story_summary_lookup,
    parse_story_summary_document,
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
# episode_page_path / publicEpisodeId
# (feature/story-manifest-public-id-renderer-switch)
# ----------------------------------------------------------------


def test_episode_page_path_prefers_public_episode_id_when_present():
    source_document = {
        "episodeId": "EP_TEST_PUBLIC_001",
        "publicEpisodeId": "PUBLIC_TEST_STORY_001_E01",
    }
    assert episode_page_path(source_document) == "stories/PUBLIC_TEST_STORY_001_E01.md"


def test_episode_page_path_falls_back_when_public_episode_id_absent():
    source_document = {"episodeId": "EP_TEST_002", "documentId": "EP_TEST_002"}
    assert episode_page_path(source_document) == "stories/EP_TEST_002.md"


def test_episode_page_path_falls_back_when_public_episode_id_is_none():
    source_document = {"episodeId": "EP_TEST_002", "publicEpisodeId": None}
    assert episode_page_path(source_document) == "stories/EP_TEST_002.md"


def test_episode_page_path_falls_back_when_public_episode_id_is_blank():
    source_document = {"episodeId": "EP_TEST_002", "publicEpisodeId": "   "}
    assert episode_page_path(source_document) == "stories/EP_TEST_002.md"


def test_episode_page_path_strips_whitespace_around_public_episode_id():
    source_document = {
        "episodeId": "EP_TEST_002",
        "publicEpisodeId": "  PUBLIC_TEST_002_E01  ",
    }
    assert episode_page_path(source_document) == "stories/PUBLIC_TEST_002_E01.md"


# ----------------------------------------------------------------
# story_page_path (feature/wiki-story-page-renderer)
# ----------------------------------------------------------------


def test_story_page_path_uses_story_id_when_no_public_story_id():
    assert story_page_path("TEST_S01_C01") == "stories/TEST_S01_C01.md"


def test_story_page_path_prefers_public_story_id_when_present():
    assert (
        story_page_path("TEST_PUBLIC_ID_STORY", "PUBLIC_TEST_STORY_001")
        == "stories/PUBLIC_TEST_STORY_001.md"
    )


def test_story_page_path_falls_back_when_public_story_id_is_none():
    assert story_page_path("TEST_S01_C01", None) == "stories/TEST_S01_C01.md"


def test_story_page_path_falls_back_when_public_story_id_is_blank():
    assert story_page_path("TEST_S01_C01", "   ") == "stories/TEST_S01_C01.md"


def test_story_page_path_strips_whitespace_around_public_story_id():
    assert (
        story_page_path("TEST_S01_C01", "  PUBLIC_TEST_001  ")
        == "stories/PUBLIC_TEST_001.md"
    )


# ----------------------------------------------------------------
# evidence_page_path (feature/evidence-index-renderer-integration)
# ----------------------------------------------------------------


def test_evidence_page_path_uses_story_id_when_no_public_story_id():
    assert evidence_page_path("TEST_S01_C01") == "evidence/TEST_S01_C01.md"


def test_evidence_page_path_prefers_public_story_id_when_present():
    assert (
        evidence_page_path("TEST_PUBLIC_ID_STORY", "PUBLIC_TEST_STORY_001")
        == "evidence/PUBLIC_TEST_STORY_001.md"
    )


def test_evidence_page_path_falls_back_when_public_story_id_is_none():
    assert evidence_page_path("TEST_S01_C01", None) == "evidence/TEST_S01_C01.md"


def test_evidence_page_path_falls_back_when_public_story_id_is_blank():
    assert evidence_page_path("TEST_S01_C01", "   ") == "evidence/TEST_S01_C01.md"


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
    """profileHighlightはWiki記載と同じ雰囲気の「【label】value」形式で、
    基本プロフィール表の「特記事項」行として表示される
    (独立sectionとしては表示しない)。"""
    page = render_character_page(resolved_character, character_profiles_index)
    assert "| 特記事項 | 【好きなこと】テストデータの整理 |" in page
    assert "### キャラ別特記事項" not in page


def test_render_character_page_profile_highlight_label_only():
    """label/valueがschema上は両方必須だが、防御的にlabelのみでも
    「【label】」表示になりクラッシュしないことを確認する。"""
    profile = CharacterProfile(
        character_id="CHAR_TEST_LABEL_ONLY",
        display_name="Test Character Label Only",
        profile_highlight=ProfileHighlight(label="合成項目", value=""),
    )
    entity = {
        "id": "CHAR_TEST_LABEL_ONLY_ENTITY",
        "canonicalId": "CHAR_TEST_LABEL_ONLY",
        "displayName": "Test Character Label Only",
        "status": "merged",
    }
    page = render_character_page(entity, {"CHAR_TEST_LABEL_ONLY": profile})
    assert "| 特記事項 | 【合成項目】 |" in page


def test_render_character_page_profile_highlight_value_only():
    """valueのみの場合はvalueそのものを表示する。"""
    profile = CharacterProfile(
        character_id="CHAR_TEST_VALUE_ONLY",
        display_name="Test Character Value Only",
        profile_highlight=ProfileHighlight(label="", value="合成値"),
    )
    entity = {
        "id": "CHAR_TEST_VALUE_ONLY_ENTITY",
        "canonicalId": "CHAR_TEST_VALUE_ONLY",
        "displayName": "Test Character Value Only",
        "status": "merged",
    }
    page = render_character_page(entity, {"CHAR_TEST_VALUE_ONLY": profile})
    assert "| 特記事項 | 合成値 |" in page


def test_render_character_page_hides_profile_source(
    resolved_character, character_profiles_index
):
    """character_profiles.yaml側にsource情報 (source.label等) があっても、
    Character page上には表示しない方針を確認する
    (character_profiles.yaml自体のsource情報は削除しない、renderer側で
    非表示にするだけ)。"""
    page = render_character_page(resolved_character, character_profiles_index)
    assert "出典" not in page
    assert "Synthetic test fixture" not in page


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
    assert "| 特記事項 | 未登録 |" in page
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
# render_character_index_page
# ----------------------------------------------------------------


def test_render_character_index_page_has_front_matter(
    synthetic_collection, character_profiles_index
):
    characters = synthetic_collection["entities"]["characters"]
    page = render_character_index_page(characters, character_profiles_index)
    assert page.startswith("---\n")
    assert 'title: "Characters"' in page
    assert "# キャラクター一覧" in page


def test_render_character_index_page_shows_profile_registered_character(
    synthetic_collection, character_profiles_index
):
    characters = synthetic_collection["entities"]["characters"]
    page = render_character_index_page(characters, character_profiles_index)
    assert "[Test Character Rain](CHAR_TEST_RAIN.md)" in page
    assert (
        "| [Test Character Rain](CHAR_TEST_RAIN.md) | 登録あり | `CHAR_TEST_RAIN` |"
        in page
    )


def test_render_character_index_page_shows_profile_unregistered_character(
    synthetic_collection, character_profiles_index
):
    characters = synthetic_collection["entities"]["characters"]
    page = render_character_index_page(characters, character_profiles_index)
    assert (
        "| [Test Character Conflict](CHAR_TEST_CONFLICT.md) | 未登録 "
        "| `CHAR_TEST_CONFLICT` |" in page
    )


def test_render_character_index_page_overview_counts(
    synthetic_collection, character_profiles_index
):
    characters = synthetic_collection["entities"]["characters"]
    page = render_character_index_page(characters, character_profiles_index)
    assert "| Character pages | 2 |" in page
    assert "| プロフィール登録あり | 1 |" in page
    assert "| プロフィール未登録 | 1 |" in page


def test_render_character_index_page_excludes_unresolved_character(
    synthetic_collection, character_profiles_index
):
    characters = synthetic_collection["entities"]["characters"]
    page = render_character_index_page(characters, character_profiles_index)
    assert "UNRESOLVED_CHAR_TEST_0001" not in page
    assert "Test Character Unknown" not in page


def test_render_character_index_page_excludes_no_canonical_id_character(
    synthetic_collection, character_profiles_index
):
    """canonicalIdが無いcharacterはCharacters indexに載らない
    (UNRESOLVED_CHAR_TEST_0001はcanonicalId: nullのケース)。"""
    characters = synthetic_collection["entities"]["characters"]
    page = render_character_index_page(characters, character_profiles_index)
    for entity in characters:
        if entity.get("canonicalId") is None:
            assert (entity.get("displayName") or "") not in page


def test_render_character_index_page_excludes_deprecated_character(
    synthetic_collection, character_profiles_index
):
    """canonicalIdはあるがstatus: mergedでないcharacter
    (CHAR_TEST_DEPRECATED) はCharacters indexに載らない。"""
    characters = synthetic_collection["entities"]["characters"]
    page = render_character_index_page(characters, character_profiles_index)
    assert "CHAR_TEST_DEPRECATED" not in page
    assert "Test Character Deprecated" not in page


def test_render_character_index_page_links_to_unresolved_report(
    synthetic_collection, character_profiles_index
):
    characters = synthetic_collection["entities"]["characters"]
    page = render_character_index_page(characters, character_profiles_index)
    assert "[Unresolved report](../reports/unresolved.md)" in page


def test_render_character_index_page_without_character_profiles_does_not_crash(
    synthetic_collection,
):
    """character_profiles省略時も落ちず、全員「未登録」表示になることを
    確認する。"""
    characters = synthetic_collection["entities"]["characters"]
    page = render_character_index_page(characters)
    assert "| Character pages | 2 |" in page
    assert "| プロフィール登録あり | 0 |" in page
    assert "| プロフィール未登録 | 2 |" in page


def test_render_character_index_page_empty_list_shows_message():
    page = render_character_index_page([])
    assert "登録されているCharacter pageはありません。" in page


def test_render_index_page_links_to_characters_index(synthetic_collection):
    page = render_index_page(synthetic_collection)
    assert "[Characters](characters/index.md)" in page


def test_build_pages_includes_characters_index(synthetic_collection):
    pages = build_pages(synthetic_collection)
    assert "characters/index.md" in pages


def test_build_pages_characters_index_page_count_matches_generated_pages(
    synthetic_collection,
):
    """Characters indexの一覧件数と、実際に生成されたCharacter page数が
    一致することを確認する。"""
    pages = build_pages(synthetic_collection)
    generated_character_pages = [
        p for p in pages if p.startswith("characters/") and p != "characters/index.md"
    ]
    assert "| Character pages | 2 |" in pages["characters/index.md"]
    assert len(generated_character_pages) == 2


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
        "| Test Character Deprecated | `CHAR_TEST_DEPRECATED` | deprecated "
        "| `CHAR_TEST_DEPRECATED` | 1/1 |" in report
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
    """列数を最小限にするため (manual visual review 001での指摘)、
    EvidenceとSource Candidatesは「Refs」列へ「evidence件数/
    source candidate件数」の形式で統合する。"""
    report = render_unresolved_report(synthetic_collection)
    assert "| Display Name | Entity ID | Status | Canonical ID | Refs |" in report
    # canonicalId未確定の場合は「未登録」が表示される
    assert (
        "| Test Character Unknown | `UNRESOLVED_CHAR_TEST_0001` "
        "| unresolved | 未登録 | 1/1 |" in report
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
# render_unresolved_report: Special Speaker Labels section
# ----------------------------------------------------------------


def test_render_unresolved_report_has_special_speaker_labels_section(
    synthetic_collection,
):
    report = render_unresolved_report(synthetic_collection)
    assert "## Special Speaker Labels" in report


def test_render_unresolved_report_special_speaker_labels_table_columns(
    synthetic_collection,
):
    report = render_unresolved_report(synthetic_collection)
    assert "| Label | Type | Inferred | Refs |" in report


def test_render_unresolved_report_special_speaker_labels_lists_speaker_group(
    synthetic_collection,
):
    report = render_unresolved_report(synthetic_collection)
    assert (
        "| Test Speaker A ＆ Test Speaker B | speaker_group "
        "| Test Speaker A | 1/1 |" in report
    )


def test_render_unresolved_report_special_speaker_labels_lists_generic_speaker(
    synthetic_collection,
):
    report = render_unresolved_report(synthetic_collection)
    assert "| ？？？ | generic_speaker | - | 1/1 |" in report


def test_render_unresolved_report_special_speaker_labels_not_in_character_section(
    synthetic_collection,
):
    """special speaker labelはentities.specialSpeakerLabels由来であり、
    entities.charactersには含まれないため、通常のcharacterセクションの
    表には重複表示されない (別セクションでのみ表示される)。"""
    report = render_unresolved_report(synthetic_collection)
    character_section_start = report.index("## character (")
    special_section_start = report.index("## Special Speaker Labels")
    character_section = report[character_section_start:special_section_start]
    assert "Test Speaker A" not in character_section
    assert "？？？" not in character_section


def test_render_unresolved_report_special_speaker_labels_table_never_shows_confirmed(
    synthetic_collection,
):
    """Special Speaker Labelsのtable行 (Label/Type/Inferred/Refs) には、
    値としての"confirmed"が現れないことを確認する (自動でconfirmed
    character解決はしない方針。説明文中の"confirmed characterへ解決..."
    という地の文は対象外)。"""
    report = render_unresolved_report(synthetic_collection)
    special_section_start = report.index("## Special Speaker Labels")
    conflict_section_start = report.index("## Conflict Summary")
    special_section = report[special_section_start:conflict_section_start]
    table_rows = [line for line in special_section.splitlines() if line.startswith("|")]
    assert table_rows, "table rows should be present"
    assert not any("confirmed" in row for row in table_rows)


def test_render_unresolved_report_special_speaker_labels_empty_shows_placeholder():
    collection = {
        "sourceDocuments": [],
        "entities": {
            "characters": [],
            "locations": [],
            "organizations": [],
            "items": [],
            "lore": [],
            "events": [],
            "relationships": [],
            "timeline": [],
            "specialSpeakerLabels": [],
        },
        "report": {},
    }
    report = render_unresolved_report(collection)
    assert "## Special Speaker Labels" in report
    assert "該当するspeaker labelはありません。" in report


def test_render_unresolved_report_special_speaker_labels_missing_key_does_not_crash():
    """既存の合成fixture (specialSpeakerLabelsキー自体が無いもの) でも
    クラッシュしないことを確認する (後方互換)。"""
    collection = {
        "sourceDocuments": [],
        "entities": {
            "characters": [],
            "locations": [],
            "organizations": [],
            "items": [],
            "lore": [],
            "events": [],
            "relationships": [],
            "timeline": [],
        },
        "report": {},
    }
    report = render_unresolved_report(collection)
    assert "## Special Speaker Labels" in report
    assert "該当するspeaker labelはありません。" in report


# ----------------------------------------------------------------
# render_index_page / render_story_index_page / render_episode_page
# ----------------------------------------------------------------


def test_render_index_page_has_summary(synthetic_collection):
    page = render_index_page(synthetic_collection)
    assert page.startswith("---\n")
    assert "サマリー" in page
    assert "[Unresolved report](reports/unresolved.md)" in page


def test_render_story_index_page_links_to_story_page(synthetic_collection):
    """stories/index.md自身がstories/配下にあるため、リンク先は
    ファイル名のみ (stories/プレフィックス無し) であることを確認する。
    リンクtext自体はstoryTitle優先の人間向け表示になる
    (feature/wiki-story-page-renderer、`Story_Page_Design.md` §8)。"""
    page = render_story_index_page(synthetic_collection)
    assert "[Synthetic Story Title](TEST_S01_C01.md)" in page
    assert "(stories/TEST_S01_C01.md)" not in page


def test_render_story_index_page_lists_all_stories(synthetic_collection):
    """合成fixtureの3ストーリー (TEST_S01_C01/TEST_PUBLIC_ID_STORY/
    TEST_SOLO_STORY) がすべて一覧に出ることを確認する。"""
    page = render_story_index_page(synthetic_collection)
    assert "[Synthetic Story Title](TEST_S01_C01.md)" in page
    assert "[Synthetic Public ID Story Title](PUBLIC_TEST_STORY_001.md)" in page
    assert "[TEST_SOLO_STORY](TEST_SOLO_STORY.md)" in page


def test_render_story_index_page_shows_episode_counts(synthetic_collection):
    """Episodes列に、そのstoryに属するepisode数が表示されることを
    確認する (TEST_S01_C01=5件、TEST_PUBLIC_ID_STORY=2件、
    TEST_SOLO_STORY=1件)。"""
    page = render_story_index_page(synthetic_collection)
    assert "| [Synthetic Story Title](TEST_S01_C01.md) | 5 |" in page
    assert "| [Synthetic Public ID Story Title](PUBLIC_TEST_STORY_001.md) | 2 |" in page
    assert "| [TEST_SOLO_STORY](TEST_SOLO_STORY.md) | 1 |" in page


def test_render_story_index_page_shows_mixed_status_when_episodes_differ(
    synthetic_collection,
):
    """story内のepisodeでmetadataStatusが異なる場合、「mixed」と表示
    されることを確認する (TEST_S01_C01: confirmed/pending/pending/
    title_unknown/deprecated混在、TEST_PUBLIC_ID_STORY: confirmed/pending
    混在)。"""
    page = render_story_index_page(synthetic_collection)
    assert "| [Synthetic Story Title](TEST_S01_C01.md) | 5 | mixed |" in page
    assert (
        "| [Synthetic Public ID Story Title](PUBLIC_TEST_STORY_001.md) | 2 | mixed |"
        in page
    )


def test_render_story_index_page_shows_uniform_status_when_consistent(
    synthetic_collection,
):
    """story内の全episodeが同じmetadataStatusの場合 (TEST_SOLO_STORY、
    episode1件のみでpending) は、そのまま日本語補足付きで表示される
    ことを確認する。"""
    page = render_story_index_page(synthetic_collection)
    assert "| [TEST_SOLO_STORY](TEST_SOLO_STORY.md) | 1 | pending（未確認） |" in page


def test_render_story_index_page_column_header(synthetic_collection):
    """Story indexの列がStory/Episodes/Status/Categoryの4列に
    なったことを確認する (feature/wiki-story-page-renderer)。"""
    page = render_story_index_page(synthetic_collection)
    header_line = next(line for line in page.splitlines() if line.startswith("| Story"))
    assert header_line == "| Story | Episodes | Status | Category |"


def test_render_story_index_page_no_double_prefix(synthetic_collection):
    """stories/index.md自身がstories/配下にあるため、Story pageへの
    リンクでも二重prefix (stories/stories/...) が起きないことを確認する。"""
    page = render_story_index_page(synthetic_collection)
    assert "stories/TEST_S01_C01.md" not in page
    assert "stories/PUBLIC_TEST_STORY_001.md" not in page


def test_render_story_index_page_links_to_public_story_id_when_present(
    synthetic_collection,
):
    """publicStoryIdが設定されているstory (TEST_PUBLIC_ID_STORY) は、
    Story indexのリンク先がpublicStoryIdベースのfilenameになることを
    確認する。"""
    page = render_story_index_page(synthetic_collection)
    assert "(PUBLIC_TEST_STORY_001.md)" in page
    assert "(TEST_PUBLIC_ID_STORY.md)" not in page


def test_render_story_index_page_falls_back_to_story_id_without_title_or_public_id(
    synthetic_collection,
):
    """storyTitle/publicStoryIdがいずれも無いstory (TEST_SOLO_STORY) は、
    リンクtext・リンク先ともにstoryIdへfallbackすることを確認する。"""
    page = render_story_index_page(synthetic_collection)
    assert "[TEST_SOLO_STORY](TEST_SOLO_STORY.md)" in page


def test_render_story_index_page_escapes_bracket_and_pipe_in_link_text():
    """storyTitleに`[`/`]`/`|`が含まれる場合でも、tableとlink構造が
    壊れないよう最小限のMarkdown escapeを行うことを確認する
    (Story link textはstoryTitle優先のため、storyTitle側で確認する)。"""
    collection = {
        "sourceDocuments": [
            {
                "path": "synthetic.json",
                "documentId": "EP_TEST_ESCAPE",
                "storyId": "TEST_ESCAPE",
                "episodeId": "EP_TEST_ESCAPE",
                "storyCategory": "MAIN",
                "storyTitle": "Chapter [1] | Special",
                "metadataStatus": "confirmed",
            }
        ],
        "report": {},
    }
    page = render_story_index_page(collection)
    assert "[Chapter \\[1\\] \\| Special](TEST_ESCAPE.md)" in page


def test_render_episode_page_summary_is_bullet_list_not_table(synthetic_collection):
    """Summaryは横長tableではなく箇条書き (definition list風) で構成される
    ことを確認する (manual visual review 001での「横長すぎる」指摘への
    対応、feature/wiki-renderer-readability-improvements)。"""
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document, synthetic_collection)
    summary_section = page.split("## Summary", 1)[1].split("## Candidate Counts", 1)[0]
    assert "| 項目 | 値 |" not in summary_section
    assert "|---|---|" not in summary_section
    assert "- Episode ID: `EP_TEST_001`" in summary_section


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


def test_render_episode_page_relative_source_path_shown_as_is(synthetic_collection):
    """既存fixtureの相対パス (tests/fixtures/...) はそのまま表示される
    ことを確認する (feature/mkdocs-local-preview-dry-run で追加した
    ローカル絶対パス縮約表示は相対パスには影響しない)。"""
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document, synthetic_collection)
    assert "tests/fixtures/wiki/synthetic_episode_extraction.json" in page


def test_render_episode_page_sanitizes_windows_absolute_source_path(
    synthetic_collection,
):
    """実データローカルdry-run時、sourceDocuments[].pathに環境依存の
    Windowsローカル絶対パスが入っていても、ファイル名のみへ縮約されて
    表示されることを確認する (ローカル絶対パス非公開方針、
    docs/runbooks/MkDocs_Local_Preview_Dry_Run.md参照)。"""
    source_document = dict(synthetic_collection["sourceDocuments"][0])
    source_document["path"] = (
        r"C:\Users\synthetic_user\project\data\extracted\synthetic_episode.json"
    )
    page = render_episode_page(source_document, synthetic_collection)
    assert r"C:\Users\synthetic_user" not in page
    assert "synthetic_episode.json" in page
    assert "ローカル絶対パスのため縮約表示" in page


def test_render_episode_page_sanitizes_posix_absolute_source_path(
    synthetic_collection,
):
    source_document = dict(synthetic_collection["sourceDocuments"][0])
    source_document["path"] = "/home/synthetic_user/project/data/synthetic_episode.json"
    page = render_episode_page(source_document, synthetic_collection)
    assert "/home/synthetic_user" not in page
    assert "synthetic_episode.json" in page
    assert "ローカル絶対パスのため縮約表示" in page


def test_render_episode_page_missing_source_path_renders_empty(synthetic_collection):
    source_document = dict(synthetic_collection["sourceDocuments"][0])
    source_document.pop("path", None)
    page = render_episode_page(source_document, synthetic_collection)
    assert "- Source Path: 未登録" in page


def test_render_episode_page_shows_story_title(synthetic_collection):
    # EP_TEST_001はstoryTitle="Synthetic Story Title"を持つ合成fixture
    # (実イベント名・実タイトルは使用しない)。
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document, synthetic_collection)
    assert "- Story Title: Synthetic Story Title" in page


def test_render_episode_page_shows_episode_subtitle(synthetic_collection):
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document, synthetic_collection)
    assert "- Episode Subtitle: Synthetic Episode Subtitle" in page


def test_render_episode_page_shows_display_title(synthetic_collection):
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document, synthetic_collection)
    assert "- Display Title: Synthetic Display Title" in page


def test_render_episode_page_shows_metadata_status_confirmed(synthetic_collection):
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document, synthetic_collection)
    assert "- Metadata Status: confirmed（確認済み）" in page


def test_render_episode_page_shows_metadata_status_pending(synthetic_collection):
    # EP_TEST_002はmetadataStatus="pending"・title/subtitle/displayTitleは
    # すべてnullの合成fixture。
    source_document = synthetic_collection["sourceDocuments"][1]
    page = render_episode_page(source_document, synthetic_collection)
    assert "- Metadata Status: pending（未確認）" in page


def test_render_episode_page_null_title_fields_show_placeholder(synthetic_collection):
    """title/subtitle/displayTitleがnullの場合、それぞれ「未登録」と
    表示され、既存のepisodeId表示 (見出し・Episode ID行) は変わらない
    ことを確認する (fallback方針)。"""
    source_document = synthetic_collection["sourceDocuments"][1]
    page = render_episode_page(source_document, synthetic_collection)
    assert "- Story Title: 未登録" in page
    assert "- Episode Subtitle: 未登録" in page
    assert "- Display Title: 未登録" in page
    assert "# EP_TEST_002" in page
    assert "- Episode ID: `EP_TEST_002`" in page


def test_render_episode_page_shows_public_episode_id_and_public_story_id(
    synthetic_collection,
):
    """publicStoryId/publicEpisodeIdが設定されているEpisode
    (EP_TEST_PUBLIC_001) のSummaryに、内部Episode ID/Story IDと並んで
    Public Episode ID/Public Story IDが表示されることを確認する。"""
    source_document = next(
        doc
        for doc in synthetic_collection["sourceDocuments"]
        if doc["episodeId"] == "EP_TEST_PUBLIC_001"
    )
    page = render_episode_page(source_document, synthetic_collection)
    assert "- Episode ID: `EP_TEST_PUBLIC_001`" in page
    assert "- Story ID: `TEST_PUBLIC_ID_STORY`" in page
    assert "- Public Episode ID: `PUBLIC_TEST_STORY_001_E01`" in page
    assert "- Public Story ID: `PUBLIC_TEST_STORY_001`" in page


def test_render_episode_page_public_ids_show_unregistered_when_absent(
    synthetic_collection,
):
    """publicStoryId/publicEpisodeIdが設定されていない既存Episode
    (EP_TEST_001) では、Public Story ID/Public Episode IDともに
    「未登録」と表示されることを確認する (既存fixture互換)。"""
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document, synthetic_collection)
    assert "- Public Episode ID: 未登録" in page
    assert "- Public Story ID: 未登録" in page


def test_render_episode_page_public_episode_id_without_public_story_id(
    synthetic_collection,
):
    """publicStoryId/publicEpisodeIdいずれもこのepisode自体には設定
    されていないEpisode (EP_TEST_PUBLIC_002、feature/wiki-story-page-renderer
    でstory-level publicStoryId解決のfallbackテスト用に再構成) では、
    Episode pageのSummary上はいずれも「未登録」になることを確認する
    (story page側ではEP_TEST_PUBLIC_001由来のpublicStoryIdへ解決される、
    別途test_render_story_page_shows_overview_fields参照)。"""
    source_document = next(
        doc
        for doc in synthetic_collection["sourceDocuments"]
        if doc["episodeId"] == "EP_TEST_PUBLIC_002"
    )
    page = render_episode_page(source_document, synthetic_collection)
    assert "- Public Episode ID: 未登録" in page
    assert "- Public Story ID: 未登録" in page


def test_render_episode_page_missing_manifest_metadata_keys_does_not_crash(
    synthetic_collection,
):
    """story_manifest.yaml統合以前の古いsourceDocument (storyTitle等の
    キー自体が無い) を渡してもクラッシュせず、未登録表示になることを
    確認する (既存fixture互換性)。"""
    source_document = dict(synthetic_collection["sourceDocuments"][0])
    for key in ("storyTitle", "episodeSubtitle", "displayTitle", "metadataStatus"):
        source_document.pop(key, None)

    page = render_episode_page(source_document, synthetic_collection)

    assert "- Story Title: 未登録" in page
    assert "- Episode Subtitle: 未登録" in page
    assert "- Display Title: 未登録" in page
    assert "- Metadata Status: 未登録" in page


def test_render_episode_page_does_not_mention_ai_generated_title(synthetic_collection):
    """公式title/subtitle表示に「AI-generated」等のAI考察ラベルが
    混ざらないことを確認する (Wiki_Output_Design.md §3の分離方針、
    AI titleは生成しない)。"""
    source_document = synthetic_collection["sourceDocuments"][0]
    page = render_episode_page(source_document, synthetic_collection)
    assert "AI-generated" not in page
    assert "AI生成" not in page
    assert "AI推定" not in page


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
# render_story_page (feature/wiki-story-page-renderer)
# ----------------------------------------------------------------


def _story_episodes(collection: dict, story_id: str) -> list[dict]:
    return [
        doc for doc in collection["sourceDocuments"] if doc.get("storyId") == story_id
    ]


def test_render_story_page_has_front_matter_and_title(synthetic_collection):
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection)
    assert page.startswith("---\n")
    assert 'page_type: "story"' in page
    assert 'story_id: "TEST_S01_C01"' in page
    assert "# Synthetic Story Title" in page


def test_render_story_page_title_falls_back_to_public_story_id(synthetic_collection):
    """storyTitleが解決できない場合はpublicStoryIdへfallbackすることを
    確認する (合成のためstoryTitleを外したepisodesのみで検証)。"""
    episodes = [
        {**doc, "storyTitle": None}
        for doc in _story_episodes(synthetic_collection, "TEST_PUBLIC_ID_STORY")
    ]
    page = render_story_page("TEST_PUBLIC_ID_STORY", episodes, synthetic_collection)
    assert "# PUBLIC_TEST_STORY_001" in page


def test_render_story_page_title_falls_back_to_story_id(synthetic_collection):
    episodes = _story_episodes(synthetic_collection, "TEST_SOLO_STORY")
    page = render_story_page("TEST_SOLO_STORY", episodes, synthetic_collection)
    assert "# TEST_SOLO_STORY" in page


def test_render_story_page_shows_overview_fields(synthetic_collection):
    episodes = _story_episodes(synthetic_collection, "TEST_PUBLIC_ID_STORY")
    page = render_story_page("TEST_PUBLIC_ID_STORY", episodes, synthetic_collection)
    assert "- Story ID: `TEST_PUBLIC_ID_STORY`" in page
    assert "- Public Story ID: `PUBLIC_TEST_STORY_001`" in page
    assert "- Category: EVT" in page
    assert "- Episodes: 2" in page


def test_render_story_page_public_story_id_shows_unregistered_when_absent(
    synthetic_collection,
):
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection)
    assert "- Public Story ID: 未登録" in page


def test_render_story_page_shows_story_summary_placeholder(synthetic_collection):
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection)
    summary_section = page.split("## Story Summary", 1)[1].split(
        "## Episode Summaries", 1
    )[0]
    assert "未生成" in summary_section


def test_render_story_page_shows_episode_summaries_per_episode(synthetic_collection):
    """Episode SummariesがEpisodeごとに区切って表示され、5episode分の
    見出しがすべて含まれることを確認する (TEST_S01_C01、5episode)。"""
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection)
    summaries_section = page.split("## Episode Summaries", 1)[1].split(
        "## Episodes", 1
    )[0]
    assert summaries_section.count("未生成") == 5


def test_render_story_page_episode_summary_heading_uses_episode_subtitle(
    synthetic_collection,
):
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection)
    assert "### Synthetic Episode Subtitle" in page
    assert "### Synthetic Episode Subtitle Only" in page


def test_render_story_page_episode_summary_heading_falls_back_to_positional_index(
    synthetic_collection,
):
    """episodeSubtitle/displayTitleがいずれも無いepisode (EP_TEST_002/004/005)
    は、story内の並び順に基づく`Episode {index}`見出しへfallbackする
    ことを確認する。"""
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection)
    assert "### Episode 2" in page
    assert "### Episode 4" in page
    assert "### Episode 5" in page


def test_render_story_page_shows_episode_list_table(synthetic_collection):
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection)
    assert "| Episode | Status | Public Episode ID |" in page
    assert "[Synthetic Display Title](EP_TEST_001.md)" in page
    assert "[EP_TEST_002](EP_TEST_002.md)" in page


def test_render_story_page_episode_list_shows_public_episode_id_column(
    synthetic_collection,
):
    episodes = _story_episodes(synthetic_collection, "TEST_PUBLIC_ID_STORY")
    page = render_story_page("TEST_PUBLIC_ID_STORY", episodes, synthetic_collection)
    assert "`PUBLIC_TEST_STORY_001_E01`" in page
    episode_list_section = page.split("## Episodes", 1)[1].split(
        "## Related Characters", 1
    )[0]
    assert "未登録" in episode_list_section


def test_render_story_page_episode_list_uses_public_episode_id_link(
    synthetic_collection,
):
    """Episode一覧のリンク先は、既存のepisode_page_path解決結果
    (publicEpisodeId優先、無ければepisodeId fallback) をそのまま使う
    ことを確認する (PR #73の方針を維持)。"""
    episodes = _story_episodes(synthetic_collection, "TEST_PUBLIC_ID_STORY")
    page = render_story_page("TEST_PUBLIC_ID_STORY", episodes, synthetic_collection)
    assert "(PUBLIC_TEST_STORY_001_E01.md)" in page
    assert "(EP_TEST_PUBLIC_002.md)" in page
    assert "stories/" not in page


def test_render_story_page_has_related_characters_section(synthetic_collection):
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection)
    assert "## Related Characters" in page
    assert "Test Character Rain" in page
    assert "`CHAR_TEST_RAIN`" in page


def test_render_story_page_related_characters_message_when_none(
    synthetic_collection,
):
    episodes = _story_episodes(synthetic_collection, "TEST_SOLO_STORY")
    page = render_story_page("TEST_SOLO_STORY", episodes, synthetic_collection)
    assert "関連するキャラクターは記録されていません。" in page


def test_render_story_page_has_unresolved_report_link(synthetic_collection):
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection)
    assert "## Review Links" in page
    assert "[Unresolved report](../reports/unresolved.md)" in page


def test_render_story_page_does_not_include_full_dialogue_text(synthetic_collection):
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection)
    assert "textExcerpt" not in page
    assert "@ChTalk" not in page
    assert "$num" not in page


# ----------------------------------------------------------------
# build_pages / write_pages (統合)
# ----------------------------------------------------------------


def test_build_pages_generates_expected_paths(synthetic_collection):
    pages = build_pages(synthetic_collection)
    assert "index.md" in pages
    assert "stories/index.md" in pages
    assert "stories/TEST_S01_C01.md" in pages
    assert "stories/PUBLIC_TEST_STORY_001.md" in pages
    assert "stories/TEST_SOLO_STORY.md" in pages
    assert "stories/EP_TEST_001.md" in pages
    assert "stories/EP_TEST_002.md" in pages
    assert "characters/index.md" in pages
    assert "characters/CHAR_TEST_RAIN.md" in pages
    assert "characters/CHAR_TEST_CONFLICT.md" in pages
    assert "reports/unresolved.md" in pages
    # canonicalIdが無いキャラクターの個別ページは生成されない
    assert "characters/UNRESOLVED_CHAR_TEST_0001.md" not in pages
    # canonicalIdはあるがstatus: mergedでないキャラクターも生成されない
    assert "characters/CHAR_TEST_DEPRECATED.md" not in pages
    # special speaker labelはCharacter pageとして生成されない
    assert "characters/UNRESOLVED_SSL_0001.md" not in pages
    assert "characters/UNRESOLVED_SSL_0002.md" not in pages


def test_build_pages_characters_index_excludes_special_speaker_labels(
    synthetic_collection,
):
    pages = build_pages(synthetic_collection)
    assert "Test Speaker A" not in pages["characters/index.md"]
    assert "？？？" not in pages["characters/index.md"]


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
    assert "characters/index.md" in pages
    assert "reports/unresolved.md" in pages
    # sourceDocumentsが空なのでepisode pageは1件も生成されない
    assert not any(
        path.startswith("stories/") and path != "stories/index.md" for path in pages
    )


def test_render_character_index_page_falls_back_to_canonical_id_for_missing_name(
    minimal_collection,
):
    """displayNameが欠落したentity (CHAR_MIN_RESOLVED) でも、
    canonicalIdをfallback表示として使いクラッシュしないことを確認する。"""
    characters = minimal_collection["entities"]["characters"]
    page = render_character_index_page(characters)
    assert "[CHAR_MIN_RESOLVED](CHAR_MIN_RESOLVED.md)" in page


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


# ----------------------------------------------------------------
# Story Summary renderer integration
# (feature/story-summary-renderer-integration)
#
# すべて合成データ (EVT_TEST_* 等のstoryId/publicStoryId・合成本文) の
# みを使う。実イベント名・実キャラ名・実あらすじ・実セリフは一切含まない。
# ----------------------------------------------------------------


def _raw_summary_document(**overrides) -> dict:
    data = {
        "schemaVersion": "0.1.0",
        "documentType": "story_summary",
        "storyId": "TEST_S01_C01",
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


def _summary_lookup(*raw_documents: dict) -> StorySummaryLookup:
    collection = StorySummaryCollection(
        documents=[parse_story_summary_document(d) for d in raw_documents]
    )
    return build_story_summary_lookup(collection)


def _story_summary_section(page: str) -> str:
    return page.split("## Story Summary", 1)[1].split("## Episode Summaries", 1)[0]


def _episode_summaries_section(page: str) -> str:
    return page.split("## Episode Summaries", 1)[1].split("## Episodes", 1)[0]


def test_story_summary_lookup_none_keeps_placeholder(synthetic_collection):
    """summary未指定 (story_summary_lookup省略) 時、Story Summaryは
    従来通り「未生成」のまま。"""
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection)
    assert "未生成" in _story_summary_section(page)


def test_reviewed_story_summary_is_displayed(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={"text": "合成reviewed Story Summaryの本文です。"}
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    assert "合成reviewed Story Summaryの本文です。" in _story_summary_section(page)


def test_approved_story_summary_is_displayed(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={"text": "合成approved Story Summaryの本文です。"},
            review={
                "status": "approved",
                "reviewer": None,
                "reviewedAt": None,
                "notes": None,
            },
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    assert "合成approved Story Summaryの本文です。" in _story_summary_section(page)


def test_unreviewed_story_summary_is_not_displayed(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={"text": "この本文は表示されないはずです。"},
            review={
                "status": "unreviewed",
                "reviewer": None,
                "reviewedAt": None,
                "notes": None,
            },
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _story_summary_section(page)
    assert "未生成" in section
    assert "この本文は表示されないはずです。" not in section


@pytest.mark.parametrize("status", ["rejected", "needs_revision"])
def test_rejected_and_needs_revision_story_summary_is_not_displayed(
    synthetic_collection, status
):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={"text": "この本文は表示されないはずです。"},
            review={
                "status": status,
                "reviewer": None,
                "reviewedAt": None,
                "notes": None,
            },
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _story_summary_section(page)
    assert "未生成" in section
    assert "この本文は表示されないはずです。" not in section


def test_deprecated_generation_status_is_not_displayed(synthetic_collection):
    """review.statusはreviewedでも、generationStatusがdeprecatedなら
    表示しない。"""
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={"text": "この本文は表示されないはずです。"},
            generationStatus="deprecated",
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _story_summary_section(page)
    assert "未生成" in section
    assert "この本文は表示されないはずです。" not in section


def test_draft_generation_status_is_not_displayed(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={"text": "この本文は表示されないはずです。"},
            generationStatus="draft",
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _story_summary_section(page)
    assert "未生成" in section
    assert "この本文は表示されないはずです。" not in section


def test_reviewed_episode_summary_is_displayed(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            episodeSummaries=[
                {
                    "episodeId": "EP_TEST_001",
                    "publicEpisodeId": None,
                    "episodeNumber": 1,
                    "text": "合成reviewed Episode Summaryの本文です。",
                    "confidence": None,
                    "evidenceRefs": [],
                }
            ]
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _episode_summaries_section(page)
    assert "合成reviewed Episode Summaryの本文です。" in section
    # EP_TEST_001以外の4episodeはsummary未登録のまま「未生成」
    assert section.count("未生成") == 4


def test_episode_without_summary_shows_missing_placeholder(synthetic_collection):
    lookup = _summary_lookup(_raw_summary_document(episodeSummaries=[]))
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _episode_summaries_section(page)
    assert section.count("未生成") == 5


def test_episode_summary_matches_by_episode_id(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            episodeSummaries=[
                {
                    "episodeId": "EP_TEST_002",
                    "publicEpisodeId": None,
                    "text": "episodeId照合で表示される本文です。",
                }
            ]
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    assert "episodeId照合で表示される本文です。" in _episode_summaries_section(page)


def test_episode_summary_matches_by_public_episode_id(synthetic_collection):
    """publicEpisodeIdが設定されたepisode (EP_TEST_PUBLIC_001 /
    PUBLIC_TEST_STORY_001_E01) について、publicEpisodeId照合で
    Episode Summaryが表示されることを確認する。"""
    lookup = _summary_lookup(
        _raw_summary_document(
            storyId="TEST_PUBLIC_ID_STORY",
            publicStoryId="PUBLIC_TEST_STORY_001",
            episodeSummaries=[
                {
                    "episodeId": "NOT_THE_SAME_EPISODE_ID",
                    "publicEpisodeId": "PUBLIC_TEST_STORY_001_E01",
                    "text": "publicEpisodeId照合で表示される本文です。",
                }
            ],
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_PUBLIC_ID_STORY")
    page = render_story_page(
        "TEST_PUBLIC_ID_STORY", episodes, synthetic_collection, lookup
    )
    assert "publicEpisodeId照合で表示される本文です。" in _episode_summaries_section(
        page
    )


def test_story_summary_matches_by_story_id(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            storyId="TEST_S01_C01",
            storySummary={"text": "storyId照合で表示される本文です。"},
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    assert "storyId照合で表示される本文です。" in _story_summary_section(page)


def test_story_summary_matches_by_public_story_id(synthetic_collection):
    """storyIdが一致しなくても、publicStoryIdが一致すれば表示される
    (TEST_PUBLIC_ID_STORY / PUBLIC_TEST_STORY_001)。"""
    lookup = _summary_lookup(
        _raw_summary_document(
            storyId="NOT_THE_SAME_STORY_ID",
            publicStoryId="PUBLIC_TEST_STORY_001",
            storySummary={"text": "publicStoryId照合で表示される本文です。"},
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_PUBLIC_ID_STORY")
    page = render_story_page(
        "TEST_PUBLIC_ID_STORY", episodes, synthetic_collection, lookup
    )
    assert "publicStoryId照合で表示される本文です。" in _story_summary_section(page)


def test_conflicting_story_id_and_public_story_id_summary_is_not_displayed(
    synthetic_collection,
):
    """storyId一致のdocumentとpublicStoryId一致のdocumentが異なる場合、
    矛盾として安全側に倒しどちらも表示しない。"""
    lookup = _summary_lookup(
        _raw_summary_document(
            storyId="TEST_S01_C01",
            publicStoryId="SOME_OTHER_PUBLIC_ID",
            storySummary={"text": "storyId側の本文（表示されないはず）。"},
        ),
        _raw_summary_document(
            storyId="TEST_PUBLIC_ID_STORY",
            publicStoryId="PUBLIC_TEST_STORY_001",
            storySummary={"text": "別ドキュメントのpublicStoryId側の本文。"},
        ),
    )
    # TEST_S01_C01のepisodesにpublicStoryId: PUBLIC_TEST_STORY_001を
    # 意図的に付与し、storyId一致(1件目)とpublicStoryId一致(2件目)が
    # 別ドキュメントを指す矛盾状態を作る。
    episodes = [
        {**doc, "publicStoryId": "PUBLIC_TEST_STORY_001"}
        for doc in _story_episodes(synthetic_collection, "TEST_S01_C01")
    ]
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _story_summary_section(page)
    assert "未生成" in section
    assert "本文（表示されないはず）" not in section
    assert "別ドキュメントのpublicStoryId側の本文。" not in section


def test_story_summary_lookup_does_not_affect_character_page(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(storySummary={"text": "合成Story Summary本文。"})
    )
    pages = build_pages(synthetic_collection, story_summary_lookup=lookup)
    character_page = pages["characters/CHAR_TEST_RAIN.md"]
    assert "合成Story Summary本文。" not in character_page
    assert "## 基本プロフィール" in character_page


def test_story_summary_lookup_does_not_affect_characters_index(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(storySummary={"text": "合成Story Summary本文。"})
    )
    pages = build_pages(synthetic_collection, story_summary_lookup=lookup)
    assert "合成Story Summary本文。" not in pages["characters/index.md"]


def test_story_summary_lookup_does_not_affect_unresolved_report(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(storySummary={"text": "合成Story Summary本文。"})
    )
    pages = build_pages(synthetic_collection, story_summary_lookup=lookup)
    assert "合成Story Summary本文。" not in pages["reports/unresolved.md"]


def test_story_summary_lookup_does_not_affect_episode_page(synthetic_collection):
    """Episode pageへのSummary表示はこのPRでは対象外
    (story-summary-renderer-integration Non-goals)。"""
    lookup = _summary_lookup(
        _raw_summary_document(
            episodeSummaries=[
                {"episodeId": "EP_TEST_001", "text": "合成Episode Summary本文。"}
            ]
        )
    )
    pages = build_pages(synthetic_collection, story_summary_lookup=lookup)
    episode_page = pages["stories/EP_TEST_001.md"]
    assert "合成Episode Summary本文。" not in episode_page
    assert "本文セリフはこのページに掲載しません" in episode_page


def test_build_pages_with_story_summary_lookup_generates_same_page_set(
    synthetic_collection,
):
    """story_summary_lookup指定時も、生成されるページの集合自体は
    変わらないことを確認する。"""
    lookup = _summary_lookup(_raw_summary_document())
    without_summaries = set(build_pages(synthetic_collection).keys())
    with_summaries = set(
        build_pages(synthetic_collection, story_summary_lookup=lookup).keys()
    )
    assert without_summaries == with_summaries


def test_render_story_page_does_not_crash_on_none_or_blank_summary_text(
    synthetic_collection,
):
    """summary textがNone/空文字/whitespaceのみの場合、rendererが
    落ちずに「未生成」を表示することを確認する (raw値の安全策)。"""
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={"text": "   "},
            episodeSummaries=[{"episodeId": "EP_TEST_001", "text": ""}],
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    assert "未生成" in _story_summary_section(page)
    assert "未生成" in _episode_summaries_section(page)


# ----------------------------------------------------------------
# Story Summary / Episode Summary evidenceRefs display
# (feature/story-summary-evidence-display)
#
# すべて合成データ (EVT_TEST_* 等のstoryId/publicStoryId・合成evidenceId)
# のみを使う。実イベント名・実キャラ名・実あらすじ・実セリフ・実DEC由来
# evidenceIdは一切含まない。
# ----------------------------------------------------------------


def test_reviewed_story_summary_evidence_refs_are_displayed(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "合成Story Summary本文。",
                "evidenceRefs": [
                    "TEST_S01_C01_E01_DLG0001",
                    "TEST_S01_C01_E02_DLG0002",
                ],
            }
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _story_summary_section(page)
    assert (
        "Evidence refs: `TEST_S01_C01_E01_DLG0001`, `TEST_S01_C01_E02_DLG0002`"
        in section
    )


def test_approved_story_summary_evidence_refs_are_displayed(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "合成Story Summary本文。",
                "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
            },
            review={
                "status": "approved",
                "reviewer": None,
                "reviewedAt": None,
                "notes": None,
            },
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    assert "Evidence refs: `TEST_S01_C01_E01_DLG0001`" in _story_summary_section(page)


def test_story_summary_without_evidence_refs_shows_nothing_extra(
    synthetic_collection,
):
    """evidenceRefsが空の場合、Evidence refs行自体を表示しない (案A)。"""
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={"text": "合成Story Summary本文。", "evidenceRefs": []}
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _story_summary_section(page)
    assert "合成Story Summary本文。" in section
    assert "Evidence refs" not in section


def test_unreviewed_story_summary_evidence_refs_are_not_displayed(
    synthetic_collection,
):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "この本文は表示されないはずです。",
                "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
            },
            review={
                "status": "unreviewed",
                "reviewer": None,
                "reviewedAt": None,
                "notes": None,
            },
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _story_summary_section(page)
    assert "未生成" in section
    assert "TEST_S01_C01_E01_DLG0001" not in section
    assert "Evidence refs" not in section


@pytest.mark.parametrize("status", ["rejected", "needs_revision"])
def test_rejected_and_needs_revision_story_summary_evidence_refs_not_displayed(
    synthetic_collection, status
):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "この本文は表示されないはずです。",
                "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
            },
            review={
                "status": status,
                "reviewer": None,
                "reviewedAt": None,
                "notes": None,
            },
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _story_summary_section(page)
    assert "未生成" in section
    assert "Evidence refs" not in section


@pytest.mark.parametrize("generation_status", ["draft", "deprecated"])
def test_draft_and_deprecated_generation_status_evidence_refs_not_displayed(
    synthetic_collection, generation_status
):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "この本文は表示されないはずです。",
                "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
            },
            generationStatus=generation_status,
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _story_summary_section(page)
    assert "未生成" in section
    assert "Evidence refs" not in section


def test_story_summary_evidence_refs_not_displayed_when_text_blank(
    synthetic_collection,
):
    """evidenceRefsだけがあってtextが空の場合、Story Summaryとしては
    「未生成」のままであり、evidenceRefsも表示しない
    (Story_Summary_Design.md §9・placeholder状態ではevidenceRefsを
    表示しない方針)。"""
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "   ",
                "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
            }
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _story_summary_section(page)
    assert "未生成" in section
    assert "Evidence refs" not in section


def test_reviewed_episode_summary_evidence_refs_are_displayed(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            episodeSummaries=[
                {
                    "episodeId": "EP_TEST_001",
                    "text": "合成Episode Summary本文。",
                    "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
                }
            ]
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _episode_summaries_section(page)
    assert "Evidence refs: `TEST_S01_C01_E01_DLG0001`" in section


def test_episode_summary_evidence_refs_match_by_public_episode_id(
    synthetic_collection,
):
    lookup = _summary_lookup(
        _raw_summary_document(
            storyId="TEST_PUBLIC_ID_STORY",
            publicStoryId="PUBLIC_TEST_STORY_001",
            episodeSummaries=[
                {
                    "episodeId": "NOT_THE_SAME_EPISODE_ID",
                    "publicEpisodeId": "PUBLIC_TEST_STORY_001_E01",
                    "text": "publicEpisodeId照合のEpisode Summary本文。",
                    "evidenceRefs": ["TEST_PUBLIC_ID_STORY_E01_DLG0001"],
                }
            ],
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_PUBLIC_ID_STORY")
    page = render_story_page(
        "TEST_PUBLIC_ID_STORY", episodes, synthetic_collection, lookup
    )
    section = _episode_summaries_section(page)
    assert "Evidence refs: `TEST_PUBLIC_ID_STORY_E01_DLG0001`" in section


def test_episode_without_summary_does_not_show_evidence_refs(synthetic_collection):
    """summaryが無いEpisodeは「未生成」のみで、Evidence refs行は
    表示されない。"""
    lookup = _summary_lookup(_raw_summary_document(episodeSummaries=[]))
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _episode_summaries_section(page)
    assert "Evidence refs" not in section


def test_episode_evidence_refs_do_not_leak_between_episodes(synthetic_collection):
    """Episode 1のevidenceRefsがEpisode 2以降に混ざらないことを確認する。"""
    lookup = _summary_lookup(
        _raw_summary_document(
            episodeSummaries=[
                {
                    "episodeId": "EP_TEST_001",
                    "text": "Episode 1の本文。",
                    "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
                },
                {
                    "episodeId": "EP_TEST_002",
                    "text": "Episode 2の本文。",
                    "evidenceRefs": ["TEST_S01_C01_E02_DLG0002"],
                },
            ]
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _episode_summaries_section(page)
    ep1_block = section.split("### Episode 2", 1)[0]
    ep2_block = section.split("### Episode 2", 1)[1]
    assert "TEST_S01_C01_E01_DLG0001" in ep1_block
    assert "TEST_S01_C01_E02_DLG0002" not in ep1_block
    assert "TEST_S01_C01_E02_DLG0002" in ep2_block
    assert "TEST_S01_C01_E01_DLG0001" not in ep2_block


def test_evidence_refs_are_backtick_quoted(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "合成Story Summary本文。",
                "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
            }
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    assert "`TEST_S01_C01_E01_DLG0001`" in page


def test_evidence_refs_display_does_not_leak_raw_text(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "合成Story Summary本文。",
                "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
            },
            episodeSummaries=[
                {
                    "episodeId": "EP_TEST_001",
                    "text": "合成Episode Summary本文。",
                    "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
                }
            ],
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    assert ".dec" not in page
    assert "@ChTalk" not in page
    assert "$num" not in page
    assert "C:\\" not in page
    assert "D:\\" not in page


def test_evidence_refs_deduplicated_and_order_preserved(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "合成Story Summary本文。",
                "evidenceRefs": [
                    "TEST_S01_C01_E02_DLG0002",
                    "TEST_S01_C01_E01_DLG0001",
                    "TEST_S01_C01_E02_DLG0002",
                ],
            }
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _story_summary_section(page)
    assert (
        "Evidence refs: `TEST_S01_C01_E02_DLG0002`, `TEST_S01_C01_E01_DLG0001`"
        in section
    )


def test_evidence_refs_ignores_non_string_entries(synthetic_collection):
    """evidenceRefs内に非文字列・空文字・whitespaceが混ざっていても
    rendererが落ちずに安全にfallbackすることを確認する。"""
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "合成Story Summary本文。",
                "evidenceRefs": ["", "   ", "TEST_S01_C01_E01_DLG0001", None, 123],
            }
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection, lookup)
    section = _story_summary_section(page)
    assert "Evidence refs: `TEST_S01_C01_E01_DLG0001`" in section


def test_evidence_refs_display_does_not_affect_episode_page(synthetic_collection):
    """Episode pageへのevidenceRefs表示はこのPRでは対象外
    (story-summary-evidence-display Non-goals)。"""
    lookup = _summary_lookup(
        _raw_summary_document(
            episodeSummaries=[
                {
                    "episodeId": "EP_TEST_001",
                    "text": "合成Episode Summary本文。",
                    "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
                }
            ]
        )
    )
    pages = build_pages(synthetic_collection, story_summary_lookup=lookup)
    episode_page = pages["stories/EP_TEST_001.md"]
    assert "Evidence refs" not in episode_page
    assert "TEST_S01_C01_E01_DLG0001" not in episode_page


# ----------------------------------------------------------------
# Evidence Index renderer integration
# (feature/evidence-index-renderer-integration)
#
# すべて合成データ (TEST_* 等のstoryId/evidenceId) のみを使う。実イベント名・
# 実キャラ名・実あらすじ・実セリフ・実DEC由来evidenceIdは一切含まない。
# ----------------------------------------------------------------


def _raw_evidence_entry(**overrides) -> dict:
    entry = {
        "evidenceId": "TEST_S01_C01_E01_DLG0001",
        "evidenceType": "dialogue",
        "storyId": "TEST_S01_C01",
        "publicStoryId": None,
        "episodeId": "EP_TEST_001",
        "publicEpisodeId": None,
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


def _raw_evidence_document(**overrides) -> dict:
    data = {
        "evidenceIndexVersion": 1,
        "generatedFrom": None,
        "entries": [_raw_evidence_entry()],
        "notes": None,
    }
    data.update(overrides)
    return data


def _evidence_lookup(*raw_documents: dict) -> EvidenceIndexLookup:
    collection = EvidenceIndexCollection(
        documents=[parse_evidence_index_document(d) for d in raw_documents]
    )
    return build_evidence_index_lookup(collection)


def test_evidence_ref_stays_plain_id_when_lookup_not_provided(synthetic_collection):
    summary_lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "合成Story Summary本文。",
                "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
            }
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page(
        "TEST_S01_C01", episodes, synthetic_collection, summary_lookup
    )
    section = _story_summary_section(page)
    assert "Evidence refs: `TEST_S01_C01_E01_DLG0001`" in section
    assert "](.." not in section


def test_story_summary_evidence_ref_is_linked_when_present(synthetic_collection):
    summary_lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "合成Story Summary本文。",
                "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
            }
        )
    )
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page(
        "TEST_S01_C01",
        episodes,
        synthetic_collection,
        summary_lookup,
        evidence_lookup,
    )
    section = _story_summary_section(page)
    assert (
        "Evidence refs: [`TEST_S01_C01_E01_DLG0001`]"
        "(../evidence/TEST_S01_C01.md#test_s01_c01_e01_dlg0001)" in section
    )


def test_episode_summary_evidence_ref_is_linked_when_present(synthetic_collection):
    summary_lookup = _summary_lookup(
        _raw_summary_document(
            episodeSummaries=[
                {
                    "episodeId": "EP_TEST_001",
                    "text": "合成Episode Summary本文。",
                    "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
                }
            ]
        )
    )
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page(
        "TEST_S01_C01",
        episodes,
        synthetic_collection,
        summary_lookup,
        evidence_lookup,
    )
    section = _episode_summaries_section(page)
    assert (
        "Evidence refs: [`TEST_S01_C01_E01_DLG0001`]"
        "(../evidence/TEST_S01_C01.md#test_s01_c01_e01_dlg0001)" in section
    )


def test_unresolved_evidence_ref_is_not_linked(synthetic_collection):
    """Evidence Indexに存在しないevidenceRefは、リンクせずID表示のまま
    (unresolved扱い、errorにしない)。"""
    summary_lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "合成Story Summary本文。",
                "evidenceRefs": ["NOT_IN_EVIDENCE_INDEX"],
            }
        )
    )
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page(
        "TEST_S01_C01",
        episodes,
        synthetic_collection,
        summary_lookup,
        evidence_lookup,
    )
    section = _story_summary_section(page)
    assert "Evidence refs: `NOT_IN_EVIDENCE_INDEX`" in section
    assert "](.." not in section


# ----------------------------------------------------------------
# Summary evidenceRefs link text: publicEvidenceId優先
# (feature/evidence-index-public-id-renderer-switch)
# ----------------------------------------------------------------


def test_evidence_ref_link_text_uses_public_evidence_id_when_present(
    synthetic_collection,
):
    """Summaryのevidenceref文字列自体は内部evidenceId (`TEST_S01_C01_E01_
    DLG0001`) のままでも、解決先entryにpublicEvidenceIdがあれば表示
    テキスト・anchorはpublicEvidenceId優先に切り替わる。"""
    summary_lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "合成Story Summary本文。",
                "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
            }
        )
    )
    evidence_lookup = _evidence_lookup(
        _raw_evidence_document(
            entries=[
                _raw_evidence_entry(
                    evidenceId="TEST_S01_C01_E01_DLG0001",
                    publicEvidenceId="EVT_TEST_001_E01_DLG0001",
                    storyId="TEST_S01_C01",
                    publicStoryId="EVT_TEST_001",
                )
            ]
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page(
        "TEST_S01_C01",
        episodes,
        synthetic_collection,
        summary_lookup,
        evidence_lookup,
    )
    section = _story_summary_section(page)
    assert (
        "Evidence refs: [`EVT_TEST_001_E01_DLG0001`]"
        "(../evidence/EVT_TEST_001.md#evt_test_001_e01_dlg0001)" in section
    )
    assert "TEST_S01_C01_E01_DLG0001" not in section


def test_evidence_ref_resolves_when_summary_ref_is_already_public_evidence_id(
    synthetic_collection,
):
    """Summaryのevidenceref文字列がすでにpublicEvidenceId値そのもの
    (Public-safe projection output style、evidenceId==publicEvidenceId)
    でも解決・リンク化できる。"""
    summary_lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "合成Story Summary本文。",
                "evidenceRefs": ["EVT_TEST_001_E01_DLG0001"],
            }
        )
    )
    evidence_lookup = _evidence_lookup(
        _raw_evidence_document(
            entries=[
                _raw_evidence_entry(
                    evidenceId="EVT_TEST_001_E01_DLG0001",
                    publicEvidenceId="EVT_TEST_001_E01_DLG0001",
                    storyId="EVT_TEST_001",
                    publicStoryId="EVT_TEST_001",
                )
            ]
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page(
        "TEST_S01_C01",
        episodes,
        synthetic_collection,
        summary_lookup,
        evidence_lookup,
    )
    section = _story_summary_section(page)
    assert (
        "Evidence refs: [`EVT_TEST_001_E01_DLG0001`]"
        "(../evidence/EVT_TEST_001.md#evt_test_001_e01_dlg0001)" in section
    )


def test_evidence_ref_still_resolves_by_internal_evidence_id_when_no_public_id(
    synthetic_collection,
):
    """publicEvidenceIdが無いentryは、従来通り内部evidenceIdで解決し
    リンク化する（後方互換のfallback）。"""
    summary_lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={
                "text": "合成Story Summary本文。",
                "evidenceRefs": ["TEST_S01_C01_E01_DLG0001"],
            }
        )
    )
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page(
        "TEST_S01_C01",
        episodes,
        synthetic_collection,
        summary_lookup,
        evidence_lookup,
    )
    section = _story_summary_section(page)
    assert (
        "Evidence refs: [`TEST_S01_C01_E01_DLG0001`]"
        "(../evidence/TEST_S01_C01.md#test_s01_c01_e01_dlg0001)" in section
    )


def test_render_evidence_page_has_front_matter_and_title():
    document = parse_evidence_index_document(_raw_evidence_document())
    page = render_evidence_page("TEST_S01_C01", document.entries)
    assert page.startswith("---\n")
    assert 'page_type: "evidence"' in page
    assert 'story_id: "TEST_S01_C01"' in page
    assert "# Evidence: TEST_S01_C01" in page


def test_render_evidence_page_title_uses_public_story_id_when_present():
    document = parse_evidence_index_document(
        _raw_evidence_document(
            entries=[
                _raw_evidence_entry(
                    storyId="TEST_S01_C01", publicStoryId="EVT_TEST_PUBLIC_001"
                )
            ]
        )
    )
    page = render_evidence_page("TEST_S01_C01", document.entries)
    assert "# Evidence: EVT_TEST_PUBLIC_001" in page


# ----------------------------------------------------------------
# Evidence page entry heading / anchor: publicEvidenceId優先
# (feature/evidence-index-public-id-renderer-switch)
# ----------------------------------------------------------------


def test_evidence_entry_heading_uses_public_evidence_id_when_present():
    document = parse_evidence_index_document(
        _raw_evidence_document(
            entries=[
                _raw_evidence_entry(
                    evidenceId="INTERNAL_TEST_EVD_001",
                    publicEvidenceId="EVT_TEST_001_E01_DLG0001",
                )
            ]
        )
    )
    page = render_evidence_page("TEST_S01_C01", document.entries)
    assert "### EVT_TEST_001_E01_DLG0001" in page
    assert "### INTERNAL_TEST_EVD_001" not in page
    assert "INTERNAL_TEST_EVD_001" not in page


def test_evidence_entry_heading_falls_back_to_evidence_id_when_public_missing():
    document = parse_evidence_index_document(
        _raw_evidence_document(
            entries=[_raw_evidence_entry(evidenceId="TEST_S01_C01_E01_DLG0001")]
        )
    )
    page = render_evidence_page("TEST_S01_C01", document.entries)
    assert "### TEST_S01_C01_E01_DLG0001" in page


def test_evidence_page_public_safe_style_entry_does_not_expose_internal_ids(
    synthetic_collection,
):
    """Public-safe projection output相当 (evidenceId/storyId/episodeIdの
    値がpublicEvidenceId/publicStoryId/publicEpisodeIdと同一、sceneId/
    blockIdなし) をrenderした場合、Evidence pageに内部IDが露出しない
    ことを確認する。"""
    evidence_lookup = _evidence_lookup(
        _raw_evidence_document(
            entries=[
                _raw_evidence_entry(
                    evidenceId="EVT_TEST_001_E01_DLG0001",
                    publicEvidenceId="EVT_TEST_001_E01_DLG0001",
                    storyId="EVT_TEST_001",
                    publicStoryId="EVT_TEST_001",
                    episodeId="EVT_TEST_001_E01",
                    publicEpisodeId="EVT_TEST_001_E01",
                    sceneId=None,
                    blockId=None,
                )
            ]
        )
    )
    pages = build_pages(synthetic_collection, evidence_index_lookup=evidence_lookup)
    evidence_page = pages["evidence/EVT_TEST_001.md"]
    assert "### EVT_TEST_001_E01_DLG0001" in evidence_page
    assert "EVT_TEST_001" in evidence_page  # public IDs are expected to appear


def test_evidence_page_is_generated_for_story_with_evidence(synthetic_collection):
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    pages = build_pages(synthetic_collection, evidence_index_lookup=evidence_lookup)
    assert "evidence/TEST_S01_C01.md" in pages


def test_evidence_page_path_uses_public_story_id_from_evidence_entries(
    synthetic_collection,
):
    evidence_lookup = _evidence_lookup(
        _raw_evidence_document(
            entries=[
                _raw_evidence_entry(
                    storyId="TEST_S01_C01", publicStoryId="EVT_TEST_PUBLIC_001"
                )
            ]
        )
    )
    pages = build_pages(synthetic_collection, evidence_index_lookup=evidence_lookup)
    assert "evidence/EVT_TEST_PUBLIC_001.md" in pages
    assert "evidence/TEST_S01_C01.md" not in pages


def test_evidence_page_not_generated_for_story_without_evidence(synthetic_collection):
    """Evidence Indexに含まれないstoryのEvidence pageは生成されない。"""
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    pages = build_pages(synthetic_collection, evidence_index_lookup=evidence_lookup)
    assert "evidence/TEST_SOLO_STORY.md" not in pages


def test_story_page_review_links_includes_evidence_link_when_available(
    synthetic_collection,
):
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page(
        "TEST_S01_C01", episodes, synthetic_collection, None, evidence_lookup
    )
    assert "- [Evidence index](../evidence/TEST_S01_C01.md)" in page


def test_story_page_review_links_resolves_evidence_link_via_public_story_id(
    synthetic_collection,
):
    """Public-safe projection output相当のEvidence Index (内部storyId自体が
    publicStoryIdの値へ置換されている) を渡した場合でも、merged knowledge
    collection側の`publicStoryId`経由でEvidence indexへのReview Linksが
    解決できることを確認する (`resolve_story_evidence_entries`、
    feature/evidence-index-public-id-renderer-switch)。story
    `TEST_PUBLIC_ID_STORY`はfixture内で`publicStoryId: PUBLIC_TEST_STORY_001`
    を持つ。"""
    evidence_lookup = _evidence_lookup(
        _raw_evidence_document(
            entries=[
                _raw_evidence_entry(
                    evidenceId="PUBLIC_TEST_STORY_001_E01_DLG0001",
                    publicEvidenceId="PUBLIC_TEST_STORY_001_E01_DLG0001",
                    storyId="PUBLIC_TEST_STORY_001",
                    publicStoryId="PUBLIC_TEST_STORY_001",
                    episodeId="PUBLIC_TEST_STORY_001_E01",
                    publicEpisodeId="PUBLIC_TEST_STORY_001_E01",
                )
            ]
        )
    )
    episodes = _story_episodes(synthetic_collection, "TEST_PUBLIC_ID_STORY")
    page = render_story_page(
        "TEST_PUBLIC_ID_STORY", episodes, synthetic_collection, None, evidence_lookup
    )
    assert "- [Evidence index](../evidence/PUBLIC_TEST_STORY_001.md)" in page


def test_story_page_review_links_no_evidence_link_when_story_has_no_evidence(
    synthetic_collection,
):
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    episodes = _story_episodes(synthetic_collection, "TEST_SOLO_STORY")
    page = render_story_page(
        "TEST_SOLO_STORY", episodes, synthetic_collection, None, evidence_lookup
    )
    assert "Evidence index" not in page
    assert "[Unresolved report](../reports/unresolved.md)" in page


def test_story_page_review_links_no_evidence_link_when_lookup_absent(
    synthetic_collection,
):
    episodes = _story_episodes(synthetic_collection, "TEST_S01_C01")
    page = render_story_page("TEST_S01_C01", episodes, synthetic_collection)
    assert "Evidence index" not in page


def test_evidence_page_shows_entry_fields(synthetic_collection):
    evidence_lookup = _evidence_lookup(
        _raw_evidence_document(
            entries=[
                _raw_evidence_entry(
                    publicEpisodeId="EVT_TEST_PUBLIC_001_E01",
                    sceneId="TEST_S01_C01_E01_SC001",
                    blockId="TEST_S01_C01_E01_DLG0001",
                    speaker={
                        "speakerId": "CHAR_TEST_001",
                        "displayName": "Synthetic Speaker",
                        "resolutionStatus": "resolved",
                    },
                    relatedEntities=[
                        {
                            "entityType": "character",
                            "id": "CHAR_TEST_001",
                            "displayName": "Synthetic Speaker",
                        }
                    ],
                    referencedBy={
                        "summaries": [
                            {
                                "storyId": "TEST_S01_C01",
                                "summaryType": "episode",
                                "episodeId": "EP_TEST_001",
                            }
                        ],
                        "candidates": [],
                    },
                )
            ]
        )
    )
    pages = build_pages(synthetic_collection, evidence_index_lookup=evidence_lookup)
    evidence_page = pages["evidence/TEST_S01_C01.md"]
    assert "### TEST_S01_C01_E01_DLG0001" in evidence_page
    assert "dialogue" in evidence_page
    assert "`EP_TEST_001`" in evidence_page
    assert "`EVT_TEST_PUBLIC_001_E01`" in evidence_page
    assert "`TEST_S01_C01_E01_SC001`" in evidence_page
    assert "Synthetic Speaker" in evidence_page
    assert "resolved" in evidence_page
    assert "character `CHAR_TEST_001`" in evidence_page
    assert "summary episode `EP_TEST_001`" in evidence_page


def test_evidence_page_overview_shows_raw_text_included_no(synthetic_collection):
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    pages = build_pages(synthetic_collection, evidence_index_lookup=evidence_lookup)
    evidence_page = pages["evidence/TEST_S01_C01.md"]
    assert "- Raw text included: No" in evidence_page


def test_evidence_page_does_not_leak_raw_text(synthetic_collection):
    evidence_lookup = _evidence_lookup(
        _raw_evidence_document(
            entries=[
                _raw_evidence_entry(
                    speaker={
                        "speakerId": "CHAR_TEST_001",
                        "displayName": "Synthetic Speaker",
                        "resolutionStatus": "resolved",
                    }
                )
            ]
        )
    )
    pages = build_pages(synthetic_collection, evidence_index_lookup=evidence_lookup)
    evidence_page = pages["evidence/TEST_S01_C01.md"]
    assert ".dec" not in evidence_page
    assert "@ChTalk" not in evidence_page
    assert "$num" not in evidence_page
    assert "C:\\" not in evidence_page
    assert "D:\\" not in evidence_page


def test_evidence_index_does_not_affect_episode_page(synthetic_collection):
    """Episode pageはEvidence Indexの影響を受けない
    (evidence-index-renderer-integration Non-goals)。"""
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    pages = build_pages(synthetic_collection, evidence_index_lookup=evidence_lookup)
    episode_page = pages["stories/EP_TEST_001.md"]
    assert "Evidence refs" not in episode_page
    assert "evidence/" not in episode_page


def test_evidence_index_does_not_affect_character_page(synthetic_collection):
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    pages = build_pages(synthetic_collection, evidence_index_lookup=evidence_lookup)
    character_page = pages["characters/CHAR_TEST_RAIN.md"]
    assert "evidence/" not in character_page


def test_evidence_index_does_not_affect_characters_index(synthetic_collection):
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    pages = build_pages(synthetic_collection, evidence_index_lookup=evidence_lookup)
    assert "evidence/" not in pages["characters/index.md"]


def test_evidence_index_does_not_affect_unresolved_report(synthetic_collection):
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    pages = build_pages(synthetic_collection, evidence_index_lookup=evidence_lookup)
    assert "evidence/" not in pages["reports/unresolved.md"]


def test_build_pages_with_evidence_index_keeps_existing_pages(synthetic_collection):
    """evidence_index_lookup指定時も、既存ページの集合は失われず
    Evidence pageのみが追加されることを確認する。"""
    without_evidence = set(build_pages(synthetic_collection).keys())
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    with_evidence = set(
        build_pages(synthetic_collection, evidence_index_lookup=evidence_lookup).keys()
    )
    assert without_evidence.issubset(with_evidence)
    assert with_evidence - without_evidence == {"evidence/TEST_S01_C01.md"}
