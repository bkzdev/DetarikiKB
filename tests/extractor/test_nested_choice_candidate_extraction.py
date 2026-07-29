"""choice option内BlockからのCandidate抽出を合成データで検証する。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from agents.extractor import Extractor
from agents.extractor.validator import run_semantic_validation

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXTRACTION_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "extraction.schema.json"


def _choice(
    block_id: str, option_id: str, blocks: list[dict[str, Any]], **fields: Any
) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": "choice",
        "source": {},
        "choiceText": None,
        "options": [
            {
                "optionId": option_id,
                "optionText": "合成選択肢",
                "blocks": blocks,
            }
        ],
        **fields,
    }


def _story(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": "0.2",
        "documentType": "normalized_story",
        "storyId": "TEST_NESTED_CHOICE",
        "storyCategory": "MAIN",
        "metadata": {},
        "parser": {
            "parserName": "test",
            "parserVersion": "0.0.0",
            "parserMode": "manual",
            "preserveStageDirections": True,
        },
        "source": {"sourceFile": "synthetic.dec", "sourceFormat": "manual"},
        "episodes": [
            {
                "episodeId": "TEST_NESTED_CHOICE_E01",
                "episodeNumber": 1,
                "metadata": {},
                "speakerAssignments": [],
                "scenes": [
                    {
                        "sceneId": "TEST_NESTED_CHOICE_E01_SC001",
                        "sceneNumber": 1,
                        "blocks": blocks,
                    }
                ],
            }
        ],
    }


def _dialogue(block_id: str, **fields: Any) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": "dialogue",
        "source": {},
        "text": "合成会話",
        "speaker": {
            "speakerId": "CHAR_SYNTHETIC_A",
            "speakerName": "合成人物A",
            "sourceCharacterId": "900001",
            "isResolved": True,
        },
        "voice": {"hasVoice": None},
        **fields,
    }


def test_nested_choice_blocks_feed_all_supported_candidate_extractors():
    top_dialogue = _dialogue(
        "TEST_NESTED_CHOICE_E01_DLG0001",
        itemId="ITEM_SYNTHETIC",
        itemName="合成アイテム",
    )
    nested_dialogue = _dialogue(
        "TEST_NESTED_CHOICE_E01_DLG0002",
        organizationId="ORG_SYNTHETIC",
        organizationName="合成組織",
        itemId="ITEM_SYNTHETIC",
        itemName="合成アイテム",
        loreId="LORE_SYNTHETIC",
        termName="合成用語",
        eventId="EVENT_SYNTHETIC",
        eventName="合成イベント",
        relationshipType="AFFILIATED_WITH",
        sourceCandidate="CHAR_SYNTHETIC_A",
        targetCandidate="ORG_SYNTHETIC",
        timelineId="TIMELINE_SYNTHETIC",
    )
    nested_stage = {
        "id": "TEST_NESTED_CHOICE_E01_STAGE0001",
        "type": "stage_direction",
        "source": {"confidence": 0.6},
        "directionType": "background",
        "rawCommand": "@SyntheticBackground",
        "normalizedCommand": "synthetic_background",
        "locationId": "LOC_SYNTHETIC",
        "locationName": "合成地点",
        "itemId": "ITEM_SYNTHETIC",
        "itemName": "合成アイテム",
    }
    deeply_nested_narration = {
        "id": "TEST_NESTED_CHOICE_E01_NAR0001",
        "type": "narration",
        "source": {},
        "text": "合成ナレーション",
        "narrationType": "plain",
        "organizationId": "ORG_SYNTHETIC",
        "organizationName": "合成組織",
        "itemId": "ITEM_SYNTHETIC",
        "itemName": "合成アイテム",
        "loreId": "LORE_SYNTHETIC",
        "termName": "合成用語",
        "eventId": "EVENT_SYNTHETIC",
        "eventName": "合成イベント",
    }
    inner_choice = _choice(
        "TEST_NESTED_CHOICE_E01_CHOICE002",
        "TEST_NESTED_CHOICE_E01_CHOICE002_OPT01",
        [deeply_nested_narration],
    )
    outer_choice = _choice(
        "TEST_NESTED_CHOICE_E01_CHOICE001",
        "TEST_NESTED_CHOICE_E01_CHOICE001_OPT01",
        [nested_dialogue, nested_stage, inner_choice],
        eventId="EVENT_SYNTHETIC",
        eventName="合成イベント",
    )

    extraction = Extractor().extract_story(_story([top_dialogue, outer_choice]))[0]

    assert extraction["characters"][0]["evidenceIds"] == [
        "TEST_NESTED_CHOICE_E01_DLG0001",
        "TEST_NESTED_CHOICE_E01_DLG0002",
    ]
    assert extraction["organizations"][0]["evidenceIds"] == [
        "TEST_NESTED_CHOICE_E01_DLG0002",
        "TEST_NESTED_CHOICE_E01_NAR0001",
    ]
    assert extraction["locations"][0]["evidenceIds"] == [
        "TEST_NESTED_CHOICE_E01_STAGE0001"
    ]
    assert extraction["items"][0]["evidenceIds"] == [
        "TEST_NESTED_CHOICE_E01_DLG0001",
        "TEST_NESTED_CHOICE_E01_DLG0002",
        "TEST_NESTED_CHOICE_E01_STAGE0001",
        "TEST_NESTED_CHOICE_E01_NAR0001",
    ]
    assert extraction["lore"][0]["evidenceIds"] == [
        "TEST_NESTED_CHOICE_E01_DLG0002",
        "TEST_NESTED_CHOICE_E01_NAR0001",
    ]
    assert extraction["events"][0]["evidenceIds"] == [
        "TEST_NESTED_CHOICE_E01_CHOICE001",
        "TEST_NESTED_CHOICE_E01_DLG0002",
        "TEST_NESTED_CHOICE_E01_NAR0001",
    ]
    assert extraction["relationships"] == []
    assert extraction["timelineCandidates"] == []

    referenced_ids = {
        evidence_id
        for key in (
            "characters",
            "organizations",
            "locations",
            "items",
            "lore",
            "events",
        )
        for candidate in extraction[key]
        for evidence_id in candidate["evidenceIds"]
    }
    assert referenced_ids <= extraction["evidenceIndex"].keys()
    assert (
        extraction["evidenceIndex"]["TEST_NESTED_CHOICE_E01_STAGE0001"]["sceneId"]
        == "TEST_NESTED_CHOICE_E01_SC001"
    )

    with open(EXTRACTION_SCHEMA_PATH, encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    schema_errors = list(Draft7Validator(schema).iter_errors(extraction))
    assert not schema_errors, [error.message for error in schema_errors]

    semantic_errors = [
        issue
        for issue in run_semantic_validation(extraction)
        if issue.severity == "error"
    ]
    assert not semantic_errors, [issue.message for issue in semantic_errors]
