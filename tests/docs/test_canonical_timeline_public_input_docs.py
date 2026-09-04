"""Canonical Timeline public input / promotion文書の引き継ぎ契約を固定する。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DESIGN = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "07_Wiki"
    / "Canonical_Timeline_Public_Input.md"
)
RUNBOOK = (
    PROJECT_ROOT / "docs" / "runbooks" / "Canonical_Timeline_Public_Input_Promotion.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_design_records_public_envelope_without_publish_approval() -> None:
    design = _read(DESIGN)
    for required in (
        "Status: Implemented",
        "knowledge/public/timelines/canonical_timeline_public_input.json",
        "schemas/canonical_timeline_public_input.schema.json",
        "schemas/canonical_timeline_public_input_review.schema.json",
        "schemas/canonical_timeline_public_preflight_record.schema.json",
        "approved_for_build",
        "projection_candidate",
        "additionalProperties: false",
        "payloadSha256",
        "reviewer名、自由記述、internal input digest",
        "publish-ready",
        "実入力も合成入力も正式保存先へ昇格しない",
        "site manifest",
        "deploy",
    ):
        assert required in design


def test_runbook_is_dry_run_by_default_and_fail_closed() -> None:
    runbook = _read(RUNBOOK)
    for required in (
        "workspace/public_wiki_inputs/",
        "--expected-projection-sha256",
        "status=dry_run",
        "--execute",
        "targetが既に存在する場合",
        "`--overwrite`は存在しない",
        "reviewer名やnoteを追加してはならない",
        "5入力digest完全一致",
        "Git indexで追跡済み",
        "secure-directory-api-unavailable",
        "Linux / WSL",
        "実public inputの生成・昇格・commit",
        "artifact upload / deploy",
    ):
        assert required in runbook


def test_handoff_points_to_site_manifest_without_real_input() -> None:
    tasks = _read(PROJECT_ROOT / "TASKS.md")
    context = _read(PROJECT_ROOT / "AI_CONTEXT.md")
    publishing = _read(
        PROJECT_ROOT
        / "docs"
        / "architecture"
        / "07_Wiki"
        / "Public_Publishing_Workflow_Decision.md"
    )
    milestones = _read(
        PROJECT_ROOT / "docs" / "architecture" / "01_Project" / "Project_Milestones.md"
    )

    assert "`codex/canonical-timeline-public-input-promotion`" in tasks
    assert "次はdeploy前site manifest / rendered HTML exposure scan" in tasks
    assert "Canonical_Timeline_Public_Input.md" in context
    assert "Canonical_Timeline_Public_Input_Promotion.md" in context
    assert "~~public-safe構造化入力の保存schema" in publishing
    assert "次はsite manifest / HTML漏えい検査" in milestones

    target_dir = PROJECT_ROOT / "knowledge" / "public" / "timelines"
    assert sorted(path.name for path in target_dir.iterdir()) == [".gitkeep"]
