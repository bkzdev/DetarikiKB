"""
tests/scripts/test_check_evidence_index_promotion.py
scripts/check_evidence_index_promotion.py のCLIテスト。

Evidence Index候補（Public Evidence Index形式）がknowledge/evidence/stories/へ
昇格可能かをcheckするgatekeeper scriptを検証する。合成データのみを一時ファイル
として生成して使う。実データ・実データ由来fixtureは一切使わない。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_evidence_index_promotion.py"


def _minimal_entry(**overrides) -> dict:
    entry = {
        "evidenceId": "EVT_TEST_A_E01_DLG0001",
        "evidenceType": "dialogue",
        "storyId": "EVT_TEST_A",
        "publicStoryId": None,
        "episodeId": "EVT_TEST_A_E01",
        "publicEpisodeId": None,
        "sceneId": None,
        "blockId": None,
        "speaker": None,
        "relatedEntities": [],
        "referencedBy": None,
        "visibility": {"public": True, "rawTextIncluded": False},
        "notes": None,
    }
    entry.update(overrides)
    return entry


def _minimal_document(**overrides) -> dict:
    data = {
        "evidenceIndexVersion": 1,
        "generatedFrom": None,
        "entries": [_minimal_entry()],
        "notes": None,
    }
    data.update(overrides)
    return data


def _minimal_story_summary(**overrides) -> dict:
    data = {
        "schemaVersion": "0.1.0",
        "documentType": "story_summary",
        "storyId": "EVT_TEST_A",
        "publicStoryId": None,
        "language": "ja",
        "generationStatus": "generated",
        "storySummary": {
            "text": "合成テスト用のStory Summaryです。",
            "confidence": 0.5,
            "evidenceRefs": ["EVT_TEST_A_E01_DLG0001"],
        },
        "episodeSummaries": [],
        "source": {
            "sourceType": "manual",
            "model": None,
            "promptVersion": None,
            "generatedAt": None,
            "inputRefs": [],
        },
        "review": {
            "status": "reviewed",
            "reviewer": "synthetic_reviewer",
            "reviewedAt": "2026-07-08",
            "notes": None,
        },
        "notes": None,
    }
    data.update(overrides)
    return data


def _write(path: Path, data: dict) -> Path:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)
    return path


def _run_cli(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *extra_args],
        capture_output=True,
        text=True,
    )


# ----------------------------------------------------------------
# Basic pass/fail
# ----------------------------------------------------------------


def test_valid_public_default_evidence_index_passes(tmp_path):
    path = _write(tmp_path / "valid.yaml", _minimal_document())
    result = _run_cli("--input", str(path))
    assert result.returncode == 0, result.stderr


def test_missing_input_path_exits_two(tmp_path):
    result = _run_cli("--input", str(tmp_path / "does_not_exist"))
    assert result.returncode == 2


def test_missing_schema_path_exits_two(tmp_path):
    path = _write(tmp_path / "valid.yaml", _minimal_document())
    result = _run_cli(
        "--input", str(path), "--schema", str(tmp_path / "does_not_exist.json")
    )
    assert result.returncode == 2


# ----------------------------------------------------------------
# Entry type policy (public-default)
# ----------------------------------------------------------------


def test_stage_direction_entry_fails_with_dedicated_message(tmp_path):
    path = _write(
        tmp_path / "stage_direction.yaml",
        _minimal_document(
            entries=[
                _minimal_entry(
                    evidenceId="EVT_TEST_A_E01_STAGE0001",
                    evidenceType="stage_direction",
                )
            ]
        ),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1
    assert "stage_direction" in result.stderr


def test_scene_episode_story_speaker_label_entries_fail(tmp_path):
    for evidence_type in ("scene", "episode", "story", "speaker_label"):
        path = _write(
            tmp_path / f"{evidence_type}.yaml",
            _minimal_document(
                entries=[
                    _minimal_entry(
                        evidenceId=f"EVT_TEST_A_E01_{evidence_type.upper()}0001",
                        evidenceType=evidence_type,
                    )
                ]
            ),
        )
        result = _run_cli("--input", str(path))
        assert result.returncode == 1, f"{evidence_type} should fail"


def test_allowed_types_all_pass(tmp_path):
    for evidence_type in ("dialogue", "monologue", "narration", "choice", "unknown"):
        path = _write(
            tmp_path / f"{evidence_type}.yaml",
            _minimal_document(
                entries=[
                    _minimal_entry(
                        evidenceId=f"EVT_TEST_A_E01_{evidence_type.upper()}0001",
                        evidenceType=evidence_type,
                    )
                ]
            ),
        )
        result = _run_cli("--input", str(path))
        assert result.returncode == 0, f"{evidence_type} should pass: {result.stderr}"


# ----------------------------------------------------------------
# Visibility / structural validation (validate_evidence_index_collectionの再利用)
# ----------------------------------------------------------------


def test_raw_text_included_true_fails(tmp_path):
    path = _write(
        tmp_path / "bad_visibility.yaml",
        _minimal_document(
            entries=[
                _minimal_entry(visibility={"public": True, "rawTextIncluded": True})
            ]
        ),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1


def test_visibility_public_false_fails(tmp_path):
    path = _write(
        tmp_path / "bad_public.yaml",
        _minimal_document(
            entries=[
                _minimal_entry(visibility={"public": False, "rawTextIncluded": False})
            ]
        ),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1


def test_duplicate_evidence_id_fails(tmp_path):
    path = _write(
        tmp_path / "dup.yaml",
        _minimal_document(
            entries=[
                _minimal_entry(evidenceId="EVT_TEST_A_E01_DLG0001"),
                _minimal_entry(evidenceId="EVT_TEST_A_E01_DLG0001"),
            ]
        ),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1


# ----------------------------------------------------------------
# Source text exposure check (ファイル全文scan)
# ----------------------------------------------------------------


def test_raw_command_in_notes_fails(tmp_path):
    path = _write(
        tmp_path / "bad_command.yaml",
        _minimal_document(
            entries=[_minimal_entry(notes="この文章には @ChTalk が混入しています。")]
        ),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1


def test_local_path_in_notes_fails(tmp_path):
    path = _write(
        tmp_path / "bad_path.yaml",
        _minimal_document(
            entries=[_minimal_entry(notes="C:\\Users\\example\\raw\\script.dec")]
        ),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1


def test_dec_extension_in_notes_fails(tmp_path):
    path = _write(
        tmp_path / "bad_dec.yaml",
        _minimal_document(entries=[_minimal_entry(notes="event_001.dec由来")]),
    )
    result = _run_cli("--input", str(path))
    assert result.returncode == 1


# ----------------------------------------------------------------
# Report generation
# ----------------------------------------------------------------


def test_report_markdown_is_generated(tmp_path):
    path = _write(tmp_path / "valid.yaml", _minimal_document())
    report_path = tmp_path / "report.md"
    result = _run_cli("--input", str(path), "--report", str(report_path))
    assert result.returncode == 0, result.stderr
    assert report_path.is_file()
    content = report_path.read_text(encoding="utf-8")
    assert "Evidence Index Promotion Check Report" in content
    assert "Final Decision" in content


def test_report_includes_entries_by_type(tmp_path):
    path = _write(
        tmp_path / "valid.yaml",
        _minimal_document(
            entries=[
                _minimal_entry(
                    evidenceId="EVT_TEST_A_E01_DLG0001", evidenceType="dialogue"
                ),
                _minimal_entry(
                    evidenceId="EVT_TEST_A_E01_NAR0001", evidenceType="narration"
                ),
            ]
        ),
    )
    report_path = tmp_path / "report.md"
    result = _run_cli("--input", str(path), "--report", str(report_path))
    assert result.returncode == 0, result.stderr
    content = report_path.read_text(encoding="utf-8")
    assert "Entries by evidenceType" in content
    assert "dialogue: 1" in content
    assert "narration: 1" in content


def test_report_records_failed_policy_check(tmp_path):
    path = _write(
        tmp_path / "bad.yaml",
        _minimal_document(
            entries=[
                _minimal_entry(
                    evidenceId="EVT_TEST_A_E01_STAGE0001",
                    evidenceType="stage_direction",
                )
            ]
        ),
    )
    report_path = tmp_path / "report.md"
    result = _run_cli("--input", str(path), "--report", str(report_path))
    assert result.returncode == 1
    content = report_path.read_text(encoding="utf-8")
    assert "FAIL" in content
    assert "stage_direction" in content


# ----------------------------------------------------------------
# Summary evidenceRefs consistency (--story-summaries)
# ----------------------------------------------------------------


def test_all_summary_evidence_refs_resolved_no_warning(tmp_path):
    evidence_path = _write(tmp_path / "evidence.yaml", _minimal_document())
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    _write(summaries_dir / "story.yaml", _minimal_story_summary())

    result = _run_cli(
        "--input", str(evidence_path), "--story-summaries", str(summaries_dir)
    )
    assert result.returncode == 0, result.stderr
    assert "警告" not in result.stdout


def test_missing_summary_evidence_ref_is_warning_not_failure(tmp_path):
    evidence_path = _write(tmp_path / "evidence.yaml", _minimal_document())
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    _write(
        summaries_dir / "story.yaml",
        _minimal_story_summary(
            storySummary={
                "text": "合成テスト用のStory Summaryです。",
                "confidence": 0.5,
                "evidenceRefs": ["EVT_TEST_A_E01_DLG9999"],
            }
        ),
    )

    result = _run_cli(
        "--input", str(evidence_path), "--story-summaries", str(summaries_dir)
    )
    assert result.returncode == 0, result.stderr
    assert "警告" in result.stdout


def test_unreviewed_summary_is_ignored(tmp_path):
    evidence_path = _write(tmp_path / "evidence.yaml", _minimal_document())
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    _write(
        summaries_dir / "story.yaml",
        _minimal_story_summary(
            storySummary={
                "text": "合成テスト用のStory Summaryです。",
                "confidence": 0.5,
                "evidenceRefs": ["EVT_TEST_A_E01_DLG9999"],
            },
            review={
                "status": "unreviewed",
                "reviewer": None,
                "reviewedAt": None,
                "notes": None,
            },
        ),
    )

    result = _run_cli(
        "--input", str(evidence_path), "--story-summaries", str(summaries_dir)
    )
    assert result.returncode == 0, result.stderr
    assert "警告" not in result.stdout


def test_deprecated_generation_status_summary_is_ignored(tmp_path):
    evidence_path = _write(tmp_path / "evidence.yaml", _minimal_document())
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()
    _write(
        summaries_dir / "story.yaml",
        _minimal_story_summary(
            generationStatus="deprecated",
            storySummary={
                "text": "合成テスト用のStory Summaryです。",
                "confidence": 0.5,
                "evidenceRefs": ["EVT_TEST_A_E01_DLG9999"],
            },
        ),
    )

    result = _run_cli(
        "--input", str(evidence_path), "--story-summaries", str(summaries_dir)
    )
    assert result.returncode == 0, result.stderr
    assert "警告" not in result.stdout


def test_no_story_summaries_flag_skips_summary_check(tmp_path):
    path = _write(tmp_path / "valid.yaml", _minimal_document())
    report_path = tmp_path / "report.md"
    result = _run_cli("--input", str(path), "--report", str(report_path))
    assert result.returncode == 0, result.stderr
    content = report_path.read_text(encoding="utf-8")
    assert "Summary evidenceRefs Consistency" not in content
