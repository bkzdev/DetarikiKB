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

from agents.parser.character_dictionary import (
    STATUS_CONFIRMED,
    STATUS_NAME_ONLY,
    CharacterDictionaryEntry,
)
from agents.parser.story_manifest_candidates import (
    build_candidate_document,
    build_character_story_manifest_candidates,
    build_story_manifest_candidate,
    build_story_manifest_candidates,
    classify_auxiliary_suffix,
    find_character_category_directory,
    find_character_date_category_directory,
    normalize_path_separators,
    parse_episode_filename,
    parse_export_directory_name,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "story_manifest.schema.json"
SOURCE_KEY = "250626_synthetic_dancer"

CHARACTER_SOURCE_ID = "42"
CHARACTER_ID = "CHAR_SYNTH_TEST"
UNCONFIRMED_SOURCE_ID = "43"


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


# ----------------------------------------------------------------
# CHARACTER / CHARACTER_DATE
# (Character_Story_ID_Manifest_Design.md §4・§8・§9 PR C)
# ----------------------------------------------------------------


def _confirmed_entry(
    source_id: str = CHARACTER_SOURCE_ID, character_id: str = CHARACTER_ID
) -> CharacterDictionaryEntry:
    return CharacterDictionaryEntry(
        source_character_id=source_id,
        display_name="Synthetic Character",
        character_id=character_id,
        status=STATUS_CONFIRMED,
    )


def _name_only_entry(
    source_id: str = UNCONFIRMED_SOURCE_ID,
) -> CharacterDictionaryEntry:
    return CharacterDictionaryEntry(
        source_character_id=source_id,
        display_name="Synthetic Pending Character",
        character_id=None,
        status=STATUS_NAME_ONLY,
    )


def _make_character_export_dir(
    raw_root: Path, source_id: str = CHARACTER_SOURCE_ID
) -> Path:
    export_dir = (
        raw_root / "CHARACTER" / f"csl_script_charastory_character{source_id}_export"
    )
    export_dir.mkdir(parents=True)
    return export_dir


def _make_character_date_export_dir(
    raw_root: Path, source_id: str = CHARACTER_SOURCE_ID
) -> Path:
    export_dir = (
        raw_root / "CHARACTER_DATE" / f"csl_script_surprise_character{source_id}_export"
    )
    export_dir.mkdir(parents=True)
    return export_dir


def _make_character_file(export_dir: Path, source_id: str, suffix: str) -> Path:
    path = export_dir / f"CAB-csl_script_charastory_character{source_id}-{suffix}.dec"
    path.write_text("", encoding="utf-8")
    return path


def _make_character_date_file(export_dir: Path, source_id: str, suffix: str) -> Path:
    path = export_dir / f"CAB-csl_script_surprise_character{source_id}-{suffix}.dec"
    path.write_text("", encoding="utf-8")
    return path


def test_find_character_category_directory_case_insensitive(tmp_path):
    (tmp_path / "Character").mkdir()
    assert find_character_category_directory(tmp_path) is not None


def test_find_character_date_category_directory_case_insensitive(tmp_path):
    (tmp_path / "Character_Date").mkdir()
    assert find_character_date_category_directory(tmp_path) is not None


def test_find_character_category_directory_returns_none_when_absent(tmp_path):
    assert find_character_category_directory(tmp_path) is None


def test_classify_auxiliary_suffix_variant_patterns():
    for suffix in (
        "H_scene6_n",
        "H_scene6_spine",
        "H_scene6_VR",
        "H_scene6 #2",
        "H_scene6_n #2",
        "H_scene6_spine #2",
    ):
        assert classify_auxiliary_suffix(suffix) == "variant", suffix


def test_classify_auxiliary_suffix_direction_patterns():
    for suffix in (
        "camera6",
        "camera6 #2",
        "camera",
        "camera #2",
        "finish #2",
        "finish",
        "episode_bgm6",
        "sv_1",
        "docking6",
        "cameradocking6",
        "episode_osawari6_start",
        "episode_osawari6_end",
        "camerabreast6",
        "breast6",
        "cameracrotch6",
        "crotch6",
        "episode_ASMR6",
        "VR_1",
        "talk",
        "start",
        "position",
    ):
        assert classify_auxiliary_suffix(suffix) == "direction", suffix


def test_classify_auxiliary_suffix_defaults_to_other():
    for suffix in (
        "H_scene6_img",
        "H_scene_test",
        "H_scene_s_tutorial",
        "episode6_n",
        "episode_osawari6_start_n",
        "PinkMan",
        "idolVR",
        "totally_unrecognized_suffix",
    ):
        assert classify_auxiliary_suffix(suffix) == "other", suffix


def test_build_character_story_manifest_candidates_generates_main_extra_hs(tmp_path):
    export_dir = _make_character_export_dir(tmp_path)
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "episode1")
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "episode_EX1")
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "H_scene6")

    candidates, report = build_character_story_manifest_candidates(
        tmp_path, [_confirmed_entry()]
    )

    story_ids = {story["storyId"] for story in candidates}
    assert story_ids == {
        "CHAR_MAIN_SYNTH_TEST",
        "CHAR_EXTRA_SYNTH_TEST",
        "CHAR_HS_SYNTH_TEST",
    }
    assert report == []
    for story in candidates:
        assert story["characterId"] == CHARACTER_ID
        assert story["category"] == "character"
        assert story["sourceKey"] == CHARACTER_SOURCE_ID


def test_build_character_story_manifest_candidates_generates_date_story(tmp_path):
    export_dir = _make_character_date_export_dir(tmp_path)
    _make_character_date_file(export_dir, CHARACTER_SOURCE_ID, "Surprise_1")
    _make_character_date_file(export_dir, CHARACTER_SOURCE_ID, "Surprise_2")

    candidates, report = build_character_story_manifest_candidates(
        tmp_path, [_confirmed_entry()]
    )

    assert len(candidates) == 1
    story = candidates[0]
    assert story["storyId"] == "CHAR_DATE_SYNTH_TEST"
    episode_numbers = [e["episodeNumber"] for e in story["episodes"]]
    assert episode_numbers == [1, 2]
    assert report == []


def test_only_stories_with_matching_files_are_generated(tmp_path):
    """該当ファイルが存在する種別のみstoryを生成する
    (Character_Story_ID_Manifest_Design.md §4.1)。"""
    export_dir = _make_character_export_dir(tmp_path)
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "episode1")

    candidates, _ = build_character_story_manifest_candidates(
        tmp_path, [_confirmed_entry()]
    )

    assert len(candidates) == 1
    assert candidates[0]["storyId"] == "CHAR_MAIN_SYNTH_TEST"


def test_h_scene_s_generates_es01_episode_id(tmp_path):
    export_dir = _make_character_export_dir(tmp_path)
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "H_scene1")
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "H_scene_s")

    candidates, report = build_character_story_manifest_candidates(
        tmp_path, [_confirmed_entry()]
    )

    assert len(candidates) == 1
    episode_ids = [e["episodeId"] for e in candidates[0]["episodes"]]
    assert episode_ids == ["CHAR_HS_SYNTH_TEST_E01", "CHAR_HS_SYNTH_TEST_ES01"]
    assert report == []


def test_unconfirmed_character_generates_pending_report_and_no_candidate(tmp_path):
    export_dir = _make_character_export_dir(tmp_path, UNCONFIRMED_SOURCE_ID)
    _make_character_file(export_dir, UNCONFIRMED_SOURCE_ID, "episode1")

    candidates, report = build_character_story_manifest_candidates(
        tmp_path, [_name_only_entry()]
    )

    assert candidates == []
    assert len(report) == 1
    assert report[0]["issueType"] == "unconfirmed_character"
    assert report[0]["sourceCharacterId"] == UNCONFIRMED_SOURCE_ID


def test_character_not_in_dictionary_at_all_is_pending(tmp_path):
    export_dir = _make_character_export_dir(tmp_path, UNCONFIRMED_SOURCE_ID)
    _make_character_file(export_dir, UNCONFIRMED_SOURCE_ID, "episode1")

    candidates, report = build_character_story_manifest_candidates(tmp_path, [])

    assert candidates == []
    assert len(report) == 1
    assert report[0]["issueType"] == "unconfirmed_character"


def test_auxiliary_files_are_classified_and_attached_to_hs_story(tmp_path):
    export_dir = _make_character_export_dir(tmp_path)
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "H_scene6")
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "H_scene6_n")
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "camera6")
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "H_scene6_img")

    candidates, report = build_character_story_manifest_candidates(
        tmp_path, [_confirmed_entry()]
    )

    assert len(candidates) == 1
    story = candidates[0]
    assert story["storyId"] == "CHAR_HS_SYNTH_TEST"
    roles_by_filename = {
        aux["sourceFileName"]: aux["fileRole"] for aux in story["auxiliaryFiles"]
    }
    prefix = f"CAB-csl_script_charastory_character{CHARACTER_SOURCE_ID}"
    assert roles_by_filename == {
        f"{prefix}-H_scene6_n.dec": "variant",
        f"{prefix}-camera6.dec": "direction",
        f"{prefix}-H_scene6_img.dec": "other",
    }
    assert report == []


def test_direction_file_falls_back_to_main_story_when_hs_story_absent(tmp_path):
    export_dir = _make_character_export_dir(tmp_path)
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "episode1")
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "camera1")

    candidates, report = build_character_story_manifest_candidates(
        tmp_path, [_confirmed_entry()]
    )

    assert len(candidates) == 1
    story = candidates[0]
    assert story["storyId"] == "CHAR_MAIN_SYNTH_TEST"
    assert len(story["auxiliaryFiles"]) == 1
    assert story["auxiliaryFiles"][0]["fileRole"] == "direction"
    assert report == []


def test_variant_file_without_hs_story_is_reported_as_unattached(tmp_path):
    """H_scene変種のみが存在しH_sceneN本体・H_scene_sが無い場合、
    紐づけ先のCHAR_HS storyが無いためpending報告として残す
    (黙って除外しない、Character_Story_ID_Manifest_Design.md §8.1)。"""
    export_dir = _make_character_export_dir(tmp_path)
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "H_scene6_n")

    candidates, report = build_character_story_manifest_candidates(
        tmp_path, [_confirmed_entry()]
    )

    assert candidates == []
    assert len(report) == 1
    assert report[0]["issueType"] == "unattached_auxiliary_file"
    assert report[0]["fileRole"] == "variant"


def test_direction_file_without_any_story_is_reported_as_unattached(tmp_path):
    export_dir = _make_character_export_dir(tmp_path)
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "camera1")

    candidates, report = build_character_story_manifest_candidates(
        tmp_path, [_confirmed_entry()]
    )

    assert candidates == []
    assert len(report) == 1
    assert report[0]["issueType"] == "unattached_auxiliary_file"
    assert report[0]["fileRole"] == "direction"


def test_id_mismatch_file_is_reported_and_excluded(tmp_path):
    """ディレクトリ名の{N}とファイル名の{N}が食い違う場合、認識できない
    ファイルとして報告し、episode/auxiliaryFilesいずれにも含めない
    (Character_Story_ID_Manifest_Design.md §4.5)。"""
    export_dir = _make_character_export_dir(tmp_path)
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "episode1")
    # ディレクトリはCHARACTER_SOURCE_IDだが、ファイル名は別ID。
    mismatched = export_dir / (
        f"CAB-csl_script_charastory_character{UNCONFIRMED_SOURCE_ID}-episode1.dec"
    )
    mismatched.write_text("", encoding="utf-8")

    candidates, report = build_character_story_manifest_candidates(
        tmp_path, [_confirmed_entry()]
    )

    assert len(candidates) == 1
    assert len(candidates[0]["episodes"]) == 1
    id_mismatch_issues = [r for r in report if r["issueType"] == "id_mismatch"]
    assert len(id_mismatch_issues) == 1
    assert id_mismatch_issues[0]["sourceCharacterId"] == CHARACTER_SOURCE_ID


def test_id_mismatch_between_character_date_dir_and_filename_is_reported(tmp_path):
    export_dir = _make_character_date_export_dir(tmp_path)
    _make_character_date_file(export_dir, CHARACTER_SOURCE_ID, "Surprise_1")
    mismatched = export_dir / (
        f"CAB-csl_script_surprise_character{UNCONFIRMED_SOURCE_ID}-Surprise_2.dec"
    )
    mismatched.write_text("", encoding="utf-8")

    candidates, report = build_character_story_manifest_candidates(
        tmp_path, [_confirmed_entry()]
    )

    assert len(candidates) == 1
    assert len(candidates[0]["episodes"]) == 1
    id_mismatch_issues = [r for r in report if r["issueType"] == "id_mismatch"]
    assert len(id_mismatch_issues) == 1


def test_build_character_story_manifest_candidates_empty_when_no_directories(tmp_path):
    candidates, report = build_character_story_manifest_candidates(tmp_path, [])
    assert candidates == []
    assert report == []


def test_event_candidates_unaffected_by_character_candidates(tmp_path):
    """EVENT既存挙動の無回帰: 同じraw_root配下にCHARACTERディレクトリが
    あってもEVENT側候補生成は影響を受けない。"""
    event_export_dir = tmp_path / "EVENT" / f"csl_script_event_{SOURCE_KEY}_export"
    event_export_dir.mkdir(parents=True)
    (event_export_dir / f"CAB-csl_script_event_{SOURCE_KEY}-episode1.dec").write_text(
        "", encoding="utf-8"
    )

    character_export_dir = _make_character_export_dir(tmp_path)
    _make_character_file(character_export_dir, CHARACTER_SOURCE_ID, "episode1")

    event_candidates = build_story_manifest_candidates(tmp_path)
    character_candidates, report = build_character_story_manifest_candidates(
        tmp_path, [_confirmed_entry()]
    )

    assert len(event_candidates) == 1
    assert event_candidates[0]["storyId"] == "EVT_250626_SYNTHETIC_DANCER"
    assert len(character_candidates) == 1
    assert character_candidates[0]["storyId"] == "CHAR_MAIN_SYNTH_TEST"
    assert report == []


def test_character_candidate_document_validates_against_schema(tmp_path):
    export_dir = _make_character_export_dir(tmp_path)
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "episode1")
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "episode_EX1")
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "H_scene1")
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "H_scene_s")
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "H_scene1_n")
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "camera1")
    _make_character_file(export_dir, CHARACTER_SOURCE_ID, "H_scene1_img")
    date_dir = _make_character_date_export_dir(tmp_path)
    _make_character_date_file(date_dir, CHARACTER_SOURCE_ID, "Surprise_1")

    candidates, _ = build_character_story_manifest_candidates(
        tmp_path, [_confirmed_entry()]
    )
    document = build_candidate_document(candidates)

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    errors = list(Draft7Validator(schema).iter_errors(document))
    assert errors == []
