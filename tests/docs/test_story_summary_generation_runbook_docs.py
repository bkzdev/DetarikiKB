"""
tests/docs/test_story_summary_generation_runbook_docs.py
Story Summary Generation Runbook
(docs/runbooks/Story_Summary_Generation_Runbook.md) の軽量な整合性テスト。

PoC（Stage 0）で確立し、summary-promotion-copy-scriptで完結したStory
Summary生成〜昇格の全8ステップ実行手順を整理したrunbookについて、必須
セクション・各ステップのCLI引数・人間レビューチェックリスト・commit可否
表・既知の制約・匿名化ルール・既存docs（Story_Summary_Generation_Plan.md・
Summary_Public_ID_Projection_Design.md・Story_Summary_Design.md）・
TASKS.mdからのリンク/記載を確認する。実storyId・実sourceKey・実タイトル・
実キャラクター名・要約本文がdocsに含まれていないことも確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Story_Summary_Generation_Runbook.md"
)
GENERATION_PLAN_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "06_AI"
    / "Story_Summary_Generation_Plan.md"
)
PROJECTION_DESIGN_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "06_AI"
    / "Summary_Public_ID_Projection_Design.md"
)
STORY_SUMMARY_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Story_Summary_Design.md"
)
TASKS_PATH = PROJECT_ROOT / "TASKS.md"

SCRIPT_PATHS = (
    PROJECT_ROOT / "scripts" / "normalize_story.py",
    PROJECT_ROOT / "scripts" / "generate_story_summaries.py",
    PROJECT_ROOT / "scripts" / "check_story_summary_drafts.py",
    PROJECT_ROOT / "scripts" / "project_story_summary_public_ids.py",
    PROJECT_ROOT / "scripts" / "promote_story_summaries.py",
    PROJECT_ROOT / "scripts" / "validate_story_summaries.py",
    PROJECT_ROOT / "scripts" / "check_evidence_index_promotion.py",
)

REQUIRED_SECTIONS = (
    "# 1. Purpose",
    "# 2. 前提",
    "# 3. Pipeline overview",
    "# 4. Step 1: 対象story選定",
    "# 5. Step 2: 再normalize",
    "# 6. Step 3: 生成",
    "# 7. Step 4: Quality gate",
    "# 8. Step 5: 人間レビュー",
    "# 9. Step 6: Public-safe projection",
    "# 10. Step 7: 昇格",
    "# 11. Step 8: commit前検証",
    "# 12. 生成物のcommit可否表",
    "# 13. Known limitations",
    "# 14. 匿名化ルール",
    "# 15. Non-goals",
    "# 16. 関連ドキュメント",
)

# 既存docs（Evidence_Index_Public_ID_Policy.md等）で禁止されている実データ
# 由来断片と同じリストを踏襲する。
REAL_DATA_HINTS = (
    "CAMI3RD",
    "260425",
    "260707",
    "260712",
    "C:\\Users",
    "D:\\Dev",
)


def _read_doc() -> str:
    return RUNBOOK_PATH.read_text(encoding="utf-8")


def test_runbook_exists():
    assert RUNBOOK_PATH.is_file()


def test_runbook_has_required_sections():
    content = _read_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"必須セクションが不足しています: {missing}"


def test_runbook_does_not_contain_real_data_hints():
    content = _read_doc()
    for forbidden in REAL_DATA_HINTS:
        assert forbidden not in content


def test_runbook_referenced_scripts_exist():
    for script_path in SCRIPT_PATHS:
        assert script_path.is_file(), f"参照scriptが存在しません: {script_path}"


def test_runbook_states_prerequisites():
    content = _read_doc()
    section = content.split("# 2. 前提", 1)[1].split("# 3. Pipeline overview", 1)[0]
    assert "Story_Summary_Generation_Plan.md" in section
    assert "Summary_Public_ID_Projection_Design.md" in section
    assert "Evidence_Index_Promotion_Copy.md" in section
    assert "Ollama" in section
    assert "AI_CONTEXT.md" in section


def test_runbook_states_pipeline_overview_with_eight_steps():
    content = _read_doc()
    section = content.split("# 3. Pipeline overview", 1)[1].split(
        "# 4. Step 1: 対象story選定", 1
    )[0]
    for step_keyword in (
        "対象story選定",
        "再normalize",
        "生成",
        "Quality gate",
        "人間レビュー",
        "Public-safe projection",
        "昇格",
        "commit前検証",
    ):
        assert step_keyword in section
    assert "workspace限定・非commit" in section


def test_runbook_step2_mentions_uv_run_requirement():
    content = _read_doc()
    section = content.split("# 5. Step 2: 再normalize", 1)[1].split(
        "# 6. Step 3: 生成", 1
    )[0]
    assert "--manifest" in section
    assert "--raw-root" in section
    assert "--manifest-strict" in section
    assert "uv run" in section
    assert "jsonschema" in section
    assert "unknownCommands: 0" in section
    assert "publicStoryId" in section


def test_runbook_step3_mentions_generation_cli_args():
    content = _read_doc()
    section = content.split("# 6. Step 3: 生成", 1)[1].split(
        "# 7. Step 4: Quality gate", 1
    )[0]
    for arg in ("--input", "--output", "--model", "--timeout", "--report", "--clean"):
        assert arg in section
    assert "workspace/summary_drafts/" in section
    assert "storyId単位" in section or "グルーピング" in section


def test_runbook_step4_mentions_quality_gate_cli_args():
    content = _read_doc()
    section = content.split("# 7. Step 4: Quality gate", 1)[1].split(
        "# 8. Step 5: 人間レビュー", 1
    )[0]
    assert "check_story_summary_drafts.py" in section
    assert "--normalized" in section
    assert "blocking issue" in section


def test_runbook_step5_has_review_checklist():
    content = _read_doc()
    section = content.split("# 8. Step 5: 人間レビュー", 1)[1].split(
        "# 9. Step 6: Public-safe projection", 1
    )[0]
    assert "主語の取り違え" in section
    assert "引用の妥当性" in section
    assert "原文にない状況説明の混入" in section
    assert "用語・略称の正式名称との対応" in section
    assert "review.notes" in section
    assert "review.status: approved" in section
    assert "generationStatus: generated" in section


def test_runbook_step6_mentions_projection_cli_args():
    content = _read_doc()
    section = content.split("# 9. Step 6: Public-safe projection", 1)[1].split(
        "# 10. Step 7: 昇格", 1
    )[0]
    for arg in (
        "--input",
        "--output",
        "--mapping-output",
        "--report",
        "--projection-mode",
        "--registry",
        "--evidence-mapping",
    ):
        assert arg in section
    assert "public-safe" in section
    assert "internal_id_exposure=0" in section
    assert "promotion-candidate" in section


def test_runbook_step7_requires_explicit_approval_for_execute():
    content = _read_doc()
    section = content.split("# 10. Step 7: 昇格", 1)[1].split(
        "# 11. Step 8: commit前検証", 1
    )[0]
    assert "--execute" in section
    assert "dry-run" in section
    assert "ユーザーの明示的な承認が必須" in section
    assert "AI_PR_Playbook.md" in section


def test_runbook_step8_mentions_standard_verification():
    content = _read_doc()
    section = content.split("# 11. Step 8: commit前検証", 1)[1].split(
        "# 12. 生成物のcommit可否表", 1
    )[0]
    assert "--require-reviewed" in section
    assert "check_evidence_index_promotion.py" in section
    assert "uv run pytest" in section
    assert "mkdocs build --strict" in section


def test_runbook_states_commit_matrix():
    content = _read_doc()
    section = content.split("# 12. 生成物のcommit可否表", 1)[1].split(
        "# 13. Known limitations", 1
    )[0]
    assert "非commit" in section
    assert "knowledge/summaries/stories/{publicStoryId}.yaml" in section
    assert "mapping CSV" in section


def test_runbook_states_known_limitations():
    content = _read_doc()
    section = content.split("# 13. Known limitations", 1)[1].split(
        "# 14. 匿名化ルール", 1
    )[0]
    assert "chunk分割" in section
    assert "主語の取り違え" in section
    assert "cp932" in section
    assert "UTF-8" in section


def test_runbook_states_anonymization_rules():
    content = _read_doc()
    section = content.split("# 14. 匿名化ルール", 1)[1].split("# 15. Non-goals", 1)[0]
    assert "{publicStoryId}" in section
    assert "REAL_DATA_HINTS" in section


def test_runbook_states_non_goals():
    content = _read_doc()
    section = content.split("# 15. Non-goals", 1)[1].split("# 16. 関連ドキュメント", 1)[
        0
    ]
    assert "agents/" in section
    assert "実データ生成・昇格の実行" in section
    assert "AI_PR_Playbook.md`自体の変更" in section


def test_generation_plan_links_to_runbook():
    content = GENERATION_PLAN_PATH.read_text(encoding="utf-8")
    assert "Story_Summary_Generation_Runbook.md" in content


def test_projection_design_links_to_runbook():
    content = PROJECTION_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Story_Summary_Generation_Runbook.md" in content


def test_story_summary_design_links_to_runbook():
    content = STORY_SUMMARY_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Story_Summary_Generation_Runbook.md" in content


def test_tasks_md_records_runbook_pr():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "feature/summary-generation-runbook" in content
    assert "summary-generation-small-batch" in content


def test_tasks_md_does_not_contain_real_data_hints():
    content = TASKS_PATH.read_text(encoding="utf-8")
    for forbidden in REAL_DATA_HINTS:
        assert forbidden not in content
