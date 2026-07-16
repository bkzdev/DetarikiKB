"""
tests/docs/test_character_story_id_manifest_design_docs.py
Character Story ID / Manifest Design
(docs/architecture/05_Parser/Character_Story_ID_Manifest_Design.md) の
軽量な整合性テスト。

`feature/character-story-id-manifest-design`で確定した主要な決定値
（storyId体系・CHAR_HSカテゴリ・episodeId suffix規則・実装PR分割計画）が
文書に明記されていること、実データ由来の断片（実キャラクター名等）が
紛れ込んでいないことを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DESIGN_DOC_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "05_Parser"
    / "Character_Story_ID_Manifest_Design.md"
)

REQUIRED_SECTIONS = (
    "# 1. 目的",
    "# 2. 背景（03_Scope決定との関係）",
    "# 3. raw配置の確認結果",
    "# 4. storyId・episodeId体系の決定",
    "# 5. CHAR_HSカテゴリ",
    "# 6. 例外変種の動的判定と別episode方式",
    "# 7. コマンド登録の決定",
    "# 8. manifest統合設計",
    "# 9. 実装PR分割計画",
    "# 10. Open questions",
    "# 11. Non-goals",
    "# 12. 参照",
)

_REAL_CHARACTER_NAMES = ("レイン", "赤城陽菜")


def _read_design_doc() -> str:
    return DESIGN_DOC_PATH.read_text(encoding="utf-8")


def test_design_doc_exists():
    assert DESIGN_DOC_PATH.is_file()


def test_design_doc_has_required_sections():
    content = _read_design_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"必須セクションが不足しています: {missing}"


def test_design_doc_states_story_id_scheme():
    content = _read_design_doc()
    for prefix in (
        "CHAR_MAIN_{ROMAJI}",
        "CHAR_EXTRA_{ROMAJI}",
        "CHAR_DATE_{ROMAJI}",
        "CHAR_HS_{ROMAJI}",
    ):
        assert prefix in content


def test_design_doc_states_char_hs_category():
    content = _read_design_doc()
    assert "CHAR_HS" in content
    assert "内部KB専用" in content
    assert "公開恒久除外" in content or "恒久除外" in content


def test_design_doc_states_episode_id_suffix_rules():
    content = _read_design_doc()
    for suffix in ("_VN", "_VSP", "_VD{K}", "_VN_D{K}", "_VSP_D{K}"):
        assert suffix in content


def test_design_doc_states_implementation_pr_split():
    content = _read_design_doc()
    for pr_label in ("PR B", "PR C", "PR D", "PR E"):
        assert pr_label in content


def test_design_doc_states_no_implementation_in_this_pr():
    content = _read_design_doc()
    section = content.split("# 11. Non-goals", 1)[1]
    assert "agents/" in section
    assert "scripts/" in section
    assert "schemas/" in section
    assert "config/" in section


def test_design_doc_states_confirmed_precondition():
    content = _read_design_doc()
    assert "confirmed" in content
    assert "72" in content


def test_design_doc_states_vr_excluded_from_dynamic_determination():
    content = _read_design_doc()
    assert "_VR" in content
    assert "動的判定の対象外" in content


def test_design_doc_does_not_reference_real_character_names():
    """実データ由来のキャラクター名が紛れ込んでいないことの簡易チェック
    (tests/docs/test_story_manifest_design_docs.py と同じ確認パターン)。"""
    content = _read_design_doc()
    for name in _REAL_CHARACTER_NAMES:
        assert name not in content


def test_design_doc_references_related_docs():
    content = _read_design_doc()
    assert "Identifier_Specification.md" in content
    assert "Story_Manifest_Design.md" in content
    assert "03_Scope.md" in content
