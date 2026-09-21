"""M7 v1 release readiness checklistの軽量な整合性テスト。"""

import json
from pathlib import Path

from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUNBOOK = PROJECT_ROOT / "docs" / "runbooks" / "V1_Release_Readiness.md"
RELEASE_RECORD = PROJECT_ROOT / "docs" / "releases" / "V1_Release_Record_2026-09-21.md"
ROLLBACK_RECORD = PROJECT_ROOT / "config" / "public_rollback.json"
ROLLBACK_SCHEMA = PROJECT_ROOT / "schemas" / "public_rollback_record.schema.json"
MILESTONES = (
    PROJECT_ROOT / "docs" / "architecture" / "01_Project" / "Project_Milestones.md"
)
TASKS = PROJECT_ROOT / "TASKS.md"
AI_CONTEXT = PROJECT_ROOT / "AI_CONTEXT.md"
REAL_DATA_DRY_RUN = PROJECT_ROOT / "docs" / "runbooks" / "Real_Data_Dry_Run.md"
MERGED_DRY_RUN = (
    PROJECT_ROOT / "docs" / "runbooks" / "Real_Data_Merged_Collection_Dry_Run.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


RELEASE_SHA = "a18122cb1ae8e196d1b5bdf4de0fc77061453277"
LOCAL_REHEARSAL_TREE_SHA256 = (
    "59e07e25d53fac86bb2356d418f7ca4d86b52d1a0bf8072c0d2e30d95e8e3b66"
)
PRODUCTION_TREE_SHA256 = (
    "eebbd70af0916ec5d7c0108757cd0092ce9b55d1a8a797018d6d11aa26f11c74"
)
PRODUCTION_MANIFEST_SHA256 = (
    "cc578d0a27664bb8821326f6eadad5838beace00e1921eeb410da74a2d8b269f"
)
PRODUCTION_RUN_ID = 35585381055


def test_release_readiness_records_completed_release_decision() -> None:
    content = _read(RUNBOOK)
    assert "Version: 1.0" in content
    assert "Status: Released; release decision completed on 2026-09-21" in content
    assert RELEASE_SHA in content
    assert "最終判断は`released`、M7は完了" in content
    assert "Final decision: pending | released | rejected" in content


def test_release_readiness_covers_required_operational_gates() -> None:
    content = _read(RUNBOOK)
    for required in (
        "## 3. Milestone依存gate",
        "## 4. 再生成と品質証跡",
        "### 4.3 Blocking条件",
        "## 5. Code / documentation gate",
        "## 6. Public release gate",
        "## 7. 障害時とrollback",
        "## 8. 継続運用",
        "## 9. Release record",
        "## 10. M7完了条件",
        "unknown、unresolved、conflict、provenanceの黙示破棄",
        "protected environmentで人間がdeployを承認",
        "expected_tree_sha256",
    ):
        assert required in content


def test_release_readiness_links_existing_source_runbooks() -> None:
    content = _read(RUNBOOK)
    for relative_path in (
        "AI_PR_Playbook.md",
        "Real_Data_Dry_Run.md",
        "Real_Data_Merged_Collection_Dry_Run.md",
        "Timeline_Consistency_Check.md",
        "Real_Data_Wiki_Render_Dry_Run.md",
        "MkDocs_Local_Preview.md",
        "Public_Build_Only.md",
        "Public_Production_Gate.md",
    ):
        assert (RUNBOOK.parent / relative_path).is_file()
        assert relative_path in content


def test_m2_release_scope_runner_and_anonymous_report_are_documented() -> None:
    readiness = _read(RUNBOOK)
    dry_run = _read(REAL_DATA_DRY_RUN)

    assert (PROJECT_ROOT / "scripts" / "normalize_release_scope.py").is_file()
    assert (
        PROJECT_ROOT / "schemas" / "release_scope_normalization_report.schema.json"
    ).is_file()
    assert "normalize_release_scope.py" in readiness
    assert "release_scope_normalization_report.schema.json" in readiness
    assert "## 7.1 v1 release scopeの一括生成" in dry_run
    assert "全件成功後だけ`--output`へatomic" in dry_run
    assert "内部ID、raw path、" in dry_run


def test_m3_release_scope_runner_and_anonymous_report_are_documented() -> None:
    readiness = _read(RUNBOOK)
    dry_run = _read(MERGED_DRY_RUN)

    assert (PROJECT_ROOT / "scripts" / "build_release_scope_knowledge.py").is_file()
    assert (
        PROJECT_ROOT / "schemas" / "release_scope_knowledge_report.schema.json"
    ).is_file()
    assert "build_release_scope_knowledge.py" in readiness
    assert "release_scope_knowledge_report.schema.json" in readiness
    assert "# 5. release scope一括実行手順（推奨）" in dry_run
    assert "個別ID、path、本文" in dry_run


def test_project_status_marks_m7_and_v1_complete() -> None:
    milestones = _read(MILESTONES)
    assert "| M3 Extraction / Merge / 内部KB | 完了 |" in milestones
    assert "M3は2026-09-17に完了した" in milestones
    assert "| M7 v1リリースと継続運用 | 完了 |" in milestones
    assert "DKB v1を2026-09-21にreleaseした" in milestones
    assert RELEASE_SHA in milestones

    assert "codex/v1-release-final-record" in _read(TASKS)
    assert "docs/runbooks/V1_Release_Readiness.md" in _read(AI_CONTEXT)


def test_release_record_preserves_public_evidence_and_final_decision() -> None:
    content = _read(RELEASE_RECORD)
    for required in (
        "Status: Released",
        RELEASE_SHA,
        "2,840 episode",
        "4,778 entity",
        "Dual build route count: 139",
        str(PRODUCTION_RUN_ID),
        LOCAL_REHEARSAL_TREE_SHA256,
        PRODUCTION_MANIFEST_SHA256,
        PRODUCTION_TREE_SHA256,
        "8cdc81c9895a242563ddf8a9818dee2c578df303b5b215802eaef74000399f35",
        "182f170fef1aa29566c7eb64c40fa8549155234d2d00bb49c68ffe9da5a887fe",
        "f550157140288df0567fbaf4898aec2ca5b8a11c6cb766a125e7ed81f6671d5b",
        "eb79814e1fd16672f51de67ca2939af371dda1dc22ba6f666fb491c539910ceb",
        "20521de32fa3a3814efa83a86249acae03b184b89b41856d2308c39707034c80",
        "MAIN 213、EVENT 537、RAID 62、CHAR_MAIN 216、CHAR_EXTRA 220、",
        "CHAR_DATE 859、CHAR_HS 733の合計2,840 episode",
        "4領域すべて`reviewable: true`",
        "`fullyConfirmed`はfalse",
        "Final decision: **released**",
    ):
        assert required in content


def test_machine_readable_rollback_record_matches_release() -> None:
    record = json.loads(_read(ROLLBACK_RECORD))
    schema = json.loads(_read(ROLLBACK_SCHEMA))
    Draft7Validator(schema).validate(record)

    assert record["sourceSha"] == RELEASE_SHA
    assert record["treeSha256"] == PRODUCTION_TREE_SHA256
    assert record["runId"] == PRODUCTION_RUN_ID
    assert record["publicUrl"] == "https://bkzdev.github.io/DetarikiKB/"


def test_release_candidate_record_is_local_and_does_not_authorize_deploy() -> None:
    content = _read(RUNBOOK)
    assert (PROJECT_ROOT / "scripts/build_v1_release_candidate_record.py").is_file()
    assert (PROJECT_ROOT / "schemas/v1_release_candidate_record.schema.json").is_file()
    assert "workspace/dry_runs/" in content
    assert "candidateGateStatus: pending_human_approval" in content
    assert "scriptはdispatch、" in content
