"""
tests/parser/test_story_manifest_candidates.py
agents/parser/story_manifest_candidates.py のユニットテスト。

すべて合成データのみ (tmp_path配下に空の.decファイルを作成) を使う。
実DECファイル・実イベント名・実データ由来fixtureは一切使わない
(docs/architecture/05_Parser/Story_Manifest_Design.md 参照)。
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

from agents.parser.story_manifest_candidates import (
    build_candidate_document,
    build_story_manifest_candidate,
    build_story_manifest_candidates,
    normalize_path_separators,
    parse_episode_filename,
    parse_export_directory_name,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "story_manifest.schema.json"
SOURCE_KEY = "250626_synthetic_dancer"


def _make_export_dir(raw_root, source_key: str = SOURCE_KEY):
    export_dir = raw_root / "EVENT" / f"csl_script_event_{source_key}_export"
    export_dir.mkdir(parents=True)
    return export_dir


def _make_episode_file(export_dir, source_key: str, episode_number: int):
    path = export_dir / f"CAB-csl_script_event_{source_key}-episode{episode_number}.dec"
    path.write_text("", encoding="utf-8")
    return path


# ----------------------------------------------------------------
# parse_export_directory_name / parse_episode_filename
# ----------------------------------------------------------------


def test_parse_export_directory_name_extracts_source_key():
    assert (
        parse_export_directory_name("csl_script_event_250626_synthetic_dancer_export")
        == "250626_synthetic_dancer"
    )


def test_parse_export_directory_name_returns_none_for_non_matching():
    assert parse_export_directory_name("some_other_directory") is None


def test_parse_episode_filename_extracts_episode_number():
    assert (
        parse_episode_filename(
            "CAB-csl_script_event_250626_synthetic_dancer-episode1.dec",
            "250626_synthetic_dancer",
        )
        == 1
    )


def test_parse_episode_filename_returns_none_for_mismatched_source_key():
    """ディレクトリ名から抽出したsourceKeyとファイル名のsourceKeyが
    食い違う場合は、認識できないファイルとして候補生成対象外にする。"""
    assert (
        parse_episode_filename(
            "CAB-csl_script_event_other_key-episode1.dec",
            "250626_synthetic_dancer",
        )
        is None
    )


def test_parse_episode_filename_returns_none_for_non_dec_file():
    assert parse_episode_filename("README.txt", "250626_synthetic_dancer") is None


def test_normalize_path_separators_converts_backslashes():
    assert (
        normalize_path_separators(
            "EVENT\\csl_script_event_250626_synthetic_dancer_export\\CAB-x.dec"
        )
        == "EVENT/csl_script_event_250626_synthetic_dancer_export/CAB-x.dec"
    )


# ----------------------------------------------------------------
# build_story_manifest_candidate / build_story_manifest_candidates
# ----------------------------------------------------------------


def test_build_story_manifest_candidate_sorts_episodes_numerically(tmp_path):
    """episode1/episode2/episode10が数値としてソートされる
    (文字列ソートでは1, 10, 2の誤った順序になる)。"""
    export_dir = _make_export_dir(tmp_path)
    for n in (2, 10, 1):
        _make_episode_file(export_dir, SOURCE_KEY, n)

    candidate = build_story_manifest_candidate(export_dir, tmp_path)

    assert candidate is not None
    episode_numbers = [e["episodeNumber"] for e in candidate["episodes"]]
    assert episode_numbers == [1, 2, 10]


def test_build_story_manifest_candidate_generates_story_and_episode_ids(tmp_path):
    export_dir = _make_export_dir(tmp_path)
    _make_episode_file(export_dir, SOURCE_KEY, 1)

    candidate = build_story_manifest_candidate(export_dir, tmp_path)

    assert candidate["storyId"] == "EVT_250626_SYNTHETIC_DANCER"
    assert candidate["category"] == "event"
    assert candidate["sourceKey"] == SOURCE_KEY
    assert candidate["episodes"][0]["episodeId"] == "EVT_250626_SYNTHETIC_DANCER_E01"


def test_build_story_manifest_candidate_ignores_non_matching_files(tmp_path):
    export_dir = _make_export_dir(tmp_path)
    _make_episode_file(export_dir, SOURCE_KEY, 1)
    (export_dir / "README.txt").write_text("not an episode file", encoding="utf-8")
    (export_dir / "CAB-csl_script_event_other_key-episode1.dec").write_text(
        "", encoding="utf-8"
    )

    candidate = build_story_manifest_candidate(export_dir, tmp_path)

    assert len(candidate["episodes"]) == 1


def test_build_story_manifest_candidate_returns_none_for_empty_export_dir(tmp_path):
    export_dir = _make_export_dir(tmp_path)
    (export_dir / "README.txt").write_text("", encoding="utf-8")

    assert build_story_manifest_candidate(export_dir, tmp_path) is None


def test_build_story_manifest_candidate_returns_none_for_non_matching_dir_name(
    tmp_path,
):
    non_matching_dir = tmp_path / "EVENT" / "some_other_directory"
    non_matching_dir.mkdir(parents=True)
    (non_matching_dir / "file.dec").write_text("", encoding="utf-8")

    assert build_story_manifest_candidate(non_matching_dir, tmp_path) is None


def test_build_story_manifest_candidate_title_and_subtitle_are_null(tmp_path):
    """DEC本文からタイトル・サブタイトルを推測しない方針
    (Story_Manifest_Design.md §11) を確認する。"""
    export_dir = _make_export_dir(tmp_path)
    _make_episode_file(export_dir, SOURCE_KEY, 1)

    candidate = build_story_manifest_candidate(export_dir, tmp_path)

    assert candidate["title"] is None
    assert candidate["displayTitle"] is None
    assert candidate["episodes"][0]["subtitle"] is None
    assert candidate["episodes"][0]["displayTitle"] is None


def test_build_story_manifest_candidate_metadata_status_is_pending(tmp_path):
    export_dir = _make_export_dir(tmp_path)
    _make_episode_file(export_dir, SOURCE_KEY, 1)

    candidate = build_story_manifest_candidate(export_dir, tmp_path)

    assert candidate["metadataStatus"] == "pending"
    assert candidate["episodes"][0]["metadataStatus"] == "pending"


def test_build_story_manifest_candidate_raw_paths_use_forward_slashes(tmp_path):
    export_dir = _make_export_dir(tmp_path)
    _make_episode_file(export_dir, SOURCE_KEY, 1)

    candidate = build_story_manifest_candidate(export_dir, tmp_path)

    assert "\\" not in candidate["rawDirectory"]
    assert "\\" not in candidate["episodes"][0]["rawPath"]
    assert candidate["rawDirectory"] == f"EVENT/csl_script_event_{SOURCE_KEY}_export"
    assert candidate["episodes"][0]["rawPath"] == (
        f"EVENT/csl_script_event_{SOURCE_KEY}_export/"
        f"CAB-csl_script_event_{SOURCE_KEY}-episode1.dec"
    )


def test_build_story_manifest_candidate_does_not_read_dec_file_contents(tmp_path):
    """DECファイルの中身は一切読まないことを確認する
    (実DEC本文らしき内容を書き込んでも出力に含まれない)。"""
    export_dir = _make_export_dir(tmp_path)
    path = _make_episode_file(export_dir, SOURCE_KEY, 1)
    path.write_text("@ChTalk 1\nこれは本文のダミーです\n", encoding="utf-8")

    candidate = build_story_manifest_candidate(export_dir, tmp_path)

    serialized = json.dumps(candidate, ensure_ascii=False)
    assert "ChTalk" not in serialized
    assert "本文のダミー" not in serialized


def test_build_story_manifest_candidates_ignores_non_event_categories(tmp_path):
    """MAINカテゴリ等、EVENT以外のディレクトリは対象外にする
    (Story_Manifest_Design.md §6、EVENTカテゴリのみ対応)。"""
    export_dir = _make_export_dir(tmp_path)
    _make_episode_file(export_dir, SOURCE_KEY, 1)

    main_dir = tmp_path / "MAIN"
    main_dir.mkdir()
    (main_dir / "MAIN_S01_C02_E01.dec").write_text("", encoding="utf-8")

    candidates = build_story_manifest_candidates(tmp_path)

    assert len(candidates) == 1
    assert candidates[0]["storyId"] == "EVT_250626_SYNTHETIC_DANCER"


def test_build_story_manifest_candidates_multiple_stories_sorted_by_story_id(
    tmp_path,
):
    export_dir_a = _make_export_dir(tmp_path, "990101_second_event")
    _make_episode_file(export_dir_a, "990101_second_event", 1)
    export_dir_b = _make_export_dir(tmp_path, "250626_synthetic_dancer")
    _make_episode_file(export_dir_b, "250626_synthetic_dancer", 1)

    candidates = build_story_manifest_candidates(tmp_path)

    story_ids = [c["storyId"] for c in candidates]
    assert story_ids == sorted(story_ids)


def test_build_story_manifest_candidates_empty_when_no_event_directory(tmp_path):
    (tmp_path / "MAIN").mkdir()
    assert build_story_manifest_candidates(tmp_path) == []


def test_build_story_manifest_candidates_finds_event_directory_case_insensitively(
    tmp_path,
):
    export_dir = tmp_path / "Event" / f"csl_script_event_{SOURCE_KEY}_export"
    export_dir.mkdir(parents=True)
    _make_episode_file(export_dir, SOURCE_KEY, 1)

    candidates = build_story_manifest_candidates(tmp_path)

    assert len(candidates) == 1


# ----------------------------------------------------------------
# schema検証
# ----------------------------------------------------------------


def test_candidate_document_validates_against_schema(tmp_path):
    export_dir = _make_export_dir(tmp_path)
    for n in (1, 2):
        _make_episode_file(export_dir, SOURCE_KEY, n)

    candidates = build_story_manifest_candidates(tmp_path)
    document = build_candidate_document(candidates)

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    errors = list(Draft7Validator(schema).iter_errors(document))
    assert errors == []


def test_empty_candidate_document_validates_against_schema():
    document = build_candidate_document([])
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    errors = list(Draft7Validator(schema).iter_errors(document))
    assert errors == []
