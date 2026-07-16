"""
tests/parser/test_story_manifest_schema.py
schemas/story_manifest.schema.json の軽量な整合性テスト。

合成データ (docs/templates/story_manifest_template.yaml、およびテスト内で
組み立てる合成dict) のみを使う。実イベント名・実データ由来fixtureは
一切使わない (docs/architecture/05_Parser/Story_Manifest_Design.md 参照)。
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "story_manifest.schema.json"
TEMPLATE_PATH = PROJECT_ROOT / "docs" / "templates" / "story_manifest_template.yaml"

_REAL_STORY_NAMES = ("レイン", "赤城陽菜")


def _load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _validate(document: dict) -> list[str]:
    errors = sorted(
        Draft7Validator(_load_schema()).iter_errors(document),
        key=lambda e: list(e.path),
    )
    return [f"{list(e.path)}: {e.message}" for e in errors]


def _synthetic_story(**overrides) -> dict:
    story = {
        "storyId": "EVT_990101_SAMPLE_EVENT",
        "category": "event",
        "sourceKey": "990101_sample_event",
        "title": None,
        "displayTitle": None,
        "metadataStatus": "pending",
        "rawDirectory": "EVENT/csl_script_event_990101_sample_event_export",
        "notes": None,
        "episodes": [
            {
                "episodeId": "EVT_990101_SAMPLE_EVENT_E01",
                "episodeNumber": 1,
                "subtitle": None,
                "displayTitle": None,
                "rawPath": (
                    "EVENT/csl_script_event_990101_sample_event_export/"
                    "CAB-csl_script_event_990101_sample_event-episode1.dec"
                ),
                "sourceFileName": (
                    "CAB-csl_script_event_990101_sample_event-episode1.dec"
                ),
                "metadataStatus": "pending",
                "notes": None,
            }
        ],
    }
    story.update(overrides)
    return story


def _document(*stories: dict) -> dict:
    return {
        "schemaVersion": "0.1.0",
        "documentType": "story_manifest",
        "stories": list(stories),
    }


# ----------------------------------------------------------------
# schemaファイル自体
# ----------------------------------------------------------------


def test_schema_file_exists():
    assert SCHEMA_PATH.is_file()


def test_schema_is_valid_json():
    _load_schema()


# ----------------------------------------------------------------
# template
# ----------------------------------------------------------------


def test_template_exists():
    assert TEMPLATE_PATH.is_file()


def test_template_validates_against_schema():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert _validate(document) == []


def test_template_does_not_contain_real_story_names():
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    for name in _REAL_STORY_NAMES:
        assert name not in content


def test_template_title_and_subtitle_are_null():
    """DECから自動推測しない方針 (Story_Manifest_Design.md §11) の通り、
    templateのtitle/subtitleがすべてnullであることを確認する。"""
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    for story in document["stories"]:
        assert story["title"] is None
        assert story["displayTitle"] is None
        for episode in story["episodes"]:
            assert episode["subtitle"] is None
            assert episode["displayTitle"] is None


def test_template_metadata_status_is_pending():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    for story in document["stories"]:
        assert story["metadataStatus"] == "pending"
        for episode in story["episodes"]:
            assert episode["metadataStatus"] == "pending"


# ----------------------------------------------------------------
# 合成データでのschema検証
# ----------------------------------------------------------------


def test_empty_stories_list_is_valid():
    assert _validate(_document()) == []


def test_synthetic_story_with_all_null_optional_fields_is_valid():
    assert _validate(_document(_synthetic_story())) == []


def test_synthetic_story_with_confirmed_title_is_valid():
    story = _synthetic_story(
        title="Synthetic Sample Event", displayTitle="Synthetic Sample Event"
    )
    story["metadataStatus"] = "confirmed"
    story["episodes"][0]["subtitle"] = "Synthetic Episode Subtitle"
    story["episodes"][0]["metadataStatus"] = "confirmed"
    assert _validate(_document(story)) == []


def test_rejects_invalid_story_id_format():
    story = _synthetic_story(storyId="not-a-valid-id")
    assert _validate(_document(story)) != []


def test_rejects_invalid_category():
    story = _synthetic_story(category="unknown_category")
    assert _validate(_document(story)) != []


def test_rejects_invalid_metadata_status():
    story = _synthetic_story(metadataStatus="not_a_real_status")
    assert _validate(_document(story)) != []


def test_rejects_episode_number_below_one():
    story = _synthetic_story()
    story["episodes"][0]["episodeNumber"] = 0
    assert _validate(_document(story)) != []


def test_rejects_missing_required_field():
    story = _synthetic_story()
    del story["rawDirectory"]
    assert _validate(_document(story)) != []


def test_rejects_additional_properties():
    story = _synthetic_story(unexpectedField="not allowed")
    assert _validate(_document(story)) != []


def test_rejects_wrong_document_type():
    document = _document(_synthetic_story())
    document["documentType"] = "not_story_manifest"
    assert _validate(document) != []


# ----------------------------------------------------------------
# titleSource / subtitleSource (feature/story-title-subtitle-import-design)
# ----------------------------------------------------------------


def test_existing_template_still_validates_without_source_tracking_fields():
    """titleSource/subtitleSourceを追加した後も、既存templateが
    (これらのフィールドを含まないまま) schema検証を通ることを確認する
    (後方互換性、Story_Manifest_Design.md §13.1)。"""
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    for story in document["stories"]:
        assert "titleSource" not in story
        for episode in story["episodes"]:
            assert "subtitleSource" not in episode
    assert _validate(document) == []


def test_title_source_is_optional_and_defaults_absent():
    """titleSourceを省略したエントリも引き続き有効であることを確認する。"""
    assert _validate(_document(_synthetic_story())) == []


def test_title_source_null_is_valid():
    story = _synthetic_story(titleSource=None)
    assert _validate(_document(story)) == []


def test_title_source_with_wiki_story_list_is_valid():
    story = _synthetic_story(
        title="Synthetic Sample Event",
        titleSource={
            "sourceType": "wiki_story_list",
            "label": "Synthetic wiki list",
            "referenceId": None,
            "notes": None,
        },
    )
    story["metadataStatus"] = "confirmed"
    assert _validate(_document(story)) == []


def test_subtitle_source_with_official_game_ui_is_valid():
    story = _synthetic_story()
    story["episodes"][0]["subtitle"] = "Synthetic Episode Subtitle"
    story["episodes"][0]["subtitleSource"] = {
        "sourceType": "official_game_ui",
        "label": None,
        "referenceId": None,
        "notes": None,
    }
    story["episodes"][0]["metadataStatus"] = "confirmed"
    assert _validate(_document(story)) == []


def test_rejects_invalid_title_source_source_type():
    story = _synthetic_story(
        titleSource={
            "sourceType": "not_a_real_source_type",
            "label": None,
            "referenceId": None,
            "notes": None,
        }
    )
    assert _validate(_document(story)) != []


def test_rejects_title_source_with_additional_properties():
    story = _synthetic_story(
        titleSource={
            "sourceType": "manual",
            "label": None,
            "referenceId": None,
            "notes": None,
            "unexpectedField": "not allowed",
        }
    )
    assert _validate(_document(story)) != []


# ----------------------------------------------------------------
# publicStoryId / publicEpisodeId (feature/story-manifest-public-id-fields-design)
# ----------------------------------------------------------------


def test_public_story_id_field_exists_in_schema():
    schema = _load_schema()
    story_props = schema["definitions"]["StoryManifestEntry"]["properties"]
    assert "publicStoryId" in story_props


def test_public_episode_id_field_exists_in_schema():
    schema = _load_schema()
    episode_props = schema["definitions"]["StoryManifestEpisodeEntry"]["properties"]
    assert "publicEpisodeId" in episode_props


def test_public_story_id_is_not_in_required_list():
    schema = _load_schema()
    required = schema["definitions"]["StoryManifestEntry"]["required"]
    assert "publicStoryId" not in required


def test_public_episode_id_is_not_in_required_list():
    schema = _load_schema()
    required = schema["definitions"]["StoryManifestEpisodeEntry"]["required"]
    assert "publicEpisodeId" not in required


def test_manifest_without_public_ids_remains_valid():
    """既存manifest (public IDフィールドを含まない) がそのまま
    schema検証を通ることを確認する (後方互換、additiveな追加)。"""
    assert _validate(_document(_synthetic_story())) == []


def test_manifest_with_public_ids_is_valid():
    story = _synthetic_story(publicStoryId="EVT_250626_001")
    story["episodes"][0]["publicEpisodeId"] = "EVT_250626_001_E01"
    assert _validate(_document(story)) == []


def test_public_story_id_null_is_valid():
    story = _synthetic_story(publicStoryId=None)
    assert _validate(_document(story)) == []


def test_public_episode_id_null_is_valid():
    story = _synthetic_story()
    story["episodes"][0]["publicEpisodeId"] = None
    assert _validate(_document(story)) == []


def test_rejects_public_story_id_with_spaces():
    story = _synthetic_story(publicStoryId="EVT 250626 001")
    assert _validate(_document(story)) != []


def test_rejects_public_story_id_with_slash():
    story = _synthetic_story(publicStoryId="EVT/250626/001")
    assert _validate(_document(story)) != []


def test_rejects_public_episode_id_with_spaces():
    story = _synthetic_story()
    story["episodes"][0]["publicEpisodeId"] = "EVT 250626 001 E01"
    assert _validate(_document(story)) != []


def test_rejects_public_episode_id_with_slash():
    story = _synthetic_story()
    story["episodes"][0]["publicEpisodeId"] = "EVT/250626/001/E01"
    assert _validate(_document(story)) != []


def test_rejects_public_story_id_lowercase():
    story = _synthetic_story(publicStoryId="evt_250626_001")
    assert _validate(_document(story)) != []


def test_template_still_validates_without_public_id_values():
    """templateはpublicStoryId/publicEpisodeIdをnullとして含むが、
    schema検証を通ることを確認する。"""
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert _validate(document) == []
    for story in document["stories"]:
        assert story["publicStoryId"] is None
        for episode in story["episodes"]:
            assert episode["publicEpisodeId"] is None


# ----------------------------------------------------------------
# characterId / auxiliaryFiles
# (feature/story-manifest-character-category-support、
# Character_Story_ID_Manifest_Design.md §8.1)
# ----------------------------------------------------------------


def test_character_id_field_exists_in_schema():
    schema = _load_schema()
    story_props = schema["definitions"]["StoryManifestEntry"]["properties"]
    assert "characterId" in story_props


def test_auxiliary_files_field_exists_in_schema():
    schema = _load_schema()
    story_props = schema["definitions"]["StoryManifestEntry"]["properties"]
    assert "auxiliaryFiles" in story_props


def test_character_id_is_not_in_required_list():
    schema = _load_schema()
    required = schema["definitions"]["StoryManifestEntry"]["required"]
    assert "characterId" not in required


def test_auxiliary_files_is_not_in_required_list():
    schema = _load_schema()
    required = schema["definitions"]["StoryManifestEntry"]["required"]
    assert "auxiliaryFiles" not in required


def test_manifest_without_character_id_or_auxiliary_files_remains_valid():
    """既存manifest (characterId/auxiliaryFilesを含まない) がそのまま
    schema検証を通ることを確認する (後方互換、additiveな追加)。"""
    assert _validate(_document(_synthetic_story())) == []


def test_character_id_null_is_valid():
    story = _synthetic_story(characterId=None)
    assert _validate(_document(story)) == []


def test_character_id_with_valid_pattern_is_valid():
    story = _synthetic_story(characterId="CHAR_SYNTH_TEST")
    assert _validate(_document(story)) == []


def test_rejects_character_id_without_char_prefix():
    story = _synthetic_story(characterId="SYNTH_TEST")
    assert _validate(_document(story)) != []


def test_rejects_character_id_lowercase():
    story = _synthetic_story(characterId="char_synth_test")
    assert _validate(_document(story)) != []


def test_empty_auxiliary_files_array_is_valid():
    story = _synthetic_story(auxiliaryFiles=[])
    assert _validate(_document(story)) == []


def test_auxiliary_file_with_variant_role_is_valid():
    story = _synthetic_story(
        auxiliaryFiles=[
            {
                "rawPath": "CHARACTER/x_export/CAB-x-H_scene1_n.dec",
                "sourceFileName": "CAB-x-H_scene1_n.dec",
                "fileRole": "variant",
                "notes": None,
            }
        ]
    )
    assert _validate(_document(story)) == []


def test_auxiliary_file_accepts_all_file_role_choices():
    for file_role in ("variant", "direction", "other"):
        story = _synthetic_story(
            auxiliaryFiles=[
                {
                    "rawPath": "CHARACTER/x_export/CAB-x-aux.dec",
                    "sourceFileName": "CAB-x-aux.dec",
                    "fileRole": file_role,
                    "notes": None,
                }
            ]
        )
        assert _validate(_document(story)) == [], f"failed for {file_role}"


def test_rejects_auxiliary_file_with_invalid_file_role():
    story = _synthetic_story(
        auxiliaryFiles=[
            {
                "rawPath": "CHARACTER/x_export/CAB-x-aux.dec",
                "sourceFileName": "CAB-x-aux.dec",
                "fileRole": "not_a_real_role",
                "notes": None,
            }
        ]
    )
    assert _validate(_document(story)) != []


def test_rejects_auxiliary_file_missing_file_role():
    story = _synthetic_story(
        auxiliaryFiles=[
            {
                "rawPath": "CHARACTER/x_export/CAB-x-aux.dec",
                "sourceFileName": "CAB-x-aux.dec",
                "notes": None,
            }
        ]
    )
    assert _validate(_document(story)) != []


def test_rejects_auxiliary_file_with_additional_properties():
    story = _synthetic_story(
        auxiliaryFiles=[
            {
                "rawPath": "CHARACTER/x_export/CAB-x-aux.dec",
                "sourceFileName": "CAB-x-aux.dec",
                "fileRole": "other",
                "notes": None,
                "unexpectedField": "not allowed",
            }
        ]
    )
    assert _validate(_document(story)) != []


def test_template_character_story_validates_and_uses_synthetic_character_id():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    character_stories = [s for s in document["stories"] if s["category"] == "character"]
    assert len(character_stories) == 1
    story = character_stories[0]
    assert story["characterId"] == "CHAR_AKAGI_HINA"
    assert len(story["auxiliaryFiles"]) == 3
    roles = {aux["fileRole"] for aux in story["auxiliaryFiles"]}
    assert roles == {"variant", "direction", "other"}


def test_all_manifest_source_type_choices_are_valid():
    """Story_Manifest_Design.md §11.5で定義した全sourceTypeがschema上
    有効であることを確認する。"""
    for source_type in (
        "manual",
        "official_game_ui",
        "official_announcement",
        "wiki_story_list",
        "wiki_event_page",
        "imported_candidate",
        "unknown",
    ):
        story = _synthetic_story(
            titleSource={
                "sourceType": source_type,
                "label": None,
                "referenceId": None,
                "notes": None,
            }
        )
        assert _validate(_document(story)) == [], f"failed for {source_type}"
