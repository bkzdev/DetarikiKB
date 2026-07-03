"""
tests/extractor/test_timeline_candidate_extraction.py
agents/extractor/extractor.py の TimelineCandidate 抽出 (rule-based) のテスト。

構造的に取得できる手がかり (episode.metadataの明示的なcanonicalOrder/
releaseOrder/displayOrder、Block上の明示的なtimelineId/timelineLabel/
timePosition/orderValue、stage_direction等の明示的なflashback/flashforward/
dayChange/timeShift/sceneTime構造フィールド) のみを対象とし、本文の自然文
からの時系列推定 (「昔」「その後」「翌日」「回想」等) は行わない。
LLM呼び出しは行わない。

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
    episode_metadata: dict[str, Any] | None = None,
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
                "metadata": episode_metadata or {},
                "speakerAssignments": [],
                "scenes": scenes,
            }
        ],
    }


def _scene(scene_id: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {"sceneId": scene_id, "sceneNumber": 1, "blocks": blocks}


def _dialogue_block(
    block_id: str,
    text: str = "テスト発言",
    **extra: Any,
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "id": block_id,
        "type": "dialogue",
        "text": text,
        "source": {},
        "voice": {"hasVoice": None},
    }
    block.update(extra)
    return block


def _stage_direction_block(block_id: str, **extra: Any) -> dict[str, Any]:
    block: dict[str, Any] = {
        "id": block_id,
        "type": "stage_direction",
        "source": {},
        "directionType": "other",
    }
    block.update(extra)
    return block


@pytest.fixture
def extraction_validator() -> Draft7Validator:
    with open(EXTRACTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


# ----------------------------------------------------------------
# 1. 明示的なtimelineId/timelineLabelからの生成
# ----------------------------------------------------------------


def test_timeline_candidate_created_from_timeline_id():
    block = _dialogue_block("EP01_DLG0001", timelineId="TL_ARC1")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    timelines = extraction["timelineCandidates"]

    assert len(timelines) == 1
    candidate = timelines[0]
    assert candidate["type"] == "timeline_candidate"
    assert candidate["sourceType"] == "script"
    assert candidate["kind"] == "explicit_order"
    assert candidate["scope"] == "block"
    assert candidate["sourceTimelineId"] == "TL_ARC1"
    assert candidate["evidenceIds"] == ["EP01_DLG0001"]
    assert candidate["confidence"] == pytest.approx(0.9)


def test_timeline_candidate_created_from_timeline_label_only():
    block = _dialogue_block("EP01_DLG0001", timelineLabel="回想:幼少期")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["timelineCandidates"][0]

    assert candidate["nameCandidates"] == ["回想:幼少期"]
    assert candidate["sourceTimelineId"] is None
    assert candidate["confidence"] == pytest.approx(0.5)


# ----------------------------------------------------------------
# 2. 明示的なtimePosition/orderValueからの生成
# ----------------------------------------------------------------


def test_timeline_candidate_created_from_order_value():
    block = _dialogue_block("EP01_DLG0001", orderValue=3)
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["timelineCandidates"][0]

    assert candidate["orderValue"] == 3
    assert candidate["orderField"] == "orderValue"
    assert candidate["confidence"] == pytest.approx(0.9)


def test_timeline_candidate_created_from_numeric_time_position():
    block = _dialogue_block("EP01_DLG0001", timePosition=2)
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["timelineCandidates"][0]

    assert candidate["orderValue"] == 2
    assert candidate["orderField"] == "timePosition"
    assert candidate["confidence"] == pytest.approx(0.9)


def test_timeline_candidate_created_from_string_time_position_is_label():
    block = _dialogue_block("EP01_DLG0001", timePosition="2日目")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["timelineCandidates"][0]

    assert candidate["orderValue"] is None
    assert candidate["nameCandidates"] == ["2日目"]
    assert candidate["confidence"] == pytest.approx(0.5)


def test_timeline_candidate_created_from_episode_metadata_canonical_order():
    block = _dialogue_block("EP01_DLG0001")
    story = _build_normalized_story(
        "EP01",
        "TEST_STORY",
        [_scene("EP01_SC001", [block])],
        episode_metadata={"canonicalOrder": 5},
    )

    extraction = Extractor().extract_story(story)[0]
    timelines = extraction["timelineCandidates"]

    assert len(timelines) == 1
    candidate = timelines[0]
    assert candidate["kind"] == "explicit_order"
    assert candidate["scope"] == "episode"
    assert candidate["orderValue"] == 5
    assert candidate["orderField"] == "canonicalOrder"
    assert candidate["evidenceIds"] == ["EP01"]
    assert candidate["confidence"] == pytest.approx(0.9)
    assert "EP01" in extraction["evidenceIndex"]


def test_timeline_candidates_from_multiple_episode_order_fields():
    block = _dialogue_block("EP01_DLG0001")
    story = _build_normalized_story(
        "EP01",
        "TEST_STORY",
        [_scene("EP01_SC001", [block])],
        episode_metadata={"releaseOrder": 10, "displayOrder": 10200},
    )

    extraction = Extractor().extract_story(story)[0]
    timelines = extraction["timelineCandidates"]

    assert len(timelines) == 2
    order_fields = {c["orderField"] for c in timelines}
    assert order_fields == {"releaseOrder", "displayOrder"}


def test_timeline_candidate_from_stage_direction_marker():
    block = _stage_direction_block("EP01_STAGE0001", flashback=True)
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    timelines = extraction["timelineCandidates"]

    assert len(timelines) == 1
    candidate = timelines[0]
    assert candidate["kind"] == "temporal_marker"
    assert candidate["markerType"] == "flashback"
    assert candidate["evidenceIds"] == ["EP01_STAGE0001"]
    assert candidate["confidence"] == pytest.approx(0.7)
    assert "EP01_STAGE0001" in extraction["evidenceIndex"]


# ----------------------------------------------------------------
# 3. 同一Timeline情報の統合 / evidenceIdsの集約
# ----------------------------------------------------------------


def test_same_timeline_id_across_blocks_merges_into_one_candidate():
    block1 = _dialogue_block("EP01_DLG0001", timelineId="TL_ARC1")
    block2 = _dialogue_block("EP01_DLG0002", timelineId="TL_ARC1")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block1, block2])]
    )

    extraction = Extractor().extract_story(story)[0]
    timelines = extraction["timelineCandidates"]

    assert len(timelines) == 1
    assert timelines[0]["evidenceIds"] == ["EP01_DLG0001", "EP01_DLG0002"]


def test_same_marker_type_across_blocks_merges_into_one_candidate():
    block1 = _stage_direction_block("EP01_STAGE0001", flashback=True)
    block2 = _stage_direction_block("EP01_STAGE0002", flashback=True)
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block1, block2])]
    )

    extraction = Extractor().extract_story(story)[0]
    timelines = extraction["timelineCandidates"]

    assert len(timelines) == 1
    assert timelines[0]["evidenceIds"] == ["EP01_STAGE0001", "EP01_STAGE0002"]


def test_different_marker_types_produce_separate_candidates():
    block1 = _stage_direction_block("EP01_STAGE0001", flashback=True)
    block2 = _stage_direction_block("EP01_STAGE0002", dayChange=True)
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block1, block2])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert len(extraction["timelineCandidates"]) == 2


# ----------------------------------------------------------------
# 4. timeline情報が無いBlockからは生成されない / 自然文推定はしない
# ----------------------------------------------------------------


def test_block_without_timeline_fields_produces_no_candidate():
    block = _dialogue_block("EP01_DLG0001")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["timelineCandidates"] == []


def test_natural_language_hints_do_not_produce_timeline_candidate():
    # 本文中に「昔」「回想」「翌日」等の語があっても、明示的な構造フィールドが
    # 無ければ生成しない
    block = _dialogue_block(
        "EP01_DLG0001",
        text="これは昔の出来事で、翌日には回想が終わってその後の話に戻る",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["timelineCandidates"] == []


def test_non_numeric_non_string_metadata_order_is_ignored():
    block = _dialogue_block("EP01_DLG0001")
    story = _build_normalized_story(
        "EP01",
        "TEST_STORY",
        [_scene("EP01_SC001", [block])],
        episode_metadata={"canonicalOrder": None},
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["timelineCandidates"] == []


# ----------------------------------------------------------------
# 5. EventCandidateとの共存
# ----------------------------------------------------------------


def test_timeline_coexists_with_event_candidate():
    block = _dialogue_block(
        "EP01_DLG0001",
        eventId="EVENT_JAMMER_FIRST",
        eventName="ジャマー初出現",
        timelineId="TL_ARC1",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]

    assert len(extraction["events"]) == 1
    assert len(extraction["timelineCandidates"]) == 1
    assert extraction["events"][0]["existingEventId"] == "EVENT_JAMMER_FIRST"
    assert extraction["timelineCandidates"][0]["sourceTimelineId"] == "TL_ARC1"


# ----------------------------------------------------------------
# 6. schema validation / semantic validation
# ----------------------------------------------------------------


def test_timeline_output_matches_extraction_schema(extraction_validator):
    order_block = _dialogue_block("EP01_DLG0001", timelineId="TL_ARC1")
    marker_block = _stage_direction_block("EP01_STAGE0001", flashback=True)
    story = _build_normalized_story(
        "EP01",
        "TEST_STORY",
        [_scene("EP01_SC001", [order_block, marker_block])],
        episode_metadata={"canonicalOrder": 1},
    )

    extraction = Extractor().extract_story(story)[0]
    errors = list(extraction_validator.iter_errors(extraction))

    assert not errors, [e.message for e in errors]


def test_timeline_passes_semantic_validation():
    order_block = _dialogue_block("EP01_DLG0001", timelineId="TL_ARC1")
    marker_block = _stage_direction_block("EP01_STAGE0001", flashback=True)
    story = _build_normalized_story(
        "EP01",
        "TEST_STORY",
        [_scene("EP01_SC001", [order_block, marker_block])],
        episode_metadata={"canonicalOrder": 1},
    )

    extraction = Extractor().extract_story(story)[0]
    issues = run_semantic_validation(extraction)
    errors = [i for i in issues if i.severity == "error"]

    assert not errors, [i.message for i in errors]
    # 明示的なフィールドを持つcandidateはtimeline系のwarningも出さない
    timeline_warnings = [i for i in issues if i.rule.startswith("timeline_")]
    assert not timeline_warnings


# ----------------------------------------------------------------
# CLI: scripts/extract_story.py の出力がschema/semantic両方に通ること
# ----------------------------------------------------------------


def test_cli_extract_story_output_passes_schema_and_semantic_validation(tmp_path):
    order_block = _dialogue_block("EP01_DLG0001", timelineId="TL_ARC1")
    marker_block = _stage_direction_block("EP01_STAGE0001", flashback=True)
    story = _build_normalized_story(
        "EP01",
        "TEST_STORY",
        [_scene("EP01_SC001", [order_block, marker_block])],
        episode_metadata={"canonicalOrder": 1},
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
    assert len(data["timelineCandidates"]) == 3
