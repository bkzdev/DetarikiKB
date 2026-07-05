"""
tests/scripts/test_normalize_story_manifest_integration.py
scripts/normalize_story.py の --manifest/--raw-root/--manifest-strict
統合のCLIスモークテスト。

すべて合成データ (tmp_path配下に組み立てるstory_manifest.yaml、合成
最小.decファイル) のみを使う。実DECファイル・実イベント名・実WIKI由来
fixtureは一切使わない (docs/architecture/05_Parser/Story_Manifest_Design.md
参照)。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
NORMALIZE_SCRIPT = PROJECT_ROOT / "scripts" / "normalize_story.py"

SOURCE_KEY = "990101_sample_event"
STORY_ID = "EVT_990101_SAMPLE_EVENT"
RAW_DIR = f"EVENT/csl_script_event_{SOURCE_KEY}_export"
EPISODE_FILENAME = f"CAB-csl_script_event_{SOURCE_KEY}-episode1.dec"
EPISODE_RAW_PATH = f"{RAW_DIR}/{EPISODE_FILENAME}"

# 合成の最小DEC本文 (実データ・実キャラ名は一切含まない)。
SYNTHETIC_DEC_CONTENT = "@ChTalk 0\nこんにちは、これはテスト用のダミー本文です。\n"


def _write_manifest(path: Path, subtitle: str | None = None) -> None:
    document = {
        "schemaVersion": "0.1.0",
        "documentType": "story_manifest",
        "stories": [
            {
                "storyId": STORY_ID,
                "category": "event",
                "sourceKey": SOURCE_KEY,
                "title": "Synthetic Sample Event",
                "displayTitle": "Synthetic Sample Event",
                "metadataStatus": "confirmed",
                "rawDirectory": RAW_DIR,
                "notes": None,
                "episodes": [
                    {
                        "episodeId": f"{STORY_ID}_E01",
                        "episodeNumber": 1,
                        "subtitle": subtitle,
                        "displayTitle": "Episode 1",
                        "rawPath": EPISODE_RAW_PATH,
                        "sourceFileName": EPISODE_FILENAME,
                        "metadataStatus": "confirmed",
                        "notes": None,
                    }
                ],
            }
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(document, f, allow_unicode=True)


def _write_synthetic_dec(raw_root: Path) -> Path:
    export_dir = raw_root / RAW_DIR
    export_dir.mkdir(parents=True)
    dec_path = export_dir / EPISODE_FILENAME
    dec_path.write_text(SYNTHETIC_DEC_CONTENT, encoding="utf-8")
    return dec_path


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(NORMALIZE_SCRIPT), *args],
        capture_output=True,
        text=True,
    )


# ----------------------------------------------------------------
# --manifest指定時、matchedの場合
# ----------------------------------------------------------------


def test_manifest_match_populates_story_and_episode_metadata(tmp_path):
    raw_root = tmp_path / "raw_root"
    dec_path = _write_synthetic_dec(raw_root)
    manifest_path = tmp_path / "story_manifest.yaml"
    _write_manifest(manifest_path, subtitle="Synthetic Episode Subtitle")
    output_dir = tmp_path / "out"

    result = _run_cli(
        [
            "--input",
            str(dec_path),
            "--output",
            str(output_dir),
            "--manifest",
            str(manifest_path),
            "--raw-root",
            str(raw_root),
            "--manifest-strict",
            "--quiet",
        ]
    )

    assert result.returncode == 0, result.stderr
    output_path = output_dir / f"{STORY_ID}_E01.json"
    assert output_path.is_file()

    with open(output_path, encoding="utf-8") as f:
        story_json = json.load(f)

    assert story_json["storyId"] == STORY_ID
    assert story_json["storyCategory"] == "EVT"
    assert story_json["metadata"]["storyTitle"] == "Synthetic Sample Event"
    assert story_json["metadata"]["displayTitle"] == "Synthetic Sample Event"
    assert story_json["metadata"]["metadataStatus"] == "confirmed"

    episode = story_json["episodes"][0]
    assert episode["episodeId"] == f"{STORY_ID}_E01"
    assert episode["metadata"]["episodeSubtitle"] == "Synthetic Episode Subtitle"
    assert episode["metadata"]["displayTitle"] == "Episode 1"
    assert episode["metadata"]["metadataStatus"] == "confirmed"

    manifest_info = story_json["source"]["manifest"]
    assert manifest_info["manifestMatched"] is True
    assert manifest_info["matchedBy"] == "raw_path"
    assert manifest_info["sourceFileName"] == EPISODE_FILENAME
    assert manifest_info["rawPath"] == EPISODE_RAW_PATH


def test_manifest_null_subtitle_is_preserved_as_null(tmp_path):
    """DEC本文からsubtitleを推測せず、manifestのnullがそのまま
    Normalized Story JSONへnullとして反映されることを確認する。"""
    raw_root = tmp_path / "raw_root"
    dec_path = _write_synthetic_dec(raw_root)
    manifest_path = tmp_path / "story_manifest.yaml"
    _write_manifest(manifest_path, subtitle=None)
    output_dir = tmp_path / "out"

    result = _run_cli(
        [
            "--input",
            str(dec_path),
            "--output",
            str(output_dir),
            "--manifest",
            str(manifest_path),
            "--raw-root",
            str(raw_root),
            "--quiet",
        ]
    )

    assert result.returncode == 0, result.stderr
    with open(output_dir / f"{STORY_ID}_E01.json", encoding="utf-8") as f:
        story_json = json.load(f)

    assert story_json["episodes"][0]["metadata"]["episodeSubtitle"] is None


def test_manifest_does_not_infer_subtitle_from_dec_body(tmp_path):
    """DEC本文中の文言 (ダミー本文の一部) が、subtitle等のメタデータ
    フィールドに紛れ込んでいないことを確認する (DEC本文からの推測をしない
    方針)。episodeSubtitle/displayTitle/storyTitleはmanifest由来の値の
    みで構成され、DEC本文の文言 (dialogue block内には正当に含まれる) が
    メタデータ側へ紛れ込んでいないことを確認する。"""
    raw_root = tmp_path / "raw_root"
    dec_path = _write_synthetic_dec(raw_root)
    manifest_path = tmp_path / "story_manifest.yaml"
    _write_manifest(manifest_path, subtitle=None)
    output_dir = tmp_path / "out"

    result = _run_cli(
        [
            "--input",
            str(dec_path),
            "--output",
            str(output_dir),
            "--manifest",
            str(manifest_path),
            "--raw-root",
            str(raw_root),
            "--quiet",
        ]
    )

    assert result.returncode == 0, result.stderr
    with open(output_dir / f"{STORY_ID}_E01.json", encoding="utf-8") as f:
        story_json = json.load(f)

    assert story_json["episodes"][0]["metadata"]["episodeSubtitle"] is None
    metadata_serialized = json.dumps(
        {
            "storyMetadata": story_json["metadata"],
            "episodeMetadata": story_json["episodes"][0]["metadata"],
        },
        ensure_ascii=False,
    )
    assert "ダミー本文" not in metadata_serialized
    # DEC本文自体は正当にdialogue blockへ含まれる (evidenceとして保持する
    # 既存方針、Normalized Story JSONはWiki出力と異なり全文を保持する)。
    serialized_full = json.dumps(story_json, ensure_ascii=False)
    assert "ダミー本文" in serialized_full


def test_manifest_match_via_source_filename_fallback(tmp_path):
    """rawPathが一致しない場所にファイルを置いても、sourceFileNameの
    一致でmatchedとして解決されることを確認する (--raw-root未指定)。"""
    unrelated_dir = tmp_path / "somewhere_else"
    unrelated_dir.mkdir()
    dec_path = unrelated_dir / EPISODE_FILENAME
    dec_path.write_text(SYNTHETIC_DEC_CONTENT, encoding="utf-8")

    manifest_path = tmp_path / "story_manifest.yaml"
    _write_manifest(manifest_path)
    output_dir = tmp_path / "out"

    result = _run_cli(
        [
            "--input",
            str(dec_path),
            "--output",
            str(output_dir),
            "--manifest",
            str(manifest_path),
            "--quiet",
        ]
    )

    assert result.returncode == 0, result.stderr
    with open(output_dir / f"{STORY_ID}_E01.json", encoding="utf-8") as f:
        story_json = json.load(f)
    assert story_json["storyId"] == STORY_ID
    assert story_json["source"]["manifest"]["matchedBy"] == "source_file_name"


# ----------------------------------------------------------------
# unmatched / ambiguous
# ----------------------------------------------------------------


def test_manifest_unmatched_without_strict_falls_back_with_explicit_ids(tmp_path):
    raw_root = tmp_path / "raw_root"
    dec_path = _write_synthetic_dec(raw_root)
    empty_manifest_path = tmp_path / "empty_manifest.yaml"
    with open(empty_manifest_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"schemaVersion": "0.1.0", "documentType": "story_manifest", "stories": []},
            f,
        )
    output_dir = tmp_path / "out"

    result = _run_cli(
        [
            "--input",
            str(dec_path),
            "--output",
            str(output_dir),
            "--manifest",
            str(empty_manifest_path),
            "--story-id",
            "EVT_FALLBACK_TEST",
            "--category",
            "EVT",
            "--quiet",
        ]
    )

    assert result.returncode == 0, result.stderr
    assert "見つかりません" in result.stderr
    output_path = output_dir / "EVT_FALLBACK_TEST_E01.json"
    assert output_path.is_file()


def test_manifest_unmatched_without_strict_and_without_explicit_ids_fails(tmp_path):
    """--manifestが一致せず、--story-id/--categoryも明示されていない場合は
    (--manifest-strict未指定でも) 必須引数不足としてexit 1になる。"""
    raw_root = tmp_path / "raw_root"
    dec_path = _write_synthetic_dec(raw_root)
    empty_manifest_path = tmp_path / "empty_manifest.yaml"
    with open(empty_manifest_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"schemaVersion": "0.1.0", "documentType": "story_manifest", "stories": []},
            f,
        )

    result = _run_cli(
        [
            "--input",
            str(dec_path),
            "--output",
            str(tmp_path / "out"),
            "--manifest",
            str(empty_manifest_path),
            "--quiet",
        ]
    )

    assert result.returncode == 1
    assert "必須です" in result.stderr


def test_manifest_strict_fails_on_unmatched(tmp_path):
    raw_root = tmp_path / "raw_root"
    dec_path = _write_synthetic_dec(raw_root)
    empty_manifest_path = tmp_path / "empty_manifest.yaml"
    with open(empty_manifest_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"schemaVersion": "0.1.0", "documentType": "story_manifest", "stories": []},
            f,
        )

    result = _run_cli(
        [
            "--input",
            str(dec_path),
            "--output",
            str(tmp_path / "out"),
            "--manifest",
            str(empty_manifest_path),
            "--manifest-strict",
            "--quiet",
        ]
    )

    assert result.returncode == 1
    assert "unmatched" in result.stderr


def test_manifest_strict_fails_on_ambiguous(tmp_path):
    duplicate_filename = "CAB-csl_script_event_duplicate-episode1.dec"
    manifest_document = {
        "schemaVersion": "0.1.0",
        "documentType": "story_manifest",
        "stories": [
            {
                "storyId": "EVT_A",
                "category": "event",
                "sourceKey": "a",
                "title": None,
                "displayTitle": None,
                "metadataStatus": "pending",
                "rawDirectory": "EVENT/a_export",
                "notes": None,
                "episodes": [
                    {
                        "episodeId": "EVT_A_E01",
                        "episodeNumber": 1,
                        "subtitle": None,
                        "displayTitle": None,
                        "rawPath": f"EVENT/a_export/{duplicate_filename}",
                        "sourceFileName": duplicate_filename,
                        "metadataStatus": "pending",
                        "notes": None,
                    }
                ],
            },
            {
                "storyId": "EVT_B",
                "category": "event",
                "sourceKey": "b",
                "title": None,
                "displayTitle": None,
                "metadataStatus": "pending",
                "rawDirectory": "EVENT/b_export",
                "notes": None,
                "episodes": [
                    {
                        "episodeId": "EVT_B_E01",
                        "episodeNumber": 1,
                        "subtitle": None,
                        "displayTitle": None,
                        "rawPath": f"EVENT/b_export/{duplicate_filename}",
                        "sourceFileName": duplicate_filename,
                        "metadataStatus": "pending",
                        "notes": None,
                    }
                ],
            },
        ],
    }
    manifest_path = tmp_path / "story_manifest.yaml"
    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(manifest_document, f)

    unrelated_dir = tmp_path / "somewhere_else"
    unrelated_dir.mkdir()
    dec_path = unrelated_dir / duplicate_filename
    dec_path.write_text(SYNTHETIC_DEC_CONTENT, encoding="utf-8")

    result = _run_cli(
        [
            "--input",
            str(dec_path),
            "--output",
            str(tmp_path / "out"),
            "--manifest",
            str(manifest_path),
            "--manifest-strict",
            "--quiet",
        ]
    )

    assert result.returncode == 1
    assert "ambiguous" in result.stderr


def test_manifest_missing_file_returns_exit_1(tmp_path):
    raw_root = tmp_path / "raw_root"
    dec_path = _write_synthetic_dec(raw_root)

    result = _run_cli(
        [
            "--input",
            str(dec_path),
            "--output",
            str(tmp_path / "out"),
            "--manifest",
            str(tmp_path / "does_not_exist.yaml"),
            "--story-id",
            "EVT_FALLBACK_TEST",
            "--category",
            "EVT",
            "--quiet",
        ]
    )

    assert result.returncode == 1
    assert "見つかりません" in result.stderr


# ----------------------------------------------------------------
# --manifest 未指定時の既存挙動維持
# ----------------------------------------------------------------


def test_without_manifest_existing_behavior_unchanged(tmp_path):
    raw_root = tmp_path / "raw_root"
    dec_path = _write_synthetic_dec(raw_root)
    output_dir = tmp_path / "out"

    result = _run_cli(
        [
            "--input",
            str(dec_path),
            "--story-id",
            "OTHER_EXISTING_BEHAVIOR",
            "--category",
            "OTHER",
            "--output",
            str(output_dir),
            "--quiet",
        ]
    )

    assert result.returncode == 0, result.stderr
    with open(output_dir / "OTHER_EXISTING_BEHAVIOR_E01.json", encoding="utf-8") as f:
        story_json = json.load(f)

    assert story_json["storyId"] == "OTHER_EXISTING_BEHAVIOR"
    assert "manifest" not in story_json["source"]
    assert "metadataStatus" not in story_json["metadata"]


def test_without_manifest_still_requires_story_id_and_category(tmp_path):
    """--manifest未指定時は、従来通り--story-id/--categoryが必須のままで
    あることを確認する。"""
    raw_root = tmp_path / "raw_root"
    dec_path = _write_synthetic_dec(raw_root)

    result = _run_cli(
        [
            "--input",
            str(dec_path),
            "--output",
            str(tmp_path / "out"),
            "--quiet",
        ]
    )

    assert result.returncode == 1
    assert "必須です" in result.stderr
