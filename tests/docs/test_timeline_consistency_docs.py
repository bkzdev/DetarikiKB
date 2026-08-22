"""Timeline横断整合性checkの設計・運用文書契約を固定する。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUNBOOK_PATH = PROJECT_ROOT / "docs" / "runbooks" / "Timeline_Consistency_Check.md"
PIPELINE_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Extraction_Pipeline.md"
)
RESULT_SCHEMA_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Extraction_Result_Schema.md"
)
MERGED_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Merged_Knowledge_Design.md"
)
DECISION_FRAME_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "03_Data_Model"
    / "Canonical_Timeline_Scope_Decision.md"
)
TIMELINE_MODEL_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "03_Data_Model" / "Timeline.md"
)
TIMELINE_PAGE_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "07_Wiki" / "Timeline_Page.md"
)
WIKI_OUTPUT_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "07_Wiki" / "Wiki_Output_Design.md"
)
TASKS_PATH = PROJECT_ROOT / "TASKS.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runbook_defines_stage_a_cycle_check_contract():
    content = _read(RUNBOOK_PATH)
    for required in (
        "scripts/check_timeline_consistency.py",
        'kind: "relative_order"',
        "timeline_relative_order_cycle",
        "timeline_relative_order_within_same_time_class",
        "Union-Find",
        "反復Kosaraju法",
        "candidate ID・Evidence ID・入力path",
        "target_not_loaded",
        "timeline_episode_order_field_value_conflict",
        "numericIgnoredObservations",
        "extractionRun",
        "timeline_canonical_order_relative_constraint_conflict",
        "cross_story_constraint",
        "releaseOrder` / `displayOrder`は補完・fallback・比較に使わない",
        "readyForCanonicalReview",
        "observedOrderBuckets",
        "readinessがfalseであることだけでは失敗にせず",
    ):
        assert required in content


def test_runbook_defines_report_and_output_safety():
    content = _read(RUNBOOK_PATH)
    for required in (
        "schemas/timeline_consistency_report.schema.json",
        'status: "passed"',
        'status: "needs_review"',
        'status: "invalid_input"',
        "workspace/dry_runs/",
        "既存reportは上書きしない",
    ):
        assert required in content


def test_architecture_keeps_check_separate_from_stage_b_merge():
    for path in (PIPELINE_PATH, RESULT_SCHEMA_PATH, MERGED_DESIGN_PATH):
        content = _read(path)
        assert "scripts/check_timeline_consistency.py" in content
        assert "same_time" in content
    assert "Stage B自体は順序graphの整合性判定を行わない" in _read(MERGED_DESIGN_PATH)
    assert "この代表値はcanonical chronologyの採用値ではない" in _read(
        MERGED_DESIGN_PATH
    )


def test_tasks_records_completed_stages_and_remaining_scope():
    content = _read(TASKS_PATH)
    assert "`codex/timeline-episode-order-value-conflict`" in content
    assert "`codex/timeline-canonical-relative-consistency`" in content
    assert "`codex/timeline-canonical-coverage-readiness`" in content
    assert "timeline contradiction detectionの第1〜第5段階" in content
    assert "総順序判定、canonical Timeline確定、cross-story chronology" in content


def test_docs_record_first_real_readiness_dry_run_without_committing_reports():
    runbook = _read(RUNBOOK_PATH)
    tasks = _read(TASKS_PATH)
    for required in (
        "初回実データdry-run（2026-08-03）",
        "resolved / valid input: 733 / 733",
        "comparable / missing / ambiguous episode: 0 / 733 / 0",
        "`readyForCanonicalReview: true`: 0 / 72 story",
        "両runのreportはv0.5 schema error 0件",
        "report本体は内部IDとlocal pathを含むため"
        "`workspace/dry_runs/`だけに保持し、commitしない",
        "人間確認後に`story_manifest.yaml`へ保存",
        "個別episodeの根拠を人間が確認してmanifestへ値を割り当て",
    ):
        assert required in runbook
    assert "`codex/timeline-canonical-readiness-first-real-dry-run`" in tasks
    assert "全733 episodeでcanonical observation未付与" in tasks


def test_global_scope_decision_frame_keeps_current_freeze_and_lists_decisions():
    content = _read(DECISION_FRAME_PATH)
    for required in (
        "Status: Proposed — 実装前に人間判断が必要",
        "# 2. 現在確定している境界",
        "# 4. 判断前に維持する不変則",
        "## D1. 初期global scope",
        "## D2. 順序表現",
        "## D3. 関係状態",
        "## D4. 許容するcross-story根拠",
        "## D5. Review unitとpromotion gate",
        "## D6. Internal / public出力",
        "partial order graph",
        "same_time",
        "unknown",
        "conflict",
        "cross_story_constraint",
        "provenance",
        "未採択",
    ):
        assert required in content


def test_global_scope_decision_frame_rejects_implicit_global_promotion():
    content = _read(DECISION_FRAME_PATH)
    for required in (
        "既存`canonicalOrder`の数値をstory間で比較しない",
        "`releaseOrder` / `displayOrder` / `episodeNumber`",
        "winner選択",
        "自動promotionしない",
        "canonical Timelineのpromotionまたは公開",
    ):
        assert required in content


def test_timeline_docs_link_to_global_scope_decision_frame():
    for path in (
        RUNBOOK_PATH,
        TIMELINE_MODEL_PATH,
        TIMELINE_PAGE_PATH,
        WIKI_OUTPUT_DESIGN_PATH,
    ):
        assert "Canonical_Timeline_Scope_Decision.md" in _read(path)


def test_tasks_records_global_scope_decision_frame_as_proposed():
    content = _read(TASKS_PATH)
    assert "`codex/timeline-canonical-global-scope-decision-frame`" in content
    assert "docs-only、Status: Proposed" in content
