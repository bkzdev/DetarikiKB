"""
tests/docs/test_evidence_index_design_docs.py
Evidence Index Design (docs/architecture/06_AI/Evidence_Index_Design.md) の
軽量な整合性テスト。

Evidence indexの役割・Public Evidence Index/Internal Review Evidence
Packetの分離・raw text非表示方針・source of truth比較・データモデル草案・
evidenceType方針・link strategy比較・Story別Evidence page推奨・
Story page/Episode page/Summaryとの関係・AI Analysis/Speculationとの
分離・implementation phasesが明記されていること、既存docs
（Story_Summary_Design.md/Wiki_Output_Design.md）・TASKS.mdから参照
されていることを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
EVIDENCE_INDEX_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Evidence_Index_Design.md"
)
STORY_SUMMARY_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Story_Summary_Design.md"
)
WIKI_OUTPUT_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "07_Wiki" / "Wiki_Output_Design.md"
)
TASKS_PATH = PROJECT_ROOT / "TASKS.md"

REQUIRED_SECTIONS = (
    "# 1. Background",
    "# 2. Goals",
    "# 3. Non-goals",
    "# 4. Evidence indexの役割",
    "# 5. Public Evidence Index",
    "# 6. Raw text非表示方針",
    "# 7. Source of truth比較と採用方針",
    "# 8. Evidence type方針",
    "# 9. Evidence ID link方針",
    "# 10. Implementation phases",
    "# 11. Story page / Episode page / Summary / Unresolved reportとの関係",
    "# 12. Evidence indexとAI Analysis / Speculationの関係",
    "# 13. Data model draft",
    "# 14. Validation plan",
    "# 15. 未確定事項",
)


def _read_design_doc() -> str:
    return EVIDENCE_INDEX_DESIGN_PATH.read_text(encoding="utf-8")


def test_design_doc_exists():
    assert EVIDENCE_INDEX_DESIGN_PATH.is_file()


def test_design_doc_has_required_sections():
    content = _read_design_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"必須セクションが不足しています: {missing}"


def test_design_doc_states_evidence_index_role():
    content = _read_design_doc()
    assert "Summaryの根拠IDを追跡する" in content
    assert "raw textを公開するページではない" in content


def test_design_doc_separates_public_and_internal_evidence():
    content = _read_design_doc()
    assert "Public Evidence Index" in content
    assert "Internal Review Evidence Packet" in content
    assert "workspace/review_packets/evidence/" in content


def test_design_doc_states_raw_text_policy():
    content = _read_design_doc()
    assert "raw DEC text" in content
    assert "元セリフ全文" in content
    assert "raw command" in content


def test_design_doc_compares_source_of_truth():
    content = _read_design_doc()
    for heading in ("候補A", "候補B", "候補C", "候補D"):
        assert heading in content
    assert "Dedicated Evidence Index file" in content


def test_design_doc_states_evidence_type_policy():
    content = _read_design_doc()
    for evidence_type in (
        "dialogue",
        "monologue",
        "narration",
        "choice",
        "stage_direction",
        "speaker_label",
        "scene",
        "episode",
        "story",
        "unknown",
    ):
        assert evidence_type in content


def test_design_doc_compares_link_strategy():
    content = _read_design_doc()
    assert "単一ページ内anchor" in content
    assert "Story別Evidence page" in content
    assert "Episode別Evidence page" in content
    assert "Story別Evidence page（候補B）がバランス良い" in content


def test_design_doc_has_data_model_draft():
    content = _read_design_doc()
    assert "evidenceIndexVersion" in content
    assert "evidenceId" in content
    assert "rawTextIncluded" in content


def test_design_doc_states_relationship_with_story_and_episode_page():
    content = _read_design_doc()
    assert "## 11.1 Story page" in content
    assert "## 11.2 Episode page" in content
    assert "## 11.3 Summary" in content
    assert "## 11.4 Unresolved report" in content


def test_design_doc_separates_from_ai_analysis():
    content = _read_design_doc()
    assert "根拠索引" in content
    assert "考察本文を持たない" in content


def test_design_doc_lists_implementation_phases():
    content = _read_design_doc()
    assert "evidence-index-schema-implementation" in content
    assert "evidence-index-renderer-integration" in content
    assert "evidence-index-generation-dry-run" in content


def test_design_doc_does_not_implement_schema_or_renderer():
    """本PRではschema実装・renderer実装を行わない方針がNon-goalsに
    明記されていることの簡易チェック。"""
    content = _read_design_doc()
    non_goals_section = content.split("# 3. Non-goals", 1)[1].split(
        "# 4. Evidence indexの役割", 1
    )[0]
    for forbidden in (
        "Evidence index schema実装",
        "Evidence index renderer実装",
        "Evidence page生成",
        "evidenceRefs",
    ):
        assert forbidden in non_goals_section


def test_story_summary_design_links_to_evidence_index_design():
    content = STORY_SUMMARY_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Design.md" in content


def test_wiki_output_design_links_to_evidence_index_design():
    content = WIKI_OUTPUT_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Design.md" in content


def test_tasks_md_lists_next_pr_candidates():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-schema-implementation" in content
    assert "evidence-index-renderer-integration" in content
    assert "evidence-index-generation-dry-run" in content


def test_design_doc_states_renderer_integration_complete():
    """feature/evidence-index-renderer-integrationで、Phase 3
    (Evidence page生成・evidenceRefsリンク化) が完了したことが
    §10 Implementation phasesに記録されていることを確認する。"""
    content = _read_design_doc()
    phases_section = content.split("# 10. Implementation phases", 1)[1].split(
        "# 11. Story page", 1
    )[0]
    assert "**完了（本PR）**" in phases_section
    assert "実装状況（`feature/evidence-index-renderer-integration`で実施）" in content
    integration_status = content.split(
        "実装状況（`feature/evidence-index-renderer-integration`で実施）", 1
    )[1]
    assert "--evidence-index" in integration_status
    assert "evidence_page_path" in integration_status
    assert "render_evidence_page" in integration_status
    assert "常に" in integration_status
