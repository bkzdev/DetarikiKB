"""release scope一括normalizeの合成データテスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from agents.parser.release_scope import normalize_release_scope

PROJECT_ROOT = Path(__file__).parent.parent.parent


def _episode(
    episode_id: str, episode_number: int, raw_path: str, source_file_name: str
) -> dict:
    return {
        "episodeId": episode_id,
        "episodeNumber": episode_number,
        "subtitle": None,
        "displayTitle": None,
        "rawPath": raw_path,
        "sourceFileName": source_file_name,
        "metadataStatus": "pending",
        "notes": None,
    }


def _story(
    story_id: str,
    category: str,
    raw_directory: str,
    episodes: list[dict],
    *,
    character_id: str | None = None,
) -> dict:
    result = {
        "storyId": story_id,
        "category": category,
        "sourceKey": "synthetic",
        "title": None,
        "displayTitle": None,
        "metadataStatus": "pending",
        "rawDirectory": raw_directory,
        "notes": None,
        "episodes": episodes,
    }
    if character_id is not None:
        result["characterId"] = character_id
        result["auxiliaryFiles"] = []
    return result


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    raw_root = tmp_path / "raw"
    event_dir = raw_root / "EVENT" / "synthetic_event_export"
    event_dir.mkdir(parents=True)
    event_name = "synthetic-event-episode1.dec"
    (event_dir / event_name).write_text("合成イベント本文\n", encoding="utf-8")

    character_dir = raw_root / "CHARACTER" / "synthetic_character_export"
    character_dir.mkdir(parents=True)
    body_name = "synthetic-H_scene1.dec"
    (character_dir / body_name).write_text("基準本文\n", encoding="utf-8")
    (character_dir / "synthetic-H_scene1_n.dec").write_text(
        "固有本文\n", encoding="utf-8"
    )
    (character_dir / "synthetic-H_scene1_spine.dec").write_text(
        "基準本文\n", encoding="utf-8"
    )
    (character_dir / "synthetic-H_scene1_VR.dec").write_text(
        "VR本文\n", encoding="utf-8"
    )

    event_raw_dir = "EVENT/synthetic_event_export"
    character_raw_dir = "CHARACTER/synthetic_character_export"
    manifest = {
        "schemaVersion": "0.1",
        "documentType": "story_manifest",
        "stories": [
            _story(
                "EVT_SYNTHETIC",
                "event",
                event_raw_dir,
                [
                    _episode(
                        "EVT_SYNTHETIC_E01",
                        1,
                        f"{event_raw_dir}/{event_name}",
                        event_name,
                    )
                ],
            ),
            _story(
                "CHAR_HS_SYNTHETIC",
                "character",
                character_raw_dir,
                [
                    _episode(
                        "CHAR_HS_SYNTHETIC_E01",
                        1,
                        f"{character_raw_dir}/{body_name}",
                        body_name,
                    )
                ],
                character_id="CHAR_SYNTHETIC",
            ),
        ],
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    characters_path = tmp_path / "characters.yaml"
    characters_path.write_text(
        'schemaVersion: "0.1"\ncharacters: []\n', encoding="utf-8"
    )
    return raw_root, manifest_path, characters_path


def _run(tmp_path: Path, output_name: str = "release") -> tuple[dict, Path]:
    raw_root, manifest_path, characters_path = _write_inputs(tmp_path)
    output_root = tmp_path / output_name
    report = normalize_release_scope(
        raw_root=raw_root,
        manifest_path=manifest_path,
        output_root=output_root,
        characters_path=characters_path,
        commands_path=PROJECT_ROOT / "config" / "script_commands.yaml",
        story_schema_path=PROJECT_ROOT / "schemas" / "story.schema.json",
        manifest_schema_path=PROJECT_ROOT / "schemas" / "story_manifest.schema.json",
        report_schema_path=(
            PROJECT_ROOT / "schemas" / "release_scope_normalization_report.schema.json"
        ),
        source_revision="a" * 40,
    )
    return report, output_root


def test_release_scope_normalizes_manifest_and_dynamic_hscene_exception(tmp_path):
    report, output_root = _run(tmp_path)

    assert report["manifestStoryCount"] == 2
    assert report["manifestEpisodeCount"] == 2
    assert report["dynamicExceptionEpisodeCount"] == 1
    assert report["normalizedEpisodeCount"] == 3
    assert report["sourceRevision"] == "a" * 40
    assert report["categoryEpisodeCounts"] == {"CHAR_HS": 2, "EVT": 1}
    assert report["hsceneVariantJudgment"] == {
        "subset": 1,
        "exception": 1,
        "skippedVr": 1,
    }
    assert (output_root / "normalized" / "event" / "EVT_SYNTHETIC_E01.json").is_file()
    assert (
        output_root / "normalized" / "character" / "CHAR_HS_SYNTHETIC_E01_VN.json"
    ).is_file()
    variant = json.loads(
        (
            output_root / "normalized" / "character" / "CHAR_HS_SYNTHETIC_E01_VN.json"
        ).read_text(encoding="utf-8")
    )
    assert variant["metadata"]["metadataStatus"] == "pending"
    assert variant["episodes"][0]["metadata"]["metadataStatus"] == "pending"
    assert variant["source"]["manifest"]["manifestMatched"] is False
    assert variant["source"]["manifest"]["matchedBy"] is None
    assert (
        variant["source"]["manifest"]["derivedFromManifestEpisode"]
        == "CHAR_HS_SYNTHETIC_E01"
    )
    assert variant["source"]["manifest"]["derivationType"] == "hscene_dynamic_exception"


def test_release_scope_report_is_schema_valid_and_anonymous(tmp_path):
    report, output_root = _run(tmp_path)
    schema = json.loads(
        (
            PROJECT_ROOT / "schemas" / "release_scope_normalization_report.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert list(Draft7Validator(schema).iter_errors(report)) == []
    stored = json.loads(
        (output_root / "release_scope_normalization_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert stored == report
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("EVT_SYNTHETIC", "CHAR_HS_SYNTHETIC", "合成イベント本文"):
        assert forbidden not in serialized


def test_release_scope_rejects_existing_output_without_modifying_it(tmp_path):
    raw_root, manifest_path, characters_path = _write_inputs(tmp_path)
    output_root = tmp_path / "existing"
    output_root.mkdir()
    marker = output_root / "marker.txt"
    marker.write_text("keep", encoding="utf-8")

    try:
        normalize_release_scope(
            raw_root=raw_root,
            manifest_path=manifest_path,
            output_root=output_root,
            characters_path=characters_path,
            commands_path=PROJECT_ROOT / "config" / "script_commands.yaml",
            story_schema_path=PROJECT_ROOT / "schemas" / "story.schema.json",
            manifest_schema_path=PROJECT_ROOT
            / "schemas"
            / "story_manifest.schema.json",
            report_schema_path=(
                PROJECT_ROOT
                / "schemas"
                / "release_scope_normalization_report.schema.json"
            ),
        )
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing output was not rejected")
    assert marker.read_text(encoding="utf-8") == "keep"


def test_release_scope_missing_raw_file_does_not_publish_partial_output(tmp_path):
    raw_root, manifest_path, characters_path = _write_inputs(tmp_path)
    next(raw_root.rglob("synthetic-event-episode1.dec")).unlink()
    output_root = tmp_path / "failed"

    try:
        normalize_release_scope(
            raw_root=raw_root,
            manifest_path=manifest_path,
            output_root=output_root,
            characters_path=characters_path,
            commands_path=PROJECT_ROOT / "config" / "script_commands.yaml",
            story_schema_path=PROJECT_ROOT / "schemas" / "story.schema.json",
            manifest_schema_path=PROJECT_ROOT
            / "schemas"
            / "story_manifest.schema.json",
            report_schema_path=(
                PROJECT_ROOT
                / "schemas"
                / "release_scope_normalization_report.schema.json"
            ),
        )
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("missing input was not rejected")
    assert not output_root.exists()
    assert not list(tmp_path.glob(".failed.tmp-*"))
    assert not (tmp_path / ".failed.lock").exists()


def test_release_scope_rejects_concurrent_output_lock(tmp_path):
    raw_root, manifest_path, characters_path = _write_inputs(tmp_path)
    output_root = tmp_path / "locked"
    lock_path = tmp_path / ".locked.lock"
    lock_path.write_text("another run", encoding="utf-8")

    with pytest.raises(FileExistsError, match="既に実行中"):
        normalize_release_scope(
            raw_root=raw_root,
            manifest_path=manifest_path,
            output_root=output_root,
            characters_path=characters_path,
            commands_path=PROJECT_ROOT / "config" / "script_commands.yaml",
            story_schema_path=PROJECT_ROOT / "schemas" / "story.schema.json",
            manifest_schema_path=PROJECT_ROOT
            / "schemas"
            / "story_manifest.schema.json",
            report_schema_path=(
                PROJECT_ROOT
                / "schemas"
                / "release_scope_normalization_report.schema.json"
            ),
        )

    assert lock_path.read_text(encoding="utf-8") == "another run"
    assert not output_root.exists()


def test_release_scope_rejects_unmanifested_hscene_body(tmp_path):
    raw_root, manifest_path, characters_path = _write_inputs(tmp_path)
    character_dir = raw_root / "CHARACTER" / "synthetic_character_export"
    (character_dir / "synthetic-H_scene2.dec").write_text(
        "未登録本体\n", encoding="utf-8"
    )
    (character_dir / "synthetic-H_scene2_n.dec").write_text(
        "未登録変種\n", encoding="utf-8"
    )
    output_root = tmp_path / "unmanifested"

    with pytest.raises(ValueError, match="manifest episode"):
        normalize_release_scope(
            raw_root=raw_root,
            manifest_path=manifest_path,
            output_root=output_root,
            characters_path=characters_path,
            commands_path=PROJECT_ROOT / "config" / "script_commands.yaml",
            story_schema_path=PROJECT_ROOT / "schemas" / "story.schema.json",
            manifest_schema_path=PROJECT_ROOT
            / "schemas"
            / "story_manifest.schema.json",
            report_schema_path=(
                PROJECT_ROOT
                / "schemas"
                / "release_scope_normalization_report.schema.json"
            ),
        )

    assert not output_root.exists()
    assert not list(tmp_path.glob(".unmanifested.tmp-*"))
    assert not (tmp_path / ".unmanifested.lock").exists()


def test_release_scope_rejects_hscene_body_raw_path_mismatch(tmp_path):
    raw_root, manifest_path, characters_path = _write_inputs(tmp_path)
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    character_episode = manifest["stories"][1]["episodes"][0]
    character_episode["rawPath"] = (
        "CHARACTER/synthetic_character_export/synthetic-H_scene1_n.dec"
    )
    character_episode["sourceFileName"] = "synthetic-H_scene1_n.dec"
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    output_root = tmp_path / "mismatched"

    with pytest.raises(ValueError, match="rawPath"):
        normalize_release_scope(
            raw_root=raw_root,
            manifest_path=manifest_path,
            output_root=output_root,
            characters_path=characters_path,
            commands_path=PROJECT_ROOT / "config" / "script_commands.yaml",
            story_schema_path=PROJECT_ROOT / "schemas" / "story.schema.json",
            manifest_schema_path=PROJECT_ROOT
            / "schemas"
            / "story_manifest.schema.json",
            report_schema_path=(
                PROJECT_ROOT
                / "schemas"
                / "release_scope_normalization_report.schema.json"
            ),
        )

    assert not output_root.exists()
    assert not list(tmp_path.glob(".mismatched.tmp-*"))
    assert not (tmp_path / ".mismatched.lock").exists()
