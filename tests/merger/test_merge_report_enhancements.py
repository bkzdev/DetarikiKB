"""
tests/merger/test_merge_report_enhancements.py
agents/merger merge report強化 (feature/merge-report-enhancements) のテスト。

複数episode_extractionを統合したときに、何が入力され、何がvalid/invalid/
skippedになり、どのcandidateから何件のmerged entityが作られ、どの
warning/conflict/manual overrideが発生したかをreport経由で把握できることを
確認する。

実データ・data/extracted/生成物は使わず、本ファイル内で組み立てる自作の
最小episode_extraction fixtureのみを使う (RPTEST_* という合成ID)。
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator

from agents.merger import MergeEngine

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMAS_DIR = PROJECT_ROOT / "schemas"
COLLECTION_SCHEMA_PATH = SCHEMAS_DIR / "merged_knowledge_collection.schema.json"
MERGE_SCRIPT = PROJECT_ROOT / "scripts" / "merge_extractions.py"
OVERRIDES_FIXTURES_DIR = (
    Path(__file__).parent.parent / "fixtures" / "merger" / "overrides"
)
VALID_OVERRIDES_FIXTURE = OVERRIDES_FIXTURES_DIR / "manual_overrides_valid.json"


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


def _evidence_ref(source_id: str, episode_id: str) -> dict[str, Any]:
    return {
        "sourceId": source_id,
        "storyId": "RPTEST_STORY",
        "episodeId": episode_id,
        "sceneId": None,
        "confidence": 0.9,
    }


def _character_candidate(
    candidate_id: str,
    evidence_id: str,
    name_candidates: list[str],
    existing_character_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "character_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": [evidence_id],
        "extractionRun": _extraction_run(),
        "existingCharacterId": existing_character_id,
        "sourceCharacterId": None,
        "nameCandidates": name_candidates,
        "fields": {},
    }


def _relationship_candidate(
    candidate_id: str,
    evidence_id: str,
    source_candidate: str,
    target_candidate: str,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "relationship_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": [evidence_id],
        "extractionRun": _extraction_run(),
        "sourceCandidate": source_candidate,
        "targetCandidate": target_candidate,
        "relationshipType": "MEMBER_OF",
        "direction": "source_to_target",
        "temporalNote": None,
        "fields": {},
    }


def _timeline_candidate(
    candidate_id: str,
    evidence_id: str,
    source_timeline_id: str,
    order_value: float,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "type": "timeline_candidate",
        "sourceType": "script",
        "confidence": 0.9,
        "evidenceIds": [evidence_id],
        "extractionRun": _extraction_run(),
        "kind": "explicit_order",
        "scope": "block",
        "relativeTo": None,
        "relation": None,
        "sourceTimelineId": source_timeline_id,
        "nameCandidates": [],
        "orderValue": order_value,
        "orderField": "orderValue",
        "markerType": None,
        "fields": {},
    }


def _episode_extraction(
    episode_id: str,
    evidence_ids: list[str],
    characters: list[dict[str, Any]] | None = None,
    relationships: list[dict[str, Any]] | None = None,
    timeline_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": "0.1",
        "documentType": "episode_extraction",
        "episodeId": episode_id,
        "storyId": "RPTEST_STORY",
        "storyCategory": "MAIN",
        "extractionRun": _extraction_run(),
        "evidenceIndex": {eid: _evidence_ref(eid, episode_id) for eid in evidence_ids},
        "characters": characters or [],
        "organizations": [],
        "locations": [],
        "items": [],
        "lore": [],
        "events": [],
        "relationships": relationships or [],
        "timelineCandidates": timeline_candidates or [],
        "extractionErrors": [],
    }


def _build_two_episode_fixtures(tmp_path: Path) -> tuple[Path, Path]:
    """report強化テスト共通の2episode fixture。

    EP01: 未解決character (existingCharacterId/sourceCharacterId無し)、
          existingCharacterId=CHAR_X のcharacter (名前"Aname")、
          両端未解決のrelationship、sourceTimelineId="TL1"のtimeline (order=1)
    EP02: existingCharacterId=CHAR_X のcharacter (名前"Bname"。EP01と合わせて
          displayName conflictを起こす)、sourceTimelineId="TL1"のtimeline
          (order=2。EP01と合わせてorderValue conflictを起こす)
    """
    doc1 = _episode_extraction(
        "RPTEST_EP01",
        evidence_ids=[
            "RPTEST_EP01_DLG0001",
            "RPTEST_EP01_DLG0002",
            "RPTEST_EP01_DLG0003",
        ],
        characters=[
            _character_candidate(
                "RPTEST_EP01_CAND_CHAR001", "RPTEST_EP01_DLG0001", ["名無し"]
            ),
            _character_candidate(
                "RPTEST_EP01_CAND_CHAR002",
                "RPTEST_EP01_DLG0002",
                ["Aname"],
                existing_character_id="CHAR_X",
            ),
        ],
        relationships=[
            _relationship_candidate(
                "RPTEST_EP01_CAND_REL001",
                "RPTEST_EP01_DLG0003",
                "NOPE_SOURCE",
                "NOPE_TARGET",
            )
        ],
        timeline_candidates=[
            _timeline_candidate(
                "RPTEST_EP01_CAND_TL001", "RPTEST_EP01_DLG0003", "TL1", 1
            )
        ],
    )
    doc2 = _episode_extraction(
        "RPTEST_EP02",
        evidence_ids=["RPTEST_EP02_DLG0001"],
        characters=[
            _character_candidate(
                "RPTEST_EP02_CAND_CHAR001",
                "RPTEST_EP02_DLG0001",
                ["Bname"],
                existing_character_id="CHAR_X",
            ),
        ],
        timeline_candidates=[
            _timeline_candidate(
                "RPTEST_EP02_CAND_TL001", "RPTEST_EP02_DLG0001", "TL1", 2
            )
        ],
    )

    path1 = tmp_path / "ep01.json"
    path2 = tmp_path / "ep02.json"
    path1.write_text(json.dumps(doc1, ensure_ascii=False), encoding="utf-8")
    path2.write_text(json.dumps(doc2, ensure_ascii=False), encoding="utf-8")
    return path1, path2


@pytest.fixture
def engine() -> MergeEngine:
    return MergeEngine()


@pytest.fixture
def two_episode_report(engine, tmp_path) -> dict[str, Any]:
    path1, path2 = _build_two_episode_fixtures(tmp_path)
    collection = engine.merge_inputs([str(path1), str(path2)])
    return collection["report"]


@pytest.fixture
def collection_validator() -> Draft7Validator:
    with open(COLLECTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


# ----------------------------------------------------------------
# 1. mergedEntityCounts / unresolvedEntityCounts
# ----------------------------------------------------------------


def test_merged_entity_counts_reflect_report(two_episode_report):
    counts = two_episode_report["mergedEntityCounts"]
    assert counts["characters"] == 2  # 未解決1件 + CHAR_X統合1件
    assert counts["timeline"] == 1
    assert counts["relationships"] == 0  # 両端未解決のためentity化されない
    for key in ("locations", "organizations", "items", "lore", "events"):
        assert counts[key] == 0


def test_unresolved_entity_counts_reflect_report(two_episode_report):
    unresolved = two_episode_report["unresolvedEntityCounts"]
    assert unresolved["characters"] == 1
    # Timelineは常にstatus: unresolved (Merged_Knowledge_Design.md §7.1)
    assert unresolved["timeline"] == 1
    assert unresolved["relationships"] == 0
    assert unresolved["organizations"] == 0


# ----------------------------------------------------------------
# 2. conflictCounts
# ----------------------------------------------------------------


def test_display_name_conflict_reflected_in_conflict_counts(two_episode_report):
    conflict_counts = two_episode_report["conflictCounts"]
    assert conflict_counts["byType"]["field_value_conflict"] == 1
    assert conflict_counts["byEntityType"]["characters"] == 1


def test_timeline_order_value_conflict_reflected_in_conflict_counts(
    two_episode_report,
):
    conflict_counts = two_episode_report["conflictCounts"]
    assert conflict_counts["byType"]["timeline_conflict"] == 1
    assert conflict_counts["byEntityType"]["timeline"] == 1


def test_conflict_counts_total_and_severity(two_episode_report):
    conflict_counts = two_episode_report["conflictCounts"]
    assert conflict_counts["total"] == 2
    assert conflict_counts["total"] == two_episode_report["conflictsCount"]
    assert conflict_counts["bySeverity"] == {"warning": 2}


# ----------------------------------------------------------------
# 3. warningCounts
# ----------------------------------------------------------------


def test_unresolved_relationship_warning_reflected_in_warning_counts(
    two_episode_report,
):
    warning_counts = two_episode_report["warningCounts"]
    assert warning_counts["unresolvedRelationships"] == 1
    assert warning_counts["total"] == len(two_episode_report["warnings"])
    assert warning_counts["skippedOverrides"] == 0


# ----------------------------------------------------------------
# 4. entityTypeSummaries
# ----------------------------------------------------------------


def test_entity_type_summaries_present_for_all_eight_types(two_episode_report):
    summaries = two_episode_report["entityTypeSummaries"]
    for key in (
        "characters",
        "locations",
        "organizations",
        "items",
        "lore",
        "events",
        "relationships",
        "timeline",
    ):
        assert key in summaries
        for field_name in (
            "candidateCount",
            "mergedCount",
            "unresolvedCount",
            "conflictCount",
        ):
            assert field_name in summaries[key]


def test_entity_type_summary_values_for_characters(two_episode_report):
    summary = two_episode_report["entityTypeSummaries"]["characters"]
    assert summary["candidateCount"] == 3
    assert summary["mergedCount"] == 2
    assert summary["unresolvedCount"] == 1
    assert summary["conflictCount"] == 1


def test_entity_type_summary_values_for_relationships(two_episode_report):
    summary = two_episode_report["entityTypeSummaries"]["relationships"]
    assert summary["candidateCount"] == 1
    assert summary["mergedCount"] == 0


# ----------------------------------------------------------------
# 5. inputSummaries
# ----------------------------------------------------------------


def test_input_summaries_present_per_input_file(two_episode_report):
    summaries = two_episode_report["inputSummaries"]
    assert len(summaries) == 2
    paths = {s["path"] for s in summaries}
    assert all(s["status"] == "valid" for s in summaries)
    assert all(s["documentId"] is not None for s in summaries)
    assert all(s["candidateCounts"] is not None for s in summaries)
    # mergedEntityCountsは方針B (TASKS.md参照): 入力別には計算しない
    assert all(s["mergedEntityCounts"] is None for s in summaries)
    assert len(paths) == 2


def test_input_summaries_candidate_counts_match_source_documents(engine, tmp_path):
    path1, path2 = _build_two_episode_fixtures(tmp_path)
    collection = engine.merge_inputs([str(path1), str(path2)])
    summaries_by_path = {s["path"]: s for s in collection["report"]["inputSummaries"]}
    for source_doc in collection["sourceDocuments"]:
        summary = summaries_by_path[source_doc["path"]]
        assert summary["candidateCounts"] == source_doc["candidateCounts"]
        assert summary["episodeId"] == source_doc["episodeId"]


def test_input_summaries_include_skipped_input(engine, tmp_path):
    path1, _path2 = _build_two_episode_fixtures(tmp_path)
    missing = tmp_path / "does_not_exist.json"
    collection = engine.merge_inputs([str(path1), str(missing)])
    summaries = collection["report"]["inputSummaries"]

    skipped = [s for s in summaries if s["status"] == "skipped"]
    assert len(skipped) == 1
    assert skipped[0]["path"] == str(missing)
    assert skipped[0]["documentId"] is None
    assert skipped[0]["candidateCounts"] is None


# ----------------------------------------------------------------
# 6. manualOverridesとの整合性
# ----------------------------------------------------------------


def test_schema_validates_without_manual_overrides(
    collection_validator, engine, tmp_path
):
    path1, path2 = _build_two_episode_fixtures(tmp_path)
    collection = engine.merge_inputs([str(path1), str(path2)])

    assert "manualOverrides" not in collection["report"]
    errors = list(collection_validator.iter_errors(collection))
    assert not errors, [e.message for e in errors]


def test_schema_validates_with_manual_overrides_via_cli(collection_validator, tmp_path):
    path1, path2 = _build_two_episode_fixtures(tmp_path)
    output_dir = tmp_path / "merge_preview"

    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(path1),
            str(path2),
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

    assert "manualOverrides" in data["report"]
    errors = list(collection_validator.iter_errors(data))
    assert not errors, [e.message for e in errors]


def test_warning_counts_skipped_overrides_reflects_manual_overrides_report(
    tmp_path,
):
    path1, path2 = _build_two_episode_fixtures(tmp_path)
    output_dir = tmp_path / "merge_preview"

    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(path1),
            str(path2),
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

    report = data["report"]
    # manual_overrides_valid.jsonのOVR_0005はCHAR_DOES_NOT_EXISTを対象と
    # しており、常にskipされる (tests/fixtures/merger/overrides参照)
    assert (
        report["warningCounts"]["skippedOverrides"]
        == report["manualOverrides"]["skippedCount"]
    )
    assert report["manualOverrides"]["skippedCount"] >= 1


# ----------------------------------------------------------------
# 7. CLI出力がcollection schema validationに通る
# ----------------------------------------------------------------


def test_cli_output_with_report_enhancements_matches_collection_schema(
    collection_validator, tmp_path
):
    path1, path2 = _build_two_episode_fixtures(tmp_path)
    output_dir = tmp_path / "merge_preview"

    result = subprocess.run(
        [
            sys.executable,
            str(MERGE_SCRIPT),
            "--input",
            str(path1),
            str(path2),
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
    assert data["report"]["entityTypeSummaries"]["characters"]["mergedCount"] == 2
