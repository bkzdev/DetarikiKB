"""
tests/scripts/test_build_story_title_subtitle_candidates.py
scripts/build_story_title_subtitle_candidates.py のCLIスモークテスト。

コアロジックのユニットテストは
tests/parser/test_story_title_subtitle_candidates.py を参照。

すべて合成データ (tmp_path配下のCSV・manifest) のみを使う。実イベント名・
実タイトル・実データ由来fixtureは一切使わない。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "build_story_title_subtitle_candidates.py"

CSV_HEADER = (
    "storyId,episodeId,episodeNumber,proposedTitle,proposedDisplayTitle,"
    "proposedSubtitle,confidence,notes\n"
)


def _write_csv(path: Path, rows: list[str]) -> None:
    path.write_text(CSV_HEADER + "\n".join(rows) + "\n", encoding="utf-8")


def _write_manifest(path: Path) -> None:
    document = {
        "schemaVersion": "0.1.0",
        "documentType": "story_manifest",
        "stories": [
            {
                "storyId": "EVT_990101_SAMPLE_EVENT",
                "category": "event",
                "sourceKey": "990101_sample_event",
                "title": None,
                "displayTitle": None,
                "metadataStatus": "pending",
                "rawDirectory": "EVENT/x_export",
                "notes": None,
                "episodes": [
                    {
                        "episodeId": "EVT_990101_SAMPLE_EVENT_E01",
                        "episodeNumber": 1,
                        "subtitle": None,
                        "displayTitle": None,
                        "rawPath": "EVENT/x_export/CAB-x-episode1.dec",
                        "sourceFileName": "CAB-x-episode1.dec",
                        "metadataStatus": "pending",
                        "notes": None,
                    }
                ],
            }
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(document, f)


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
    )


def test_cli_missing_input_csv_returns_exit_1(tmp_path):
    result = _run_cli(
        [
            "--input-csv",
            str(tmp_path / "does_not_exist.csv"),
            "--source-type",
            "wiki_story_list",
        ]
    )
    assert result.returncode == 1


def test_cli_missing_manifest_returns_exit_1(tmp_path):
    csv_path = tmp_path / "rows.csv"
    _write_csv(
        csv_path,
        ['EVT_990101_SAMPLE_EVENT,EVT_990101_SAMPLE_EVENT_E01,1,,,"Subtitle",,'],
    )

    result = _run_cli(
        [
            "--input-csv",
            str(csv_path),
            "--source-type",
            "wiki_story_list",
            "--manifest",
            str(tmp_path / "does_not_exist.yaml"),
        ]
    )
    assert result.returncode == 1


def test_cli_generates_output_with_matched_and_unmatched(tmp_path):
    csv_path = tmp_path / "rows.csv"
    _write_csv(
        csv_path,
        [
            (
                "EVT_990101_SAMPLE_EVENT,EVT_990101_SAMPLE_EVENT_E01,1,"
                'Synthetic Sample Event,,"Synthetic Episode Subtitle",'
                "source_exact,Synthetic example only."
            ),
            "EVT_UNMATCHED_STORY,EVT_UNMATCHED_STORY_E01,1,Unmatched Story,,,,",
        ],
    )
    manifest_path = tmp_path / "manifest.yaml"
    _write_manifest(manifest_path)
    output_path = tmp_path / "out" / "candidates.yaml"

    result = _run_cli(
        [
            "--input-csv",
            str(csv_path),
            "--manifest",
            str(manifest_path),
            "--source-type",
            "wiki_story_list",
            "--source-label",
            "Synthetic wiki list",
            "--output",
            str(output_path),
            "--quiet",
        ]
    )

    assert result.returncode == 0, result.stderr
    assert output_path.is_file()

    with open(output_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)

    assert document["documentType"] == "story_title_subtitle_candidates"
    assert document["source"]["sourceType"] == "wiki_story_list"

    candidates_by_id = {c["storyId"]: c for c in document["candidates"]}
    assert candidates_by_id["EVT_990101_SAMPLE_EVENT"]["foundInManifest"] is True
    assert candidates_by_id["EVT_UNMATCHED_STORY"]["foundInManifest"] is False
    for story in document["candidates"]:
        for episode in story["episodes"]:
            assert episode["reviewStatus"] == "pending"


def test_cli_without_output_does_not_write_file(tmp_path):
    csv_path = tmp_path / "rows.csv"
    _write_csv(
        csv_path,
        ["EVT_990101_SAMPLE_EVENT,EVT_990101_SAMPLE_EVENT_E01,1,,,,,"],
    )

    result = _run_cli(
        [
            "--input-csv",
            str(csv_path),
            "--source-type",
            "manual",
        ]
    )

    assert result.returncode == 0, result.stderr
    assert "EVT_990101_SAMPLE_EVENT" in result.stdout
    assert not (tmp_path / "candidates.yaml").exists()


def test_cli_quiet_suppresses_summary_output(tmp_path):
    csv_path = tmp_path / "rows.csv"
    _write_csv(
        csv_path,
        ["EVT_990101_SAMPLE_EVENT,EVT_990101_SAMPLE_EVENT_E01,1,,,,,"],
    )

    result = _run_cli(
        [
            "--input-csv",
            str(csv_path),
            "--source-type",
            "manual",
            "--quiet",
        ]
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_cli_does_not_infer_subtitle_from_blank_csv_cell(tmp_path):
    csv_path = tmp_path / "rows.csv"
    _write_csv(
        csv_path,
        ["EVT_990101_SAMPLE_EVENT,EVT_990101_SAMPLE_EVENT_E01,1,,,,,"],
    )
    output_path = tmp_path / "candidates.yaml"

    result = _run_cli(
        [
            "--input-csv",
            str(csv_path),
            "--source-type",
            "manual",
            "--output",
            str(output_path),
            "--quiet",
        ]
    )

    assert result.returncode == 0, result.stderr
    with open(output_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert document["candidates"][0]["episodes"][0]["proposedSubtitle"] is None


def test_cli_rejects_invalid_source_type(tmp_path):
    csv_path = tmp_path / "rows.csv"
    _write_csv(csv_path, ["EVT_990101_SAMPLE_EVENT,,,,,,,"])

    result = _run_cli(
        [
            "--input-csv",
            str(csv_path),
            "--source-type",
            "not_a_real_source_type",
        ]
    )

    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def test_cli_does_not_produce_json_output_error(tmp_path):
    """スモークとして、生成された候補全体がJSON互換 (jsonへdumpできる)
    であることを確認する (schema検証はtests/parser/test_story_manifest_schema.py
    ではなくここでは行わない、candidateドキュメント自体は別schema)。"""
    csv_path = tmp_path / "rows.csv"
    _write_csv(csv_path, ["EVT_990101_SAMPLE_EVENT,,,,,,,"])
    output_path = tmp_path / "candidates.yaml"

    result = _run_cli(
        [
            "--input-csv",
            str(csv_path),
            "--source-type",
            "manual",
            "--output",
            str(output_path),
            "--quiet",
        ]
    )

    assert result.returncode == 0, result.stderr
    with open(output_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    json.dumps(document, ensure_ascii=False)
