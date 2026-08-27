"""Canonical Timeline review packet builder CLIの合成fixtureテスト。"""

from __future__ import annotations

import copy
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

import scripts.build_canonical_timeline_review_packet as builder
import scripts.validate_canonical_timeline_review_packet as validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "extraction"
    / "minimal_episode_extraction.json"
)


def _candidate(episode_id: str, relative_to: str) -> dict[str, Any]:
    extraction_run = {
        "extractionVersion": "0.1.0",
        "extractionMethod": "rule_based",
        "modelProvider": None,
        "modelName": None,
        "promptVersion": None,
        "extractedAt": None,
        "parserCompatibilityAtExtraction": "compatible",
    }
    return {
        "id": f"{episode_id}_CAND_TL001",
        "type": "timeline_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": [f"{episode_id}_DLG0001"],
        "extractionRun": extraction_run,
        "kind": "relative_order",
        "scope": "episode",
        "relativeTo": relative_to,
        "relation": "before",
        "sourceTimelineId": None,
        "nameCandidates": [],
        "sceneRefs": [],
        "orderValue": None,
        "orderField": None,
        "markerType": None,
        "fields": {},
    }


def _document(
    story_id: str,
    episode_id: str,
    relative_to: str | None = None,
) -> dict[str, Any]:
    document = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    document["episodeId"] = episode_id
    document["storyId"] = story_id
    document["storyCategory"] = "EVT"
    document["characters"] = []
    document["extractionRun"] = {
        "extractionVersion": "0.1.0",
        "extractionMethod": "rule_based",
        "modelProvider": None,
        "modelName": None,
        "promptVersion": None,
        "extractedAt": None,
        "parserCompatibilityAtExtraction": "compatible",
    }
    evidence_id = f"{episode_id}_DLG0001"
    document["evidenceIndex"] = {
        evidence_id: {
            "sourceId": evidence_id,
            "storyId": story_id,
            "episodeId": episode_id,
            "sceneId": f"{episode_id}_SC001",
            "confidence": 0.9,
        }
    }
    document["timelineCandidates"] = (
        [_candidate(episode_id, relative_to)] if relative_to else []
    )
    return document


def _write(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


def _completed(returncode: int, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


@pytest.fixture
def configured_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    packet_root = tmp_path / "workspace" / "review_packets" / "canonical_timeline"
    monkeypatch.setattr(validator, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(validator, "_PACKET_ROOT", packet_root)
    monkeypatch.setattr(
        builder,
        "_utc_now",
        lambda: datetime(2099, 1, 1, tzinfo=timezone.utc),
    )

    def fake_git(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["rev-parse", "--show-toplevel"]:
            return _completed(0, str(tmp_path))
        if args and args[0] in {"check-ignore", "ls-files"}:
            return _completed(0)
        raise AssertionError(args)

    monkeypatch.setattr(validator, "_run_git", fake_git)
    return packet_root


def _args(input_dir: Path, *, execute: bool = False) -> list[str]:
    args = [
        "--input",
        str(input_dir),
        "--story-pair-index",
        "1",
        "--packet-name",
        "canonical_timeline_review_test.json",
        "--review-batch-id",
        "test-batch-001",
    ]
    if execute:
        args.append("--execute")
    return args


def _write_pair(input_dir: Path) -> None:
    _write(
        input_dir / "source.json",
        _document("EVT_TEST_A", "TEST_A_E01", "TEST_B_E01"),
    )
    _write(
        input_dir / "target.json",
        _document("EVT_TEST_B", "TEST_B_E01"),
    )


def test_cli_is_dry_run_by_default_and_execute_publishes_valid_packet(
    configured_workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir = tmp_path / "inputs"
    _write_pair(input_dir)
    target = configured_workspace / "canonical_timeline_review_test.json"

    assert builder.main(_args(input_dir)) == 0
    dry_run_output = capsys.readouterr()
    assert "status=dry_run" in dry_run_output.out
    assert not target.exists()

    assert builder.main(_args(input_dir, execute=True)) == 0
    execute_output = capsys.readouterr()
    assert "status=written" in execute_output.out
    packet = json.loads(target.read_text(encoding="utf-8"))
    result = validator.validate_packet_document(
        packet,
        current_time=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    assert result.is_valid and not result.warning_codes
    assert packet["expiresAt"] == "2099-04-01T00:00:00Z"
    combined = dry_run_output.out + execute_output.out
    assert "EVT_TEST" not in combined
    assert str(input_dir) not in combined
    assert str(target) not in combined


def test_cli_no_clobber_preserves_existing_packet(
    configured_workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir = tmp_path / "inputs"
    _write_pair(input_dir)
    assert builder.main(_args(input_dir, execute=True)) == 0
    capsys.readouterr()
    target = configured_workspace / "canonical_timeline_review_test.json"
    before = target.read_bytes()

    assert builder.main(_args(input_dir, execute=True)) == 2
    captured = capsys.readouterr()
    assert "packet-target-unavailable" in captured.err
    assert target.read_bytes() == before


def test_cli_fails_closed_for_invalid_input_or_unavailable_pair(
    configured_workspace: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir = tmp_path / "invalid"
    invalid = copy.deepcopy(_document("EVT_TEST_A", "TEST_A_E01"))
    del invalid["documentType"]
    _write(input_dir / "invalid.json", invalid)

    assert builder.main(_args(input_dir, execute=True)) == 1
    captured = capsys.readouterr()
    assert "status=invalid_input" in captured.err
    assert not configured_workspace.exists()

    empty_dir = tmp_path / "empty-candidate"
    _write(empty_dir / "valid.json", _document("EVT_TEST_A", "TEST_A_E01"))
    assert builder.main(_args(empty_dir, execute=True)) == 1
    captured = capsys.readouterr()
    assert "story-pair-index-unavailable" in captured.err
    assert "story_pairs=0" in captured.err
    assert not configured_workspace.exists()


def test_cli_atomic_failure_leaves_no_packet_or_temporary_file(
    configured_workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir = tmp_path / "inputs"
    _write_pair(input_dir)

    def fail_link(_source: Path, _target: Path) -> None:
        raise OSError("synthetic link failure")

    monkeypatch.setattr(builder.os, "link", fail_link)
    assert builder.main(_args(input_dir, execute=True)) == 2
    captured = capsys.readouterr()
    assert "atomic-publish-failed" in captured.err
    assert not (configured_workspace / "canonical_timeline_review_test.json").exists()
    assert list(configured_workspace.glob(".*.tmp")) == []


def test_cli_rejects_input_when_repository_boundary_cannot_be_verified(
    configured_workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir = tmp_path / "inputs"
    _write_pair(input_dir)

    def reject_input(_path: Path) -> None:
        raise validator.ConfigError("reparse-point-rejected")

    monkeypatch.setattr(validator, "check_repository_input", reject_input)
    assert builder.main(_args(input_dir, execute=True)) == 2
    captured = capsys.readouterr()
    assert "reparse-point-rejected" in captured.err
    assert not configured_workspace.exists()


def test_cli_rechecks_publish_boundary_before_link_and_cleanup(
    configured_workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir = tmp_path / "inputs"
    _write_pair(input_dir)
    actual_packet_path = validator.packet_path
    call_count = 0

    def changing_boundary(packet_name: str) -> Path:
        nonlocal call_count
        call_count += 1
        if call_count == 4:
            raise validator.ConfigError("reparse-point-rejected")
        return actual_packet_path(packet_name)

    monkeypatch.setattr(validator, "packet_path", changing_boundary)
    assert builder.main(_args(input_dir, execute=True)) == 2
    captured = capsys.readouterr()
    assert "reparse-point-rejected" in captured.err
    assert call_count == 5
    assert not (configured_workspace / "canonical_timeline_review_test.json").exists()
    assert list(configured_workspace.glob(".*.tmp")) == []


def test_cli_does_not_delete_a_preexisting_temporary_name(
    configured_workspace: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir = tmp_path / "inputs"
    _write_pair(input_dir)
    configured_workspace.mkdir(parents=True)
    monkeypatch.setattr(builder.secrets, "token_hex", lambda _size: "reserved")
    temporary = (
        configured_workspace / ".canonical_timeline_review_test.json.reserved.tmp"
    )
    temporary.write_text("preexisting", encoding="utf-8")

    assert builder.main(_args(input_dir, execute=True)) == 2
    captured = capsys.readouterr()
    assert "packet-target-unavailable" in captured.err
    assert temporary.read_text(encoding="utf-8") == "preexisting"
