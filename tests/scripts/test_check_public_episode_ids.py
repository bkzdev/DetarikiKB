"""
tests/scripts/test_check_public_episode_ids.py
scripts/check_public_episode_ids.py のCLIテスト。

publicEpisodeId未確定のepisodeを検出し、割当候補（suggestion）を
workspace相当のtmp_path配下にのみ提案するcheck-only scriptを検証する。
合成データのみを一時ファイルとして生成して使う。実データ・実データ由来
fixtureは一切使わない。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_public_episode_ids.py"


def _entry(**overrides) -> dict:
    entry = {
        "evidenceId": "EVT_TEST_A_E01_DLG0001",
        "evidenceType": "dialogue",
        "storyId": "EVT_TEST_A",
        "publicStoryId": "PUB_TEST_A",
        "episodeId": "EVT_TEST_A_E01",
        "publicEpisodeId": "PUB_TEST_A_E01",
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


def _document(entries: list[dict] | None = None, **overrides) -> dict:
    data = {
        "evidenceIndexVersion": 1,
        "generatedFrom": None,
        "entries": entries if entries is not None else [_entry()],
        "notes": None,
    }
    data.update(overrides)
    return data


def _write(path: Path, data: dict) -> Path:
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
    report: Path | None = None,
    suggestions_output: Path | None = None,
    extra: list[str] | None = None,
) -> list[str]:
    if input_path is None:
        input_path = _write(tmp_path / "input.yaml", _document())
    if report is None:
        report = tmp_path / "report.md"
    if suggestions_output is None:
        suggestions_output = tmp_path / "suggestions.yaml"
    args = [
        "--input",
        str(input_path),
        "--report",
        str(report),
        "--suggestions-output",
        str(suggestions_output),
    ]
    if extra:
        args.extend(extra)
    return args


def _read_suggestions(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["suggestions"]


# ----------------------------------------------------------------
# all assigned -> exit 0
# ----------------------------------------------------------------


def test_all_assigned_passes(tmp_path):
    entries = [
        _entry(evidenceId="EVT_TEST_A_E01_DLG0001"),
        _entry(
            evidenceId="EVT_TEST_A_E02_DLG0001",
            episodeId="EVT_TEST_A_E02",
            publicEpisodeId="PUB_TEST_A_E02",
        ),
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 0, result.stderr
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "PASS" in report_text
    assert _read_suggestions(tmp_path / "suggestions.yaml") == []


# ----------------------------------------------------------------
# missing publicEpisodeId -> exit 1, suggestion generated
# ----------------------------------------------------------------


def test_missing_public_episode_id_fails_and_suggests(tmp_path):
    entries = [
        _entry(evidenceId="EVT_TEST_A_E01_DLG0001"),
        _entry(
            evidenceId="EVT_TEST_A_E02_DLG0001",
            episodeId="EVT_TEST_A_E02",
            publicEpisodeId=None,
        ),
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout
    suggestions = _read_suggestions(tmp_path / "suggestions.yaml")
    assert len(suggestions) == 1
    assert suggestions[0]["publicStoryId"] == "PUB_TEST_A"
    assert suggestions[0]["missingEpisodeOrder"] == 2
    assert suggestions[0]["suggestedPublicEpisodeId"] == "PUB_TEST_A_E02"
    assert suggestions[0]["reviewRequired"] is True
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Missing publicEpisodeId count: 1" in report_text
    assert "FAIL" in report_text


def test_suggestion_uses_public_story_id_episode_style(tmp_path):
    entries = [
        _entry(
            evidenceId="EVT_TEST_A_E01_DLG0001",
            publicStoryId="PUB_XYZ",
            publicEpisodeId=None,
        )
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout
    suggestions = _read_suggestions(tmp_path / "suggestions.yaml")
    assert suggestions[0]["suggestedPublicEpisodeId"] == "PUB_XYZ_E01"


# ----------------------------------------------------------------
# no internal IDs leak into report/suggestions
# ----------------------------------------------------------------


def test_no_internal_ids_in_suggestions_or_report(tmp_path):
    entries = [
        _entry(
            evidenceId="EVT_SOURCEKEY_INTERNAL_E01_DLG0001",
            storyId="EVT_SOURCEKEY_INTERNAL",
            episodeId="EVT_SOURCEKEY_INTERNAL_E01",
            publicEpisodeId=None,
        )
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    report_path = tmp_path / "report.md"
    suggestions_path = tmp_path / "suggestions.yaml"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            report=report_path,
            suggestions_output=suggestions_path,
        )
    )
    assert result.returncode == 1, result.stdout
    report_text = report_path.read_text(encoding="utf-8")
    suggestions_text = suggestions_path.read_text(encoding="utf-8")
    assert "EVT_SOURCEKEY_INTERNAL" not in report_text
    assert "EVT_SOURCEKEY_INTERNAL" not in suggestions_text


# ----------------------------------------------------------------
# duplicate / missing publicStoryId / multiple stories
# ----------------------------------------------------------------


def test_duplicate_public_episode_id_detects_error(tmp_path):
    entries = [
        _entry(evidenceId="EVT_TEST_A_E01_DLG0001", publicEpisodeId="PUB_TEST_A_E01"),
        _entry(
            evidenceId="EVT_TEST_A_E02_DLG0001",
            episodeId="EVT_TEST_A_E02",
            publicEpisodeId="PUB_TEST_A_E01",
        ),
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "重複しています" in report_text
    assert "Duplicate publicEpisodeId count: 1" in report_text


def test_missing_public_story_id_detects_error(tmp_path):
    entries = [_entry(publicStoryId=None, publicEpisodeId=None)]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "unidentified-story-group-1" in report_text
    assert "Missing publicStoryId count: 1" in report_text
    suggestions = _read_suggestions(tmp_path / "suggestions.yaml")
    assert suggestions == []


def test_multiple_stories_handled(tmp_path):
    entries = [
        _entry(
            evidenceId="EVT_A_E01_DLG0001",
            storyId="EVT_A",
            publicStoryId="PUB_A",
            episodeId="EVT_A_E01",
            publicEpisodeId="PUB_A_E01",
        ),
        _entry(
            evidenceId="EVT_B_E01_DLG0001",
            storyId="EVT_B",
            publicStoryId="PUB_B",
            episodeId="EVT_B_E01",
            publicEpisodeId=None,
        ),
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Story count: 2" in report_text
    suggestions = _read_suggestions(tmp_path / "suggestions.yaml")
    assert len(suggestions) == 1
    assert suggestions[0]["publicStoryId"] == "PUB_B"


# ----------------------------------------------------------------
# report generated / registry input / strict mode
# ----------------------------------------------------------------


def test_report_output_contains_required_sections(tmp_path):
    result = _run_cli(*_base_args(tmp_path))
    assert result.returncode == 0, result.stderr
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "# Public Episode ID Assignment Check Report" in report_text
    assert "## Stories" in report_text
    assert "## Suggestions" in report_text
    assert "## Issues" in report_text
    assert "## Final Decision" in report_text
    assert "review" in report_text.lower()


def test_registry_input_is_used_for_suggestion(tmp_path):
    entries = [_entry(publicEpisodeId=None)]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    registry_path = tmp_path / "registry.yaml"
    with open(registry_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "registryVersion": 1,
                "stories": [
                    {
                        "publicStoryId": "PUB_TEST_A",
                        "category": "event",
                        "episodes": [
                            {
                                "publicEpisodeId": "PUB_TEST_A_E01_LEGACY",
                                "episodeOrder": 1,
                            }
                        ],
                    }
                ],
            },
            f,
        )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 1, result.stdout
    suggestions = _read_suggestions(tmp_path / "suggestions.yaml")
    assert suggestions[0]["suggestedPublicEpisodeId"] == "PUB_TEST_A_E01_LEGACY"
    assert "Registry" in suggestions[0]["reason"]


def test_registry_schema_invalid_returns_exit_2(tmp_path):
    registry_path = tmp_path / "registry.yaml"
    with open(registry_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"registryVersion": 1, "stories": [{"invalidField": True}]}, f)
    result = _run_cli(*_base_args(tmp_path), "--registry", str(registry_path))
    assert result.returncode == 2, result.stdout


def test_missing_registry_path_returns_exit_2(tmp_path):
    result = _run_cli(
        *_base_args(tmp_path), "--registry", str(tmp_path / "does_not_exist.yaml")
    )
    assert result.returncode == 2, result.stdout


def test_strict_flag_makes_conflict_blocking(tmp_path):
    entries = [
        _entry(evidenceId="EVT_TEST_A_E01_DLG0001", publicEpisodeId="PUB_TEST_A_E01"),
        _entry(
            evidenceId="EVT_TEST_A_E01_DLG0002", publicEpisodeId="PUB_TEST_A_E01_ALT"
        ),
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))

    lenient_result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert lenient_result.returncode == 0, lenient_result.stderr
    lenient_report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "要review" in lenient_report

    strict_result = _run_cli(*_base_args(tmp_path, input_path=input_path), "--strict")
    assert strict_result.returncode == 1, strict_result.stdout


# ----------------------------------------------------------------
# directory input / missing input path
# ----------------------------------------------------------------


def test_directory_input_processes_all_files(tmp_path):
    input_dir = tmp_path / "input_dir"
    input_dir.mkdir()
    _write(
        input_dir / "story_a.yaml",
        _document(
            [
                _entry(
                    evidenceId="EVT_A_E01_DLG0001",
                    storyId="EVT_A",
                    publicStoryId="PUB_A",
                    episodeId="EVT_A_E01",
                    publicEpisodeId="PUB_A_E01",
                )
            ]
        ),
    )
    _write(
        input_dir / "story_b.yaml",
        _document(
            [
                _entry(
                    evidenceId="EVT_B_E01_DLG0001",
                    storyId="EVT_B",
                    publicStoryId="PUB_B",
                    episodeId="EVT_B_E01",
                    publicEpisodeId=None,
                )
            ]
        ),
    )
    result = _run_cli(*_base_args(tmp_path, input_path=input_dir))
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "File count: 2" in report_text
    assert "Story count: 2" in report_text


def test_missing_input_path_returns_exit_2(tmp_path):
    result = _run_cli(
        *_base_args(tmp_path, input_path=tmp_path / "does_not_exist.yaml")
    )
    assert result.returncode == 2


# ----------------------------------------------------------------
# safety: --report/--suggestions-output must never target
# knowledge/evidence/ or knowledge/public_ids/
# ----------------------------------------------------------------


def test_report_under_knowledge_evidence_is_rejected(tmp_path):
    forbidden_report = (
        PROJECT_ROOT / "knowledge" / "evidence" / "stories" / "_test_reject_report.md"
    )
    result = _run_cli(*_base_args(tmp_path, report=forbidden_report))
    assert result.returncode == 2
    assert not forbidden_report.exists()


def test_suggestions_output_under_knowledge_public_ids_is_rejected(tmp_path):
    forbidden_output = (
        PROJECT_ROOT / "knowledge" / "public_ids" / "_test_reject_suggestions.yaml"
    )
    result = _run_cli(*_base_args(tmp_path, suggestions_output=forbidden_output))
    assert result.returncode == 2
    assert not forbidden_output.exists()
