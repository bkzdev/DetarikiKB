"""
tests/scripts/test_promote_story_summaries.py
scripts/promote_story_summaries.py のCLIテスト。

Public-safe projection・review/品質ゲートを通過したStory Summary候補を
knowledge/summaries/stories/相当のtargetへ安全にcopyするgatekeeper scriptを
検証する。合成データのみを一時ファイルとして生成して使う。targetは必ず
tmp_path配下（--allow-nonstandard-target）を使い、実際の
knowledge/summaries/stories/へは一切書き込まない。実データ・実データ由来
fixtureは一切使わない。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "promote_story_summaries.py"


# ----------------------------------------------------------------
# Fixture builders (合成データのみ)
# ----------------------------------------------------------------


def _minimal_summary(**overrides) -> dict:
    """public-safe projection済み・review承認済み・generated済みの、
    そのまま昇格可能なStory Summary document。"""
    data = {
        "schemaVersion": "0.1.0",
        "documentType": "story_summary",
        "storyId": "EVT_TEST_A",
        "publicStoryId": "EVT_TEST_A",
        "language": "ja",
        "generationStatus": "generated",
        "storySummary": {
            "text": "合成テスト用のStory Summaryです。",
            "confidence": 0.5,
            "evidenceRefs": ["EVT_TEST_A_E01_DLG0001"],
        },
        "episodeSummaries": [
            {
                "episodeId": "EVT_TEST_A_E01",
                "publicEpisodeId": "EVT_TEST_A_E01",
                "episodeNumber": 1,
                "text": "Episode 1のあらすじです。",
                "confidence": 0.5,
                "evidenceRefs": ["EVT_TEST_A_E01_DLG0001"],
            }
        ],
        "source": {
            "sourceType": "ai_generated",
            "model": None,
            "promptVersion": None,
            "generatedAt": None,
            "inputRefs": [],
        },
        "review": {
            "status": "approved",
            "reviewer": "tester",
            "reviewedAt": "2026-07-13",
            "notes": None,
        },
        "notes": None,
    }
    data.update(overrides)
    return data


def _minimal_registry(**overrides) -> dict:
    data = {
        "registryVersion": 1,
        "stories": [
            {
                "publicStoryId": "EVT_TEST_A",
                "category": "event",
                "episodes": [
                    {"publicEpisodeId": "EVT_TEST_A_E01", "episodeOrder": 1},
                ],
            }
        ],
    }
    data.update(overrides)
    return data


def _minimal_evidence_entry(**overrides) -> dict:
    entry = {
        "evidenceId": "EVT_TEST_A_E01_DLG0001",
        "evidenceType": "dialogue",
        "storyId": "EVT_TEST_A",
        "publicStoryId": "EVT_TEST_A",
        "episodeId": "EVT_TEST_A_E01",
        "publicEpisodeId": "EVT_TEST_A_E01",
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


def _minimal_evidence_index(**overrides) -> dict:
    data = {
        "evidenceIndexVersion": 1,
        "generatedFrom": None,
        "entries": [_minimal_evidence_entry()],
        "notes": None,
    }
    data.update(overrides)
    return data


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    return path


def _run_cli(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *extra_args],
        capture_output=True,
        text=True,
    )


def _base_args(
    tmp_path: Path,
    *,
    input_path: Path | None = None,
    target: Path | None = None,
) -> list[str]:
    if input_path is None:
        input_path = _write(tmp_path / "EVT_TEST_A.yaml", _minimal_summary())
    if target is None:
        target = tmp_path / "target"
    return [
        "--input",
        str(input_path),
        "--target",
        str(target),
        "--allow-nonstandard-target",
    ]


# ----------------------------------------------------------------
# dry-run default
# ----------------------------------------------------------------


def test_dry_run_does_not_copy(tmp_path):
    target = tmp_path / "target"
    result = _run_cli(*_base_args(tmp_path, target=target))
    assert result.returncode == 0, result.stderr
    assert "DRY RUN" in result.stdout
    assert not target.exists() or list(target.iterdir()) == []


def test_dry_run_reports_would_copy(tmp_path):
    target = tmp_path / "target"
    result = _run_cli(*_base_args(tmp_path, target=target))
    assert result.returncode == 0, result.stderr
    assert "Would copy:" in result.stdout
    assert "-> " in result.stdout


# ----------------------------------------------------------------
# execute (normal copy)
# ----------------------------------------------------------------


def test_execute_copies_to_target(tmp_path):
    target = tmp_path / "target"
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", _minimal_summary())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, target=target), "--execute"
    )
    assert result.returncode == 0, result.stderr
    copied = target / "EVT_TEST_A.yaml"
    assert copied.is_file()
    assert copied.read_bytes() == input_path.read_bytes()


def test_execute_without_flag_never_writes(tmp_path):
    target = tmp_path / "target"
    result = _run_cli(*_base_args(tmp_path, target=target))
    assert result.returncode == 0, result.stderr
    assert not target.exists() or list(target.iterdir()) == []


# ----------------------------------------------------------------
# Precondition 1: public-safe projection
# ----------------------------------------------------------------


def test_missing_public_story_id_is_skipped(tmp_path):
    input_path = _write(
        tmp_path / "EVT_TEST_A.yaml", _minimal_summary(publicStoryId=None)
    )
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout
    assert "skipped 1" in result.stderr


def test_story_id_public_story_id_mismatch_is_skipped(tmp_path):
    input_path = _write(
        tmp_path / "EVT_TEST_A.yaml",
        _minimal_summary(publicStoryId="EVT_TEST_B"),
    )
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout


def test_episode_id_public_episode_id_mismatch_is_skipped(tmp_path):
    summary = _minimal_summary()
    summary["episodeSummaries"][0]["publicEpisodeId"] = "EVT_TEST_A_E02"
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", summary)
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout


def test_missing_episode_public_episode_id_is_skipped(tmp_path):
    summary = _minimal_summary()
    summary["episodeSummaries"][0]["publicEpisodeId"] = None
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", summary)
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout


def test_filename_mismatch_is_skipped(tmp_path):
    input_path = _write(tmp_path / "WRONG_FILENAME.yaml", _minimal_summary())
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout


# ----------------------------------------------------------------
# Precondition 2: review.status / generationStatus
# ----------------------------------------------------------------


def test_review_status_unreviewed_is_skipped(tmp_path):
    input_path = _write(
        tmp_path / "EVT_TEST_A.yaml",
        _minimal_summary(review={"status": "unreviewed"}),
    )
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout


def test_review_status_rejected_is_skipped(tmp_path):
    input_path = _write(
        tmp_path / "EVT_TEST_A.yaml",
        _minimal_summary(review={"status": "rejected"}),
    )
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout


def test_review_status_reviewed_is_accepted(tmp_path):
    target = tmp_path / "target"
    input_path = _write(
        tmp_path / "EVT_TEST_A.yaml",
        _minimal_summary(review={"status": "reviewed"}),
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, target=target), "--execute"
    )
    assert result.returncode == 0, result.stderr
    assert (target / "EVT_TEST_A.yaml").is_file()


def test_generation_status_draft_is_skipped(tmp_path):
    input_path = _write(
        tmp_path / "EVT_TEST_A.yaml", _minimal_summary(generationStatus="draft")
    )
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout


# ----------------------------------------------------------------
# Precondition: schema validation
# ----------------------------------------------------------------


def test_schema_violation_is_skipped(tmp_path):
    summary = _minimal_summary()
    del summary["source"]
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", summary)
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout
    assert "skipped 1" in result.stderr


# ----------------------------------------------------------------
# Precondition 3: forbidden text pattern scan
# ----------------------------------------------------------------


def test_forbidden_text_in_story_summary_is_skipped(tmp_path):
    summary = _minimal_summary()
    summary["storySummary"]["text"] = "raw command @ChTalk が含まれています。"
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", summary)
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout


def test_forbidden_text_in_episode_summary_is_skipped(tmp_path):
    summary = _minimal_summary()
    summary["episodeSummaries"][0]["text"] = "local path C:\\Users\\test を含む。"
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", summary)
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout


# ----------------------------------------------------------------
# Precondition 4: Public ID Registry existence check (--registry)
# ----------------------------------------------------------------


def test_registry_missing_public_story_id_is_skipped(tmp_path):
    registry_path = _write(
        tmp_path / "registry.yaml",
        _minimal_registry(stories=[]),
    )
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", _minimal_summary())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 1, result.stdout


def test_registry_missing_public_episode_id_is_skipped(tmp_path):
    registry = _minimal_registry()
    registry["stories"][0]["episodes"] = []
    registry_path = _write(tmp_path / "registry.yaml", registry)
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", _minimal_summary())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 1, result.stdout


def test_registry_present_is_accepted(tmp_path):
    target = tmp_path / "target"
    registry_path = _write(tmp_path / "registry.yaml", _minimal_registry())
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", _minimal_summary())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, target=target),
        "--registry",
        str(registry_path),
        "--execute",
    )
    assert result.returncode == 0, result.stderr
    assert (target / "EVT_TEST_A.yaml").is_file()


def test_missing_registry_path_exits_two(tmp_path):
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", _minimal_summary())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(tmp_path / "does_not_exist.yaml"),
    )
    assert result.returncode == 2, result.stdout


# ----------------------------------------------------------------
# Precondition 5: Evidence Index evidenceRefs resolution (--evidence-index)
# ----------------------------------------------------------------


def test_evidence_refs_unresolved_is_skipped(tmp_path):
    evidence_index_path = _write(
        tmp_path / "evidence.yaml",
        _minimal_evidence_index(
            entries=[_minimal_evidence_entry(evidenceId="EVT_TEST_A_E01_DLG9999")]
        ),
    )
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", _minimal_summary())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--evidence-index",
        str(evidence_index_path),
    )
    assert result.returncode == 1, result.stdout


def test_evidence_refs_resolved_is_accepted(tmp_path):
    target = tmp_path / "target"
    evidence_index_path = _write(tmp_path / "evidence.yaml", _minimal_evidence_index())
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", _minimal_summary())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, target=target),
        "--evidence-index",
        str(evidence_index_path),
        "--execute",
    )
    assert result.returncode == 0, result.stderr
    assert (target / "EVT_TEST_A.yaml").is_file()


def test_empty_evidence_refs_are_accepted(tmp_path):
    """空のevidenceRefsは--evidence-index指定時でも許容される (Plan §4.3.3)。"""
    target = tmp_path / "target"
    evidence_index_path = _write(
        tmp_path / "evidence.yaml", _minimal_evidence_index(entries=[])
    )
    summary = _minimal_summary()
    summary["storySummary"]["evidenceRefs"] = []
    summary["episodeSummaries"][0]["evidenceRefs"] = []
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", summary)
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, target=target),
        "--evidence-index",
        str(evidence_index_path),
        "--execute",
    )
    assert result.returncode == 0, result.stderr
    assert (target / "EVT_TEST_A.yaml").is_file()


def test_missing_evidence_index_path_exits_two(tmp_path):
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", _minimal_summary())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--evidence-index",
        str(tmp_path / "does_not_exist.yaml"),
    )
    assert result.returncode == 2, result.stdout


# ----------------------------------------------------------------
# Overwrite policy
# ----------------------------------------------------------------


def test_overwrite_conflict_without_flag_blocks(tmp_path):
    target = tmp_path / "target"
    target.mkdir(parents=True)
    (target / "EVT_TEST_A.yaml").write_text("existing content", encoding="utf-8")
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", _minimal_summary())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, target=target), "--execute"
    )
    assert result.returncode == 1, result.stdout
    assert "overwrite conflicts" in result.stderr
    # 既存ファイルは書き換えられていないこと
    assert (target / "EVT_TEST_A.yaml").read_text(encoding="utf-8") == (
        "existing content"
    )


def test_overwrite_flag_allows_execute(tmp_path):
    target = tmp_path / "target"
    target.mkdir(parents=True)
    (target / "EVT_TEST_A.yaml").write_text("existing content", encoding="utf-8")
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", _minimal_summary())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, target=target),
        "--overwrite",
        "--execute",
    )
    assert result.returncode == 0, result.stderr
    assert (target / "EVT_TEST_A.yaml").read_bytes() == input_path.read_bytes()


# ----------------------------------------------------------------
# --target restriction
# ----------------------------------------------------------------


def test_nonstandard_target_without_flag_exits_two(tmp_path):
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", _minimal_summary())
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(input_path),
            "--target",
            str(tmp_path / "target"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, result.stdout


# ----------------------------------------------------------------
# Post-copy validation (sanity re-check)
# ----------------------------------------------------------------


def test_post_copy_validation_passes_after_execute(tmp_path):
    target = tmp_path / "target"
    registry_path = _write(tmp_path / "registry.yaml", _minimal_registry())
    evidence_index_path = _write(tmp_path / "evidence.yaml", _minimal_evidence_index())
    report_path = tmp_path / "report.md"
    input_path = _write(tmp_path / "EVT_TEST_A.yaml", _minimal_summary())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, target=target),
        "--registry",
        str(registry_path),
        "--evidence-index",
        str(evidence_index_path),
        "--report",
        str(report_path),
        "--execute",
    )
    assert result.returncode == 0, result.stderr
    report_text = report_path.read_text(encoding="utf-8")
    assert "## Post-copy validation" in report_text
    assert "- Result: PASS" in report_text


# ----------------------------------------------------------------
# Report content
# ----------------------------------------------------------------


def test_report_contains_required_sections(tmp_path):
    target = tmp_path / "target"
    report_path = tmp_path / "report.md"
    result = _run_cli(
        *_base_args(tmp_path, target=target), "--report", str(report_path)
    )
    assert result.returncode == 0, result.stderr
    report_text = report_path.read_text(encoding="utf-8")
    for heading in (
        "## Preconditions",
        "## Planned copies",
        "## Skipped files",
        "## Overwrite conflicts",
        "## Copied files",
        "## Post-copy validation",
        "## Final Decision",
    ):
        assert heading in report_text, heading


def test_report_under_knowledge_dir_exits_two(tmp_path):
    target = tmp_path / "target"
    forbidden_report = PROJECT_ROOT / "knowledge" / "summaries" / "tmp_test_report.md"
    result = _run_cli(
        *_base_args(tmp_path, target=target), "--report", str(forbidden_report)
    )
    assert result.returncode == 2, result.stdout
    assert not forbidden_report.exists()
