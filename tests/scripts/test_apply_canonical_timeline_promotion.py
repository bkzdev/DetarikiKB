"""Canonical Timeline promotion executorの合成CLIテスト。"""

from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import scripts.apply_canonical_timeline_promotion as executor
from agents.extractor.canonical_timeline_promotion_plan import (
    build_canonical_timeline_promotion_plan,
)


def _episode(number: int) -> dict[str, str]:
    story = f"EVT_TEST_STORY_{number:02d}"
    return {"storyId": story, "episodeId": f"{story}_E01", "storyCategory": "EVT"}


def _packet(start: int = 1, relation: str = "before") -> dict[str, object]:
    source, target = _episode(start), _episode(start + 1)
    return {
        "schemaVersion": "0.2",
        "documentType": "canonical_timeline_review_packet",
        "packetId": "ctrp-20990101T000000Z-deadbeef",
        "reviewBatchId": "test-batch",
        "classification": "local_internal",
        "commitAllowed": False,
        "scopeStoryCategory": "EVT",
        "visibility": "internal_only",
        "createdAt": "2099-01-01T00:00:00Z",
        "expiresAt": "2099-04-01T00:00:00Z",
        "storyPair": [
            {"storyId": source["storyId"], "storyCategory": "EVT"},
            {"storyId": target["storyId"], "storyCategory": "EVT"},
        ],
        "edges": [
            {
                "reviewEdgeKey": "edge-0001",
                "from": source,
                "to": target,
                "relationState": relation,
                "stateReason": None,
                "reviewStatus": "confirmed",
                "candidateProvenance": [
                    {
                        "candidateId": "TEST_CANDIDATE",
                        "sourceEpisode": deepcopy(source),
                        "targetEpisode": deepcopy(target),
                        "observedRelation": relation,
                        "evidenceIds": ["TEST_EVIDENCE"],
                        "sourceType": "manual",
                        "confidence": 1.0,
                        "extractionRun": {
                            "extractionVersion": "test",
                            "extractionMethod": "manual",
                            "modelProvider": None,
                            "modelName": None,
                            "promptVersion": None,
                            "extractedAt": "2099-01-01T00:00:00Z",
                            "parserCompatibilityAtExtraction": "compatible",
                        },
                    }
                ],
                "humanDecision": {
                    "reviewer": "TEST",
                    "decidedAt": "2099-01-02T00:00:00Z",
                    "evidenceSummary": "Synthetic summary.",
                    "notes": None,
                },
            }
        ],
    }


def _write(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _configure(monkeypatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(executor, "_PROJECT_ROOT", tmp_path)
    root = tmp_path / "workspace" / "canonical_timeline"
    monkeypatch.setattr(executor, "_WORKSPACE_ROOT", root)
    monkeypatch.setattr(executor, "_TARGET", root / "canonical_timeline.json")
    monkeypatch.setattr(executor, "_HISTORY", root / "history")
    monkeypatch.setattr(executor, "_PLAN_ROOT", root / "plans")
    monkeypatch.setattr(
        executor,
        "_PACKET_ROOT",
        tmp_path / "workspace" / "review_packets" / "canonical_timeline",
    )
    monkeypatch.setattr(executor, "_check_untracked", lambda *_args, **_kwargs: None)
    return root


def _inputs(
    tmp_path: Path, start: int = 1, relation: str = "before"
) -> tuple[Path, Path]:
    packet = _packet(start, relation)
    plan = build_canonical_timeline_promotion_plan(
        packet, created_at=datetime(2099, 1, 4, tzinfo=timezone.utc)
    )
    plan_path = executor._PLAN_ROOT / f"canonical_timeline_plan_{start}_{relation}.json"
    packet_path = (
        executor._PACKET_ROOT / f"canonical_timeline_packet_{start}_{relation}.json"
    )
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    _write(plan_path, plan)
    _write(packet_path, packet)
    return plan_path, packet_path


def _args(plan: Path, packet: Path) -> list[str]:
    return [
        "--plan-name",
        plan.name,
        "--packet-name",
        packet.name,
        "--expected-plan-sha256",
        hashlib.sha256(plan.read_bytes()).hexdigest(),
        "--expected-packet-sha256",
        hashlib.sha256(packet.read_bytes()).hexdigest(),
    ]


def test_fixed_root_input_boundary_rejects_names_tracking_and_reparse(  # noqa: C901
    monkeypatch, tmp_path
) -> None:
    root = tmp_path / "workspace" / "canonical_timeline" / "plans"
    root.mkdir(parents=True)
    input_path = root / "canonical_timeline_plan_ok.json"
    input_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(executor, "_PROJECT_ROOT", tmp_path)

    def git_ignored(args):
        if args[0] == "check-ignore":
            return subprocess.CompletedProcess([], 0, "", "")
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(executor, "_git", git_ignored)
    assert executor._safe_workspace_input(input_path.name, root) == input_path
    for unsafe in ("../canonical_timeline_plan_ok.json", str(input_path)):
        try:
            executor._safe_workspace_input(unsafe, root)
        except executor.PromotionError as exc:
            assert exc.code == "input-name-invalid"
        else:
            raise AssertionError("unsafe input name accepted")

    def git_tracked(args):
        if args[0] == "ls-files":
            return subprocess.CompletedProcess([], 0, "tracked\n", "")
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(executor, "_git", git_tracked)
    try:
        executor._safe_workspace_input(input_path.name, root)
    except executor.PromotionError as exc:
        assert exc.code == "tracked-path-rejected"
    else:
        raise AssertionError("tracked input accepted")

    monkeypatch.setattr(executor, "_git", git_ignored)
    monkeypatch.setattr(executor, "_is_reparse", lambda path: path == input_path)
    try:
        executor._safe_workspace_input(input_path.name, root)
    except executor.PromotionError as exc:
        assert exc.code == "reparse-point-rejected"
    else:
        raise AssertionError("reparse input accepted")


def test_dry_run_seed_writes_no_artifact(monkeypatch, tmp_path, capsys) -> None:
    root = _configure(monkeypatch, tmp_path)
    plan, packet = _inputs(tmp_path)
    assert executor.main(_args(plan, packet) + ["--create-seed"]) == 0
    assert not (root / "canonical_timeline.json").exists()
    output = capsys.readouterr().out
    assert (
        "status=dry_run plan_sha256=" in output
        and "packet_sha256=" in output
        and "current_artifact_sha256=none" in output
        and "proposed_artifact_sha256=" in output
    )
    assert "EVT_TEST_STORY" not in output
    assert str(plan) not in output


def test_expired_packet_is_warning_only(monkeypatch, tmp_path, capsys) -> None:
    _configure(monkeypatch, tmp_path)
    packet = _packet()
    packet["createdAt"] = "2000-01-01T00:00:00Z"
    packet["expiresAt"] = "2000-03-31T00:00:00Z"
    plan = build_canonical_timeline_promotion_plan(
        packet, created_at=datetime(2099, 1, 4, tzinfo=timezone.utc)
    )
    plan_path = executor._PLAN_ROOT / "canonical_timeline_plan_expired.json"
    packet_path = executor._PACKET_ROOT / "canonical_timeline_packet_expired.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    _write(plan_path, plan)
    _write(packet_path, packet)

    assert executor.main(_args(plan_path, packet_path) + ["--create-seed"]) == 0
    result = capsys.readouterr()
    assert "status=dry_run" in result.out
    assert "code=canonical_timeline_review_packet_expired" in result.err


def test_execute_rechecks_input_boundary_before_seed_publish(
    monkeypatch, tmp_path
) -> None:
    root = _configure(monkeypatch, tmp_path)
    plan, packet = _inputs(tmp_path)
    checks = {plan: 0, packet: 0}

    def reject_replaced_input(path: Path, **_kwargs) -> None:
        if path in checks:
            checks[path] += 1
            if checks[path] > 1:
                raise executor.PromotionError("reparse-point-rejected")

    monkeypatch.setattr(executor, "_check_untracked", reject_replaced_input)
    assert executor.main(_args(plan, packet) + ["--create-seed", "--execute"]) == 2
    assert not (root / "canonical_timeline.json").exists()


def test_seed_cleanup_failure_is_applied_warning(monkeypatch, tmp_path, capsys) -> None:
    root = _configure(monkeypatch, tmp_path)
    plan, packet = _inputs(tmp_path)
    original_unlink = Path.unlink

    def fail_seed_temp(path: Path, *args, **kwargs) -> None:
        if path.parent == root and path.name.startswith(".canonical_timeline.json."):
            raise OSError("synthetic seed cleanup failure")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_seed_temp)
    assert executor.main(_args(plan, packet) + ["--create-seed", "--execute"]) == 0
    result = capsys.readouterr()
    assert "status=written" in result.out
    assert "code=seed-applied-temporary-cleanup-failed" in result.err
    assert (root / "canonical_timeline.json").is_file()


def test_seed_no_clobber_and_update_snapshot(monkeypatch, tmp_path, capsys) -> None:
    root = _configure(monkeypatch, tmp_path)
    plan, packet = _inputs(tmp_path)
    base = _args(plan, packet) + ["--create-seed", "--execute"]
    assert executor.main(base) == 0
    old = (root / "canonical_timeline.json").read_bytes()
    assert executor.main(base) == 2
    digest = hashlib.sha256(old).hexdigest()
    next_plan, next_packet = _inputs(tmp_path, 2)
    dry_run = _args(next_plan, next_packet)
    assert executor.main(dry_run) == 0
    output = capsys.readouterr().out
    assert f"current_artifact_sha256={digest}" in output
    assert "proposed_artifact_sha256=" in output
    assert "EVT_TEST_STORY" not in output
    assert (
        executor.main(dry_run + ["--execute", "--expected-artifact-sha256", "0" * 64])
        == 2
    )
    assert (root / "canonical_timeline.json").read_bytes() == old
    assert not list((root / "history").glob("*.json"))
    assert (
        executor.main(
            _args(next_plan, next_packet)
            + ["--execute", "--expected-artifact-sha256", digest]
        )
        == 0
    )
    assert (root / "history" / f"{digest}.json").read_bytes() == old


def test_preflight_blocked_and_replace_failure_preserve_artifact(
    monkeypatch, tmp_path
) -> None:
    root = _configure(monkeypatch, tmp_path)
    plan, packet = _inputs(tmp_path)
    assert executor.main(_args(plan, packet) + ["--create-seed", "--execute"]) == 0
    old = (root / "canonical_timeline.json").read_bytes()
    digest = hashlib.sha256(old).hexdigest()
    blocked_plan, blocked_packet = _inputs(tmp_path, 1, "after")
    assert executor.main(_args(blocked_plan, blocked_packet)) == 2
    assert (root / "canonical_timeline.json").read_bytes() == old

    next_plan, next_packet = _inputs(tmp_path, 2)

    def fail_replace(*_args) -> None:
        raise OSError("synthetic")

    monkeypatch.setattr(executor.os, "replace", fail_replace)
    assert (
        executor.main(
            _args(next_plan, next_packet)
            + ["--execute", "--expected-artifact-sha256", digest]
        )
        == 2
    )
    assert (root / "canonical_timeline.json").read_bytes() == old
    assert (root / "history" / f"{digest}.json").read_bytes() == old
    assert not (root / ".canonical_timeline.lock").exists()
    assert not list(root.glob(".canonical_timeline.json.*.tmp"))


def test_stale_lock_rejects_update_without_changing_artifact(
    monkeypatch, tmp_path
) -> None:
    root = _configure(monkeypatch, tmp_path)
    plan, packet = _inputs(tmp_path)
    assert executor.main(_args(plan, packet) + ["--create-seed", "--execute"]) == 0
    old = (root / "canonical_timeline.json").read_bytes()
    digest = hashlib.sha256(old).hexdigest()
    (root / ".canonical_timeline.lock").write_bytes(b"other-owner")
    next_plan, next_packet = _inputs(tmp_path, 2)
    assert (
        executor.main(
            _args(next_plan, next_packet)
            + ["--execute", "--expected-artifact-sha256", digest]
        )
        == 2
    )
    assert (root / "canonical_timeline.json").read_bytes() == old
    assert (root / ".canonical_timeline.lock").read_bytes() == b"other-owner"


def test_post_replace_temporary_cleanup_failure_is_warning(
    monkeypatch, tmp_path, capsys
) -> None:
    root = _configure(monkeypatch, tmp_path)
    plan, packet = _inputs(tmp_path)
    assert executor.main(_args(plan, packet) + ["--create-seed", "--execute"]) == 0
    old = (root / "canonical_timeline.json").read_bytes()
    digest = hashlib.sha256(old).hexdigest()
    next_plan, next_packet = _inputs(tmp_path, 2)
    original_unlink = Path.unlink

    def fail_replaced_temp(path: Path, *args, **kwargs) -> None:
        if path.parent == root and path.name.startswith(".canonical_timeline.json."):
            raise OSError("synthetic post-replace cleanup failure")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_replaced_temp)
    assert (
        executor.main(
            _args(next_plan, next_packet)
            + ["--execute", "--expected-artifact-sha256", digest]
        )
        == 0
    )
    result = capsys.readouterr()
    assert "status=written" in result.out
    assert "code=update-applied-temporary-cleanup-failed" in result.err
    assert (root / "canonical_timeline.json").read_bytes() != old
    assert (root / "history" / f"{digest}.json").read_bytes() == old


def test_invalid_input_does_not_leak_input_path(monkeypatch, tmp_path, capsys) -> None:
    _configure(monkeypatch, tmp_path)
    plan, packet = _inputs(tmp_path)
    plan.write_text("{}", encoding="utf-8")
    assert executor.main(_args(plan, packet) + ["--create-seed"]) == 2
    output = capsys.readouterr().err
    assert "plan-schema-invalid" in output
    assert str(plan) not in output
