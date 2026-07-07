"""
tests/scripts/test_build_evidence_index_candidates.py
scripts/build_evidence_index_candidates.py のCLI/生成ロジックテスト。

Normalized Story JSON (必要ならExtraction Resultも) からPublic Evidence
Index候補YAMLをdry-run生成するスクリプトを検証する。合成fixture
(tests/fixtures/normalized_story/build_evidence_index_candidates/,
tests/fixtures/extraction/build_evidence_index_candidates/) のみを使い、
実データは一切使わない。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_evidence_index_candidates.py"
NORMALIZED_FIXTURES_DIR = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "normalized_story"
    / "build_evidence_index_candidates"
)
EXTRACTION_FIXTURES_DIR = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "extraction"
    / "build_evidence_index_candidates"
)
INVALID_JSON_PATH = NORMALIZED_FIXTURES_DIR / "invalid_examples" / "broken.json"

# 生成物に絶対含まれてはいけない、fixture中のraw text本文語。
FORBIDDEN_SUBSTRINGS = (
    "This is synthetic dialogue text",
    "Synthetic monologue text",
    "Synthetic narration text",
    "Unclassified synthetic line",
    "This block has no id",
    "This nested block has no id",
    "@ChTalk",
    "bg 1 1",
)


def _run_cli(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *extra_args],
        capture_output=True,
        text=True,
    )


def _run_generation(tmp_path: Path, *, with_extractions: bool = False) -> Path:
    output_dir = tmp_path / "out"
    args = [
        "--input",
        str(NORMALIZED_FIXTURES_DIR),
        "--output",
        str(output_dir),
        "--clean",
    ]
    if with_extractions:
        args.extend(["--extractions", str(EXTRACTION_FIXTURES_DIR)])
    result = _run_cli(*args)
    assert result.returncode == 0, result.stderr
    return output_dir


def _load_story_document(output_dir: Path, story_id: str) -> dict:
    with open(output_dir / "stories" / f"{story_id}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _all_generated_text(output_dir: Path) -> str:
    parts = []
    for path in output_dir.rglob("*"):
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


# ----------------------------------------------------------------
# Generation basics
# ----------------------------------------------------------------


def test_cli_valid_input_exits_zero(tmp_path):
    output_dir = _run_generation(tmp_path)
    assert (output_dir / "stories" / "TEST_S01_C01.yaml").is_file()
    assert (output_dir / "stories" / "TEST_S02_SOLO.yaml").is_file()
    assert (output_dir / "report.json").is_file()
    assert (output_dir / "report.md").is_file()


def test_cli_missing_input_path_exits_two(tmp_path):
    result = _run_cli(
        "--input",
        str(tmp_path / "does_not_exist"),
        "--output",
        str(tmp_path / "out"),
    )
    assert result.returncode == 2


def test_cli_missing_extractions_path_exits_two(tmp_path):
    result = _run_cli(
        "--input",
        str(NORMALIZED_FIXTURES_DIR),
        "--extractions",
        str(tmp_path / "does_not_exist_extractions"),
        "--output",
        str(tmp_path / "out"),
    )
    assert result.returncode == 2


def test_cli_all_inputs_invalid_json_exits_one(tmp_path):
    result = _run_cli(
        "--input",
        str(INVALID_JSON_PATH),
        "--output",
        str(tmp_path / "out"),
    )
    assert result.returncode == 1


def test_cli_creates_output_directory(tmp_path):
    output_dir = tmp_path / "nested" / "out"
    assert not output_dir.exists()
    result = _run_cli(
        "--input", str(NORMALIZED_FIXTURES_DIR), "--output", str(output_dir)
    )
    assert result.returncode == 0, result.stderr
    assert output_dir.is_dir()


def test_cli_clean_removes_previous_output(tmp_path):
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    stale_file = output_dir / "stale.txt"
    stale_file.write_text("stale", encoding="utf-8")

    result = _run_cli(
        "--input",
        str(NORMALIZED_FIXTURES_DIR),
        "--output",
        str(output_dir),
        "--clean",
    )
    assert result.returncode == 0, result.stderr
    assert not stale_file.exists()


# ----------------------------------------------------------------
# Content policy: raw text / raw command must never appear
# ----------------------------------------------------------------


def test_generated_output_does_not_contain_raw_text(tmp_path):
    output_dir = _run_generation(tmp_path, with_extractions=True)
    generated_text = _all_generated_text(output_dir)
    for forbidden in FORBIDDEN_SUBSTRINGS:
        assert forbidden not in generated_text


def test_generated_entries_have_raw_text_included_false(tmp_path):
    output_dir = _run_generation(tmp_path)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    assert document["entries"], "entries should not be empty"
    for entry in document["entries"]:
        assert entry["visibility"]["rawTextIncluded"] is False
        assert entry["visibility"]["public"] is True


# ----------------------------------------------------------------
# evidenceType mapping / skip policy
# ----------------------------------------------------------------


def test_evidence_type_mapping_matches_block_types(tmp_path):
    output_dir = _run_generation(tmp_path)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    by_id = {e["evidenceId"]: e for e in document["entries"]}

    assert by_id["TEST_S01_C01_E01_DLG0001"]["evidenceType"] == "dialogue"
    assert by_id["TEST_S01_C01_E01_MONO0001"]["evidenceType"] == "monologue"
    assert by_id["TEST_S01_C01_E01_NAR0001"]["evidenceType"] == "narration"
    assert by_id["TEST_S01_C01_E01_STAGE0001"]["evidenceType"] == "stage_direction"
    assert by_id["TEST_S01_C01_E01_UNKNOWN0001"]["evidenceType"] == "unknown"
    assert by_id["TEST_S01_C01_E01_CHOICE001"]["evidenceType"] == "choice"
    # choice option内のnested dialogue blockも生成される
    assert by_id["TEST_S01_C01_E01_DLG0002"]["evidenceType"] == "dialogue"


def test_blocks_without_id_are_skipped_and_counted(tmp_path):
    output_dir = _run_generation(tmp_path)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    ids = {e["evidenceId"] for e in document["entries"]}
    # 2件のid無しblock (トップレベル1件・choice option内1件) は生成されない
    assert len(ids) == 7 + 1  # E01内7件 + E02内1件

    with open(output_dir / "report.json", encoding="utf-8") as f:
        report = json.load(f)
    assert report["skippedReasonCounts"]["missing_block_id"] == 2


def test_unmapped_block_type_is_skipped_and_counted(tmp_path):
    output_dir = _run_generation(tmp_path)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    ids = {e["evidenceId"] for e in document["entries"]}
    assert "TEST_S01_C01_E01_FUTURE0001" not in ids

    with open(output_dir / "report.json", encoding="utf-8") as f:
        report = json.load(f)
    assert (
        report["skippedReasonCounts"]["unmapped_block_type:future_unmapped_type"] == 1
    )


# ----------------------------------------------------------------
# Speaker / relatedEntities policy
# ----------------------------------------------------------------


def test_resolved_speaker_included_unresolved_speaker_excluded(tmp_path):
    output_dir = _run_generation(tmp_path)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    by_id = {e["evidenceId"]: e for e in document["entries"]}

    resolved = by_id["TEST_S01_C01_E01_DLG0001"]
    assert resolved["speaker"]["speakerId"] == "CHAR_TEST_RAIN"
    assert resolved["speaker"]["displayName"] is None
    assert resolved["speaker"]["resolutionStatus"] == "resolved"
    assert {"entityType": "character", "id": "CHAR_TEST_RAIN"} in (
        resolved["relatedEntities"]
    )

    unresolved = by_id["TEST_S01_C01_E01_MONO0001"]
    assert unresolved["speaker"] is None


def test_location_id_added_to_related_entities_when_present(tmp_path):
    output_dir = _run_generation(tmp_path)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    by_id = {e["evidenceId"]: e for e in document["entries"]}

    with_location = by_id["TEST_S01_C01_E01_NAR0001"]
    assert {"entityType": "location", "id": "LOC_TEST_HQ"} in (
        with_location["relatedEntities"]
    )

    without_location = by_id["TEST_S01_C01_E02_DLG0001"]
    assert without_location["relatedEntities"] == []


# ----------------------------------------------------------------
# publicStoryId / publicEpisodeId propagation
# ----------------------------------------------------------------


def test_public_ids_propagated_per_entry_when_present(tmp_path):
    output_dir = _run_generation(tmp_path)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    by_id = {e["evidenceId"]: e for e in document["entries"]}

    e01_entry = by_id["TEST_S01_C01_E01_DLG0001"]
    assert e01_entry["publicStoryId"] == "PUBLIC_TEST_STORY_001"
    assert e01_entry["publicEpisodeId"] == "PUBLIC_TEST_STORY_001_E01"

    e02_entry = by_id["TEST_S01_C01_E02_DLG0001"]
    assert e02_entry["publicStoryId"] is None
    assert e02_entry["publicEpisodeId"] is None


# ----------------------------------------------------------------
# Multi-file story aggregation
# ----------------------------------------------------------------


def test_multiple_episode_files_merge_into_one_story_document(tmp_path):
    output_dir = _run_generation(tmp_path)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    episode_ids = {
        ref["episodeId"] for ref in document["generatedFrom"]["normalizedStoryRefs"]
    }
    assert episode_ids == {"TEST_S01_C01_E01", "TEST_S01_C01_E02"}
    story_ids_in_entries = {e["storyId"] for e in document["entries"]}
    assert story_ids_in_entries == {"TEST_S01_C01"}


# ----------------------------------------------------------------
# Extraction Result -> referencedBy.candidates
# ----------------------------------------------------------------


def test_extraction_candidates_are_attached_when_provided(tmp_path):
    output_dir = _run_generation(tmp_path, with_extractions=True)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    by_id = {e["evidenceId"]: e for e in document["entries"]}

    entry = by_id["TEST_S01_C01_E01_DLG0001"]
    assert entry["referencedBy"]["candidates"] == [
        {"candidateId": "TEST_S01_C01_E01_CAND_CHAR001", "entityType": "character"}
    ]
    assert "TEST_S01_C01_E01" in document["generatedFrom"]["extractionRefs"]


def test_no_extraction_candidates_without_extractions_flag(tmp_path):
    output_dir = _run_generation(tmp_path, with_extractions=False)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    by_id = {e["evidenceId"]: e for e in document["entries"]}
    assert by_id["TEST_S01_C01_E01_DLG0001"]["referencedBy"] is None
    assert document["generatedFrom"]["extractionRefs"] == []


# ----------------------------------------------------------------
# Schema validation of generated output
# ----------------------------------------------------------------


def test_generated_output_passes_validate_evidence_index_cli(tmp_path):
    output_dir = _run_generation(tmp_path, with_extractions=True)
    validate_script = PROJECT_ROOT / "scripts" / "validate_evidence_index.py"
    result = subprocess.run(
        [
            sys.executable,
            str(validate_script),
            "--input",
            str(output_dir / "stories"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


# ----------------------------------------------------------------
# Report content
# ----------------------------------------------------------------


def test_report_json_has_expected_counts(tmp_path):
    output_dir = _run_generation(tmp_path, with_extractions=True)
    with open(output_dir / "report.json", encoding="utf-8") as f:
        report = json.load(f)

    assert report["inputFileCount"] == 3
    assert report["extractionInputFileCount"] == 1
    assert report["storyCount"] == 2
    assert report["episodeCount"] == 3
    assert report["generatedEntryCount"] == 9
    assert report["skippedBlockCount"] == 3
    assert report["candidateReferencesAttachedCount"] == 1
    assert report["validation"]["schemaValid"] is True
    assert report["validation"]["issuesByStoryId"] == {}
    assert set(report["outputFiles"]) == {
        str(Path("stories") / "TEST_S01_C01.yaml"),
        str(Path("stories") / "TEST_S02_SOLO.yaml"),
    }


def test_report_md_mentions_key_sections(tmp_path):
    output_dir = _run_generation(tmp_path)
    content = (output_dir / "report.md").read_text(encoding="utf-8")
    assert "Skipped reason counts" in content
    assert "Entries by evidenceType" in content
    assert "Output files" in content
    assert "Validation" in content
    assert "schemaValid: true" in content


def test_report_does_not_contain_raw_text(tmp_path):
    output_dir = _run_generation(tmp_path, with_extractions=True)
    report_text = (output_dir / "report.md").read_text(encoding="utf-8")
    report_text += (output_dir / "report.json").read_text(encoding="utf-8")
    for forbidden in FORBIDDEN_SUBSTRINGS:
        assert forbidden not in report_text
