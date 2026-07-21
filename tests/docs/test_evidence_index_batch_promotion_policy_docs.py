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

from _public_id_registry_hints import filter_unregistered_hints

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
    "# 11. 公開済みEvidence Indexの更新（re-promotion）方針",
    "# 12. PR分割方針",
    "# 13. `evidence-index-promotion-first-batch-dry-run`",
    "# 14. Non-goals",
    "# 15. 関連ドキュメント",
    "# 16. publicStoryId命名規約v2への移行実行手順",
)

REAL_DATA_HINTS = (
    "CAMI3RD",
    "260425",
    # "260707"/"260712"は§16.3で移行対象と確定した旧publicStoryId（v1、
    # Registry登録日ベース）の日付断片であり、sourceKey由来の実データを
    # 含まないと既に判断済み（`Evidence_Index_Public_ID_Policy.md` §16.3参
    # 照）。移行実行PR（publicStoryId命名規約v2移行）でRegistryから旧
    # entryが削除された後も、旧IDそのものは本文書§16.2の手順定義・
    # `Evidence_Index_Public_ID_Policy.md` §16.3の新旧mapping表に記載され
    # 続けるため、恒久的にforbidden hintsから除外する。
    "C:\\Users",
    "D:\\Dev",
)


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
    section = content.split("# 10. Rollback policy", 1)[1].split(
        "# 11. 公開済みEvidence Indexの更新（re-promotion）方針", 1
    )[0]
    assert "1 story 1 file" in section
    assert "再利用しない" in section
    assert "exposure check" in section


def test_batch_policy_doc_states_pr_split_policy():
    content = _read_doc()
    section = content.split("# 12. PR分割方針", 1)[1].split(
        "# 13. `evidence-index-promotion-first-batch-dry-run`", 1
    )[0]
    assert "案A" in section
    assert "案B" in section
    assert "案C" in section


def test_batch_policy_doc_states_first_batch_dry_run_scope():
    content = _read_doc()
    heading = "# 13. `evidence-index-promotion-first-batch-dry-run`"
    assert heading in content
    section = content.split(heading, 1)[1].split("# 14. Non-goals", 1)[0]
    assert "## 13.1 やること" in section
    assert "## 13.2 やらないこと" in section
    assert "実promotion" in section
    assert "Registry entryの実commit" in section


def test_batch_policy_doc_states_non_goals():
    content = _read_doc()
    section = content.split("# 14. Non-goals", 1)[1].split("# 15. 関連ドキュメント", 1)[
        0
    ]
    for forbidden in (
        "複数story分のEvidence Index/Registry entryのcommit",
        "batch promotionの実行",
        "batch promotion script",
    ):
        assert forbidden in section


def test_batch_policy_doc_does_not_contain_real_data_hints():
    # Registry連動許可リスト方式（tests/docs/_public_id_registry_hints.py）:
    # §16の移行実行手順で言及する既存Evidence Indexファイル名（旧publicStoryId
    # 由来、Registryに正式登録済みで割当日ベース・sourceKey由来ではない）は
    # 許可されるが、それ以外の実データ日付断片・イベント名断片は引き続き
    # 検出される。
    content = _read_doc()
    for forbidden in filter_unregistered_hints(REAL_DATA_HINTS):
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
        "# 13. `evidence-index-promotion-first-batch-dry-run`のスコープ", 1
    )[1].split("# 14. Non-goals", 1)[0]
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
    # §13.12以降は本PR（evidence-index-promotion-first-real-batch）の実施記録で、
    # 具体的なpublicStoryId値（260712）を書いてよいセクションのため、§13.11の
    # 終端は次見出し（§13.12）までとし、§13.12を巻き込まないようにする。
    section = content.split("### 13.11 進捗", 1)[1].split("### 13.12 進捗", 1)[0]
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


# ----------------------------------------------------------------
# feature/evidence-index-batch-candidate-selection-policy
# ----------------------------------------------------------------

SELECTION_CRITERIA_HEADING = "## 4.3 Candidate selection criteria（候補storyの選定基準"


def _selection_criteria_section() -> str:
    content = _read_doc()
    return content.split(SELECTION_CRITERIA_HEADING, 1)[1].split(
        STAGE2_BATCH_PROMOTION_HEADING, 1
    )[0]


def test_batch_policy_doc_has_selection_criteria_section():
    content = _read_doc()
    assert SELECTION_CRITERIA_HEADING in content


def test_batch_policy_doc_states_selection_thresholds():
    section = _selection_criteria_section()
    assert "unknown比率" in section
    assert "10%" in section
    assert "30%" in section
    assert "70%" in section
    assert "600" in section


def test_batch_policy_doc_states_selection_classification_labels():
    section = _selection_criteria_section()
    for label in ("promotion-candidate", "parser-improvement-wait", "excluded"):
        assert label in section


def test_batch_policy_doc_states_parser_compatibility_handling():
    section = _selection_criteria_section()
    for value in ("compatible", "warning", "needs_update", "blocked"):
        assert value in section


def test_batch_policy_doc_states_real_batch_promotion_prerequisites():
    section = _selection_criteria_section()
    assert "real batch promotionへ進むための最低条件" in section
    assert "Story page" in section
    assert "最大3 story" in section


def test_batch_policy_doc_states_roadmap():
    section = _selection_criteria_section()
    assert "script-command-dictionary-expansion-batch-001" in section
    assert "story-manifest-public-story-id-real-data-assignment" in section
    assert "evidence-index-promotion-second-batch-dry-run" in section
    assert "evidence-index-promotion-first-real-batch" in section


def test_batch_policy_doc_states_pr102_classification():
    section = _selection_criteria_section()
    assert "parser-improvement-wait" in section
    assert "PR #102" in section


def test_batch_policy_doc_states_batch_tooling_cli_usage_and_outputs():
    section = _selection_criteria_section()
    assert "scripts/classify_promotion_candidates.py" in section
    assert "storyReports[].entriesByEvidenceType" in section
    assert (
        "--report workspace/evidence_index_dry_runs/<run>/default/report.json"
        in section
    )
    assert "--normalized-input data/normalized/<category>" in section
    assert "classification_report.json" in section
    assert "classification_report.md" in section
    assert "promotionCandidateStoryIds" in section
    assert "--public-profile default" in section
    assert "commitしない" in section


def test_batch_policy_doc_marks_batch_tooling_implemented_after_original_non_goal():
    section = _selection_criteria_section()
    assert "evidence-index-promotion-batch-tooling" in section
    assert "実装済み" in section
    assert "当初のNon-goal" in section


def test_batch_policy_doc_selection_criteria_does_not_contain_real_data_hints():
    section = _selection_criteria_section()
    for forbidden in REAL_DATA_HINTS + ("260624", "260504", "CAB-csl"):
        assert forbidden not in section


def test_promotion_policy_references_selection_criteria():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    assert "evidence-index-batch-candidate-selection-policy" in content
    assert "Evidence_Index_Batch_Promotion_Policy.md" in content


def test_tasks_md_lists_script_command_dictionary_next_candidate():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "script-command-dictionary-expansion-batch-001" in content
    assert "evidence-index-promotion-second-batch-dry-run" in content


# ----------------------------------------------------------------
# feature/story-manifest-public-story-id-real-data-assignment
# ----------------------------------------------------------------

SECOND_BATCH_DRY_RUN_HEADING = (
    "## 4.5 `story-manifest-public-story-id-real-data-assignment`実施結果"
)


def _second_batch_dry_run_section() -> str:
    content = _read_doc()
    return content.split(SECOND_BATCH_DRY_RUN_HEADING, 1)[1].split(
        STAGE2_BATCH_PROMOTION_HEADING, 1
    )[0]


def test_batch_policy_doc_has_second_batch_dry_run_section():
    content = _read_doc()
    assert SECOND_BATCH_DRY_RUN_HEADING in content


def test_batch_policy_doc_states_second_batch_dry_run_roadmap_steps():
    section = _second_batch_dry_run_section()
    assert "ロードマップ手順2" in section
    assert "手順3" in section
    assert "{publicStoryId}" in section
    assert "{publicEpisodeId}" in section


def test_batch_policy_doc_states_story_page_linkage_resolved():
    section = _second_batch_dry_run_section()
    assert "Review Links" in section
    assert "Evidence index" in section
    assert "resolve_story_evidence_entries" in section
    assert "by_public_story_id" in section
    assert "evidence-index-public-id-renderer-switch" in section


def test_batch_policy_doc_states_second_batch_dry_run_matrix():
    section = _second_batch_dry_run_section()
    assert "promotion-candidate" in section
    assert "warning" in section
    assert "0%" in section
    assert "Failed story count: 0" in section
    assert "excluded story count: 0" in section


def test_batch_policy_doc_states_ready_for_first_real_batch():
    section = _second_batch_dry_run_section()
    assert "evidence-index-promotion-first-real-batch" in section
    assert "進める状態と判定" in section


def test_batch_policy_doc_second_batch_dry_run_states_non_goals():
    section = _second_batch_dry_run_section()
    assert "promote_evidence_index.py" in section
    assert "--execute" in section
    assert "commit" in section.lower()


def test_batch_policy_doc_second_batch_dry_run_does_not_contain_real_data_hints():
    section = _second_batch_dry_run_section()
    for forbidden in REAL_DATA_HINTS + ("260624", "260504", "CAB-csl"):
        assert forbidden not in section


def test_tasks_md_lists_first_real_batch_next_candidate():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-promotion-first-real-batch" in content
    assert "story-manifest-public-story-id-real-data-assignment" in content


def test_tasks_md_second_batch_dry_run_does_not_contain_real_data_hints():
    content = TASKS_PATH.read_text(encoding="utf-8")
    for forbidden in REAL_DATA_HINTS + ("260624", "260504", "CAB-csl"):
        assert forbidden not in content


# ----------------------------------------------------------------
# feature/evidence-index-promotion-first-real-batch
# ----------------------------------------------------------------

FIRST_REAL_BATCH_HEADING = "## 4.6 `evidence-index-promotion-first-real-batch`実施結果"


def _first_real_batch_section() -> str:
    content = _read_doc()
    return content.split(FIRST_REAL_BATCH_HEADING, 1)[1].split(
        STAGE2_BATCH_PROMOTION_HEADING, 1
    )[0]


def test_batch_policy_doc_has_first_real_batch_section():
    content = _read_doc()
    assert FIRST_REAL_BATCH_HEADING in content


def test_batch_policy_doc_states_first_real_batch_registry_review():
    section = _first_real_batch_section()
    assert "publicStoryId" in section
    assert "publicEpisodeId" in section
    assert "check_public_episode_ids.py" in section
    assert "8項目" in section


def test_batch_policy_doc_states_first_real_batch_pre_checklist_results():
    section = _first_real_batch_section()
    for script in (
        "check_public_episode_ids.py",
        "project_evidence_index_public_ids.py",
        "validate_evidence_index.py",
        "check_evidence_index_promotion.py",
        "render_wiki.py",
        "promote_evidence_index.py",
    ):
        assert script in section
    assert "205 entries" in section
    assert "internal_id_exposure=0" in section
    assert "Approved for promotion" in section


def test_batch_policy_doc_states_first_real_batch_execute_result():
    section = _first_real_batch_section()
    assert "--execute" in section
    assert "2ファイル" in section or "2件" in section
    assert "git status" in section


def test_batch_policy_doc_states_first_real_batch_post_checklist_results():
    section = _first_real_batch_section()
    assert "392 entries" in section
    assert "mkdocs build --strict" in section


def test_batch_policy_doc_states_first_real_batch_conclusion():
    section = _first_real_batch_section()
    assert "Failed story count: 0" in section
    assert "Phase 3を完了とする" in section


def test_batch_policy_doc_first_real_batch_states_non_goals():
    section = _first_real_batch_section()
    assert "3 story目以降の追加" in section
    assert "既存の昇格済みstory" in section


def test_batch_policy_doc_first_real_batch_does_not_contain_real_data_hints():
    section = _first_real_batch_section()
    for forbidden in REAL_DATA_HINTS + ("260624", "260504", "CAB-csl"):
        assert forbidden not in section


def test_batch_policy_doc_phase3_marked_complete():
    content = _read_doc()
    section = content.split("# 4. Batch size policy", 1)[1].split(
        "# 5. Registry entry review条件", 1
    )[0]
    assert "Phase 3" in section
    assert "完了" in section
    assert "evidence-index-promotion-first-real-batch" in section


def test_tasks_md_lists_first_real_batch_current_focus():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-promotion-first-real-batch" in content
    assert "evidence-index-promotion-batch-tooling" in content
    assert "internal-review-evidence-packet-design" in content


def test_tasks_md_first_real_batch_does_not_contain_real_data_hints():
    content = TASKS_PATH.read_text(encoding="utf-8")
    for forbidden in REAL_DATA_HINTS + ("260624", "260504", "CAB-csl"):
        assert forbidden not in content


# ----------------------------------------------------------------
# feature/evidence-index-republication-policy-dry-run
# ----------------------------------------------------------------

REPUBLICATION_POLICY_HEADING = "# 11. 公開済みEvidence Indexの更新（re-promotion）方針"


def _republication_policy_section() -> str:
    content = _read_doc()
    return content.split(REPUBLICATION_POLICY_HEADING, 1)[1].split(
        "# 12. PR分割方針", 1
    )[0]


def test_batch_policy_doc_has_republication_policy_section():
    content = _read_doc()
    assert REPUBLICATION_POLICY_HEADING in content


def test_batch_policy_doc_states_republication_id_stability_gate():
    section = _republication_policy_section()
    assert "publicEvidenceId" in section
    assert "完全一致" in section
    assert "blocking" in section
    assert "エスカレーション" in section


def test_batch_policy_doc_states_republication_allowed_diff_scope():
    section = _republication_policy_section()
    assert "unresolved" in section
    assert "resolved" in section
    assert "relatedEntities" in section
    assert "text" in section


def test_batch_policy_doc_states_republication_procedure():
    section = _republication_policy_section()
    for script in (
        "project_evidence_index_public_ids.py",
        "promote_evidence_index.py",
        "validate_evidence_index.py",
        "check_evidence_index_promotion.py",
        "render_wiki.py",
        "mkdocs build --strict",
    ):
        assert script in section
    assert "--execute --overwrite" in section
    assert "ユーザーの明示的な事前承認" in section


def test_batch_policy_doc_states_republication_summary_handling():
    section = _republication_policy_section()
    assert "knowledge/summaries/stories/" in section
    assert "evidenceRefs" in section


def test_batch_policy_doc_states_republication_rollback_inherits_existing():
    section = _republication_policy_section()
    assert "§10" in section
    assert "git revert" in section


def test_batch_policy_doc_states_republication_dry_run_result():
    section = _republication_policy_section()
    assert "392 entries" in section
    assert "148" in section
    assert "blocking" in section
    assert "見送" in section


def test_batch_policy_doc_republication_states_non_goals():
    section = _republication_policy_section()
    assert "--execute" in section
    assert "commit" in section.lower()


def test_batch_policy_doc_republication_does_not_contain_real_data_hints():
    section = _republication_policy_section()
    for forbidden in REAL_DATA_HINTS + ("260624", "260504", "CAB-csl"):
        assert forbidden not in section


def test_tasks_md_lists_republication_dry_run_current_focus():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-republication-policy-dry-run" in content


def test_tasks_md_republication_does_not_contain_real_data_hints():
    content = TASKS_PATH.read_text(encoding="utf-8")
    for forbidden in REAL_DATA_HINTS + ("260624", "260504", "CAB-csl"):
        assert forbidden not in content


# ----------------------------------------------------------------
# feature/evidence-index-stage2-candidate-selection
# ----------------------------------------------------------------

STAGE2_SELECTION_HEADING = "## 4.8 Stage 2 first candidate selection"

STAGE2_REAL_DATA_HINTS = (
    "230315",
    "3rdelection",
    "3RDELECTION",
    "03_christmas_2019",
    "CHRISTMAS_2019",
    "06_swimsuit_b_2020",
    "SWIMSUIT_B_2020",
    "10_entry_nozomi",
    "ENTRY_NOZOMI",
    "31_comingofageceremony_2021",
    "COMINGOFAGECEREMONY",
    "csl_script_event",
    "CAB-csl",
    # feature/evidence-index-stage2-candidate-reselection で追加した実データ断片
    "210526",
    "babydoll",
    "BABYDOLL",
    "210707",
    "wetuniform",
    "WETUNIFORM",
    "210721",
    "210804",
    "swimsuit",
    "SWIMSUIT",
    "220302",
    "election_export",
)

# feature/evidence-index-stage2-batch-promotion で新設した§4.10は、Registry
# 確定・実昇格済みのセクションであり、他の一般セクション（§4.6等）と同じく
# filter_unregistered_hints経由でRegistry登録済みの日付断片を許可してよい。
# そのため§4.8/§4.9の「無条件禁止」範囲の終端を§4.10の開始位置に絞り、
# §4.10自体はこの範囲に含めない。
STAGE2_BATCH_PROMOTION_HEADING = (
    "## 4.10 `evidence-index-stage2-batch-promotion`実施結果"
)


def _stage2_selection_section() -> str:
    content = _read_doc()
    return content.split(STAGE2_SELECTION_HEADING, 1)[1].split(
        STAGE2_BATCH_PROMOTION_HEADING, 1
    )[0]


def test_batch_policy_doc_has_stage2_selection_section():
    content = _read_doc()
    assert STAGE2_SELECTION_HEADING in content


def test_batch_policy_doc_states_stage2_screening_summary():
    section = _stage2_selection_section()
    assert "167" in section
    assert "166" in section
    assert "needs_update" in section
    assert "blocked" in section


def test_batch_policy_doc_states_stage2_selection_matrix():
    section = _stage2_selection_section()
    assert "Story A" in section
    assert "Story E" in section
    assert "promotion-candidate" in section
    assert "9.09%" in section


def test_batch_policy_doc_states_stage2_conclusion():
    section = _stage2_selection_section()
    assert "Failed story count: 0" in section
    assert "excluded story count: 0" in section


def test_batch_policy_doc_stage2_states_non_goals():
    section = _stage2_selection_section()
    assert "Public ID Registry" in section
    assert "publicStoryId" in section
    assert "commit" in section.lower()


def test_batch_policy_doc_stage2_does_not_contain_real_data_hints():
    section = _stage2_selection_section()
    for forbidden in REAL_DATA_HINTS + STAGE2_REAL_DATA_HINTS:
        assert forbidden not in section


def test_tasks_md_lists_stage2_candidate_selection_current_focus():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-stage2-candidate-selection" in content


def test_tasks_md_stage2_does_not_contain_real_data_hints():
    # TASKS.mdはPR横断の単一ファイルであり、feature/evidence-index-stage2-
    # batch-promotion以降のエントリはRegistry確定・実昇格済みのpublicStoryId
    # 日付断片を含みうるため、filter_unregistered_hints経由でRegistry登録済み
    # の日付断片のみ許可する(英字混じりのイベント名断片は引き続き禁止)。
    content = TASKS_PATH.read_text(encoding="utf-8")
    for forbidden in filter_unregistered_hints(
        REAL_DATA_HINTS + STAGE2_REAL_DATA_HINTS
    ):
        assert forbidden not in content


# ----------------------------------------------------------------
# feature/evidence-index-stage2-candidate-reselection
# ----------------------------------------------------------------

STAGE2_RESELECTION_HEADING = "## 4.9 Stage 2 candidate reselection"


def _stage2_reselection_section() -> str:
    content = _read_doc()
    return content.split(STAGE2_RESELECTION_HEADING, 1)[1].split(
        STAGE2_BATCH_PROMOTION_HEADING, 1
    )[0]


def test_batch_policy_doc_has_stage2_reselection_section():
    content = _read_doc()
    assert STAGE2_RESELECTION_HEADING in content


def test_batch_policy_doc_states_stage2_reselection_screening_summary():
    section = _stage2_reselection_section()
    assert "167" in section
    assert "129" in section
    assert "128" in section
    assert "127" in section
    assert "needs_update" in section
    assert "blocked" in section


def test_batch_policy_doc_states_stage2_reselection_matrix():
    section = _stage2_reselection_section()
    assert "Story A" in section
    assert "Story E" in section
    assert "promotion-candidate" in section
    assert "9.09%" in section


def test_batch_policy_doc_states_stage2_reselection_supersedes_old_candidates():
    section = _stage2_reselection_section()
    assert "差し替え" in section
    assert "excluded" in section
    assert "§4.8" in section


def test_batch_policy_doc_states_stage2_reselection_proposed_id_not_recorded():
    section = _stage2_reselection_section()
    assert "Registry未登録" in section
    assert "candidate_summary_for_user.md" in section


def test_batch_policy_doc_states_stage2_reselection_conclusion():
    section = _stage2_reselection_section()
    assert "Failed story count: 0" in section
    assert "excluded story count: 0" in section


def test_batch_policy_doc_stage2_reselection_states_non_goals():
    section = _stage2_reselection_section()
    assert "Public ID Registry" in section
    assert "publicStoryId" in section
    assert "commit" in section.lower()


def test_batch_policy_doc_stage2_reselection_does_not_contain_real_data_hints():
    section = _stage2_reselection_section()
    for forbidden in REAL_DATA_HINTS + STAGE2_REAL_DATA_HINTS:
        assert forbidden not in section


def test_batch_policy_doc_states_stage2_reselection_non_goals_section_in_scope_list():
    content = _read_doc()
    section = content.split("# 14. Non-goals", 1)[1].split("# 15. 関連ドキュメント", 1)[
        0
    ]
    assert "evidence-index-stage2-candidate-reselection" in section


def test_tasks_md_lists_stage2_candidate_reselection_current_focus():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-stage2-candidate-reselection" in content


def test_tasks_md_stage2_reselection_does_not_contain_real_data_hints():
    # test_tasks_md_stage2_does_not_contain_real_data_hintsと同じ理由で
    # Registry連動許可リストを適用する。
    content = TASKS_PATH.read_text(encoding="utf-8")
    for forbidden in filter_unregistered_hints(
        REAL_DATA_HINTS + STAGE2_REAL_DATA_HINTS
    ):
        assert forbidden not in content


# ----------------------------------------------------------------
# feature/public-id-naming-v2-design
# ----------------------------------------------------------------

MIGRATION_PROCEDURE_HEADING = "# 16. publicStoryId命名規約v2への移行実行手順"


def _migration_procedure_section() -> str:
    content = _read_doc()
    return content.split(MIGRATION_PROCEDURE_HEADING, 1)[1]


def test_batch_policy_doc_has_migration_procedure_section():
    content = _read_doc()
    assert MIGRATION_PROCEDURE_HEADING in content


def test_batch_policy_doc_states_naming_v2_non_goals():
    content = _read_doc()
    section = content.split("# 14. Non-goals", 1)[1].split("# 15. 関連ドキュメント", 1)[
        0
    ]
    assert "feature/public-id-naming-v2-design" in section
    assert "knowledge/public_ids/story_public_ids.yaml" in section


def test_batch_policy_doc_states_migration_not_executed_in_this_pr():
    section = _migration_procedure_section()
    assert "本PRでは一切実施しない" in section


def test_batch_policy_doc_states_migration_procedure_steps():
    section = _migration_procedure_section()
    steps_section = section.split("## 16.2 移行実行手順（次PRで実施）", 1)[1].split(
        "## 16.3", 1
    )[0]
    assert "Registry書き換え" in steps_section
    assert "knowledge/evidence/stories/" in steps_section
    assert "knowledge/summaries/stories/" in steps_section
    assert "改名" in steps_section
    assert "evidenceRefs" in steps_section


def test_batch_policy_doc_states_migration_verification_suite():
    section = _migration_procedure_section()
    steps_section = section.split("## 16.2 移行実行手順（次PRで実施）", 1)[1].split(
        "## 16.3", 1
    )[0]
    assert "検証suite" in steps_section
    assert "render_wiki.py" in steps_section
    assert "mkdocs build --strict" in steps_section
    assert "exposure check" in steps_section
    assert "新旧mapping逆引き検証" in steps_section


def test_batch_policy_doc_states_migration_merge_gate():
    section = _migration_procedure_section()
    steps_section = section.split("## 16.2 移行実行手順（次PRで実施）", 1)[1].split(
        "## 16.3", 1
    )[0]
    assert "ユーザーが事前承認済み" in steps_section
    assert "Fableが確認してからマージする" in steps_section


def test_batch_policy_doc_states_migration_does_not_touch_past_docs_records():
    section = _migration_procedure_section()
    assert (
        "本PR（`feature/public-id-naming-v2-design`）では、これらの既存docs記載箇所はいずれも変更しない"
        in section
    )


def test_batch_policy_doc_states_migration_non_goals():
    section = _migration_procedure_section()
    non_goals_section = section.split("## 16.4 本PRでは実装しないこと", 1)[1]
    assert "knowledge/public_ids/story_public_ids.yaml" in non_goals_section
    assert "knowledge/evidence/stories/" in non_goals_section
    assert "knowledge/summaries/stories/" in non_goals_section
