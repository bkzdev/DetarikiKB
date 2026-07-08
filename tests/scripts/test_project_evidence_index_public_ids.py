"""
tests/scripts/test_project_evidence_index_public_ids.py
scripts/project_evidence_index_public_ids.py のCLIテスト。

Public Evidence Index候補にpublicEvidenceIdを生成・付与する
"Compatible projection"（案A、内部IDは削除しない）scriptを検証する。
合成データのみを一時ファイルとして生成して使う。実データ・実データ由来
fixtureは一切使わない。--output/--mapping-output/--reportはいずれも
tmp_path配下 (workspace相当) を使い、knowledge/evidence/への書き込みは
一切発生させない。
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "project_evidence_index_public_ids.py"


def _entry(**overrides) -> dict:
    entry = {
        "evidenceId": "EVT_TEST_A_E01_DLG0001",
        "evidenceType": "dialogue",
        "storyId": "EVT_TEST_A",
        "publicStoryId": "PUB_TEST_A",
        "episodeId": "EVT_TEST_A_E01",
        "publicEpisodeId": "PUB_TEST_A_E01",
        "publicEvidenceId": None,
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
    output_dir: Path | None = None,
    mapping_output: Path | None = None,
    report: Path | None = None,
    extra: list[str] | None = None,
) -> list[str]:
    if input_path is None:
        input_path = _write(tmp_path / "input.yaml", _document())
    if output_dir is None:
        output_dir = tmp_path / "output"
    if mapping_output is None:
        mapping_output = tmp_path / "mapping.csv"
    if report is None:
        report = tmp_path / "report.md"
    args = [
        "--input",
        str(input_path),
        "--output",
        str(output_dir),
        "--mapping-output",
        str(mapping_output),
        "--report",
        str(report),
    ]
    if extra:
        args.extend(extra)
    return args


def _read_output_entries(output_dir: Path, filename: str) -> list[dict]:
    with open(output_dir / filename, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["entries"]


# ----------------------------------------------------------------
# prefix generation per evidenceType
# ----------------------------------------------------------------


def test_generates_dialogue_prefix(tmp_path):
    entry = _entry(evidenceId="EVT_A_E01_DLG0001", evidenceType="dialogue")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    entries = _read_output_entries(output_dir, "input.yaml")
    assert entries[0]["publicEvidenceId"] == "PUB_TEST_A_E01_DLG0001"


def test_generates_narration_prefix(tmp_path):
    entry = _entry(evidenceId="EVT_A_E01_NAR0001", evidenceType="narration")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    entries = _read_output_entries(output_dir, "input.yaml")
    assert entries[0]["publicEvidenceId"] == "PUB_TEST_A_E01_NAR0001"


def test_generates_monologue_prefix(tmp_path):
    entry = _entry(evidenceId="EVT_A_E01_MONO0001", evidenceType="monologue")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    entries = _read_output_entries(output_dir, "input.yaml")
    assert entries[0]["publicEvidenceId"] == "PUB_TEST_A_E01_MONO0001"


def test_generates_choice_prefix(tmp_path):
    entry = _entry(evidenceId="EVT_A_E01_CHOICE0001", evidenceType="choice")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    entries = _read_output_entries(output_dir, "input.yaml")
    assert entries[0]["publicEvidenceId"] == "PUB_TEST_A_E01_CHO0001"


def test_generates_unknown_prefix(tmp_path):
    entry = _entry(evidenceId="EVT_A_E01_UNKNOWN0001", evidenceType="unknown")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    entries = _read_output_entries(output_dir, "input.yaml")
    assert entries[0]["publicEvidenceId"] == "PUB_TEST_A_E01_UNK0001"


# ----------------------------------------------------------------
# numbering: per-episode reset, per-type counters
# ----------------------------------------------------------------


def test_numbering_resets_per_episode(tmp_path):
    entries = [
        _entry(
            evidenceId="EVT_A_E01_DLG0001",
            episodeId="EVT_A_E01",
            publicEpisodeId="PUB_A_E01",
        ),
        _entry(
            evidenceId="EVT_A_E02_DLG0001",
            episodeId="EVT_A_E02",
            publicEpisodeId="PUB_A_E02",
        ),
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    out_entries = _read_output_entries(output_dir, "input.yaml")
    assert out_entries[0]["publicEvidenceId"] == "PUB_A_E01_DLG0001"
    assert out_entries[1]["publicEvidenceId"] == "PUB_A_E02_DLG0001"


def test_numbering_increments_within_same_episode_and_type(tmp_path):
    entries = [
        _entry(evidenceId="EVT_A_E01_DLG0001"),
        _entry(evidenceId="EVT_A_E01_DLG0002"),
        _entry(evidenceId="EVT_A_E01_DLG0003"),
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    out_entries = _read_output_entries(output_dir, "input.yaml")
    assert [e["publicEvidenceId"] for e in out_entries] == [
        "PUB_TEST_A_E01_DLG0001",
        "PUB_TEST_A_E01_DLG0002",
        "PUB_TEST_A_E01_DLG0003",
    ]


def test_numbering_is_per_type_independent(tmp_path):
    entries = [
        _entry(evidenceId="EVT_A_E01_DLG0001", evidenceType="dialogue"),
        _entry(evidenceId="EVT_A_E01_NAR0001", evidenceType="narration"),
        _entry(evidenceId="EVT_A_E01_DLG0002", evidenceType="dialogue"),
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    out_entries = _read_output_entries(output_dir, "input.yaml")
    assert out_entries[0]["publicEvidenceId"] == "PUB_TEST_A_E01_DLG0001"
    assert out_entries[1]["publicEvidenceId"] == "PUB_TEST_A_E01_NAR0001"
    assert out_entries[2]["publicEvidenceId"] == "PUB_TEST_A_E01_DLG0002"


# ----------------------------------------------------------------
# blocking: missing publicStoryId / publicEpisodeId
# ----------------------------------------------------------------


def test_missing_public_story_id_fails(tmp_path):
    entry = _entry(publicStoryId=None)
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "publicStoryId" in report_text
    assert "FAIL" in report_text


def test_missing_public_episode_id_fails(tmp_path):
    entry = _entry(publicEpisodeId=None)
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "publicEpisodeId" in report_text


def test_missing_public_episode_id_fails_even_for_unknown_type(tmp_path):
    entry = _entry(
        evidenceId="EVT_A_E01_UNKNOWN0001",
        evidenceType="unknown",
        publicEpisodeId=None,
    )
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout


def test_unknown_type_is_projected_when_public_episode_id_present(tmp_path):
    entry = _entry(evidenceId="EVT_A_E01_UNKNOWN0001", evidenceType="unknown")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    entries = _read_output_entries(output_dir, "input.yaml")
    assert entries[0]["publicEvidenceId"] == "PUB_TEST_A_E01_UNK0001"


# ----------------------------------------------------------------
# existing publicEvidenceId: match / conflict
# ----------------------------------------------------------------


def test_existing_matching_public_evidence_id_passes(tmp_path):
    entry = _entry(publicEvidenceId="PUB_TEST_A_E01_DLG0001")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    entries = _read_output_entries(output_dir, "input.yaml")
    assert entries[0]["publicEvidenceId"] == "PUB_TEST_A_E01_DLG0001"
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Existing publicEvidenceId count (matched): 1" in report_text
    assert "Generated publicEvidenceId count: 0" in report_text


def test_existing_conflicting_public_evidence_id_fails(tmp_path):
    entry = _entry(publicEvidenceId="PUB_TEST_A_E01_DLG9999")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "一致しません" in report_text
    assert "Conflicts count: 1" in report_text


# ----------------------------------------------------------------
# duplicate publicEvidenceId (blocking)
# ----------------------------------------------------------------


def test_duplicate_public_evidence_id_fails(tmp_path):
    entries = [
        _entry(evidenceId="EVT_A_E01_DLG0001", evidenceType="dialogue"),
        _entry(
            evidenceId="EVT_A_E01_STAGE0001",
            evidenceType="stage_direction",
            publicEvidenceId="PUB_TEST_A_E01_DLG0001",
        ),
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "重複しています" in report_text
    assert "Duplicate publicEvidenceId count: 1" in report_text


# ----------------------------------------------------------------
# --policy / --strict (out-of-policy types)
# ----------------------------------------------------------------


def test_out_of_policy_type_is_left_without_public_evidence_id_by_default(tmp_path):
    entry = _entry(
        evidenceId="EVT_A_E01_STAGE0001",
        evidenceType="stage_direction",
    )
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    entries = _read_output_entries(output_dir, "input.yaml")
    assert entries[0]["publicEvidenceId"] is None


def test_strict_flag_fails_on_out_of_policy_type(tmp_path):
    entry = _entry(
        evidenceId="EVT_A_E01_STAGE0001",
        evidenceType="stage_direction",
    )
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    result = _run_cli(*_base_args(tmp_path, input_path=input_path, extra=["--strict"]))
    assert result.returncode == 1, result.stdout


# ----------------------------------------------------------------
# mapping output / report output
# ----------------------------------------------------------------


def test_mapping_output_contains_expected_columns_and_rows(tmp_path):
    entries = [
        _entry(evidenceId="EVT_A_E01_DLG0001"),
        _entry(evidenceId="EVT_A_E01_DLG0002"),
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    mapping_output = tmp_path / "mapping.csv"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, mapping_output=mapping_output)
    )
    assert result.returncode == 0, result.stderr
    with open(mapping_output, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    expected_columns = {
        "storyId",
        "publicStoryId",
        "episodeId",
        "publicEpisodeId",
        "evidenceId",
        "publicEvidenceId",
        "evidenceType",
        "sceneId",
        "blockId",
    }
    assert expected_columns.issubset(rows[0].keys())
    assert rows[0]["evidenceId"] == "EVT_A_E01_DLG0001"
    assert rows[0]["publicEvidenceId"] == "PUB_TEST_A_E01_DLG0001"


def test_report_output_contains_required_sections(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    report_path = tmp_path / "report.md"
    result = _run_cli(*_base_args(tmp_path, input_path=input_path, report=report_path))
    assert result.returncode == 0, result.stderr
    text = report_path.read_text(encoding="utf-8")
    assert "# Evidence Index Public ID Projection Report" in text
    assert "## Entries by evidenceType" in text
    assert "## Projection Result" in text
    assert "## Final Decision" in text
    assert "compatible projection" in text.lower()
    assert "NOT promotion-ready" in text
    assert "must never be committed" in text


# ----------------------------------------------------------------
# directory input / file input
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
                    episodeId="EVT_A_E01",
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
                    publicEpisodeId="PUB_B_E01",
                )
            ]
        ),
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_dir, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    assert (output_dir / "story_a.yaml").is_file()
    assert (output_dir / "story_b.yaml").is_file()


# ----------------------------------------------------------------
# --clean
# ----------------------------------------------------------------


def test_clean_removes_stale_files_from_output_dir(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    stale_file = output_dir / "stale.yaml"
    stale_file.write_text("stale: true\n", encoding="utf-8")
    result = _run_cli(
        *_base_args(
            tmp_path, input_path=input_path, output_dir=output_dir, extra=["--clean"]
        )
    )
    assert result.returncode == 0, result.stderr
    assert not stale_file.exists()
    assert (output_dir / "input.yaml").is_file()


def test_file_input_processes_single_file(tmp_path):
    input_path = _write(tmp_path / "single.yaml", _document())
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    assert (output_dir / "single.yaml").is_file()
    assert len(list(output_dir.iterdir())) == 1


# ----------------------------------------------------------------
# projected output schema validity / input file untouched
# ----------------------------------------------------------------


def test_projected_output_validates_against_schema(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr

    import json

    from jsonschema import Draft7Validator

    schema_path = PROJECT_ROOT / "schemas" / "evidence_index.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    with open(output_dir / "input.yaml", encoding="utf-8") as f:
        projected = yaml.safe_load(f)
    errors = list(Draft7Validator(schema).iter_errors(projected))
    assert errors == []


def test_input_file_remains_unmodified(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    original_bytes = input_path.read_bytes()
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    assert input_path.read_bytes() == original_bytes
    with open(input_path, encoding="utf-8") as f:
        original_data = yaml.safe_load(f)
    assert original_data["entries"][0]["publicEvidenceId"] is None


def test_always_writes_output_even_without_dry_run_flag(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    mapping_output = tmp_path / "mapping.csv"
    report_path = tmp_path / "report.md"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            mapping_output=mapping_output,
            report=report_path,
        )
    )
    assert result.returncode == 0, result.stderr
    assert output_dir.is_dir()
    assert mapping_output.is_file()
    assert report_path.is_file()


# ----------------------------------------------------------------
# safety: --output/--mapping-output/--report must never target
# knowledge/evidence/
# ----------------------------------------------------------------


def test_output_under_knowledge_evidence_is_rejected(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    forbidden_output = (
        PROJECT_ROOT / "knowledge" / "evidence" / "stories" / "_test_reject"
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=forbidden_output)
    )
    assert result.returncode == 2
    assert not forbidden_output.exists()


def test_mapping_output_under_knowledge_evidence_is_rejected(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    forbidden_mapping = (
        PROJECT_ROOT / "knowledge" / "evidence" / "stories" / "_test_reject_mapping.csv"
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, mapping_output=forbidden_mapping)
    )
    assert result.returncode == 2
    assert not forbidden_mapping.exists()


def test_report_under_knowledge_evidence_is_rejected(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    forbidden_report = (
        PROJECT_ROOT / "knowledge" / "evidence" / "stories" / "_test_reject_report.md"
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, report=forbidden_report)
    )
    assert result.returncode == 2
    assert not forbidden_report.exists()


# ----------------------------------------------------------------
# input/schema not found -> exit 2
# ----------------------------------------------------------------


def test_missing_input_path_returns_exit_2(tmp_path):
    result = _run_cli(
        *_base_args(tmp_path, input_path=tmp_path / "does_not_exist.yaml")
    )
    assert result.returncode == 2
