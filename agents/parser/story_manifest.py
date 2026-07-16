"""
DKB Parser - Story Manifest Loader
`story_manifest.yaml`（`docs/architecture/05_Parser/Story_Manifest_Design.md`
準拠）を読み込み、raw DECファイルパスに対応するepisode entryを検索する。

`knowledge/dictionaries/characters.yaml`（ID解決用辞書、
`agents/parser/character_dictionary.py`）とは別物であり、raw DECファイル
配置 ⇔ storyId/episodeId/title/subtitle/rawPathの対応を保持する。

`publicStoryId`/`publicEpisodeId`は将来の公開Wiki URL用の任意フィールド
（`Story_ID_Policy_Decision.md` §7）。未設定時は`None`のまま保持し、
既存`storyId`/`episodeId`へのfallbackは呼び出し側の責務とする
（このモジュール自体はfallback判定を行わない）。

**重要**: このモジュールはDEC本文を一切読まない。subtitle等の値は
manifestに書かれた値をそのまま返すのみで、推測・生成は一切行わない。
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# story_manifest.yamlのcategory (小文字) -> scripts/normalize_story.pyの
# --category (Identifier_Specification.md準拠、大文字prefix) への対応。
# characterは3種類のprefix (CHAR_MAIN/CHAR_EXTRA/CHAR_DATE) のいずれに
# 該当するかraw配置だけからは判定できないため、意図的に対応表へ含めない
# (Story_Manifest_Design.md §6、§18 OD-003)。
MANIFEST_CATEGORY_TO_STORY_CATEGORY: dict[str, str] = {
    "main": "MAIN",
    "event": "EVT",
    "raid": "RAID",
    "other": "OTHER",
}


def resolve_story_category(manifest_category: str) -> str | None:
    """story_manifest.yamlのcategoryから、normalize_story.pyの`--category`
    相当の値を解決する。対応が無い場合 (例: character) はNoneを返す。"""
    return MANIFEST_CATEGORY_TO_STORY_CATEGORY.get(manifest_category)


def normalize_manifest_path(path: str) -> str:
    """バックスラッシュ区切りをスラッシュ区切りへ正規化し、`./`や連続する
    スラッシュを整理する (Story_Manifest_Design.md §5)。"""
    posix_path = path.replace("\\", "/")
    return posixpath.normpath(posix_path)


@dataclass
class StoryManifestEpisode:
    """1エピソード分のmanifestエントリ。"""

    episode_id: str
    episode_number: int
    subtitle: str | None
    display_title: str | None
    raw_path: str
    source_file_name: str
    metadata_status: str
    notes: str | None = None
    public_episode_id: str | None = None


@dataclass
class StoryManifestAuxiliaryFile:
    """story-levelの補助ファイル記録（H_scene変種・camera/finish等の演出コマンド
    専用ファイル等、独立episodeとしてはパースしないファイルの記録）。
    `Character_Story_ID_Manifest_Design.md` §8.1準拠。"""

    raw_path: str
    source_file_name: str
    file_role: str
    notes: str | None = None


@dataclass
class StoryManifestStory:
    """1ストーリー分のmanifestエントリ。"""

    story_id: str
    category: str
    source_key: str
    title: str | None
    display_title: str | None
    metadata_status: str
    raw_directory: str
    episodes: list[StoryManifestEpisode] = field(default_factory=list)
    notes: str | None = None
    public_story_id: str | None = None
    character_id: str | None = None
    auxiliary_files: list[StoryManifestAuxiliaryFile] = field(default_factory=list)


@dataclass
class StoryManifest:
    """`story_manifest.yaml`全体。"""

    schema_version: str
    stories: list[StoryManifestStory] = field(default_factory=list)


@dataclass
class StoryManifestLookupResult:
    """story_manifestからのepisode検索結果。

    `status`: `"matched"`（一意に一致）/ `"unmatched"`（一致なし）/
    `"ambiguous"`（sourceFileNameが複数エントリと一致し一意に決定できない）。
    `matched_by`: `"raw_path"` / `"source_file_name"`
    （statusが`"matched"`の場合のみ設定される）。
    """

    status: str
    story: StoryManifestStory | None = None
    episode: StoryManifestEpisode | None = None
    matched_by: str | None = None


def _parse_episode(raw: dict[str, Any]) -> StoryManifestEpisode:
    return StoryManifestEpisode(
        episode_id=raw.get("episodeId", ""),
        episode_number=raw.get("episodeNumber", 0),
        subtitle=raw.get("subtitle"),
        display_title=raw.get("displayTitle"),
        raw_path=raw.get("rawPath", ""),
        source_file_name=raw.get("sourceFileName", ""),
        metadata_status=raw.get("metadataStatus", "pending"),
        notes=raw.get("notes"),
        public_episode_id=raw.get("publicEpisodeId"),
    )


def _parse_auxiliary_file(raw: dict[str, Any]) -> StoryManifestAuxiliaryFile:
    return StoryManifestAuxiliaryFile(
        raw_path=raw.get("rawPath", ""),
        source_file_name=raw.get("sourceFileName", ""),
        file_role=raw.get("fileRole", ""),
        notes=raw.get("notes"),
    )


def _parse_story(raw: dict[str, Any]) -> StoryManifestStory:
    episodes = [_parse_episode(e) for e in raw.get("episodes", []) or []]
    auxiliary_files = [
        _parse_auxiliary_file(a) for a in raw.get("auxiliaryFiles", []) or []
    ]
    return StoryManifestStory(
        story_id=raw.get("storyId", ""),
        category=raw.get("category", ""),
        source_key=raw.get("sourceKey", ""),
        title=raw.get("title"),
        display_title=raw.get("displayTitle"),
        metadata_status=raw.get("metadataStatus", "pending"),
        raw_directory=raw.get("rawDirectory", ""),
        episodes=episodes,
        notes=raw.get("notes"),
        public_story_id=raw.get("publicStoryId"),
        character_id=raw.get("characterId"),
        auxiliary_files=auxiliary_files,
    )


def load_story_manifest(path: str | Path) -> StoryManifest:
    """`story_manifest.yaml`相当のYAMLを読み込む。

    ファイルが存在しない場合は空の`StoryManifest`を返す
    (`agents/parser/character_profiles.py`の`load_character_profiles`と
    同じ方針)。呼び出し側 (CLI等) が「ファイルが存在するべきなのに無い」
    ことをエラー扱いするかどうかを判断する。
    """
    p = Path(path)
    if not p.exists():
        return StoryManifest(schema_version="")

    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    stories = [_parse_story(s) for s in data.get("stories", []) or []]
    return StoryManifest(schema_version=data.get("schemaVersion", ""), stories=stories)


def find_episode_by_raw_path(
    manifest: StoryManifest, input_path: Path, raw_root: Path | None = None
) -> tuple[StoryManifestStory, StoryManifestEpisode] | None:
    """rawPath一致でepisodeを検索する。

    `raw_root`指定時は、`input_path`を`raw_root`相対に変換した上で
    `episode.rawPath`と完全一致するか確認する（優先順位1）。一致しなければ、
    正規化した`input_path`の末尾が`episode.rawPath`と一致するかで比較する
    （優先順位2、suffix match。`raw_root`未指定の場合もこちらで判定する）。
    一致が無ければNoneを返す。
    """
    relative_candidate: str | None = None
    if raw_root is not None:
        try:
            relative_candidate = normalize_manifest_path(
                str(input_path.resolve().relative_to(raw_root.resolve()))
            )
        except ValueError:
            relative_candidate = None

    if relative_candidate is not None:
        for story in manifest.stories:
            for episode in story.episodes:
                if relative_candidate == normalize_manifest_path(episode.raw_path):
                    return story, episode

    normalized_input = normalize_manifest_path(str(input_path))
    for story in manifest.stories:
        for episode in story.episodes:
            episode_raw_path = normalize_manifest_path(episode.raw_path)
            if normalized_input == episode_raw_path or normalized_input.endswith(
                "/" + episode_raw_path
            ):
                return story, episode

    return None


def find_episode_by_source_filename(
    manifest: StoryManifest, source_file_name: str
) -> list[tuple[StoryManifestStory, StoryManifestEpisode]]:
    """sourceFileName一致でepisodeを検索する（優先順位3）。

    一致した全件をリストで返す（呼び出し側で複数一致=ambiguousと判定できる
    ように、ここでは絞り込みを行わない）。
    """
    matches: list[tuple[StoryManifestStory, StoryManifestEpisode]] = []
    for story in manifest.stories:
        for episode in story.episodes:
            if episode.source_file_name == source_file_name:
                matches.append((story, episode))
    return matches


def resolve_manifest_episode(
    manifest: StoryManifest, input_path: Path, raw_root: Path | None = None
) -> StoryManifestLookupResult:
    """`input_path`に対応するepisode entryを、優先順位に従って検索する
    （rawPath一致 > sourceFileName一致、Story_Manifest_Design.md準拠）。
    """
    raw_path_match = find_episode_by_raw_path(manifest, input_path, raw_root)
    if raw_path_match is not None:
        story, episode = raw_path_match
        return StoryManifestLookupResult(
            status="matched", story=story, episode=episode, matched_by="raw_path"
        )

    filename_matches = find_episode_by_source_filename(manifest, input_path.name)
    if len(filename_matches) == 1:
        story, episode = filename_matches[0]
        return StoryManifestLookupResult(
            status="matched",
            story=story,
            episode=episode,
            matched_by="source_file_name",
        )
    if len(filename_matches) > 1:
        return StoryManifestLookupResult(status="ambiguous")

    return StoryManifestLookupResult(status="unmatched")
