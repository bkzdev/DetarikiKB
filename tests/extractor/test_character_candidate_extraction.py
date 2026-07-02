"""
tests/extractor/test_character_candidate_extraction.py
agents/extractor/extractor.py の CharacterCandidate 抽出 (rule-based) のテスト。

speakerAssignments / dialogue / monologue Block から最小のCharacterCandidateを
生成する。choice内の話者は今回のスコープでは対象外。LLM呼び出しは行わない。

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
STORY_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "story.schema.json"
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


def _scene(scene_id: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {"sceneId": scene_id, "sceneNumber": 1, "blocks": blocks}


def _dialogue_block(
    block_id: str, speaker: dict[str, Any], text: str = "テスト発言"
) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": "dialogue",
        "text": text,
        "source": {},
        "speaker": speaker,
        "voice": {"hasVoice": None},
    }


def _monologue_block(
    block_id: str, speaker: dict[str, Any], text: str = "テストモノローグ"
) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": "monologue",
        "text": text,
        "source": {},
        "speaker": speaker,
        "voice": {"hasVoice": None},
    }


def _choice_block(
    block_id: str, option_id: str, inner_blocks: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "id": block_id,
        "type": "choice",
        "source": {},
        "choiceText": None,
        "options": [
            {"optionId": option_id, "optionText": "選択肢1", "blocks": inner_blocks}
        ],
    }


# ----------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------


@pytest.fixture
def story_validator() -> Draft7Validator:
    with open(STORY_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


@pytest.fixture
def extraction_validator() -> Draft7Validator:
    with open(EXTRACTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


# ----------------------------------------------------------------
# フィクスチャビルダー自体の健全性確認
# ----------------------------------------------------------------


def test_fixture_builder_produces_schema_valid_normalized_story(story_validator):
    block = _dialogue_block(
        "EP01_DLG0001",
        speaker={"speakerId": "CHAR_A", "speakerName": "A", "isResolved": True},
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    errors = list(story_validator.iter_errors(story))
    assert not errors, [e.message for e in errors]


# ----------------------------------------------------------------
# 1. speakerAssignments からの生成
# ----------------------------------------------------------------


def test_character_candidate_created_from_speaker_assignments():
    speaker_assignments = [
        {
            "slot": "1",
            "sourceCharacterId": "26",
            "speakerId": "CHAR_RAIN",
            "speakerName": "レイン",
        }
    ]
    # Block自体のspeakerはslotのみ (未解決) -> speakerAssignmentsで補完される
    block = _dialogue_block("EP01_DLG0001", speaker={"slot": "1", "isResolved": False})
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])], speaker_assignments
    )

    extraction = Extractor().extract_story(story)[0]
    characters = extraction["characters"]

    assert len(characters) == 1
    candidate = characters[0]
    assert candidate["existingCharacterId"] == "CHAR_RAIN"
    assert candidate["sourceCharacterId"] == "26"
    assert candidate["nameCandidates"] == ["レイン"]
    assert candidate["evidenceIds"] == ["EP01_DLG0001"]
    assert candidate["confidence"] == pytest.approx(0.9)


# ----------------------------------------------------------------
# 2. dialogue/monologue Block speakerからの生成
# ----------------------------------------------------------------


def test_character_candidate_created_from_dialogue_speaker_resolved():
    block = _dialogue_block(
        "EP01_DLG0001",
        speaker={
            "speakerId": "CHAR_RAIN",
            "speakerName": "レイン",
            "sourceCharacterId": "26",
            "slot": "1",
            "isResolved": True,
        },
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    characters = extraction["characters"]

    assert len(characters) == 1
    assert characters[0]["existingCharacterId"] == "CHAR_RAIN"
    assert characters[0]["confidence"] == pytest.approx(0.9)
    assert characters[0]["type"] == "character_candidate"
    assert characters[0]["sourceType"] == "script"


def test_character_candidate_created_from_monologue_speaker_unresolved():
    block = _monologue_block(
        "EP01_MONO0001",
        speaker={
            "speakerName": "不明人物(ID:99)",
            "sourceCharacterId": "99",
            "isResolved": False,
        },
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["characters"][0]

    assert candidate["existingCharacterId"] is None
    assert candidate["sourceCharacterId"] == "99"
    assert candidate["nameCandidates"] == ["不明人物(ID:99)"]
    assert candidate["confidence"] == pytest.approx(0.5)


# ----------------------------------------------------------------
# 3. 同一話者の複数発言は1件に統合される
# ----------------------------------------------------------------


def test_same_speaker_multiple_utterances_merge_into_one_candidate():
    speaker = {
        "speakerId": "CHAR_RAIN",
        "speakerName": "レイン",
        "sourceCharacterId": "26",
        "isResolved": True,
    }
    block1 = _dialogue_block("EP01_DLG0001", speaker=dict(speaker), text="こんにちは")
    block2 = _monologue_block("EP01_MONO0001", speaker=dict(speaker), text="……そうか")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block1, block2])]
    )

    extraction = Extractor().extract_story(story)[0]
    characters = extraction["characters"]

    assert len(characters) == 1
    assert characters[0]["evidenceIds"] == ["EP01_DLG0001", "EP01_MONO0001"]


def test_multiple_distinct_speakers_produce_multiple_candidates():
    block1 = _dialogue_block(
        "EP01_DLG0001",
        speaker={"speakerId": "CHAR_A", "speakerName": "A", "isResolved": True},
    )
    block2 = _dialogue_block(
        "EP01_DLG0002",
        speaker={"speakerId": "CHAR_B", "speakerName": "B", "isResolved": True},
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block1, block2])]
    )

    extraction = Extractor().extract_story(story)[0]
    ids = {c["id"] for c in extraction["characters"]}

    assert ids == {"EP01_CAND_CHAR001", "EP01_CAND_CHAR002"}


# ----------------------------------------------------------------
# 4. speakerIdなし/speakerNameのみのケース
# ----------------------------------------------------------------


def test_speaker_name_only_without_source_character_id():
    block = _dialogue_block(
        "EP01_DLG0001", speaker={"speakerName": "謎の声", "isResolved": False}
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["characters"][0]

    assert candidate["existingCharacterId"] is None
    assert candidate["sourceCharacterId"] is None
    assert candidate["nameCandidates"] == ["謎の声"]
    assert candidate["confidence"] == pytest.approx(0.5)


def test_speaker_missing_entirely_produces_no_candidate():
    # speakerキー自体が無いdialogue Blockはcandidateを生成しない
    block = {
        "id": "EP01_DLG0001",
        "type": "dialogue",
        "text": "話者不明",
        "source": {},
        "voice": {"hasVoice": None},
    }
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["characters"] == []


# ----------------------------------------------------------------
# 5. choice内の話者は対象外
# ----------------------------------------------------------------


def test_choice_nested_dialogue_speaker_is_excluded():
    inner = _dialogue_block(
        "EP01_DLG0001",
        speaker={"speakerId": "CHAR_A", "speakerName": "A", "isResolved": True},
    )
    choice_block = _choice_block("EP01_CHOICE001", "EP01_CHOICE001_OPT01", [inner])
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [choice_block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["characters"] == []


# ----------------------------------------------------------------
# 6. semantic validation / schema validation
# ----------------------------------------------------------------


def test_character_candidate_evidence_ids_pass_semantic_validation():
    speaker = {"speakerId": "CHAR_RAIN", "speakerName": "レイン", "isResolved": True}
    block = _dialogue_block("EP01_DLG0001", speaker=speaker)
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    issues = run_semantic_validation(extraction)
    errors = [i for i in issues if i.severity == "error"]

    assert not errors, [i.message for i in errors]


def test_character_candidate_output_matches_extraction_schema(extraction_validator):
    speaker = {
        "speakerName": "不明人物(ID:1)",
        "sourceCharacterId": "1",
        "isResolved": False,
    }
    block = _dialogue_block("EP01_DLG0001", speaker=speaker)
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    errors = list(extraction_validator.iter_errors(extraction))

    assert not errors, [e.message for e in errors]


# ----------------------------------------------------------------
# CLI: scripts/extract_story.py の出力がschema/semantic両方に通ること
# ----------------------------------------------------------------


def test_cli_extract_story_output_passes_schema_and_semantic_validation(tmp_path):
    speaker = {
        "speakerId": "CHAR_RAIN",
        "speakerName": "レイン",
        "sourceCharacterId": "26",
        "isResolved": True,
    }
    block1 = _dialogue_block("EP01_DLG0001", speaker=dict(speaker), text="こんにちは")
    block2 = _dialogue_block(
        "EP01_DLG0002",
        speaker={
            "speakerName": "不明人物(ID:2)",
            "sourceCharacterId": "2",
            "isResolved": False,
        },
        text="……",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block1, block2])]
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
    assert len(data["characters"]) == 2
