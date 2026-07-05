"""
tests/parser/test_story_title_subtitle_candidates.py
agents/parser/story_title_subtitle_candidates.py のユニットテスト。

すべて合成データ (テスト内で組み立てるCSV行・StoryManifest) のみを使う。
実イベント名・実タイトル・実データ由来fixtureは一切使わない
(docs/architecture/05_Parser/Story_Manifest_Design.md §11.7参照)。
"""

from __future__ import annotations

import csv
from pathlib import Path

from agents.parser.story_manifest import (
    StoryManifest,
    StoryManifestEpisode,
    StoryManifestStory,
)
from agents.parser.story_title_subtitle_candidates import (
    build_candidate_document,
    build_candidates_from_rows,
    read_candidate_rows_from_csv,
)

CSV_FIELDS = [
    "storyId",
    "episodeId",
    "episodeNumber",
    "proposedTitle",
    "proposedDisplayTitle",
    "proposedSubtitle",
    "confidence",
    "notes",
]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _row(**overrides) -> dict[str, str]:
    row = dict.fromkeys(CSV_FIELDS, "")
    row.update(overrides)
    return row


def _synthetic_manifest() -> StoryManifest:
    episode = StoryManifestEpisode(
        episode_id="EVT_990101_SAMPLE_EVENT_E01",
        episode_number=1,
        subtitle=None,
        display_title=None,
        raw_path="EVENT/x_export/CAB-x-episode1.dec",
        source_file_name="CAB-x-episode1.dec",
        metadata_status="pending",
    )
    story = StoryManifestStory(
        story_id="EVT_990101_SAMPLE_EVENT",
        category="event",
        source_key="990101_sample_event",
        title=None,
        display_title=None,
        metadata_status="pending",
        raw_directory="EVENT/x_export",
        episodes=[episode],
    )
    return StoryManifest(schema_version="0.1.0", stories=[story])


# ----------------------------------------------------------------
# read_candidate_rows_from_csv
# ----------------------------------------------------------------


def test_read_candidate_rows_from_csv(tmp_path):
    csv_path = tmp_path / "rows.csv"
    _write_csv(
        csv_path,
        [
            _row(
                storyId="EVT_990101_SAMPLE_EVENT",
                episodeId="EVT_990101_SAMPLE_EVENT_E01",
                episodeNumber="1",
                proposedSubtitle="Synthetic Episode Subtitle",
            )
        ],
    )

    rows = read_candidate_rows_from_csv(csv_path)

    assert len(rows) == 1
    assert rows[0]["storyId"] == "EVT_990101_SAMPLE_EVENT"
    assert rows[0]["proposedSubtitle"] == "Synthetic Episode Subtitle"


# ----------------------------------------------------------------
# build_candidates_from_rows
# ----------------------------------------------------------------


def test_build_candidates_groups_episodes_under_story():
    rows = [
        _row(
            storyId="EVT_990101_SAMPLE_EVENT",
            episodeId="EVT_990101_SAMPLE_EVENT_E01",
            episodeNumber="1",
            proposedTitle="Synthetic Sample Event",
            proposedSubtitle="Synthetic Episode 1 Subtitle",
        ),
        _row(
            storyId="EVT_990101_SAMPLE_EVENT",
            episodeId="EVT_990101_SAMPLE_EVENT_E02",
            episodeNumber="2",
            proposedSubtitle="Synthetic Episode 2 Subtitle",
        ),
    ]

    candidates = build_candidates_from_rows(rows)

    assert len(candidates) == 1
    story = candidates[0]
    assert story["storyId"] == "EVT_990101_SAMPLE_EVENT"
    assert story["proposedTitle"] == "Synthetic Sample Event"
    assert len(story["episodes"]) == 2
    assert story["episodes"][0]["proposedSubtitle"] == "Synthetic Episode 1 Subtitle"
    assert story["episodes"][1]["proposedSubtitle"] == "Synthetic Episode 2 Subtitle"


def test_build_candidates_all_have_pending_review_status():
    """すべてのcandidateがreviewStatus: pendingで生成されることを確認する
    (自動でconfirmedにしない方針、Story_Manifest_Design.md §11.7)。"""
    rows = [
        _row(
            storyId="EVT_990101_SAMPLE_EVENT",
            episodeId="EVT_990101_SAMPLE_EVENT_E01",
            episodeNumber="1",
        )
    ]

    candidates = build_candidates_from_rows(rows)

    assert candidates[0]["episodes"][0]["reviewStatus"] == "pending"


def test_build_candidates_defaults_confidence_to_source_exact():
    rows = [
        _row(
            storyId="EVT_990101_SAMPLE_EVENT",
            episodeId="EVT_990101_SAMPLE_EVENT_E01",
            episodeNumber="1",
        )
    ]

    candidates = build_candidates_from_rows(rows)

    assert candidates[0]["episodes"][0]["confidence"] == "source_exact"


def test_build_candidates_story_level_row_without_episode_id():
    """episodeIdが空のstory単位行でも、story candidateとしては生成される
    (episodesは空リスト)。"""
    rows = [_row(storyId="EVT_990101_SAMPLE_EVENT", proposedTitle="Synthetic Title")]

    candidates = build_candidates_from_rows(rows)

    assert len(candidates) == 1
    assert candidates[0]["proposedTitle"] == "Synthetic Title"
    assert candidates[0]["episodes"] == []


def test_build_candidates_marks_found_in_manifest_true_when_matched():
    rows = [
        _row(
            storyId="EVT_990101_SAMPLE_EVENT",
            episodeId="EVT_990101_SAMPLE_EVENT_E01",
            episodeNumber="1",
        )
    ]
    manifest = _synthetic_manifest()

    candidates = build_candidates_from_rows(rows, manifest)

    assert candidates[0]["foundInManifest"] is True
    assert candidates[0]["episodes"][0]["foundInManifest"] is True


def test_build_candidates_unmatched_story_still_emitted_as_pending():
    """manifestに存在しないstoryId/episodeIdでも、candidateとしては
    必ず出力される (黙って除外しない、Story_Manifest_Design.md §11.7)。"""
    rows = [
        _row(
            storyId="EVT_UNMATCHED_STORY",
            episodeId="EVT_UNMATCHED_STORY_E01",
            episodeNumber="1",
        )
    ]
    manifest = _synthetic_manifest()

    candidates = build_candidates_from_rows(rows, manifest)

    assert len(candidates) == 1
    assert candidates[0]["foundInManifest"] is False
    assert candidates[0]["episodes"][0]["foundInManifest"] is False
    assert candidates[0]["episodes"][0]["reviewStatus"] == "pending"


def test_build_candidates_without_manifest_found_in_manifest_is_false():
    rows = [
        _row(
            storyId="EVT_990101_SAMPLE_EVENT",
            episodeId="EVT_990101_SAMPLE_EVENT_E01",
            episodeNumber="1",
        )
    ]

    candidates = build_candidates_from_rows(rows, manifest=None)

    assert candidates[0]["foundInManifest"] is False


def test_build_candidates_ignores_rows_without_story_id():
    rows = [_row(storyId="", episodeId="EVT_X_E01")]

    candidates = build_candidates_from_rows(rows)

    assert candidates == []


def test_build_candidates_does_not_infer_subtitle_when_blank():
    """proposedSubtitleが空のCSV行は、candidate内でもNoneのままである
    ことを確認する (推測で埋めない)。"""
    rows = [
        _row(
            storyId="EVT_990101_SAMPLE_EVENT",
            episodeId="EVT_990101_SAMPLE_EVENT_E01",
            episodeNumber="1",
            proposedSubtitle="",
        )
    ]

    candidates = build_candidates_from_rows(rows)

    assert candidates[0]["episodes"][0]["proposedSubtitle"] is None


# ----------------------------------------------------------------
# build_candidate_document
# ----------------------------------------------------------------


def test_build_candidate_document_has_expected_shape():
    document = build_candidate_document(
        candidates=[],
        source_type="wiki_story_list",
        source_label="Synthetic wiki list",
    )

    assert document["schemaVersion"] == "0.1.0"
    assert document["documentType"] == "story_title_subtitle_candidates"
    assert document["source"]["sourceType"] == "wiki_story_list"
    assert document["source"]["label"] == "Synthetic wiki list"
    assert document["source"]["fetchedAt"] is None
    assert document["candidates"] == []
