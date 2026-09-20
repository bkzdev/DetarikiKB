"""v1 release candidate recordの合成契約テスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.extractor.canonical_timeline_public_input import (
    build_canonical_timeline_public_input,
    canonical_json_sha256,
)
from agents.release_candidate import (
    ReleaseCandidateError,
    build_release_candidate_record,
    sha256_bytes,
)
from agents.wiki_generator.public_site_manifest import build_public_site_manifest

PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_ROOT = PROJECT_ROOT / "schemas"
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


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode()


def _normalization() -> dict:
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
        "hsceneVariantJudgment": {"subset": 0, "exception": 0, "skippedVr": 0},
    }


def _knowledge(normalization_digest: str) -> dict:
    zero = dict.fromkeys(ENTITY_KEYS, 0)
    merged = {**zero, "characters": 1}
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
        "mergedEntityCounts": merged,
        "unresolvedEntityCounts": zero,
        "conflictCount": 0,
        "conflictEntityCounts": zero,
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


def _curation(normalization_digest: str, knowledge_digest: str) -> dict:
    counts = dict.fromkeys(ENTITY_KEYS, 0)
    canonical = {
        "entityCounts": counts,
        "assignedCounts": counts,
        "pendingCounts": counts,
        "conflictCounts": counts,
        "totalAssigned": 0,
        "invalidCount": 0,
        "duplicateCount": 0,
        "warningCount": 0,
        "reviewable": True,
        "fullyConfirmed": False,
    }
    return {
        "schemaVersion": "0.1",
        "documentType": "release_scope_curation_readiness_report",
        "status": "complete",
        "sourceRevision": "a" * 40,
        "inputDigests": {
            "normalizationReportSha256": normalization_digest,
            "knowledgeReportSha256": knowledge_digest,
            "collectionSha256": "2" * 64,
            "characterDictionarySha256": "3" * 64,
            "characterProfilesSha256": "4" * 64,
            "storyTimelineReportSha256": "5" * 64,
            "canonicalTimelineSha256": "6" * 64,
        },
        "canonicalIds": canonical,
        "characterProfiles": {
            "observedSourceIdCount": 0,
            "knownSourceIdCount": 0,
            "unknownSourceIdCount": 0,
            "dictionaryConfirmedCount": 0,
            "releaseCanonicalCharacterCount": 0,
            "confirmedProfileCount": 0,
            "profileOutsideReleaseCount": 0,
            "releaseCharacterWithProfileCount": 0,
            "releaseCharacterPendingProfileCount": 0,
            "reviewable": True,
            "fullyConfirmed": False,
        },
        "storyLocalTimeline": {
            "inputEpisodeCount": 1,
            "storyCount": 1,
            "readyStoryCount": 0,
            "pendingStoryCount": 1,
            "comparableEpisodeCount": 0,
            "missingEpisodeCount": 0,
            "ambiguousEpisodeCount": 0,
            "findingCount": 0,
            "reviewable": True,
            "fullyConfirmed": False,
        },
        "crossStoryTimeline": {
            "nodeCount": 0,
            "edgeCount": 0,
            "relationStateCounts": {},
            "reviewStatusCounts": {},
            "adoptionStatusCounts": {},
            "releaseScopeNodeCount": 0,
            "outsideReleaseScopeNodeCount": 0,
            "findingCount": 0,
            "reviewable": True,
            "fullyConfirmed": False,
        },
        "reviewable": True,
        "fullyConfirmed": False,
    }


def _public_input() -> bytes:
    projection = json.loads(
        (
            PROJECT_ROOT
            / "tests/fixtures/canonical_timeline_public_projection"
            / "valid_projection.json"
        ).read_text(encoding="utf-8")
    )
    digest = canonical_json_sha256(projection)
    digests = {
        "internalDocument": "1" * 64,
        "projection": digest,
        "publicEpisodeMapping": "2" * 64,
        "publicIdRegistry": "3" * 64,
        "publicLabelSource": "4" * 64,
    }
    review = {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_public_input_review",
        "classification": "local_internal",
        "commitAllowed": False,
        "decision": "approved_for_build",
        "reviewedAt": "2099-01-01T00:00:00Z",
        "reviewerType": "human",
        "projectionSha256": digest,
        "preflightStatus": "clean",
        "preflightInputDigests": digests,
        "checks": {
            "projectionSchemaValid": True,
            "projectionSemanticsReviewed": True,
            "internalExposureClear": True,
            "visualReviewCompleted": True,
        },
    }
    preflight = {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_public_preflight_record",
        "classification": "local_internal",
        "commitAllowed": False,
        "status": "clean",
        "publishStatus": "projection_candidate",
        "inputDigests": digests,
        "findings": [],
    }
    return _json_bytes(
        build_canonical_timeline_public_input(projection, review, preflight, digest)
    )


def _manifest(
    tmp_path: Path, source_sha: str, lock: bytes, public_input: bytes, generator: str
) -> dict:
    site = tmp_path / generator
    site.mkdir()
    (site / "index.html").write_text("<h1>合成公開ページ</h1>", encoding="utf-8")
    return build_public_site_manifest(
        site,
        source_sha=source_sha,
        lock_bytes=lock,
        public_input_bytes=public_input,
        generator_name=generator,
        generator_version="1.0.0",
        config_bytes=b"config",
    )


def _inputs(tmp_path: Path) -> dict:
    candidate = "a" * 40
    lock = b"synthetic-lock"
    public_input = _public_input()
    normalization = _normalization()
    normalization_bytes = _json_bytes(normalization)
    knowledge = _knowledge(sha256_bytes(normalization_bytes))
    knowledge_bytes = _json_bytes(knowledge)
    curation = _curation(
        sha256_bytes(normalization_bytes), sha256_bytes(knowledge_bytes)
    )

    def workflow(name: str, run: int) -> dict:
        return {
            "workflow": name,
            "headSha": candidate,
            "conclusion": "success",
            "runUrl": f"https://github.com/example/project/actions/runs/{run}",
        }

    return {
        "candidate_sha": candidate,
        "lock_bytes": lock,
        "public_input_bytes": public_input,
        "normalization_report": normalization,
        "normalization_report_bytes": normalization_bytes,
        "knowledge_report": knowledge,
        "knowledge_report_bytes": knowledge_bytes,
        "curation_report": curation,
        "curation_report_bytes": _json_bytes(curation),
        "mkdocs_manifest": _manifest(
            tmp_path, candidate, lock, public_input, "mkdocs-material"
        ),
        "zensical_manifest": _manifest(
            tmp_path, candidate, lock, public_input, "zensical"
        ),
        "main_ci": workflow("CI", 1),
        "public_build": workflow("Public Build (Reviewed Input, No Deploy)", 2),
        "rollback_source_sha": "b" * 40,
        "rollback_tree_sha256": "c" * 64,
        "rollback_run_url": "https://github.com/example/project/actions/runs/3",
        "public_url": "https://example.invalid/",
        "validated_at": "2099-01-01T00:00:00Z",
        "schema_root": SCHEMA_ROOT,
    }


def test_builds_anonymous_pending_rehearsal_record(tmp_path) -> None:
    record = build_release_candidate_record(**_inputs(tmp_path))
    assert record["status"] == "rehearsal_complete"
    assert record["production"]["candidateGateStatus"] == "pending_human_approval"
    assert record["finalDecision"] == "pending"
    assert record["qualityEvidence"]["normalizedEpisodeCount"] == 1
    assert record["scope"]["categoryEpisodeCounts"] == {"MAIN": 1}
    assert "production_deploy" in record["scope"]["exclusions"]
    assert "path" not in json.dumps(record).lower()


@pytest.mark.parametrize(
    ("mutation", "code"),
    (
        (
            lambda value: value["knowledge_report"].update(
                normalizationReportSha256="0" * 64
            ),
            "release-m2-m3-digest-mismatch",
        ),
        (
            lambda value: value["curation_report"]["inputDigests"].update(
                knowledgeReportSha256="0" * 64
            ),
            "release-m3-m4-digest-mismatch",
        ),
        (
            lambda value: value["curation_report"].update(reviewable=False),
            "release-curation-not-reviewable",
        ),
        (
            lambda value: value["zensical_manifest"].update(lockSha256="0" * 64),
            "release-public-build-pair-invalid",
        ),
        (
            lambda value: value["main_ci"].update(headSha="b" * 40),
            "release-workflow-evidence-invalid",
        ),
        (
            lambda value: value.update(validated_at="2099-01-01"),
            "release-validation-time-invalid",
        ),
        (
            lambda value: value["normalization_report"].pop("sourceRevision"),
            "release-quality-source-mismatch",
        ),
    ),
)
def test_rejects_mixed_or_incomplete_evidence(tmp_path, mutation, code) -> None:
    inputs = _inputs(tmp_path)
    mutation(inputs)
    with pytest.raises(ReleaseCandidateError, match=code):
        build_release_candidate_record(**inputs)
