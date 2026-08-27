from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

import scripts.validate_canonical_timeline_review_packet as validator


def _episode(number: int) -> dict[str, str]:
    return {
        "storyId": f"EVT_TEST_STORY_{number:02d}",
        "episodeId": f"EVT_TEST_STORY_{number:02d}_E01",
        "storyCategory": "EVT",
    }


def _provenance(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "candidateId": "TEST_CANDIDATE_001",
        "sourceEpisode": _episode(1),
        "targetEpisode": _episode(2),
        "observedRelation": "before",
        "evidenceIds": ["TEST_EVIDENCE_001"],
        "sourceType": "manual",
        "confidence": 1.0,
        "extractionRun": {
            "extractionVersion": "test-0.1",
            "extractionMethod": "manual",
            "modelProvider": None,
            "modelName": None,
            "promptVersion": None,
            "extractedAt": "2099-01-01T00:00:00Z",
            "parserCompatibilityAtExtraction": "compatible",
        },
    }
    value.update(overrides)
    return value


def _decision(summary: str = "Synthetic evidence summary.") -> dict[str, object]:
    return {
        "reviewer": "TEST_REVIEWER",
        "decidedAt": "2099-01-02T00:00:00Z",
        "evidenceSummary": summary,
        "notes": None,
    }


def _edge(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "reviewEdgeKey": "edge-0001",
        "from": _episode(1),
        "to": _episode(2),
        "relationState": "before",
        "stateReason": None,
        "reviewStatus": "pending",
        "candidateProvenance": [_provenance()],
        "humanDecision": None,
    }
    value.update(overrides)
    return value


def _packet(*edges: dict[str, object], **overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_review_packet",
        "packetId": "ctrp-20990101T000000Z-deadbeef",
        "reviewBatchId": "test-batch-001",
        "classification": "local_internal",
        "commitAllowed": False,
        "scopeStoryCategory": "EVT",
        "visibility": "internal_only",
        "createdAt": "2099-01-01T00:00:00Z",
        "storyPair": [
            {"storyId": "EVT_TEST_STORY_01", "storyCategory": "EVT"},
            {"storyId": "EVT_TEST_STORY_02", "storyCategory": "EVT"},
        ],
        "edges": list(edges) or [_edge()],
    }
    packet.update(overrides)
    return packet


def _packet_v2(*edges: dict[str, object], **overrides: object) -> dict[str, object]:
    packet = _packet(*edges)
    packet.update(
        {
            "schemaVersion": "0.2",
            "expiresAt": "2099-04-01T00:00:00Z",
        }
    )
    packet.update(overrides)
    return packet


def _completed(returncode: int, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


def _configure_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    packet_root = tmp_path / "workspace" / "review_packets" / "canonical_timeline"
    packet_root.mkdir(parents=True)
    monkeypatch.setattr(validator, "_PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(validator, "_PACKET_ROOT", packet_root)

    def fake_git(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["rev-parse", "--show-toplevel"]:
            return _completed(0, str(tmp_path))
        if args and args[0] == "check-ignore":
            return _completed(0)
        if args and args[0] == "ls-files":
            return _completed(0)
        raise AssertionError(args)

    monkeypatch.setattr(validator, "_run_git", fake_git)
    return packet_root


def _write_packet(
    root: Path, packet: object, name: str = "canonical_timeline_review_test.json"
) -> Path:
    path = root / name
    path.write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
    return path


def test_document_validation_is_offline_schema_and_semantic_read_only() -> None:
    packet = _packet()
    original = deepcopy(packet)
    result = validator.validate_packet_document(packet)
    assert result.is_valid
    assert result.edge_count == 1
    assert packet == original

    invalid = _packet(_edge(to=_episode(3)))
    result = validator.validate_packet_document(invalid)
    assert "canonical_timeline_review_edge_outside_story_pair" in result.issue_codes


def test_v02_retention_is_exact_and_expiration_is_warning_only() -> None:
    packet = _packet_v2()
    original = deepcopy(packet)
    current_time = datetime(2099, 4, 2, tzinfo=timezone.utc)

    result = validator.validate_packet_document(packet, current_time=current_time)
    assert result.is_valid
    assert result.warning_codes == ("canonical_timeline_review_packet_expired",)
    assert packet == original

    invalid = _packet_v2(expiresAt="2099-03-31T23:59:59Z")
    result = validator.validate_packet_document(
        invalid,
        current_time=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    assert result.issue_codes == ("canonical_timeline_review_retention_window_invalid",)


def test_review_brief_is_fixed_natural_language_without_internal_values() -> None:
    packet = _packet_v2(
        _edge(
            candidateProvenance=[
                _provenance(),
                _provenance(candidateId="TEST_CANDIDATE_002"),
            ]
        )
    )
    result = validator.validate_packet_document(
        packet,
        current_time=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    brief = validator.render_review_brief(result)

    assert "対象: 2つのEVENT story間の候補" in brief
    assert "確認対象: 1 edge" in brief
    assert "observations=2" in brief
    for forbidden in (
        "EVT_TEST",
        "TEST_CANDIDATE",
        "TEST_EVIDENCE",
        "sourcePath",
        "http://",
        "https://",
        ".dec",
    ):
        assert forbidden not in brief


@pytest.mark.parametrize(
    "text,code",
    (
        (r"C:\\private\\story.dec", "free-text-sensitive-content"),
        (r"see (C:\\private\\story.json)", "free-text-sensitive-content"),
        (r"see (\\server\share\story.json)", "free-text-sensitive-content"),
        ("see (/private/raw/story.json)", "free-text-sensitive-content"),
        ("see /tmp", "free-text-sensitive-content"),
        ("see https://example.test/evidence", "free-text-sensitive-content"),
        ("mentions EVT_TEST_STORY_01", "free-text-internal-id"),
        ("mentions TEST_CANDIDATE_001", "free-text-internal-id"),
        ("mentions TEST_EVIDENCE_001", "free-text-internal-id"),
    ),
)
def test_free_text_sensitive_values_return_fixed_codes(text: str, code: str) -> None:
    edge = _edge(
        reviewStatus="confirmed",
        humanDecision=_decision(text),
    )
    result = validator.validate_packet_document(_packet(edge))
    assert code in result.issue_codes


def test_reviewer_is_checked_and_short_ids_do_not_overmatch() -> None:
    edge = _edge(
        reviewStatus="confirmed",
        humanDecision={
            **_decision("Evidence remains a safe synthetic summary."),
            "reviewer": r"C:\private\reviewer.txt",
        },
    )
    result = validator.validate_packet_document(_packet(edge))
    assert "free-text-sensitive-content" in result.issue_codes

    packet = _packet()
    packet["edges"][0]["candidateProvenance"][0]["candidateId"] = "E"
    packet["edges"][0]["candidateProvenance"][0]["evidenceIds"] = ["Q"]
    assert validator.validate_packet_document(packet).is_valid


def test_cli_valid_is_aggregate_only_and_does_not_modify_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _configure_workspace(monkeypatch, tmp_path)
    path = _write_packet(root, _packet())
    before = path.read_bytes()
    before_stat = path.stat()

    assert validator.main(["--packet-name", path.name]) == 0
    captured = capsys.readouterr()
    assert "status=valid edges=1" in captured.out
    assert captured.err == ""
    assert "EVT_TEST" not in captured.out
    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == before_stat.st_mtime_ns


def test_cli_quiet_valid_has_no_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _configure_workspace(monkeypatch, tmp_path)
    path = _write_packet(root, _packet())
    assert validator.main(["--packet-name", path.name, "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_cli_expired_packet_returns_zero_warning_and_never_deletes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _configure_workspace(monkeypatch, tmp_path)
    packet = _packet_v2(
        createdAt="2000-01-01T00:00:00Z",
        expiresAt="2000-03-31T00:00:00Z",
    )
    path = _write_packet(root, packet)
    before = path.read_bytes()

    assert validator.main(["--packet-name", path.name, "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "canonical_timeline_review_packet_expired" in captured.err
    assert path.read_bytes() == before


def test_cli_can_render_anonymous_review_brief(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _configure_workspace(monkeypatch, tmp_path)
    path = _write_packet(root, _packet_v2())

    assert validator.main(["--packet-name", path.name, "--render-review-brief"]) == 0
    captured = capsys.readouterr()
    assert "Canonical Timeline レビュー概要" in captured.out
    assert "EVT_TEST" not in captured.out + captured.err


def test_cli_invalid_json_and_semantic_values_do_not_leak(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = _configure_workspace(monkeypatch, tmp_path)
    invalid_json = root / "canonical_timeline_review_invalid.json"
    invalid_json.write_text("{not json", encoding="utf-8")
    assert validator.main(["--packet-name", invalid_json.name]) == 1
    assert "packet-json-invalid" in capsys.readouterr().err

    path = _write_packet(root, _packet(_edge(to=_episode(3))))
    assert validator.main(["--packet-name", path.name]) == 1
    captured = capsys.readouterr()
    assert "canonical_timeline_review_edge_outside_story_pair" in captured.err
    assert "EVT_TEST_STORY_03" not in captured.err


@pytest.mark.parametrize(
    "name",
    (
        "../canonical_timeline_review_test.json",
        "canonical_timeline_review_TEST.json",
        "other.json",
        "canonical_timeline_review_test.yaml",
    ),
)
def test_cli_rejects_invalid_basename_with_config_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    name: str,
) -> None:
    _configure_workspace(monkeypatch, tmp_path)
    assert validator.main(["--packet-name", name]) == 2
    captured = capsys.readouterr()
    assert "packet-name-invalid" in captured.err
    assert name not in captured.err


def test_git_ignored_and_tracked_boundaries_are_blocking(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _configure_workspace(monkeypatch, tmp_path)
    path = _write_packet(root, _packet())

    def not_ignored(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[0] == "rev-parse":
            return _completed(0, str(tmp_path))
        if args[0] == "check-ignore":
            return _completed(1)
        return _completed(0)

    monkeypatch.setattr(validator, "_run_git", not_ignored)
    assert validator.main(["--packet-name", path.name]) == 2

    def tracked(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[0] == "rev-parse":
            return _completed(0, str(tmp_path))
        if args[0] == "check-ignore":
            return _completed(0)
        if args[0] == "ls-files":
            return _completed(0, "workspace/review_packets/test.json\n")
        raise AssertionError(args)

    monkeypatch.setattr(validator, "_run_git", tracked)
    assert validator.main(["--packet-name", path.name]) == 2


def test_symlink_leaf_is_rejected_before_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _configure_workspace(monkeypatch, tmp_path)
    target = _write_packet(root, _packet(), "canonical_timeline_review_target.json")
    link = root / "canonical_timeline_review_link.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink unavailable")
    assert validator.main(["--packet-name", link.name]) == 2


def test_reparse_ancestor_is_rejected_before_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = _configure_workspace(monkeypatch, tmp_path)
    path = _write_packet(root, _packet())
    actual_is_reparse = validator._is_reparse

    def fake_is_reparse(candidate: Path) -> bool:
        return candidate == root.parent or actual_is_reparse(candidate)

    monkeypatch.setattr(validator, "_is_reparse", fake_is_reparse)
    assert validator.main(["--packet-name", path.name]) == 2


def test_schema_invalid_and_bad_timestamp_return_invalid_not_config() -> None:
    packet = _packet()
    packet["visibility"] = "public"
    assert validator.validate_packet_document(packet).issue_codes == (
        "packet-schema-invalid",
    )

    packet = _packet()
    packet["createdAt"] = "not-a-date"
    assert validator.validate_packet_document(packet).issue_codes == (
        "packet-schema-invalid",
    )
