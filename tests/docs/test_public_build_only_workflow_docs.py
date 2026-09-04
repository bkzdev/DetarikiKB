"""合成public build-only workflow / runbookの契約テスト。"""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "public-build.yml"
RUNBOOK = PROJECT_ROOT / "docs" / "runbooks" / "Public_Build_Only.md"
TASKS = PROJECT_ROOT / "TASKS.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_workflow_is_read_only_synthetic_build_without_upload_or_deploy() -> None:
    text = _read(WORKFLOW)
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"pull_request", "push"}
    assert workflow["on"]["push"]["branches"] == ["main"]
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"public-build"}
    assert workflow["jobs"]["public-build"]["runs-on"] == "ubuntu-latest"

    for required in (
        "actions/checkout@v4",
        "astral-sh/setup-uv@v5",
        "actions/setup-python@v5",
        "uv sync --locked",
        "approved_synthetic_input.json",
        "$RUNNER_TEMP/dkb-public-build",
        "prepare_public_build.py",
        "mkdocs build --strict",
        "zensical build --strict --clean",
        "check_public_site_manifest.py",
        "--generator-name mkdocs-material",
        "--generator-name zensical",
        "--write-manifest",
        "compare_public_site_manifests.py",
        "git rev-parse HEAD",
    ):
        assert required in text

    for forbidden in (
        "pull_request_target",
        "workflow_dispatch",
        "actions/upload-artifact",
        "actions/upload-pages-artifact",
        "actions/deploy-pages",
        "pages: write",
        "id-token: write",
        "environment:",
        "knowledge/public/",
    ):
        assert forbidden not in text


def test_runbook_and_handoff_fix_build_only_boundary() -> None:
    runbook = _read(RUNBOOK)
    tasks = _read(TASKS)
    for required in (
        "Status: Implemented",
        ".github/workflows/public-build.yml",
        "commit済みの匿名合成public inputだけ",
        "contents: read",
        "public-only semantic gate",
        "detached manifest",
        "artifactとしてuploadしない",
        "manual production workflow",
    ):
        assert required in runbook
    assert "`codex/public-build-only-workflow`" in tasks
    assert "次はmanual production workflow" in tasks
