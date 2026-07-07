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


def _run_generation(
    tmp_path: Path,
    *,
    with_extractions: bool = False,
    profile: str | None = None,
    extra_args: list[str] | None = None,
) -> Path:
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
    if profile is not None:
        args.extend(["--public-profile", profile])
    if extra_args:
        args.extend(extra_args)
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
    # full profileでstage_direction/unknown等も含む全typeを確認する
    # (defaultはPublic向けにstage_directionを除外するため)。
    output_dir = _run_generation(tmp_path, profile="full")
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
    # full profileでfilterの影響を受けない状態でskip件数のみを確認する。
    output_dir = _run_generation(tmp_path, profile="full")
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
    # full profileでfilterの影響を受けない状態で既存カウントを確認する。
    output_dir = _run_generation(tmp_path, with_extractions=True, profile="full")
    with open(output_dir / "report.json", encoding="utf-8") as f:
        report = json.load(f)

    assert report["inputFileCount"] == 3
    assert report["extractionInputFileCount"] == 1
    assert report["storyCount"] == 2
    assert report["episodeCount"] == 3
    assert report["generatedEntryCount"] == 9
    assert report["generatedEntryCountBeforeFilter"] == 9
    assert report["generatedEntryCountAfterFilter"] == 9
    assert report["filteredEntryCount"] == 0
    assert report["filteredReasonCounts"] == {}
    assert report["filteredByTypeCounts"] == {}
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


# ----------------------------------------------------------------
# entry type filtering (--public-profile / --include-types / --exclude-types)
# ----------------------------------------------------------------


def test_default_profile_excludes_stage_direction(tmp_path):
    output_dir = _run_generation(tmp_path)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    evidence_types = {e["evidenceType"] for e in document["entries"]}
    assert "stage_direction" not in evidence_types
    assert "TEST_S01_C01_E01_STAGE0001" not in {
        e["evidenceId"] for e in document["entries"]
    }


def test_full_profile_includes_stage_direction(tmp_path):
    output_dir = _run_generation(tmp_path, profile="full")
    document = _load_story_document(output_dir, "TEST_S01_C01")
    by_id = {e["evidenceId"]: e for e in document["entries"]}
    assert by_id["TEST_S01_C01_E01_STAGE0001"]["evidenceType"] == "stage_direction"


def test_review_profile_behaves_like_full_profile(tmp_path):
    output_dir = _run_generation(tmp_path, profile="review")
    document = _load_story_document(output_dir, "TEST_S01_C01")
    by_id = {e["evidenceId"]: e for e in document["entries"]}
    assert by_id["TEST_S01_C01_E01_STAGE0001"]["evidenceType"] == "stage_direction"


def test_include_types_restricts_output_to_listed_types(tmp_path):
    output_dir = _run_generation(
        tmp_path, extra_args=["--include-types", "dialogue,narration"]
    )
    document = _load_story_document(output_dir, "TEST_S01_C01")
    evidence_types = {e["evidenceType"] for e in document["entries"]}
    assert evidence_types == {"dialogue", "narration"}


def test_include_types_overrides_profile_include_set(tmp_path):
    # defaultはunknownを含むが、--include-typesは丸ごと置き換えるため
    # unknownは出力されない
    output_dir = _run_generation(tmp_path, extra_args=["--include-types", "dialogue"])
    document = _load_story_document(output_dir, "TEST_S01_C01")
    evidence_types = {e["evidenceType"] for e in document["entries"]}
    assert evidence_types == {"dialogue"}


def test_exclude_types_removes_listed_types_from_full_profile(tmp_path):
    output_dir = _run_generation(
        tmp_path,
        profile="full",
        extra_args=["--exclude-types", "stage_direction"],
    )
    document = _load_story_document(output_dir, "TEST_S01_C01")
    evidence_types = {e["evidenceType"] for e in document["entries"]}
    assert "stage_direction" not in evidence_types
    assert evidence_types == {"dialogue", "monologue", "narration", "unknown", "choice"}


def test_exclude_types_wins_over_include_types_conflict(tmp_path):
    output_dir = _run_generation(
        tmp_path,
        extra_args=[
            "--include-types",
            "dialogue,stage_direction",
            "--exclude-types",
            "stage_direction",
        ],
    )
    document = _load_story_document(output_dir, "TEST_S01_C01")
    evidence_types = {e["evidenceType"] for e in document["entries"]}
    assert evidence_types == {"dialogue"}


def test_invalid_evidence_type_in_include_types_exits_two(tmp_path):
    result = _run_cli(
        "--input",
        str(NORMALIZED_FIXTURES_DIR),
        "--output",
        str(tmp_path / "out"),
        "--include-types",
        "dialogue,not_a_real_type",
    )
    assert result.returncode == 2
    assert "not_a_real_type" in result.stderr


def test_invalid_evidence_type_in_exclude_types_exits_two(tmp_path):
    result = _run_cli(
        "--input",
        str(NORMALIZED_FIXTURES_DIR),
        "--output",
        str(tmp_path / "out"),
        "--exclude-types",
        "not_a_real_type",
    )
    assert result.returncode == 2


def test_invalid_public_profile_exits_two(tmp_path):
    result = _run_cli(
        "--input",
        str(NORMALIZED_FIXTURES_DIR),
        "--output",
        str(tmp_path / "out"),
        "--public-profile",
        "not_a_real_profile",
    )
    assert result.returncode == 2


# ----------------------------------------------------------------
# Report: filter counts, skip vs filter distinction
# ----------------------------------------------------------------


def test_report_json_has_filter_counts_for_default_profile(tmp_path):
    output_dir = _run_generation(tmp_path, with_extractions=True)
    with open(output_dir / "report.json", encoding="utf-8") as f:
        report = json.load(f)

    assert report["publicProfile"] == "default"
    assert report["includedTypes"] == [
        "choice",
        "dialogue",
        "monologue",
        "narration",
        "unknown",
    ]
    assert report["excludedTypes"] == [
        "episode",
        "scene",
        "speaker_label",
        "stage_direction",
        "story",
    ]
    # TEST_S01_C01のSTAGE0001 1件のみがfilterされる
    # (TEST_S02_SOLOにはstage_directionが無い)
    assert report["filteredEntryCount"] == 1
    assert report["filteredByTypeCounts"] == {"stage_direction": 1}
    assert report["filteredReasonCounts"] == {"excluded_by_profile:stage_direction": 1}
    assert report["generatedEntryCount"] == 8
    assert report["generatedEntryCountBeforeFilter"] == 9
    assert report["generatedEntryCountAfterFilter"] == 8


def test_skip_and_filter_counts_are_tracked_separately(tmp_path):
    output_dir = _run_generation(tmp_path)
    with open(output_dir / "report.json", encoding="utf-8") as f:
        report = json.load(f)

    # skip (missing_block_id/unmapped_block_type) はprofileの影響を受けない
    assert report["skippedBlockCount"] == 3
    assert report["skippedReasonCounts"] == {
        "missing_block_id": 2,
        "unmapped_block_type:future_unmapped_type": 1,
    }
    # filter (stage_direction) はskippedReasonCountsに含まれない
    assert "stage_direction" not in "".join(report["skippedReasonCounts"].keys())
    assert report["filteredEntryCount"] == 1


def test_report_md_mentions_filter_section(tmp_path):
    output_dir = _run_generation(tmp_path)
    content = (output_dir / "report.md").read_text(encoding="utf-8")
    assert "## Filter" in content
    assert "Public profile: default" in content
    assert "Included types:" in content
    assert "Excluded types:" in content
    assert "filtered stage_direction: 1" in content


# ----------------------------------------------------------------
# Candidate references: only attached to entries that survive filtering
# ----------------------------------------------------------------


def test_candidate_references_not_attached_to_filtered_out_entries(tmp_path):
    # stage_directionを対象にreferencedBy.candidatesが付与されうる状況でも、
    # default profileで除外されたentryにはcandidate referencesが付かない
    # (そもそも出力entry自体が存在しない)。
    output_dir = _run_generation(tmp_path, with_extractions=True)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    ids = {e["evidenceId"] for e in document["entries"]}
    assert "TEST_S01_C01_E01_STAGE0001" not in ids


def test_candidate_references_still_attached_to_included_entries(tmp_path):
    output_dir = _run_generation(tmp_path, with_extractions=True)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    by_id = {e["evidenceId"]: e for e in document["entries"]}
    entry = by_id["TEST_S01_C01_E01_DLG0001"]
    assert entry["referencedBy"]["candidates"] == [
        {"candidateId": "TEST_S01_C01_E01_CAND_CHAR001", "entityType": "character"}
    ]


# ----------------------------------------------------------------
# Schema validation / raw text policy still hold after filtering
# ----------------------------------------------------------------


def test_filtered_output_passes_validate_evidence_index_cli(tmp_path):
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


def test_filtered_output_entries_have_raw_text_included_false(tmp_path):
    output_dir = _run_generation(tmp_path)
    document = _load_story_document(output_dir, "TEST_S01_C01")
    assert document["entries"], "entries should not be empty"
    for entry in document["entries"]:
        assert entry["visibility"]["rawTextIncluded"] is False


def test_raw_text_fields_still_ignored_under_default_profile(tmp_path):
    output_dir = _run_generation(tmp_path, with_extractions=True)
    generated_text = _all_generated_text(output_dir)
    for forbidden in FORBIDDEN_SUBSTRINGS:
        assert forbidden not in generated_text
