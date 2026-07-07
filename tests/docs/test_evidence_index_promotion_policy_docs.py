"""
tests/docs/test_evidence_index_promotion_policy_docs.py
Evidence Index Promotion Policy
(docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md) の
軽量な整合性テスト。

PR #85のdry-run結果レビュー・stage_direction大量entry問題・初期公開対象
entry type方針・promotion/exclusion criteria・filter policy・Evidence
page size policy・candidate references方針・Summary evidenceRefs優先
方針・source text exposure checklist・human review checklistが明記
されていること、既存docs（Evidence_Index_Design.md/
Evidence_Index_Generation_Dry_Run.md/Wiki_Output_Design.md）・
TASKS.mdから参照されていることを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
PROMOTION_POLICY_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "06_AI"
    / "Evidence_Index_Promotion_Policy.md"
)
EVIDENCE_INDEX_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Evidence_Index_Design.md"
)
DRY_RUN_RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Evidence_Index_Generation_Dry_Run.md"
)
WIKI_OUTPUT_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "07_Wiki" / "Wiki_Output_Design.md"
)
TASKS_PATH = PROJECT_ROOT / "TASKS.md"

REQUIRED_SECTIONS = (
    "# 1. Background",
    "# 2. Dry-run result summary",
    "# 3. Problem: stage_direction explosion",
    "# 4. Public evidence type policy",
    "# 5. Promotion criteria",
    "# 6. Exclusion criteria",
    "# 7. Filter policy",
    "# 8. Evidence page size policy",
    "# 9. Candidate references policy",
    "# 10. Summary evidenceRefsとの関係",
    "# 11. Source text exposure checklist",
    "# 12. Human review checklist",
    "# 13. Implementation phases",
    "# 14. Non-goals",
    "# 15. 未確定事項",
)


def _read_policy_doc() -> str:
    return PROMOTION_POLICY_PATH.read_text(encoding="utf-8")


def test_policy_doc_exists():
    assert PROMOTION_POLICY_PATH.is_file()


def test_policy_doc_has_required_sections():
    content = _read_policy_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"必須セクションが不足しています: {missing}"


def test_policy_doc_states_dry_run_result_summary():
    content = _read_policy_doc()
    for value in ("1793", "1606", "153", "26", "6"):
        assert value in content
    assert "stage_direction" in content


def test_policy_doc_compares_stage_direction_candidates():
    content = _read_policy_doc()
    for heading in ("候補A", "候補B", "候補C"):
        assert heading in content
    assert "候補Cを基本としつつ" in content


def test_policy_doc_states_initial_public_evidence_types():
    content = _read_policy_doc()
    for evidence_type in ("dialogue", "monologue", "narration", "choice", "unknown"):
        assert evidence_type in content
    for excluded_type in ("scene", "episode", "story", "speaker_label"):
        assert excluded_type in content


def test_policy_doc_has_promotion_and_exclusion_criteria():
    content = _read_policy_doc()
    promotion_section = content.split("# 5. Promotion criteria", 1)[1].split(
        "# 6. Exclusion criteria", 1
    )[0]
    assert "schema validation" in promotion_section
    assert "validate_evidence_index.py" in promotion_section
    assert "source text exposure check" in promotion_section
    exclusion_section = content.split("# 6. Exclusion criteria", 1)[1].split(
        "# 7. Filter policy", 1
    )[0]
    assert "unreviewed" in exclusion_section


def test_policy_doc_states_filter_policy():
    content = _read_policy_doc()
    filter_section = content.split("# 7. Filter policy", 1)[1].split(
        "# 8. Evidence page size policy", 1
    )[0]
    assert "--include-types" in filter_section
    assert "--exclude-types" in filter_section
    assert "本PRでは実装しない" in filter_section


def test_policy_doc_states_evidence_page_size_policy():
    content = _read_policy_doc()
    size_section = content.split("# 8. Evidence page size policy", 1)[1].split(
        "# 9. Candidate references policy", 1
    )[0]
    assert "Episode別Evidence page" in size_section


def test_policy_doc_states_candidate_references_policy():
    content = _read_policy_doc()
    section = content.split("# 9. Candidate references policy", 1)[1].split(
        "# 10. Summary evidenceRefs", 1
    )[0]
    assert "referencedBy.candidates" in section


def test_policy_doc_states_summary_evidence_refs_priority():
    content = _read_policy_doc()
    section = content.split("# 10. Summary evidenceRefs", 1)[1].split(
        "# 11. Source text exposure checklist", 1
    )[0]
    assert "優先する" in section


def test_policy_doc_has_source_text_exposure_checklist():
    content = _read_policy_doc()
    section = content.split("# 11. Source text exposure checklist", 1)[1].split(
        "# 12. Human review checklist", 1
    )[0]
    for pattern in ("@ChTalk", "$num", "C:\\", "D:\\"):
        assert pattern in section


def test_policy_doc_states_non_goals():
    content = _read_policy_doc()
    non_goals_section = content.split("# 14. Non-goals", 1)[1].split(
        "# 15. 未確定事項", 1
    )[0]
    for forbidden in (
        "Evidence Index filter実装",
        "Evidence Index promotion script実装",
        "knowledge/evidence/stories/",
        "Internal Review Evidence Packet生成",
    ):
        assert forbidden in non_goals_section


def test_evidence_index_design_links_to_promotion_policy():
    content = EVIDENCE_INDEX_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Promotion_Policy.md" in content


def test_dry_run_runbook_links_to_promotion_policy():
    content = DRY_RUN_RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Promotion_Policy.md" in content


def test_wiki_output_design_links_to_promotion_policy():
    content = WIKI_OUTPUT_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Promotion_Policy.md" in content


def test_tasks_md_lists_next_pr_candidates():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-generation-filtering" in content
    assert "evidence-index-promotion-policy-implementation" in content
