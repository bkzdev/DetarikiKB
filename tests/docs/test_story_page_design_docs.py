"""
tests/docs/test_story_page_design_docs.py
Story Page Design (docs/architecture/07_Wiki/Story_Page_Design.md) の
軽量な整合性テスト。

Story page追加方針・Episode page維持方針・Summary placeholder方針・
Episode Summariesの区切り方針・evidenceId/episodeId/blockId管理方針・
raw script text非掲載方針・URL構造候補比較・次PRスコープが明記されて
いること、既存docs（Wiki_Output_Design.md）・TASKS.mdから参照されて
いることを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
STORY_PAGE_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "07_Wiki" / "Story_Page_Design.md"
)
WIKI_OUTPUT_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "07_Wiki" / "Wiki_Output_Design.md"
)
TASKS_PATH = PROJECT_ROOT / "TASKS.md"

REQUIRED_SECTIONS = (
    "# 1. 目的",
    "# 2. Background",
    "# 3. Current structure",
    "# 4. Problem",
    "# 5. Adopted direction",
    "# 6. Story page role",
    "# 7. Episode page role",
    "# 8. Summary placement",
    "# 9. Evidence management",
    "# 10. URL structure options",
    "# 11. Recommended phase plan",
    "# 12. Non-goals",
    "# 13. Next PR scope",
)


def _read_design_doc() -> str:
    return STORY_PAGE_DESIGN_PATH.read_text(encoding="utf-8")


def test_design_doc_exists():
    assert STORY_PAGE_DESIGN_PATH.is_file()


def test_design_doc_has_required_sections():
    content = _read_design_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"必須セクションが不足しています: {missing}"


def test_design_doc_states_story_page_addition_policy():
    content = _read_design_doc()
    assert "Story pageを新規生成する" in content


def test_design_doc_states_episode_page_kept():
    content = _read_design_doc()
    assert "Episode pageは残す" in content


def test_design_doc_states_summary_placeholder_policy():
    content = _read_design_doc()
    assert "Summary placeholder" in content
    assert "未生成" in content


def test_design_doc_states_episode_summaries_split_per_episode():
    content = _read_design_doc()
    assert "Episode Summaries" in content
    assert "区切" in content


def test_design_doc_states_evidence_management_kept_per_episode():
    content = _read_design_doc()
    assert "evidenceId" in content
    assert "episodeId" in content
    assert "blockId" in content
    assert "Episode単位で維持する" in content


def test_design_doc_states_no_raw_script_text():
    content = _read_design_doc()
    assert "raw script text" in content.lower()


def test_design_doc_compares_url_structure_options():
    content = _read_design_doc()
    for heading in ("候補A", "候補B", "候補C"):
        assert heading in content


def test_design_doc_lists_next_pr_scope():
    content = _read_design_doc()
    assert content.count("wiki-story-page-renderer") >= 2


def test_design_doc_does_not_implement_renderer_changes():
    """実装変更しない方針が守られていることの簡易チェック
    (Non-goalsにrenderer/paths.py変更・schema変更等が明記されていること)。"""
    content = _read_design_doc()
    non_goals_section = content.split("# 12. Non-goals", 1)[1].split(
        "# 13. Next PR scope", 1
    )[0]
    for forbidden in (
        "Story page rendererの実装",
        "Episode page pathの変更",
        "renderer.py",
        "storyId",
    ):
        assert forbidden in non_goals_section


def test_wiki_output_design_links_to_story_page_design():
    content = WIKI_OUTPUT_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Story_Page_Design.md" in content


def test_tasks_md_reflects_story_page_policy():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "Story page" in content
    assert "wiki-story-page-renderer" in content


def test_design_doc_states_evidence_page_review_links_policy():
    """feature/evidence-index-renderer-integrationで、Review Linksへの
    Evidence pageリンクが条件付きで追加されたことが§8に記録されている
    ことを確認する。"""
    content = _read_design_doc()
    summary_section = content.split("# 8. Summary placement", 1)[1].split(
        "# 9. Evidence management", 1
    )[0]
    integration_label = (
        "Evidence index renderer統合"
        "（`feature/evidence-index-renderer-integration`で実施）"
    )
    assert integration_label in summary_section
    assert "Review Links" in summary_section
    assert "render_evidence_page" in summary_section
