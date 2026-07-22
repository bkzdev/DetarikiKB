"""Internal Review Evidence Packet validatorの合成bundleテスト。

fixture・選択入力ともTEST_/Syntheticの値だけを使い、実データやDEC由来の
内容には一切依存しない。CLI境界の確認ではgitignore済み固定root直下だけを
一時使用し、テスト終了時にその専用pathを削除する。
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "validate_internal_review_evidence_packet.py"
FIXTURE_DIR = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "internal_review_evidence_packet"
    / "valid_bundle"
)
PACKET_ID = "erp-20990101T000000Z-a1b2c3d4"
PACKET_ROOT = PROJECT_ROOT / "workspace" / "review_packets" / "evidence"
SELECTION_ROOT = (
    PROJECT_ROOT / "workspace" / "local_inputs" / "evidence_packet_selection"
)


def _load_validator_module():
    spec = importlib.util.spec_from_file_location("packet_validator", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = _load_validator_module()


def _copy_bundle(tmp_path: Path) -> Path:
    destination = tmp_path / "valid_bundle"
    shutil.copytree(FIXTURE_DIR, destination)
    return destination


def _refresh_component_digest(bundle: Path, relative_path: str) -> None:
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256((bundle / relative_path).read_bytes()).hexdigest()
    for component in manifest["components"]:
        if component["relativePath"] == relative_path:
            component["sha256"] = digest
            break
    else:
        raise AssertionError(f"component not found: {relative_path}")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _issue_codes(result) -> set[str]:
    return {issue.code for issue in result.issues}


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@pytest.fixture
def ignored_packet_dir() -> Path:
    packet_dir = PACKET_ROOT / PACKET_ID
    if packet_dir.exists():
        shutil.rmtree(packet_dir)
    packet_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURE_DIR, packet_dir)
    try:
        yield packet_dir
    finally:
        if packet_dir.exists():
            shutil.rmtree(packet_dir)


def test_all_packet_schemas_are_valid_draft7_documents():
    for schema_path in sorted(
        PROJECT_ROOT.glob("schemas/internal_review_evidence_packet*.json")
    ):
        Draft7Validator.check_schema(
            json.loads(schema_path.read_text(encoding="utf-8"))
        )


def test_story_schema_accepts_source_character_id_and_extraction_candidate_types():
    schema = json.loads(
        (
            PROJECT_ROOT
            / "schemas"
            / "internal_review_evidence_packet_story.schema.json"
        ).read_text(encoding="utf-8")
    )
    story = json.loads(
        (FIXTURE_DIR / "stories" / "story-0001.json").read_text(encoding="utf-8")
    )
    story["entries"][0]["extraction"] = {
        "candidates": [
            {
                "candidateId": "TEST_CANDIDATE",
                "candidateType": "character_candidate",
                "confidence": 0.75,
            }
        ]
    }

    assert list(Draft7Validator(schema).iter_errors(story)) == []

    invalid = copy.deepcopy(story)
    invalid["entries"][0]["rawContent"]["rawCommand"] = "@SyntheticCommand"
    assert list(Draft7Validator(schema).iter_errors(invalid))


def test_valid_synthetic_bundle_has_no_errors_or_warnings(tmp_path):
    result = validator.validate_packet_directory(_copy_bundle(tmp_path), PACKET_ID)

    assert result.errors == []
    assert result.warnings == []
    assert (result.story_count, result.entry_count, result.component_count) == (1, 1, 3)


def test_component_digest_mismatch_is_rejected(tmp_path):
    bundle = _copy_bundle(tmp_path)
    story_path = bundle / "stories" / "story-0001.json"
    story_path.write_text("{}\n", encoding="utf-8")

    result = validator.validate_packet_directory(bundle, PACKET_ID)

    assert "component-digest-mismatch" in _issue_codes(result)


def test_duplicate_mapping_public_evidence_id_is_rejected(tmp_path):
    bundle = _copy_bundle(tmp_path)
    mapping_path = bundle / "mappings" / "evidence-id-map.csv"
    row = mapping_path.read_text(encoding="utf-8").splitlines()[1]
    duplicate = row.replace("TEST_EVIDENCE", "TEST_EVIDENCE_TWO")
    mapping_path.write_text(
        mapping_path.read_text(encoding="utf-8") + duplicate + "\n", encoding="utf-8"
    )
    _refresh_component_digest(bundle, "mappings/evidence-id-map.csv")
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["components"][0]["recordCount"] = 2
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    result = validator.validate_packet_directory(bundle, PACKET_ID)

    assert "mapping-public-evidence-id-duplicate" in _issue_codes(result)


def test_mapping_episode_source_must_match_public_id_state(tmp_path):
    bundle = _copy_bundle(tmp_path)
    mapping_path = bundle / "mappings" / "evidence-id-map.csv"
    mapping = mapping_path.read_text(encoding="utf-8").replace(
        ",input,False,False,", ",missing,False,False,"
    )
    mapping_path.write_text(mapping, encoding="utf-8")
    _refresh_component_digest(bundle, "mappings/evidence-id-map.csv")

    result = validator.validate_packet_directory(bundle, PACKET_ID)

    assert "mapping-registry-id-invalid" in _issue_codes(result)


def test_malformed_mapping_row_is_reported_without_crashing(tmp_path):
    bundle = _copy_bundle(tmp_path)
    mapping_path = bundle / "mappings" / "evidence-id-map.csv"
    header = mapping_path.read_text(encoding="utf-8").splitlines()[0]
    mapping_path.write_text(f"{header}\nTEST_STORY\n", encoding="utf-8")
    _refresh_component_digest(bundle, "mappings/evidence-id-map.csv")

    result = validator.validate_packet_directory(bundle, PACKET_ID)

    assert "mapping-row-shape-invalid" in _issue_codes(result)


def test_invalid_utf8_mapping_is_reported_without_crashing(tmp_path):
    bundle = _copy_bundle(tmp_path)
    mapping_path = bundle / "mappings" / "evidence-id-map.csv"
    mapping_path.write_bytes(b"\xff\xfe")
    _refresh_component_digest(bundle, "mappings/evidence-id-map.csv")

    result = validator.validate_packet_directory(bundle, PACKET_ID)

    assert "mapping-csv-invalid" in _issue_codes(result)


def test_path_like_sensitive_value_is_rejected_without_echoing_value(tmp_path):
    bundle = _copy_bundle(tmp_path)
    story_path = bundle / "stories" / "story-0001.json"
    story = json.loads(story_path.read_text(encoding="utf-8"))
    forbidden_marker = "SENSITIVE_TEST_PATH C:\\secret\\synthetic.dec"
    story["entries"][0]["rawContent"]["text"] = forbidden_marker
    story_path.write_text(json.dumps(story, indent=2) + "\n", encoding="utf-8")
    _refresh_component_digest(bundle, "stories/story-0001.json")

    result = validator.validate_packet_directory(bundle, PACKET_ID)

    assert "entry-path-like-value" in _issue_codes(result)
    assert forbidden_marker not in " ".join(issue.code for issue in result.issues)


def test_web_url_is_not_mistaken_for_local_absolute_path():
    assert not validator._contains_forbidden_path("https://example.test/review/item")


def test_manifest_rejects_internal_id_in_safe_field(tmp_path):
    bundle = _copy_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generatorVersion"] = "TEST_STORY"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    result = validator.validate_packet_directory(bundle, PACKET_ID)

    assert any(
        issue.code == "safe-component-internal-id-exposed"
        and issue.component_path == "manifest.json"
        for issue in result.issues
    )


def test_selection_schema_rejects_duplicate_internal_evidence_ids(tmp_path):
    selection = tmp_path / "selection.json"
    selection.write_text(
        json.dumps(
            {
                "selectionVersion": 1,
                "evidenceIds": ["TEST_EVIDENCE", "TEST_EVIDENCE"],
            }
        ),
        encoding="utf-8",
    )

    issues = validator.validate_selection_document(selection)

    assert [issue.code for issue in issues] == ["selection-schema-invalid"]


def test_cli_accepts_valid_bundle_only_under_ignored_fixed_root(ignored_packet_dir):
    result = _run_cli("--packet-id", PACKET_ID)

    assert result.returncode == 0, result.stderr
    assert "status=valid" in result.stdout
    assert "TEST_STORY" not in result.stdout + result.stderr
    assert "Synthetic review text." not in result.stdout + result.stderr


def test_cli_rejects_path_in_packet_id_without_echoing_it():
    unsafe_value = "../SENSITIVE_TEST_PATH"
    result = _run_cli("--packet-id", unsafe_value)

    assert result.returncode == 2
    assert "packet-id-invalid" in result.stderr
    assert unsafe_value not in result.stdout + result.stderr


def test_cli_invalid_bundle_does_not_echo_sensitive_values(ignored_packet_dir):
    story_path = ignored_packet_dir / "stories" / "story-0001.json"
    story = json.loads(story_path.read_text(encoding="utf-8"))
    forbidden_marker = "SENSITIVE_TEST_PATH C:\\secret\\synthetic.dec"
    story["entries"][0]["rawContent"]["text"] = forbidden_marker
    story_path.write_text(json.dumps(story, indent=2) + "\n", encoding="utf-8")
    _refresh_component_digest(ignored_packet_dir, "stories/story-0001.json")

    result = _run_cli("--packet-id", PACKET_ID)

    assert result.returncode == 1
    assert "entry-path-like-value" in result.stderr
    assert forbidden_marker not in result.stdout + result.stderr
    assert "TEST_STORY" not in result.stdout + result.stderr


def test_cli_invalid_utf8_component_has_no_traceback(ignored_packet_dir):
    story_path = ignored_packet_dir / "stories" / "story-0001.json"
    story_path.write_bytes(b"\xff\xfe")
    _refresh_component_digest(ignored_packet_dir, "stories/story-0001.json")

    result = _run_cli("--packet-id", PACKET_ID)

    assert result.returncode == 1
    assert "story-json-invalid" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_safe_report_internal_id_exposure_is_not_echoed(ignored_packet_dir):
    report_path = ignored_packet_dir / "reports" / "validation.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["warningCount"] = 1
    report["issues"] = [
        {
            "issueCode": "TEST_EVIDENCE",
            "severity": "warning",
            "reviewStoryKey": None,
            "reviewEntryId": None,
            "componentPath": None,
        }
    ]
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _refresh_component_digest(ignored_packet_dir, "reports/validation.json")
    manifest_path = ignored_packet_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for component in manifest["components"]:
        if component["relativePath"] == "reports/validation.json":
            component["recordCount"] = 1
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    result = _run_cli("--packet-id", PACKET_ID)

    assert result.returncode == 1
    assert "safe-component-internal-id-exposed" in result.stderr
    assert "TEST_EVIDENCE" not in result.stdout + result.stderr


def test_cli_selection_uses_fixed_ignored_root_and_does_not_echo_internal_id():
    filename = "test-selection-erp-a1b2c3d4.json"
    selection_path = SELECTION_ROOT / filename
    selection_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(
        json.dumps({"selectionVersion": 1, "evidenceIds": ["TEST_EVIDENCE"]}),
        encoding="utf-8",
    )
    try:
        result = _run_cli("--selection-file", filename)
    finally:
        if selection_path.exists():
            selection_path.unlink()

    assert result.returncode == 0, result.stderr
    assert "status=valid" in result.stdout
    assert "TEST_EVIDENCE" not in result.stdout + result.stderr
