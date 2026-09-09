"""Public site manifest / exposure scan文書の引き継ぎ契約。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DESIGN = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "07_Wiki"
    / "Public_Site_Manifest_Exposure_Scan.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_design_fixes_manifest_exposure_and_authorization_boundaries() -> None:
    design = _read(DESIGN)
    for required in (
        "Status: Implemented",
        "schemas/public_site_manifest.schema.json",
        "agents/wiki_generator/public_site_manifest.py",
        "scripts/check_public_site_manifest.py",
        "verified_build_candidate",
        "deploymentAuthorized: false",
        "detached JSON",
        "treeSha256",
        "HTML entity",
        "sto<span>ryId</span>",
        "search/search_index.json",
        "JSON parse後のkey / valueもscan",
        "全site相対file pathも同じmarker ruleでscan",
        "検出値、file path、HTML断片はlogへ出さない",
        "実HTML、実manifest、実public inputをcommit / uploadしない",
        "build-only GitHub Actions workflowへの統合",
    ):
        assert required in design


def test_handoff_records_rehearsal_and_points_to_prepush_review() -> None:
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
    dual_build = _read(PROJECT_ROOT / "docs" / "runbooks" / "Wiki_Dual_Build.md")

    assert "`codex/public-projection-prepush-review`" in tasks
    assert "Public_Site_Manifest_Exposure_Scan.md" in context
    assert "~~deploy前site manifest / exposure scan契約" in publishing
    assert "A→B→A rollback rehearsalまで完了" in milestones
    assert "同じ`check_public_site_manifest.py`を各siteへ適用" in dual_build
    assert "Pages artifact upload / protected deploy" in dual_build
