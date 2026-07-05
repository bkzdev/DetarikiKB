"""
DKB Parser - Story Manifest Candidate Builder
ローカルのraw DECファイル配置（`EVENT`カテゴリのみ）から、
`story_manifest.yaml`候補（`schemas/story_manifest.schema.json`準拠）を
機械的に生成する。

docs/architecture/05_Parser/Story_Manifest_Design.md 参照。

**重要**: このモジュールはDEC本文を一切読まない（ファイル名・ディレクトリ名の
文字列処理のみ）。title/subtitle/displayTitleは常にnull、metadataStatusは
常にpendingとして組み立てる。他カテゴリ（MAIN/RAID/OTHER/CHARACTER）の
raw配置規約は未確認のため、このモジュールはEVENTカテゴリのみに対応する
（Story_Manifest_Design.md §6・§18 OD-002/OD-003）。
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = "0.1.0"
DOCUMENT_TYPE = "story_manifest"
METADATA_STATUS_PENDING = "pending"

# EVENT/csl_script_event_{sourceKey}_export ディレクトリ名パターン
_EXPORT_DIRECTORY_PATTERN = re.compile(
    r"^csl_script_event_(?P<source_key>.+)_export$", re.IGNORECASE
)

# CAB-csl_script_event_{sourceKey}-episode{N}.dec ファイル名パターン
_EPISODE_FILE_PATTERN = re.compile(
    r"^CAB-csl_script_event_(?P<source_key>.+)-episode(?P<episode_number>\d+)\.dec$",
    re.IGNORECASE,
)


def normalize_path_separators(path: str) -> str:
    """Windowsのバックスラッシュ区切りをスラッシュ区切りへ正規化する
    (Story_Manifest_Design.md §5)。"""
    return path.replace("\\", "/")


def _relative_posix_path(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    return normalize_path_separators(str(PurePosixPath(*relative.parts)))


def parse_export_directory_name(name: str) -> str | None:
    """ディレクトリ名から sourceKey を抽出する。一致しなければNone。"""
    match = _EXPORT_DIRECTORY_PATTERN.match(name)
    if match is None:
        return None
    return match.group("source_key")


def parse_episode_filename(name: str, expected_source_key: str) -> int | None:
    """ファイル名から episodeNumber を抽出する。

    ディレクトリ名から抽出したsourceKeyと一致しない場合はNoneを返す
    (認識できないファイルとして候補生成対象外にする、Story_Manifest_Design.md §16)。
    """
    match = _EPISODE_FILE_PATTERN.match(name)
    if match is None:
        return None
    if match.group("source_key").lower() != expected_source_key.lower():
        return None
    return int(match.group("episode_number"))


def build_story_manifest_candidate(
    export_dir: Path, raw_root: Path
) -> dict[str, Any] | None:
    """1つの`_export`ディレクトリからstory manifest候補エントリを組み立てる。

    対象となる`.dec`ファイルが1件も見つからない場合はNoneを返す。
    """
    source_key = parse_export_directory_name(export_dir.name)
    if source_key is None:
        return None

    story_id = f"EVT_{source_key.upper()}"
    episodes: list[dict[str, Any]] = []
    for entry in export_dir.iterdir():
        if not entry.is_file():
            continue
        episode_number = parse_episode_filename(entry.name, source_key)
        if episode_number is None:
            continue
        episodes.append(
            {
                "episodeId": f"{story_id}_E{episode_number:02d}",
                "episodeNumber": episode_number,
                "subtitle": None,
                "displayTitle": None,
                "rawPath": _relative_posix_path(entry, raw_root),
                "sourceFileName": entry.name,
                "metadataStatus": METADATA_STATUS_PENDING,
                "notes": None,
            }
        )

    if not episodes:
        return None

    episodes.sort(key=lambda episode: episode["episodeNumber"])

    return {
        "storyId": story_id,
        "category": "event",
        "sourceKey": source_key,
        "title": None,
        "displayTitle": None,
        "metadataStatus": METADATA_STATUS_PENDING,
        "rawDirectory": _relative_posix_path(export_dir, raw_root),
        "notes": None,
        "episodes": episodes,
    }


def find_event_category_directory(raw_root: Path) -> Path | None:
    """raw_root直下のEVENTディレクトリを探す (大文字小文字を区別しない)。"""
    for entry in raw_root.iterdir():
        if entry.is_dir() and entry.name.lower() == "event":
            return entry
    return None


def build_story_manifest_candidates(raw_root: Path) -> list[dict[str, Any]]:
    """raw_root配下のEVENTカテゴリから、story manifest候補一覧を組み立てる。

    storyId順にソートして返す (他カテゴリはStory_Manifest_Design.md §6の通り
    このモジュールでは未対応)。
    """
    event_dir = find_event_category_directory(raw_root)
    if event_dir is None:
        return []

    candidates: list[dict[str, Any]] = []
    for entry in event_dir.iterdir():
        if not entry.is_dir():
            continue
        candidate = build_story_manifest_candidate(entry, raw_root)
        if candidate is not None:
            candidates.append(candidate)

    candidates.sort(key=lambda story: story["storyId"])
    return candidates


def build_candidate_document(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "documentType": DOCUMENT_TYPE,
        "stories": candidates,
    }
