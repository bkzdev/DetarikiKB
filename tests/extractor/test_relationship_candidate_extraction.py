"""
tests/extractor/test_relationship_candidate_extraction.py
agents/extractor/extractor.py の RelationshipCandidate 抽出 (rule-based) のテスト。

構造的に取得できる手がかり (Block上の明示的なrelationshipType+source/target
ペア、speakerAssignmentsの明示的なorganizationId/affiliation) のみを対象とし、
本文の自然文からの関係推定 (「友人らしい」「敵対しているらしい」等) は行わない。
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


@pytest.fixture
def extraction_validator() -> Draft7Validator:
    with open(EXTRACTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


# ----------------------------------------------------------------
# 1. Blockの明示的なrelationshipフィールドからの生成
# ----------------------------------------------------------------


def test_relationship_candidate_created_from_source_target_fields():
    block = _dialogue_block(
        "EP01_DLG0001",
        relationshipType="TRUSTS",
        sourceCandidate="CHAR_AKAGI_HINA",
        targetCandidate="CHAR_RAIN",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    relationships = extraction["relationships"]

    assert len(relationships) == 1
    candidate = relationships[0]
    assert candidate["type"] == "relationship_candidate"
    assert candidate["sourceType"] == "script"
    assert candidate["sourceCandidate"] == "CHAR_AKAGI_HINA"
    assert candidate["targetCandidate"] == "CHAR_RAIN"
    assert candidate["relationshipType"] == "TRUSTS"
    assert candidate["direction"] == "source_to_target"
    assert candidate["evidenceIds"] == ["EP01_DLG0001"]
    assert candidate["existingRelationshipId"] is None
    # source/targetは既に解決済みIDだが、relationshipId自体は無いのでunresolved扱い
    assert candidate["confidence"] == pytest.approx(0.5)


def test_relationship_candidate_created_from_subject_object_fields():
    block = _dialogue_block(
        "EP01_DLG0001",
        relationshipType="RELATED_TO",
        subjectId="CHAR_A",
        objectId="CHAR_B",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["relationships"][0]

    assert candidate["sourceCandidate"] == "CHAR_A"
    assert candidate["targetCandidate"] == "CHAR_B"
    assert candidate["relationshipType"] == "RELATED_TO"


def test_relationship_candidate_with_relationship_id_is_high_confidence():
    block = _dialogue_block(
        "EP01_DLG0001",
        relationshipId="REL_AKAGI_RAIN_0001",
        relationshipType="TRUSTS",
        sourceCandidate="CHAR_AKAGI_HINA",
        targetCandidate="CHAR_RAIN",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["relationships"][0]

    assert candidate["existingRelationshipId"] == "REL_AKAGI_RAIN_0001"
    assert candidate["confidence"] == pytest.approx(0.9)


def test_relationship_candidate_respects_explicit_direction():
    block = _dialogue_block(
        "EP01_DLG0001",
        relationshipType="TRUSTS",
        sourceCandidate="CHAR_A",
        targetCandidate="CHAR_B",
        direction="bidirectional",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["relationships"][0]["direction"] == "bidirectional"


def test_relationship_candidate_invalid_direction_falls_back_to_default():
    block = _dialogue_block(
        "EP01_DLG0001",
        relationshipType="TRUSTS",
        sourceCandidate="CHAR_A",
        targetCandidate="CHAR_B",
        direction="sideways",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["relationships"][0]["direction"] == "source_to_target"


# ----------------------------------------------------------------
# 2. 同一source+target+relationshipTypeの統合
# ----------------------------------------------------------------


def test_same_source_target_type_merges_into_one_candidate():
    block1 = _dialogue_block(
        "EP01_DLG0001",
        relationshipType="TRUSTS",
        sourceCandidate="CHAR_A",
        targetCandidate="CHAR_B",
    )
    block2 = _dialogue_block(
        "EP01_DLG0002",
        relationshipType="TRUSTS",
        sourceCandidate="CHAR_A",
        targetCandidate="CHAR_B",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block1, block2])]
    )

    extraction = Extractor().extract_story(story)[0]
    relationships = extraction["relationships"]

    assert len(relationships) == 1
    assert relationships[0]["evidenceIds"] == ["EP01_DLG0001", "EP01_DLG0002"]


def test_different_relationship_type_produces_separate_candidate():
    block1 = _dialogue_block(
        "EP01_DLG0001",
        relationshipType="TRUSTS",
        sourceCandidate="CHAR_A",
        targetCandidate="CHAR_B",
    )
    block2 = _dialogue_block(
        "EP01_DLG0002",
        relationshipType="APPEARS_WITH",
        sourceCandidate="CHAR_A",
        targetCandidate="CHAR_B",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block1, block2])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert len(extraction["relationships"]) == 2


# ----------------------------------------------------------------
# 3. relationship情報が無いBlockからは生成されない / 自然文からの推定はしない
# ----------------------------------------------------------------


def test_block_without_relationship_fields_produces_no_candidate():
    block = _dialogue_block("EP01_DLG0001")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["relationships"] == []


def test_natural_language_hints_do_not_produce_relationship_candidate():
    # 本文中に「友人」「敵対」といった関係を示唆する語があっても、
    # 明示的なrelationship系フィールドが無ければ生成しない
    block = _dialogue_block(
        "EP01_DLG0001",
        text="レインとはずっと友人らしいし、対策班とは敵対しているらしい",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["relationships"] == []


def test_self_reference_block_does_not_produce_candidate():
    block = _dialogue_block(
        "EP01_DLG0001",
        relationshipType="RELATED_TO",
        sourceCandidate="CHAR_A",
        targetCandidate="CHAR_A",
    )
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])]
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["relationships"] == []


# ----------------------------------------------------------------
# 4. speakerAssignmentsからのCharacter -> Organization 所属候補
# ----------------------------------------------------------------


def test_membership_candidate_from_resolved_organization_id():
    speaker_assignments = [
        {
            "slot": "1",
            "speakerId": "CHAR_RAIN",
            "organizationId": "ORG_TAISAKUHAN",
        }
    ]
    block = _dialogue_block("EP01_DLG0001")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])], speaker_assignments
    )

    extraction = Extractor().extract_story(story)[0]
    relationships = extraction["relationships"]

    assert len(relationships) == 1
    candidate = relationships[0]
    assert candidate["sourceCandidate"] == "CHAR_RAIN"
    assert candidate["targetCandidate"] == "ORG_TAISAKUHAN"
    assert candidate["relationshipType"] == "MEMBER_OF"
    assert candidate["confidence"] == pytest.approx(0.9)
    assert candidate["evidenceIds"] == ["EP01"]
    assert "EP01" in extraction["evidenceIndex"]


def test_membership_candidate_from_affiliation_name_only_is_lower_confidence():
    speaker_assignments = [
        {"slot": "1", "sourceCharacterId": "26", "affiliation": "異形生物対策班"}
    ]
    block = _dialogue_block("EP01_DLG0001")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])], speaker_assignments
    )

    extraction = Extractor().extract_story(story)[0]
    candidate = extraction["relationships"][0]

    assert candidate["sourceCandidate"] == "26"
    assert candidate["targetCandidate"] == "異形生物対策班"
    assert candidate["relationshipType"] == "AFFILIATED_WITH"
    assert candidate["confidence"] == pytest.approx(0.5)


def test_assignment_without_character_or_organization_produces_no_candidate():
    speaker_assignments = [{"slot": "1", "organizationId": "ORG_TAISAKUHAN"}]
    block = _dialogue_block("EP01_DLG0001")
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])], speaker_assignments
    )

    extraction = Extractor().extract_story(story)[0]
    assert extraction["relationships"] == []


# ----------------------------------------------------------------
# 5. CharacterCandidate / OrganizationCandidateとの共存
# ----------------------------------------------------------------


def test_relationship_coexists_with_character_and_organization_candidates():
    speaker_assignments = [
        {
            "slot": "1",
            "sourceCharacterId": "26",
            "speakerId": "CHAR_RAIN",
            "speakerName": "レイン",
            "organizationId": "ORG_TAISAKUHAN",
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
    story = _build_normalized_story(
        "EP01", "TEST_STORY", [_scene("EP01_SC001", [block])], speaker_assignments
    )

    extraction = Extractor().extract_story(story)[0]

    assert len(extraction["characters"]) == 1
    assert len(extraction["organizations"]) == 1
    assert len(extraction["relationships"]) == 1
    assert extraction["relationships"][0]["relationshipType"] == "MEMBER_OF"


# ----------------------------------------------------------------
# 6. schema validation / semantic validation
# ----------------------------------------------------------------


def test_relationship_output_matches_extraction_schema(extraction_validator):
    block_relationship = _dialogue_block(
        "EP01_DLG0001",
        relationshipType="TRUSTS",
        sourceCandidate="CHAR_A",
        targetCandidate="CHAR_B",
    )
    speaker_assignments = [
        {"slot": "1", "speakerId": "CHAR_RAIN", "organizationId": "ORG_TAISAKUHAN"}
    ]
    story = _build_normalized_story(
        "EP01",
        "TEST_STORY",
        [_scene("EP01_SC001", [block_relationship])],
        speaker_assignments,
    )

    extraction = Extractor().extract_story(story)[0]
    errors = list(extraction_validator.iter_errors(extraction))

    assert not errors, [e.message for e in errors]


def test_relationship_passes_semantic_validation():
    block_relationship = _dialogue_block(
        "EP01_DLG0001",
        relationshipType="TRUSTS",
        sourceCandidate="CHAR_A",
        targetCandidate="CHAR_B",
    )
    speaker_assignments = [
        {"slot": "1", "speakerId": "CHAR_RAIN", "organizationId": "ORG_TAISAKUHAN"}
    ]
    story = _build_normalized_story(
        "EP01",
        "TEST_STORY",
        [_scene("EP01_SC001", [block_relationship])],
        speaker_assignments,
    )

    extraction = Extractor().extract_story(story)[0]
    issues = run_semantic_validation(extraction)
    errors = [i for i in issues if i.severity == "error"]

    assert not errors, [i.message for i in errors]


# ----------------------------------------------------------------
# CLI: scripts/extract_story.py の出力がschema/semantic両方に通ること
# ----------------------------------------------------------------


def test_cli_extract_story_output_passes_schema_and_semantic_validation(tmp_path):
    block_relationship = _dialogue_block(
        "EP01_DLG0001",
        relationshipType="TRUSTS",
        sourceCandidate="CHAR_A",
        targetCandidate="CHAR_B",
    )
    speaker_assignments = [
        {"slot": "1", "speakerId": "CHAR_RAIN", "organizationId": "ORG_TAISAKUHAN"}
    ]
    story = _build_normalized_story(
        "EP01",
        "TEST_STORY",
        [_scene("EP01_SC001", [block_relationship])],
        speaker_assignments,
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
    assert len(data["relationships"]) == 2
