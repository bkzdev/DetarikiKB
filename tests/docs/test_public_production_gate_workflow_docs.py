"""Manual public production environment gateの契約テスト。"""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "public-production-gate.yml"
RUNBOOK = PROJECT_ROOT / "docs" / "runbooks" / "Public_Production_Gate.md"
TASKS = PROJECT_ROOT / "TASKS.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_workflow_is_manual_protected_synthetic_gate_without_deploy() -> None:
    text = _read(WORKFLOW)
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"source_sha"}
    assert inputs["source_sha"]["required"] == "true"
    assert inputs["source_sha"]["type"] == "string"
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "public-production",
        "cancel-in-progress": "false",
    }
    assert set(workflow["jobs"]) == {"preflight", "production-gate"}
    preflight = workflow["jobs"]["preflight"]
    steps = preflight["steps"]
    assert [step["name"] for step in steps[:4]] == [
        "Verify dispatch context",
        "Checkout trusted main",
        "Verify protected production environment",
        "Verify and checkout requested source",
    ]
    checkout = steps[1]
    assert checkout["uses"] == (
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"
    )
    assert checkout["with"] == {
        "ref": "refs/heads/main",
        "fetch-depth": "0",
        "persist-credentials": "false",
    }
    environment_check = steps[2]["run"]
    assert "check_public_environment.py" in environment_check
    verify_source = steps[3]["run"]
    assert "check_public_production_source.py" in verify_source
    assert verify_source.index(
        "check_public_production_source.py"
    ) < verify_source.index("git checkout --quiet --detach")
    gate = workflow["jobs"]["production-gate"]
    assert gate["needs"] == "preflight"
    assert gate["environment"] == {"name": "github-pages"}

    for required in (
        "refs/heads/main",
        "check_public_environment.py",
        "production-environment-unavailable",
        "deployment-branch-policies",
        "check_public_production_source.py",
        "git fetch --quiet --no-tags origin refs/heads/main:refs/remotes/origin/main",
        "git checkout --quiet --detach",
        "persist-credentials: false",
        "fetch-depth: 0",
        "ref: refs/heads/main",
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
        "astral-sh/setup-uv@e58605a9b6da7c637471fab8847a5e5a6b8df081",
        "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
        "approved_synthetic_input.json",
        "$RUNNER_TEMP/dkb-production-gate",
        "prepare_public_build.py",
        "mkdocs build --strict",
        "zensical build --strict --clean",
        "check_public_site_manifest.py",
        "compare_public_site_manifests.py",
        "deployment_authorized=false",
    ):
        assert required in text

    for forbidden in (
        "pull_request:",
        "pull_request_target",
        "push:",
        "actions/upload-artifact",
        "actions/upload-pages-artifact",
        "actions/configure-pages",
        "actions/deploy-pages",
        "pages: write",
        "id-token: write",
        "environment_url",
        "environment_configured",
        "knowledge/public/",
    ):
        assert forbidden not in text


def test_runbook_and_handoff_fix_manual_non_deploy_boundary() -> None:
    runbook = _read(RUNBOOK)
    tasks = _read(TASKS)
    for required in (
        "Status: Implemented",
        ".github/workflows/public-production-gate.yml",
        "初回dispatch前の人間設定",
        "required reviewer",
        "自己申告は承認根拠にしない",
        "administrator bypass禁止",
        "custom branch policyが`main`だけ",
        "小文字40桁",
        "origin/main",
        "contents: read",
        "deployment_authorized=false",
        "artifact upload",
        "rollback rehearsal",
    ):
        assert required in runbook
    assert "`codex/manual-production-workflow-gate`" in tasks
    assert "次は匿名合成siteのdeploy / rollback rehearsal" in tasks
