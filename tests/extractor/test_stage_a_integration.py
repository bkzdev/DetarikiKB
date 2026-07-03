"""
tests/extractor/test_stage_a_integration.py
Stage A Extraction 統合テスト。

実装済みの全Candidate種別 (Character / Location / Organization / Item /
Lore / Event / Relationship / Timeline) が、1つのepisode_extraction内で
共存し、schema validation・semantic validation・CLI連携すべてに通ることを
確認する横断テスト。

各Candidate個別の詳細な挙動は、種別ごとのテストファイル
(test_character_candidate_extraction.py 等) が担う。本ファイルは
「全種が同時に出ても壊れない」という統合面のみを確認する。

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

# 全8種のCandidate配列キー (schemas/extraction.schema.md §3.2 / validator.py
# CANDIDATE_ARRAY_KEYS のうち、rule-basedで生成される候補配列)。
ALL_CANDIDATE_ARRAY_KEYS = (
    "characters",
    "locations",
    "organizations",
    "items",
    "lore",
    "events",
    "relationships",
    "timelineCandidates",
)


def _build_all_candidate_story(
    episode_id: str = "EP01", story_id: str = "TEST_STORY"
) -> dict[str, Any]:
    """全8種のCandidateを1エピソードで誘発する最小フィクスチャを組み立てる。

    - character: dialogueのspeaker (slot経由でspeakerAssignmentsのCHAR_RAINに解決)
    - organization: block organizationId/organizationName
    - location: Scene.location
    - item: block itemId/itemName
    - lore: block loreId/termName
    - event: block eventId/eventName
    - relationship: block relationshipType + sourceCandidate/targetCandidate
                    (加えて speakerAssignments の organizationId から MEMBER_OF)
    - timeline: block timelineId + episode.metadata.canonicalOrder
    """
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
        "relationshipType": "TRUSTS",
        "sourceCandidate": "CHAR_AKAGI_HINA",
        "targetCandidate": "CHAR_RAIN",
        "timelineId": "TL_ARC1",
    }
    scene = {
        "sceneId": "EP01_SC001",
        "sceneNumber": 1,
        "location": {"locationId": "LOC_HQ", "locationName": "本部"},
        "blocks": [block],
    }
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
        "source": {"sourceFile": "test.dec", "sourceFormat": "manual"},
        "episodes": [
            {
                "episodeId": episode_id,
                "episodeNumber": 1,
                "metadata": {"canonicalOrder": 1},
                "speakerAssignments": speaker_assignments,
                "scenes": [scene],
            }
        ],
    }


@pytest.fixture
def extraction_validator() -> Draft7Validator:
    with open(EXTRACTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


# ----------------------------------------------------------------
# 1. 全8種が共存する
# ----------------------------------------------------------------


def test_all_eight_candidate_types_present_in_one_episode():
    extraction = Extractor().extract_story(_build_all_candidate_story())[0]

    for key in ALL_CANDIDATE_ARRAY_KEYS:
        assert extraction[key], f"{key} が空です (全種共存を期待)"


def test_all_candidate_ids_are_unique_across_types():
    extraction = Extractor().extract_story(_build_all_candidate_story())[0]

    ids = [
        candidate["id"]
        for key in ALL_CANDIDATE_ARRAY_KEYS
        for candidate in extraction[key]
    ]
    assert len(ids) == len(set(ids)), f"candidate idが重複しています: {ids}"


def test_all_candidate_envelopes_are_consistent():
    extraction = Extractor().extract_story(_build_all_candidate_story())[0]
    document_run = extraction["extractionRun"]

    for key in ALL_CANDIDATE_ARRAY_KEYS:
        for candidate in extraction[key]:
            # CandidateEnvelope 共通フィールド (Extraction_Result_Schema.md §4.1)
            assert candidate["id"]
            assert candidate["type"]
            assert candidate["sourceType"] in {
                "official",
                "script",
                "ai_extracted",
                "ai_inferred",
                "manual",
                "unknown",
            }
            assert 0.0 <= candidate["confidence"] <= 1.0
            assert candidate["evidenceIds"], "evidenceIdsは最低1件必須"
            # 候補側extractionRunはdocument側の複製
            assert candidate["extractionRun"] == document_run


# ----------------------------------------------------------------
# 2. evidenceIdsの整合性 (全candidateの根拠がevidenceIndexに実在する)
# ----------------------------------------------------------------


def test_all_candidate_evidence_ids_exist_in_evidence_index():
    extraction = Extractor().extract_story(_build_all_candidate_story())[0]
    evidence_index = extraction["evidenceIndex"]

    for key in ALL_CANDIDATE_ARRAY_KEYS:
        for candidate in extraction[key]:
            for evidence_id in candidate["evidenceIds"]:
                assert evidence_id in evidence_index, (
                    f"{key}/{candidate['id']} の evidenceId "
                    f"'{evidence_id}' が evidenceIndex に存在しません"
                )


# ----------------------------------------------------------------
# 3. schema validation / semantic validation
# ----------------------------------------------------------------


def test_all_candidate_types_pass_schema_validation(extraction_validator):
    extraction = Extractor().extract_story(_build_all_candidate_story())[0]
    errors = list(extraction_validator.iter_errors(extraction))
    assert not errors, [e.message for e in errors]


def test_all_candidate_types_pass_semantic_validation():
    extraction = Extractor().extract_story(_build_all_candidate_story())[0]
    issues = run_semantic_validation(extraction)
    errors = [i for i in issues if i.severity == "error"]
    assert not errors, [i.message for i in errors]


# ----------------------------------------------------------------
# 4. CLI連携: extract_story.py --validate → validate_extraction_json.py --semantic
# ----------------------------------------------------------------


def test_cli_chain_extract_then_validate_semantic(tmp_path):
    story = _build_all_candidate_story()

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
    for key in ALL_CANDIDATE_ARRAY_KEYS:
        assert data[key], f"CLI出力の {key} が空です"
