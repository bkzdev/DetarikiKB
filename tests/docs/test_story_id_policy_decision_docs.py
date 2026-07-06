"""
tests/docs/test_story_id_policy_decision_docs.py
Story ID Policy Decision (docs/architecture/05_Parser/Story_ID_Policy_Decision.md) の
軽量な整合性テスト。

PR #70 (Story_ID_Policy_Review.md) の比較結果を踏まえて採用したID方針が
文書化されていること、public ID field名の採用候補・migration方針・
次PRのスコープが明記されていること、既存docsからリンクされていること、
このPRでは実装変更を行わない方針が守られていることを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DECISION_DOC_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "05_Parser" / "Story_ID_Policy_Decision.md"
)
REVIEW_DOC_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "05_Parser" / "Story_ID_Policy_Review.md"
)
STORY_MANIFEST_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "05_Parser" / "Story_Manifest_Design.md"
)
IDENTIFIER_SPEC_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "05_Parser" / "Identifier_Specification.md"
)
WIKI_OUTPUT_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "07_Wiki" / "Wiki_Output_Design.md"
)

REQUIRED_SECTIONS = (
    "# 1. 目的",
    "# 2. Decision summary",
    "# 3. Background",
    "# 4. Inputs from PR #70",
    "# 5. Adopted policy",
    "# 6. Category-specific policy",
    "# 7. Public ID field naming decision",
    "# 8. Non-adopted options",
    "# 9. Migration strategy",
    "# 10. Implementation phases",
    "# 11. Impacted files for future PRs",
    "# 12. Open Questions",
    "# 13. Non-goals",
)


def _read_decision_doc() -> str:
    return DECISION_DOC_PATH.read_text(encoding="utf-8")


def test_decision_doc_exists():
    assert DECISION_DOC_PATH.is_file()


def test_decision_doc_has_required_sections():
    content = _read_decision_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"必須セクションが不足しています: {missing}"


def test_decision_doc_has_decision_summary():
    content = _read_decision_doc()
    section = content.split("# 2. Decision summary", 1)[1].split("# 3.", 1)[0]
    assert len(section.strip()) > 0


def test_decision_doc_states_public_id_field_names():
    content = _read_decision_doc()
    assert "publicStoryId" in content
    assert "publicEpisodeId" in content


def test_decision_doc_states_source_key_kept_for_traceability():
    content = _read_decision_doc()
    assert "sourceKey" in content
    assert "raw trace用として" in content


def test_decision_doc_states_existing_ids_kept_for_now():
    content = _read_decision_doc()
    assert "当面維持する" in content
    assert "storyId" in content and "episodeId" in content


def test_decision_doc_states_no_url_or_path_change_in_this_pr():
    content = _read_decision_doc()
    assert "URL/file pathも変更しない" in content


def test_decision_doc_states_migration_is_additive_first():
    content = _read_decision_doc()
    assert "migration is additive first" in content
    assert "no breaking change in this PR" in content
    assert "generated URLs remain unchanged until renderer/paths switch" in content
    assert "sourceKey remains available for traceability" in content


def test_decision_doc_does_not_adopt_title_subtitle_derived_url():
    content = _read_decision_doc()
    assert "title/subtitle由来のURL" in content
    non_adopted_section = content.split("# 8. Non-adopted options", 1)[1]
    assert "採用しない" in non_adopted_section


def test_decision_doc_lists_next_pr_scope():
    content = _read_decision_doc()
    assert content.count("story-manifest-public-id-fields-design") >= 2


def test_decision_doc_does_not_implement_changes():
    """実装変更しない方針が守られていることの簡易チェック。
    Non-goalsセクションに、実装を伴う変更が明示的に禁止として
    列挙されていることを確認する。"""
    content = _read_decision_doc()
    non_goals_section = content.split("# 13. Non-goals（このPRで実装しないこと）", 1)[1]
    for forbidden in (
        "storyId",
        "episodeId",
        "schema変更",
        "URL/file pathの変更",
        "publicStoryId",
        "publicEpisodeId",
    ):
        assert forbidden in non_goals_section


def test_decision_doc_references_review_doc():
    content = _read_decision_doc()
    assert "Story_ID_Policy_Review.md" in content


def test_review_doc_links_to_decision_doc():
    content = REVIEW_DOC_PATH.read_text(encoding="utf-8")
    assert "Story_ID_Policy_Decision.md" in content


def test_story_manifest_design_links_to_decision_doc():
    content = STORY_MANIFEST_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Story_ID_Policy_Decision.md" in content


def test_identifier_specification_links_to_decision_doc():
    content = IDENTIFIER_SPEC_PATH.read_text(encoding="utf-8")
    assert "Story_ID_Policy_Decision.md" in content


def test_wiki_output_design_links_to_decision_doc():
    content = WIKI_OUTPUT_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Story_ID_Policy_Decision.md" in content


# ----------------------------------------------------------------
# publicStoryId / publicEpisodeId 実装状況
# (feature/story-manifest-public-id-fields-design)
# ----------------------------------------------------------------


def test_decision_doc_records_public_id_fields_implementation_status():
    content = _read_decision_doc()
    assert "## 10.3 実装状況" in content
    assert "feature/story-manifest-public-id-fields-design" in content


def test_decision_doc_implementation_status_confirms_no_renderer_paths_change():
    content = _read_decision_doc()
    section = content.split("## 10.3 実装状況", 1)[1]
    assert "renderer.py" in section or "paths.py" in section
    assert "変更していない" in section
