"""
tests/docs/test_story_summary_design_docs.py
Story Summary Design (docs/architecture/06_AI/Story_Summary_Design.md) の
軽量な整合性テスト。

Story Summary / Episode Summary / AI Analysis・Speculationの区別、raw
テキスト非保存方針、evidenceRefs方針、保存場所方針、status/review
workflow、renderer統合方針が明記されていること、既存docs
（Story_Page_Design.md / Wiki_Output_Design.md）・TASKS.mdから参照
されていることを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
STORY_SUMMARY_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Story_Summary_Design.md"
)
STORY_PAGE_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "07_Wiki" / "Story_Page_Design.md"
)
WIKI_OUTPUT_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "07_Wiki" / "Wiki_Output_Design.md"
)
EXTRACTION_PIPELINE_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Extraction_Pipeline.md"
)
TASKS_PATH = PROJECT_ROOT / "TASKS.md"

REQUIRED_SECTIONS = (
    "# 1. Background",
    "# 2. Summary types",
    "# 3. Data ownership",
    "# 4. Non-goals",
    "# 5. Storage options",
    "# 6. Status and review workflow",
    "# 7. Separation from AI analysis/speculation",
    "# 8. Data model",
    "# 9. Evidence references",
    "# 10. Renderer integration plan",
    "# 11. Validation plan",
    "# 12. Implementation phases",
    "# 13. Non-goals",
    "# 14. Open questions",
)


def _read_design_doc() -> str:
    return STORY_SUMMARY_DESIGN_PATH.read_text(encoding="utf-8")


def test_design_doc_exists():
    assert STORY_SUMMARY_DESIGN_PATH.is_file()


def test_design_doc_has_required_sections():
    content = _read_design_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"必須セクションが不足しています: {missing}"


def test_design_doc_distinguishes_summary_types():
    content = _read_design_doc()
    assert "Story Summary" in content
    assert "Episode Summary" in content
    assert "AI Analysis" in content
    assert "Speculation" in content


def test_design_doc_excludes_ai_analysis_from_summary_schema():
    content = _read_design_doc()
    assert "本文書のSummary schemaには一切含めない" in content


def test_design_doc_states_no_raw_text_policy():
    content = _read_design_doc()
    assert "raw DEC textを含めない" in content
    assert "元セリフ全文を保存・表示しない" in content


def test_design_doc_states_evidence_refs_policy():
    content = _read_design_doc()
    assert "evidenceRefs" in content
    assert "必須にはしない" in content
    assert "Episode単位のID体系をそのまま維持する" in content


def test_design_doc_states_storage_policy():
    content = _read_design_doc()
    assert "knowledge/summaries/stories/{storyId}.yaml" in content
    assert "workspace/summary_drafts/" in content


def test_design_doc_states_status_and_review_workflow():
    content = _read_design_doc()
    for status in ("missing", "draft", "generated", "deprecated"):
        assert status in content
    for review_status in (
        "unreviewed",
        "reviewed",
        "approved",
        "rejected",
        "needs_revision",
    ):
        assert review_status in content


def test_design_doc_states_renderer_integration_plan():
    content = _read_design_doc()
    assert "Renderer integration plan" in content
    assert "--story-summaries" in content


def test_design_doc_does_not_implement_schema_or_renderer():
    """本PRではschema実装・renderer統合を行わない方針が
    Non-goalsに明記されていることの簡易チェック。"""
    content = _read_design_doc()
    non_goals_section = content.split("# 13. Non-goals", 1)[1]
    for forbidden in (
        "AI要約生成実装",
        "renderer integration実装",
        "Story page renderer変更",
    ):
        assert forbidden in non_goals_section


def test_story_page_design_links_to_story_summary_design():
    content = STORY_PAGE_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Story_Summary_Design.md" in content


def test_wiki_output_design_links_to_story_summary_design():
    content = WIKI_OUTPUT_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Story_Summary_Design.md" in content


def test_extraction_pipeline_links_to_story_summary_design():
    content = EXTRACTION_PIPELINE_PATH.read_text(encoding="utf-8")
    assert "Story_Summary_Design.md" in content


def test_tasks_md_lists_next_pr_candidates():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "story-summary-schema-implementation" in content
    assert "story-summary-renderer-integration" in content


def test_design_doc_states_evidence_index_linkification_implemented():
    """feature/evidence-index-renderer-integrationで、evidenceRefsが
    Evidence Indexへリンク化されたことが§9に記録されていることを確認する。"""
    content = _read_design_doc()
    evidence_section = content.split("# 9. Evidence references", 1)[1].split(
        "# 10. Renderer integration plan", 1
    )[0]
    integration_label = (
        "Evidence index renderer統合"
        "（`feature/evidence-index-renderer-integration`で実施）"
    )
    assert integration_label in evidence_section
    assert "--evidence-index" in evidence_section
