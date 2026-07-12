"""
tests/docs/test_story_summary_generation_plan_docs.py
Story Summary Generation Plan
(docs/architecture/06_AI/Story_Summary_Generation_Plan.md) の軽量な整合性
テスト。

Summary fileの公開ID問題へのEvidence Index方式踏襲方針、パイプライン段階
設計、prompt設計方針、provider抽象配置、品質ゲート、実装フェーズ分割、
Non-goals、既存docs（Story_Summary_Design.md）・TASKS.mdからのリンクを
確認する。実storyId・実sourceKey・実タイトルがdocsに含まれていないことも
確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
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
AI_CONTEXT_PATH = PROJECT_ROOT / "AI_CONTEXT.md"
TASKS_PATH = PROJECT_ROOT / "TASKS.md"
STORY_SUMMARY_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "story_summary.schema.json"

REQUIRED_SECTIONS = (
    "# 1. Background",
    "# 2. Scope",
    "# 3. Fixed premises",
    "# 4. Summary fileの公開ID問題",
    "# 5. Pipeline stage design",
    "# 6. Prompt design policy level",
    "# 7. Provider抽象の配置",
    "# 8. Quality gate",
    "# 9. Implementation phases",
    "# 10. Non-goals",
    "# 11. Open questions",
    "# 12. 参照",
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
    return GENERATION_PLAN_PATH.read_text(encoding="utf-8")


def test_generation_plan_doc_exists():
    assert GENERATION_PLAN_PATH.is_file()


def test_generation_plan_doc_has_required_sections():
    content = _read_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"必須セクションが不足しています: {missing}"


def test_generation_plan_doc_does_not_contain_real_data_hints():
    content = _read_doc()
    for forbidden in REAL_DATA_HINTS:
        assert forbidden not in content


def test_generation_plan_doc_states_fixed_premises():
    content = _read_doc()
    section = content.split("# 3. Fixed premises", 1)[1].split(
        "# 4. Summary fileの公開ID問題", 1
    )[0]
    assert "Ollama" in section
    assert "opt-in" in section
    assert "Episode Summary" in section
    assert "Story Summary" in section
    assert "workspace/summary_drafts/" in section
    assert "publicEvidenceId" in section


def test_generation_plan_doc_identifies_public_id_problem_isomorphism():
    """Summary fileの現行設計がEvidence Indexと同型の問題を持つことの
    明記を確認する（本PRの最重要論点）。"""
    content = _read_doc()
    section = content.split("# 4. Summary fileの公開ID問題", 1)[1].split(
        "# 5. Pipeline stage design", 1
    )[0]
    assert "storyId" in section
    assert "publicStoryId" in section
    assert "完全に同型" in section or "同型" in section
    assert "Evidence_Index_Public_ID_Policy.md" in section


def test_generation_plan_doc_adopts_evidence_index_solution():
    content = _read_doc()
    section = content.split("# 4. Summary fileの公開ID問題", 1)[1].split(
        "# 5. Pipeline stage design", 1
    )[0]
    assert "案C" in section
    assert "Public-safe projection" in section
    assert "knowledge/public_ids/story_public_ids.yaml" in section
    assert "{publicStoryId}.yaml" in section


def test_generation_plan_doc_states_schema_change_proposal_only():
    """schema変更は提案の整理のみで、実施しない方針を確認する。"""
    content = _read_doc()
    section = content.split("## 4.3.5 必要なschema変更の整理", 1)[1].split("## 4.4", 1)[
        0
    ]
    assert "本PRでは上記のいずれのschema変更も実施しない" in section


def test_generation_plan_doc_states_pipeline_stages():
    content = _read_doc()
    section = content.split("# 5. Pipeline stage design", 1)[1].split(
        "# 6. Prompt design policy level", 1
    )[0]
    assert "PoC" in section
    assert "small batch" in section
    assert "通常運用" in section


def test_generation_plan_doc_states_prompt_policy_without_actual_prompt():
    content = _read_doc()
    section = content.split("# 6. Prompt design policy level", 1)[1].split(
        "# 7. Provider抽象の配置", 1
    )[0]
    assert "本PRでは実際のprompt文面は一切書かない" in section
    assert "blockId" in section
    assert "hallucination" in section


def test_generation_plan_doc_states_provider_placement():
    content = _read_doc()
    section = content.split("# 7. Provider抽象の配置", 1)[1].split(
        "# 8. Quality gate", 1
    )[0]
    assert "agents/summarizer/" in section
    assert "現時点で存在しない" in section
    assert "agents/extractor/" in section


def test_generation_plan_doc_states_quality_gate_split():
    content = _read_doc()
    section = content.split("# 8. Quality gate", 1)[1].split(
        "# 9. Implementation phases", 1
    )[0]
    assert "機械的検証" in section
    assert "人間レビュー" in section
    assert "evidenceRefs実在性" in section


def test_generation_plan_doc_states_implementation_phases():
    content = _read_doc()
    section = content.split("# 9. Implementation phases", 1)[1].split(
        "# 10. Non-goals", 1
    )[0]
    for candidate in (
        "summary-generation-skeleton",
        "summary-public-id-projection-design",
        "summary-generation-public-safe-projection",
        "summary-generation-quality-gate",
        "summary-generation-poc",
    ):
        assert candidate in section


def test_generation_plan_doc_states_non_goals():
    content = _read_doc()
    section = content.split("# 10. Non-goals", 1)[1].split("# 11. Open questions", 1)[0]
    for forbidden in (
        "LLM呼び出し",
        "prompt・provider実装",
        "実要約生成",
        "summary fixtureのmigration",
    ):
        assert forbidden in section


def test_story_summary_design_links_to_generation_plan():
    content = STORY_SUMMARY_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Story_Summary_Generation_Plan.md" in content


def test_ai_context_links_to_generation_plan():
    content = AI_CONTEXT_PATH.read_text(encoding="utf-8")
    assert "Story_Summary_Generation_Plan.md" in content


def test_tasks_md_records_generation_planning_pr():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "feature/story-summary-generation-planning" in content
    assert "summary-generation-skeleton" in content
    assert "summary-public-id-projection-design" in content


def test_tasks_md_does_not_contain_real_data_hints():
    content = TASKS_PATH.read_text(encoding="utf-8")
    for forbidden in REAL_DATA_HINTS:
        assert forbidden not in content


def test_ai_context_does_not_contain_real_data_hints():
    content = AI_CONTEXT_PATH.read_text(encoding="utf-8")
    for forbidden in REAL_DATA_HINTS:
        assert forbidden not in content


def test_generation_plan_doc_references_existing_schema_file():
    """本文書が言及する既存schemaファイルが実在することを確認する
    (docの記述と実装のずれを検知するための軽い整合性チェック)。"""
    assert STORY_SUMMARY_SCHEMA_PATH.is_file()
    schema_content = STORY_SUMMARY_SCHEMA_PATH.read_text(encoding="utf-8")
    assert '"storyId"' in schema_content
    assert '"publicStoryId"' in schema_content
