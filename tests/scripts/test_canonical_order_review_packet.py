"""Canonical order review packetの生成・検証を合成データだけで確認する。"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
BUILDER_PATH = PROJECT_ROOT / "scripts" / "build_canonical_order_review_packet.py"
VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "validate_canonical_order_review_packet.py"
FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "canonical_order_review_packet"
    / "synthetic_manifest.yaml"
)
PACKET_ROOT = PROJECT_ROOT / "workspace" / "review_packets" / "canonical_order"
PACKET_NAME = "canonical_order_review_synthetic_cli.yaml"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = _load_module("canonical_order_packet_validator", VALIDATOR_PATH)
builder = _load_module("canonical_order_packet_builder", BUILDER_PATH)


def _manifest() -> tuple[dict, bytes]:
    payload = FIXTURE_PATH.read_bytes()
    return yaml.safe_load(payload.decode("utf-8")), payload


def _packet() -> dict:
    manifest, payload = _manifest()
    return builder.build_packet(
        manifest,
        payload,
        story_index=1,
        review_batch_id="canonical-order-review-synthetic",
        created_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        retention_days=14,
    )


def _run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@pytest.fixture
def clean_cli_packet():
    path = PACKET_ROOT / PACKET_NAME
    if path.exists():
        path.unlink()
    try:
        yield path
    finally:
        if path.exists():
            path.unlink()


def test_packet_schema_is_valid_draft7():
    schema_path = PROJECT_ROOT / "schemas" / "canonical_order_review_packet.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)


def test_builder_creates_one_story_pending_packet_without_raw_location_copy():
    packet = _packet()

    assert packet["classification"] == "local_internal"
    assert packet["commitAllowed"] is False
    assert packet["story"]["episodeCount"] == 2
    assert [entry["humanReviewStatus"] for entry in packet["episodes"]] == [
        "pending",
        "pending",
    ]
    assert packet["episodes"][1]["currentCanonicalOrder"] == 8
    serialized = yaml.safe_dump(packet, allow_unicode=True)
    assert "rawPath" not in serialized
    assert "sourceFileName" not in serialized
    assert "sourceKey" not in serialized
    assert ".dec" not in serialized
    assert validator.validate_packet_document(packet).is_valid


def test_builder_rejects_out_of_range_story_index_without_exposing_id():
    manifest, payload = _manifest()
    with pytest.raises(builder.ContentError) as caught:
        builder.build_packet(
            manifest,
            payload,
            story_index=2,
            review_batch_id="canonical-order-review-synthetic",
            created_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            retention_days=14,
        )
    assert caught.value.code == "story-index-out-of-range"
    assert "EVT_SYNTHETIC_REVIEW" not in str(caught.value)


def test_manifest_reparse_ancestor_is_rejected_before_read(
    monkeypatch: pytest.MonkeyPatch,
):
    original = builder.packet_validator._is_reparse

    def fixture_parent_is_reparse(path: Path) -> bool:
        if path.absolute() == FIXTURE_PATH.parent.absolute():
            return True
        return original(path)

    monkeypatch.setattr(
        builder.packet_validator, "_is_reparse", fixture_parent_is_reparse
    )

    with pytest.raises(builder.packet_validator.ConfigError) as caught:
        builder._load_manifest(FIXTURE_PATH)

    assert caught.value.code == "reparse-point-rejected"


def test_validator_rejects_candidate_without_source_and_evidence():
    packet = _packet()
    packet["episodes"][0]["candidateCanonicalOrder"] = 1

    result = validator.validate_packet_document(packet)

    assert result.issue_codes == ("packet-schema-invalid",)


def test_validator_rejects_confirmed_review_without_value_and_source():
    packet = _packet()
    packet["episodes"][0]["humanReviewStatus"] = "confirmed"

    result = validator.validate_packet_document(packet)

    assert result.issue_codes == ("packet-schema-invalid",)


def test_validator_allows_same_confirmed_order_for_multiple_episodes():
    packet = _packet()
    for episode in packet["episodes"]:
        episode["humanReviewStatus"] = "confirmed"
        episode["humanConfirmedCanonicalOrder"] = 5
        episode["humanConfirmedSource"] = {
            "sourceType": "manual",
            "confidence": None,
            "note": "Synthetic human review.",
        }

    result = validator.validate_packet_document(packet)

    assert result.is_valid
    assert result.confirmed_count == 2


def test_validator_rejects_expired_packet():
    packet = _packet()
    packet["createdAt"] = "2000-01-01T00:00:00Z"
    packet["expiresAt"] = "2000-01-15T00:00:00Z"

    result = validator.validate_packet_document(packet)

    assert result.issue_codes == ("packet-expired",)


@pytest.mark.parametrize(
    "unsafe_text",
    [
        r"C:\sensitive\source.dec",
        r"\\server\share\source",
        "/sensitive/local/source/file",
        "@SyntheticCommand",
        "$num1 was observed",
        "EVT_SYNTHETIC_REVIEW_E01 is earlier",
    ],
)
def test_validator_rejects_sensitive_free_text(unsafe_text: str):
    packet = _packet()
    packet["episodes"][0]["reviewerNotes"] = unsafe_text

    result = validator.validate_packet_document(packet)

    assert not result.is_valid
    assert set(result.issue_codes) & {
        "free-text-sensitive-content",
        "free-text-internal-id",
    }


def test_cli_builds_and_validates_packet_under_fixed_ignored_root(clean_cli_packet):
    build = _run(
        BUILDER_PATH,
        "--manifest",
        str(FIXTURE_PATH),
        "--story-index",
        "1",
        "--output-name",
        PACKET_NAME,
        "--review-batch-id",
        "canonical-order-review-synthetic",
    )
    assert build.returncode == 0, build.stderr
    assert clean_cli_packet.is_file()
    assert "EVT_SYNTHETIC_REVIEW" not in build.stdout + build.stderr
    assert "synthetic-episode1.dec" not in build.stdout + build.stderr

    validate = _run(VALIDATOR_PATH, "--packet-name", PACKET_NAME)
    assert validate.returncode == 0, validate.stderr
    assert "status=valid" in validate.stdout
    assert "EVT_SYNTHETIC_REVIEW" not in validate.stdout + validate.stderr


def test_cli_no_clobber_preserves_existing_packet(clean_cli_packet):
    clean_cli_packet.parent.mkdir(parents=True, exist_ok=True)
    clean_cli_packet.write_text("unchanged\n", encoding="utf-8")

    result = _run(
        BUILDER_PATH,
        "--manifest",
        str(FIXTURE_PATH),
        "--story-index",
        "1",
        "--output-name",
        PACKET_NAME,
        "--review-batch-id",
        "canonical-order-review-synthetic",
    )

    assert result.returncode == 2
    assert "packet-already-exists" in result.stderr
    assert clean_cli_packet.read_text(encoding="utf-8") == "unchanged\n"


def test_output_root_is_checked_before_creation_and_publish(
    clean_cli_packet, monkeypatch: pytest.MonkeyPatch
):
    events: list[tuple[str, Path]] = []
    original_check = builder.packet_validator._check_fixed_root
    original_mkdir = Path.mkdir

    def checked(path: Path) -> None:
        events.append(("check", path))
        original_check(path)

    def tracked_mkdir(path: Path, *args, **kwargs):
        if path == clean_cli_packet.parent:
            events.append(("mkdir", path))
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(builder.packet_validator, "_check_fixed_root", checked)
    monkeypatch.setattr(Path, "mkdir", tracked_mkdir)

    builder._write_no_clobber(clean_cli_packet, _packet())

    mkdir_position = events.index(("mkdir", clean_cli_packet.parent))
    assert ("check", clean_cli_packet) in events[:mkdir_position]
    assert sum(event == ("check", clean_cli_packet) for event in events) >= 3
    temporary_checks = [
        path
        for event, path in events
        if event == "check" and path.name.startswith(".tmp-")
    ]
    assert len(temporary_checks) >= 3


def test_output_reparse_ancestor_is_rejected_before_temporary_write(
    clean_cli_packet, monkeypatch: pytest.MonkeyPatch
):
    original = builder.packet_validator._is_reparse
    before = set(clean_cli_packet.parent.glob(".tmp-*.yaml"))

    def packet_root_is_reparse(path: Path) -> bool:
        if path.absolute() == clean_cli_packet.parent.absolute():
            return True
        return original(path)

    monkeypatch.setattr(builder.packet_validator, "_is_reparse", packet_root_is_reparse)

    with pytest.raises(builder.packet_validator.ConfigError) as caught:
        builder._write_no_clobber(clean_cli_packet, _packet())

    assert caught.value.code == "reparse-point-rejected"
    assert set(clean_cli_packet.parent.glob(".tmp-*.yaml")) == before


def test_validator_cli_does_not_echo_invalid_packet_contents(clean_cli_packet):
    clean_cli_packet.parent.mkdir(parents=True, exist_ok=True)
    marker = r"SENSITIVE C:\private\source.dec"
    packet = _packet()
    packet["episodes"][0]["reviewerNotes"] = marker
    clean_cli_packet.write_text(
        yaml.safe_dump(packet, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    result = _run(VALIDATOR_PATH, "--packet-name", PACKET_NAME)

    assert result.returncode == 1
    assert "free-text-sensitive-content" in result.stderr
    assert marker not in result.stdout + result.stderr


def test_packet_root_is_git_ignored():
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", "--", str(PACKET_ROOT)],
        cwd=PROJECT_ROOT,
        check=False,
    )
    assert result.returncode == 0
