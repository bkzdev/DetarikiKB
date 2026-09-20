"""Release scope curation readinessの匿名集約テスト。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from agents.extractor.release_curation_readiness import (
    build_release_curation_readiness_report,
)
from agents.merger.engine import MergeEngine
from scripts import check_release_scope_curation_readiness as readiness_cli
from scripts.check_timeline_consistency import _build_report

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXTRACTION_FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "extraction"
    / "minimal_episode_extraction.json"
)

ENTITY_KEYS = (
    "characters",
    "locations",
    "organizations",
    "items",
    "lore",
    "events",
    "relationships",
    "timeline",
)


def _write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def _normalization_report() -> dict:
    return {
        "schemaVersion": "0.1",
        "documentType": "release_scope_normalization_report",
        "status": "complete",
        "sourceRevision": "a" * 40,
        "manifestSha256": "0" * 64,
        "manifestStoryCount": 1,
        "manifestEpisodeCount": 1,
        "dynamicExceptionEpisodeCount": 0,
        "normalizedEpisodeCount": 1,
        "invalidCount": 0,
        "skippedCount": 0,
        "categoryEpisodeCounts": {"MAIN": 1},
        "compatibilityStatusCounts": {"compatible": 1},
        "unknownBlockCount": 0,
        "episodesWithUnknownBlocks": 0,
        "unknownCommandDistinctCount": 0,
        "unknownCommandOccurrenceCount": 0,
        "episodesWithUnknownCommands": 0,
        "unknownCharacterIdDistinctCount": 0,
        "episodesWithUnknownCharacterIds": 0,
        "unresolvedSpeakerBlockCount": 0,
        "episodesWithUnresolvedSpeakers": 0,
        "nonSpeakerNumericAssignmentCount": 0,
        "nonLiteralSpeakerExpressionCount": 0,
        "branchIssueCount": 0,
        "caseVariantCount": 0,
        "controlCharsRemoved": 0,
        "hsceneVariantJudgment": {
            "subset": 0,
            "exception": 0,
            "skippedVr": 0,
        },
    }


def _knowledge_report(normalization_digest: str) -> dict:
    zero_entities = dict.fromkeys(ENTITY_KEYS, 0)
    entity_counts = {**zero_entities, "characters": 1}
    return {
        "schemaVersion": "0.1",
        "documentType": "release_scope_knowledge_report",
        "status": "complete",
        "sourceRevision": "a" * 40,
        "normalizationReportSha256": normalization_digest,
        "normalizedTreeSha256": "1" * 64,
        "normalizedDocumentCount": 1,
        "normalizedEpisodeCount": 1,
        "normalizedCategoryCounts": {
            "MAIN": 1,
            "EVT": 0,
            "RAID": 0,
            "OTHER": 0,
            "CHAR_MAIN": 0,
            "CHAR_EXTRA": 0,
            "CHAR_DATE": 0,
            "CHAR_HS": 0,
        },
        "extractionDocumentCount": 1,
        "extractionInvalidCount": 0,
        "extractionSemanticErrorCount": 0,
        "extractionSemanticWarningCount": 0,
        "hsceneDedup": {
            "bodyEpisodeCount": 0,
            "variantEpisodeCount": 0,
            "excludedBlockCount": 0,
        },
        "mergeResolvedInputCount": 1,
        "mergeValidInputCount": 1,
        "mergeInvalidInputCount": 0,
        "mergeSkippedInputCount": 0,
        "candidateCounts": {
            "characters": 1,
            "locations": 0,
            "organizations": 0,
            "items": 0,
            "lore": 0,
            "events": 0,
            "relationships": 0,
            "timelineCandidates": 0,
        },
        "specialSpeakerLabelCandidateCount": 0,
        "mergedEntityCounts": entity_counts,
        "unresolvedEntityCounts": zero_entities,
        "conflictCount": 0,
        "conflictEntityCounts": zero_entities,
        "warningCounts": {
            "total": 0,
            "unresolvedRelationships": 0,
            "skippedOverrides": 0,
            "other": 0,
        },
        "relationshipReviewRecordCount": 0,
        "canonicalIdSummary": {
            "totalAssigned": 1,
            "duplicateCount": 0,
            "invalidCount": 0,
        },
        "specialSpeakerLabelCount": 0,
    }


def _inputs(tmp_path: Path) -> dict[str, Path]:
    normalization = _write_json(
        tmp_path / "normalization.json", _normalization_report()
    )
    normalization_digest = hashlib.sha256(normalization.read_bytes()).hexdigest()
    knowledge = _write_json(
        tmp_path / "knowledge.json", _knowledge_report(normalization_digest)
    )
    collection = MergeEngine().merge_inputs([str(EXTRACTION_FIXTURE)])
    character = collection["entities"]["characters"][0]
    character["status"] = "merged"
    character["canonicalId"] = "CHAR_TEST_SECRET"
    collection["report"]["canonicalIdSummary"] = {
        "totalAssigned": 1,
        "duplicateCount": 0,
        "invalidCount": 0,
        "warnings": [],
    }
    collection["report"]["unresolvedCount"] = 0
    collection["report"]["unresolvedEntityCounts"]["characters"] = 0
    collection_path = _write_json(tmp_path / "collection.json", collection)
    dictionary_path = tmp_path / "characters.yaml"
    dictionary_path.write_text(
        yaml.safe_dump(
            {
                "characters": [
                    {
                        "sourceCharacterId": character["sourceCharacterIds"][0],
                        "characterId": "CHAR_TEST_SECRET",
                        "displayName": "Synthetic Secret",
                        "aliases": [],
                        "status": "confirmed",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    profiles_path = tmp_path / "profiles.yaml"
    profiles_path.write_text("profiles: []\n", encoding="utf-8")
    timeline_report, _ = _build_report([str(EXTRACTION_FIXTURE)], recursive=False)
    timeline_path = _write_json(tmp_path / "timeline_report.json", timeline_report)
    canonical_path = _write_json(
        tmp_path / "canonical_timeline.json",
        {
            "schemaVersion": "0.1",
            "documentType": "canonical_timeline",
            "scopeStoryCategory": "EVT",
            "visibility": "internal_only",
            "nodes": [],
            "edges": [],
        },
    )
    return {
        "normalization_report_path": normalization,
        "knowledge_report_path": knowledge,
        "collection_path": collection_path,
        "character_dictionary_path": dictionary_path,
        "character_profiles_path": profiles_path,
        "story_timeline_report_path": timeline_path,
        "canonical_timeline_path": canonical_path,
        "schema_root": PROJECT_ROOT / "schemas",
    }


def test_builds_schema_valid_anonymous_reviewable_report(tmp_path):
    report = build_release_curation_readiness_report(**_inputs(tmp_path))

    schema = json.loads(
        (
            PROJECT_ROOT
            / "schemas"
            / "release_scope_curation_readiness_report.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert not list(Draft7Validator(schema).iter_errors(report))
    assert report["reviewable"] is True
    assert report["sourceRevision"] == "a" * 40
    assert report["fullyConfirmed"] is False
    assert report["canonicalIds"]["totalAssigned"] == 1
    assert report["canonicalIds"]["warningCount"] == 0
    assert report["canonicalIds"]["fullyConfirmed"] is True
    assert report["characterProfiles"]["releaseCharacterPendingProfileCount"] == 1
    assert report["characterProfiles"]["profileOutsideReleaseCount"] == 0
    serialized = json.dumps(report, ensure_ascii=False)
    assert "TEST_S01" not in serialized
    assert str(tmp_path) not in serialized


def test_rejects_normalization_digest_mismatch(tmp_path):
    inputs = _inputs(tmp_path)
    knowledge = json.loads(inputs["knowledge_report_path"].read_text(encoding="utf-8"))
    knowledge["normalizationReportSha256"] = "f" * 64
    _write_json(inputs["knowledge_report_path"], knowledge)

    try:
        build_release_curation_readiness_report(**inputs)
    except ValueError as exc:
        assert "digest does not match" in str(exc)
    else:
        raise AssertionError("digest mismatch must fail closed")


def test_rejects_release_report_source_revision_mismatch(tmp_path):
    inputs = _inputs(tmp_path)
    knowledge = json.loads(inputs["knowledge_report_path"].read_text(encoding="utf-8"))
    knowledge["sourceRevision"] = "b" * 40
    _write_json(inputs["knowledge_report_path"], knowledge)

    with pytest.raises(ValueError, match="source revisions do not match"):
        build_release_curation_readiness_report(**inputs)


def test_rejects_same_size_different_timeline_episode_set(tmp_path):
    inputs = _inputs(tmp_path)
    timeline = json.loads(
        inputs["story_timeline_report_path"].read_text(encoding="utf-8")
    )
    story = timeline["canonicalReadinessStories"][0]
    story["episodeIds"] = ["DIFFERENT_EPISODE"]
    story["missingEpisodeIds"] = ["DIFFERENT_EPISODE"]
    _write_json(inputs["story_timeline_report_path"], timeline)

    try:
        build_release_curation_readiness_report(**inputs)
    except ValueError as exc:
        assert "episode sets do not match" in str(exc)
    else:
        raise AssertionError("different corpus must fail closed")


def test_collection_report_mismatch_is_not_fully_confirmed(tmp_path):
    inputs = _inputs(tmp_path)
    collection = json.loads(inputs["collection_path"].read_text(encoding="utf-8"))
    collection["report"]["canonicalIdSummary"]["totalAssigned"] = 0
    _write_json(inputs["collection_path"], collection)

    report = build_release_curation_readiness_report(**inputs)

    assert report["canonicalIds"]["reviewable"] is False
    assert report["canonicalIds"]["fullyConfirmed"] is False
    assert report["reviewable"] is False
    assert report["fullyConfirmed"] is False


def test_rejects_category_count_mismatch(tmp_path):
    inputs = _inputs(tmp_path)
    collection = json.loads(inputs["collection_path"].read_text(encoding="utf-8"))
    collection["sourceDocuments"][0]["storyCategory"] = "EVT"
    _write_json(inputs["collection_path"], collection)

    with pytest.raises(ValueError, match="category counts do not match"):
        build_release_curation_readiness_report(**inputs)


def test_output_path_rejects_existing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness_cli, "_DRY_RUN_ROOT", tmp_path.resolve())
    existing = tmp_path / "report.json"
    existing.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="既に存在"):
        readiness_cli._output_path(str(existing))

    assert existing.read_text(encoding="utf-8") == "keep"
