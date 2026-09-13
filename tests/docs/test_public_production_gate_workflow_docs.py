"""Manual public production environment gateの契約テスト。"""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "public-production-gate.yml"
INPUT_SELECTOR = PROJECT_ROOT / "scripts" / "select_public_production_input.py"
RUNBOOK = PROJECT_ROOT / "docs" / "runbooks" / "Public_Production_Gate.md"
TASKS = PROJECT_ROOT / "TASKS.md"
AI_CONTEXT = PROJECT_ROOT / "AI_CONTEXT.md"
MILESTONES = (
    PROJECT_ROOT / "docs" / "architecture" / "01_Project" / "Project_Milestones.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_workflow_is_manual_protected_reviewed_pages_deploy() -> None:
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
    assert [step["name"] for step in steps[:6]] == [
        "Verify dispatch context",
        "Checkout trusted main",
        "Verify protected production environment",
        "Verify requested source",
        "Select reviewed public input",
        "Checkout requested source",
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
    assert "git checkout --quiet --detach" not in verify_source
    select_input = steps[4]["run"]
    assert "select_public_production_input.py" in select_input
    assert "jq -er '.path'" in select_input
    assert "jq -er '.profile'" in select_input
    checkout_source = steps[5]["run"]
    assert "git checkout --quiet --detach" in checkout_source
    assert "production-source-checkout-mismatch" in checkout_source
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
        if step["name"] == "Deploy verified public site"
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
        "select_public_production_input.py",
        "git fetch --quiet --no-tags origin refs/heads/main:refs/remotes/origin/main",
        "git checkout --quiet --detach",
        "persist-credentials: false",
        "fetch-depth: 0",
        "ref: refs/heads/main",
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
        "astral-sh/setup-uv@e58605a9b6da7c637471fab8847a5e5a6b8df081",
        "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
        "$RUNNER_TEMP/dkb-production-gate",
        "prepare_public_build.py",
        "mkdocs build --strict",
        "zensical build --strict --clean",
        "check_public_site_manifest.py",
        "compare_public_site_manifests.py",
        "production-rollback-digest-required",
        "production-output-digest-mismatch",
        "Verified public Pages candidate",
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
        "site-mkdocs\n          retention-days",
        "preview: true",
    ):
        assert forbidden not in text


def test_input_selector_pins_reviewed_and_legacy_boundaries() -> None:
    selector = _read(INPUT_SELECTOR)
    for required in (
        "bb37a6274e79f504e5ddc3e240e2c4420196ca70",
        "knowledge/public/timelines/canonical_timeline_public_input.json",
        "approved_synthetic_input.json",
        "reviewed-public-input",
        "legacy-synthetic-rollback",
        "production-public-input-boundary-unavailable",
        "production-public-input-unavailable",
        "merge-base",
        "--is-ancestor",
    ):
        assert required in selector


def test_runbook_and_handoff_fix_reviewed_deploy_and_rollback_boundary() -> None:
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
        "legacy-synthetic-rollback",
    ):
        assert required in runbook
    assert "`codex/canonical-timeline-real-workflow-switch`" in tasks
    assert "実入力導入commit" in tasks
    assert "34323175235" in runbook
    assert "34742291497" in runbook
    assert "eebbd70af0916ec5d7c0108757cd0092ce9b55d1a8a797018d6d11aa26f11c74" in runbook
    assert "Status: Implemented, rehearsed, and live" in runbook
    assert "初回実content deploy" in tasks
    assert "実データpublic projectionのpush前review" in milestones
    assert "72 episode / 40 confirmed relation" in context
    assert "レビュー済みpublic input" in context
    for handoff in (context, milestones):
        assert "push前" in handoff
