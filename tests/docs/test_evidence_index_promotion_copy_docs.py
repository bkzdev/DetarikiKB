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
