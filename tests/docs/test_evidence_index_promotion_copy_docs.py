"""
tests/docs/test_evidence_index_promotion_copy_docs.py
Evidence Index Promotion Copy
(docs/runbooks/Evidence_Index_Promotion_Copy.md /
scripts/promote_evidence_index.py) に関するdocsの軽量な整合性テスト。

promotion copy runbookの必須項目（dry-run既定・--execute必須・review note
必須・overwrite方針）、既存docsからのリンク、TASKS.mdの次PR候補を確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
PROMOTION_COPY_RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Evidence_Index_Promotion_Copy.md"
)
PROMOTION_CHECK_RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Evidence_Index_Promotion_Check.md"
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
TASKS_PATH = PROJECT_ROOT / "TASKS.md"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "promote_evidence_index.py"

REQUIRED_RUNBOOK_SECTIONS = (
    "# 1. Purpose",
    "# 2. 前提",
    "# 3. Required inputs",
    "# 4. Dry-run command",
    "# 5. Execute command",
    "# 6. Overwrite policy",
    "# 7. Review note requirement",
    "# 8. Target path",
    "# 9. Report出力",
    "# 10. Safety checks",
    "# 11. Commit safety checklist",
    "# 12. Non-goals",
    "# 13. First reviewed sample flow",
    "# 14. 関連ドキュメント",
)


def _read_runbook() -> str:
    return PROMOTION_COPY_RUNBOOK_PATH.read_text(encoding="utf-8")


def test_promotion_copy_runbook_exists():
    assert PROMOTION_COPY_RUNBOOK_PATH.is_file()


def test_promotion_copy_script_exists():
    assert SCRIPT_PATH.is_file()


def test_promotion_copy_runbook_has_required_sections():
    content = _read_runbook()
    missing = [s for s in REQUIRED_RUNBOOK_SECTIONS if s not in content]
    assert not missing, f"不足しているセクション: {missing}"


def test_promotion_copy_runbook_mentions_dry_run_default():
    content = _read_runbook()
    assert "デフォルトは常にdry-run" in content
    assert "何もcopyしない" in content


def test_promotion_copy_runbook_mentions_execute_flag():
    content = _read_runbook()
    assert "--execute" in content
    assert "明示指定しない限り一切ファイルを書き込まない" in content


def test_promotion_copy_runbook_mentions_review_note_required():
    content = _read_runbook()
    assert "--review-note" in content
    assert "Approved for promotion" in content
    assert "Needs revision" in content
    assert "Rejected" in content


def test_promotion_copy_runbook_mentions_overwrite_policy():
    content = _read_runbook()
    assert "--overwrite" in content
    overwrite_section = content.split("# 6. Overwrite policy", 1)[1].split(
        "# 7. Review note requirement", 1
    )[0]
    assert "既定では上書き禁止" in overwrite_section


def test_promotion_copy_runbook_mentions_target_path():
    content = _read_runbook()
    assert "knowledge/evidence/stories" in content
    assert "--allow-nonstandard-target" in content


def test_promotion_copy_runbook_states_no_commit_by_script():
    content = _read_runbook()
    assert "本scriptはcopyのみを行い、`git add`/`git commit`は行わない" in content


def test_promotion_check_runbook_links_to_promotion_copy():
    content = PROMOTION_CHECK_RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Promotion_Copy.md" in content


def test_promotion_policy_mentions_promotion_copy_script():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    assert "promote_evidence_index.py" in content


def test_promotion_policy_links_to_promotion_copy_runbook():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Promotion_Copy.md" in content


def test_evidence_index_design_mentions_promotion_copy_script():
    content = EVIDENCE_INDEX_DESIGN_PATH.read_text(encoding="utf-8")
    assert "promote_evidence_index.py" in content


def test_tasks_md_lists_next_pr_candidates():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-promotion-first-reviewed-sample" in content
    assert "evidence-index-promotion-copy-script-hardening" in content
    assert "internal-review-evidence-packet-design" in content


def test_tasks_md_records_no_real_data_commit():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "実データEvidence Indexのcommitは未実施" in content


# ----------------------------------------------------------------
# feature/evidence-index-promotion-first-reviewed-sample
# ----------------------------------------------------------------


def test_promotion_copy_runbook_has_first_reviewed_sample_result():
    content = _read_runbook()
    assert "## 13.1 初回実施結果" in content
    section = content.split("## 13.1 初回実施結果", 1)[1].split(
        "# 14. 関連ドキュメント", 1
    )[0]
    assert "187" in section
    assert "見送った" in section


def test_promotion_copy_runbook_states_target_filename_concern():
    content = _read_runbook()
    section = content.split("## 13.1 初回実施結果", 1)[1].split(
        "# 14. 関連ドキュメント", 1
    )[0]
    assert "sourceKey由来" in section
    assert "publicStoryId" in section
    assert "Git履歴に永続的に残る" in section


def test_promotion_copy_runbook_does_not_contain_real_data_hints():
    """実イベント名・実ファイル名・raw pathを書かない方針の簡易チェック。"""
    content = _read_runbook()
    for forbidden in ("CAMI3RD", "260425", "C:\\Users", "D:\\Dev", ".dec\n"):
        assert forbidden not in content


def test_promotion_policy_states_first_sample_result():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    assert (
        "実施結果（`feature/evidence-index-promotion-first-reviewed-sample`" in content
    )
    assert "見送った" in content


def test_promotion_policy_open_questions_mentions_filename_policy():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    open_questions_section = content.split("# 15. 未確定事項", 1)[1].split(
        "# 16. 参照", 1
    )[0]
    assert "publicStoryId" in open_questions_section
    assert "ファイル名" in open_questions_section


def test_tasks_md_lists_target_filename_policy_next_candidate():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-promotion-target-filename-policy" in content
    assert "evidence-index-promotion-first-sample-visual-review" in content


def test_tasks_md_does_not_contain_real_data_hints():
    content = TASKS_PATH.read_text(encoding="utf-8")
    for forbidden in ("CAMI3RD", "260425", "C:\\Users", "D:\\Dev"):
        assert forbidden not in content
