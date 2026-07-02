"""
tests/extractor/test_item_lore_event_candidate_extraction.py
agents/extractor/extractor.py の ItemCandidate / LoreCandidate / EventCandidate
抽出 (rule-based) のテスト。

構造的に取得できる手がかり (明示的なitemId/itemName、loreId/termName、
eventId/eventNameフィールド) のみを対象とし、本文の自然文からの推定は
行わない。LLM呼び出しは行わない。

Normalized Story JSONは、実スクリプトではなく手書きの小さい自作フィクスチャ
(schemas/story.schema.json準拠) だけを使う。
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator

from agents.extractor import Extractor
from agents.extractor.validator import run_semantic_validation

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXTRACTION_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "extraction.schema.json"
EXTRACT_SCRIPT = PROJECT_ROOT / "scripts" / "extract_story.py"
VALIDATE_SCRIPT = PROJECT_ROOT / "scripts" / "validate_extraction_json.py"


# ----------------------------------------------------------------
# Normalized Story JSON フィクスチャビルダー
# ----------------------------------------------------------------


def _build_normalized_story(
    episode_id: str,
    story_id: str,
    scenes: list[dict[str, Any]],
    speaker_assignments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": "0.2",
        "documentType": "normalized_story",
        "storyId": story_id,
        "storyCategory": "MAIN",
        "metadata": {},
        "parser": {
            "parserName": "test",
            "parserVersion": "0.0.0",
            "parserMode": "manual",
            "preserveStageDirections": True,
        },
        "source": {
            "sourceFile": "test.dec",
            "sourceFormat": "manual",
        },
        "episodes": [
            {
                "episodeId": episode_id,
                "episodeNumber": 1,
                "metadata": {},
                "speakerAssignments": speaker_assignments or [],
                "scenes": scenes,
            }
        ],
    }


def _scene(
    scene_id: str,
    blocks: list[dict[str, Any]],
    location: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scene: dict[str, Any] = {"sceneId": scene_id, "sceneNumber": 1, "blocks": blocks}
    if location is not None:
        scene["location"] = location
    return scene


def _dialogue_block(
    block_id: str,
    text: str = "テスト発言",
    item_id: str | None = None,
    item_name: str | None = None,
    lore_id: str | None = None,
    term_name: str | None = None,
    event_id: str | None = None,
    event_name: str | None = None,
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "id": block_id,
        "type": "dialogue",
        "text": text,
        "source": {},
        "voice": {"hasVoice": None},
    }
    if item_id is not None:
        block["itemId"] = item_id
    if item_name is not None:
        block["itemName"] = item_name
    if lore_id is not None:
        block["loreId"] = lore_id
    if term_name is not None:
        block["termName"] = term_name
    if event_id is not None:
        block["eventId"] = event_id
    if event_name is not None:
        block["eventName"] = event_name
    return block


def _stage_direction_block(
    block_id: str,
    direction_type: str = "prop",
    item_id: str | None = None,
    item_name: str | None = None,
    event_id: str | None = None,
    event_name: str | None = None,
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "id": block_id,
        "type": "stage_direction",
        "source": {},
        "directionType": direction_type,
    }
    if item_id is not None:
        block["itemId"] = item_id
    if item_name is not None:
        block["itemName"] = item_name
    if event_id is not None:
        block["eventId"] = event_id
    if event_name is not None:
        block["eventName"] = event_name
    return block


@pytest.fixture
def extraction_validator() -> Draft7Validator:
    with open(EXTRACTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


# ----------------------------------------------------------------
# 1. ItemCandidate
# ----------------------------------------------------------------


def test_item_candidate_created_from_block_id_and_name():
    block = _dialogue_block(
        "EP01_DLG0001", item_id="ITEM_DETARIKI", item_name="デタリキ"
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    items = extraction["items"]

    assert len(items) == 1
    candidate = items[0]
    assert candidate["existingItemId"] == "ITEM_DETARIKI"
    assert candidate["nameCandidates"] == ["デタリキ"]
    assert candidate["evidenceIds"] == ["EP01_DLG0001"]
    assert candidate["confidence"] == pytest.approx(0.9)
    assert candidate["type"] == "item_candidate"
    assert candidate["sourceType"] == "script"


def test_item_candidate_created_from_name_only():
    block = _dialogue_block("EP01_DLG0001", item_name="謎のデバイス")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["items"][0]

    assert candidate["existingItemId"] is None
    assert candidate["nameCandidates"] == ["謎のデバイス"]
    assert candidate["confidence"] == pytest.approx(0.5)


def test_item_candidate_created_from_stage_direction():
    block = _stage_direction_block("EP01_STAGE0001", item_id="ITEM_KEY", item_name="鍵")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["items"][0]

    assert candidate["existingItemId"] == "ITEM_KEY"
    assert candidate["evidenceIds"] == ["EP01_STAGE0001"]
    assert "EP01_STAGE0001" in extraction["evidenceIndex"]


def test_same_item_across_blocks_merges_into_one_candidate():
    block1 = _dialogue_block(
        "EP01_DLG0001", item_id="ITEM_DETARIKI", item_name="デタリキ"
    )
    block2 = _dialogue_block(
        "EP01_DLG0002", item_id="ITEM_DETARIKI", item_name="デタリキ"
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block1, block2])]
    )

    extraction = Extractor().extract_story(story)[0]
    items = extraction["items"]

    assert len(items) == 1
    assert items[0]["evidenceIds"] == ["EP01_DLG0001", "EP01_DLG0002"]


def test_block_without_item_fields_produces_no_item_candidate():
    block = _dialogue_block("EP01_DLG0001")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["items"] == []


# ----------------------------------------------------------------
# 2. LoreCandidate (保守的: Block由来のみ)
# ----------------------------------------------------------------


def test_lore_candidate_created_from_block_id_and_term():
    block = _dialogue_block(
        "EP01_DLG0001", lore_id="LORE_DETARIKIZ", term_name="デタリキZ"
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    lore = extraction["lore"]

    assert len(lore) == 1
    candidate = lore[0]
    assert candidate["existingLoreId"] == "LORE_DETARIKIZ"
    assert candidate["termCandidates"] == ["デタリキZ"]
    assert candidate["evidenceIds"] == ["EP01_DLG0001"]
    assert candidate["confidence"] == pytest.approx(0.9)
    assert candidate["type"] == "lore_candidate"
    assert candidate["sourceType"] == "script"


def test_lore_candidate_created_from_term_only():
    block = _dialogue_block("EP01_DLG0001", term_name="異形生物")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["lore"][0]

    assert candidate["existingLoreId"] is None
    assert candidate["termCandidates"] == ["異形生物"]
    assert candidate["confidence"] == pytest.approx(0.5)


def test_same_lore_across_blocks_merges_into_one_candidate():
    block1 = _dialogue_block("EP01_DLG0001", lore_id="LORE_X", term_name="用語X")
    block2 = _dialogue_block("EP01_DLG0002", lore_id="LORE_X", term_name="用語X")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block1, block2])]
    )

    extraction = Extractor().extract_story(story)[0]
    lore = extraction["lore"]

    assert len(lore) == 1
    assert lore[0]["evidenceIds"] == ["EP01_DLG0001", "EP01_DLG0002"]


def test_lore_is_not_generated_from_stage_direction_or_plain_text():
    # Loreは保守的にBlock (dialogue等) の明示フィールドのみを対象とし、
    # stage_directionや本文テキストからは生成しない
    stage_block = _stage_direction_block("EP01_STAGE0001", direction_type="bgm")
    stage_block["loreId"] = "LORE_SHOULD_NOT_APPEAR"
    stage_block["termName"] = "無視されるはずの用語"
    text_only_block = _dialogue_block(
        "EP01_DLG0001", text="デタリキZという専門用語が本文中に出てくる。"
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [stage_block, text_only_block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["lore"] == []


# ----------------------------------------------------------------
# 3. EventCandidate
# ----------------------------------------------------------------


def test_event_candidate_created_from_block_id_and_name():
    block = _dialogue_block(
        "EP01_DLG0001", event_id="EVENT_JAMMER_FIRST", event_name="ジャマー初出現"
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    events = extraction["events"]

    assert len(events) == 1
    candidate = events[0]
    assert candidate["existingEventId"] == "EVENT_JAMMER_FIRST"
    assert candidate["nameCandidates"] == ["ジャマー初出現"]
    assert candidate["evidenceIds"] == ["EP01_DLG0001"]
    assert candidate["confidence"] == pytest.approx(0.9)
    assert candidate["type"] == "event_candidate"


def test_event_candidate_created_from_stage_direction():
    block = _stage_direction_block(
        "EP01_STAGE0001", direction_type="event_trigger", event_name="警報発令"
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["events"][0]

    assert candidate["nameCandidates"] == ["警報発令"]
    assert candidate["evidenceIds"] == ["EP01_STAGE0001"]
    assert "EP01_STAGE0001" in extraction["evidenceIndex"]


def test_event_candidate_is_not_generated_from_conversation_content():
    # 「戦闘」「移動」等を示唆する自然文があってもeventId/eventNameが
    # 明示されていなければEventCandidateは生成しない
    block = _dialogue_block(
        "EP01_DLG0001", text="ついに戦闘が始まった。全員配置につけ！"
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["events"] == []


def test_same_event_across_blocks_merges_into_one_candidate():
    block1 = _dialogue_block("EP01_DLG0001", event_id="EVENT_X", event_name="出来事X")
    block2 = _dialogue_block("EP01_DLG0002", event_id="EVENT_X", event_name="出来事X")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block1, block2])]
    )

    extraction = Extractor().extract_story(story)[0]
    events = extraction["events"]

    assert len(events) == 1
    assert events[0]["evidenceIds"] == ["EP01_DLG0001", "EP01_DLG0002"]


# ----------------------------------------------------------------
# 4. Character/Location/Organizationとの共存
# ----------------------------------------------------------------


def test_all_candidate_types_coexist():
    speaker_assignments = [
        {
            "slot": "1",
            "sourceCharacterId": "26",
            "speakerId": "CHAR_RAIN",
            "speakerName": "レイン",
        }
    ]
    block = {
        "id": "EP01_DLG0001",
        "type": "dialogue",
        "text": "デタリキZの力でジャマーを倒す",
        "source": {},
        "speaker": {"slot": "1", "isResolved": False},
        "voice": {"hasVoice": None},
        "organizationId": "ORG_TAISAKUHAN",
        "organizationName": "異形生物対策班",
        "itemId": "ITEM_DETARIKI",
        "itemName": "デタリキ",
        "loreId": "LORE_DETARIKIZ",
        "termName": "デタリキZ",
        "eventId": "EVENT_JAMMER_FIRST",
        "eventName": "ジャマー初出現",
    }
    scene = _scene(
        "EP01_SC001", [block], location={"locationId": "LOC_HQ", "locationName": "本部"}
    )
    story = _build_normalized_story("EP01", "TEST_STORY", [scene], speaker_assignments)

    extraction = Extractor().extract_story(story)[0]

    assert len(extraction["characters"]) == 1
    assert len(extraction["locations"]) == 1
    assert len(extraction["organizations"]) == 1
    assert len(extraction["items"]) == 1
    assert len(extraction["lore"]) == 1
    assert len(extraction["events"]) == 1


# ----------------------------------------------------------------
# 5. schema validation / semantic validation
# ----------------------------------------------------------------


def test_item_lore_event_output_matches_extraction_schema(extraction_validator):
    block = _dialogue_block(
        "EP01_DLG0001",
        item_name="デタリキ",
        term_name="デタリキZ",
        event_name="ジャマー初出現",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    errors = list(extraction_validator.iter_errors(extraction))

    assert not errors, [e.message for e in errors]


def test_item_lore_event_evidence_pass_semantic_validation():
    stage_block = _stage_direction_block(
        "EP01_STAGE0001", item_id="ITEM_KEY", item_name="鍵", event_name="扉が開く"
    )
    dialogue_block = _dialogue_block(
        "EP01_DLG0001", lore_id="LORE_X", term_name="用語X"
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [stage_block, dialogue_block])]
    )

    extraction = Extractor().extract_story(story)[0]
    issues = run_semantic_validation(extraction)
    errors = [i for i in issues if i.severity == "error"]

    assert not errors, [i.message for i in errors]


# ----------------------------------------------------------------
# CLI: scripts/extract_story.py の出力がschema/semantic両方に通ること
# ----------------------------------------------------------------


def test_cli_extract_story_output_passes_schema_and_semantic_validation(tmp_path):
    block = _dialogue_block(
        "EP01_DLG0001",
        item_id="ITEM_DETARIKI",
        item_name="デタリキ",
        lore_id="LORE_DETARIKIZ",
        term_name="デタリキZ",
        event_id="EVENT_JAMMER_FIRST",
        event_name="ジャマー初出現",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    normalized_path = tmp_path / "normalized.json"
    with open(normalized_path, "w", encoding="utf-8") as f:
        json.dump(story, f, ensure_ascii=False)

    output_dir = tmp_path / "extracted"

    extract_result = subprocess.run(
        [
            sys.executable,
            str(EXTRACT_SCRIPT),
            "--input",
            str(normalized_path),
            "--output",
            str(output_dir),
            "--validate",
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert extract_result.returncode == 0, extract_result.stderr

    output_file = output_dir / "EP01.extraction.json"
    assert output_file.exists()

    semantic_result = subprocess.run(
        [
            sys.executable,
            str(VALIDATE_SCRIPT),
            "--input",
            str(output_file),
            "--semantic",
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert semantic_result.returncode == 0, semantic_result.stderr

    with open(output_file, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["items"]) == 1
    assert len(data["lore"]) == 1
    assert len(data["events"]) == 1
