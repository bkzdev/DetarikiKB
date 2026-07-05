"""
tests/parser/test_story_manifest.py
agents/parser/story_manifest.py のユニットテスト。

すべて合成データ (tmp_path配下に組み立てるstory_manifest.yaml、および
テスト内で直接組み立てるStoryManifest) のみを使う。実DECファイル・
実イベント名・実データ由来fixtureは一切使わない
(docs/architecture/05_Parser/Story_Manifest_Design.md 参照)。
"""

from __future__ import annotations

from pathlib import Path, PureWindowsPath

import yaml

from agents.parser.story_manifest import (
    StoryManifest,
    StoryManifestEpisode,
    StoryManifestStory,
    find_episode_by_raw_path,
    find_episode_by_source_filename,
    load_story_manifest,
    normalize_manifest_path,
    resolve_manifest_episode,
    resolve_story_category,
)

SOURCE_KEY = "250626_synthetic_dancer"
STORY_ID = "EVT_250626_SYNTHETIC_DANCER"
RAW_DIR = f"EVENT/csl_script_event_{SOURCE_KEY}_export"
EPISODE_1_FILENAME = f"CAB-csl_script_event_{SOURCE_KEY}-episode1.dec"
EPISODE_1_RAW_PATH = f"{RAW_DIR}/{EPISODE_1_FILENAME}"


def _synthetic_manifest_dict(**episode_overrides) -> dict:
    episode = {
        "episodeId": f"{STORY_ID}_E01",
        "episodeNumber": 1,
        "subtitle": None,
        "displayTitle": None,
        "rawPath": EPISODE_1_RAW_PATH,
        "sourceFileName": EPISODE_1_FILENAME,
        "metadataStatus": "pending",
        "notes": None,
    }
    episode.update(episode_overrides)
    return {
        "schemaVersion": "0.1.0",
        "documentType": "story_manifest",
        "stories": [
            {
                "storyId": STORY_ID,
                "category": "event",
                "sourceKey": SOURCE_KEY,
                "title": None,
                "displayTitle": None,
                "metadataStatus": "pending",
                "rawDirectory": RAW_DIR,
                "notes": None,
                "episodes": [episode],
            }
        ],
    }


def _write_manifest(path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)


# ----------------------------------------------------------------
# resolve_story_category
# ----------------------------------------------------------------


def test_resolve_story_category_maps_event_to_evt():
    assert resolve_story_category("event") == "EVT"


def test_resolve_story_category_maps_main_raid_other():
    assert resolve_story_category("main") == "MAIN"
    assert resolve_story_category("raid") == "RAID"
    assert resolve_story_category("other") == "OTHER"


def test_resolve_story_category_returns_none_for_character():
    """CHAR_MAIN/CHAR_EXTRA/CHAR_DATEのいずれか判定できないため、
    characterカテゴリは自動解決しない (Story_Manifest_Design.md §18 OD-003)。"""
    assert resolve_story_category("character") is None


def test_resolve_story_category_returns_none_for_unknown():
    assert resolve_story_category("unknown_category") is None


# ----------------------------------------------------------------
# normalize_manifest_path
# ----------------------------------------------------------------


def test_normalize_manifest_path_converts_backslashes():
    assert (
        normalize_manifest_path("EVENT\\csl_script_event_x_export\\CAB-x.dec")
        == "EVENT/csl_script_event_x_export/CAB-x.dec"
    )


def test_normalize_manifest_path_strips_leading_dot_slash():
    assert normalize_manifest_path("./EVENT/x/y.dec") == "EVENT/x/y.dec"


def test_normalize_manifest_path_collapses_duplicate_slashes():
    assert normalize_manifest_path("EVENT//x///y.dec") == "EVENT/x/y.dec"


# ----------------------------------------------------------------
# load_story_manifest
# ----------------------------------------------------------------


def test_load_story_manifest_reads_stories_and_episodes(tmp_path):
    manifest_path = tmp_path / "story_manifest.yaml"
    _write_manifest(manifest_path, _synthetic_manifest_dict())

    manifest = load_story_manifest(manifest_path)

    assert len(manifest.stories) == 1
    story = manifest.stories[0]
    assert story.story_id == STORY_ID
    assert story.category == "event"
    assert len(story.episodes) == 1
    assert story.episodes[0].episode_id == f"{STORY_ID}_E01"
    assert story.episodes[0].raw_path == EPISODE_1_RAW_PATH


def test_load_story_manifest_preserves_null_subtitle(tmp_path):
    manifest_path = tmp_path / "story_manifest.yaml"
    _write_manifest(manifest_path, _synthetic_manifest_dict(subtitle=None))

    manifest = load_story_manifest(manifest_path)

    assert manifest.stories[0].episodes[0].subtitle is None


def test_load_story_manifest_returns_empty_manifest_for_missing_file(tmp_path):
    manifest = load_story_manifest(tmp_path / "does_not_exist.yaml")
    assert manifest.stories == []


# ----------------------------------------------------------------
# find_episode_by_raw_path
# ----------------------------------------------------------------


def test_find_episode_by_raw_path_matches_windows_style_input(tmp_path):
    """Windows風 `EVENT\\...\\file.dec` の入力パスと、manifestの
    `EVENT/.../file.dec` (スラッシュ区切り) が一致することを確認する。"""
    manifest_path = tmp_path / "story_manifest.yaml"
    _write_manifest(manifest_path, _synthetic_manifest_dict())
    manifest = load_story_manifest(manifest_path)

    windows_style_input = PureWindowsPath(EPISODE_1_RAW_PATH.replace("/", "\\"))

    result = find_episode_by_raw_path(manifest, windows_style_input, raw_root=None)

    assert result is not None
    story, episode = result
    assert story.story_id == STORY_ID
    assert episode.episode_id == f"{STORY_ID}_E01"


def test_find_episode_by_raw_path_matches_with_raw_root(tmp_path):
    """raw_root指定時、input pathをraw_root相対に変換して一致させる。"""
    manifest_path = tmp_path / "story_manifest.yaml"
    _write_manifest(manifest_path, _synthetic_manifest_dict())
    manifest = load_story_manifest(manifest_path)

    raw_root = tmp_path / "raw_root"
    export_dir = raw_root / RAW_DIR
    export_dir.mkdir(parents=True)
    input_path = export_dir / EPISODE_1_FILENAME
    input_path.write_text("", encoding="utf-8")

    result = find_episode_by_raw_path(manifest, input_path, raw_root=raw_root)

    assert result is not None
    story, episode = result
    assert episode.episode_id == f"{STORY_ID}_E01"


def test_find_episode_by_raw_path_matches_suffix_without_raw_root(tmp_path):
    """raw_root未指定でも、正規化input pathの末尾がepisode.rawPathと
    一致すれば検出できる (suffix match)。"""
    manifest_path = tmp_path / "story_manifest.yaml"
    _write_manifest(manifest_path, _synthetic_manifest_dict())
    manifest = load_story_manifest(manifest_path)

    input_path = Path("/some/local/checkout") / RAW_DIR / EPISODE_1_FILENAME

    result = find_episode_by_raw_path(manifest, input_path, raw_root=None)

    assert result is not None


def test_find_episode_by_raw_path_returns_none_when_no_match(tmp_path):
    manifest_path = tmp_path / "story_manifest.yaml"
    _write_manifest(manifest_path, _synthetic_manifest_dict())
    manifest = load_story_manifest(manifest_path)

    result = find_episode_by_raw_path(
        manifest, Path("/unrelated/path/unrelated.dec"), raw_root=None
    )

    assert result is None


# ----------------------------------------------------------------
# find_episode_by_source_filename
# ----------------------------------------------------------------


def test_find_episode_by_source_filename_matches_single_entry(tmp_path):
    manifest_path = tmp_path / "story_manifest.yaml"
    _write_manifest(manifest_path, _synthetic_manifest_dict())
    manifest = load_story_manifest(manifest_path)

    matches = find_episode_by_source_filename(manifest, EPISODE_1_FILENAME)

    assert len(matches) == 1
    assert matches[0][1].episode_id == f"{STORY_ID}_E01"


def test_find_episode_by_source_filename_returns_empty_for_no_match():
    manifest = StoryManifest(schema_version="0.1.0", stories=[])
    assert find_episode_by_source_filename(manifest, "not_found.dec") == []


def test_find_episode_by_source_filename_detects_ambiguous_matches():
    """同名sourceFileNameが複数のepisodeエントリに存在する場合、
    呼び出し側でambiguous判定できるよう全件返す。"""
    duplicate_filename = "CAB-csl_script_event_duplicate-episode1.dec"
    episode_a = StoryManifestEpisode(
        episode_id="EVT_A_E01",
        episode_number=1,
        subtitle=None,
        display_title=None,
        raw_path=f"EVENT/a_export/{duplicate_filename}",
        source_file_name=duplicate_filename,
        metadata_status="pending",
    )
    episode_b = StoryManifestEpisode(
        episode_id="EVT_B_E01",
        episode_number=1,
        subtitle=None,
        display_title=None,
        raw_path=f"EVENT/b_export/{duplicate_filename}",
        source_file_name=duplicate_filename,
        metadata_status="pending",
    )
    story_a = StoryManifestStory(
        story_id="EVT_A",
        category="event",
        source_key="a",
        title=None,
        display_title=None,
        metadata_status="pending",
        raw_directory="EVENT/a_export",
        episodes=[episode_a],
    )
    story_b = StoryManifestStory(
        story_id="EVT_B",
        category="event",
        source_key="b",
        title=None,
        display_title=None,
        metadata_status="pending",
        raw_directory="EVENT/b_export",
        episodes=[episode_b],
    )
    manifest = StoryManifest(schema_version="0.1.0", stories=[story_a, story_b])

    matches = find_episode_by_source_filename(manifest, duplicate_filename)

    assert len(matches) == 2


# ----------------------------------------------------------------
# resolve_manifest_episode (優先順位の統合テスト)
# ----------------------------------------------------------------


def test_resolve_manifest_episode_matched_by_raw_path(tmp_path):
    manifest_path = tmp_path / "story_manifest.yaml"
    _write_manifest(manifest_path, _synthetic_manifest_dict())
    manifest = load_story_manifest(manifest_path)

    raw_root = tmp_path / "raw_root"
    export_dir = raw_root / RAW_DIR
    export_dir.mkdir(parents=True)
    input_path = export_dir / EPISODE_1_FILENAME
    input_path.write_text("", encoding="utf-8")

    result = resolve_manifest_episode(manifest, input_path, raw_root=raw_root)

    assert result.status == "matched"
    assert result.matched_by == "raw_path"
    assert result.story.story_id == STORY_ID


def test_resolve_manifest_episode_falls_back_to_source_filename(tmp_path):
    """rawPathで一致しない場所に置かれたファイルでも、sourceFileNameで
    一致すればmatchedとして解決する (優先順位3)。"""
    manifest_path = tmp_path / "story_manifest.yaml"
    _write_manifest(manifest_path, _synthetic_manifest_dict())
    manifest = load_story_manifest(manifest_path)

    unrelated_dir = tmp_path / "somewhere_else"
    unrelated_dir.mkdir()
    input_path = unrelated_dir / EPISODE_1_FILENAME
    input_path.write_text("", encoding="utf-8")

    result = resolve_manifest_episode(manifest, input_path, raw_root=None)

    assert result.status == "matched"
    assert result.matched_by == "source_file_name"


def test_resolve_manifest_episode_ambiguous_when_filename_matches_multiple(tmp_path):
    duplicate_filename = "CAB-csl_script_event_duplicate-episode1.dec"
    manifest_dict = {
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
    _write_manifest(manifest_path, manifest_dict)
    manifest = load_story_manifest(manifest_path)

    unrelated_dir = tmp_path / "somewhere_else"
    unrelated_dir.mkdir()
    input_path = unrelated_dir / duplicate_filename
    input_path.write_text("", encoding="utf-8")

    result = resolve_manifest_episode(manifest, input_path, raw_root=None)

    assert result.status == "ambiguous"
    assert result.story is None
    assert result.episode is None


def test_resolve_manifest_episode_unmatched_for_empty_manifest():
    manifest = StoryManifest(schema_version="0.1.0", stories=[])
    result = resolve_manifest_episode(manifest, Path("/some/file.dec"), raw_root=None)
    assert result.status == "unmatched"
