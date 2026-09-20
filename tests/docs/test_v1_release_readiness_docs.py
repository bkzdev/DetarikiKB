"""M7 v1 release readiness checklistの軽量な整合性テスト。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUNBOOK = PROJECT_ROOT / "docs" / "runbooks" / "V1_Release_Readiness.md"
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


def test_release_readiness_is_a_draft_not_a_release_decision() -> None:
    content = _read(RUNBOOK)
    assert "Status: Draft checklist; release decision not yet made" in content
    assert "v1 releaseの承認やM2〜M5の完了を意味しない" in content
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


def test_project_status_marks_m7_in_progress_without_completing_it() -> None:
    milestones = _read(MILESTONES)
    assert "| M3 Extraction / Merge / 内部KB | 完了 |" in milestones
    assert "M3は2026-09-17に完了した" in milestones
    assert "| M7 v1リリースと継続運用 | 進行中 |" in milestones
    assert "rehearsal recordを実装済み" in milestones
    assert "production dispatchやM7完了判定はこの段階では行わない" in milestones

    assert "codex/v1-release-readiness-checklist" in _read(TASKS)
    assert "docs/runbooks/V1_Release_Readiness.md" in _read(AI_CONTEXT)


def test_release_candidate_record_is_local_and_does_not_authorize_deploy() -> None:
    content = _read(RUNBOOK)
    assert (PROJECT_ROOT / "scripts/build_v1_release_candidate_record.py").is_file()
    assert (PROJECT_ROOT / "schemas/v1_release_candidate_record.schema.json").is_file()
    assert "workspace/dry_runs/" in content
    assert "candidateGateStatus: pending_human_approval" in content
    assert "scriptはdispatch、" in content
