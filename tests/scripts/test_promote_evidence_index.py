"""
tests/scripts/test_promote_evidence_index.py
scripts/promote_evidence_index.py のCLIテスト。

promotion checkをPASSしたEvidence Index候補をknowledge/evidence/stories/
相当のtargetへ安全にcopyするgatekeeper scriptを検証する。合成データのみを
一時ファイルとして生成して使う。targetは必ずtmp_path配下
(--allow-nonstandard-target)を使い、実際のknowledge/evidence/stories/へは
一切書き込まない。実データ・実データ由来fixtureは一切使わない。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "promote_evidence_index.py"


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


def _write(path: Path, data: dict) -> Path:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)
    return path


def _review_note(path: Path, decision: str = "approved") -> Path:
    boxes = {
        "approved": (
            "- [x] Approved for promotion\n- [ ] Needs revision\n- [ ] Rejected"
        ),
        "needs_revision": (
            "- [ ] Approved for promotion\n- [x] Needs revision\n- [ ] Rejected"
        ),
        "rejected": (
            "- [ ] Approved for promotion\n- [ ] Needs revision\n- [x] Rejected"
        ),
        "undecided": (
            "- [ ] Approved for promotion\n- [ ] Needs revision\n- [ ] Rejected"
        ),
    }[decision]
    path.write_text(
        f"# Evidence Index Promotion Review\n\n## Decision\n\n{boxes}\n\n## Notes\n",
        encoding="utf-8",
    )
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
    review_note_path: Path | None = None,
    target: Path | None = None,
) -> list[str]:
    if input_path is None:
        input_path = _write(tmp_path / "input.yaml", _minimal_document())
    if review_note_path is None:
        review_note_path = _review_note(tmp_path / "review_note.md")
    if target is None:
        target = tmp_path / "target"
    return [
        "--input",
        str(input_path),
        "--review-note",
        str(review_note_path),
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
# execute
# ----------------------------------------------------------------


def test_execute_copies_to_target(tmp_path):
    target = tmp_path / "target"
    result = _run_cli(*_base_args(tmp_path, target=target), "--execute")
    assert result.returncode == 0, result.stderr
    assert (target / "EVT_TEST_A.yaml").is_file()


def test_execute_without_flag_never_writes(tmp_path):
    target = tmp_path / "target"
    result = _run_cli(*_base_args(tmp_path, target=target))
    assert result.returncode == 0, result.stderr
    assert not (target / "EVT_TEST_A.yaml").exists()


def test_target_directory_created_on_execute(tmp_path):
    target = tmp_path / "nested" / "target"
    assert not target.exists()
    result = _run_cli(*_base_args(tmp_path, target=target), "--execute")
    assert result.returncode == 0, result.stderr
    assert target.is_dir()


# ----------------------------------------------------------------
# review note requirement
# ----------------------------------------------------------------


def test_missing_review_note_exits_two(tmp_path):
    result = _run_cli(
        "--input",
        str(_write(tmp_path / "input.yaml", _minimal_document())),
        "--review-note",
        str(tmp_path / "does_not_exist.md"),
        "--target",
        str(tmp_path / "target"),
        "--allow-nonstandard-target",
    )
    assert result.returncode == 2


def test_undecided_review_note_fails(tmp_path):
    review_note_path = _review_note(tmp_path / "review_note.md", decision="undecided")
    result = _run_cli(
        *_base_args(tmp_path, review_note_path=review_note_path), "--execute"
    )
    assert result.returncode == 1
    assert not (tmp_path / "target" / "EVT_TEST_A.yaml").exists()


def test_needs_revision_review_note_fails(tmp_path):
    review_note_path = _review_note(
        tmp_path / "review_note.md", decision="needs_revision"
    )
    result = _run_cli(
        *_base_args(tmp_path, review_note_path=review_note_path), "--execute"
    )
    assert result.returncode == 1
    assert not (tmp_path / "target" / "EVT_TEST_A.yaml").exists()


def test_rejected_review_note_fails(tmp_path):
    review_note_path = _review_note(tmp_path / "review_note.md", decision="rejected")
    result = _run_cli(
        *_base_args(tmp_path, review_note_path=review_note_path), "--execute"
    )
    assert result.returncode == 1
    assert not (tmp_path / "target" / "EVT_TEST_A.yaml").exists()


def test_actual_review_template_is_not_falsely_flagged_for_source_text(tmp_path):
    """docs/templates/evidence_index_promotion_review_template.mdの
    チェックリスト自体 (`no `.dec``等) が禁止文字列scanで誤検知されない
    ことを確認する (承認チェックが無いため実際には未承認でfailするが、
    その理由がsource text issueではないことを確認する)。"""
    template_path = (
        PROJECT_ROOT
        / "docs"
        / "templates"
        / "evidence_index_promotion_review_template.md"
    )
    result = _run_cli(*_base_args(tmp_path, review_note_path=template_path))
    assert "source text exposure" not in result.stderr


def test_review_note_with_real_command_text_fails(tmp_path):
    review_note_path = tmp_path / "bad_review_note.md"
    review_note_path.write_text(
        "# Evidence Index Promotion Review\n\n"
        "## Decision\n\n"
        "- [x] Approved for promotion\n"
        "- [ ] Needs revision\n"
        "- [ ] Rejected\n\n"
        "## Notes\n\nこのnoteには @ChTalk が混入しています。\n",
        encoding="utf-8",
    )
    result = _run_cli(
        *_base_args(tmp_path, review_note_path=review_note_path), "--execute"
    )
    assert result.returncode == 1
    assert not (tmp_path / "target" / "EVT_TEST_A.yaml").exists()


# ----------------------------------------------------------------
# promotion check reuse (stage_direction等の除外type)
# ----------------------------------------------------------------


def test_stage_direction_input_fails_promotion_check(tmp_path):
    input_path = _write(
        tmp_path / "input.yaml",
        _minimal_document(
            entries=[
                _minimal_entry(
                    evidenceId="EVT_TEST_A_E01_STAGE0001",
                    evidenceType="stage_direction",
                )
            ]
        ),
    )
    result = _run_cli(*_base_args(tmp_path, input_path=input_path), "--execute")
    assert result.returncode == 1
    assert not (tmp_path / "target" / "EVT_TEST_A.yaml").exists()


# ----------------------------------------------------------------
# overwrite policy
# ----------------------------------------------------------------


def test_overwrite_conflict_without_flag_fails(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "EVT_TEST_A.yaml").write_text("existing: true\n", encoding="utf-8")

    result = _run_cli(*_base_args(tmp_path, target=target), "--execute")
    assert result.returncode == 1
    assert (target / "EVT_TEST_A.yaml").read_text(
        encoding="utf-8"
    ) == "existing: true\n"


def test_overwrite_with_flag_succeeds(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "EVT_TEST_A.yaml").write_text("existing: true\n", encoding="utf-8")

    result = _run_cli(*_base_args(tmp_path, target=target), "--execute", "--overwrite")
    assert result.returncode == 0, result.stderr
    assert (target / "EVT_TEST_A.yaml").read_text(
        encoding="utf-8"
    ) != "existing: true\n"


# ----------------------------------------------------------------
# 1 file 1 story policy
# ----------------------------------------------------------------


def test_multiple_story_ids_in_one_file_is_skipped(tmp_path):
    input_path = _write(
        tmp_path / "input.yaml",
        _minimal_document(
            entries=[
                _minimal_entry(
                    evidenceId="EVT_TEST_A_E01_DLG0001", storyId="EVT_TEST_A"
                ),
                _minimal_entry(
                    evidenceId="EVT_TEST_B_E01_DLG0001", storyId="EVT_TEST_B"
                ),
            ]
        ),
    )
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1
    assert "複数のstoryId" in result.stderr


def test_multiple_files_input_all_planned(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(
        input_dir / "story_a.yaml",
        _minimal_document(
            entries=[
                _minimal_entry(
                    evidenceId="EVT_TEST_A_E01_DLG0001", storyId="EVT_TEST_A"
                )
            ]
        ),
    )
    _write(
        input_dir / "story_b.yaml",
        _minimal_document(
            entries=[
                _minimal_entry(
                    evidenceId="EVT_TEST_B_E01_DLG0001", storyId="EVT_TEST_B"
                )
            ]
        ),
    )
    result = _run_cli(*_base_args(tmp_path, input_path=input_dir))
    assert result.returncode == 0, result.stderr
    assert "EVT_TEST_A.yaml" in result.stdout
    assert "EVT_TEST_B.yaml" in result.stdout


def test_non_yaml_files_in_directory_are_ignored(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _write(input_dir / "story_a.yaml", _minimal_document())
    (input_dir / "notes.txt").write_text("not yaml", encoding="utf-8")
    result = _run_cli(*_base_args(tmp_path, input_path=input_dir))
    assert result.returncode == 0, result.stderr


# ----------------------------------------------------------------
# Report generation
# ----------------------------------------------------------------


def test_report_markdown_is_generated_dry_run(tmp_path):
    report_path = tmp_path / "report.md"
    result = _run_cli(*_base_args(tmp_path), "--report", str(report_path))
    assert result.returncode == 0, result.stderr
    assert report_path.is_file()
    content = report_path.read_text(encoding="utf-8")
    assert "Evidence Index Promotion Copy Report" in content
    assert "Mode: dry-run" in content
    assert "Final Decision" in content


def test_report_includes_planned_copies(tmp_path):
    report_path = tmp_path / "report.md"
    result = _run_cli(*_base_args(tmp_path), "--report", str(report_path))
    assert result.returncode == 0, result.stderr
    content = report_path.read_text(encoding="utf-8")
    assert "Planned copies" in content
    assert "EVT_TEST_A.yaml" in content


def test_report_includes_copied_files_on_execute(tmp_path):
    report_path = tmp_path / "report.md"
    result = _run_cli(*_base_args(tmp_path), "--report", str(report_path), "--execute")
    assert result.returncode == 0, result.stderr
    content = report_path.read_text(encoding="utf-8")
    assert "Mode: execute" in content
    assert "Copied files" in content
    assert "EVT_TEST_A.yaml" in content


def test_report_includes_post_copy_validation_on_execute(tmp_path):
    report_path = tmp_path / "report.md"
    result = _run_cli(*_base_args(tmp_path), "--report", str(report_path), "--execute")
    assert result.returncode == 0, result.stderr
    content = report_path.read_text(encoding="utf-8")
    assert "Post-copy validation" in content
    assert "Result: PASS" in content


def test_report_records_skipped_files(tmp_path):
    input_path = _write(
        tmp_path / "input.yaml",
        _minimal_document(
            entries=[
                _minimal_entry(
                    evidenceId="EVT_TEST_A_E01_DLG0001", storyId="EVT_TEST_A"
                ),
                _minimal_entry(
                    evidenceId="EVT_TEST_B_E01_DLG0001", storyId="EVT_TEST_B"
                ),
            ]
        ),
    )
    report_path = tmp_path / "report.md"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path), "--report", str(report_path)
    )
    assert result.returncode == 1
    content = report_path.read_text(encoding="utf-8")
    assert "Skipped files" in content


def test_report_records_overwrite_conflicts(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "EVT_TEST_A.yaml").write_text("existing: true\n", encoding="utf-8")
    report_path = tmp_path / "report.md"
    result = _run_cli(
        *_base_args(tmp_path, target=target), "--report", str(report_path)
    )
    assert result.returncode == 1
    content = report_path.read_text(encoding="utf-8")
    assert "Overwrite conflicts" in content
    assert "EVT_TEST_A.yaml" in content


# ----------------------------------------------------------------
# Path / config errors
# ----------------------------------------------------------------


def test_missing_input_path_exits_two(tmp_path):
    result = _run_cli(
        "--input",
        str(tmp_path / "does_not_exist"),
        "--review-note",
        str(_review_note(tmp_path / "review_note.md")),
        "--target",
        str(tmp_path / "target"),
        "--allow-nonstandard-target",
    )
    assert result.returncode == 2


def test_missing_schema_path_exits_two(tmp_path):
    result = _run_cli(
        *_base_args(tmp_path), "--schema", str(tmp_path / "does_not_exist.json")
    )
    assert result.returncode == 2


def test_nonstandard_target_without_flag_exits_two(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _minimal_document())
    review_note_path = _review_note(tmp_path / "review_note.md")
    result = _run_cli(
        "--input",
        str(input_path),
        "--review-note",
        str(review_note_path),
        "--target",
        str(tmp_path / "target"),
    )
    assert result.returncode == 2
