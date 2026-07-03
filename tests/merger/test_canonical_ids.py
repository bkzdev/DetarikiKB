"""
tests/merger/test_canonical_ids.py
agents/merger/canonical_ids.py (canonical ID policyのhelper/validation) の
テスト。

docs/architecture/06_AI/Canonical_ID_Policy.mdの方針通り、既存entityへの
canonical ID自動付与は行わないこと、canonicalIdの形式・重複・
unresolvedとの整合性がvalidationで検出されることを重点的に確認する。

実データ・data/extracted/生成物は使わず、本ファイル内で組み立てる自作の
最小fixtureのみを使う。
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator

from agents.merger import MergeEngine
from agents.merger.canonical_ids import (
    CANONICAL_ID_SOURCE_MANUAL_OVERRIDE,
    CANONICAL_ID_SOURCE_NONE,
    CANONICAL_ID_SOURCE_STRUCTURED_ID,
    CANONICAL_ID_SOURCE_UNKNOWN,
    build_canonical_id,
    classify_canonical_id_source,
    is_valid_canonical_id,
    sanitize_canonical_id_segment,
    validate_canonical_ids,
)
from agents.merger.character import build_character_entities

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
COLLECTION_SCHEMA_PATH = SCHEMAS_DIR / "merged_knowledge_collection.schema.json"
MERGE_SCRIPT = PROJECT_ROOT / "scripts" / "merge_extractions.py"
OVERRIDES_FIXTURES_DIR = (
    Path(__file__).parent.parent / "fixtures" / "merger" / "overrides"
)
VALID_OVERRIDES_FIXTURE = OVERRIDES_FIXTURES_DIR / "manual_overrides_valid.json"


def _entity(
    entity_id: str,
    entity_type: str,
    canonical_id: str | None,
    status: str = "merged",
    manual_overrides_applied: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": entity_id,
        "type": entity_type,
        "canonicalId": canonical_id,
        "status": status,
        "manualOverridesApplied": manual_overrides_applied or [],
    }


def _empty_entities() -> dict[str, list[dict[str, Any]]]:
    return {
        "characters": [],
        "locations": [],
        "organizations": [],
        "items": [],
        "lore": [],
        "events": [],
        "relationships": [],
        "timeline": [],
    }


# ----------------------------------------------------------------
# 1. build_canonical_id / sanitize_canonical_id_segment
# ----------------------------------------------------------------


def test_sanitize_canonical_id_segment_converts_to_safe_slug():
    assert sanitize_canonical_id_segment("赤城陽菜") != ""
    assert sanitize_canonical_id_segment("Akagi Hina") == "AKAGI_HINA"
    assert sanitize_canonical_id_segment("akagi-hina") == "AKAGI_HINA"


def test_build_canonical_id_produces_expected_prefix():
    assert build_canonical_id("character", "Akagi Hina") == "CHAR_AKAGI_HINA"
    assert build_canonical_id("organization", "Taisakuhan Honbu") == (
        "ORG_TAISAKUHAN_HONBU"
    )
    assert build_canonical_id("location", "Honbu") == "LOC_HONBU"


def test_build_canonical_id_rejects_unknown_entity_type():
    with pytest.raises(ValueError):
        build_canonical_id("not_a_real_type", "X")


# ----------------------------------------------------------------
# 2. is_valid_canonical_id
# ----------------------------------------------------------------


def test_valid_canonical_id_is_accepted():
    assert is_valid_canonical_id("CHAR_AKAGI_HINA") is True
    assert is_valid_canonical_id("ORG_TEST_ALPHA") is True


def test_invalid_canonical_id_formats_are_rejected():
    assert is_valid_canonical_id("") is False
    assert is_valid_canonical_id("char_akagi_hina") is False  # 小文字
    assert is_valid_canonical_id("AKAGI HINA") is False  # 空白
    assert is_valid_canonical_id("UNKNOWN_PREFIX_X") is False  # 未知prefix
    assert is_valid_canonical_id(None) is False


# ----------------------------------------------------------------
# 3. classify_canonical_id_source
# ----------------------------------------------------------------


def test_classify_structured_id_source():
    entity = _entity("CHAR_RAIN", "character", "CHAR_RAIN", status="merged")
    assert classify_canonical_id_source(entity) == CANONICAL_ID_SOURCE_STRUCTURED_ID


def test_classify_manual_override_source():
    entity = _entity(
        "UNRESOLVED_ORG_0001",
        "organization",
        "ORG_TEST_ALPHA",
        status="unresolved",
        manual_overrides_applied=["OVR_0003"],
    )
    assert classify_canonical_id_source(entity) == CANONICAL_ID_SOURCE_MANUAL_OVERRIDE


def test_classify_none_when_canonical_id_missing():
    entity = _entity("UNRESOLVED_CHAR_0001", "character", None, status="unresolved")
    assert classify_canonical_id_source(entity) == CANONICAL_ID_SOURCE_NONE


def test_classify_unknown_when_no_clear_signal():
    # statusはunresolvedなのにcanonicalIdがあり、manualOverridesAppliedも
    # 空 (validate_canonical_idsがwarningとして検出すべき疑わしいケース)
    entity = _entity(
        "UNRESOLVED_CHAR_0001", "character", "CHAR_SUSPICIOUS", status="unresolved"
    )
    assert classify_canonical_id_source(entity) == CANONICAL_ID_SOURCE_UNKNOWN


# ----------------------------------------------------------------
# 4. validate_canonical_ids: valid / invalid / duplicate / unresolved
# ----------------------------------------------------------------


def test_valid_canonical_ids_pass_validation():
    entities = _empty_entities()
    entities["characters"] = [_entity("CHAR_RAIN", "character", "CHAR_RAIN")]
    entities["organizations"] = [
        _entity("ORG_TAISAKUHAN", "organization", "ORG_TAISAKUHAN")
    ]

    result = validate_canonical_ids({"entities": entities})

    assert result.total_assigned == 2
    assert result.invalid_count == 0
    assert result.duplicate_count == 0
    assert result.warnings == []


def test_invalid_format_canonical_id_is_detected():
    entities = _empty_entities()
    entities["characters"] = [_entity("CHAR_RAIN", "character", "char_rain_lowercase")]

    result = validate_canonical_ids({"entities": entities})

    assert result.invalid_count == 1
    assert any("形式が不正" in w for w in result.warnings)


def test_prefix_mismatch_canonical_id_is_detected():
    entities = _empty_entities()
    # organization entityにCHAR_接頭辞のcanonicalIdが付いている (誤り)
    entities["organizations"] = [_entity("ORG_X", "organization", "CHAR_WRONG_PREFIX")]

    result = validate_canonical_ids({"entities": entities})

    assert result.invalid_count == 1
    assert any("接頭辞" in w for w in result.warnings)


def test_duplicate_canonical_id_within_same_type_is_detected():
    entities = _empty_entities()
    entities["characters"] = [
        _entity("CHAR_A_INSTANCE1", "character", "CHAR_DUP"),
        _entity("CHAR_A_INSTANCE2", "character", "CHAR_DUP"),
    ]

    result = validate_canonical_ids({"entities": entities})

    assert result.duplicate_count == 1
    assert any("CHAR_DUP" in w and "重複" in w for w in result.warnings)


def test_duplicate_canonical_id_across_types_is_detected():
    entities = _empty_entities()
    entities["characters"] = [_entity("CHAR_X", "character", "SHARED_ID")]
    entities["organizations"] = [_entity("ORG_X", "organization", "SHARED_ID")]

    result = validate_canonical_ids({"entities": entities})

    assert result.duplicate_count == 1
    assert any("複数のentity type" in w for w in result.warnings)


def test_unresolved_entity_with_canonical_id_produces_warning():
    entities = _empty_entities()
    entities["organizations"] = [
        _entity(
            "UNRESOLVED_ORG_0001",
            "organization",
            "ORG_TEST_ALPHA",
            status="unresolved",
        )
    ]

    result = validate_canonical_ids({"entities": entities})

    # 形式自体は妥当なのでinvalidにはしない (warningのみ)
    assert result.invalid_count == 0
    assert any("unresolved" in w for w in result.warnings)


def test_empty_canonical_ids_are_skipped_not_counted():
    entities = _empty_entities()
    entities["characters"] = [_entity("UNRESOLVED_CHAR_0001", "character", None)]

    result = validate_canonical_ids({"entities": entities})

    assert result.total_assigned == 0
    assert result.invalid_count == 0
    assert result.warnings == []


# ----------------------------------------------------------------
# 5. 名前だけcandidateからcanonicalIdが自動生成されないこと (回帰確認)
# ----------------------------------------------------------------


def _extraction_run() -> dict[str, Any]:
    return {
        "extractionVersion": "0.1.0",
        "extractionMethod": "rule_based",
        "modelProvider": None,
        "modelName": None,
        "promptVersion": None,
        "extractedAt": None,
        "parserCompatibilityAtExtraction": "compatible",
    }


def test_name_only_candidate_does_not_get_canonical_id():
    document = {
        "schemaVersion": "0.1",
        "documentType": "episode_extraction",
        "episodeId": "EP01",
        "storyId": "TEST_STORY",
        "storyCategory": "MAIN",
        "extractionRun": _extraction_run(),
        "evidenceIndex": {
            "EP01_DLG0001": {
                "sourceId": "EP01_DLG0001",
                "storyId": "TEST_STORY",
                "episodeId": "EP01",
                "sceneId": None,
                "confidence": 0.5,
            }
        },
        "characters": [
            {
                "id": "EP01_CAND_CHAR001",
                "type": "character_candidate",
                "sourceType": "script",
                "confidence": 0.5,
                "evidenceIds": ["EP01_DLG0001"],
                "extractionRun": _extraction_run(),
                "existingCharacterId": None,
                "sourceCharacterId": None,
                "nameCandidates": ["名無しの人物"],
                "fields": {},
            }
        ],
        "organizations": [],
        "locations": [],
        "items": [],
        "lore": [],
        "events": [],
        "relationships": [],
        "timelineCandidates": [],
        "extractionErrors": [],
    }

    entities = build_character_entities([("ep01.json", document)])

    assert len(entities) == 1
    entity = entities[0]
    assert entity["status"] == "unresolved"
    assert entity["canonicalId"] is None

    result = validate_canonical_ids(
        {"entities": {**_empty_entities(), "characters": entities}}
    )
    assert result.total_assigned == 0
    assert result.warnings == []


# ----------------------------------------------------------------
# 6. MergeEngine/CLI経由でreport.canonicalIdSummaryが出る
# ----------------------------------------------------------------


@pytest.fixture
def engine() -> MergeEngine:
    return MergeEngine()


@pytest.fixture
def collection_validator() -> Draft7Validator:
    with open(COLLECTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


def _write_document(tmp_path: Path, name: str, document: dict[str, Any]) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


def _document_with_resolved_character(episode_id: str) -> dict[str, Any]:
    return {
        "schemaVersion": "0.1",
        "documentType": "episode_extraction",
        "episodeId": episode_id,
        "storyId": "TEST_STORY",
        "storyCategory": "MAIN",
        "extractionRun": _extraction_run(),
        "evidenceIndex": {
            f"{episode_id}_DLG0001": {
                "sourceId": f"{episode_id}_DLG0001",
                "storyId": "TEST_STORY",
                "episodeId": episode_id,
                "sceneId": None,
                "confidence": 0.9,
            }
        },
        "characters": [
            {
                "id": f"{episode_id}_CAND_CHAR001",
                "type": "character_candidate",
                "sourceType": "script",
                "confidence": 0.9,
                "evidenceIds": [f"{episode_id}_DLG0001"],
                "extractionRun": _extraction_run(),
                "existingCharacterId": "CHAR_RAIN",
                "sourceCharacterId": None,
                "nameCandidates": ["レイン"],
                "fields": {},
            }
        ],
        "organizations": [],
        "locations": [],
        "items": [],
        "lore": [],
        "events": [],
        "relationships": [],
        "timelineCandidates": [],
        "extractionErrors": [],
    }


def test_report_canonical_id_summary_present_via_engine(engine, tmp_path):
    document = _document_with_resolved_character("EP01")
    path = _write_document(tmp_path, "ep01.json", document)

    collection = engine.merge_inputs([str(path)])

    summary = collection["report"]["canonicalIdSummary"]
    assert summary["totalAssigned"] == 1
    assert summary["invalidCount"] == 0
    assert summary["duplicateCount"] == 0


def test_schema_validates_with_canonical_id_summary(
    collection_validator, engine, tmp_path
):
    document = _document_with_resolved_character("EP01")
    path = _write_document(tmp_path, "ep01.json", document)

    collection = engine.merge_inputs([str(path)])
    errors = list(collection_validator.iter_errors(collection))
    assert not errors, [e.message for e in errors]
    assert "canonicalIdSummary" in collection["report"]


def test_cli_output_matches_collection_schema_with_canonical_id_summary(
    collection_validator, tmp_path
):
    document = _document_with_resolved_character("EP01")
    path = _write_document(tmp_path, "ep01.json", document)
    output_dir = tmp_path / "merge_preview"

    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(path),
            "--output",
            str(output_dir),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    output_file = output_dir / "merged_knowledge_collection.json"
    with open(output_file, encoding="utf-8") as f:
        data = json.load(f)

    errors = list(collection_validator.iter_errors(data))
    assert not errors, [e.message for e in errors]
    assert data["report"]["canonicalIdSummary"]["totalAssigned"] == 1


# ----------------------------------------------------------------
# 7. manual overrideでcanonicalIdを付けた場合にsummaryへ反映される
# ----------------------------------------------------------------


def test_manual_override_canonical_id_reflected_in_summary(
    collection_validator, tmp_path
):
    document = _document_with_resolved_character("EP01")
    path = _write_document(tmp_path, "ep01.json", document)
    output_dir = tmp_path / "merge_preview"

    # manual_overrides_valid.jsonのOVR_0003が
    # UNRESOLVED_ORG_0001 へcanonicalId: ORG_TEST_ALPHA を指定する
    # (organizationのcandidateがこの入力には無いため、対象entity自体は
    # 存在せずoverrideはskipされる。ここではCLIがoverride適用後の
    # collectionでcanonicalIdSummaryを再計算していること自体を確認する)
    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(path),
            "--output",
            str(output_dir),
            "--overrides",
            str(VALID_OVERRIDES_FIXTURE),
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    output_file = output_dir / "merged_knowledge_collection.json"
    with open(output_file, encoding="utf-8") as f:
        data = json.load(f)

    errors = list(collection_validator.iter_errors(data))
    assert not errors, [e.message for e in errors]
    # override適用後のcollectionに対してcanonicalIdSummaryが計算し直されて
    # いること (CHAR_RAINのcanonicalIdが引き続きtotalAssignedへ反映される)
    assert data["report"]["canonicalIdSummary"]["totalAssigned"] >= 1


def test_manual_override_setting_canonical_id_on_unresolved_entity_flagged():
    # organizationCandidateが無いUNRESOLVED_ORG_0001というidは実際には
    # merged collectionへ現れないため、ここではvalidate_canonical_ids単体を
    # 直接使い、overrides.pyが実際に書き込む形 (status: unresolvedのままの
    # entityへcanonicalId追加) を再現して確認する。
    entities = _empty_entities()
    entities["organizations"] = [
        _entity(
            "UNRESOLVED_ORG_0001",
            "organization",
            "ORG_TEST_ALPHA",
            status="unresolved",
            manual_overrides_applied=["OVR_0003"],
        )
    ]

    result = validate_canonical_ids({"entities": entities})

    assert result.total_assigned == 1
    assert result.invalid_count == 0
    assert any("unresolved" in w for w in result.warnings)
