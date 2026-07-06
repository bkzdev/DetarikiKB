"""
tests/docs/test_wiki_output_design_docs.py
Wiki Output Design (docs/architecture/07_Wiki/Wiki_Output_Design.md) の
軽量な整合性テスト。

必須セクションが揃っていること、実データ由来生成物をcommitしない方針・
AI考察分離方針・canonicalId優先URL方針が明記されていることを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DESIGN_DOC_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "07_Wiki" / "Wiki_Output_Design.md"
)
EXAMPLES_DIR = PROJECT_ROOT / "docs" / "examples" / "wiki_output"

# Wiki_Output_Design.md に含まれているべき必須セクション見出し
REQUIRED_SECTIONS = (
    "# 1. 目的",
    "# 2. Knowledge BaseとWikiの関係",
    "# 3. 情報の分離方針",
    "# 4. evidenceRefs の扱い",
    "# 5. unresolved entity",
    "# 6. hidden / excluded entity",
    "# 7. 実データ由来生成物をcommitしない方針",
    "# 8. ページ種別と優先順位",
    "# 9. ページ責務",
    "# 10. Markdown front matter 方針",
    "# 11. 出力ディレクトリ案",
    "# 12. テンプレート方針",
    "# 13. merged collection との対応表",
    "# 14. URL / slug 方針",
    "# 15. 将来の実装PR案",
    "# 16. Non-goals",
)

# ページ種別 (Phase分け) に含まれているべきキーワード
REQUIRED_PAGE_TYPES = (
    "Top page",
    "Story index",
    "Episode page",
    "Character page",
    "Unresolved report",
    "Location page",
    "Organization page",
    "Item page",
    "Lore page",
    "Event page",
    "Timeline page",
    "AI analysis",
)


def _read_design_doc() -> str:
    return DESIGN_DOC_PATH.read_text(encoding="utf-8")


def test_design_doc_exists():
    assert DESIGN_DOC_PATH.is_file()


def test_design_doc_has_required_sections():
    content = _read_design_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"必須セクションが不足しています: {missing}"


def test_design_doc_has_required_page_types():
    content = _read_design_doc()
    missing = [p for p in REQUIRED_PAGE_TYPES if p not in content]
    assert not missing, f"必須ページ種別への言及が不足しています: {missing}"


def test_design_doc_states_no_real_data_commit_policy():
    content = _read_design_doc()
    assert "commitしない" in content
    assert "実データ" in content


def test_design_doc_states_ai_analysis_separation_policy():
    content = _read_design_doc()
    assert "AI推定" in content or "AI-generated" in content
    assert "混ぜない" in content or "分離" in content


def test_design_doc_states_canonical_id_first_url_policy():
    content = _read_design_doc()
    assert "canonicalId" in content
    assert "名前ベースslugは原則避ける" in content


def test_design_doc_does_not_reference_committed_real_data_examples():
    """実データ由来のIDらしき列挙 (大量の数値ID羅列等) が含まれていないことの
    簡易チェック。合成ID (CHAR_EXAMPLE等) のみで構成されていることを
    間接的に確認する。"""
    content = _read_design_doc()
    # このプロジェクトの実キャラクター名の一部が紛れ込んでいないことを確認
    assert "レイン" not in content
    assert "赤城陽菜" not in content


def test_examples_directory_exists_and_is_synthetic_only():
    assert EXAMPLES_DIR.is_dir()
    readme = EXAMPLES_DIR / "README.md"
    assert readme.is_file()
    readme_content = readme.read_text(encoding="utf-8")
    assert "合成データ" in readme_content
    assert "commit" in readme_content


# ----------------------------------------------------------------
# publicStoryId / publicEpisodeId (feature/story-manifest-public-id-fields-design)
# ----------------------------------------------------------------


def test_design_doc_mentions_public_id_fields():
    content = _read_design_doc()
    assert "publicStoryId" in content
    assert "publicEpisodeId" in content


def test_design_doc_states_renderer_paths_switch_is_future_work():
    content = _read_design_doc()
    section = content.split("# 14. URL / slug 方針", 1)[1]
    assert "publicStoryId" in section
    assert "まだ行っていない" in section or "後続PR" in section or "将来PR" in section


def test_design_doc_links_to_story_page_design():
    """Story page中心構造への設計方針 (feature/wiki-story-page-design) が
    Story_Page_Design.mdへリンクされていることを確認する。"""
    content = _read_design_doc()
    assert "Story_Page_Design.md" in content
    assert "Story page" in content


def test_design_doc_states_renderer_switch_implemented_for_public_episode_id():
    """feature/story-manifest-public-id-renderer-switchで、
    publicEpisodeIdがEpisode page URL/filenameに実際に反映されたことが
    記録されていることを確認する。"""
    content = _read_design_doc()
    section = content.split("# 14. URL / slug 方針", 1)[1]
    assert "feature/story-manifest-public-id-renderer-switch" in section
    assert "episode_page_path" in section
    assert "fallback" in section

    for example_path in EXAMPLES_DIR.glob("*_example.md"):
        content = example_path.read_text(encoding="utf-8")
        # 実データ由来のキャラクター名が紛れ込んでいないことを確認
        assert "レイン" not in content
        assert "赤城陽菜" not in content
        # 合成データであることが明示されていること
        assert "合成データ" in content
