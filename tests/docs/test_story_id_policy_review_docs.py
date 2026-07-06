"""
tests/docs/test_story_id_policy_review_docs.py
Story ID Policy Review (docs/architecture/05_Parser/Story_ID_Policy_Review.md) の
軽量な整合性テスト。

必須セクションが揃っていること、ID生成ロジック・URL/file pathを変更しない
方針が明記されていること、public URL / internal source trace IDの分離に
ついて書かれていること、次PR候補が書かれていること、自動confirmedや
実データcommitを促す記述が無いことを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
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
    "# 2. 背景",
    "# 3. 現行仕様の整理",
    "# 4. 実データサンプル観察結果（匿名化）",
    "# 5. 問題点の具体化",
    "# 6. 比較するID案",
    "# 7. 評価表",
    "# 8. 推奨方針",
    "# 9. public URL と internal source trace ID の分離について",
    "# 10. 次PR候補（実装しない、タスク分解のみ）",
    "# 11. Migration impact（もし将来ID方式を変更する場合）",
    "# 12. Open Questions",
    "# 13. このPRで実装しないこと（Non-goals）",
)


def _read_review_doc() -> str:
    return REVIEW_DOC_PATH.read_text(encoding="utf-8")


def test_review_doc_exists():
    assert REVIEW_DOC_PATH.is_file()


def test_review_doc_has_required_sections():
    content = _read_review_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"必須セクションが不足しています: {missing}"


def test_review_doc_states_no_id_generation_logic_change():
    content = _read_review_doc()
    assert "ID生成ロジックを変更しない" in content
    assert "URL/file pathも変更しない" in content


def test_review_doc_compares_four_id_options():
    content = _read_review_doc()
    for heading in (
        "案A: 現行維持",
        "案B: date + sequence",
        "案C: manifest-assigned stable ID",
        "案D: category-specific policy",
    ):
        assert heading in content


def test_review_doc_has_recommendation():
    content = _read_review_doc()
    assert "# 8. 推奨方針" in content
    assert "短期" in content
    assert "中期" in content
    assert "長期" in content


def test_review_doc_discusses_public_url_and_source_trace_id_separation():
    content = _read_review_doc()
    assert "public URL" in content
    assert "internal source trace ID" in content or "raw traceability" in content


def test_review_doc_lists_next_pr_candidates():
    content = _read_review_doc()
    assert "story-id-policy-design-decision" in content
    assert "story-manifest-public-id-fields-design" in content


def test_review_doc_does_not_encourage_auto_confirmed_or_real_data_commit():
    """自動confirmed化やmigration script作成、実データcommitを促す記述が
    無いことを確認する (Non-goalsとして明記されていること)。"""
    content = _read_review_doc()
    assert "migration scriptの作成" in content
    non_goals_section = content.split("# 13. このPRで実装しないこと（Non-goals）", 1)[1]
    for forbidden in (
        "storyId",
        "episodeId",
        "URL/file path",
        "migration script",
    ):
        assert forbidden in non_goals_section


def test_review_doc_does_not_reference_real_data_sample_content():
    """匿名化ルールに従い、実イベント名・実sourceKeyそのものを記載していない
    ことの簡易チェック (既存のmanual review実データで使われた具体的な
    sourceKey文字列を含まないこと)。"""
    content = _read_review_doc()
    for forbidden in ("mizugimassage", "cami3rd", "childwb", "tukasahome", "cosplay"):
        assert forbidden not in content.lower()


def test_review_doc_anonymizes_observations_with_sample_labels():
    content = _read_review_doc()
    assert "EVENT sample A" in content
    assert "匿名化" in content


def test_story_manifest_design_links_to_review_doc():
    content = STORY_MANIFEST_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Story_ID_Policy_Review.md" in content


def test_identifier_specification_links_to_review_doc():
    content = IDENTIFIER_SPEC_PATH.read_text(encoding="utf-8")
    assert "Story_ID_Policy_Review.md" in content


def test_wiki_output_design_links_to_review_doc():
    content = WIKI_OUTPUT_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Story_ID_Policy_Review.md" in content
