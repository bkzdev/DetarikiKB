"""
tests/parser/test_normalized_story_schema.py
Normalized Story JSON が story.schema.json に準拠しているかテストする
"""

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

from agents.parser.normalizer import Normalizer
from agents.parser.parser import StoryParser

# プロジェクトルートからの相対パス
SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "story.schema.json"


@pytest.fixture
def schema():
    assert SCHEMA_PATH.exists(), f"Schema file not found at {SCHEMA_PATH}"
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_normalized_json_schema(schema):
    # テスト用の簡易スクリプト
    script = """$num0 = 26
@ScenarioCos 1 26
@ChTalk 0
正常な会話ブロックです。
msg
そしてナレーション。
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script, source_file="test_script")

    normalizer = Normalizer(
        story_id="TEST_001",
        story_category="MAIN",
        source_file="test_script",
    )

    story_json = normalizer.normalize(parse_result, line_count=6)

    # jsonschemaによる検証
    try:
        validate(instance=story_json, schema=schema)
    except ValidationError as e:
        pytest.fail(f"Schema validation failed: {e.message}\nPath: {list(e.path)}")


def test_normalized_json_with_choice(schema):
    script = """branch 選択肢1 選択肢2
#if $branch
@ChTalk 0
ルート1
#else
@ChTalk 0
ルート2
#endif
"""
    parser = StoryParser()
    parse_result = parser.parse_text(script, source_file="test_choice")

    normalizer = Normalizer(
        story_id="TEST_002",
        story_category="EVT",
        source_file="test_choice",
    )

    story_json = normalizer.normalize(parse_result)

    # jsonschemaによる検証
    try:
        validate(instance=story_json, schema=schema)
    except ValidationError as e:
        pytest.fail(
            f"Schema validation failed (choice block): {e.message}\n"
            f"Path: {list(e.path)}"
        )


def test_scene_accepts_structured_extension_fields(schema):
    """Scene直下の構造化された拡張フィールドを保持できる。"""
    parser = StoryParser()
    parse_result = parser.parse_text(
        "@ChTalkName 0 テスト話者 synthetic/voice\n合成テストです。\n",
        source_file="test_scene_extensions",
    )
    normalizer = Normalizer(
        story_id="TEST_SCENE_EXTENSIONS",
        story_category="OTHER",
        source_file="test_scene_extensions",
    )
    story_json = normalizer.normalize(parse_result)
    scene = story_json["episodes"][0]["scenes"][0]
    scene.update(
        {
            "itemId": "ITEM_SYNTHETIC",
            "eventName": "合成イベント",
            "timelineId": "TIMELINE_SYNTHETIC",
            "orderValue": 10,
            "extensionPayload": {"source": "synthetic"},
        }
    )

    validate(instance=story_json, schema=schema)


def test_scene_extensions_keep_core_field_constraints(schema):
    """拡張許容後もSceneの既知フィールド制約は維持される。"""
    parser = StoryParser()
    parse_result = parser.parse_text(
        "合成ナレーションです。\n",
        source_file="test_scene_core_constraints",
    )
    normalizer = Normalizer(
        story_id="TEST_SCENE_CONSTRAINTS",
        story_category="OTHER",
        source_file="test_scene_core_constraints",
    )
    story_json = normalizer.normalize(parse_result)
    scene = story_json["episodes"][0]["scenes"][0]
    scene["customMarker"] = True

    scene["sceneNumber"] = "1"
    with pytest.raises(ValidationError):
        validate(instance=story_json, schema=schema)

    scene["sceneNumber"] = 1
    del scene["blocks"]
    with pytest.raises(ValidationError):
        validate(instance=story_json, schema=schema)


def test_normalized_json_char_hs_category(schema):
    """storyCategory `CHAR_HS` (H_scene系例外変種、
    Character_Story_ID_Manifest_Design.md §5.2) がschemaで受理されることを
    確認する回帰テスト (character-story-id-manifest-design-pr-d)。"""
    script = "$num0 = 1\n@ChTalk 0 test/asset/1\nテスト用のせりふです。\n"
    parser = StoryParser()
    parse_result = parser.parse_text(script, source_file="H_scene1")

    normalizer = Normalizer(
        story_id="CHAR_HS_TEST",
        story_category="CHAR_HS",
        episode_id="CHAR_HS_TEST_E01_VN",
        source_file="H_scene1_n",
        variant_trace={
            "baseEpisodeId": "CHAR_HS_TEST_E01",
            "variantPattern": "n",
            "dupIndex": None,
            "judgment": "exception",
        },
    )
    story_json = normalizer.normalize(parse_result)

    try:
        validate(instance=story_json, schema=schema)
    except ValidationError as e:
        pytest.fail(
            f"Schema validation failed (CHAR_HS): {e.message}\nPath: {list(e.path)}"
        )
