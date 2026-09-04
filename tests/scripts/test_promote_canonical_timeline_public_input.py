"""Canonical Timeline public input promotion CLIの合成テスト。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import scripts.promote_canonical_timeline_public_input as promoter
from agents.extractor.canonical_timeline_public_input import canonical_json_sha256

PROJECT_ROOT = Path(__file__).parent.parent.parent
PROJECTION_FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "canonical_timeline_public_projection"
    / "valid_projection.json"
)
REQUIRES_SECURE_EXECUTE = pytest.mark.skipif(
    not promoter._secure_dir_fd_supported(),
    reason="secure dir-fd execute is unavailable on this platform",
)


def _projection() -> dict:
    return json.loads(PROJECTION_FIXTURE.read_text(encoding="utf-8"))


def _review(projection: dict, *, decision: str = "approved_for_build") -> dict:
    digest = canonical_json_sha256(projection)
    return {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_public_input_review",
        "classification": "local_internal",
        "commitAllowed": False,
        "decision": decision,
        "reviewedAt": "2099-01-01T00:00:00Z",
        "reviewerType": "human",
        "projectionSha256": digest,
        "preflightStatus": "clean",
        "preflightInputDigests": {
            "internalDocument": "1" * 64,
            "projection": digest,
            "publicEpisodeMapping": "2" * 64,
            "publicIdRegistry": "3" * 64,
            "publicLabelSource": "4" * 64,
        },
        "checks": {
            "projectionSchemaValid": True,
            "projectionSemanticsReviewed": True,
            "internalExposureClear": True,
            "visualReviewCompleted": True,
        },
    }


def _preflight(projection: dict) -> dict:
    digest = canonical_json_sha256(projection)
    return {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_public_preflight_record",
        "classification": "local_internal",
        "commitAllowed": False,
        "status": "clean",
        "publishStatus": "projection_candidate",
        "inputDigests": {
            "internalDocument": "1" * 64,
            "projection": digest,
            "publicEpisodeMapping": "2" * 64,
            "publicIdRegistry": "3" * 64,
            "publicLabelSource": "4" * 64,
        },
        "findings": [],
    }


def _configure(monkeypatch, tmp_path: Path) -> tuple[Path, list[str]]:
    root = tmp_path / "workspace" / "public_wiki_inputs"
    root.mkdir(parents=True)
    target = (
        tmp_path
        / "knowledge"
        / "public"
        / "timelines"
        / "canonical_timeline_public_input.json"
    )
    monkeypatch.setattr(promoter, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(promoter, "_WORKSPACE_ROOT", root)
    monkeypatch.setattr(promoter, "_TARGET", target)

    def git_ok(args):
        return subprocess.CompletedProcess(
            args, 1 if "--error-unmatch" in args else 0, "", ""
        )

    monkeypatch.setattr(promoter, "_git", git_ok)
    projection = _projection()
    values = {
        "canonical_timeline_public_projection_test.json": projection,
        "canonical_timeline_public_input_review_test.json": _review(projection),
        "canonical_timeline_public_preflight_test.json": _preflight(projection),
    }
    for name, value in values.items():
        (root / name).write_text(json.dumps(value), encoding="utf-8")
    args = [
        "--projection-name",
        "canonical_timeline_public_projection_test.json",
        "--review-name",
        "canonical_timeline_public_input_review_test.json",
        "--preflight-name",
        "canonical_timeline_public_preflight_test.json",
        "--expected-projection-sha256",
        canonical_json_sha256(projection),
    ]
    return target, args


def test_default_dry_run_writes_nothing(monkeypatch, tmp_path, capsys) -> None:
    target, args = _configure(monkeypatch, tmp_path)
    assert promoter.main(args) == 0
    assert not target.exists()
    output = capsys.readouterr().out
    assert "status=dry_run projection_sha256=" in output
    assert "PUBLIC_" not in output
    assert str(tmp_path) not in output


@REQUIRES_SECURE_EXECUTE
def test_execute_atomically_creates_valid_input_and_no_clobbers(
    monkeypatch, tmp_path, capsys
) -> None:
    target, args = _configure(monkeypatch, tmp_path)
    assert promoter.main(args + ["--execute"]) == 0
    document = json.loads(target.read_text(encoding="utf-8"))
    assert document["buildStatus"] == "approved_for_build"
    assert document["projection"]["publishStatus"] == "projection_candidate"

    assert promoter.main(args + ["--execute"]) == 1
    assert "code=target-exists" in capsys.readouterr().err


def test_digest_preflight_and_review_failures_write_nothing(
    monkeypatch, tmp_path
) -> None:
    target, args = _configure(monkeypatch, tmp_path)
    bad_args = args[:-1] + ["0" * 64]
    assert promoter.main(bad_args + ["--execute"]) == 1
    assert not target.exists()

    preflight = promoter._WORKSPACE_ROOT / args[5]
    preflight.write_text(
        json.dumps(
            {
                **_preflight(_projection()),
                "status": "blocked",
                "findings": [{"rule": "synthetic", "count": 1}],
            }
        ),
        encoding="utf-8",
    )
    assert promoter.main(args + ["--execute"]) == 1
    assert not target.exists()


def test_unsafe_name_and_tracked_input_are_rejected(monkeypatch, tmp_path) -> None:
    _target, args = _configure(monkeypatch, tmp_path)
    unsafe = args.copy()
    unsafe[1] = "../canonical_timeline_public_projection_test.json"
    assert promoter.main(unsafe) == 1

    def git_tracked(arguments):
        output = "tracked\n" if arguments[0] == "ls-files" else ""
        return subprocess.CompletedProcess(arguments, 0, output, "")

    monkeypatch.setattr(promoter, "_git", git_tracked)
    assert promoter.main(args) == 1


@REQUIRES_SECURE_EXECUTE
def test_execute_detects_input_change_before_publish(monkeypatch, tmp_path) -> None:
    target, args = _configure(monkeypatch, tmp_path)
    original = promoter._build
    calls = 0

    def changing_build(namespace):
        nonlocal calls
        calls += 1
        document, digest = original(namespace)
        if calls == 2:
            document["pushReview"]["reviewedAt"] = "2099-01-02T00:00:00Z"
        return document, digest

    monkeypatch.setattr(promoter, "_build", changing_build)
    assert promoter.main(args + ["--execute"]) == 1
    assert not target.exists()


@REQUIRES_SECURE_EXECUTE
def test_atomic_setup_failure_leaves_target_absent(monkeypatch, tmp_path) -> None:
    target, args = _configure(monkeypatch, tmp_path)

    def fail_write(*_args, **_kwargs):
        raise promoter.PublicInputError("temporary-file-unavailable")

    monkeypatch.setattr(promoter, "_write_temporary_file", fail_write)
    assert promoter.main(args + ["--execute"]) == 1
    assert not target.exists()


@REQUIRES_SECURE_EXECUTE
def test_tracked_target_is_rejected_even_when_worktree_file_is_absent(
    monkeypatch, tmp_path
) -> None:
    target, args = _configure(monkeypatch, tmp_path)

    def git_target_tracked(arguments):
        is_target = "--error-unmatch" in arguments
        return subprocess.CompletedProcess(
            arguments,
            0,
            "knowledge/public/timelines/input.json\n" if is_target else "",
            "",
        )

    monkeypatch.setattr(promoter, "_git", git_target_tracked)
    assert promoter.main(args + ["--execute"]) == 1
    assert not target.exists()


def test_mixed_preflight_input_digests_are_rejected(monkeypatch, tmp_path) -> None:
    target, args = _configure(monkeypatch, tmp_path)
    preflight = promoter._WORKSPACE_ROOT / args[5]
    value = json.loads(preflight.read_text(encoding="utf-8"))
    value["inputDigests"]["publicIdRegistry"] = "9" * 64
    preflight.write_text(json.dumps(value), encoding="utf-8")

    assert promoter.main(args + ["--execute"]) == 1
    assert not target.exists()


@REQUIRES_SECURE_EXECUTE
def test_post_write_corruption_is_removed(monkeypatch, tmp_path) -> None:
    target, args = _configure(monkeypatch, tmp_path)
    real_link = promoter.os.link

    def corrupt_after_link(source, destination, *arguments, **keywords):
        real_link(source, destination, *arguments, **keywords)
        target.write_bytes(b"{}\n")

    monkeypatch.setattr(promoter.os, "link", corrupt_after_link)
    assert promoter.main(args + ["--execute"]) == 1
    assert not target.exists()


@REQUIRES_SECURE_EXECUTE
def test_publish_uses_same_directory_descriptor_for_link(monkeypatch, tmp_path) -> None:
    target, args = _configure(monkeypatch, tmp_path)
    real_link = promoter.os.link
    observed = []

    def record_link(source, destination, *arguments, **keywords):
        observed.append((source, destination, keywords))
        return real_link(source, destination, *arguments, **keywords)

    monkeypatch.setattr(promoter.os, "link", record_link)
    assert promoter.main(args + ["--execute"]) == 0
    source, destination, keywords = observed[0]
    assert Path(source).name == source
    assert destination == target.name
    assert keywords["src_dir_fd"] == keywords["dst_dir_fd"]
    assert keywords["follow_symlinks"] is False


@REQUIRES_SECURE_EXECUTE
def test_cleanup_failure_is_reported_without_unlinking_unknown_file(
    monkeypatch, tmp_path, capsys
) -> None:
    target, args = _configure(monkeypatch, tmp_path)
    real_link = promoter.os.link
    real_unlink = promoter.os.unlink

    def corrupt_after_link(source, destination, *arguments, **keywords):
        real_link(source, destination, *arguments, **keywords)
        target.write_bytes(b"{}\n")

    def reject_target_cleanup(path, *arguments, **keywords):
        if path == target.name:
            raise OSError("synthetic cleanup failure")
        return real_unlink(path, *arguments, **keywords)

    monkeypatch.setattr(promoter.os, "link", corrupt_after_link)
    monkeypatch.setattr(promoter.os, "unlink", reject_target_cleanup)
    assert promoter.main(args + ["--execute"]) == 1
    assert "code=post-write-cleanup-failed" in capsys.readouterr().err
    assert target.exists()


def test_execute_fails_closed_without_secure_directory_api(
    monkeypatch, tmp_path, capsys
) -> None:
    target, args = _configure(monkeypatch, tmp_path)
    monkeypatch.setattr(promoter, "_secure_dir_fd_supported", lambda: False)
    assert promoter.main(args + ["--execute"]) == 1
    assert "code=secure-directory-api-unavailable" in capsys.readouterr().err
    assert not target.exists()
