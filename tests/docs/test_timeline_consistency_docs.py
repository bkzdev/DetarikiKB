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
TASKS_PATH = PROJECT_ROOT / "TASKS.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runbook_defines_stage_a_cycle_check_contract():
    content = _read(RUNBOOK_PATH)
    for required in (
        "scripts/check_timeline_consistency.py",
        'TimelineCandidate(kind: "relative_order")',
        "timeline_relative_order_cycle",
        "timeline_relative_order_within_same_time_class",
        "Union-Find",
        "反復Kosaraju法",
        "candidate ID・Evidence ID・入力path",
        "target_not_loaded",
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


def test_tasks_records_completed_first_stage_and_remaining_scope():
    content = _read(TASKS_PATH)
    assert "`codex/timeline-same-time-consistency`" in content
    assert "timeline contradiction detectionの第1・第2段階" in content
    assert "数値順序のfield別整合性・総順序判定" in content
