"""audit_candidate_ids.py CLIの終了コード・匿名性・出力保護を検証する。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "audit_candidate_ids.py"
EPISODE_ID = "SENSITIVE_CLI_EPISODE_SENTINEL"
EVIDENCE_ID = "SENSITIVE_CLI_EVIDENCE_SENTINEL"


def _normalized() -> dict:
    return {
        "episodes": [
            {
                "episodeId": EPISODE_ID,
                "scenes": [
                    {
                        "sceneId": "SENSITIVE_CLI_SCENE_SENTINEL",
                        "blocks": [{"id": EVIDENCE_ID, "type": "dialogue"}],
                    }
                ],
            }
        ]
    }


def _extraction(*, candidate_number: str = "001") -> dict:
    return {
        "episodeId": EPISODE_ID,
        "extractionRun": {"extractionMethod": "rule_based"},
        "characters": [
            {
                "id": f"{EPISODE_ID}_CAND_CHAR{candidate_number}",
                "type": "character_candidate",
                "evidenceIds": [EVIDENCE_ID],
            }
        ],
        "organizations": [],
        "locations": [],
        "items": [],
        "lore": [],
        "events": [],
        "relationships": [],
        "timelineCandidates": [],
        "specialSpeakerLabelCandidates": [],
    }


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _run_cli(*args: Path | str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *(str(arg) for arg in args)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        check=False,
    )


def test_cli_writes_anonymous_report_is_quiet_and_does_not_clobber(tmp_path: Path):
    extraction_path = tmp_path / "extraction.json"
    normalized_path = tmp_path / "normalized.json"
    report_path = tmp_path / "report.json"
    _write_json(extraction_path, _extraction())
    _write_json(normalized_path, _normalized())

    result = _run_cli(
        "--input",
        extraction_path,
        "--normalized-input",
        normalized_path,
        "--comparison-input",
        extraction_path,
        "--report-output",
        report_path,
    )

    assert result.returncode == 0
    assert "status=pass" in result.stdout
    report_text = report_path.read_text(encoding="utf-8")
    for sentinel in (EPISODE_ID, EVIDENCE_ID, str(extraction_path)):
        assert sentinel not in result.stdout
        assert sentinel not in result.stderr
        assert sentinel not in report_text

    original_report = report_text
    clobber_result = _run_cli(
        "--input",
        extraction_path,
        "--normalized-input",
        normalized_path,
        "--report-output",
        report_path,
    )
    assert clobber_result.returncode == 2
    assert report_path.read_text(encoding="utf-8") == original_report

    quiet_result = _run_cli(
        "--input",
        extraction_path,
        "--normalized-input",
        normalized_path,
        "--quiet",
    )
    assert quiet_result.returncode == 0
    assert quiet_result.stdout == ""
    assert quiet_result.stderr == ""


def test_cli_returns_one_for_contract_failure_without_identifier_leak(
    tmp_path: Path,
):
    extraction_path = tmp_path / "extraction.json"
    normalized_path = tmp_path / "normalized.json"
    extraction = _extraction(candidate_number="000")
    extraction["extractionRun"]["extractionMethod"] = "manual"
    _write_json(extraction_path, extraction)
    _write_json(normalized_path, _normalized())

    result = _run_cli(
        "--input",
        extraction_path,
        "--normalized-input",
        normalized_path,
    )

    assert result.returncode == 1
    assert "status=fail" in result.stdout
    assert EPISODE_ID not in result.stdout + result.stderr
    assert EVIDENCE_ID not in result.stdout + result.stderr


def test_cli_returns_two_without_path_leak_and_rejects_unsafe_outputs(
    tmp_path: Path,
):
    input_directory = tmp_path / "SENSITIVE_INPUT_DIRECTORY_SENTINEL"
    extraction_path = input_directory / "extraction.json"
    normalized_path = tmp_path / "normalized.json"
    _write_json(extraction_path, _extraction())
    _write_json(normalized_path, _normalized())

    nested_report = input_directory / "report.json"
    nested_result = _run_cli(
        "--input",
        input_directory,
        "--normalized-input",
        normalized_path,
        "--report-output",
        nested_report,
    )
    assert nested_result.returncode == 2
    assert not nested_report.exists()
    assert "SENSITIVE_INPUT_DIRECTORY_SENTINEL" not in (
        nested_result.stdout + nested_result.stderr
    )

    forbidden_repo_report = PROJECT_ROOT / "candidate_id_audit_forbidden_test.json"
    repo_result = _run_cli(
        "--input",
        extraction_path,
        "--normalized-input",
        normalized_path,
        "--report-output",
        forbidden_repo_report,
    )
    assert repo_result.returncode == 2
    assert not forbidden_repo_report.exists()

    malformed_path = tmp_path / "SENSITIVE_MALFORMED_PATH_SENTINEL.json"
    malformed_path.write_text("{", encoding="utf-8")
    malformed_result = _run_cli(
        "--input",
        malformed_path,
        "--normalized-input",
        normalized_path,
    )
    assert malformed_result.returncode == 2
    assert "SENSITIVE_MALFORMED_PATH_SENTINEL" not in (
        malformed_result.stdout + malformed_result.stderr
    )

    malformed_extraction = _extraction()
    malformed_extraction["extractionRun"] = "SENSITIVE_STRUCTURE_SENTINEL"
    _write_json(extraction_path, malformed_extraction)
    structure_result = _run_cli(
        "--input",
        extraction_path,
        "--normalized-input",
        normalized_path,
    )
    assert structure_result.returncode == 2
    assert "Traceback" not in structure_result.stderr
    assert "SENSITIVE_STRUCTURE_SENTINEL" not in structure_result.stderr

    _write_json(extraction_path, _extraction())
    _write_json(
        normalized_path,
        {
            "storyId": "SENSITIVE_STRUCTURE_SENTINEL",
            "episodes": ["SENSITIVE_STRUCTURE_SENTINEL"],
        },
    )
    normalized_structure_result = _run_cli(
        "--input",
        extraction_path,
        "--normalized-input",
        normalized_path,
    )
    assert normalized_structure_result.returncode == 2
    assert "Traceback" not in normalized_structure_result.stderr
    assert "SENSITIVE_STRUCTURE_SENTINEL" not in normalized_structure_result.stderr
