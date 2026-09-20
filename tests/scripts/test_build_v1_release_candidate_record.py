"""v1 release candidate record CLIの境界テスト。"""

from __future__ import annotations

import json

import pytest

from agents.release_candidate import ReleaseCandidateError
from scripts import build_v1_release_candidate_record as cli


def test_git_gate_requires_clean_head_equal_to_origin_main(monkeypatch) -> None:
    candidate = "a" * 40
    responses = {
        (
            "git",
            "fetch",
            "--quiet",
            "--no-tags",
            "origin",
            "refs/heads/main:refs/remotes/origin/main",
        ): "",
        ("git", "status", "--porcelain"): "",
        ("git", "branch", "--show-current"): "main",
        ("git", "rev-parse", "HEAD"): candidate,
        ("git", "rev-parse", "origin/main"): candidate,
    }
    monkeypatch.setattr(cli, "_run", lambda *args: responses[args])
    cli._check_git(candidate)

    responses[("git", "rev-parse", "origin/main")] = "b" * 40
    with pytest.raises(
        ReleaseCandidateError, match="release-candidate-not-origin-main"
    ):
        cli._check_git(candidate)


def test_repository_must_match_origin_and_gh_context(monkeypatch) -> None:
    def run(*args: str) -> str:
        if args[:3] == ("git", "remote", "get-url"):
            return "https://github.com/example/project.git"
        return json.dumps({"nameWithOwner": "example/project"})

    monkeypatch.setattr(cli, "_run", run)
    assert cli._repository(None) == "example/project"
    assert cli._public_url("Example/project") == "https://example.github.io/project/"
    with pytest.raises(ReleaseCandidateError, match="release-repository-mismatch"):
        cli._repository("other/project")


def test_committed_rollback_record_is_schema_and_run_verified(monkeypatch) -> None:
    rollback = json.loads(cli._ROLLBACK_RECORD.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        cli,
        "_rollback_run_url",
        lambda repository, run_id, source_sha: (
            f"https://github.com/{repository}/actions/runs/{run_id}"
        ),
    )
    record, url = cli._rollback_record("bkzdev/DetarikiKB")
    assert record == rollback
    assert url.endswith(f"/{rollback['runId']}")


def test_workflow_run_is_read_only_verified_by_id(monkeypatch) -> None:
    payload = {
        "status": "completed",
        "conclusion": "success",
        "event": "push",
        "head_branch": "main",
        "path": ".github/workflows/ci.yml",
        "name": "CI",
        "head_sha": "a" * 40,
        "html_url": "https://github.com/example/project/actions/runs/1",
    }
    monkeypatch.setattr(cli, "_run", lambda *args: json.dumps(payload))
    evidence = cli._workflow_evidence("example/project", 1, payload["path"])
    assert evidence == {
        "workflow": "CI",
        "headSha": "a" * 40,
        "conclusion": "success",
        "runUrl": "https://github.com/example/project/actions/runs/1",
    }


@pytest.mark.parametrize(
    "field,value",
    (
        ("conclusion", "failure"),
        ("event", "pull_request"),
        ("head_branch", "feature"),
        ("path", ".github/workflows/other.yml"),
    ),
)
def test_workflow_run_rejects_wrong_or_failed_evidence(
    monkeypatch, field, value
) -> None:
    payload = {
        "status": "completed",
        "conclusion": "success",
        "event": "push",
        "head_branch": "main",
        "path": ".github/workflows/ci.yml",
        "name": "CI",
        "head_sha": "a" * 40,
        "html_url": "https://github.com/example/project/actions/runs/1",
    }
    payload[field] = value
    monkeypatch.setattr(cli, "_run", lambda *args: json.dumps(payload))
    with pytest.raises(ReleaseCandidateError, match="release-workflow-run-invalid"):
        cli._workflow_evidence("example/project", 1, ".github/workflows/ci.yml")


def test_rollback_run_is_verified_against_known_source(monkeypatch) -> None:
    source = "b" * 40
    payload = {
        "status": "completed",
        "conclusion": "success",
        "event": "workflow_dispatch",
        "head_branch": "main",
        "head_sha": source,
        "path": ".github/workflows/public-production-gate.yml",
        "html_url": "https://github.com/example/project/actions/runs/3",
    }
    monkeypatch.setattr(cli, "_run", lambda *args: json.dumps(payload))
    assert cli._rollback_run_url("example/project", 3, source).endswith("/3")

    payload["head_sha"] = "c" * 40
    with pytest.raises(ReleaseCandidateError, match="release-rollback-run-invalid"):
        cli._rollback_run_url("example/project", 3, source)
