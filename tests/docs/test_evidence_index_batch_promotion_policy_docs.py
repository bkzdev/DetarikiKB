"""
tests/docs/test_evidence_index_batch_promotion_policy_docs.py
Evidence Index Batch Promotion Policy
(docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md) に関するdocsの
軽量な整合性テスト。

batch size方針・Registry entry review条件・promotion前後チェックリスト・
visual review方針・failed story/rollback方針・PR分割方針・次PRスコープが
文書化されていること、既存docsからのリンク、TASKS.mdの次PR候補、実データ
ヒント（sourceKey/実タイトル）が含まれていないことを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
BATCH_POLICY_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Evidence_Index_Batch_Promotion_Policy.md"
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
PROMOTION_COPY_RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Evidence_Index_Promotion_Copy.md"
)
PROMOTION_CHECK_RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Evidence_Index_Promotion_Check.md"
)
PUBLIC_ID_REGISTRY_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Public_ID_Registry_Design.md"
)
TASKS_PATH = PROJECT_ROOT / "TASKS.md"

REQUIRED_SECTIONS = (
    "# 1. Purpose",
    "# 2. Background",
    "# 3. Basic policy",
    "# 4. Batch size policy",
    "# 5. Registry entry review条件",
    "# 6. Promotion前チェックリスト",
    "# 7. Promotion後チェックリスト",
    "# 8. Visual review方針",
    "# 9. Failed story handling",
    "# 10. Rollback policy",
    "# 11. PR分割方針",
    "# 12. `evidence-index-promotion-first-batch-dry-run`",
    "# 13. Non-goals",
    "# 14. 関連ドキュメント",
)

REAL_DATA_HINTS = ("CAMI3RD", "260425", "260707", "C:\\Users", "D:\\Dev")


def _read_doc() -> str:
    return BATCH_POLICY_PATH.read_text(encoding="utf-8")


def test_batch_policy_doc_exists():
    assert BATCH_POLICY_PATH.is_file()


def test_batch_policy_doc_has_required_sections():
    content = _read_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"不足しているセクション: {missing}"


def test_batch_policy_doc_states_batch_size_table():
    content = _read_doc()
    section = content.split("# 4. Batch size policy", 1)[1].split(
        "# 5. Registry entry review条件", 1
    )[0]
    for phase_label in ("Phase 2", "Phase 3", "Phase 4", "Phase 5"):
        assert phase_label in section
    assert "3" in section
    assert "5" in section
    assert "明示的な承認があるまで許可しない" in section


def test_batch_policy_doc_states_registry_review_conditions():
    content = _read_doc()
    section = content.split("# 5. Registry entry review条件", 1)[1].split(
        "# 6. Promotion前チェックリスト", 1
    )[0]
    assert "publicStoryId" in section
    assert "publicEpisodeId" in section
    assert "check_public_episode_ids.py" in section
    assert "duplicate" in section.lower()


def test_batch_policy_doc_states_pre_promotion_checklist():
    content = _read_doc()
    section = content.split("# 6. Promotion前チェックリスト", 1)[1].split(
        "# 7. Promotion後チェックリスト", 1
    )[0]
    for script in (
        "check_public_episode_ids.py",
        "project_evidence_index_public_ids.py",
        "validate_evidence_index.py",
        "check_evidence_index_promotion.py",
        "render_wiki.py",
        "promote_evidence_index.py",
    ):
        assert script in section
    assert "human review note" in section
    assert "Approved for promotion" in section


def test_batch_policy_doc_states_post_promotion_checklist():
    content = _read_doc()
    section = content.split("# 7. Promotion後チェックリスト", 1)[1].split(
        "# 8. Visual review方針", 1
    )[0]
    assert "validate_evidence_index.py" in section
    assert "check_evidence_index_promotion.py" in section
    assert "mkdocs build --strict" in section
    assert "CI" in section


def test_batch_policy_doc_states_visual_review_policy():
    content = _read_doc()
    section = content.split("# 8. Visual review方針", 1)[1].split(
        "# 9. Failed story handling", 1
    )[0]
    assert "publicEvidenceId" in section
    assert "publicStoryId" in section
    assert "stage_direction" in section
    assert "batch全体を止める" in section


def test_batch_policy_doc_states_failed_story_categories():
    content = _read_doc()
    section = content.split("# 9. Failed story handling", 1)[1].split(
        "# 10. Rollback policy", 1
    )[0]
    for category in (
        "Registry missing",
        "Registry conflict",
        "publicEpisodeId missing",
        "projection failure",
        "validation failure",
        "promotion check failure",
        "exposure failure",
        "render failure",
        "visual review failure",
    ):
        assert category in section


def test_batch_policy_doc_states_rollback_policy():
    content = _read_doc()
    section = content.split("# 10. Rollback policy", 1)[1].split("# 11. PR分割方針", 1)[
        0
    ]
    assert "1 story 1 file" in section
    assert "再利用しない" in section
    assert "exposure check" in section


def test_batch_policy_doc_states_pr_split_policy():
    content = _read_doc()
    section = content.split("# 11. PR分割方針", 1)[1].split(
        "# 12. `evidence-index-promotion-first-batch-dry-run`", 1
    )[0]
    assert "案A" in section
    assert "案B" in section
    assert "案C" in section


def test_batch_policy_doc_states_first_batch_dry_run_scope():
    content = _read_doc()
    heading = "# 12. `evidence-index-promotion-first-batch-dry-run`"
    assert heading in content
    section = content.split(heading, 1)[1].split("# 13. Non-goals", 1)[0]
    assert "## 12.1 やること" in section
    assert "## 12.2 やらないこと" in section
    assert "実promotion" in section
    assert "Registry entryの実commit" in section


def test_batch_policy_doc_states_non_goals():
    content = _read_doc()
    section = content.split("# 13. Non-goals", 1)[1].split("# 14. 関連ドキュメント", 1)[
        0
    ]
    for forbidden in (
        "複数story分のEvidence Index/Registry entryのcommit",
        "batch promotionの実行",
        "batch promotion script",
    ):
        assert forbidden in section


def test_batch_policy_doc_does_not_contain_real_data_hints():
    content = _read_doc()
    for forbidden in REAL_DATA_HINTS:
        assert forbidden not in content


def test_promotion_policy_links_to_batch_policy():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Batch_Promotion_Policy.md" in content
    assert "evidence-index-promotion-batch-policy" in content


def test_evidence_index_design_links_to_batch_policy():
    content = EVIDENCE_INDEX_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Batch_Promotion_Policy.md" in content


def test_promotion_copy_runbook_links_to_batch_policy():
    content = PROMOTION_COPY_RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Batch_Promotion_Policy.md" in content
    assert "### 13.10 進捗" in content


def test_promotion_check_runbook_links_to_batch_policy():
    content = PROMOTION_CHECK_RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Batch_Promotion_Policy.md" in content


def test_public_id_registry_design_links_to_batch_policy():
    content = PUBLIC_ID_REGISTRY_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Batch_Promotion_Policy.md" in content


def test_tasks_md_lists_batch_dry_run_next_candidate():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-promotion-first-batch-dry-run" in content
    assert "internal-review-evidence-packet-design" in content
    assert "story-summary-generation-planning" in content
    assert "public-publishing-platform-evaluation" in content


def test_tasks_md_does_not_contain_real_data_hints():
    content = TASKS_PATH.read_text(encoding="utf-8")
    for forbidden in ("CAMI3RD", "260425", "260707", "C:\\Users", "D:\\Dev"):
        assert forbidden not in content


# ----------------------------------------------------------------
# feature/evidence-index-promotion-first-batch-dry-run
# ----------------------------------------------------------------

DRY_RUN_RESULT_HEADING = "## 4.2 Phase 2 dry-run実施結果"


def test_batch_policy_doc_states_dry_run_result():
    content = _read_doc()
    assert DRY_RUN_RESULT_HEADING in content
    section = content.split(DRY_RUN_RESULT_HEADING, 1)[1].split("---", 1)[0]
    assert "tooling観点はすべてPASS" in section
    assert "internal_id_exposure=0" in section
    assert "推奨しない" in section


def test_batch_policy_doc_dry_run_result_states_findings():
    content = _read_doc()
    section = content.split(DRY_RUN_RESULT_HEADING, 1)[1].split("---", 1)[0]
    assert "unknown" in section
    assert "Story page" in section
    assert "Failed story count: 0" in section


def test_batch_policy_doc_dry_run_result_does_not_contain_real_data_hints():
    content = _read_doc()
    section = content.split(DRY_RUN_RESULT_HEADING, 1)[1].split("---", 1)[0]
    for forbidden in REAL_DATA_HINTS + ("260624", "260504", "CAB-csl"):
        assert forbidden not in section


def test_batch_policy_doc_states_scope_already_executed():
    content = _read_doc()
    section = content.split(
        "# 12. `evidence-index-promotion-first-batch-dry-run`のスコープ", 1
    )[1].split("# 13. Non-goals", 1)[0]
    assert "実施済み" in section


def test_promotion_copy_runbook_states_batch_dry_run_result():
    content = PROMOTION_COPY_RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "### 13.11 進捗" in content
    section = content.split("### 13.11 進捗", 1)[1].split("# 14. 関連ドキュメント", 1)[
        0
    ]
    assert "実Registry entry・実Evidence Indexのcommitはいずれも行っていない" in section
    assert "Failed story count: 0" in section


def test_promotion_copy_runbook_batch_dry_run_does_not_contain_real_data_hints():
    content = PROMOTION_COPY_RUNBOOK_PATH.read_text(encoding="utf-8")
    section = content.split("### 13.11 進捗", 1)[1].split("# 14. 関連ドキュメント", 1)[
        0
    ]
    for forbidden in REAL_DATA_HINTS + ("260624", "260504", "CAB-csl"):
        assert forbidden not in section


def test_tasks_md_lists_batch_tooling_and_manifest_next_candidates():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-promotion-batch-tooling" in content
    assert "story-manifest-public-story-id-real-data-assignment" in content


def test_tasks_md_does_not_contain_dry_run_source_hints():
    content = TASKS_PATH.read_text(encoding="utf-8")
    for forbidden in ("260624", "260504", "CAB-csl"):
        assert forbidden not in content
