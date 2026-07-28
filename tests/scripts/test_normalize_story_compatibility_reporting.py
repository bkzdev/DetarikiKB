"""normalize_story.pyの互換性レポート出力先指定を検証する。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import scripts.normalize_story as normalize_story

PROJECT_ROOT = Path(__file__).parent.parent.parent
NORMALIZE_SCRIPT = PROJECT_ROOT / "scripts" / "normalize_story.py"


def _write_synthetic_script(tmp_path: Path) -> Path:
    input_path = tmp_path / "synthetic.dec"
    input_path.write_text("msg\nこれは合成テスト用の本文です。\n", encoding="utf-8")
    return input_path


def _required_cli_args(input_path: Path, output_dir: Path) -> list[str]:
    return [
        sys.executable,
        str(NORMALIZE_SCRIPT),
        "--input",
        str(input_path),
        "--story-id",
        "TEST_COMPAT_REPORT",
        "--episode-id",
        "TEST_COMPAT_REPORT_E01",
        "--category",
        "OTHER",
        "--output",
        str(output_dir),
        "--quiet",
    ]


def test_cli_writes_compatibility_reports_to_custom_directory(tmp_path):
    input_path = _write_synthetic_script(tmp_path)
    normalized_dir = tmp_path / "normalized"
    report_dir = tmp_path / "dry_run" / "reports"

    result = subprocess.run(
        [
            *_required_cli_args(input_path, normalized_dir),
            "--check-compat",
            "--compat-report-output",
            str(report_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (normalized_dir / "TEST_COMPAT_REPORT_E01.json").is_file()
    json_report = report_dir / "script_compatibility_report.json"
    assert json_report.is_file()
    assert (report_dir / "script_compatibility_report.md").is_file()
    report = json.loads(json_report.read_text(encoding="utf-8"))
    assert report["summary"]["totalFiles"] == 1


def test_cli_rejects_report_output_without_check_compat(tmp_path):
    input_path = _write_synthetic_script(tmp_path)
    report_dir = tmp_path / "reports"

    result = subprocess.run(
        [
            *_required_cli_args(input_path, tmp_path / "normalized"),
            "--compat-report-output",
            str(report_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "--compat-report-output" in result.stderr
    assert "--check-compat" in result.stderr
    assert not report_dir.exists()


def test_embedded_check_forwards_custom_report_output(monkeypatch, tmp_path):
    report_dir = tmp_path / "reports"
    args = argparse.Namespace(
        check_compat=True,
        quiet=True,
        characters=str(normalize_story.DEFAULT_CHARACTERS_PATH),
        commands=str(normalize_story.DEFAULT_COMMANDS_CONFIG),
        compat_report_output=str(report_dir),
    )
    captured_command: list[str] = []

    def fake_run(command, **kwargs):
        captured_command.extend(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert normalize_story._run_compatibility_check(args, Path("synthetic.dec")) is None
    output_index = captured_command.index("--output")
    assert captured_command[output_index + 1] == str(report_dir)


def test_embedded_check_preserves_checker_default_when_output_is_omitted(
    monkeypatch,
):
    args = argparse.Namespace(
        check_compat=True,
        quiet=True,
        characters=str(normalize_story.DEFAULT_CHARACTERS_PATH),
        commands=str(normalize_story.DEFAULT_COMMANDS_CONFIG),
        compat_report_output=None,
    )
    captured_command: list[str] = []

    def fake_run(command, **kwargs):
        captured_command.extend(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert normalize_story._run_compatibility_check(args, Path("synthetic.dec")) is None
    assert "--output" not in captured_command


def test_embedded_check_is_not_run_when_disabled(monkeypatch):
    args = argparse.Namespace(check_compat=False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called")

    monkeypatch.setattr(subprocess, "run", fail_if_called)

    assert normalize_story._run_compatibility_check(args, Path("synthetic.dec")) is None
