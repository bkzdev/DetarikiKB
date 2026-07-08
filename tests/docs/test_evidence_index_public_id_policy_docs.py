"""
tests/docs/test_evidence_index_public_id_policy_docs.py
Evidence Index Public ID Policy
(docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md) の
軽量な整合性テスト。

PR #91のfirst promotion attemptで発見されたsourceKey由来ID問題の記録、
ID分類（内部trace ID/公開ID/表示用label）、案A/B/C/D比較、案C採用方針、
publicEvidenceId方針、internalTrace方針、Summary evidenceRefs/Renderer/
schema/promotion copyへの影響、既存docsからのリンク、TASKS.mdの次PR候補
を確認する。実storyId・実sourceKeyがdocsに含まれていないことも確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
PUBLIC_ID_POLICY_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "06_AI"
    / "Evidence_Index_Public_ID_Policy.md"
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
STORY_SUMMARY_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Story_Summary_Design.md"
)
TASKS_PATH = PROJECT_ROOT / "TASKS.md"

REQUIRED_SECTIONS = (
    "# 1. Background",
    "# 2. Problem discovered in first promotion attempt",
    "# 3. ID categories",
    "# 4. Options",
    "# 5. Adopted direction",
    "# 6. publicEvidenceId policy",
    "# 7. internalTrace policy",
    "# 8. Summary evidenceRefsへの影響",
    "# 9. Renderer / pathへの影響",
    "# 10. Schemaへの影響",
    "# 11. Promotion copyへの影響",
    "# 12. Implementation phases",
    "# 13. Non-goals",
    "# 14. Open questions",
    "# 15. 参照",
)

REAL_DATA_HINTS = ("CAMI3RD", "260425", "260707", "C:\\Users", "D:\\Dev")


def _read_doc() -> str:
    return PUBLIC_ID_POLICY_PATH.read_text(encoding="utf-8")


def test_public_id_policy_doc_exists():
    assert PUBLIC_ID_POLICY_PATH.is_file()


def test_public_id_policy_doc_has_required_sections():
    content = _read_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"不足しているセクション: {missing}"


def test_public_id_policy_doc_states_problem_discovered():
    content = _read_doc()
    section = content.split("# 2. Problem discovered in first promotion attempt", 1)[
        1
    ].split("# 3. ID categories", 1)[0]
    assert "187" in section
    assert "ファイル名" in section
    assert "publicStoryId" in section
    assert "Git履歴" in section


def test_public_id_policy_doc_classifies_id_categories():
    content = _read_doc()
    section = content.split("# 3. ID categories", 1)[1].split("# 4. Options", 1)[0]
    assert "内部trace ID" in section
    assert "公開ID" in section
    assert "表示用label" in section
    for field in ("storyId", "episodeId", "sceneId", "blockId", "evidenceId"):
        assert field in section
    for field in ("publicStoryId", "publicEpisodeId", "publicEvidenceId"):
        assert field in section


def test_public_id_policy_doc_compares_options():
    content = _read_doc()
    section = content.split("# 4. Options", 1)[1].split("# 5. Adopted direction", 1)[0]
    for heading in ("案A", "案B", "案C", "案D"):
        assert heading in section


def test_public_id_policy_doc_adopts_option_c():
    content = _read_doc()
    section = content.split("# 5. Adopted direction", 1)[1].split(
        "# 6. publicEvidenceId policy", 1
    )[0]
    assert "案Cを長期方針として採用する" in section
    assert "案Aは採用しない" in section


def test_public_id_policy_doc_states_public_evidence_id_policy():
    content = _read_doc()
    section = content.split("# 6. publicEvidenceId policy", 1)[1].split(
        "# 7. internalTrace policy", 1
    )[0]
    assert "publicEvidenceId" in section
    assert "publicEpisodeId" in section


def test_public_id_policy_doc_states_internal_trace_policy():
    content = _read_doc()
    section = content.split("# 7. internalTrace policy", 1)[1].split(
        "# 8. Summary evidenceRefsへの影響", 1
    )[0]
    assert "internalTraceRef" in section or "mapping" in section


def test_public_id_policy_doc_states_summary_impact():
    content = _read_doc()
    section = content.split("# 8. Summary evidenceRefsへの影響", 1)[1].split(
        "# 9. Renderer / pathへの影響", 1
    )[0]
    assert "evidenceRefs" in section
    assert "publicEvidenceId" in section


def test_public_id_policy_doc_states_renderer_impact():
    content = _read_doc()
    section = content.split("# 9. Renderer / pathへの影響", 1)[1].split(
        "# 10. Schemaへの影響", 1
    )[0]
    assert "render_evidence_page" in section or "evidence_page_path" in section
    assert "anchor" in section


def test_public_id_policy_doc_states_schema_impact():
    content = _read_doc()
    section = content.split("# 10. Schemaへの影響", 1)[1].split(
        "# 11. Promotion copyへの影響", 1
    )[0]
    assert "evidence_index.schema.json" in section
    assert "急に既存schemaを破壊しない" in section


def test_public_id_policy_doc_states_promotion_copy_impact():
    content = _read_doc()
    section = content.split("# 11. Promotion copyへの影響", 1)[1].split(
        "# 12. Implementation phases", 1
    )[0]
    assert "promote_evidence_index.py" in section


def test_public_id_policy_doc_states_non_goals():
    content = _read_doc()
    section = content.split("# 13. Non-goals", 1)[1].split("# 14. Open questions", 1)[0]
    for forbidden in (
        "実Evidence Indexのcommit",
        "knowledge/evidence/stories/",
        "ID rewrite実装",
    ):
        assert forbidden in section


def test_public_id_policy_doc_does_not_contain_real_data_hints():
    content = _read_doc()
    for forbidden in REAL_DATA_HINTS:
        assert forbidden not in content


def test_promotion_policy_links_to_public_id_policy():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Public_ID_Policy.md" in content


def test_evidence_index_design_links_to_public_id_policy():
    content = EVIDENCE_INDEX_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Public_ID_Policy.md" in content


def test_promotion_copy_runbook_links_to_public_id_policy():
    content = PROMOTION_COPY_RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Public_ID_Policy.md" in content


def test_story_summary_design_links_to_public_id_policy():
    content = STORY_SUMMARY_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Public_ID_Policy.md" in content


def test_tasks_md_lists_next_pr_candidates():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-public-id-schema-design" in content
    assert "evidence-index-public-id-projection" in content
    assert "evidence-index-promotion-first-reviewed-sample-retry" in content


def test_tasks_md_does_not_contain_real_data_hints():
    content = TASKS_PATH.read_text(encoding="utf-8")
    for forbidden in REAL_DATA_HINTS:
        assert forbidden not in content


# ----------------------------------------------------------------
# feature/evidence-index-public-id-schema-design
# ----------------------------------------------------------------


def test_public_id_policy_doc_states_public_evidence_id_format():
    content = _read_doc()
    section = content.split("## 6.4 publicEvidenceId形式（決定）", 1)[1].split(
        "## 6.5 evidenceType prefix mapping", 1
    )[0]
    assert "{publicEpisodeId}_{PREFIX}{sequence:04d}" in section
    assert "候補B" in section


def test_public_id_policy_doc_has_prefix_mapping_table():
    content = _read_doc()
    section = content.split("## 6.5 evidenceType prefix mapping", 1)[1].split(
        "## 6.6 採番方針", 1
    )[0]
    expected_prefixes = {
        "dialogue": "DLG",
        "monologue": "MONO",
        "narration": "NAR",
        "choice": "CHO",
        "unknown": "UNK",
        "stage_direction": "STG",
    }
    for evidence_type, prefix in expected_prefixes.items():
        assert evidence_type in section
        assert prefix in section


def test_public_id_policy_doc_states_numbering_policy():
    content = _read_doc()
    section = content.split("## 6.6 採番方針（決定）", 1)[1].split("---", 1)[0]
    assert "evidenceType別に連番" in section
    assert "stage_direction" in section


def test_public_id_policy_doc_states_schema_implementation_status():
    content = _read_doc()
    assert (
        "## 10.3 実装状況（`feature/evidence-index-public-id-schema-design`で実施）"
        in content
    )
    section = content.split(
        "## 10.3 実装状況（`feature/evidence-index-public-id-schema-design`で実施）",
        1,
    )[1].split("## 10.4", 1)[0]
    assert "publicEvidenceId" in section
    assert "optional" in section
    assert "evidenceId" in section


def test_public_id_policy_doc_states_required_timing():
    content = _read_doc()
    assert "## 10.4 publicStoryId / publicEpisodeId required化タイミング" in content
    section = content.split(
        "## 10.4 publicStoryId / publicEpisodeId required化タイミング", 1
    )[1].split("---", 1)[0]
    assert "本PRでは`publicStoryId`/`publicEpisodeId`のrequired化は行わない" in section


def test_public_id_policy_doc_schema_change_is_documented_in_non_goals_history():
    content = _read_doc()
    section = content.split("# 13. Non-goals", 1)[1].split("# 14. Open questions", 1)[0]
    assert "feature/evidence-index-public-id-schema-design`で最小実装済み" in section


def test_schema_file_states_public_evidence_id_field():
    schema_path = PROJECT_ROOT / "schemas" / "evidence_index.schema.json"
    content = schema_path.read_text(encoding="utf-8")
    assert "publicEvidenceId" in content


# ----------------------------------------------------------------
# feature/evidence-index-public-id-projection
# ----------------------------------------------------------------

PROJECTION_STATUS_HEADING = (
    "## 6.7 projection実装状況（`feature/evidence-index-public-id-projection`で実施）"
)


def _projection_status_section() -> str:
    content = _read_doc()
    return content.split(PROJECTION_STATUS_HEADING, 1)[1].split(
        "# 7. internalTrace policy", 1
    )[0]


def test_public_id_policy_doc_states_projection_implementation_status():
    content = _read_doc()
    assert PROJECTION_STATUS_HEADING in content
    section = _projection_status_section()
    assert "Compatible projection" in section
    assert "project_evidence_index_public_ids.py" in section
    assert "案A" in section


def test_public_id_policy_doc_states_compatible_projection_not_promotion_ready():
    section = _projection_status_section()
    assert "not promotion-ready" in section


def test_public_id_policy_doc_states_mapping_output_commit_prohibition():
    section = _projection_status_section()
    assert "mapping" in section.lower()
    assert "commit禁止" in section or "commit対象外" in section


def test_public_id_policy_doc_records_projection_as_completed_in_phases():
    content = _read_doc()
    section = content.split("# 12. Implementation phases", 1)[1].split(
        "# 13. Non-goals", 1
    )[0]
    assert "evidence-index-public-id-projection" in section
    assert "evidence-index-public-id-public-safe-projection" in section


def test_public_id_policy_doc_projection_non_goals_mentions_public_safe_projection():
    content = _read_doc()
    section = content.split("# 13. Non-goals", 1)[1].split("# 14. Open questions", 1)[0]
    assert "Public-safe projection" in section


def test_evidence_index_design_states_projection_implementation():
    content = EVIDENCE_INDEX_DESIGN_PATH.read_text(encoding="utf-8")
    assert "project_evidence_index_public_ids.py" in content
    assert "Compatible projection" in content


def test_promotion_policy_states_projection_implementation():
    content = PROMOTION_POLICY_PATH.read_text(encoding="utf-8")
    assert "project_evidence_index_public_ids.py" in content


def test_tasks_md_lists_public_safe_projection_next_candidate():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-public-id-public-safe-projection" in content
    assert "evidence-index-public-id-renderer-switch" in content
    assert "evidence-index-promotion-first-reviewed-sample-retry" in content
    assert "internal-review-evidence-packet-design" in content
    assert "story-summary-generation-planning" in content
