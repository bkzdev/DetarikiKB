"""
tests/docs/test_summary_public_id_projection_design_docs.py
Summary Public ID Projection Design
(docs/architecture/06_AI/Summary_Public_ID_Projection_Design.md) の軽量な
整合性テスト。

Story_Summary_Generation_Plan.md §4.3の提案を実装レベルまで詳細化した設計
（projection scriptのCLI仕様・exit code・blocking条件・field変換表・
evidenceRefs変換仕様・Registry共有設計・schema変更不要の結論・実装フェーズ
対応・Non-goals・Open questions）と、既存docs（Story_Summary_Generation_Plan.md・
Story_Summary_Design.md・Evidence_Index_Public_ID_Policy.md）・TASKS.mdからの
リンク/参照を確認する。実storyId・実sourceKey・実タイトルがdocsに含まれて
いないことも確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
PROJECTION_DESIGN_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "06_AI"
    / "Summary_Public_ID_Projection_Design.md"
)
GENERATION_PLAN_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "06_AI"
    / "Story_Summary_Generation_Plan.md"
)
STORY_SUMMARY_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Story_Summary_Design.md"
)
PUBLIC_ID_POLICY_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "06_AI"
    / "Evidence_Index_Public_ID_Policy.md"
)
TASKS_PATH = PROJECT_ROOT / "TASKS.md"
STORY_SUMMARY_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "story_summary.schema.json"

REQUIRED_SECTIONS = (
    "# 1. Background",
    "# 2. Scope",
    "# 3. ID categories",
    "# 4. Projection script design",
    "# 5. Field rewrite table",
    "# 6. evidenceRefs conversion",
    "# 7. Registry sharing design",
    "# 8. Schema変更要否の結論",
    "# 9. sourceKey由来ID exposure scan仕様",
    "# 10. Implementation phases",
    "# 11. Non-goals",
    "# 12. Open questions",
    "# 13. 参照",
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
    return PROJECTION_DESIGN_PATH.read_text(encoding="utf-8")


def test_projection_design_doc_exists():
    assert PROJECTION_DESIGN_PATH.is_file()


def test_projection_design_doc_has_required_sections():
    content = _read_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"必須セクションが不足しています: {missing}"


def test_projection_design_doc_does_not_contain_real_data_hints():
    content = _read_doc()
    for forbidden in REAL_DATA_HINTS:
        assert forbidden not in content


def test_projection_design_doc_states_background():
    content = _read_doc()
    section = content.split("# 1. Background", 1)[1].split("# 2. Scope", 1)[0]
    assert "docs-only PR" in section
    assert "Evidence_Index_Public_ID_Policy.md" in section
    assert "Story_Summary_Generation_Plan.md" in section


def test_projection_design_doc_states_scope():
    content = _read_doc()
    section = content.split("# 2. Scope", 1)[1].split("# 3. ID categories", 1)[0]
    assert "project_story_summary_public_ids.py" in section
    assert "Non-goals" in section


def test_projection_design_doc_classifies_id_categories():
    content = _read_doc()
    section = content.split("# 3. ID categories", 1)[1].split(
        "# 4. Projection script design", 1
    )[0]
    for field in ("storyId", "episodeId", "evidenceRefs", "inputRefs"):
        assert field in section
    for field in ("publicStoryId", "publicEpisodeId", "publicEvidenceId"):
        assert field in section


def test_projection_design_doc_states_script_cli():
    content = _read_doc()
    section = content.split("# 4. Projection script design", 1)[1].split(
        "# 5. Field rewrite table", 1
    )[0]
    for arg in (
        "--input",
        "--output",
        "--mapping-output",
        "--report",
        "--registry",
        "--evidence-mapping",
        "--projection-mode",
    ):
        assert arg in section
    assert "compatible" in section
    assert "public-safe" in section
    assert "knowledge/summaries/" in section
    assert "knowledge/public_ids/" in section


def test_projection_design_doc_states_exit_codes():
    content = _read_doc()
    section = content.split("## 4.2 Exit codes", 1)[1].split("## 4.3 Blocking条件", 1)[
        0
    ]
    assert "`0`" in section
    assert "`1`" in section
    assert "`2`" in section


def test_projection_design_doc_states_blocking_conditions():
    content = _read_doc()
    section = content.split("## 4.3 Blocking条件", 1)[1].split("## 4.4 安全策", 1)[0]
    assert "1 file = 1 publicStoryId" in section
    assert "sourceKey由来ID exposure scan" in section
    assert "含めない条件" in section
    assert "validate_story_summaries.py --require-reviewed" in section


def test_projection_design_doc_states_field_rewrite_table():
    content = _read_doc()
    section = content.split("# 5. Field rewrite table", 1)[1].split(
        "# 6. evidenceRefs conversion", 1
    )[0]
    for field in (
        "storyId",
        "publicStoryId",
        "episodeId",
        "publicEpisodeId",
        "evidenceRefs",
        "inputRefs",
    ):
        assert field in section
    assert "{storyId}.yaml" in section
    assert "{publicStoryId}.yaml" in section


def test_projection_design_doc_states_evidence_refs_conversion():
    content = _read_doc()
    section = content.split("# 6. evidenceRefs conversion", 1)[1].split(
        "# 7. Registry sharing design", 1
    )[0]
    assert "--evidence-mapping" in section
    assert "publicEvidenceId" in section
    assert "空配列" in section
    assert "Story_Summary_Generation_Plan.md" in section


def test_projection_design_doc_states_registry_sharing():
    content = _read_doc()
    section = content.split("# 7. Registry sharing design", 1)[1].split(
        "# 8. Schema変更要否の結論", 1
    )[0]
    assert "_resolve_registry_lookup" in section
    assert "_group_entries_by_internal_story" in section
    assert "check_public_episode_ids" in section
    assert "adapter" in section.lower()


def test_projection_design_doc_states_schema_change_conclusion():
    content = _read_doc()
    section = content.split("# 8. Schema変更要否の結論", 1)[1].split(
        "# 9. sourceKey由来ID exposure scan仕様", 1
    )[0]
    assert "変更は一切不要である" in section
    assert "スキップ可能" in section


def test_projection_design_doc_states_exposure_scan_spec():
    content = _read_doc()
    section = content.split("# 9. sourceKey由来ID exposure scan仕様", 1)[1].split(
        "# 10. Implementation phases", 1
    )[0]
    assert "4文字未満" in section
    assert "blocking error" in section
    assert "ヒューリスティック" in section


def test_projection_design_doc_states_implementation_phase_mapping():
    content = _read_doc()
    section = content.split("# 10. Implementation phases", 1)[1].split(
        "# 11. Non-goals", 1
    )[0]
    assert "summary-public-id-schema-implementation" in section
    assert "スキップ可能" in section
    assert "summary-generation-public-safe-projection" in section


def test_projection_design_doc_states_non_goals():
    content = _read_doc()
    section = content.split("# 11. Non-goals", 1)[1].split("# 12. Open questions", 1)[0]
    for forbidden in (
        "project_story_summary_public_ids.py`本体の実装",
        "実データprojection実行",
        "agents/`・`scripts/`・`schemas/`配下の一切の変更",
    ):
        assert forbidden in section


def test_projection_design_doc_states_open_questions():
    content = _read_doc()
    section = content.split("# 12. Open questions", 1)[1].split("# 13. 参照", 1)[0]
    assert "review.status" in section
    assert "reviewer" in section


def test_generation_plan_marks_projection_design_completed():
    content = GENERATION_PLAN_PATH.read_text(encoding="utf-8")
    section = content.split("# 9. Implementation phases", 1)[1].split(
        "# 10. Non-goals", 1
    )[0]
    assert "summary-public-id-projection-design" in section
    assert "**完了**" in section
    assert "スキップ可能" in section


def test_generation_plan_open_questions_mark_script_split_resolved():
    content = GENERATION_PLAN_PATH.read_text(encoding="utf-8")
    section = content.split("# 11. Open questions", 1)[1].split("# 12. 参照", 1)[0]
    assert "summary-public-id-projection-design`で確定" in section


def test_generation_plan_links_to_projection_design():
    content = GENERATION_PLAN_PATH.read_text(encoding="utf-8")
    assert "Summary_Public_ID_Projection_Design.md" in content


def test_story_summary_design_links_to_projection_design():
    content = STORY_SUMMARY_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Summary_Public_ID_Projection_Design.md" in content


def test_public_id_policy_links_to_projection_design():
    content = PUBLIC_ID_POLICY_PATH.read_text(encoding="utf-8")
    assert "Summary_Public_ID_Projection_Design.md" in content


def test_tasks_md_records_projection_design_pr():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "feature/summary-public-id-projection-design" in content
    assert "summary-generation-public-safe-projection" in content


def test_tasks_md_notes_schema_implementation_skip():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "summary-public-id-schema-implementation" in content
    assert "スキップ" in content


def test_tasks_md_does_not_contain_real_data_hints():
    content = TASKS_PATH.read_text(encoding="utf-8")
    for forbidden in REAL_DATA_HINTS:
        assert forbidden not in content


def test_projection_design_doc_references_existing_schema_file():
    """本文書が言及する既存schemaファイルが実在し、§8の結論どおり
    storyId/publicStoryId双方のpatternが一致していることを確認する
    (docの記述と実装のずれを検知するための軽い整合性チェック)。"""
    assert STORY_SUMMARY_SCHEMA_PATH.is_file()
    schema_content = STORY_SUMMARY_SCHEMA_PATH.read_text(encoding="utf-8")
    assert '"storyId"' in schema_content
    assert '"publicStoryId"' in schema_content
    assert '"^[A-Z][A-Z0-9_]*$"' in schema_content


def test_projection_design_doc_references_existing_scripts():
    """本文書が踏襲元として言及する既存scriptが実在することを確認する。"""
    evidence_projection_script = (
        PROJECT_ROOT / "scripts" / "project_evidence_index_public_ids.py"
    )
    check_public_episode_ids_script = (
        PROJECT_ROOT / "scripts" / "check_public_episode_ids.py"
    )
    assert evidence_projection_script.is_file()
    assert check_public_episode_ids_script.is_file()
    content = check_public_episode_ids_script.read_text(encoding="utf-8")
    assert "_resolve_registry_lookup" in content
    assert "_group_entries_by_internal_story" in content
