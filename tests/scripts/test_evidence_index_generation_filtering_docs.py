"""
tests/scripts/test_evidence_index_generation_filtering_docs.py
Evidence Index generation entry type filtering
(scripts/build_evidence_index_candidates.pyの--public-profile/
--include-types/--exclude-types) に関するdocsの軽量な整合性テスト。

runbook・promotion policy・design docにfiltering実装状況が明記されて
いること、default profileがstage_directionを除外する新しいdefault挙動
であること、TASKS.mdに次PR候補が記録されていることを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Evidence_Index_Generation_Dry_Run.md"
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


def test_runbook_mentions_include_exclude_and_profile_options():
    content = RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "--include-types" in content
    assert "--exclude-types" in content
    assert "--public-profile" in content
    for profile in ("default", "full", "review"):
        assert profile in content


def test_runbook_states_default_profile_excludes_stage_direction():
    content = RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "デフォルト`default`" in content or "デフォルトはdefault" in content
    assert "stage_direction`は除外" in content


def test_runbook_distinguishes_skip_and_filter():
    content = RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "skipとfilterは区別する" in content
    assert "filteredEntryCount" in content
    assert "filteredByTypeCounts" in content
    assert "filteredReasonCounts" in content


def test_runbook_states_candidate_references_only_for_output_entries():
    content = RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "filterで出力対象になったentryにのみ付与" in content


def test_promotion_policy_states_filter_implemented():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    assert "feature/evidence-index-generation-filtering" in content
    assert "--public-profile" in content
    assert "--include-types" in content
    assert "--exclude-types" in content


def test_promotion_policy_states_default_excludes_stage_direction():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    assert "デフォルトは`default`" in content
    assert "stage_direction`を除外" in content


def test_promotion_policy_states_real_data_rerun_counts():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    assert "187" in content
    assert "155" in content


def test_promotion_policy_marks_filter_non_goal_as_implemented():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    non_goals_section = content.split("# 14. Non-goals", 1)[1].split(
        "# 15. 未確定事項", 1
    )[0]
    assert "実装済み" in non_goals_section


def test_evidence_index_design_states_filtering_implementation_status():
    content = EVIDENCE_INDEX_DESIGN_PATH.read_text(encoding="utf-8")
    assert "実装状況（`feature/evidence-index-generation-filtering`で実施）" in content
    filtering_status = content.split(
        "実装状況（`feature/evidence-index-generation-filtering`で実施）", 1
    )[1]
    assert "--public-profile" in filtering_status
    assert "default挙動をPR #85時点の全type生成からPublic向け" in filtering_status


def test_tasks_md_lists_next_pr_candidates():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-promotion-policy-implementation" in content
    assert "internal-review-evidence-packet-design" in content
    assert "feature/evidence-index-generation-filtering" in content
