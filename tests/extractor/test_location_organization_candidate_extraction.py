"""
tests/extractor/test_location_organization_candidate_extraction.py
agents/extractor/extractor.py の LocationCandidate / OrganizationCandidate
抽出 (rule-based) のテスト。

構造的に取得できる手がかり (Scene.location、stage_direction(background)、
明示的なorganizationId/organizationName/affiliationフィールド) のみを対象とし、
本文の自然文からの推定は行わない。LLM呼び出しは行わない。

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
    organization_id: str | None = None,
    organization_name: str | None = None,
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "id": block_id,
        "type": "dialogue",
        "text": text,
        "source": {},
        "voice": {"hasVoice": None},
    }
    if organization_id is not None:
        block["organizationId"] = organization_id
    if organization_name is not None:
        block["organizationName"] = organization_name
    return block


def _background_block(
    block_id: str,
    normalized_command: str | None = None,
    location_id: str | None = None,
    location_name: str | None = None,
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "id": block_id,
        "type": "stage_direction",
        "source": {},
        "directionType": "background",
    }
    if normalized_command is not None:
        block["normalizedCommand"] = normalized_command
    if location_id is not None:
        block["locationId"] = location_id
    if location_name is not None:
        block["locationName"] = location_name
    return block


@pytest.fixture
def extraction_validator() -> Draft7Validator:
    with open(EXTRACTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


# ----------------------------------------------------------------
# 1. Scene.locationからの生成
# ----------------------------------------------------------------


def test_location_candidate_created_from_scene_location_name_only():
    story = _build_normalized_story(
        "EP01",
        "TEST_STORY",
        [
            _scene(
                "EP01_SC001", [], location={"locationId": None, "locationName": "本部"}
            )
        ],
    )

    extraction = Extractor().extract_story(story)[0]
    locations = extraction["locations"]

    assert len(locations) == 1
    candidate = locations[0]
    assert candidate["existingLocationId"] is None
    assert candidate["nameCandidates"] == ["本部"]
    assert candidate["sceneRefs"] == ["EP01_SC001"]
    assert candidate["evidenceIds"] == ["EP01_SC001"]
    assert candidate["confidence"] == pytest.approx(0.5)
    assert candidate["type"] == "location_candidate"
    assert candidate["sourceType"] == "script"


def test_location_candidate_created_from_scene_location_with_id():
    story = _build_normalized_story(
        "EP01",
        "TEST_STORY",
        [
            _scene(
                "EP01_SC001",
                [],
                location={"locationId": "LOC_HQ", "locationName": "本部"},
            )
        ],
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["locations"][0]

    assert candidate["existingLocationId"] == "LOC_HQ"
    assert candidate["confidence"] == pytest.approx(0.9)


def test_location_candidate_created_from_background_stage_direction():
    block = _background_block("EP01_STAGE0001", normalized_command="bg_school")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["locations"][0]

    assert candidate["nameCandidates"] == ["bg_school"]
    assert candidate["evidenceIds"] == ["EP01_STAGE0001"]
    assert candidate["sceneRefs"] == ["EP01_SC001"]
    assert candidate["existingLocationId"] is None
    assert candidate["confidence"] == pytest.approx(0.5)


def test_non_background_stage_direction_does_not_produce_location_candidate():
    block = {
        "id": "EP01_STAGE0001",
        "type": "stage_direction",
        "source": {},
        "directionType": "bgm",
        "normalizedCommand": "bgm_calm",
    }
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["locations"] == []


# ----------------------------------------------------------------
# 2. 同一locationの統合
# ----------------------------------------------------------------


def test_same_location_across_scenes_merges_into_one_candidate():
    scene1 = _scene(
        "EP01_SC001", [], location={"locationId": None, "locationName": "本部"}
    )
    scene2 = _scene(
        "EP01_SC002", [], location={"locationId": None, "locationName": "本部"}
    )
    story = _build_normalized_story("EP01", "TEST_STORY", [scene1, scene2])

    extraction = Extractor().extract_story(story)[0]
    locations = extraction["locations"]

    assert len(locations) == 1
    candidate = locations[0]
    assert candidate["evidenceIds"] == ["EP01_SC001", "EP01_SC002"]
    assert candidate["sceneRefs"] == ["EP01_SC001", "EP01_SC002"]


def test_evidence_index_contains_scene_and_stage_direction_evidence():
    scene_block = _background_block("EP01_STAGE0001", normalized_command="bg_school")
    scene = _scene(
        "EP01_SC001",
        [scene_block],
        location={"locationId": None, "locationName": "本部"},
    )
    story = _build_normalized_story("EP01", "TEST_STORY", [scene])

    extraction = Extractor().extract_story(story)[0]

    assert "EP01_SC001" in extraction["evidenceIndex"]
    assert "EP01_STAGE0001" in extraction["evidenceIndex"]


# ----------------------------------------------------------------
# 3. 明示的なorganization情報からの生成
# ----------------------------------------------------------------


def test_organization_candidate_created_from_block_fields():
    block = _dialogue_block(
        "EP01_DLG0001",
        organization_id="ORG_TAISAKUHAN",
        organization_name="異形生物対策班",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    organizations = extraction["organizations"]

    assert len(organizations) == 1
    candidate = organizations[0]
    assert candidate["existingOrganizationId"] == "ORG_TAISAKUHAN"
    assert candidate["nameCandidates"] == ["異形生物対策班"]
    assert candidate["evidenceIds"] == ["EP01_DLG0001"]
    assert candidate["confidence"] == pytest.approx(0.9)
    assert candidate["type"] == "organization_candidate"
    assert candidate["sourceType"] == "script"


def test_organization_candidate_created_from_speaker_assignments():
    speaker_assignments = [
        {"slot": "1", "sourceCharacterId": "26", "affiliation": "異形生物対策班"}
    ]
    block = _dialogue_block("EP01_DLG0001")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])], speaker_assignments
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["organizations"][0]

    assert candidate["existingOrganizationId"] is None
    assert candidate["nameCandidates"] == ["異形生物対策班"]
    assert candidate["evidenceIds"] == ["EP01"]
    assert candidate["confidence"] == pytest.approx(0.5)
    assert "EP01" in extraction["evidenceIndex"]


def test_same_organization_from_block_and_assignment_merges():
    speaker_assignments = [{"slot": "1", "organizationName": "異形生物対策班"}]
    block = _dialogue_block("EP01_DLG0001", organization_name="異形生物対策班")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])], speaker_assignments
    )

    extraction = Extractor().extract_story(story)[0]
    organizations = extraction["organizations"]

    assert len(organizations) == 1
    assert set(organizations[0]["evidenceIds"]) == {"EP01_DLG0001", "EP01"}


def test_block_without_organization_fields_produces_no_candidate():
    block = _dialogue_block("EP01_DLG0001")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["organizations"] == []


# ----------------------------------------------------------------
# 4. CharacterCandidateとの共存
# ----------------------------------------------------------------


def test_character_location_organization_candidates_coexist():
    # 話者・場所・組織それぞれ1件ずつが独立に生成され、共存できることを確認する。
    # organizationはBlock側のみに付与し (assignment側には付与しない)、
    # id有無で識別キーが割れて2件に分裂しないようにする。
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
        "text": "作戦開始",
        "source": {},
        "speaker": {"slot": "1", "isResolved": False},
        "voice": {"hasVoice": None},
        "organizationId": "ORG_TAISAKUHAN",
        "organizationName": "異形生物対策班",
    }
    scene = _scene(
        "EP01_SC001", [block], location={"locationId": "LOC_HQ", "locationName": "本部"}
    )
    story = _build_normalized_story("EP01", "TEST_STORY", [scene], speaker_assignments)

    extraction = Extractor().extract_story(story)[0]

    assert len(extraction["characters"]) == 1
    assert extraction["characters"][0]["existingCharacterId"] == "CHAR_RAIN"
    assert len(extraction["locations"]) == 1
    assert extraction["locations"][0]["existingLocationId"] == "LOC_HQ"
    assert len(extraction["organizations"]) == 1
    assert extraction["organizations"][0]["existingOrganizationId"] == "ORG_TAISAKUHAN"


# ----------------------------------------------------------------
# 5. semantic validation / schema validation
# ----------------------------------------------------------------


def test_location_and_organization_evidence_pass_semantic_validation():
    bg_block = _background_block("EP01_STAGE0001", normalized_command="bg_school")
    org_block = _dialogue_block(
        "EP01_DLG0001",
        organization_id="ORG_TAISAKUHAN",
        organization_name="異形生物対策班",
    )
    speaker_assignments = [{"slot": "1", "affiliation": "別動隊"}]
    scene = _scene(
        "EP01_SC001",
        [bg_block, org_block],
        location={"locationId": None, "locationName": "本部"},
    )
    story = _build_normalized_story("EP01", "TEST_STORY", [scene], speaker_assignments)

    extraction = Extractor().extract_story(story)[0]
    issues = run_semantic_validation(extraction)
    errors = [i for i in issues if i.severity == "error"]

    assert not errors, [i.message for i in errors]


def test_location_and_organization_output_matches_extraction_schema(
    extraction_validator,
):
    bg_block = _background_block(
        "EP01_STAGE0001", location_id="LOC_SCHOOL", location_name="学園"
    )
    org_block = _dialogue_block("EP01_DLG0001", organization_name="生徒会")
    scene = _scene("EP01_SC001", [bg_block, org_block])
    story = _build_normalized_story("EP01", "TEST_STORY", [scene])

    extraction = Extractor().extract_story(story)[0]
    errors = list(extraction_validator.iter_errors(extraction))

    assert not errors, [e.message for e in errors]


# ----------------------------------------------------------------
# CLI: scripts/extract_story.py の出力がschema/semantic両方に通ること
# ----------------------------------------------------------------


def test_cli_extract_story_output_passes_schema_and_semantic_validation(tmp_path):
    bg_block = _background_block("EP01_STAGE0001", normalized_command="bg_school")
    org_block = _dialogue_block(
        "EP01_DLG0001",
        organization_id="ORG_TAISAKUHAN",
        organization_name="異形生物対策班",
    )
    scene = _scene(
        "EP01_SC001",
        [bg_block, org_block],
        location={"locationId": "LOC_HQ", "locationName": "本部"},
    )
    story = _build_normalized_story("EP01", "TEST_STORY", [scene])

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
    # bg_school (stage_direction) と 本部 (Scene.location) は別のLocationCandidate
    assert len(data["locations"]) == 2
    assert len(data["organizations"]) == 1
