"""
DKB Parser - Story Title/Subtitle Candidate Builder
外部情報源（Wiki story list、公式告知、ゲーム画面メモ等）から取得した
title/subtitle候補を、`story_manifest.yaml`へ直接書き込まず
「import candidate」ドキュメント（`documentType: "story_title_subtitle_candidates"`）
として組み立てる。

docs/architecture/05_Parser/Story_Manifest_Design.md §11.7 参照。

**重要**: このモジュールはDEC本文を読まず、AIによるタイトル生成も行わない。
CSV入力に書かれた値をそのまま候補として保持するのみで、
`story_manifest.yaml`への反映（confirmed化）は一切行わない。すべての候補は
`reviewStatus: "pending"`として出力される。
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .story_manifest import StoryManifest

SCHEMA_VERSION = "0.1.0"
DOCUMENT_TYPE = "story_title_subtitle_candidates"
REVIEW_STATUS_PENDING = "pending"


def read_candidate_rows_from_csv(path: str | Path) -> list[dict[str, str]]:
    """CSVファイルを読み込み、行のリストとして返す。

    想定する列: storyId/episodeId/episodeNumber/proposedTitle/
    proposedDisplayTitle/proposedSubtitle/confidence/notes
    （episodeId以降はエピソード単位の行にのみ必要、ストーリー単位の行では
    空でよい）。
    """
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _story_exists(manifest: StoryManifest | None, story_id: str) -> bool:
    if manifest is None:
        return False
    return any(story.story_id == story_id for story in manifest.stories)


def _episode_exists(
    manifest: StoryManifest | None, story_id: str, episode_id: str
) -> bool:
    if manifest is None:
        return False
    for story in manifest.stories:
        if story.story_id != story_id:
            continue
        return any(episode.episode_id == episode_id for episode in story.episodes)
    return False


def _merge_story_fields(story: dict[str, Any], row: dict[str, str]) -> None:
    if story["proposedTitle"] is None:
        story["proposedTitle"] = _blank_to_none(row.get("proposedTitle"))
    if story["proposedDisplayTitle"] is None:
        story["proposedDisplayTitle"] = _blank_to_none(row.get("proposedDisplayTitle"))


def _build_episode_candidate(row: dict[str, str], episode_id: str) -> dict[str, Any]:
    episode_number_raw = _blank_to_none(row.get("episodeNumber"))
    return {
        "episodeId": episode_id,
        "episodeNumber": int(episode_number_raw) if episode_number_raw else None,
        "proposedSubtitle": _blank_to_none(row.get("proposedSubtitle")),
        "confidence": _blank_to_none(row.get("confidence")) or "source_exact",
        "reviewStatus": REVIEW_STATUS_PENDING,
        "notes": _blank_to_none(row.get("notes")),
    }


def build_candidates_from_rows(
    rows: list[dict[str, str]], manifest: StoryManifest | None = None
) -> list[dict[str, Any]]:
    """CSV行群を`storyId`単位でグルーピングし、candidate構造
    （story + episodes）を組み立てる。

    `manifest`を渡すと、各`storyId`/`episodeId`がmanifestに実在するかを
    `foundInManifest`として記録する（Story_Manifest_Design.md §11.7）。
    **一致有無に関わらず、candidateとしては必ず出力する**
    （unmatchedを黙って捨てない）。
    """
    stories_by_id: dict[str, dict[str, Any]] = {}

    for row in rows:
        story_id = _blank_to_none(row.get("storyId"))
        if story_id is None:
            continue

        story = stories_by_id.setdefault(
            story_id,
            {
                "storyId": story_id,
                "proposedTitle": None,
                "proposedDisplayTitle": None,
                "foundInManifest": _story_exists(manifest, story_id),
                "episodes": [],
            },
        )
        _merge_story_fields(story, row)

        episode_id = _blank_to_none(row.get("episodeId"))
        if episode_id is None:
            continue

        episode = _build_episode_candidate(row, episode_id)
        episode["foundInManifest"] = _episode_exists(manifest, story_id, episode_id)
        story["episodes"].append(episode)

    return list(stories_by_id.values())


def build_candidate_document(
    candidates: list[dict[str, Any]],
    source_type: str,
    source_label: str | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "documentType": DOCUMENT_TYPE,
        "source": {
            "sourceType": source_type,
            "label": source_label,
            "fetchedAt": None,
        },
        "candidates": candidates,
    }
