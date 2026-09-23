"""
tests/wiki/test_wiki_renderer.py
agents/wiki_generator/ のrenderer skeletonのユニットテスト。

すべて合成fixture (tests/fixtures/wiki/synthetic_merged_collection.json、
CHAR_TEST_RAIN等の架空ID・架空名) のみを使う。実データ由来のキャラクター
名・セリフ・ID・merged knowledge collectionは一切含まない。
"""

from __future__ import annotations

import json
from copy import deepcopy
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
    event_page_path,
    evidence_page_path,
    is_page_eligible,
    item_page_path,
    location_page_path,
    lore_page_path,
    organization_page_path,
    render_character_index_page,
    render_character_page,
    render_episode_page,
    render_event_index_page,
    render_event_page,
    render_evidence_page,
    render_index_page,
    render_item_index_page,
    render_item_page,
    render_location_index_page,
    render_location_page,
    render_lore_index_page,
    render_lore_page,
    render_organization_index_page,
    render_organization_page,
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


@pytest.fixture
def resolved_location(synthetic_collection) -> dict:
    """Location page用の合成entity。実データは含まない。"""
    unresolved = synthetic_collection["entities"]["locations"][0]
    location = deepcopy(unresolved)
    location.update(
        {
            "id": "LOC_TEST_PLAZA",
            "canonicalId": "LOC_TEST_PLAZA",
            "status": "merged",
            "displayName": "Test Plaza",
            "aliases": ["Synthetic Square"],
            "sourceTypes": ["script", "manual"],
            "confidence": 0.95,
            "sceneRefs": ["EP_TEST_001_SC001", "EP_TEST_002_SC001"],
            "extractionRunRefs": {
                "EP_TEST_001": "RUN_TEST_001",
                "EP_TEST_MISSING": "RUN_TEST_MISSING",
            },
        }
    )
    location["evidenceRefs"] = [
        {
            "evidenceId": "EV_TEST_LOCATION_001",
            "episodeId": "EP_TEST_001",
            "sceneId": "EP_TEST_001_SC001",
            "blockId": "EP_TEST_001_DLG0001",
            "textExcerpt": "SYNTHETIC RAW TEXT MUST NOT APPEAR",
        }
    ]
    location["sourceCandidates"] = [
        {
            "candidateId": "LOC_CAND_TEST_001",
            "candidateType": "location",
            "episodeId": "EP_TEST_002",
            "evidenceIds": ["EV_TEST_LOCATION_002"],
            "sourceDocumentId": "EP_TEST_002",
            "raw": "SYNTHETIC RAW PAYLOAD MUST NOT APPEAR",
        }
    ]
    return location


@pytest.fixture
def resolved_item(resolved_location) -> dict:
    """Item page用の合成entity。実データは含まない。"""
    item = deepcopy(resolved_location)
    item.update(
        {
            "id": "ITEM_TEST_COMPASS",
            "type": "item",
            "canonicalId": "ITEM_TEST_COMPASS",
            "displayName": "Test Compass",
            "aliases": ["Synthetic Navigator"],
        }
    )
    item.pop("sceneRefs", None)
    item["sourceCandidates"][0]["candidateId"] = "ITEM_CAND_TEST_001"
    item["sourceCandidates"][0]["candidateType"] = "item_candidate"
    return item


@pytest.fixture
def resolved_lore(resolved_item) -> dict:
    """Lore page用の合成entity。実データは含まない。"""
    lore = deepcopy(resolved_item)
    lore.update(
        {
            "id": "LORE_TEST_AETHER",
            "type": "lore",
            "canonicalId": "LORE_TEST_AETHER",
            "displayName": "Test Aether",
            "aliases": ["Synthetic Essence"],
        }
    )
    lore["sourceCandidates"][0]["candidateId"] = "LORE_CAND_TEST_001"
    lore["sourceCandidates"][0]["candidateType"] = "lore_candidate"
    lore["conflicts"] = []
    return lore


@pytest.fixture
def resolved_event(resolved_item) -> dict:
    """Event page用の合成entity。実データは含まない。"""
    event = deepcopy(resolved_item)
    event.update(
        {
            "id": "EVENT_TEST_LAUNCH",
            "type": "event",
            "canonicalId": "EVENT_TEST_LAUNCH",
            "displayName": "Test Launch",
            "aliases": ["Synthetic Opening"],
            "participantEntityIds": ["CHAR_TEST_RAIN"],
            "locationEntityIds": ["LOC_TEST_PLAZA"],
        }
    )
    event["sourceCandidates"][0]["candidateId"] = "EVENT_CAND_TEST_001"
    event["sourceCandidates"][0]["candidateType"] = "event_candidate"
    event["conflicts"] = []
    return event


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


def test_build_front_matter_escapes_newlines_as_single_yaml_scalar():
    front_matter = build_front_matter(
        {
            "title": "Safe\n# injected heading",
            "generated_from": "merged_knowledge_collection",
        }
    )
    assert 'title: "Safe\\n# injected heading"' in front_matter
    assert "\n# injected heading" not in front_matter


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


def test_location_page_path_uses_canonical_id(resolved_location):
    assert location_page_path(resolved_location) == "locations/LOC_TEST_PLAZA.md"


def test_location_page_path_none_for_unresolved(synthetic_collection):
    unresolved = synthetic_collection["entities"]["locations"][0]
    assert location_page_path(unresolved) is None


def test_location_page_path_includes_conflict_with_canonical_id(resolved_location):
    conflict = deepcopy(resolved_location)
    conflict["status"] = "conflict"
    assert location_page_path(conflict) == "locations/LOC_TEST_PLAZA.md"


def test_organization_page_path_uses_canonical_id():
    organization = _synthetic_public_organization()
    assert organization_page_path(organization) == "organizations/ORG_TEST_ALPHA.md"


def test_organization_page_path_none_for_unresolved():
    organization = _synthetic_public_organization(page_eligible=False)
    assert organization_page_path(organization) is None


def test_organization_page_path_rejects_unsafe_canonical_id():
    organization = _synthetic_public_organization()
    organization["canonicalId"] = "../ORG_TEST_ALPHA"
    assert organization_page_path(organization) is None


def test_page_eligibility_rejects_conflict_without_canonical_id(resolved_location):
    conflict = deepcopy(resolved_location)
    conflict.update({"status": "conflict", "canonicalId": None})
    assert is_page_eligible(conflict) is False


def test_page_eligibility_rejects_low_confidence_entity(resolved_location):
    location = deepcopy(resolved_location)
    location["confidence"] = 0.39
    assert is_page_eligible(location) is False
    assert location_page_path(location) is None


def test_page_eligibility_rejects_entity_without_evidence(resolved_location):
    location = deepcopy(resolved_location)
    location["evidenceRefs"] = []
    assert is_page_eligible(location) is False
    assert location_page_path(location) is None


def test_item_page_path_uses_canonical_id(resolved_item):
    assert item_page_path(resolved_item) == "items/ITEM_TEST_COMPASS.md"


def test_item_page_path_none_for_unresolved(resolved_item):
    item = deepcopy(resolved_item)
    item.update({"canonicalId": None, "status": "unresolved"})
    assert item_page_path(item) is None


def test_lore_page_path_uses_canonical_id(resolved_lore):
    assert lore_page_path(resolved_lore) == "lore/LORE_TEST_AETHER.md"


def test_lore_page_path_none_for_unresolved(resolved_lore):
    lore = deepcopy(resolved_lore)
    lore.update({"canonicalId": None, "status": "unresolved"})
    assert lore_page_path(lore) is None


def test_lore_page_path_rejects_unsafe_canonical_id(resolved_lore):
    lore = deepcopy(resolved_lore)
    lore["canonicalId"] = "../../outside"
    assert is_page_eligible(lore) is False
    assert lore_page_path(lore) is None


def test_event_page_path_uses_canonical_id(resolved_event):
    assert event_page_path(resolved_event) == "events/EVENT_TEST_LAUNCH.md"


def test_event_page_path_none_for_unresolved(resolved_event):
    event = deepcopy(resolved_event)
    event.update({"canonicalId": None, "status": "unresolved"})
    assert event_page_path(event) is None


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


def test_episode_page_path_rejects_unsafe_public_episode_id():
    source_document = {
        "episodeId": "EP_TEST_SAFE_FALLBACK",
        "publicEpisodeId": "../outside",
    }
    assert episode_page_path(source_document) is None


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
    assert "- Source types: script" in page
    assert 'source_types: "script"' in page


def test_render_character_page_shows_confidence(resolved_character):
    page = render_character_page(resolved_character)
    assert "- Confidence: 0.9" in page
    assert 'confidence: "0.9"' in page


def test_render_character_page_details_use_narrow_lists(
    resolved_character, character_profiles_index
):
    page = render_character_page(resolved_character, character_profiles_index)
    summary = page.split("## Summary\n\n", 1)[1].split("## 基本プロフィール", 1)[0]
    profile = page.split("## 基本プロフィール\n\n", 1)[1].split("### 自己紹介", 1)[0]

    assert "| 項目 | 値 |" not in summary + profile
    assert summary.index("- Entity ID: CHAR_TEST_RAIN") < summary.index(
        "- Source types: script"
    )
    assert profile.index("- 名前: Test Character Rain") < profile.index(
        "- Status: confirmed"
    )


def test_render_character_page_details_escape_untrusted_values(
    resolved_character, character_profiles_index
):
    resolved_character["sourceTypes"] = ["script*", "<img>"]
    profile = character_profiles_index["CHAR_TEST_RAIN"]
    profile.display_name = "Test *Rain* <img>"
    profile.profile_highlight = ProfileHighlight(label="趣味 [A]", value="<script>")

    page = render_character_page(resolved_character, character_profiles_index)
    details = page.split("## Summary\n\n", 1)[1].split("### 自己紹介", 1)[0]

    assert "- Source types: script\\*, &lt;img&gt;" in details
    assert "- 名前: Test \\*Rain\\* &lt;img&gt;" in details
    assert "- 特記事項: 【趣味 \\[A\\]】&lt;script&gt;" in details
    assert "<img>" not in details
    assert "<script>" not in details


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


def _synthetic_public_organization(
    *, entity_id: str = "ORG_ENTITY_TEST_ALPHA", page_eligible: bool = True
) -> dict:
    return {
        "id": entity_id,
        "type": "organization",
        "canonicalId": "ORG_TEST_ALPHA" if page_eligible else None,
        "displayName": "Test Organization Alpha",
        "aliases": ["Test Org Alpha"],
        "status": "merged" if page_eligible else "unresolved",
        "sourceTypes": ["script"],
        "confidence": 0.9,
        "evidenceRefs": [{"evidenceId": "EVIDENCE_TEST_ORG_001"}],
        "sourceCandidates": [],
        "extractionRunRefs": {},
        "conflicts": [],
    }


def _synthetic_public_relationship(
    *,
    relationship_id: str = "REL_TEST_MEMBER_OF_SCRIPT",
    target_entity_id: str = "ORG_ENTITY_TEST_ALPHA",
    publication_status: str = "eligible",
    relationship_type: str = "member_of",
    source_type: str = "script",
) -> dict:
    return {
        "id": relationship_id,
        "sourceEntityId": "CHAR_TEST_RAIN",
        "targetEntityId": target_entity_id,
        "sourceEntityType": "character",
        "targetEntityType": "organization",
        "relationshipType": relationship_type,
        "normalizedRelationshipType": relationship_type,
        "taxonomyState": "formal_v1",
        "direction": "source_to_target",
        "sourceType": source_type,
        "publicationStatus": publication_status,
        "temporalNote": "Synthetic period only",
        "evidenceRefs": [
            {"evidenceId": "EVIDENCE_TEST_REL_001"},
            {"evidenceId": "EVIDENCE_TEST_REL_002"},
        ],
    }


def test_render_character_page_shows_public_relationship(resolved_character):
    organization = _synthetic_public_organization()
    relationship = _synthetic_public_relationship()

    page = render_character_page(
        resolved_character,
        relationships=[relationship],
        organizations=[organization],
    )

    assert "## Relationships" in page
    assert (
        "**所属**: [Test Organization Alpha]"
        "(../organizations/ORG_TEST_ALPHA.md)" in page
    )
    assert "Direction: source_to_target" in page
    assert "Source: 本文抽出" in page
    assert "Evidence: 2 件" in page
    assert "Temporal note: Synthetic period only" in page
    assert "REL_TEST_MEMBER_OF_SCRIPT" not in page


def test_render_character_page_shows_affiliated_manual_label(resolved_character):
    relationship = _synthetic_public_relationship(
        relationship_type="affiliated_with", source_type="manual"
    )
    page = render_character_page(
        resolved_character,
        relationships=[relationship],
        organizations=[_synthetic_public_organization()],
    )

    assert "**関係あり（所属未確定）**" in page
    assert "Source: 人間確認済み" in page


def test_render_character_page_hides_review_required_relationship(
    resolved_character,
):
    relationship = _synthetic_public_relationship(
        publication_status="review_required",
        relationship_type="unrecognized_test_relationship",
    )
    page = render_character_page(
        resolved_character,
        relationships=[relationship],
        organizations=[_synthetic_public_organization()],
    )

    assert "公開可能な関係は記録されていません。" in page
    assert "unrecognized_test_relationship" not in page
    assert "Test Organization Alpha" not in page


def test_render_character_page_does_not_expose_unpublished_counterpart_id(
    resolved_character,
):
    target_id = "INTERNAL_ORG_TEST_UNPUBLISHED"
    relationship = _synthetic_public_relationship(target_entity_id=target_id)
    organization = _synthetic_public_organization(
        entity_id=target_id, page_eligible=False
    )
    page = render_character_page(
        resolved_character,
        relationships=[relationship],
        organizations=[organization],
    )

    assert "**所属**: 関連先の個別ページは未公開です" in page
    assert target_id not in page
    assert "Test Organization Alpha" not in page


def test_render_character_page_ignores_relationship_for_another_character(
    resolved_character,
):
    relationship = _synthetic_public_relationship()
    relationship["sourceEntityId"] = "CHAR_TEST_OTHER"
    page = render_character_page(
        resolved_character,
        relationships=[relationship],
        organizations=[_synthetic_public_organization()],
    )

    assert "公開可能な関係は記録されていません。" in page
    assert "Test Organization Alpha" not in page


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("normalizedRelationshipType", "unknown_public_type"),
        ("taxonomyState", "provisional"),
        ("taxonomyState", "unrecognized"),
        ("sourceType", "ai_inferred"),
        ("direction", "bidirectional"),
        ("sourceEntityType", "organization"),
        ("targetEntityType", "character"),
    ],
)
def test_render_character_page_hides_malformed_eligible_relationship(
    resolved_character, field, value
):
    relationship = _synthetic_public_relationship()
    relationship[field] = value
    page = render_character_page(
        resolved_character,
        relationships=[relationship],
        organizations=[_synthetic_public_organization()],
    )

    assert "公開可能な関係は記録されていません。" in page
    assert relationship["id"] not in page
    assert "Test Organization Alpha" not in page


def test_render_character_page_escapes_relationship_display_values(
    resolved_character,
):
    organization = _synthetic_public_organization()
    organization["displayName"] = "Test [Organization](bad)<tag>\nInjected"
    relationship = _synthetic_public_relationship()
    relationship["temporalNote"] = "Period [link](bad)<script>\nInjected"

    page = render_character_page(
        resolved_character,
        relationships=[relationship],
        organizations=[organization],
    )

    assert "[Organization](bad)" not in page
    assert "<tag>" not in page
    assert "<script>" not in page
    assert r"Test \[Organization\]\(bad\)&lt;tag&gt; Injected" in page
    assert r"Period \[link\]\(bad\)&lt;script&gt; Injected" in page


def test_render_character_page_relationship_order_is_deterministic(
    resolved_character,
):
    organization_alpha = _synthetic_public_organization()
    organization_beta = _synthetic_public_organization(entity_id="ORG_ENTITY_TEST_BETA")
    organization_beta["canonicalId"] = "ORG_TEST_BETA"
    organization_beta["displayName"] = "Test Organization Beta"
    member = _synthetic_public_relationship(source_type="manual")
    affiliated = _synthetic_public_relationship(
        relationship_id="REL_TEST_AFFILIATED_SCRIPT",
        target_entity_id="ORG_ENTITY_TEST_BETA",
        relationship_type="affiliated_with",
    )

    page_a = render_character_page(
        resolved_character,
        relationships=[member, affiliated],
        organizations=[organization_alpha, organization_beta],
    )
    page_b = render_character_page(
        resolved_character,
        relationships=[affiliated, member],
        organizations=[organization_beta, organization_alpha],
    )

    assert page_a == page_b


def test_build_pages_passes_relationships_to_character_page(synthetic_collection):
    collection = deepcopy(synthetic_collection)
    collection["entities"]["organizations"].append(_synthetic_public_organization())
    collection["entities"]["relationships"].append(_synthetic_public_relationship())

    page = build_pages(collection)["characters/CHAR_TEST_RAIN.md"]

    assert (
        "**所属**: [Test Organization Alpha]"
        "(../organizations/ORG_TEST_ALPHA.md)" in page
    )
    assert "REL_TEST_UNKNOWN" not in page


def test_render_organization_page_has_summary_aliases_and_relationship(
    resolved_character,
):
    organization = _synthetic_public_organization()
    relationship = _synthetic_public_relationship()

    page = render_organization_page(
        organization,
        relationships=[relationship],
        characters=[resolved_character],
    )

    assert 'entity_type: "organization"' in page
    assert 'canonical_id: "ORG_TEST_ALPHA"' in page
    assert "# Test Organization Alpha" in page
    assert "- Test Org Alpha" in page
    assert "**所属**: [Test Character Rain](../characters/CHAR_TEST_RAIN.md)" in page
    assert "Source: 本文抽出" in page
    assert "Evidence: 2 件" in page


def test_render_organization_page_hides_review_required_relationship(
    resolved_character,
):
    relationship = _synthetic_public_relationship(
        publication_status="review_required",
        relationship_type="internal_review_type",
    )
    page = render_organization_page(
        _synthetic_public_organization(),
        relationships=[relationship],
        characters=[resolved_character],
    )

    assert "公開可能な関係は記録されていません。" in page
    assert "internal_review_type" not in page
    assert "Test Character Rain" not in page


def test_render_organization_page_hides_malformed_taxonomy_state(
    resolved_character,
):
    relationship = _synthetic_public_relationship()
    relationship["taxonomyState"] = "provisional"
    page = render_organization_page(
        _synthetic_public_organization(),
        relationships=[relationship],
        characters=[resolved_character],
    )

    assert "公開可能な関係は記録されていません。" in page
    assert "Test Character Rain" not in page


def test_render_organization_page_rejects_reversed_subject_endpoint(
    resolved_character,
):
    relationship = _synthetic_public_relationship()
    relationship["sourceEntityId"], relationship["targetEntityId"] = (
        relationship["targetEntityId"],
        relationship["sourceEntityId"],
    )
    page = render_organization_page(
        _synthetic_public_organization(),
        relationships=[relationship],
        characters=[resolved_character],
    )

    assert "公開可能な関係は記録されていません。" in page
    assert "Test Character Rain" not in page


def test_render_organization_page_hides_unpublished_character_identity():
    relationship = _synthetic_public_relationship()
    unpublished = {
        "id": "CHAR_TEST_RAIN",
        "type": "character",
        "canonicalId": None,
        "displayName": "Internal Character Name",
        "status": "unresolved",
        "confidence": 0.9,
        "evidenceRefs": [{"evidenceId": "EVIDENCE_TEST_CHAR_001"}],
    }
    page = render_organization_page(
        _synthetic_public_organization(),
        relationships=[relationship],
        characters=[unpublished],
    )

    assert "関連先の個別ページは未公開です" in page
    assert "CHAR_TEST_RAIN" not in page
    assert "Internal Character Name" not in page


def test_render_organization_page_links_appearing_episode(synthetic_collection):
    organization = _synthetic_public_organization()
    organization["evidenceRefs"][0]["episodeId"] = "EP_TEST_001"
    page = render_organization_page(
        organization, source_documents=synthetic_collection["sourceDocuments"]
    )

    assert "## Appearing Episodes" in page
    assert "](../stories/EP_TEST_001.md)" in page


def test_render_organization_page_conflict_shows_warning():
    organization = _synthetic_public_organization()
    organization["status"] = "conflict"
    page = render_organization_page(organization)
    assert '!!! warning "未解決の矛盾があります"' in page


def test_render_organization_index_is_sorted_and_excludes_unresolved():
    alpha = _synthetic_public_organization()
    beta = _synthetic_public_organization(entity_id="ORG_ENTITY_TEST_BETA")
    beta["canonicalId"] = "ORG_TEST_BETA"
    beta["displayName"] = "Test Organization Beta"
    unresolved = _synthetic_public_organization(
        entity_id="ORG_ENTITY_TEST_UNRESOLVED", page_eligible=False
    )
    relationship = _synthetic_public_relationship()

    page = render_organization_index_page([beta, unresolved, alpha], [relationship])

    assert "| Organization pages | 2 |" in page
    assert "[Test Organization Alpha](ORG_TEST_ALPHA.md)" in page
    assert "[Test Organization Beta](ORG_TEST_BETA.md)" in page
    assert "ORG_ENTITY_TEST_UNRESOLVED" not in page
    assert page.index("Test Organization Alpha") < page.index("Test Organization Beta")
    assert (
        "- [Test Organization Alpha](ORG_TEST_ALPHA.md)\n"
        "    - Relationships: 1\n"
        "    - ID: `ORG_TEST_ALPHA`" in page
    )


def test_render_organization_index_empty_list_shows_message():
    page = render_organization_index_page([])
    assert "登録されているOrganization pageはありません。" in page


def test_build_pages_includes_organization_pages_and_mutual_links(
    synthetic_collection,
):
    collection = deepcopy(synthetic_collection)
    collection["entities"]["organizations"].append(_synthetic_public_organization())
    collection["entities"]["relationships"].append(_synthetic_public_relationship())

    pages = build_pages(collection)

    assert "organizations/index.md" in pages
    assert "organizations/ORG_TEST_ALPHA.md" in pages
    assert (
        "[Test Organization Alpha](../organizations/ORG_TEST_ALPHA.md)"
        in pages["characters/CHAR_TEST_RAIN.md"]
    )
    assert (
        "[Test Character Rain](../characters/CHAR_TEST_RAIN.md)"
        in pages["organizations/ORG_TEST_ALPHA.md"]
    )


def test_render_index_page_links_to_organizations_index(synthetic_collection):
    page = render_index_page(synthetic_collection)
    assert "[Organizations](organizations/index.md)" in page


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
    assert "- ふりがな: てすとれいん" in page
    assert "- ローマ字: Tesuto Rein" in page
    assert "- 所属: Test Team Alpha" in page
    assert "- 血液型: A" in page
    assert "- CV: Test Voice Actor" in page


def test_render_character_page_formats_height_cm(
    resolved_character, character_profiles_index
):
    page = render_character_page(resolved_character, character_profiles_index)
    assert "- 身長: 150cm" in page


def test_render_character_page_shows_birthday_display(
    resolved_character, character_profiles_index
):
    page = render_character_page(resolved_character, character_profiles_index)
    assert "- 誕生日: 4/23" in page


def test_render_character_page_shows_profile_highlight(
    resolved_character, character_profiles_index
):
    """profileHighlightはWiki記載と同じ雰囲気の「【label】value」形式で、
    基本プロフィール一覧の「特記事項」項目として表示される
    (独立sectionとしては表示しない)。"""
    page = render_character_page(resolved_character, character_profiles_index)
    assert "- 特記事項: 【好きなこと】テストデータの整理" in page
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
    assert "- 特記事項: 【合成項目】" in page


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
    assert "- 特記事項: 合成値" in page


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
    assert "- 特記事項: 未登録" in page
    assert "- ふりがな: 未登録" in page
    assert "- 身長: 未登録" in page


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
    assert "- CV: Test Voice Actor" in rain_page


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
        "- [Test Character Rain](CHAR_TEST_RAIN.md)\n"
        "    - Profile: 登録あり\n"
        "    - ID: `CHAR_TEST_RAIN`" in page
    )


def test_render_character_index_page_shows_profile_unregistered_character(
    synthetic_collection, character_profiles_index
):
    characters = synthetic_collection["entities"]["characters"]
    page = render_character_index_page(characters, character_profiles_index)
    assert (
        "- [Test Character Conflict](CHAR_TEST_CONFLICT.md)\n"
        "    - Profile: 未登録\n"
        "    - ID: `CHAR_TEST_CONFLICT`" in page
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
# render_location_page / render_location_index_page
# ----------------------------------------------------------------


def test_render_location_page_has_summary_and_aliases(
    synthetic_collection, resolved_location
):
    page = render_location_page(
        resolved_location, synthetic_collection["sourceDocuments"]
    )
    assert 'entity_type: "location"' in page
    assert 'canonical_id: "LOC_TEST_PLAZA"' in page
    assert "# Test Plaza" in page
    assert "| Scene refs | 2 |" in page
    assert "- Synthetic Square" in page


def test_render_location_page_links_known_episodes_and_keeps_unknown_id(
    synthetic_collection, resolved_location
):
    page = render_location_page(
        resolved_location, synthetic_collection["sourceDocuments"]
    )
    assert "[" in page and "](../stories/EP_TEST_001.md)" in page
    assert "](../stories/EP_TEST_002.md)" in page
    assert page.count("<code>EP_TEST_001</code>") == 1
    assert "- <code>EP_TEST_MISSING</code>" in page


def test_render_location_page_prefers_public_episode_path(
    synthetic_collection, resolved_location
):
    location = deepcopy(resolved_location)
    location["evidenceRefs"][0]["episodeId"] = "EP_TEST_PUBLIC_001"
    location["sourceCandidates"] = []
    location["extractionRunRefs"] = {}
    page = render_location_page(location, synthetic_collection["sourceDocuments"])
    assert "](../stories/PUBLIC_TEST_STORY_001_E01.md)" in page


def test_render_location_page_without_episode_refs_shows_empty_message(
    resolved_location,
):
    location = deepcopy(resolved_location)
    location["evidenceRefs"] = []
    location["sourceCandidates"] = []
    location["extractionRunRefs"] = {}
    page = render_location_page(location)
    assert "登場エピソードは記録されていません。" in page


def test_render_location_page_episode_order_is_deterministic(resolved_location):
    first = deepcopy(resolved_location)
    first["evidenceRefs"] = [
        {"evidenceId": "EV_B", "episodeId": "EP_TEST_002"},
        {"evidenceId": "EV_A", "episodeId": "EP_TEST_001"},
    ]
    first["sourceCandidates"] = [{"candidateId": "C_A", "episodeId": "EP_TEST_001"}]
    first["extractionRunRefs"] = {"EP_TEST_003": {}, "EP_TEST_002": {}}
    second = deepcopy(first)
    second["evidenceRefs"].reverse()
    second["extractionRunRefs"] = {"EP_TEST_002": {}, "EP_TEST_003": {}}

    first_page = render_location_page(first)
    second_page = render_location_page(second)
    first_section = first_page.split("## Appearing Episodes\n", 1)[1].split(
        "## Evidence", 1
    )[0]
    second_section = second_page.split("## Appearing Episodes\n", 1)[1].split(
        "## Evidence", 1
    )[0]
    assert first_section == second_section
    assert first_section.index("EP_TEST_001") < first_section.index("EP_TEST_002")
    assert first_section.index("EP_TEST_002") < first_section.index("EP_TEST_003")


def test_render_location_page_conflict_shows_warning(resolved_location):
    conflict = deepcopy(resolved_location)
    conflict["status"] = "conflict"
    page = render_location_page(conflict)
    assert '!!! warning "未解決の矛盾があります"' in page


def test_render_location_page_does_not_include_raw_payload(
    synthetic_collection, resolved_location
):
    page = render_location_page(
        resolved_location, synthetic_collection["sourceDocuments"]
    )
    assert "SYNTHETIC RAW TEXT MUST NOT APPEAR" not in page
    assert "SYNTHETIC RAW PAYLOAD MUST NOT APPEAR" not in page


def test_render_location_index_is_sorted_and_excludes_unresolved(resolved_location):
    later = deepcopy(resolved_location)
    later.update(
        {
            "id": "LOC_TEST_ZOO",
            "canonicalId": "LOC_TEST_ZOO",
            "displayName": "Test Zoo",
            "sceneRefs": [],
        }
    )
    unresolved = deepcopy(resolved_location)
    unresolved.update(
        {
            "id": "UNRESOLVED_LOC_TEST_HIDDEN",
            "canonicalId": None,
            "status": "unresolved",
            "displayName": "Hidden Place",
        }
    )
    page = render_location_index_page([later, unresolved, resolved_location])
    assert "| Location pages | 2 |" in page
    assert "[Test Plaza](LOC_TEST_PLAZA.md)" in page
    assert (
        "- [Test Plaza](LOC_TEST_PLAZA.md)\n"
        "    - Scenes: 2\n"
        "    - ID: `LOC_TEST_PLAZA`" in page
    )
    assert page.index("Test Plaza") < page.index("Test Zoo")
    assert "Hidden Place" not in page
    assert "[Unresolved report](../reports/unresolved.md)" in page


def test_render_location_index_escapes_markdown_name(resolved_location):
    location = deepcopy(resolved_location)
    location["displayName"] = "Test | [Plaza]"
    page = render_location_index_page([location])
    assert r"[Test \| \[Plaza\]](LOC_TEST_PLAZA.md)" in page


def test_conflict_location_is_generated_and_not_in_unresolved_report(
    synthetic_collection, resolved_location
):
    collection = deepcopy(synthetic_collection)
    conflict = deepcopy(resolved_location)
    conflict.update(
        {
            "id": "LOC_TEST_CONFLICT",
            "canonicalId": "LOC_TEST_CONFLICT",
            "displayName": "Test Conflict Location",
            "status": "conflict",
        }
    )
    collection["entities"]["locations"].append(conflict)
    pages = build_pages(collection)
    assert "locations/LOC_TEST_CONFLICT.md" in pages
    assert "Test Conflict Location" in pages["locations/index.md"]
    assert "Test Conflict Location" not in pages["reports/unresolved.md"]


def test_conflict_for_unimplemented_entity_type_stays_in_unresolved_report(
    synthetic_collection, resolved_location
):
    collection = deepcopy(synthetic_collection)
    organization = deepcopy(resolved_location)
    organization.update(
        {
            "id": "ORG_TEST_CONFLICT",
            "type": "organization",
            "canonicalId": "ORG_TEST_CONFLICT",
            "displayName": "Test Conflict Organization",
            "status": "conflict",
        }
    )
    organization.pop("sceneRefs", None)
    collection["entities"]["organizations"].append(organization)
    report = render_unresolved_report(collection)
    assert "Test Conflict Organization" in report
    assert "ORG_TEST_CONFLICT" in report


def test_render_index_page_links_to_locations_index(synthetic_collection):
    page = render_index_page(synthetic_collection)
    assert "[Locations](locations/index.md)" in page


def test_build_pages_generates_location_pages(synthetic_collection, resolved_location):
    collection = deepcopy(synthetic_collection)
    collection["entities"]["locations"].append(resolved_location)
    pages = build_pages(collection)
    assert "locations/index.md" in pages
    assert "items/index.md" in pages
    assert "lore/index.md" in pages
    assert "events/index.md" in pages
    assert "locations/LOC_TEST_PLAZA.md" in pages
    assert "locations/UNRESOLVED_LOC_TEST_0001.md" not in pages
    assert "| Location pages | 1 |" in pages["locations/index.md"]


# ----------------------------------------------------------------
# render_item_page / render_item_index_page
# ----------------------------------------------------------------


def test_render_item_page_has_summary_aliases_and_episodes(
    synthetic_collection, resolved_item
):
    page = render_item_page(resolved_item, synthetic_collection["sourceDocuments"])
    assert 'entity_type: "item"' in page
    assert 'canonical_id: "ITEM_TEST_COMPASS"' in page
    assert "# Test Compass" in page
    assert "- Synthetic Navigator" in page
    assert "](../stories/EP_TEST_001.md)" in page
    assert "](../stories/EP_TEST_002.md)" in page
    assert "- <code>EP_TEST_MISSING</code>" in page
    assert "Scene refs" not in page


def test_render_item_page_prefers_public_episode_path(
    synthetic_collection, resolved_item
):
    item = deepcopy(resolved_item)
    item["evidenceRefs"][0]["episodeId"] = "EP_TEST_PUBLIC_001"
    item["sourceCandidates"] = []
    item["extractionRunRefs"] = {}
    page = render_item_page(item, synthetic_collection["sourceDocuments"])
    assert "](../stories/PUBLIC_TEST_STORY_001_E01.md)" in page


def test_render_item_page_safely_keeps_untrusted_unknown_episode_id(resolved_item):
    item = deepcopy(resolved_item)
    item["evidenceRefs"] = []
    item["sourceCandidates"] = []
    item["extractionRunRefs"] = {"EP_SAFE`\n## injected <script>": {}}
    page = render_item_page(item)
    assert "\n## injected" not in page
    assert "<script>" not in page
    assert "<code>EP_SAFE` ## injected &lt;script&gt;</code>" in page


def test_render_item_page_does_not_link_unsafe_episode_path(resolved_item):
    item = deepcopy(resolved_item)
    item["evidenceRefs"] = [{"evidenceId": "EV-1", "episodeId": "EP_TEST_UNSAFE"}]
    item["sourceCandidates"] = []
    item["extractionRunRefs"] = {}
    source_documents = [
        {
            "episodeId": "EP_TEST_UNSAFE",
            "publicEpisodeId": "BAD)\n## injected",
            "displayTitle": "Unsafe Link Target",
        }
    ]
    page = render_item_page(item, source_documents)
    assert "\n## injected" not in page
    assert "../stories/BAD" not in page
    assert "Unsafe Link Target" in page
    assert "<code>EP_TEST_UNSAFE</code>" in page


def test_render_item_page_conflict_shows_warning(resolved_item):
    item = deepcopy(resolved_item)
    item["status"] = "conflict"
    page = render_item_page(item)
    assert '!!! warning "未解決の矛盾があります"' in page


def test_render_item_page_does_not_include_raw_payload(resolved_item):
    page = render_item_page(resolved_item)
    assert "SYNTHETIC RAW TEXT MUST NOT APPEAR" not in page
    assert "SYNTHETIC RAW PAYLOAD MUST NOT APPEAR" not in page


def test_render_item_page_escapes_untrusted_display_text(resolved_item):
    item = deepcopy(resolved_item)
    item["displayName"] = "Safe\n# injected <script> [name]"
    item["aliases"] = ["Alias\n## injected <b> `code`"]
    page = render_item_page(item)
    body = page.split("---", 2)[2]
    assert "\n# injected" not in body
    assert "\n## injected" not in body
    assert "<script>" not in body
    assert "<b>" not in body
    assert "&lt;script&gt;" in body
    assert "&lt;b&gt;" in body


def test_render_item_page_escapes_reference_and_conflict_summaries(resolved_item):
    item = deepcopy(resolved_item)
    item["evidenceRefs"][0]["evidenceId"] = "EV_SAFE\n## evidence injected <i>"
    item["sourceCandidates"][0].update(
        {
            "candidateId": "CAND_SAFE\n## candidate injected <b>",
            "sourceDocumentId": "DOC_SAFE\n## document injected",
        }
    )
    item["conflicts"] = [
        {
            "conflictType": "type\n## conflict injected <script>",
            "field": "field\n## field injected",
            "severity": "warning",
            "resolutionStatus": "unresolved",
        }
    ]
    page = render_item_page(item)
    assert "\n## evidence injected" not in page
    assert "\n## candidate injected" not in page
    assert "\n## document injected" not in page
    assert "\n## conflict injected" not in page
    assert "\n## field injected" not in page
    assert "<i>" not in page
    assert "<b>" not in page
    assert "<script>" not in page
    assert "&lt;i&gt;" in page
    assert "&lt;b&gt;" in page
    assert "&lt;script&gt;" in page


def test_render_item_index_is_sorted_escaped_and_excludes_unresolved(resolved_item):
    later = deepcopy(resolved_item)
    later.update(
        {
            "id": "ITEM_TEST_ZETA",
            "canonicalId": "ITEM_TEST_ZETA",
            "displayName": "Test | [Zeta]",
        }
    )
    unresolved = deepcopy(resolved_item)
    unresolved.update(
        {
            "id": "UNRESOLVED_ITEM_TEST_HIDDEN",
            "canonicalId": None,
            "status": "unresolved",
            "displayName": "Hidden Item",
        }
    )
    page = render_item_index_page([later, unresolved, resolved_item])
    assert "| Item pages | 2 |" in page
    assert "[Test Compass](ITEM_TEST_COMPASS.md)" in page
    assert (
        "- [Test Compass](ITEM_TEST_COMPASS.md)\n    - ID: `ITEM_TEST_COMPASS`" in page
    )
    assert r"[Test \| \[Zeta\]](ITEM_TEST_ZETA.md)" in page
    assert page.index("Test Compass") < page.index(r"Test \| \[Zeta\]")
    assert "Hidden Item" not in page
    assert "[Unresolved report](../reports/unresolved.md)" in page


def test_render_index_page_links_to_items_index(synthetic_collection):
    page = render_index_page(synthetic_collection)
    assert "[Items](items/index.md)" in page


def test_build_pages_generates_item_pages(synthetic_collection, resolved_item):
    collection = deepcopy(synthetic_collection)
    conflict = deepcopy(resolved_item)
    conflict.update(
        {
            "id": "ITEM_TEST_CONFLICT",
            "canonicalId": "ITEM_TEST_CONFLICT",
            "displayName": "Test Conflict Item",
            "status": "conflict",
        }
    )
    collection["entities"]["items"].extend([resolved_item, conflict])
    pages = build_pages(collection)
    assert "items/index.md" in pages
    assert "items/ITEM_TEST_COMPASS.md" in pages
    assert "items/ITEM_TEST_CONFLICT.md" in pages
    assert "Test Conflict Item" not in pages["reports/unresolved.md"]
    assert "| Item pages | 2 |" in pages["items/index.md"]


# ----------------------------------------------------------------
# render_lore_page / render_lore_index_page
# ----------------------------------------------------------------


def test_render_lore_page_has_term_aliases_and_episodes(
    synthetic_collection, resolved_lore
):
    page = render_lore_page(resolved_lore, synthetic_collection["sourceDocuments"])
    assert 'entity_type: "lore"' in page
    assert 'canonical_id: "LORE_TEST_AETHER"' in page
    assert "# Test Aether" in page
    assert "- Synthetic Essence" in page
    assert "](../stories/EP_TEST_001.md)" in page
    assert "](../stories/EP_TEST_002.md)" in page
    assert "- <code>EP_TEST_MISSING</code>" in page


def test_render_lore_page_shows_strong_merge_suggestion_warning(resolved_lore):
    lore = deepcopy(resolved_lore)
    lore["conflicts"] = [
        {
            "conflictType": "merge_suggestion",
            "severity": "info",
            "resolutionStatus": "unresolved",
        }
    ]
    page = render_lore_page(lore)
    assert page.count('!!! danger "同名の別概念候補が記録されています"') == 1
    assert "現在の判断状態はConflictsを確認してください" in page


def test_render_lore_page_merge_suggestion_warning_is_accurate_when_resolved(
    resolved_lore,
):
    lore = deepcopy(resolved_lore)
    lore["conflicts"] = [
        {
            "conflictType": "merge_suggestion",
            "severity": "info",
            "resolutionStatus": "manual_resolved",
        }
    ]
    page = render_lore_page(lore)
    assert '!!! danger "同名の別概念候補が記録されています"' in page
    assert "統合判断は確定していません" not in page
    assert "manual_resolved" in page


def test_render_lore_page_does_not_strengthen_other_conflicts(resolved_lore):
    lore = deepcopy(resolved_lore)
    lore["status"] = "conflict"
    lore["conflicts"] = [
        {
            "conflictType": "field_value_conflict",
            "severity": "warning",
            "resolutionStatus": "unresolved",
        }
    ]
    page = render_lore_page(lore)
    assert '!!! danger "同名の別概念候補が記録されています"' not in page
    assert '!!! warning "未解決の矛盾があります"' in page


def test_render_lore_page_does_not_include_raw_payload(resolved_lore):
    page = render_lore_page(resolved_lore)
    assert "SYNTHETIC RAW TEXT MUST NOT APPEAR" not in page
    assert "SYNTHETIC RAW PAYLOAD MUST NOT APPEAR" not in page


def test_render_lore_index_is_sorted_escaped_and_excludes_unresolved(resolved_lore):
    later = deepcopy(resolved_lore)
    later.update(
        {
            "id": "LORE_TEST_ZETA",
            "canonicalId": "LORE_TEST_ZETA",
            "displayName": "Test | [Zeta]",
        }
    )
    unresolved = deepcopy(resolved_lore)
    unresolved.update(
        {
            "id": "UNRESOLVED_LORE_TEST_HIDDEN",
            "canonicalId": None,
            "status": "unresolved",
            "displayName": "Hidden Lore",
        }
    )
    page = render_lore_index_page([later, unresolved, resolved_lore])
    assert "| Lore pages | 2 |" in page
    assert "[Test Aether](LORE_TEST_AETHER.md)" in page
    assert "- [Test Aether](LORE_TEST_AETHER.md)\n    - ID: `LORE_TEST_AETHER`" in page
    assert r"[Test \| \[Zeta\]](LORE_TEST_ZETA.md)" in page
    assert page.index("Test Aether") < page.index(r"Test \| \[Zeta\]")
    assert "Hidden Lore" not in page
    assert "[Unresolved report](../reports/unresolved.md)" in page


def test_render_index_page_links_to_lore_index(synthetic_collection):
    page = render_index_page(synthetic_collection)
    assert "[Lore](lore/index.md)" in page


def test_build_pages_generates_lore_pages(synthetic_collection, resolved_lore):
    collection = deepcopy(synthetic_collection)
    conflict = deepcopy(resolved_lore)
    conflict.update(
        {
            "id": "LORE_TEST_CONFLICT",
            "canonicalId": "LORE_TEST_CONFLICT",
            "displayName": "Test Conflict Lore",
            "status": "conflict",
            "conflicts": [
                {
                    "conflictType": "merge_suggestion",
                    "severity": "warning",
                    "resolutionStatus": "unresolved",
                }
            ],
        }
    )
    collection["entities"]["lore"].extend([resolved_lore, conflict])
    pages = build_pages(collection)
    assert "lore/index.md" in pages
    assert "lore/LORE_TEST_AETHER.md" in pages
    assert "lore/LORE_TEST_CONFLICT.md" in pages
    assert "Test Conflict Lore" not in pages["reports/unresolved.md"]
    assert "| Lore pages | 2 |" in pages["lore/index.md"]


def test_build_pages_keeps_unsafe_lore_id_in_unresolved_report(
    synthetic_collection, resolved_lore
):
    collection = deepcopy(synthetic_collection)
    lore = deepcopy(resolved_lore)
    lore.update(
        {
            "id": "LORE_TEST_UNSAFE",
            "canonicalId": "../../outside",
            "displayName": "Unsafe Lore ID",
        }
    )
    collection["entities"]["lore"].append(lore)

    pages = build_pages(collection)
    assert "lore/../../outside.md" not in pages
    assert "Unsafe Lore ID" in pages["reports/unresolved.md"]


# ----------------------------------------------------------------
# render_event_page / render_event_index_page
# ----------------------------------------------------------------


def test_render_event_page_links_participants_locations_and_episodes(
    synthetic_collection, resolved_character, resolved_location, resolved_event
):
    page = render_event_page(
        resolved_event,
        synthetic_collection["sourceDocuments"],
        [resolved_character],
        [resolved_location],
    )
    assert 'entity_type: "event"' in page
    assert 'canonical_id: "EVENT_TEST_LAUNCH"' in page
    assert "# Test Launch" in page
    assert "- Synthetic Opening" in page
    assert "[Test Character Rain](../characters/CHAR_TEST_RAIN.md)" in page
    assert "[Test Plaza](../locations/LOC_TEST_PLAZA.md)" in page
    assert "](../stories/EP_TEST_001.md)" in page
    assert "- <code>EP_TEST_MISSING</code>" in page


def test_render_event_page_keeps_unknown_wrong_type_and_ineligible_refs(
    resolved_character,
    resolved_location,
    unresolved_character,
    resolved_event,
):
    event = deepcopy(resolved_event)
    event["participantEntityIds"] = [
        "CHAR_TEST_RAIN",
        "CHAR_TEST_RAIN",
        "LOC_TEST_PLAZA",
        "CHAR_TEST_UNKNOWN",
        unresolved_character["id"],
    ]
    page = render_event_page(
        event,
        characters=[resolved_character, resolved_location, unresolved_character],
        locations=[resolved_location],
    )
    participants = page.split("## Participants", 1)[1].split("## Locations", 1)[0]
    assert participants.count("../characters/CHAR_TEST_RAIN.md") == 1
    assert "../locations/LOC_TEST_PLAZA.md" not in participants
    assert "<code>LOC_TEST_PLAZA</code>（リンクなし）" in participants
    assert "<code>CHAR_TEST_UNKNOWN</code>（リンクなし）" in participants
    assert f"<code>{unresolved_character['id']}</code>、リンクなし" in participants


def test_render_event_page_does_not_resolve_reference_by_canonical_id_only(
    resolved_character, resolved_event
):
    character = deepcopy(resolved_character)
    character["id"] = "MERGED_CHAR_TEST_RAIN"
    event = deepcopy(resolved_event)
    event["participantEntityIds"] = [character["canonicalId"]]

    page = render_event_page(event, characters=[character])
    participants = page.split("## Participants", 1)[1].split("## Locations", 1)[0]
    assert "../characters/CHAR_TEST_RAIN.md" not in participants
    assert "<code>CHAR_TEST_RAIN</code>（リンクなし）" in participants


def test_render_event_page_safely_keeps_untrusted_reference_id(resolved_event):
    event = deepcopy(resolved_event)
    event["participantEntityIds"] = ["CHAR_SAFE`\n## injected <script>"]
    event["locationEntityIds"] = []
    page = render_event_page(event)
    assert "\n## injected" not in page
    assert "<script>" not in page
    assert "<code>CHAR_SAFE` ## injected &lt;script&gt;</code>" in page


def test_render_event_page_conflict_shows_warning(resolved_event):
    event = deepcopy(resolved_event)
    event["status"] = "conflict"
    page = render_event_page(event)
    assert '!!! warning "未解決の矛盾があります"' in page


def test_render_event_page_does_not_include_raw_payload(resolved_event):
    page = render_event_page(resolved_event)
    assert "SYNTHETIC RAW TEXT MUST NOT APPEAR" not in page
    assert "SYNTHETIC RAW PAYLOAD MUST NOT APPEAR" not in page


def test_render_event_index_is_sorted_escaped_and_excludes_unresolved(resolved_event):
    later = deepcopy(resolved_event)
    later.update(
        {
            "id": "EVENT_TEST_ZETA",
            "canonicalId": "EVENT_TEST_ZETA",
            "displayName": "Test | [Zeta]",
            "participantEntityIds": ["CHAR_A", "CHAR_A", "CHAR_B"],
            "locationEntityIds": ["LOC_A"],
        }
    )
    unresolved = deepcopy(resolved_event)
    unresolved.update(
        {
            "id": "UNRESOLVED_EVENT_TEST_HIDDEN",
            "canonicalId": None,
            "status": "unresolved",
            "displayName": "Hidden Event",
        }
    )
    page = render_event_index_page([later, unresolved, resolved_event])
    assert "| Event pages | 2 |" in page
    assert "[Test Launch](EVENT_TEST_LAUNCH.md)" in page
    assert r"[Test \| \[Zeta\]](EVENT_TEST_ZETA.md)" in page
    assert (
        "- [Test \\| \\[Zeta\\]](EVENT_TEST_ZETA.md)\n"
        "    - Participants: 2\n"
        "    - Locations: 1\n"
        "    - ID: `EVENT_TEST_ZETA`" in page
    )
    assert page.index("Test Launch") < page.index(r"Test \| \[Zeta\]")
    assert "Hidden Event" not in page
    assert "[Unresolved report](../reports/unresolved.md)" in page


def test_render_index_page_links_to_events_index(synthetic_collection):
    page = render_index_page(synthetic_collection)
    assert "[Events](events/index.md)" in page


def test_build_pages_generates_event_pages(
    synthetic_collection, resolved_location, resolved_event
):
    collection = deepcopy(synthetic_collection)
    collection["entities"]["locations"].append(resolved_location)
    conflict = deepcopy(resolved_event)
    conflict.update(
        {
            "id": "EVENT_TEST_CONFLICT",
            "canonicalId": "EVENT_TEST_CONFLICT",
            "displayName": "Test Conflict Event",
            "status": "conflict",
        }
    )
    collection["entities"]["events"].extend([resolved_event, conflict])
    pages = build_pages(collection)
    assert "events/index.md" in pages
    assert "events/EVENT_TEST_LAUNCH.md" in pages
    assert "events/EVENT_TEST_CONFLICT.md" in pages
    assert (
        "[Test Plaza](../locations/LOC_TEST_PLAZA.md)"
        in pages["events/EVENT_TEST_LAUNCH.md"]
    )
    assert "Test Conflict Event" not in pages["reports/unresolved.md"]
    assert "| Event pages | 2 |" in pages["events/index.md"]


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
        "- **Test Character Deprecated**\n"
        "    - Entity ID: `CHAR_TEST_DEPRECATED`\n"
        "    - Status: deprecated\n"
        "    - Canonical ID: `CHAR_TEST_DEPRECATED`\n"
        "    - Refs: 1/1"
    ) in report


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


def test_render_unresolved_report_entity_details_are_grouped(synthetic_collection):
    """Entityごとに全てのreview情報を保持し、横長の表を作らない。"""
    report = render_unresolved_report(synthetic_collection)
    assert (
        "- **Test Character Unknown**\n"
        "    - Entity ID: `UNRESOLVED_CHAR_TEST_0001`\n"
        "    - Status: unresolved\n"
        "    - Canonical ID: 未登録\n"
        "    - Refs: 1/1"
    ) in report
    assert "| Display Name | Entity ID | Status | Canonical ID | Refs |" not in report


def test_render_unresolved_report_list_labels_escape_markdown(synthetic_collection):
    unresolved_character = next(
        entity
        for entity in synthetic_collection["entities"]["characters"]
        if entity["id"] == "UNRESOLVED_CHAR_TEST_0001"
    )
    unresolved_character["displayName"] = "Test *Name* <script>"
    speaker = synthetic_collection["entities"]["specialSpeakerLabels"][0]
    speaker["rawLabel"] = "Speaker [Test] <script>"
    speaker["labelType"] = "<img src=x onerror=alert(1)>"

    report = render_unresolved_report(synthetic_collection)

    assert "- **Test \\*Name\\* &lt;script&gt;**" in report
    assert "- **Speaker \\[Test\\] &lt;script&gt;**" in report
    assert r"    - Type: &lt;img src=x onerror=alert\(1\)&gt;" in report
    assert "<script>" not in report
    assert "<img" not in report


def test_render_unresolved_report_preserves_entity_and_label_order(
    synthetic_collection,
):
    report = render_unresolved_report(synthetic_collection)
    first_entity = report.index("- **Test Character Unknown**")
    second_entity = report.index("- **Test Character Deprecated**")
    first_label = report.index("- **Test Speaker A ＆ Test Speaker B**")
    second_label = report.index("- **？？？**")

    assert first_entity < second_entity < first_label < second_label
    assert report.index("Entity ID: `UNRESOLVED_CHAR_TEST_0001`") < second_entity
    assert report.index("Type: speaker_group") < second_label


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
    """relationshipTypeSummary.unrecognizedTypesは自動修正せず、目立つ見出し
    付きで一覧表示されることを確認する。"""
    report = render_unresolved_report(synthetic_collection)
    assert "## Relationship Type Summary" in report
    assert "| Unrecognized Types | 1 |" in report
    assert "MYSTERIOUS_BOND_TEST" in report


def test_render_unresolved_report_relationship_review_records_are_aggregated(
    synthetic_collection,
):
    synthetic_collection["report"]["relationshipReviewRecords"] = [
        {
            "candidateId": "PRIVATE_CANDIDATE_ID",
            "reasons": ["provisional_type", "non_public_source_type"],
            "evidenceIds": ["PRIVATE_EVIDENCE_ID"],
        },
        {"candidateId": "OTHER_PRIVATE_ID", "reasons": ["provisional_type"]},
    ]

    report = render_unresolved_report(synthetic_collection)

    assert "| Review Records | 2 |" in report
    assert "provisional_type（2 件）" in report
    assert "non_public_source_type（1 件）" in report
    assert "PRIVATE_CANDIDATE_ID" not in report
    assert "PRIVATE_EVIDENCE_ID" not in report


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


def test_render_unresolved_report_special_speaker_labels_use_grouped_details(
    synthetic_collection,
):
    report = render_unresolved_report(synthetic_collection)
    assert "| Label | Type | Inferred | Refs |" not in report


def test_render_unresolved_report_special_speaker_labels_lists_speaker_group(
    synthetic_collection,
):
    report = render_unresolved_report(synthetic_collection)
    assert (
        "- **Test Speaker A ＆ Test Speaker B**\n"
        "    - Type: speaker_group\n"
        "    - Inferred: Test Speaker A\n"
        "    - Refs: 1/1"
    ) in report


def test_render_unresolved_report_special_speaker_labels_lists_generic_speaker(
    synthetic_collection,
):
    report = render_unresolved_report(synthetic_collection)
    assert (
        "- **？？？**\n    - Type: generic_speaker\n    - Inferred: -\n    - Refs: 1/1"
    ) in report


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


def test_render_unresolved_report_special_speaker_labels_never_shows_confirmed(
    synthetic_collection,
):
    """Special Speaker Labelsの一覧には、
    値としての"confirmed"が現れないことを確認する (自動でconfirmed
    character解決はしない方針。説明文中の"confirmed characterへ解決..."
    という地の文は対象外)。"""
    report = render_unresolved_report(synthetic_collection)
    special_section_start = report.index("## Special Speaker Labels")
    conflict_section_start = report.index("## Conflict Summary")
    special_section = report[special_section_start:conflict_section_start]
    detail_rows = [
        line for line in special_section.splitlines() if line.startswith("    -")
    ]
    assert detail_rows
    assert not any("confirmed" in row for row in detail_rows)


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
    """各StoryのEpisodes項目に、そのstoryのepisode数が表示されることを
    確認する (TEST_S01_C01=5件、TEST_PUBLIC_ID_STORY=2件、
    TEST_SOLO_STORY=1件)。"""
    page = render_story_index_page(synthetic_collection)
    assert "- [Synthetic Story Title](TEST_S01_C01.md)\n    - Episodes: 5" in page
    assert (
        "- [Synthetic Public ID Story Title](PUBLIC_TEST_STORY_001.md)\n"
        "    - Episodes: 2"
    ) in page
    assert "- [TEST_SOLO_STORY](TEST_SOLO_STORY.md)\n    - Episodes: 1" in page


def test_render_story_index_page_shows_mixed_status_when_episodes_differ(
    synthetic_collection,
):
    """story内のepisodeでmetadataStatusが異なる場合、「mixed」と表示
    されることを確認する (TEST_S01_C01: confirmed/pending/pending/
    title_unknown/deprecated混在、TEST_PUBLIC_ID_STORY: confirmed/pending
    混在)。"""
    page = render_story_index_page(synthetic_collection)
    assert (
        "- [Synthetic Story Title](TEST_S01_C01.md)\n"
        "    - Episodes: 5\n    - Status: mixed"
    ) in page
    assert (
        "- [Synthetic Public ID Story Title](PUBLIC_TEST_STORY_001.md)\n"
        "    - Episodes: 2\n    - Status: mixed"
    ) in page


def test_render_story_index_page_shows_uniform_status_when_consistent(
    synthetic_collection,
):
    """story内の全episodeが同じmetadataStatusの場合 (TEST_SOLO_STORY、
    episode1件のみでpending) は、そのまま日本語補足付きで表示される
    ことを確認する。"""
    page = render_story_index_page(synthetic_collection)
    assert (
        "- [TEST_SOLO_STORY](TEST_SOLO_STORY.md)\n"
        "    - Episodes: 1\n    - Status: pending（未確認）"
    ) in page


def test_render_story_index_page_uses_grouped_details(synthetic_collection):
    """横長の表を作らず、各Storyの値を同じ項目にまとめる。"""
    page = render_story_index_page(synthetic_collection)
    assert "| Story | Episodes | Status | Category |" not in page
    assert (
        "- [Synthetic Story Title](TEST_S01_C01.md)\n"
        "    - Episodes: 5\n"
        "    - Status: mixed\n"
        "    - Category: MAIN"
    ) in page
    assert page.index("TEST_S01_C01.md") < page.index("PUBLIC_TEST_STORY_001.md")
    assert page.index("PUBLIC_TEST_STORY_001.md") < page.index("TEST_SOLO_STORY.md")


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


def test_render_story_index_page_escapes_untrusted_inline_text():
    """storyTitleやcategoryにMarkdown/HTMLが含まれても構造を保つ。
    (Story link textはstoryTitle優先のため、storyTitle側で確認する)。"""
    collection = {
        "sourceDocuments": [
            {
                "path": "synthetic.json",
                "documentId": "EP_TEST_ESCAPE",
                "storyId": "TEST_ESCAPE",
                "episodeId": "EP_TEST_ESCAPE",
                "storyTitle": "Chapter [1] | <script>",
                "metadataStatus": "confirmed",
                "storyCategory": "MAIN *unsafe* <img>",
            }
        ],
        "report": {},
    }
    page = render_story_index_page(collection)
    assert "[Chapter \\[1\\] \\| &lt;script&gt;](TEST_ESCAPE.md)" in page
    assert "Category: MAIN \\*unsafe\\* &lt;img&gt;" in page
    assert "<script>" not in page
    assert "<img>" not in page


def test_render_story_index_page_escapes_unknown_metadata_status(
    synthetic_collection,
):
    solo_document = next(
        doc
        for doc in synthetic_collection["sourceDocuments"]
        if doc["storyId"] == "TEST_SOLO_STORY"
    )
    solo_document["metadataStatus"] = "<img src=x onerror=alert(1)>"

    page = render_story_index_page(synthetic_collection)

    assert "Status: &lt;img src=x onerror=alert\\(1\\)&gt;" in page
    assert "<img" not in page


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


def _story_related_character(
    entity_id: str,
    display_name: str,
    episode_ids: list[str],
    *,
    canonical_id: str | None,
) -> dict:
    """Story pageのRelated Characters検証用の最小合成entityを返す。"""
    return {
        "id": entity_id,
        "canonicalId": canonical_id,
        "displayName": display_name,
        "status": "merged" if canonical_id else "unresolved",
        "confidence": 0.9,
        "evidenceRefs": [{"episodeId": episode_id} for episode_id in episode_ids],
        "sourceCandidates": [],
        "extractionRunRefs": {},
    }


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
    assert "### Resolved (2 件)" in page
    assert "Test Character Rain" in page
    assert "`CHAR_TEST_RAIN`" in page


def test_render_story_page_related_characters_use_first_episode_order_and_identity():
    """入力episode順やcollection全体順ではなくstory内の初出episode順で並べ、
    resolved characterはcanonicalId単位で1回だけ表示する。"""
    episodes = [
        {"storyId": "TEST_STORY", "episodeId": "EP_TEST_002"},
        {"storyId": "TEST_STORY", "episodeId": "EP_TEST_001"},
    ]
    second = _story_related_character(
        "CHAR_ENTITY_SECOND",
        "Second Episode Character",
        ["EP_TEST_002"],
        canonical_id="CHAR_TEST_SECOND",
    )
    first = _story_related_character(
        "CHAR_ENTITY_FIRST",
        "First Episode Character",
        ["EP_TEST_001", "EP_TEST_002"],
        canonical_id="CHAR_TEST_FIRST",
    )
    duplicate_first = _story_related_character(
        "CHAR_ENTITY_FIRST_DUPLICATE",
        "Duplicate Canonical Character",
        ["EP_TEST_001"],
        canonical_id="CHAR_TEST_FIRST",
    )
    collection = {
        "entities": {"characters": [second, first, duplicate_first]},
    }

    page = render_story_page("TEST_STORY", episodes, collection)
    section = page.split("## Related Characters", 1)[1].split("## Review Links", 1)[0]

    assert section.index("First Episode Character") < section.index(
        "Second Episode Character"
    )
    assert section.count("`CHAR_TEST_FIRST`") == 1
    assert "Duplicate Canonical Character" not in section
    assert "### Resolved (2 件)" in section


def test_render_story_page_groups_distinct_unresolved_characters_for_review():
    """unresolvedは内部IDを列挙せず件数とreview導線を表示する。

    同じdisplayNameでも内部idが異なるentityは統合しない一方、同じ内部idの
    重複は複数episode・複数recordにまたがっても1件として数える。
    """
    episodes = [
        {"storyId": "TEST_STORY", "episodeId": "EP_TEST_001"},
        {"storyId": "TEST_STORY", "episodeId": "EP_TEST_002"},
    ]
    resolved = _story_related_character(
        "CHAR_ENTITY_RESOLVED",
        "Resolved Character",
        ["EP_TEST_002"],
        canonical_id="CHAR_TEST_RESOLVED",
    )
    unresolved_first = _story_related_character(
        "UNRESOLVED_TEST_001",
        "Same Unknown Label",
        ["EP_TEST_001", "EP_TEST_002"],
        canonical_id=None,
    )
    unresolved_first_duplicate = _story_related_character(
        "UNRESOLVED_TEST_001",
        "Same Unknown Label",
        ["EP_TEST_002"],
        canonical_id=None,
    )
    unresolved_second = _story_related_character(
        "UNRESOLVED_TEST_002",
        "Same Unknown Label",
        ["EP_TEST_002"],
        canonical_id=None,
    )
    collection = {
        "entities": {
            "characters": [
                resolved,
                unresolved_first,
                unresolved_first_duplicate,
                unresolved_second,
            ]
        },
    }

    page = render_story_page("TEST_STORY", episodes, collection)
    section = page.split("## Related Characters", 1)[1].split("## Review Links", 1)[0]

    assert section.index("### Resolved") < section.index("### Needs Review")
    assert "### Needs Review (2 件)" in section
    assert "[Unresolved report](../reports/unresolved.md)" in section
    assert "UNRESOLVED_TEST_001" not in section
    assert "UNRESOLVED_TEST_002" not in section
    assert "Same Unknown Label" not in section


def test_render_story_page_unresolved_only_is_not_reported_as_empty():
    episodes = [{"storyId": "TEST_STORY", "episodeId": "EP_TEST_001"}]
    unresolved = _story_related_character(
        "UNRESOLVED_TEST_ONLY",
        "Only Unknown Character",
        ["EP_TEST_001"],
        canonical_id=None,
    )
    collection = {"entities": {"characters": [unresolved]}}

    page = render_story_page("TEST_STORY", episodes, collection)
    section = page.split("## Related Characters", 1)[1].split("## Review Links", 1)[0]

    assert "### Resolved" not in section
    assert "### Needs Review (1 件)" in section
    assert "関連するキャラクターは記録されていません。" not in section


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
    assert "locations/index.md" in pages
    assert "items/index.md" in pages
    assert "lore/index.md" in pages
    assert "events/index.md" in pages
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


def test_build_and_write_pages_skip_unsafe_episode_output_path(
    synthetic_collection, resolved_item, tmp_path
):
    collection = deepcopy(synthetic_collection)
    source_document = collection["sourceDocuments"][0]
    source_document["publicEpisodeId"] = "../outside"
    item = deepcopy(resolved_item)
    item["evidenceRefs"] = [
        {"evidenceId": "EV-UNSAFE-PATH", "episodeId": source_document["episodeId"]}
    ]
    item["sourceCandidates"] = []
    item["extractionRunRefs"] = {}
    collection["entities"]["items"] = [item]

    pages = build_pages(collection)
    assert "stories/../outside.md" not in pages
    assert "../stories/../outside.md" not in pages["items/ITEM_TEST_COMPASS.md"]
    assert "<code>EP_TEST_001</code>" in pages["items/ITEM_TEST_COMPASS.md"]

    write_pages(pages, tmp_path)
    assert not (tmp_path.parent / "outside.md").exists()


def test_write_pages_rejects_output_path_outside_root_before_writing(tmp_path):
    output_dir = tmp_path / "site"
    pages = {
        "index.md": "safe",
        "lore/../../outside.md": "unsafe",
    }

    with pytest.raises(ValueError, match="output path must stay under output_dir"):
        write_pages(pages, output_dir)

    assert not (output_dir / "index.md").exists()
    assert not (tmp_path / "outside.md").exists()


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
    assert "locations/index.md" in pages
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


@pytest.mark.parametrize("review_status", ["reviewed", "approved"])
def test_displayable_episode_summary_is_displayed_on_episode_page(
    synthetic_collection, review_status
):
    lookup = _summary_lookup(
        _raw_summary_document(
            episodeSummaries=[
                {"episodeId": "EP_TEST_001", "text": "合成Episode Summary本文。"}
            ],
            review={
                "status": review_status,
                "reviewer": None,
                "reviewedAt": None,
                "notes": None,
            },
        )
    )
    pages = build_pages(synthetic_collection, story_summary_lookup=lookup)
    episode_page = pages["stories/EP_TEST_001.md"]
    assert "## Episode Summary" in episode_page
    assert "合成Episode Summary本文。" in episode_page
    assert "本文セリフはこのページに掲載しません" in episode_page


def test_episode_page_resolves_summary_by_public_ids(synthetic_collection):
    """内部IDが一致しなくてもpublic Story/Episode IDで照合できる。"""
    source_document = next(
        doc
        for doc in synthetic_collection["sourceDocuments"]
        if doc.get("episodeId") == "EP_TEST_PUBLIC_001"
    )
    lookup = _summary_lookup(
        _raw_summary_document(
            storyId="SOME_OTHER_INTERNAL_STORY",
            publicStoryId="PUBLIC_TEST_STORY_001",
            episodeSummaries=[
                {
                    "episodeId": "SOME_OTHER_INTERNAL_EPISODE",
                    "publicEpisodeId": "PUBLIC_TEST_STORY_001_E01",
                    "text": "公開ID照合で表示するEpisode Summary。",
                }
            ],
        )
    )
    page = render_episode_page(
        source_document,
        synthetic_collection,
        story_summary_lookup=lookup,
    )
    assert "## Episode Summary" in page
    assert "公開ID照合で表示するEpisode Summary。" in page


@pytest.mark.parametrize(
    ("document_overrides", "entry"),
    [
        ({}, None),
        (
            {
                "review": {
                    "status": "needs_revision",
                    "reviewer": None,
                    "reviewedAt": None,
                    "notes": None,
                }
            },
            {"episodeId": "EP_TEST_001", "text": "非表示の要約。"},
        ),
        (
            {"generationStatus": "draft"},
            {"episodeId": "EP_TEST_001", "text": "非表示の要約。"},
        ),
        ({}, {"episodeId": "EP_TEST_001", "text": "   "}),
    ],
)
def test_episode_page_omits_summary_section_when_not_displayable(
    synthetic_collection, document_overrides, entry
):
    """欠落・未review・未生成・空本文ではsectionもplaceholderも出さない。"""
    lookup = _summary_lookup(
        _raw_summary_document(
            episodeSummaries=[] if entry is None else [entry],
            **document_overrides,
        )
    )
    pages = build_pages(synthetic_collection, story_summary_lookup=lookup)
    episode_page = pages["stories/EP_TEST_001.md"]
    assert "## Episode Summary" not in episode_page
    assert "非表示の要約。" not in episode_page
    assert "未生成" not in episode_page


def test_episode_page_does_not_repeat_story_summary(synthetic_collection):
    lookup = _summary_lookup(
        _raw_summary_document(
            storySummary={"text": "Episode pageへ再掲しないStory Summary。"},
            episodeSummaries=[
                {"episodeId": "EP_TEST_001", "text": "表示するEpisode Summary。"}
            ],
        )
    )
    pages = build_pages(synthetic_collection, story_summary_lookup=lookup)
    episode_page = pages["stories/EP_TEST_001.md"]
    assert "表示するEpisode Summary。" in episode_page
    assert "Episode pageへ再掲しないStory Summary。" not in episode_page
    assert "## Story Summary" not in episode_page


def test_episode_page_hides_summary_on_story_id_conflict(synthetic_collection):
    """storyId一致とpublicStoryId一致が別documentなら安全側で非表示。"""
    source_document = {
        **synthetic_collection["sourceDocuments"][0],
        "publicStoryId": "PUBLIC_TEST_STORY_001",
    }
    lookup = _summary_lookup(
        _raw_summary_document(
            publicStoryId="SOME_OTHER_PUBLIC_ID",
            episodeSummaries=[{"episodeId": "EP_TEST_001", "text": "内部ID側の要約。"}],
        ),
        _raw_summary_document(
            storyId="TEST_PUBLIC_ID_STORY",
            publicStoryId="PUBLIC_TEST_STORY_001",
            episodeSummaries=[{"episodeId": "EP_TEST_001", "text": "公開ID側の要約。"}],
        ),
    )
    page = render_episode_page(
        source_document,
        synthetic_collection,
        story_summary_lookup=lookup,
    )
    assert "## Episode Summary" not in page
    assert "内部ID側の要約。" not in page
    assert "公開ID側の要約。" not in page


def test_episode_page_hides_summary_on_episode_id_conflict(synthetic_collection):
    """episodeId一致とpublicEpisodeId一致が別entryなら安全側で非表示。"""
    source_document = {
        **synthetic_collection["sourceDocuments"][0],
        "publicEpisodeId": "PUBLIC_TEST_STORY_001_E01",
    }
    lookup = _summary_lookup(
        _raw_summary_document(
            episodeSummaries=[
                {
                    "episodeId": "EP_TEST_001",
                    "publicEpisodeId": "SOME_OTHER_PUBLIC_EPISODE",
                    "text": "内部ID側の要約。",
                },
                {
                    "episodeId": "SOME_OTHER_INTERNAL_EPISODE",
                    "publicEpisodeId": "PUBLIC_TEST_STORY_001_E01",
                    "text": "公開ID側の要約。",
                },
            ]
        )
    )
    page = render_episode_page(
        source_document,
        synthetic_collection,
        story_summary_lookup=lookup,
    )
    assert "## Episode Summary" not in page
    assert "内部ID側の要約。" not in page
    assert "公開ID側の要約。" not in page


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


def test_episode_page_evidence_ref_stays_plain_without_evidence_lookup(
    synthetic_collection,
):
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
    assert "Evidence refs: `TEST_S01_C01_E01_DLG0001`" in episode_page
    assert "](../evidence/" not in episode_page


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


def test_episode_page_evidence_refs_use_public_link_and_unresolved_fallback(
    synthetic_collection,
):
    """Episode pageでも既存helperの公開ID優先linkと未解決fallbackを使う。"""
    summary_lookup = _summary_lookup(
        _raw_summary_document(
            episodeSummaries=[
                {
                    "episodeId": "EP_TEST_001",
                    "text": "合成Episode Summary本文。",
                    "evidenceRefs": [
                        "TEST_S01_C01_E01_DLG0001",
                        "NOT_IN_EVIDENCE_INDEX",
                    ],
                }
            ]
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
    pages = build_pages(
        synthetic_collection,
        story_summary_lookup=summary_lookup,
        evidence_index_lookup=evidence_lookup,
    )
    episode_page = pages["stories/EP_TEST_001.md"]
    assert (
        "Evidence refs: [`EVT_TEST_001_E01_DLG0001`]"
        "(../evidence/EVT_TEST_001.md#evt_test_001_e01_dlg0001), "
        "`NOT_IN_EVIDENCE_INDEX`" in episode_page
    )
    assert "TEST_S01_C01_E01_DLG0001" not in episode_page
    assert "[Evidence index]" not in episode_page


def test_episode_page_omits_evidence_line_when_refs_are_empty(synthetic_collection):
    summary_lookup = _summary_lookup(
        _raw_summary_document(
            episodeSummaries=[
                {
                    "episodeId": "EP_TEST_001",
                    "text": "evidenceRefsなしのEpisode Summary。",
                    "evidenceRefs": [],
                }
            ]
        )
    )
    pages = build_pages(synthetic_collection, story_summary_lookup=summary_lookup)
    episode_page = pages["stories/EP_TEST_001.md"]
    assert "## Episode Summary" in episode_page
    assert "evidenceRefsなしのEpisode Summary。" in episode_page
    assert "Evidence refs:" not in episode_page


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
    """Summaryが無ければgeneral Evidence index導線を追加しない。"""
    evidence_lookup = _evidence_lookup(_raw_evidence_document())
    pages = build_pages(synthetic_collection, evidence_index_lookup=evidence_lookup)
    episode_page = pages["stories/EP_TEST_001.md"]
    assert "## Episode Summary" not in episode_page
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
