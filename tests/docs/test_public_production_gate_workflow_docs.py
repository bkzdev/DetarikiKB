"""Manual public production environment gateの契約テスト。"""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "public-production-gate.yml"
RUNBOOK = PROJECT_ROOT / "docs" / "runbooks" / "Public_Production_Gate.md"
TASKS = PROJECT_ROOT / "TASKS.md"
AI_CONTEXT = PROJECT_ROOT / "AI_CONTEXT.md"
MILESTONES = (
    PROJECT_ROOT / "docs" / "architecture" / "01_Project" / "Project_Milestones.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_workflow_is_manual_protected_synthetic_pages_deploy() -> None:
    text = _read(WORKFLOW)
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"source_sha", "expected_tree_sha256"}
    assert inputs["source_sha"]["required"] == "true"
    assert inputs["source_sha"]["type"] == "string"
    assert inputs["expected_tree_sha256"] == {
        "description": "Optional lowercase Zensical tree SHA-256 required for rollback",
        "required": "false",
        "default": "",
        "type": "string",
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "public-production",
        "cancel-in-progress": "false",
    }
    assert set(workflow["jobs"]) == {"preflight", "deploy"}
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
    assert '--expected-reviewer "$GITHUB_REPOSITORY_OWNER"' in environment_check
    verify_source = steps[3]["run"]
    assert "check_public_production_source.py" in verify_source
    assert verify_source.index(
        "check_public_production_source.py"
    ) < verify_source.index("git checkout --quiet --detach")
    upload = next(
        step for step in steps if step["name"] == "Upload verified Zensical site"
    )
    assert upload["uses"] == (
        "actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9"
    )
    assert upload["with"] == {
        "name": "github-pages",
        "path": "${{ env.PUBLIC_BUILD_ROOT }}/site-zensical",
        "retention-days": "1",
    }
    deploy = workflow["jobs"]["deploy"]
    assert deploy["needs"] == "preflight"
    assert deploy["permissions"] == {
        "contents": "read",
        "pages": "write",
        "id-token": "write",
    }
    assert deploy["environment"] == {
        "name": "github-pages",
        "url": "${{ steps.deployment.outputs.page_url }}",
    }
    deployment = next(
        step
        for step in deploy["steps"]
        if step["name"] == "Deploy verified synthetic site"
    )
    assert deployment["uses"] == (
        "actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346"
    )
    assert deployment["with"] == {"artifact_name": "github-pages"}
    pages_config = next(
        step
        for step in deploy["steps"]
        if step["name"] == "Verify GitHub Pages settings"
    )
    assert deploy["steps"].index(pages_config) < deploy["steps"].index(deployment)
    assert '.build_type == "workflow"' in pages_config["run"]
    assert ".cname == null" in pages_config["run"]
    assert '(.html_url | rtrimstr("/")) == $expected_url' in pages_config["run"]
    assert "Authorization: Bearer $GH_TOKEN" in pages_config["run"]

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
        "production-rollback-digest-required",
        "production-output-digest-mismatch",
        "Verified synthetic Pages candidate",
        "actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9",
        "actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346",
        "production-pages-settings-invalid",
        "production-page-url-mismatch",
        "deployment_authorized=true",
    ):
        assert required in text

    for forbidden in (
        "pull_request:",
        "pull_request_target",
        "push:",
        "knowledge/public/",
        "site-mkdocs\n          retention-days",
        "preview: true",
    ):
        assert forbidden not in text


def test_runbook_and_handoff_fix_synthetic_deploy_and_rollback_boundary() -> None:
    runbook = _read(RUNBOOK)
    tasks = _read(TASKS)
    context = _read(AI_CONTEXT)
    milestones = _read(MILESTONES)
    for required in (
        "Status: Implemented",
        ".github/workflows/public-production-gate.yml",
        "初回dispatch前の人間設定",
        "required reviewer",
        "自己申告は承認根拠にしない",
        "administrator bypass禁止",
        "custom branch policyが`main`だけ",
        "solo運用",
        "self-reviewを許可",
        "小文字40桁",
        "origin/main",
        "expected_tree_sha256",
        "Zensical",
        "A→B→A",
        "deployment record",
        "rollback rehearsal",
    ):
        assert required in runbook
    assert "`codex/public-projection-prepush-review`" in tasks
    assert "A→B→A" in tasks
    assert "34323175235" in runbook
    assert "Status: Implemented and rehearsed" in runbook
    for handoff in (tasks, context, milestones):
        assert "実データpublic projectionをignored workspaceで生成" in handoff
        assert "push前" in handoff
