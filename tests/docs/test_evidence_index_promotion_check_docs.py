"""
tests/docs/test_evidence_index_promotion_check_docs.py
Evidence Index Promotion Check
(docs/runbooks/Evidence_Index_Promotion_Check.md /
scripts/check_evidence_index_promotion.py) に関するdocsの軽量な整合性テスト。

promotion check runbook・human review template・Evidence_Index_Promotion_
Policy.mdのpromotion script言及・TASKS.mdの次PR候補・Generation dry-run
runbookからのリンクを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
PROMOTION_CHECK_RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Evidence_Index_Promotion_Check.md"
)
REVIEW_TEMPLATE_PATH = (
    PROJECT_ROOT / "docs" / "templates" / "evidence_index_promotion_review_template.md"
)
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
TASKS_PATH = PROJECT_ROOT / "TASKS.md"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_evidence_index_promotion.py"

REQUIRED_RUNBOOK_SECTIONS = (
    "# 1. Purpose",
    "# 2. 前提",
    "# 3. スコープ",
    "# 4. public-default policy",
    "# 5. 実行手順",
    "# 6. Validation sequence",
    "# 7. Human review",
    "# 8. Source text exposure check",
    "# 9. Summary evidenceRefs整合性チェック方針",
    "# 10. commit前チェックリスト",
    "# 11. Non-goals",
    "# 12. Dry-run result",
    "# 13. Next steps",
)


def test_promotion_check_runbook_exists():
    assert PROMOTION_CHECK_RUNBOOK_PATH.is_file()


def test_promotion_check_script_exists():
    assert SCRIPT_PATH.is_file()


def test_review_template_exists():
    assert REVIEW_TEMPLATE_PATH.is_file()


def test_review_template_is_synthetic_only():
    content = REVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "合成の空欄テンプレート" in content
    assert "実施結果の記入・commitはしないこと" in content


def test_review_template_has_required_sections():
    content = REVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
    for section in (
        "## Target",
        "## Validation",
        "## Entry Summary",
        "## Public Type Policy",
        "## Source Text Exposure",
        "## Summary Evidence Refs",
        "## Decision",
        "## Notes",
    ):
        assert section in content


def test_promotion_check_runbook_has_required_sections():
    content = PROMOTION_CHECK_RUNBOOK_PATH.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_RUNBOOK_SECTIONS if s not in content]
    assert not missing, f"不足しているセクション: {missing}"


def test_promotion_check_runbook_states_no_copy_policy():
    content = PROMOTION_CHECK_RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "実際のcopy・commit・自動昇格は行わない" in content


def test_promotion_check_runbook_states_public_default_policy():
    content = PROMOTION_CHECK_RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "public-default" in content
    assert "stage_direction" in content
    for excluded in ("scene", "episode", "story", "speaker_label"):
        assert excluded in content


def test_promotion_check_runbook_references_actual_script_name():
    content = PROMOTION_CHECK_RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "check_evidence_index_promotion.py" in content
    assert "--story-summaries" in content
    assert "--report" in content
    assert "--policy" in content


def test_promotion_check_runbook_links_to_review_template():
    content = PROMOTION_CHECK_RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "evidence_index_promotion_review_template.md" in content


def test_promotion_policy_mentions_promotion_script():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    assert "check_evidence_index_promotion.py" in content


def test_promotion_policy_links_to_promotion_check_runbook():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Promotion_Check.md" in content


def test_evidence_index_design_mentions_promotion_script():
    content = EVIDENCE_INDEX_DESIGN_PATH.read_text(encoding="utf-8")
    assert "check_evidence_index_promotion.py" in content


def test_dry_run_runbook_links_to_promotion_check_runbook():
    content = DRY_RUN_RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Promotion_Check.md" in content


def test_tasks_md_lists_next_pr_candidates():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-promotion-dry-run" in content
    assert "evidence-index-promotion-copy-script" in content
    assert "internal-review-evidence-packet-design" in content


def test_promotion_check_runbook_has_dry_run_result_section():
    content = PROMOTION_CHECK_RUNBOOK_PATH.read_text(encoding="utf-8")
    dry_run_section = content.split("# 12. Dry-run result", 1)[1].split(
        "# 13. Next steps", 1
    )[0]
    assert "187" in dry_run_section
    assert "PASS" in dry_run_section
    assert "匿名化" in dry_run_section


def test_promotion_check_runbook_has_known_limitations_and_follow_up():
    content = PROMOTION_CHECK_RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "Known limitations" in content
    assert "Follow-up tasks" in content


def test_promotion_check_runbook_does_not_contain_real_data_hints():
    """実イベント名・実ファイル名・rawPathを書かない方針の簡易チェック。"""
    content = PROMOTION_CHECK_RUNBOOK_PATH.read_text(encoding="utf-8")
    for forbidden in ("C:\\Users", "D:\\Dev", "EVT_260425", "CAMI3RD"):
        assert forbidden not in content
