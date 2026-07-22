"""Internal Review Evidence Packet generatorの合成入力テスト。

実DEC・実Normalized Story・実candidateは使わない。CLI成功時に作られる
bundleはstdoutのopaque packetIdから特定した1 directoryだけをcleanupし、
既存のworkspace rootを列挙・削除しない。
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts import generate_internal_review_evidence_packet as packet_generator

PROJECT_ROOT = Path(__file__).parent.parent.parent
GENERATOR_SCRIPT = (
    PROJECT_ROOT / "scripts" / "generate_internal_review_evidence_packet.py"
)
VALIDATOR_SCRIPT = (
    PROJECT_ROOT / "scripts" / "validate_internal_review_evidence_packet.py"
)
INPUT_FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "internal_review_evidence_packet"
    / "generator_input"
)
NORMALIZED_INPUT = INPUT_FIXTURE / "normalized" / "test_story.json"
PUBLIC_CANDIDATE = INPUT_FIXTURE / "public_candidate" / "test_public_safe.yaml"
PROJECTION_MAPPING = INPUT_FIXTURE / "projection_mapping" / "evidence-id-map.csv"
EXTRACTIONS = INPUT_FIXTURE / "extractions" / "test_episode_extraction.json"
REGISTRY = INPUT_FIXTURE / "registry" / "test_public_ids.yaml"
SELECTION_SOURCE = INPUT_FIXTURE / "selection" / "stage_then_dialogue.json"
PACKET_ROOT = PROJECT_ROOT / "workspace" / "review_packets" / "evidence"
SELECTION_ROOT = (
    PROJECT_ROOT / "workspace" / "local_inputs" / "evidence_packet_selection"
)
GENERATOR_INPUT_TEST_ROOT = (
    PROJECT_ROOT / "workspace" / "local_inputs" / "evidence_packet_generator_tests"
)
PACKET_ID_PATTERN = re.compile(r"erp-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}")
SENSITIVE_MARKERS = (
    "Synthetic dialogue text for packet review.",
    "Synthetic unknown diagnostic text.",
    "@SyntheticCommand",
    "TEST_PACKET_STORY",
    "C:\\secret\\synthetic.dec",
)


def _run_generator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GENERATOR_SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _base_args(
    *,
    normalized: Path = NORMALIZED_INPUT,
    candidate: Path = PUBLIC_CANDIDATE,
    mapping: Path = PROJECTION_MAPPING,
) -> list[str]:
    return [
        "--normalized-input",
        str(normalized),
        "--public-candidate",
        str(candidate),
        "--projection-mapping",
        str(mapping),
    ]


def _packet_id_from_output(result: subprocess.CompletedProcess[str]) -> str:
    match = PACKET_ID_PATTERN.search(result.stdout + result.stderr)
    assert match is not None, result.stdout + result.stderr
    return match.group(0)


def _load_packet(packet_id: str) -> tuple[Path, dict, list[dict], dict]:
    packet_dir = PACKET_ROOT / packet_id
    manifest = json.loads((packet_dir / "manifest.json").read_text(encoding="utf-8"))
    story = json.loads(
        (packet_dir / "stories" / "story-0001.json").read_text(encoding="utf-8")
    )
    with open(
        packet_dir / "mappings" / "evidence-id-map.csv", encoding="utf-8", newline=""
    ) as mapping_file:
        mapping_rows = list(csv.DictReader(mapping_file))
    report = json.loads(
        (packet_dir / "reports" / "validation.json").read_text(encoding="utf-8")
    )
    return packet_dir, manifest, mapping_rows, {"story": story, "report": report}


def _cleanup_packet(packet_id: str) -> None:
    packet_dir = PACKET_ROOT / packet_id
    if packet_dir.exists():
        shutil.rmtree(packet_dir)


def _assert_console_is_safe(result: subprocess.CompletedProcess[str]) -> None:
    output = result.stdout + result.stderr
    for marker in SENSITIVE_MARKERS:
        assert marker not in output


def _install_selection(filename: str) -> Path:
    destination = SELECTION_ROOT / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    shutil.copy2(SELECTION_SOURCE, destination)
    return destination


def _assert_no_temp_for(packet_id: str) -> None:
    assert not (PACKET_ROOT / f".tmp-{packet_id}").exists()


def _remove_local_input_dir(path: Path) -> None:
    """テストが作成した直下directoryだけを安全に削除する。"""
    root = GENERATOR_INPUT_TEST_ROOT.resolve()
    target = path.resolve()
    assert target.parent == root
    if path.exists():
        shutil.rmtree(path)


def _mapping_rows() -> list[dict[str, str]]:
    with open(PROJECTION_MAPPING, encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def _write_mapping(path: Path, rows: list[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def local_input_dir() -> Path:
    """repo内・ignored固定root直下のopaqueなテスト入力directory。"""
    directory = GENERATOR_INPUT_TEST_ROOT / f"test-{uuid.uuid4().hex}"
    directory.mkdir(parents=True, exist_ok=False)
    try:
        yield directory
    finally:
        _remove_local_input_dir(directory)


def test_public_candidate_generates_valid_packet_with_allowlisted_raw_content():
    result = _run_generator(*_base_args())
    assert result.returncode == 0, result.stderr
    _assert_console_is_safe(result)
    packet_id = _packet_id_from_output(result)
    try:
        packet_dir, manifest, mapping_rows, components = _load_packet(packet_id)
        story = components["story"]
        report = components["report"]

        assert packet_dir.is_dir()
        assert manifest["packetId"] == packet_id
        assert manifest["selectionMode"] == "public-candidate"
        assert manifest["commitAllowed"] is False
        assert manifest["retentionClass"] == "ephemeral"
        created = datetime.fromisoformat(manifest["createdAt"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(manifest["expiresAt"].replace("Z", "+00:00"))
        assert (expires - created).days == 14
        assert len(manifest["components"]) == 3
        assert all(
            len(component["sha256"]) == 64 for component in manifest["components"]
        )
        assert len(mapping_rows) == 2
        assert [row["evidenceId"] for row in mapping_rows] == [
            "TEST_PACKET_DIALOGUE",
            "TEST_PACKET_UNKNOWN",
        ]

        entries = story["entries"]
        assert len(entries) == 2
        entry = entries[0]
        assert entry["identifiers"]["internal"]["evidenceId"] == "TEST_PACKET_DIALOGUE"
        assert entry["rawContent"] == {
            "reason": "evidence-review",
            "text": "Synthetic dialogue text for packet review.",
            "rawCommand": None,
            "arguments": [],
        }
        assert entry["context"] == {"before": [], "after": []}
        unknown = entries[1]
        assert unknown["identifiers"]["internal"]["evidenceId"] == "TEST_PACKET_UNKNOWN"
        assert unknown["rawContent"]["text"] == "Synthetic unknown diagnostic text."
        assert report["status"] == "valid"
        assert report["errorCount"] == 0
        assert report["warningCount"] == 0

        validation = subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), "--packet-id", packet_id],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert validation.returncode == 0, validation.stderr
        _assert_console_is_safe(validation)
        _assert_no_temp_for(packet_id)
    finally:
        _cleanup_packet(packet_id)


def test_explicit_selection_uses_fixed_selection_root_and_mapping_input_order():
    filename = "test-packet-generator-stage-then-dialogue.json"
    selection_path = _install_selection(filename)
    result = _run_generator(*_base_args(), "--selection-file", filename)
    try:
        assert result.returncode == 0, result.stderr
        _assert_console_is_safe(result)
        packet_id = _packet_id_from_output(result)
        packet_dir, manifest, mapping_rows, components = _load_packet(packet_id)
        assert packet_dir.is_dir()
        assert manifest["selectionMode"] == "explicit-entry-list"
        # selection documentの順ではなく、projection mappingの元順を維持する。
        assert [row["evidenceId"] for row in mapping_rows] == [
            "TEST_PACKET_DIALOGUE",
            "TEST_PACKET_STAGE",
        ]
        entries = components["story"]["entries"]
        assert [
            entry["identifiers"]["internal"]["evidenceId"] for entry in entries
        ] == [
            "TEST_PACKET_DIALOGUE",
            "TEST_PACKET_STAGE",
        ]
        stage = entries[1]
        assert stage["evidenceType"] == "stage_direction"
        assert stage["rawContent"]["reason"] == "parser-diagnostic"
        assert stage["rawContent"]["rawCommand"] == "@SyntheticCommand"
        assert stage["rawContent"]["arguments"] == ["foreground", "fade"]
    finally:
        if "packet_id" in locals():
            _cleanup_packet(packet_id)
        if selection_path.exists():
            selection_path.unlink()


def test_optional_extraction_is_projected_to_limited_metadata_only():
    result = _run_generator(*_base_args(), "--extractions", str(EXTRACTIONS))
    assert result.returncode == 0, result.stderr
    packet_id = _packet_id_from_output(result)
    try:
        _, _, _, components = _load_packet(packet_id)
        extraction = components["story"]["entries"][0]["extraction"]
        assert extraction == {
            "candidates": [
                {
                    "candidateId": "TEST_PACKET_CANDIDATE",
                    "candidateType": "character_candidate",
                    "confidence": 0.9,
                }
            ]
        }
        serialized = json.dumps(extraction)
        assert "Synthetic Speaker" not in serialized
        assert "extractionRun" not in serialized
    finally:
        _cleanup_packet(packet_id)


def test_same_story_can_be_loaded_from_multiple_episode_documents(
    local_input_dir: Path,
):
    normalized_dir = local_input_dir / "normalized"
    normalized_dir.mkdir()
    first_normalized = json.loads(NORMALIZED_INPUT.read_text(encoding="utf-8"))
    replacements = {
        "TEST_PACKET_EPISODE": "TEST_PACKET_EPISODE_2",
        "TEST_PUBLIC_001_E01": "TEST_PUBLIC_001_E02",
        "TEST_PACKET_SCENE": "TEST_PACKET_SCENE_2",
        "TEST_PACKET_DIALOGUE": "TEST_PACKET_DIALOGUE_2",
        "TEST_PACKET_UNKNOWN": "TEST_PACKET_UNKNOWN_2",
        "TEST_PACKET_STAGE": "TEST_PACKET_STAGE_2",
    }
    serialized_second = json.dumps(first_normalized)
    for source, destination in replacements.items():
        serialized_second = serialized_second.replace(source, destination)
    second_normalized = json.loads(serialized_second)
    second_normalized["episodes"][0]["episodeNumber"] = 2
    (normalized_dir / "episode-1.json").write_text(
        json.dumps(first_normalized), encoding="utf-8"
    )
    (normalized_dir / "episode-2.json").write_text(
        json.dumps(second_normalized), encoding="utf-8"
    )

    candidate = yaml.safe_load(PUBLIC_CANDIDATE.read_text(encoding="utf-8"))
    serialized_entries = json.dumps(candidate["entries"])
    for source, destination in replacements.items():
        serialized_entries = serialized_entries.replace(source, destination)
    candidate["entries"].extend(json.loads(serialized_entries))
    candidate_path = local_input_dir / "candidate.yaml"
    candidate_path.write_text(
        yaml.safe_dump(candidate, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    mapping = _mapping_rows()
    second_mapping = []
    for original_row in mapping:
        row = dict(original_row)
        for name, value in row.items():
            for source, destination in replacements.items():
                value = value.replace(source, destination)
            row[name] = value
        row["episodeOrder"] = "2"
        second_mapping.append(row)
    mapping.extend(second_mapping)
    mapping_path = local_input_dir / "mapping.csv"
    _write_mapping(mapping_path, mapping)

    result = _run_generator(
        *_base_args(
            normalized=normalized_dir,
            candidate=candidate_path,
            mapping=mapping_path,
        )
    )
    assert result.returncode == 0, result.stderr
    packet_id = _packet_id_from_output(result)
    try:
        _, manifest, _, components = _load_packet(packet_id)
        assert manifest["sourceSnapshot"]["normalizedStoryFileCount"] == 2
        assert components["report"]["storyCount"] == 1
        assert [
            entry["identifiers"]["internal"]["episodeId"]
            for entry in components["story"]["entries"]
        ] == [
            "TEST_PACKET_EPISODE",
            "TEST_PACKET_EPISODE",
            "TEST_PACKET_EPISODE_2",
            "TEST_PACKET_EPISODE_2",
        ]
    finally:
        _cleanup_packet(packet_id)


@pytest.mark.parametrize(
    ("mutator", "expected_code"),
    [
        (
            lambda extraction: extraction.update({"evidenceIndex": {}}),
            "extraction-semantic-invalid",
        ),
        (
            lambda extraction: extraction["evidenceIndex"][
                "TEST_PACKET_DIALOGUE"
            ].update({"sceneId": "TEST_PACKET_OTHER_SCENE"}),
            "extraction-normalized-block-mismatch",
        ),
    ],
    ids=["missing-evidence-index", "normalized-scene-mismatch"],
)
def test_extraction_semantic_failures_are_blocking(
    local_input_dir: Path, mutator, expected_code: str
):
    extraction = json.loads(EXTRACTIONS.read_text(encoding="utf-8"))
    mutator(extraction)
    extraction_path = local_input_dir / "extraction.json"
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")

    result = _run_generator(
        *_base_args(), "--extractions", str(extraction_path), "--quiet"
    )
    assert result.returncode == 1
    assert f"code={expected_code}" in result.stderr
    _assert_console_is_safe(result)


@pytest.mark.parametrize(
    ("mutator", "expected_code"),
    [
        (
            lambda candidate, mapping: candidate["entries"][0].update(
                {"publicEvidenceId": "TEST_PUBLIC_001_E01_WRONG"}
            ),
            1,
        ),
        (
            lambda candidate, mapping: mapping.append(dict(mapping[0])),
            1,
        ),
        (
            lambda candidate, mapping: candidate["entries"][0].update(
                {"sceneId": "PUBLIC_SAFE_SCENE_SHOULD_BE_ABSENT"}
            ),
            1,
        ),
    ],
    ids=[
        "candidate-mapping-cross-mismatch",
        "duplicate-mapping-row",
        "candidate-is-not-public-safe-projection",
    ],
)
def test_cross_consistency_failures_do_not_create_final_packet(
    local_input_dir: Path, mutator, expected_code: int
):
    candidate_path = local_input_dir / "candidate.yaml"
    mapping_path = local_input_dir / "mapping.csv"
    candidate = yaml.safe_load(PUBLIC_CANDIDATE.read_text(encoding="utf-8"))
    mapping = _mapping_rows()
    mutator(candidate, mapping)
    candidate_path.write_text(
        yaml.safe_dump(candidate, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    _write_mapping(mapping_path, mapping)

    result = _run_generator(
        *_base_args(candidate=candidate_path, mapping=mapping_path), "--quiet"
    )
    assert result.returncode == expected_code
    _assert_console_is_safe(result)


def test_missing_explicit_selection_entry_fails_without_sensitive_console_output():
    filename = "test-packet-generator-missing-entry.json"
    selection_path = SELECTION_ROOT / filename
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(
        json.dumps({"selectionVersion": 1, "evidenceIds": ["TEST_PACKET_MISSING"]}),
        encoding="utf-8",
    )
    try:
        result = _run_generator(*_base_args(), "--selection-file", filename)
    finally:
        if selection_path.exists():
            selection_path.unlink()
    assert result.returncode == 1
    _assert_console_is_safe(result)


def test_registry_conflict_fails_without_creating_packet(local_input_dir: Path):
    registry_path = local_input_dir / "conflicting-registry.yaml"
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    registry["stories"][0]["episodes"][0]["publicEpisodeId"] = "TEST_PUBLIC_001_E99"
    registry_path.write_text(
        yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    result = _run_generator(*_base_args(), "--registry", str(registry_path))
    assert result.returncode == 1
    _assert_console_is_safe(result)


def test_registry_completed_mapping_matches_normalized_without_public_episode_id(
    local_input_dir: Path,
):
    normalized_path = local_input_dir / "normalized.json"
    mapping_path = local_input_dir / "mapping.csv"
    normalized = json.loads(NORMALIZED_INPUT.read_text(encoding="utf-8"))
    del normalized["episodes"][0]["metadata"]["publicEpisodeId"]
    normalized_path.write_text(json.dumps(normalized), encoding="utf-8")
    mapping = _mapping_rows()
    for row in mapping:
        row["publicEpisodeIdSource"] = "registry"
        row["registryMatched"] = "True"
        row["registryPublicEpisodeId"] = "TEST_PUBLIC_001_E01"
    _write_mapping(mapping_path, mapping)

    result = _run_generator(
        *_base_args(normalized=normalized_path, mapping=mapping_path),
        "--registry",
        str(REGISTRY),
    )
    assert result.returncode == 0, result.stderr
    packet_id = _packet_id_from_output(result)
    try:
        _, manifest, _, components = _load_packet(packet_id)
        assert manifest["sourceSnapshot"]["registryDigest"] is not None
        assert (
            components["story"]["entries"][0]["identifiers"]["public"][
                "publicEpisodeId"
            ]
            == "TEST_PUBLIC_001_E01"
        )
    finally:
        _cleanup_packet(packet_id)


def test_mapping_with_registry_metadata_requires_registry_input(local_input_dir: Path):
    mapping_path = local_input_dir / "mapping.csv"
    mapping = _mapping_rows()
    for row in mapping:
        row["publicEpisodeIdSource"] = "registry"
        row["registryMatched"] = "True"
        row["registryPublicEpisodeId"] = "TEST_PUBLIC_001_E01"
    _write_mapping(mapping_path, mapping)

    result = _run_generator(*_base_args(mapping=mapping_path))
    assert result.returncode == 1
    assert "code=mapping-registry-input-missing" in result.stderr
    _assert_console_is_safe(result)


@pytest.mark.parametrize(
    "candidate_contents",
    [
        "SENSITIVE_TEST_RAW C:\\secret\\synthetic.dec",
        "TEST_PACKET_STORY",
        "@ChTalk should not appear in a Public-safe candidate",
        "$num1 should not appear in a Public-safe candidate",
        "<script should not appear in a Public-safe candidate",
    ],
    ids=[
        "candidate-raw-path",
        "candidate-internal-id",
        "candidate-raw-command",
        "candidate-variable-token",
        "candidate-script-tag",
    ],
)
def test_unsafe_public_candidate_input_is_rejected_without_echoing_contents(
    local_input_dir: Path, candidate_contents: str
):
    candidate_path = local_input_dir / "unsafe-candidate.yaml"
    candidate = yaml.safe_load(PUBLIC_CANDIDATE.read_text(encoding="utf-8"))
    candidate["notes"] = candidate_contents
    candidate_path.write_text(
        yaml.safe_dump(candidate, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    result = _run_generator(*_base_args(candidate=candidate_path))
    if result.returncode == 0:
        _cleanup_packet(_packet_id_from_output(result))
    assert result.returncode in {1, 2}
    assert candidate_contents not in result.stdout + result.stderr


def test_invalid_utf8_candidate_is_not_echoed_to_console(local_input_dir: Path):
    candidate_path = local_input_dir / "invalid-utf8.yaml"
    candidate_path.write_bytes(b"\xff\xfeSENSITIVE_TEST_RAW C:\\secret\\synthetic.dec")

    result = _run_generator(*_base_args(candidate=candidate_path))
    assert result.returncode in {1, 2}
    assert "SENSITIVE_TEST_RAW" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_raw_arguments_are_not_silently_dropped():
    with pytest.raises(packet_generator.ContentError) as caught:
        packet_generator._raw_content(
            {"rawCommand": "@SyntheticCommand", "args": ["safe", 1]}
        )
    assert caught.value.code == "raw-arguments-invalid"


def test_atomic_rename_does_not_replace_existing_destination(local_input_dir: Path):
    source = local_input_dir / "source"
    destination = local_input_dir / "destination"
    source.mkdir()
    destination.mkdir()
    marker = destination / "marker.txt"
    marker.write_text("unchanged", encoding="utf-8")

    with pytest.raises(packet_generator.ConfigError) as caught:
        packet_generator._rename_no_replace(source, destination)

    assert caught.value.code == "packet-id-collision"
    assert source.is_dir()
    assert marker.read_text(encoding="utf-8") == "unchanged"


def test_existing_final_packet_is_rejected_before_input_read(
    local_input_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    packet_root = local_input_dir / "packets"
    packet_id = "erp-20260722T030000Z-deadbeef"
    final = packet_root / packet_id
    final.mkdir(parents=True)
    (final / "marker.txt").write_text("unchanged", encoding="utf-8")
    input_read = False

    def fail_if_called(_path: Path) -> bytes:
        nonlocal input_read
        input_read = True
        raise AssertionError("input must not be read before output preflight")

    monkeypatch.setattr(packet_generator, "_PACKET_ROOT", packet_root)
    monkeypatch.setattr(packet_generator, "_packet_id", lambda _created: packet_id)
    monkeypatch.setattr(packet_generator, "_read_bytes_once", fail_if_called)

    assert packet_generator.main(_base_args()) == 2
    assert input_read is False
    assert (final / "marker.txt").read_text(encoding="utf-8") == "unchanged"


def test_validator_failure_removes_exact_temporary_directory(
    local_input_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    packet_root = local_input_dir / "packets"
    packet_id = "erp-20260722T030001Z-feedface"
    monkeypatch.setattr(packet_generator, "_PACKET_ROOT", packet_root)
    monkeypatch.setattr(packet_generator, "_packet_id", lambda _created: packet_id)
    monkeypatch.setattr(
        packet_generator.packet_validator,
        "validate_packet_directory",
        lambda _path, _packet_id: SimpleNamespace(errors=[object()]),
    )

    assert packet_generator.main(_base_args()) == 1
    assert not (packet_root / packet_id).exists()
    assert not (packet_root / f".tmp-{packet_id}").exists()


def test_raw_argument_limit_failure_removes_temporary_directory(
    local_input_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    normalized = json.loads(NORMALIZED_INPUT.read_text(encoding="utf-8"))
    normalized["episodes"][0]["scenes"][0]["blocks"][2]["args"] = ["arg"] * 17
    normalized_path = local_input_dir / "normalized.json"
    normalized_path.write_text(json.dumps(normalized), encoding="utf-8")
    selection_root = local_input_dir / "selections"
    selection_root.mkdir()
    shutil.copy2(SELECTION_SOURCE, selection_root / "selection.json")
    packet_root = local_input_dir / "packets"
    packet_id = "erp-20260722T030002Z-aabbccdd"
    monkeypatch.setattr(packet_generator, "_PACKET_ROOT", packet_root)
    monkeypatch.setattr(packet_generator, "_SELECTION_ROOT", selection_root)
    monkeypatch.setattr(packet_generator, "_packet_id", lambda _created: packet_id)

    result = packet_generator.main(
        [
            *_base_args(normalized=normalized_path),
            "--selection-file",
            "selection.json",
            "--quiet",
        ]
    )

    assert result == 1
    assert not (packet_root / packet_id).exists()
    assert not (packet_root / f".tmp-{packet_id}").exists()


def test_reparse_input_is_rejected_before_any_input_read(
    local_input_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    packet_root = local_input_dir / "packets"
    packet_id = "erp-20260722T030003Z-11223344"
    original_is_reparse = packet_generator._is_reparse
    input_read = False

    def reparse_only_for_normalized(path: Path) -> bool:
        if path.absolute() == NORMALIZED_INPUT.absolute():
            return True
        return original_is_reparse(path)

    def fail_if_called(_path: Path) -> bytes:
        nonlocal input_read
        input_read = True
        raise AssertionError("reparse input must fail before reading bytes")

    monkeypatch.setattr(packet_generator, "_PACKET_ROOT", packet_root)
    monkeypatch.setattr(packet_generator, "_packet_id", lambda _created: packet_id)
    monkeypatch.setattr(packet_generator, "_is_reparse", reparse_only_for_normalized)
    monkeypatch.setattr(packet_generator, "_read_bytes_once", fail_if_called)

    assert packet_generator.main(_base_args()) == 2
    assert input_read is False
    assert not (packet_root / packet_id).exists()
    assert not (packet_root / f".tmp-{packet_id}").exists()
