"""
tests/extractor/test_special_speaker_label_candidate_extraction.py
agents/extractor/character.py の SpecialSpeakerLabelCandidate 抽出のテスト。

name command/@ChTalkName 由来のspeaker labelのうち、speaker_labels.
is_special_label_typeがTrueのものが、通常のCharacterCandidateとは
別配列 (specialSpeakerLabelCandidates) へ分離されることを確認する。
合成データのみを使う。
"""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator

from agents.extractor import Extractor
from agents.extractor.validator import run_semantic_validation
from agents.parser.speaker_labels import analyze_speaker_label

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXTRACTION_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "extraction.schema.json"


@pytest.fixture
def extraction_validator() -> Draft7Validator:
    with open(EXTRACTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


def _build_normalized_story(
    episode_id: str, story_id: str, scenes: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "schemaVersion": "0.2",
        "documentType": "normalized_story",
        "storyId": story_id,
        "storyCategory": "EVT",
        "metadata": {},
        "parser": {
            "parserName": "test",
            "parserVersion": "0.0.0",
            "parserMode": "manual",
            "preserveStageDirections": True,
        },
        "source": {"sourceFile": "test.dec", "sourceFormat": "manual"},
        "episodes": [
            {
                "episodeId": episode_id,
                "episodeNumber": 1,
                "metadata": {},
                "speakerAssignments": [],
                "scenes": scenes,
            }
        ],
    }


def _scene(scene_id: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {"sceneId": scene_id, "sceneNumber": 1, "blocks": blocks}


def _name_command_speaker(raw_label: str) -> dict[str, Any]:
    """name コマンド由来speaker labelを模したspeaker dictを作る
    (StoryParserを介さず、Normalized Story JSON形式を直接構築する)。
    """
    analysis = analyze_speaker_label(raw_label, source="name_command")
    return {
        "speakerId": None,
        "speakerName": raw_label,
        "sourceCharacterId": None,
        "slot": None,
        "isResolved": False,
        "labelSource": "name_command",
        "labelAnalysis": analysis.to_dict(),
    }


def _dialogue_block(
    block_id: str, speaker: dict[str, Any], text: str = "テスト"
) -> dict:
    return {
        "id": block_id,
        "type": "dialogue",
        "text": text,
        "source": {},
        "speaker": speaker,
        "voice": {"hasVoice": None},
    }


def test_speaker_group_label_routed_to_special_candidates_not_characters():
    block = _dialogue_block("EP01_DLG0001", _name_command_speaker("セイナ＆イヴ"))
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]

    assert extraction["characters"] == []
    special = extraction["specialSpeakerLabelCandidates"]
    assert len(special) == 1
    candidate = special[0]
    assert candidate["type"] == "special_speaker_label_candidate"
    assert candidate["rawLabel"] == "セイナ＆イヴ"
    assert candidate["labelType"] == "speaker_group"
    assert candidate["components"] == ["セイナ", "イヴ"]
    assert candidate["resolutionStatus"] == "inferred"
    assert candidate["evidenceIds"] == ["EP01_DLG0001"]


def test_generic_speaker_label_routed_to_special_candidates():
    block = _dialogue_block("EP01_DLG0001", _name_command_speaker("？？？"))
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]

    assert extraction["characters"] == []
    special = extraction["specialSpeakerLabelCandidates"]
    assert len(special) == 1
    assert special[0]["labelType"] == "generic_speaker"
    assert special[0]["resolutionStatus"] == "needs_review"


def test_single_speaker_name_command_label_stays_normal_character_candidate():
    block = _dialogue_block("EP01_DLG0001", _name_command_speaker("レイン"))
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]

    assert extraction["specialSpeakerLabelCandidates"] == []
    characters = extraction["characters"]
    assert len(characters) == 1
    assert characters[0]["nameCandidates"] == ["レイン"]


def test_multiple_utterances_of_same_special_label_merge_into_one_candidate():
    block1 = _dialogue_block(
        "EP01_DLG0001", _name_command_speaker("紬（小声）"), text="一言目"
    )
    block2 = _dialogue_block(
        "EP01_DLG0002", _name_command_speaker("紬（小声）"), text="二言目"
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block1, block2])]
    )

    extraction = Extractor().extract_story(story)[0]
    special = extraction["specialSpeakerLabelCandidates"]

    assert len(special) == 1
    assert special[0]["evidenceIds"] == ["EP01_DLG0001", "EP01_DLG0002"]


def test_regular_character_and_special_label_coexist_in_same_episode():
    normal_block = _dialogue_block(
        "EP01_DLG0001",
        {
            "speakerId": "CHAR_RAIN",
            "speakerName": "レイン",
            "sourceCharacterId": "26",
            "isResolved": True,
        },
    )
    special_block = _dialogue_block(
        "EP01_DLG0002", _name_command_speaker("セイナ＆イヴ")
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [normal_block, special_block])]
    )

    extraction = Extractor().extract_story(story)[0]

    assert len(extraction["characters"]) == 1
    assert extraction["characters"][0]["existingCharacterId"] == "CHAR_RAIN"
    assert len(extraction["specialSpeakerLabelCandidates"]) == 1


def test_special_speaker_label_candidate_passes_schema_validation(
    extraction_validator,
):
    block = _dialogue_block("EP01_DLG0001", _name_command_speaker("セイナ＆イヴ"))
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    errors = list(extraction_validator.iter_errors(extraction))

    assert not errors, [e.message for e in errors]


def test_special_speaker_label_candidate_passes_semantic_validation():
    block = _dialogue_block("EP01_DLG0001", _name_command_speaker("セイナ＆イヴ"))
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    issues = run_semantic_validation(extraction)
    errors = [i for i in issues if i.severity == "error"]

    assert not errors, [i.message for i in issues]
