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


# ----------------------------------------------------------------
# --projection-mode public-safe: field rewrite
# ----------------------------------------------------------------


def _read_public_safe_document(output_dir: Path, filename: str) -> dict:
    with open(output_dir / filename, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_public_safe_evidence_id_becomes_public_evidence_id(tmp_path):
    entry = _entry(evidenceId="EVT_A_E01_DLG0001")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_public_safe_document(output_dir, "PUB_TEST_A.yaml")
    assert doc["entries"][0]["evidenceId"] == "PUB_TEST_A_E01_DLG0001"
    assert doc["entries"][0]["publicEvidenceId"] == "PUB_TEST_A_E01_DLG0001"


def test_public_safe_story_id_becomes_public_story_id(tmp_path):
    entry = _entry()
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_public_safe_document(output_dir, "PUB_TEST_A.yaml")
    assert doc["entries"][0]["storyId"] == "PUB_TEST_A"
    assert doc["entries"][0]["publicStoryId"] == "PUB_TEST_A"


def test_public_safe_episode_id_becomes_public_episode_id(tmp_path):
    entry = _entry()
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_public_safe_document(output_dir, "PUB_TEST_A.yaml")
    assert doc["entries"][0]["episodeId"] == "PUB_TEST_A_E01"
    assert doc["entries"][0]["publicEpisodeId"] == "PUB_TEST_A_E01"


def test_public_safe_scene_id_and_block_id_are_not_output(tmp_path):
    entry = _entry(sceneId="EVT_TEST_A_E01_SC001", blockId="EVT_TEST_A_E01_DLG0001")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_public_safe_document(output_dir, "PUB_TEST_A.yaml")
    assert "sceneId" not in doc["entries"][0]
    assert "blockId" not in doc["entries"][0]


def test_public_safe_referenced_by_is_not_output(tmp_path):
    entry = _entry(
        referencedBy={"summaries": [{"storyId": "EVT_TEST_A", "summaryType": "story"}]}
    )
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_public_safe_document(output_dir, "PUB_TEST_A.yaml")
    assert "referencedBy" not in doc["entries"][0]


def test_public_safe_generated_from_is_not_output(tmp_path):
    input_path = _write(
        tmp_path / "input.yaml",
        _document(
            generatedFrom={
                "normalizedStoryRefs": [{"storyId": "EVT_TEST_A"}],
                "extractionRefs": [],
            }
        ),
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_public_safe_document(output_dir, "PUB_TEST_A.yaml")
    assert doc.get("generatedFrom") is None


def test_public_safe_unresolved_speaker_is_dropped(tmp_path):
    entry = _entry(
        speaker={
            "speakerId": None,
            "displayName": "不明人物",
            "resolutionStatus": "unresolved",
        }
    )
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_public_safe_document(output_dir, "PUB_TEST_A.yaml")
    assert "speaker" not in doc["entries"][0]


def test_public_safe_resolved_speaker_is_kept(tmp_path):
    entry = _entry(
        speaker={
            "speakerId": "CHAR_ALICE",
            "displayName": None,
            "resolutionStatus": "resolved",
        }
    )
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_public_safe_document(output_dir, "PUB_TEST_A.yaml")
    assert doc["entries"][0]["speaker"]["speakerId"] == "CHAR_ALICE"


def test_public_safe_out_of_policy_entry_is_excluded_from_output(tmp_path):
    entries = [
        _entry(evidenceId="EVT_A_E01_DLG0001", evidenceType="dialogue"),
        _entry(
            evidenceId="EVT_A_E01_STAGE0001",
            evidenceType="stage_direction",
        ),
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_public_safe_document(output_dir, "PUB_TEST_A.yaml")
    assert len(doc["entries"]) == 1
    assert doc["entries"][0]["evidenceType"] == "dialogue"


# ----------------------------------------------------------------
# --projection-mode public-safe: filename policy
# ----------------------------------------------------------------


def test_public_safe_output_filename_is_public_story_id(tmp_path):
    entry = _entry(storyId="EVT_TEST_A", publicStoryId="PUB_TEST_XYZ")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    assert (output_dir / "PUB_TEST_XYZ.yaml").is_file()


def test_public_safe_multiple_public_story_ids_in_one_file_fails(tmp_path):
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
            publicEpisodeId="PUB_B_E01",
        ),
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "複数のpublicStoryId" in report_text
    assert "not-promotion-ready" in report_text


def test_public_safe_duplicate_target_filename_across_files_fails(tmp_path):
    input_dir = tmp_path / "input_dir"
    input_dir.mkdir()
    _write(
        input_dir / "story_a.yaml",
        _document(
            [
                _entry(
                    evidenceId="EVT_A_E01_DLG0001",
                    storyId="EVT_A",
                    publicStoryId="PUB_SAME",
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
                    publicStoryId="PUB_SAME",
                    episodeId="EVT_B_E01",
                    publicEpisodeId="PUB_B_E01",
                )
            ]
        ),
    )
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "PUB_SAME" in report_text
    assert "衝突" in report_text


def test_public_safe_missing_public_episode_id_fails(tmp_path):
    entry = _entry(publicEpisodeId=None)
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "publicEpisodeId" in report_text
    assert "not-promotion-ready" in report_text


# ----------------------------------------------------------------
# --projection-mode public-safe: internal ID exposure scan
# ----------------------------------------------------------------


def test_public_safe_internal_story_id_does_not_leak_into_output(tmp_path):
    entry = _entry(
        storyId="EVT_INTERNAL_SOURCEKEY_STORY",
        publicStoryId="PUB_TEST_A",
    )
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    output_text = (output_dir / "PUB_TEST_A.yaml").read_text(encoding="utf-8")
    assert "EVT_INTERNAL_SOURCEKEY_STORY" not in output_text


def test_public_safe_internal_evidence_id_does_not_leak_into_output(tmp_path):
    entry = _entry(evidenceId="EVT_INTERNAL_SOURCEKEY_STORY_E01_DLG0001")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    output_text = (output_dir / "PUB_TEST_A.yaml").read_text(encoding="utf-8")
    assert "EVT_INTERNAL_SOURCEKEY_STORY_E01_DLG0001" not in output_text


def test_public_safe_internal_episode_id_does_not_leak_into_output(tmp_path):
    entry = _entry(episodeId="EVT_INTERNAL_SOURCEKEY_STORY_E01")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    output_text = (output_dir / "PUB_TEST_A.yaml").read_text(encoding="utf-8")
    assert "EVT_INTERNAL_SOURCEKEY_STORY_E01" not in output_text


def test_public_safe_internal_id_leak_via_notes_is_blocked(tmp_path):
    entry = _entry(
        evidenceId="EVT_INTERNAL_SOURCEKEY_STORY_E01_DLG0001",
        notes="internal ref: EVT_INTERNAL_SOURCEKEY_STORY_E01_DLG0001",
    )
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "internal ID exposure" in report_text
    assert "not-promotion-ready" in report_text


# ----------------------------------------------------------------
# --projection-mode public-safe: mapping output / schema validation /
# promotion readiness reporting
# ----------------------------------------------------------------


def test_public_safe_mapping_output_still_contains_internal_ids(tmp_path):
    entry = _entry(evidenceId="EVT_A_E01_DLG0001", storyId="EVT_TEST_A")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    mapping_output = tmp_path / "mapping.csv"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            mapping_output=mapping_output,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    with open(mapping_output, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["storyId"] == "EVT_TEST_A"
    assert rows[0]["evidenceId"] == "EVT_A_E01_DLG0001"


def test_public_safe_output_validates_against_schema(tmp_path):
    entries = [
        _entry(evidenceId="EVT_A_E01_DLG0001", evidenceType="dialogue"),
        _entry(
            evidenceId="EVT_A_E01_STAGE0001",
            evidenceType="stage_direction",
        ),
    ]
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr

    import json

    from jsonschema import Draft7Validator

    schema_path = PROJECT_ROOT / "schemas" / "evidence_index.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    with open(output_dir / "PUB_TEST_A.yaml", encoding="utf-8") as f:
        projected = yaml.safe_load(f)
    errors = list(Draft7Validator(schema).iter_errors(projected))
    assert errors == []


def test_public_safe_report_contains_promotion_readiness(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    report_path = tmp_path / "report.md"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            report=report_path,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    text = report_path.read_text(encoding="utf-8")
    assert "## Public-safe Projection" in text
    assert "Promotion readiness: promotion-candidate" in text
    assert "publicStoryId-based" in text


def test_public_safe_report_not_promotion_ready_when_blocking_issue_present(tmp_path):
    entry = _entry(publicEpisodeId=None)
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Promotion readiness: not-promotion-ready" in report_text


def test_compatible_mode_is_default_projection_mode(tmp_path):
    entry = _entry(evidenceId="EVT_A_E01_DLG0001")
    input_path = _write(tmp_path / "input.yaml", _document([entry]))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    entries = _read_output_entries(output_dir, "input.yaml")
    assert entries[0]["evidenceId"] == "EVT_A_E01_DLG0001"
    assert entries[0]["storyId"] == "EVT_TEST_A"


# ----------------------------------------------------------------
# --registry: Public ID Registry integration
# ----------------------------------------------------------------


def _write_registry(path: Path, stories: list[dict]) -> Path:
    return _write(path, {"registryVersion": 1, "stories": stories})


def _registry_story(public_story_id: str, episodes: list[dict], **overrides) -> dict:
    story = {
        "publicStoryId": public_story_id,
        "category": "event",
        "episodes": episodes,
    }
    story.update(overrides)
    return story


def _two_episode_entries(*, second_public_episode_id: str | None = None) -> list[dict]:
    return [
        _entry(evidenceId="EVT_TEST_A_E01_DLG0001"),
        _entry(
            evidenceId="EVT_TEST_A_E02_DLG0001",
            episodeId="EVT_TEST_A_E02",
            publicEpisodeId=second_public_episode_id,
        ),
    ]


def test_registry_completes_missing_public_episode_id(tmp_path):
    entries = _two_episode_entries(second_public_episode_id=None)
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1},
                    {"publicEpisodeId": "PUB_TEST_A_E02", "episodeOrder": 2},
                ],
            )
        ],
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 0, result.stderr
    entries_out = _read_output_entries(output_dir, "input.yaml")
    assert entries_out[1]["publicEpisodeId"] == "PUB_TEST_A_E02"


def test_registry_completion_generates_public_evidence_id_with_new_prefix(tmp_path):
    entries = _two_episode_entries(second_public_episode_id=None)
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1},
                    {"publicEpisodeId": "PUB_TEST_A_E02", "episodeOrder": 2},
                ],
            )
        ],
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 0, result.stderr
    entries_out = _read_output_entries(output_dir, "input.yaml")
    assert entries_out[1]["publicEvidenceId"] == "PUB_TEST_A_E02_DLG0001"


def test_registry_completion_public_safe_mode_passes_schema_validation(tmp_path):
    entries = _two_episode_entries(second_public_episode_id=None)
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1},
                    {"publicEpisodeId": "PUB_TEST_A_E02", "episodeOrder": 2},
                ],
            )
        ],
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        ),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 0, result.stderr

    import json

    from jsonschema import Draft7Validator

    schema_path = PROJECT_ROOT / "schemas" / "evidence_index.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    with open(output_dir / "PUB_TEST_A.yaml", encoding="utf-8") as f:
        projected = yaml.safe_load(f)
    errors = list(Draft7Validator(schema).iter_errors(projected))
    assert errors == []
    assert len(projected["entries"]) == 2


def test_registry_completion_works_in_compatible_mode(tmp_path):
    entries = _two_episode_entries(second_public_episode_id=None)
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1},
                    {"publicEpisodeId": "PUB_TEST_A_E02", "episodeOrder": 2},
                ],
            )
        ],
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "compatible"],
        ),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 0, result.stderr
    entries_out = _read_output_entries(output_dir, "input.yaml")
    assert entries_out[1]["episodeId"] == "EVT_TEST_A_E02"
    assert entries_out[1]["publicEpisodeId"] == "PUB_TEST_A_E02"
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "NOT promotion-ready" in report_text


def test_registry_mismatch_with_existing_public_episode_id_fails(tmp_path):
    entries = _two_episode_entries(second_public_episode_id="PUB_TEST_A_E02")
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1},
                    {"publicEpisodeId": "PUB_TEST_A_E02_DIFFERENT", "episodeOrder": 2},
                ],
            )
        ],
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "一致しません" in report_text
    assert "Registry conflicts: 1" in report_text


def test_missing_public_episode_id_not_in_registry_still_fails(tmp_path):
    entries = _two_episode_entries(second_public_episode_id=None)
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [{"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1}],
            )
        ],
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Missing publicEpisodeId count: 1" in report_text
    assert "Entries with publicEpisodeId from registry: 0" in report_text


def test_invalid_registry_schema_returns_exit_2(tmp_path):
    registry_path = tmp_path / "registry.yaml"
    with open(registry_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"registryVersion": 1, "stories": [{"invalidField": True}]}, f)
    input_path = _write(tmp_path / "input.yaml", _document())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 2, result.stdout


def test_registry_with_source_key_like_extra_field_fails_schema(tmp_path):
    registry_path = tmp_path / "registry.yaml"
    with open(registry_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {
                "registryVersion": 1,
                "stories": [
                    {
                        "publicStoryId": "PUB_TEST_A",
                        "category": "event",
                        "sourceKey": "not_allowed",
                        "episodes": [
                            {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1}
                        ],
                    }
                ],
            },
            f,
        )
    input_path = _write(tmp_path / "input.yaml", _document())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 2, result.stdout


def test_duplicate_public_episode_id_within_registry_fails(tmp_path):
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1},
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 2},
                ],
            )
        ],
    )
    input_path = _write(tmp_path / "input.yaml", _document())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 2, result.stdout


def test_mapping_output_shows_registry_source(tmp_path):
    entries = _two_episode_entries(second_public_episode_id=None)
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1},
                    {"publicEpisodeId": "PUB_TEST_A_E02", "episodeOrder": 2},
                ],
            )
        ],
    )
    mapping_output = tmp_path / "mapping.csv"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, mapping_output=mapping_output),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 0, result.stderr
    with open(mapping_output, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["publicEpisodeIdSource"] == "input"
    assert rows[1]["publicEpisodeIdSource"] == "registry"
    assert rows[1]["registryMatched"] == "True"
    assert rows[1]["registryPublicEpisodeId"] == "PUB_TEST_A_E02"


def test_report_contains_registry_summary(tmp_path):
    entries = _two_episode_entries(second_public_episode_id=None)
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1},
                    {"publicEpisodeId": "PUB_TEST_A_E02", "episodeOrder": 2},
                ],
            )
        ],
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 0, result.stderr
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "## Registry" in report_text
    assert "Registry stories count: 1" in report_text
    assert "Registry episodes count: 2" in report_text
    assert "Entries with publicEpisodeId from registry: 1" in report_text


def test_existing_public_episode_id_matching_registry_passes(tmp_path):
    entries = _two_episode_entries(second_public_episode_id="PUB_TEST_A_E02")
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1},
                    {"publicEpisodeId": "PUB_TEST_A_E02", "episodeOrder": 2},
                ],
            )
        ],
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 0, result.stderr
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Registry conflicts: 0" in report_text


def test_existing_public_episode_id_missing_from_registry_warns_but_passes(tmp_path):
    entries = _two_episode_entries(second_public_episode_id="PUB_TEST_A_E02")
    input_path = _write(tmp_path / "input.yaml", _document(entries))
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A", [{"publicEpisodeId": "PUB_TEST_A_E02", "episodeOrder": 2}]
            )
        ],
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 0, result.stderr
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Registryには" in report_text
    assert "## Warnings" in report_text
    assert "(none)" not in report_text.split("## Warnings")[1].split("##")[0]


def test_missing_registry_path_returns_exit_2(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(tmp_path / "does_not_exist.yaml"),
    )
    assert result.returncode == 2, result.stdout


def test_no_registry_still_reports_registry_section_as_unused(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 0, result.stderr
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Registry path: (none)" in report_text
