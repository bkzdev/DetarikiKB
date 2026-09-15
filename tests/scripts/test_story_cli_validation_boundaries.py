"""Story normalize/extract CLIのfail-closedなschema検証境界を検証する。"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

import scripts.extract_story as extract_story
import scripts.normalize_story as normalize_story
from agents.parser.normalizer import Normalizer
from agents.parser.parser import StoryParser

PROJECT_ROOT = Path(__file__).parent.parent.parent
NORMALIZE_SCRIPT = PROJECT_ROOT / "scripts" / "normalize_story.py"
EXTRACT_SCRIPT = PROJECT_ROOT / "scripts" / "extract_story.py"
EPISODE_ID = "TEST_VALIDATION_E01"


def _build_normalized_story(episode_id: str = EPISODE_ID) -> dict:
    parse_result = StoryParser().parse_text(
        "msg\nこれは合成テスト本文です。\n",
        source_file="synthetic.dec",
    )
    return Normalizer(
        story_id=episode_id.removesuffix("_E01"),
        story_category="OTHER",
        episode_id=episode_id,
        source_file="synthetic.dec",
    ).normalize(parse_result)


def _prepare_cli(tmp_path: Path, pipeline: str) -> tuple[list[str], Path]:
    output_dir = tmp_path / f"{pipeline}_output"

    if pipeline == "normalize":
        input_path = tmp_path / "synthetic.dec"
        input_path.write_text("msg\nこれは合成テスト本文です。\n", encoding="utf-8")
        command = [
            sys.executable,
            str(NORMALIZE_SCRIPT),
            "--input",
            str(input_path),
            "--story-id",
            "TEST_VALIDATION",
            "--episode-id",
            EPISODE_ID,
            "--category",
            "OTHER",
            "--output",
            str(output_dir),
            "--validate",
            "--quiet",
        ]
        output_path = output_dir / f"{EPISODE_ID}.json"
    else:
        story_json = _build_normalized_story()
        input_path = tmp_path / "normalized.json"
        input_path.write_text(
            json.dumps(story_json, ensure_ascii=False), encoding="utf-8"
        )
        command = [
            sys.executable,
            str(EXTRACT_SCRIPT),
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--validate",
            "--quiet",
        ]
        output_path = output_dir / f"{EPISODE_ID}.extraction.json"

    return command, output_path


@pytest.mark.parametrize("pipeline", ["normalize", "extract"])
def test_validate_rejects_missing_schema_without_writing_output(tmp_path, pipeline):
    command, output_path = _prepare_cli(tmp_path, pipeline)
    missing_schema = tmp_path / "missing.schema.json"

    result = subprocess.run(
        [*command, "--schema", str(missing_schema)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "スキーマファイルが見つかりません" in result.stderr
    assert not output_path.exists()


@pytest.mark.parametrize("pipeline", ["normalize", "extract"])
def test_validate_rejects_invalid_schema_without_writing_output(tmp_path, pipeline):
    command, output_path = _prepare_cli(tmp_path, pipeline)
    invalid_schema = tmp_path / "invalid.schema.json"
    invalid_schema.write_text('{"type": 123}', encoding="utf-8")

    result = subprocess.run(
        [*command, "--schema", str(invalid_schema)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "123 is not valid" in result.stderr
    assert not output_path.exists()


@pytest.mark.parametrize("pipeline", ["normalize", "extract"])
def test_validation_failure_preserves_existing_output(tmp_path, pipeline):
    command, output_path = _prepare_cli(tmp_path, pipeline)
    rejecting_schema = tmp_path / "rejecting.schema.json"
    rejecting_schema.write_text("false", encoding="utf-8")
    output_path.parent.mkdir(parents=True)
    original = b"existing validated artifact\n"
    output_path.write_bytes(original)

    result = subprocess.run(
        [*command, "--schema", str(rejecting_schema)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "JSON Schema 検証失敗" in result.stderr
    assert output_path.read_bytes() == original


@pytest.mark.parametrize(
    "validator",
    [extract_story.validate_schema, normalize_story.validate_schema],
)
def test_validate_fails_when_jsonschema_is_unavailable(
    monkeypatch, tmp_path, validator: Callable[[dict, Path, bool], int]
):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text("{}", encoding="utf-8")
    original_import = __import__

    def import_without_jsonschema(name, *args, **kwargs):
        if name == "jsonschema":
            raise ImportError("synthetic missing dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", import_without_jsonschema)

    assert validator({}, schema_path, quiet=True) != 0


def test_extract_batch_validates_every_episode_before_writing(tmp_path):
    input_dir = tmp_path / "normalized"
    input_dir.mkdir()
    for episode_id in ("TEST_BATCH_A_E01", "TEST_BATCH_B_E01"):
        (input_dir / f"{episode_id}.json").write_text(
            json.dumps(_build_normalized_story(episode_id), ensure_ascii=False),
            encoding="utf-8",
        )

    schema_path = tmp_path / "reject_second.schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "not": {
                    "properties": {"episodeId": {"const": "TEST_BATCH_B_E01"}},
                    "required": ["episodeId"],
                }
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "extracted"

    result = subprocess.run(
        [
            sys.executable,
            str(EXTRACT_SCRIPT),
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_dir),
            "--validate",
            "--schema",
            str(schema_path),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert not output_dir.exists()


@pytest.mark.parametrize(
    ("schema_content", "expected_success"),
    [(None, False), ('{"type": 123}', False), ("{}", True)],
)
def test_extract_empty_batch_still_validates_schema(
    tmp_path, schema_content, expected_success
):
    input_dir = tmp_path / "normalized"
    input_dir.mkdir()
    empty_story = _build_normalized_story()
    empty_story["episodes"] = []
    (input_dir / "empty.json").write_text(
        json.dumps(empty_story, ensure_ascii=False), encoding="utf-8"
    )
    output_dir = tmp_path / "extracted"
    schema_path = tmp_path / "batch.schema.json"
    if schema_content is not None:
        schema_path.write_text(schema_content, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(EXTRACT_SCRIPT),
            "--input-dir",
            str(input_dir),
            "--output",
            str(output_dir),
            "--validate",
            "--schema",
            str(schema_path),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )

    assert (result.returncode == 0) is expected_success
    assert output_dir.exists() is expected_success
