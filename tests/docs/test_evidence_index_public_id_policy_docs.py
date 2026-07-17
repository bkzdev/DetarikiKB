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

from _public_id_registry_hints import filter_unregistered_hints

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
    "# 16. publicStoryId命名規約v2",
)

REAL_DATA_HINTS = (
    "CAMI3RD",
    "260425",
    # "260707"/"260712"は§16.3で移行対象と確定した旧publicStoryId（v1、
    # Registry登録日ベース）の日付断片であり、sourceKey由来の実データを
    # 含まないと既に判断済み（§16.3参照）。移行実行PR（publicStoryId
    # 命名規約v2移行）でRegistryから旧entryが削除された後も、旧IDそのもの
    # は§16.3の新旧mapping表等に記載され続けるため、恒久的にforbidden
    # hintsから除外する（Registry連動許可リストの対象外の恒久許可）。
    "C:\\Users",
    "D:\\Dev",
)


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
    # Registry連動許可リスト方式（`Evidence_Index_Public_ID_Policy.md` §16、
    # tests/docs/_public_id_registry_hints.py）: `knowledge/public_ids/
    # story_public_ids.yaml`へ正式登録済みのpublicStoryId/publicEpisodeId
    # に含まれる日付断片のみを許可する。§16.3の新旧mapping表に書く旧ID
    # （割当日ベース、sourceKey由来ではない）はこの許可リストに該当する
    # ため許可されるが、それ以外の実データ日付断片・イベント名断片は
    # 引き続き検出される。
    content = _read_doc()
    for forbidden in filter_unregistered_hints(REAL_DATA_HINTS):
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


# ----------------------------------------------------------------
# feature/public-id-naming-v2-design
# ----------------------------------------------------------------

NAMING_V2_HEADING = "# 16. publicStoryId命名規約v2"


def _naming_v2_section() -> str:
    content = _read_doc()
    return content.split(NAMING_V2_HEADING, 1)[1]


def test_public_id_policy_doc_has_naming_v2_section():
    content = _read_doc()
    assert NAMING_V2_HEADING in content


def test_public_id_policy_doc_states_naming_v2_format():
    section = _naming_v2_section()
    assert "## 16.2 新形式（v2、決定）" in section
    assert "{CATEGORY}_{seq:03d}_{YYMMDD}" in section
    assert "EVENT" in section
    assert "RAID" in section


def test_public_id_policy_doc_states_naming_v2_change_reason():
    section = _naming_v2_section()
    reason_section = section.split("## 16.1 v1からの変更理由", 1)[1].split(
        "## 16.2", 1
    )[0]
    assert "割当日" in reason_section
    assert "sourceKey" in reason_section
    assert "2026-07-14" in reason_section


def test_public_id_policy_doc_states_naming_v2_migration_mapping_table():
    section = _naming_v2_section()
    mapping_section = section.split("## 16.3 移行対象3件の新旧mapping", 1)[1].split(
        "## 16.4", 1
    )[0]
    assert "EVT_260707_001" in mapping_section
    assert "EVT_260712_001" in mapping_section
    assert "RAID_260712_001" in mapping_section
    assert "EVENT_001_{YYMMDD}" in mapping_section
    assert "EVENT_002_{YYMMDD}" in mapping_section
    assert "RAID_001_{YYMMDD}" in mapping_section
    # 新IDの実値（sourceKey日付接頭辞）はRegistry登録前のため、まだ書かない
    assert "260425" not in mapping_section
    assert "260624" not in mapping_section
    assert "260504" not in mapping_section


def test_public_id_policy_doc_states_naming_v2_deprecation():
    section = _naming_v2_section()
    deprecation_section = section.split("## 16.4 旧ID廃止と再利用禁止", 1)[1].split(
        "## 16.5", 1
    )[0]
    assert "廃止" in deprecation_section
    assert "再利用しない" in deprecation_section


def test_public_id_policy_doc_states_naming_v2_anonymization_amendment():
    section = _naming_v2_section()
    amendment_section = section.split("## 16.5 匿名化方針の改定", 1)[1].split(
        "## 16.6", 1
    )[0]
    assert "sourceKeyの日付部分のみ" in amendment_section
    assert "イベント名部分" in amendment_section
    assert "使用禁止" in amendment_section


def test_public_id_policy_doc_states_naming_v2_open_questions():
    section = _naming_v2_section()
    assert "## 16.6 Open questions" in section
    open_questions_section = section.split("## 16.6 Open questions", 1)[1]
    assert "MAIN" in open_questions_section
    assert "OTHER" in open_questions_section


def test_public_id_policy_doc_naming_v2_does_not_expose_new_id_real_values():
    # Registry未登録の新publicStoryId実値（sourceKey日付接頭辞）はdocs全体の
    # どこにも書かれていないことを確認する。ただし§16.7（v2.1移行実行PR、
    # `feature/public-id-naming-v2-1-global-sequence`）でRegistryへ正式登録
    # 済みとなった日付断片（既公開EVENT 2 storyの新publicStoryIdに含まれる
    # 260425/260624）は、Registry連動許可リスト（`filter_unregistered_hints`、
    # §16.5の匿名化方針改定）により許可する。RAID（260504）は本PRでは
    # 変更対象外だが既にv2移行時点でRegistry登録済みのため同様に許可される。
    content = _read_doc()
    for forbidden in filter_unregistered_hints(("260425", "260624", "260504")):
        assert forbidden not in content


# ----------------------------------------------------------------
# feature/public-id-naming-v2-1-global-sequence
# ----------------------------------------------------------------

NAMING_V2_1_HEADING = (
    "## 16.7 v2.1改定（全体採番方式、2026-07-14ユーザー決定、"
    "`feature/public-id-naming-v2-1-global-sequence`で設計・実行）"
)


def _naming_v2_1_section() -> str:
    section = _naming_v2_section()
    return section.split(NAMING_V2_1_HEADING, 1)[1]


def test_public_id_policy_doc_has_naming_v2_1_section():
    content = _read_doc()
    assert NAMING_V2_1_HEADING in content


def test_public_id_policy_doc_states_naming_v2_1_change_reason():
    section = _naming_v2_1_section()
    reason_section = section.split("### 16.7.1 v2からの変更理由", 1)[1].split(
        "### 16.7.2", 1
    )[0]
    assert "Registry登録" in reason_section
    assert "通し番号" in reason_section
    assert "全量" in reason_section
    assert "2026-07-14" in reason_section


def test_public_id_policy_doc_states_naming_v2_1_numbering_rule():
    section = _naming_v2_1_section()
    rule_section = section.split("### 16.7.2 v2.1採番規則（決定）", 1)[1].split(
        "### 16.7.3", 1
    )[0]
    assert "037" in rule_section
    assert "038" in rule_section
    assert "168" in rule_section
    assert "EVENT_{seq:03d}" in rule_section
    assert (
        "{CATEGORY}_{seq:03d}_{YYMMDD}" in rule_section
        or "EVENT_{seq:03d}_{YYMMDD}" in rule_section
    )
    assert "event_numbering_table.tsv" in rule_section
    assert "typo" in rule_section.lower()
    assert "実sourceKey名は本文書に記載しない" in rule_section


def test_public_id_policy_doc_naming_v2_1_does_not_expose_typo_source_key():
    # typo事例の実sourceKey・実イベント名は書かない方針（プロンプト前提）の
    # 簡易チェック。7桁の日付らしき数字列（誤りうるパターン）が本文書に
    # 書かれていないことを確認する。
    content = _read_doc()
    assert "2411017" not in content


def test_public_id_policy_doc_states_naming_v2_1_late_discovery_rule():
    section = _naming_v2_1_section()
    rule_section = section.split("### 16.7.3 遅延発見イベントのルール（新設）", 1)[
        1
    ].split("### 16.7.4", 1)[0]
    assert "末尾seq" in rule_section
    assert "日付順序は崩れる" in rule_section
    # 2026-07-18ユーザー決定で§16.9へ改定されたため、旧ルールは取り消し線
    # (~~...~~)付きで記録し、改定先を明示するポインタを併記する
    assert "~~" in rule_section
    assert "§16.9" in rule_section
    assert "改定" in rule_section


def test_public_id_policy_doc_states_naming_v2_1_raid_open_question():
    section = _naming_v2_1_section()
    rule_section = section.split(
        "### 16.7.4 RAIDカテゴリの扱い（Open question→§16.8で解決）", 1
    )[1].split("### 16.7.5", 1)[0]
    assert "本PRでは変更しない" in rule_section
    assert "raid batch" in rule_section
    assert "未確定" in rule_section
    assert "§16.8" in rule_section


def test_public_id_policy_doc_states_naming_v2_1_rename_mapping_table():
    section = _naming_v2_1_section()
    mapping_section = section.split(
        "### 16.7.5 再改名対象（既公開EVENT 2 story）と新旧mapping", 1
    )[1].split("### 16.7.6", 1)[0]
    # 260425/260624はknowledge/public_ids/story_public_ids.yamlへ正式登録済み
    # のため、Registry連動許可リストにより本文書に書いてよい（本テストでは
    # 具体的な新旧ID値そのものの存在を直接確認する）。
    assert "EVENT_001_260425" in mapping_section
    assert "EVENT_002_260624" in mapping_section
    assert "EVENT_164_260425" in mapping_section
    assert "EVENT_168_260624" in mapping_section


def test_public_id_policy_doc_states_naming_v2_1_deprecation():
    section = _naming_v2_1_section()
    deprecation_section = section.split("### 16.7.6 旧v2 ID廃止と再利用禁止", 1)[
        1
    ].split("### 16.7.7", 1)[0]
    assert "廃止" in deprecation_section
    assert "再利用しない" in deprecation_section


def test_public_id_policy_doc_states_naming_v2_1_non_goals():
    section = _naming_v2_1_section()
    non_goals_section = section.split("### 16.7.7 本PRのNon-goals", 1)[1].split(
        "## 16.8", 1
    )[0]
    assert "RAID_001_260504" in non_goals_section
    assert "raidカテゴリ" in non_goals_section


# ----------------------------------------------------------------
# feature/raid-public-id-v2-1-alignment
# ----------------------------------------------------------------

NAMING_RAID_V2_1_HEADING = (
    "## 16.8 RAIDカテゴリへのv2.1適用（2026-07-15ユーザー決定、"
    "`feature/raid-public-id-v2-1-alignment`で設計・実行）"
)


def _naming_raid_v2_1_section() -> str:
    content = _read_doc()
    return content.split(NAMING_RAID_V2_1_HEADING, 1)[1]


def test_public_id_policy_doc_has_naming_raid_v2_1_section():
    content = _read_doc()
    assert NAMING_RAID_V2_1_HEADING in content


def test_public_id_policy_doc_states_naming_raid_v2_1_numbering_rule():
    section = _naming_raid_v2_1_section()
    rule_section = section.split("### 16.8.1 対象母集団と採番規則（決定）", 1)[1].split(
        "### 16.8.2", 1
    )[0]
    assert "27 export dir" in rule_section
    assert "001" in rule_section
    assert "004" in rule_section
    assert "005" in rule_section
    assert "027" in rule_section
    assert "RAID_{seq:03d}" in rule_section
    assert (
        "{CATEGORY}_{seq:03d}_{YYMMDD}" in rule_section
        or "RAID_{seq:03d}_{YYMMDD}" in rule_section
    )
    assert "raid_numbering_table.tsv" in rule_section
    # §16.7.3（遅延発見イベントのルール）は2026-07-18に§16.9へ改定済みで
    # あり、RAIDカテゴリにも改定後ルールが適用される旨が1行追記されている
    assert "§16.9" in rule_section
    assert "改定" in rule_section


def test_public_id_policy_doc_states_naming_raid_v2_1_rename_mapping_table():
    section = _naming_raid_v2_1_section()
    mapping_section = section.split(
        "### 16.8.2 再改名対象（既公開RAID 1 story）と新旧mapping", 1
    )[1].split("### 16.8.3", 1)[0]
    # 260504はv2移行時点でknowledge/public_ids/story_public_ids.yamlへ既に
    # 正式登録済みのため、Registry連動許可リストにより本文書に書いてよい
    # （本テストでは具体的な新旧ID値そのものの存在を直接確認する）。
    assert "RAID_001_260504" in mapping_section
    assert "RAID_027_260504" in mapping_section


def test_public_id_policy_doc_states_naming_raid_v2_1_deprecation():
    section = _naming_raid_v2_1_section()
    deprecation_section = section.split("### 16.8.3 旧v2 ID廃止と再利用禁止", 1)[
        1
    ].split("### 16.8.4", 1)[0]
    assert "廃止" in deprecation_section
    assert "再利用しない" in deprecation_section


def test_public_id_policy_doc_states_naming_raid_v2_1_non_goals():
    section = _naming_raid_v2_1_section()
    non_goals_section = section.split("### 16.8.4 本PRのNon-goals", 1)[1]
    assert "raid batch" in non_goals_section
    assert "EVENT" in non_goals_section


# ----------------------------------------------------------------
# feature/late-discovery-anchor-seq-add-rule
# ----------------------------------------------------------------

NAMING_LATE_DISCOVERY_V2_HEADING = (
    "## 16.9 遅延発見イベントルールの改定（アンカーseq+ADDマーカー方式、"
    "2026-07-18ユーザー決定、`feature/late-discovery-anchor-seq-add-rule`で"
    "設計・適用）"
)

# 遅延発見6件のうち実データ由来の断片（sourceKeyの日付・slug断片、確定
# publicStoryId）は、匿名化ルール（`AI_PR_Playbook.md` §5）によりdocsに
# 一切書かない。REAL_DATA_HINTSへ追加し、文書全体から誤って書き込まれて
# いないことを機械的に確認する（Registry未登録のため`filter_unregistered_
# hints`による許可対象にはならない）。
LATE_DISCOVERY_REAL_DATA_HINTS = (
    "220706",
    "220928",
    "231122",
    "240430",
    "240710",
    "241002",
    "infection_lala",
    "bodychange",
    "4thanniversary_2",
    "idol_purity9",
    "swimsuit",
    "tikan",
    "EVENT_069_220706_ADD",
    "EVENT_074_220928_ADD",
    "EVENT_103_231122_ADD",
    "EVENT_113_240430_ADD",
    "EVENT_118_240710_ADD",
    "EVENT_123_241002_ADD",
)


def _late_discovery_v2_section() -> str:
    content = _read_doc()
    return content.split(NAMING_LATE_DISCOVERY_V2_HEADING, 1)[1]


def test_public_id_policy_doc_has_late_discovery_v2_section():
    content = _read_doc()
    assert NAMING_LATE_DISCOVERY_V2_HEADING in content


def test_public_id_policy_doc_states_late_discovery_v2_anchor_seq_rule():
    section = _late_discovery_v2_section()
    rule_section = section.split("### 16.9.2 アンカーseq+ADDマーカー方式（決定）", 1)[
        1
    ].split("### 16.9.3", 1)[0]
    assert "アンカーseq" in rule_section
    assert "_ADD" in rule_section
    assert "{CATEGORY}_{アンカーseq:03d}_{YYMMDD}_ADD" in rule_section
    assert "_ADD2" in rule_section
    assert "ASCII文字列ソート" in rule_section
    # 実際の適用ID・日付・sourceKeyは書かない方針の合成例のみを使う
    assert "EVENT_070_990101_ADD" in rule_section


def test_public_id_policy_doc_states_late_discovery_v2_deprecates_tail_seq():
    section = _late_discovery_v2_section()
    rule_section = section.split("### 16.9.3 §16.7.3（末尾seq方式）の廃止", 1)[1].split(
        "### 16.9.4", 1
    )[0]
    assert "廃止" in rule_section
    assert "適用実績ゼロ" in rule_section


def test_public_id_policy_doc_states_late_discovery_v2_first_application():
    section = _late_discovery_v2_section()
    rule_section = section.split(
        "### 16.9.4 初回適用（event categoryの遅延発見6件）", 1
    )[1].split("### 16.9.5", 1)[0]
    assert "168" in rule_section
    assert "174" in rule_section
    assert "event_numbering_table.tsv" in rule_section
    assert "非commit" in rule_section


def test_public_id_policy_doc_states_late_discovery_v2_non_goals():
    section = _late_discovery_v2_section()
    non_goals_section = section.split("### 16.9.5 本PRのNon-goals", 1)[1]
    assert "raw配置" in non_goals_section
    assert "Registry" in non_goals_section


def test_public_id_policy_doc_does_not_contain_late_discovery_real_data():
    content = _read_doc()
    for forbidden in filter_unregistered_hints(LATE_DISCOVERY_REAL_DATA_HINTS):
        assert forbidden not in content


def test_tasks_md_does_not_contain_late_discovery_real_data():
    content = TASKS_PATH.read_text(encoding="utf-8")
    for forbidden in filter_unregistered_hints(LATE_DISCOVERY_REAL_DATA_HINTS):
        assert forbidden not in content
