"""
tests/extractor/test_extractor_skeleton.py
agents/extractor の最小skeleton (LLM呼び出しなし) のテスト。

Normalized Story JSONは、実スクリプトではなくStoryParserで生成した
小さい自作フィクスチャ (インラインスクリプト) だけを使う。
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator

from agents.extractor import Extractor
from agents.parser.normalizer import Normalizer
from agents.parser.parser import StoryParser

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXTRACTION_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "extraction.schema.json"
EXTRACT_SCRIPT = PROJECT_ROOT / "scripts" / "extract_story.py"


def _build_story_json(
    script: str, story_id: str, category: str = "MAIN"
) -> dict[str, Any]:
    parser = StoryParser()
    parse_result = parser.parse_text(script, source_file="test_extractor_script")
    normalizer = Normalizer(
        story_id=story_id,
        story_category=category,
        source_file="test_extractor_script",
    )
    return normalizer.normalize(parse_result)


@pytest.fixture
def extraction_validator() -> Draft7Validator:
    assert EXTRACTION_SCHEMA_PATH.exists(), (
        f"Schema not found: {EXTRACTION_SCHEMA_PATH}"
    )
    with open(EXTRACTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


@pytest.fixture
def simple_story_json() -> dict[str, Any]:
    script = """$num0 = 26
@ScenarioCos 1 26
@ChTalk 0
これはテスト用の会話です。
msg
そしてナレーション。
"""
    return _build_story_json(script, story_id="TEST_EXTRACT_001")


@pytest.fixture
def choice_story_json() -> dict[str, Any]:
    script = """branch 選択肢1 選択肢2
#if $branch
@ChTalk 0
ルート1
#else
@ChTalk 0
ルート2
#endif
"""
    return _build_story_json(script, story_id="TEST_EXTRACT_002")


def _all_blocks(story_json: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        block
        for episode in story_json["episodes"]
        for scene in episode["scenes"]
        for block in scene["blocks"]
    ]


def test_extract_story_returns_one_extraction_per_episode(simple_story_json):
    extractions = Extractor().extract_story(simple_story_json)
    assert len(extractions) == len(simple_story_json["episodes"])


def test_extract_episode_basic_fields(simple_story_json):
    extraction = Extractor().extract_story(simple_story_json)[0]
    episode = simple_story_json["episodes"][0]

    assert extraction["schemaVersion"] == "0.1"
    assert extraction["documentType"] == "episode_extraction"
    assert extraction["episodeId"] == episode["episodeId"]
    assert extraction["storyId"] == simple_story_json["storyId"]
    assert extraction["storyCategory"] == simple_story_json["storyCategory"]


def test_extract_episode_candidates_are_empty(simple_story_json):
    extraction = Extractor().extract_story(simple_story_json)[0]

    for key in (
        "characters",
        "organizations",
        "locations",
        "items",
        "lore",
        "events",
        "relationships",
        "timelineCandidates",
        "extractionErrors",
    ):
        assert extraction[key] == []


def test_extraction_run_has_no_llm_values_yet(simple_story_json):
    # LLM呼び出しは未実装のため、extractionMethodはrule_based固定
    # provider/model/prompt/extractedAtはNoneのまま
    extraction = Extractor().extract_story(simple_story_json)[0]
    run = extraction["extractionRun"]

    assert run["extractionMethod"] == "rule_based"
    assert run["modelProvider"] is None
    assert run["modelName"] is None
    assert run["promptVersion"] is None
    assert run["extractedAt"] is None


def test_evidence_index_contains_dialogue_and_narration(simple_story_json):
    extraction = Extractor().extract_story(simple_story_json)[0]
    block_types_by_id = {b["id"]: b["type"] for b in _all_blocks(simple_story_json)}

    assert extraction["evidenceIndex"], "evidenceIndexが空であってはならない"
    for source_id in extraction["evidenceIndex"]:
        assert block_types_by_id[source_id] in {
            "dialogue",
            "monologue",
            "narration",
            "choice",
        }

    dialogue_ids = [bid for bid, t in block_types_by_id.items() if t == "dialogue"]
    narration_ids = [bid for bid, t in block_types_by_id.items() if t == "narration"]
    assert dialogue_ids and all(
        bid in extraction["evidenceIndex"] for bid in dialogue_ids
    )
    assert narration_ids and all(
        bid in extraction["evidenceIndex"] for bid in narration_ids
    )


def test_evidence_index_excludes_stage_direction_and_unknown(simple_story_json):
    extraction = Extractor().extract_story(simple_story_json)[0]

    excluded_ids = [
        b["id"]
        for b in _all_blocks(simple_story_json)
        if b["type"] in {"stage_direction", "unknown"}
    ]
    for block_id in excluded_ids:
        assert block_id not in extraction["evidenceIndex"]


def test_evidence_ref_structure(simple_story_json):
    extraction = Extractor().extract_story(simple_story_json)[0]
    episode_id = extraction["episodeId"]
    story_id = extraction["storyId"]

    for source_id, ref in extraction["evidenceIndex"].items():
        assert ref["sourceId"] == source_id
        assert ref["storyId"] == story_id
        assert ref["episodeId"] == episode_id
        assert 0.0 <= ref["confidence"] <= 1.0


def test_choice_option_blocks_are_included_in_evidence_index(choice_story_json):
    extraction = Extractor().extract_story(choice_story_json)[0]

    inner_ids = [
        inner["id"]
        for block in _all_blocks(choice_story_json)
        if block["type"] == "choice"
        for option in block.get("options", [])
        for inner in option.get("blocks", [])
        if inner["type"] in {"dialogue", "monologue", "narration"}
    ]

    assert inner_ids, "choiceのoption内にdialogue Blockがあるはず"
    for block_id in inner_ids:
        assert block_id in extraction["evidenceIndex"]


def test_extraction_output_matches_schema(extraction_validator, simple_story_json):
    extraction = Extractor().extract_story(simple_story_json)[0]
    errors = list(extraction_validator.iter_errors(extraction))
    assert not errors, f"Unexpected validation errors: {[e.message for e in errors]}"


def test_choice_extraction_output_matches_schema(
    extraction_validator, choice_story_json
):
    extraction = Extractor().extract_story(choice_story_json)[0]
    errors = list(extraction_validator.iter_errors(extraction))
    assert not errors, f"Unexpected validation errors: {[e.message for e in errors]}"


def test_cli_generates_valid_extraction_file(tmp_path, simple_story_json):
    normalized_path = tmp_path / "normalized.json"
    with open(normalized_path, "w", encoding="utf-8") as f:
        json.dump(simple_story_json, f, ensure_ascii=False)

    output_dir = tmp_path / "extracted"

    result = subprocess.run(
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
    assert result.returncode == 0, result.stderr

    episode_id = simple_story_json["episodes"][0]["episodeId"]
    output_file = output_dir / f"{episode_id}.extraction.json"
    assert output_file.exists()

    with open(output_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data["documentType"] == "episode_extraction"


def test_cli_reports_missing_input_file(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(EXTRACT_SCRIPT),
            "--input",
            str(tmp_path / "does_not_exist.json"),
            "--output",
            str(tmp_path / "extracted"),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
