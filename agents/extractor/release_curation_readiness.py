"""Release scope curation artifactsの匿名readiness集約。"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from agents.extractor.canonical_timeline_consistency import (
    validate_canonical_timeline_consistency,
)
from agents.merger.canonical_ids import validate_canonical_ids
from agents.merger.models import MERGED_ENTITY_KEYS
from agents.merger.schema_validation import load_merged_collection_validator
from agents.parser.character_dictionary import (
    STATUS_CONFIRMED,
    build_character_dictionary_coverage_report,
    load_character_dictionary,
    validate_character_dictionary,
)
from agents.parser.character_profiles import (
    load_character_profiles,
    validate_character_profiles,
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_schema(document: dict[str, Any], schema_path: Path) -> None:
    schema = _load_json(schema_path)
    errors = sorted(
        Draft7Validator(schema).iter_errors(document),
        key=lambda error: list(error.path),
    )
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.path) or "(root)"
        raise ValueError(
            f"schema validation failed ({schema_path.name}): "
            f"{location}: {first.message}"
        )


def _count_story_readiness(report: dict[str, Any]) -> dict[str, int | bool]:
    stories = report["canonicalReadinessStories"]
    comparable = sum(len(story["comparableEpisodeIds"]) for story in stories)
    missing = sum(len(story["missingEpisodeIds"]) for story in stories)
    ambiguous = sum(len(story["ambiguousEpisodes"]) for story in stories)
    findings = (
        report["findingCount"]
        + report["numericFindingCount"]
        + report["canonicalConstraintFindingCount"]
    )
    structurally_valid = (
        report["status"] == "passed"
        and report["invalidInputs"] == 0
        and not report["skippedInputs"]
        and findings == 0
    )
    report = {
        "inputEpisodeCount": report["validInputs"],
        "storyCount": report["canonicalReadinessStoryCount"],
        "readyStoryCount": report["canonicalReadyStoryCount"],
        "pendingStoryCount": (
            report["canonicalReadinessStoryCount"] - report["canonicalReadyStoryCount"]
        ),
        "comparableEpisodeCount": comparable,
        "missingEpisodeCount": missing,
        "ambiguousEpisodeCount": ambiguous,
        "findingCount": findings,
        "reviewable": structurally_valid,
        "fullyConfirmed": structurally_valid and missing == 0 and ambiguous == 0,
    }
    return report


def build_release_curation_readiness_report(  # noqa: C901
    *,
    normalization_report_path: Path,
    knowledge_report_path: Path,
    collection_path: Path,
    character_dictionary_path: Path,
    character_profiles_path: Path,
    story_timeline_report_path: Path,
    canonical_timeline_path: Path,
    schema_root: Path,
) -> dict[str, Any]:
    """既存artifactを変更せず、M4 curation readinessを匿名集約する。"""
    normalization_report = _load_json(normalization_report_path)
    knowledge_report = _load_json(knowledge_report_path)
    collection = _load_json(collection_path)
    story_timeline_report = _load_json(story_timeline_report_path)
    canonical_timeline = _load_json(canonical_timeline_path)

    _validate_schema(
        normalization_report,
        schema_root / "release_scope_normalization_report.schema.json",
    )
    _validate_schema(
        knowledge_report, schema_root / "release_scope_knowledge_report.schema.json"
    )
    _validate_schema(
        story_timeline_report, schema_root / "timeline_consistency_report.schema.json"
    )
    _validate_schema(canonical_timeline, schema_root / "canonical_timeline.schema.json")
    collection_validator = load_merged_collection_validator(
        schema_root / "merged_knowledge_collection.schema.json"
    )
    collection_errors = sorted(
        collection_validator.iter_errors(collection),
        key=lambda error: list(error.path),
    )
    if collection_errors:
        first = collection_errors[0]
        location = "/".join(str(part) for part in first.path) or "(root)"
        raise ValueError(
            f"merged collection schema validation failed: {location}: {first.message}"
        )

    if (
        _sha256(normalization_report_path)
        != knowledge_report["normalizationReportSha256"]
    ):
        raise ValueError("normalization report digest does not match knowledge report")
    if (
        normalization_report["normalizedEpisodeCount"]
        != knowledge_report["normalizedEpisodeCount"]
    ):
        raise ValueError("normalization and knowledge report counts do not match")

    if collection.get("documentType") != "merged_knowledge_collection":
        raise ValueError("collection documentType is not merged_knowledge_collection")
    if (
        len(collection.get("sourceDocuments", []))
        != knowledge_report["normalizedDocumentCount"]
    ):
        raise ValueError("collection sourceDocuments and knowledge report do not match")
    if story_timeline_report["validInputs"] != len(
        collection.get("sourceDocuments", [])
    ):
        raise ValueError("story Timeline report and collection counts do not match")
    collection_episodes = Counter(
        (source["storyId"], source["episodeId"])
        for source in collection["sourceDocuments"]
    )
    timeline_episodes = Counter(
        (story["storyId"], episode_id)
        for story in story_timeline_report["canonicalReadinessStories"]
        for episode_id in story["episodeIds"]
    )
    if timeline_episodes != collection_episodes:
        raise ValueError(
            "story Timeline report and collection episode sets do not match"
        )
    collection_categories = Counter(
        source["storyCategory"] for source in collection["sourceDocuments"]
    )
    knowledge_categories = {
        key: count
        for key, count in knowledge_report["normalizedCategoryCounts"].items()
        if count
    }
    if dict(collection_categories) != knowledge_categories:
        raise ValueError("collection and knowledge report category counts do not match")
    if dict(collection_categories) != normalization_report["categoryEpisodeCounts"]:
        raise ValueError(
            "collection and normalization report category counts do not match"
        )

    dictionary = load_character_dictionary(character_dictionary_path)
    dictionary_issues = validate_character_dictionary(dictionary)
    if dictionary_issues:
        raise ValueError(
            f"character dictionary is invalid ({len(dictionary_issues)} issues)"
        )
    profiles = load_character_profiles(character_profiles_path)
    profile_issues = validate_character_profiles(profiles, dictionary)
    if profile_issues:
        raise ValueError(
            f"character profiles are invalid ({len(profile_issues)} issues)"
        )

    entities = collection["entities"]
    entity_counts = {key: len(entities.get(key, [])) for key in MERGED_ENTITY_KEYS}
    assigned_counts = {
        key: sum(bool(entity.get("canonicalId")) for entity in entities.get(key, []))
        for key in MERGED_ENTITY_KEYS
    }
    pending_counts = {
        key: entity_counts[key] - assigned_counts[key] for key in MERGED_ENTITY_KEYS
    }
    canonical_validation = validate_canonical_ids(collection)
    report_canonical = knowledge_report["canonicalIdSummary"]
    collection_report = collection["report"]
    collection_canonical = collection_report["canonicalIdSummary"]
    collection_conflicts = {
        key: collection_report["conflictCounts"]["byEntityType"].get(key, 0)
        for key in MERGED_ENTITY_KEYS
    }
    canonical_reconciled = (
        canonical_validation.total_assigned == report_canonical["totalAssigned"]
        and canonical_validation.invalid_count == report_canonical["invalidCount"]
        and canonical_validation.duplicate_count == report_canonical["duplicateCount"]
        and collection_canonical["totalAssigned"] == report_canonical["totalAssigned"]
        and collection_canonical["invalidCount"] == report_canonical["invalidCount"]
        and collection_canonical["duplicateCount"] == report_canonical["duplicateCount"]
        and entity_counts == knowledge_report["mergedEntityCounts"]
        and pending_counts == knowledge_report["unresolvedEntityCounts"]
        and collection_report["unresolvedEntityCounts"]
        == knowledge_report["unresolvedEntityCounts"]
        and collection_conflicts == knowledge_report["conflictEntityCounts"]
    )
    canonical_reviewable = (
        canonical_reconciled
        and canonical_validation.invalid_count == 0
        and canonical_validation.duplicate_count == 0
    )
    canonical_warning_count = len(canonical_validation.warnings)
    canonical_ids = {
        "entityCounts": entity_counts,
        "assignedCounts": assigned_counts,
        "pendingCounts": pending_counts,
        "conflictCounts": knowledge_report["conflictEntityCounts"],
        "totalAssigned": canonical_validation.total_assigned,
        "invalidCount": canonical_validation.invalid_count,
        "duplicateCount": canonical_validation.duplicate_count,
        "warningCount": canonical_warning_count,
        "reviewable": canonical_reviewable,
        "fullyConfirmed": canonical_reviewable
        and sum(pending_counts.values()) == 0
        and sum(knowledge_report["conflictEntityCounts"].values()) == 0
        and canonical_warning_count == 0,
    }

    observed_source_ids: Counter[str] = Counter()
    for entity in entities.get("characters", []):
        observed_source_ids.update(entity.get("sourceCharacterIds", []))
    coverage = build_character_dictionary_coverage_report(
        dictionary, dict(observed_source_ids)
    )
    profile_ids = {
        profile.character_id
        for profile in profiles
        if profile.status == STATUS_CONFIRMED and profile.character_id
    }
    release_character_ids = {
        entity["canonicalId"]
        for entity in entities.get("characters", [])
        if entity.get("canonicalId")
    }
    profiles_summary = {
        "observedSourceIdCount": coverage["observedCount"],
        "knownSourceIdCount": coverage["knownCount"],
        "unknownSourceIdCount": coverage["unknownCount"],
        "dictionaryConfirmedCount": coverage["dictionaryConfirmedCount"],
        "releaseCanonicalCharacterCount": len(release_character_ids),
        "confirmedProfileCount": len(profile_ids),
        "profileOutsideReleaseCount": len(profile_ids - release_character_ids),
        "releaseCharacterWithProfileCount": len(release_character_ids & profile_ids),
        "releaseCharacterPendingProfileCount": len(release_character_ids - profile_ids),
        "reviewable": (
            coverage["knownCount"] + coverage["unknownCount"]
            == coverage["observedCount"]
        ),
        "fullyConfirmed": len(release_character_ids - profile_ids) == 0,
    }

    timeline_findings = validate_canonical_timeline_consistency(canonical_timeline)
    relation_counts = Counter(
        edge["relationState"] for edge in canonical_timeline["edges"]
    )
    review_counts = Counter(
        edge["reviewStatus"] for edge in canonical_timeline["edges"]
    )
    adoption_counts = Counter(
        edge["adoptionStatus"] for edge in canonical_timeline["edges"]
    )
    release_episodes = {
        (source["storyId"], source["episodeId"])
        for source in collection["sourceDocuments"]
    }
    inside_node_count = sum(
        (node["storyId"], node["episodeId"]) in release_episodes
        for node in canonical_timeline["nodes"]
    )
    outside_node_count = len(canonical_timeline["nodes"]) - inside_node_count
    pending_edge_count = sum(
        count for status, count in review_counts.items() if status != "confirmed"
    )
    cross_story = {
        "nodeCount": len(canonical_timeline["nodes"]),
        "edgeCount": len(canonical_timeline["edges"]),
        "relationStateCounts": dict(sorted(relation_counts.items())),
        "reviewStatusCounts": dict(sorted(review_counts.items())),
        "adoptionStatusCounts": dict(sorted(adoption_counts.items())),
        "releaseScopeNodeCount": inside_node_count,
        "outsideReleaseScopeNodeCount": outside_node_count,
        "findingCount": len(timeline_findings),
        "reviewable": len(timeline_findings) == 0,
        "fullyConfirmed": len(timeline_findings) == 0
        and pending_edge_count == 0
        and outside_node_count == 0,
    }
    story_local = _count_story_readiness(story_timeline_report)

    sections = [canonical_ids, profiles_summary, story_local, cross_story]
    report = {
        "schemaVersion": "0.1",
        "documentType": "release_scope_curation_readiness_report",
        "status": "complete",
        "inputDigests": {
            "normalizationReportSha256": _sha256(normalization_report_path),
            "knowledgeReportSha256": _sha256(knowledge_report_path),
            "collectionSha256": _sha256(collection_path),
            "characterDictionarySha256": _sha256(character_dictionary_path),
            "characterProfilesSha256": _sha256(character_profiles_path),
            "storyTimelineReportSha256": _sha256(story_timeline_report_path),
            "canonicalTimelineSha256": _sha256(canonical_timeline_path),
        },
        "canonicalIds": canonical_ids,
        "characterProfiles": profiles_summary,
        "storyLocalTimeline": story_local,
        "crossStoryTimeline": cross_story,
        "reviewable": all(section["reviewable"] for section in sections),
        "fullyConfirmed": all(section["fullyConfirmed"] for section in sections),
    }
    normalization_revision = normalization_report.get("sourceRevision")
    knowledge_revision = knowledge_report.get("sourceRevision")
    if normalization_revision is not None or knowledge_revision is not None:
        if normalization_revision != knowledge_revision:
            raise ValueError("release report source revisions do not match")
        report["sourceRevision"] = normalization_revision
    return report
