"""
tests/docs/test_story_manifest_design_docs.py
Story Manifest Design (docs/architecture/05_Parser/Story_Manifest_Design.md) の
軽量な整合性テスト。

必須セクションが揃っていること、DECから subtitle を推測しない方針・
実DEC/実manifestをcommitしない方針が明記されていることを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DESIGN_DOC_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "05_Parser" / "Story_Manifest_Design.md"
)

REQUIRED_SECTIONS = (
    "# 1. 目的",
    "# 2. story_manifest.yaml の位置づけ",
    "# 3. DECファイル配置とDKB正規IDの分離方針",
    "# 4. raw DEC layout supported pattern",
    "# 5. パス正規化方針",
    "# 6. category正規化方針",
    "# 7. sourceKey抽出方針",
    "# 8. storyId生成方針",
    "# 9. episodeId生成方針",
    "# 10. episodeNumber数値ソート方針",
    "# 11. title / subtitle / displayTitle の扱い",
    "# 12. metadataStatus方針",
    "# 13. schema",
    "# 14. parser/normalizerとの連携方針",
    "# 15. Wiki出力との連携方針",
    "# 16. 候補生成script",
    "# 17. 実DEC・実manifestはcommitしない方針",
    "# 18. 未確定事項",
    "# 19. Non-goals",
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


def test_design_doc_states_event_layout_supported_pattern():
    content = _read_design_doc()
    assert "csl_script_event_250626_dancer_export" in content
    assert "CAB-csl_script_event_250626_dancer-episode1.dec" in content
    assert "EVT_250626_DANCER" in content


def test_design_doc_states_subtitle_not_inferred_from_dec():
    content = _read_design_doc()
    assert "自動推測しない" in content
    assert "subtitle" in content.lower() or "サブタイトル" in content


def test_design_doc_states_null_allowed_for_title_and_subtitle():
    content = _read_design_doc()
    assert "null" in content
    assert "null許容" in content


def test_design_doc_states_no_real_data_commit_policy():
    content = _read_design_doc()
    assert "commitしない" in content
    assert "実DEC" in content or "実データ" in content


def test_design_doc_states_path_normalization_policy():
    content = _read_design_doc()
    assert "スラッシュ" in content
    assert "\\" in content


def test_design_doc_states_metadata_status_values():
    content = _read_design_doc()
    for status in ("pending", "confirmed", "title_unknown", "deprecated"):
        assert status in content


def test_design_doc_does_not_reference_real_character_names():
    """実データ由来のキャラクター名が紛れ込んでいないことの簡易チェック
    (tests/docs/test_wiki_output_design_docs.py と同じ確認パターン)。"""
    content = _read_design_doc()
    for name in _REAL_CHARACTER_NAMES:
        assert name not in content
