#!/usr/bin/env python3
"""main上の同一revisionからv1 release rehearsal recordを生成する。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.release_candidate import (  # noqa: E402
    ReleaseCandidateError,
    build_release_candidate_record,
)
from agents.wiki_generator.public_site_manifest import (  # noqa: E402
    build_public_site_manifest,
)

_SCHEMA_ROOT = _PROJECT_ROOT / "schemas"
_DRY_RUN_ROOT = (_PROJECT_ROOT / "workspace" / "dry_runs").resolve()
_PUBLIC_INPUT = (
    _PROJECT_ROOT / "knowledge/public/timelines/canonical_timeline_public_input.json"
)
_ROLLBACK_RECORD = _PROJECT_ROOT / "config/public_rollback.json"
_ROLLBACK_SCHEMA = _PROJECT_ROOT / "schemas/public_rollback_record.schema.json"
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="mainの同一revisionへM2-M4・public build・CI証跡を束縛します"
    )
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--normalization-report", required=True)
    parser.add_argument("--knowledge-report", required=True)
    parser.add_argument("--curation-report", required=True)
    parser.add_argument("--ci-run-id", required=True, type=int)
    parser.add_argument("--public-build-run-id", required=True, type=int)
    parser.add_argument("--validated-at", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repository")
    parser.add_argument("--quiet", "-q", action="store_true")
    return parser.parse_args(argv)


def _run(*arguments: str) -> str:
    try:
        result = subprocess.run(
            list(arguments),
            cwd=_PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise ReleaseCandidateError("release-command-unavailable") from exc
    if result.returncode != 0:
        raise ReleaseCandidateError("release-command-failed")
    return result.stdout.strip()


def _check_git(candidate_sha: str) -> None:
    _run(
        "git",
        "fetch",
        "--quiet",
        "--no-tags",
        "origin",
        "refs/heads/main:refs/remotes/origin/main",
    )
    if _run("git", "status", "--porcelain"):
        raise ReleaseCandidateError("release-worktree-dirty")
    if _run("git", "branch", "--show-current") != "main":
        raise ReleaseCandidateError("release-branch-not-main")
    if _run("git", "rev-parse", "HEAD") != candidate_sha:
        raise ReleaseCandidateError("release-candidate-not-head")
    if _run("git", "rev-parse", "origin/main") != candidate_sha:
        raise ReleaseCandidateError("release-candidate-not-origin-main")


def _repository(explicit: str | None) -> str:
    remote = _run("git", "remote", "get-url", "origin")
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?",
        remote,
    )
    if match is None:
        raise ReleaseCandidateError("release-repository-invalid")
    origin_repository = match.group(1)
    if explicit is not None and explicit != origin_repository:
        raise ReleaseCandidateError("release-repository-mismatch")
    payload = json.loads(_run("gh", "repo", "view", "--json", "nameWithOwner"))
    value = payload.get("nameWithOwner") if isinstance(payload, dict) else None
    if (
        not isinstance(value, str)
        or _REPOSITORY.fullmatch(value) is None
        or value != origin_repository
    ):
        raise ReleaseCandidateError("release-repository-invalid")
    return value


def _public_url(repository: str) -> str:
    owner, name = repository.split("/", maxsplit=1)
    return f"https://{owner.lower()}.github.io/{name}/"


def _rollback_record(repository: str) -> tuple[dict[str, Any], str]:
    record, _ = _load(str(_ROLLBACK_RECORD))
    schema, _ = _load(str(_ROLLBACK_SCHEMA))
    if list(Draft7Validator(schema).iter_errors(record)):
        raise ReleaseCandidateError("release-rollback-record-invalid")
    if record["publicUrl"] != _public_url(repository):
        raise ReleaseCandidateError("release-rollback-record-invalid")
    run_url = _rollback_run_url(repository, record["runId"], record["sourceSha"])
    return record, run_url


def _build_public_manifests(
    candidate_sha: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="dkb-release-candidate-") as temporary:
        root = Path(temporary) / "build"
        _run(
            "uv",
            "run",
            "python",
            "scripts/prepare_public_build.py",
            "--public-input",
            str(_PUBLIC_INPUT),
            "--output-root",
            str(root),
        )
        _run(
            "uv",
            "run",
            "mkdocs",
            "build",
            "--strict",
            "--config-file",
            str(root / "mkdocs-public.yml"),
        )
        _run(
            "uv",
            "run",
            "zensical",
            "build",
            "--strict",
            "--clean",
            "-f",
            str(root / "zensical-public.yml"),
        )
        shared = {
            "source_sha": candidate_sha,
            "lock_bytes": (_PROJECT_ROOT / "uv.lock").read_bytes(),
            "public_input_bytes": _PUBLIC_INPUT.read_bytes(),
        }
        mkdocs = build_public_site_manifest(
            root / "site-mkdocs",
            generator_name="mkdocs-material",
            generator_version=version("mkdocs-material"),
            config_bytes=(root / "mkdocs-public.yml").read_bytes(),
            **shared,
        )
        zensical = build_public_site_manifest(
            root / "site-zensical",
            generator_name="zensical",
            generator_version=version("zensical"),
            config_bytes=(root / "zensical-public.yml").read_bytes(),
            **shared,
        )
    return mkdocs, zensical


def _workflow_evidence(
    repository: str, run_id: int, expected_path: str
) -> dict[str, Any]:
    payload = json.loads(_run("gh", "api", f"repos/{repository}/actions/runs/{run_id}"))
    if not isinstance(payload, dict) or (
        payload.get("status") != "completed"
        or payload.get("conclusion") != "success"
        or payload.get("event") != "push"
        or payload.get("head_branch") != "main"
        or payload.get("path") != expected_path
    ):
        raise ReleaseCandidateError("release-workflow-run-invalid")
    return {
        "workflow": payload.get("name"),
        "headSha": payload.get("head_sha"),
        "conclusion": payload.get("conclusion"),
        "runUrl": payload.get("html_url"),
    }


def _rollback_run_url(repository: str, run_id: int, source_sha: str) -> str:
    payload = json.loads(_run("gh", "api", f"repos/{repository}/actions/runs/{run_id}"))
    if not isinstance(payload, dict) or (
        payload.get("status") != "completed"
        or payload.get("conclusion") != "success"
        or payload.get("event") != "workflow_dispatch"
        or payload.get("head_branch") != "main"
        or payload.get("head_sha") != source_sha
        or payload.get("path") != ".github/workflows/public-production-gate.yml"
    ):
        raise ReleaseCandidateError("release-rollback-run-invalid")
    url = payload.get("html_url")
    if not isinstance(url, str):
        raise ReleaseCandidateError("release-rollback-run-invalid")
    return url


def _load(path: str) -> tuple[dict[str, Any], bytes]:
    try:
        payload = Path(path).read_bytes()
        document = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseCandidateError("release-input-invalid") from exc
    if not isinstance(document, dict):
        raise ReleaseCandidateError("release-input-invalid")
    return document, payload


def _output(raw: str) -> Path:
    output = Path(raw).resolve()
    try:
        output.relative_to(_DRY_RUN_ROOT)
    except ValueError as exc:
        raise ReleaseCandidateError("release-output-outside-workspace") from exc
    if output.exists():
        raise ReleaseCandidateError("release-output-exists")
    return output


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        output = _output(args.output)
        _check_git(args.candidate_sha)
        repository = _repository(args.repository)
        rollback, rollback_run_url = _rollback_record(repository)
        normalization, normalization_bytes = _load(args.normalization_report)
        knowledge, knowledge_bytes = _load(args.knowledge_report)
        curation, curation_bytes = _load(args.curation_report)
        mkdocs, zensical = _build_public_manifests(args.candidate_sha)
        record = build_release_candidate_record(
            candidate_sha=args.candidate_sha,
            lock_bytes=(_PROJECT_ROOT / "uv.lock").read_bytes(),
            public_input_bytes=_PUBLIC_INPUT.read_bytes(),
            normalization_report=normalization,
            normalization_report_bytes=normalization_bytes,
            knowledge_report=knowledge,
            knowledge_report_bytes=knowledge_bytes,
            curation_report=curation,
            curation_report_bytes=curation_bytes,
            mkdocs_manifest=mkdocs,
            zensical_manifest=zensical,
            main_ci=_workflow_evidence(
                repository, args.ci_run_id, ".github/workflows/ci.yml"
            ),
            public_build=_workflow_evidence(
                repository,
                args.public_build_run_id,
                ".github/workflows/public-build.yml",
            ),
            rollback_source_sha=rollback["sourceSha"],
            rollback_tree_sha256=rollback["treeSha256"],
            rollback_run_url=rollback_run_url,
            public_url=rollback["publicUrl"],
            validated_at=args.validated_at,
            schema_root=_SCHEMA_ROOT,
        )
        _check_git(args.candidate_sha)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as destination:
            json.dump(record, destination, ensure_ascii=False, indent=2, sort_keys=True)
            destination.write("\n")
    except (ReleaseCandidateError, OSError, json.JSONDecodeError) as exc:
        code = (
            exc.code
            if isinstance(exc, ReleaseCandidateError)
            else "release-input-invalid"
        )
        print(f"status=blocked code={code}", file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"status=rehearsal_complete output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
