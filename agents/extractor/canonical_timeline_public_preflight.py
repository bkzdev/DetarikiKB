"""Canonical Timeline public projectionのread-only preflight。

入力digest pin、schema、Registry / label source、internal value exposure、
projector整合を検査する。入力更新、artifact出力、publish-ready化は行わない。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from agents.extractor.canonical_timeline_public_projection import (
    PublicEpisodeMapping,
    build_canonical_timeline_public_projection,
    validate_canonical_timeline_public_projection_consistency,
)

INPUT_DIGEST_MISMATCH = "canonical_timeline_public_preflight_input_digest_mismatch"
INPUT_INVALID = "canonical_timeline_public_preflight_input_invalid"
INTERNAL_SCHEMA_INVALID = "canonical_timeline_public_preflight_internal_schema_invalid"
PROJECTION_SCHEMA_INVALID = (
    "canonical_timeline_public_preflight_projection_schema_invalid"
)
REGISTRY_SCHEMA_INVALID = "canonical_timeline_public_preflight_registry_schema_invalid"
REGISTRY_DUPLICATE = "canonical_timeline_public_preflight_registry_duplicate"
REGISTRY_MAPPING_MISMATCH = (
    "canonical_timeline_public_preflight_registry_mapping_mismatch"
)
PUBLIC_LABEL_SOURCE_INVALID = (
    "canonical_timeline_public_preflight_public_label_source_invalid"
)
PUBLIC_LABEL_MISSING = "canonical_timeline_public_preflight_public_label_missing"
PUBLIC_LABEL_MISMATCH = "canonical_timeline_public_preflight_public_label_mismatch"
INTERNAL_VALUE_EXPOSURE = "canonical_timeline_public_preflight_internal_value_exposure"

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATHS = {
    "internal": _PROJECT_ROOT / "schemas" / "canonical_timeline.schema.json",
    "projection": _PROJECT_ROOT
    / "schemas"
    / "canonical_timeline_public_projection.schema.json",
    "registry": _PROJECT_ROOT / "schemas" / "public_id_registry.schema.json",
}
_DIGEST_KEYS = {
    "internalDocument",
    "projection",
    "publicEpisodeMapping",
    "publicIdRegistry",
    "publicLabelSource",
}
_LABEL_SOURCE_FIELDS = {"storyLabels", "episodeLabels"}
_INTERNAL_IDENTIFIER_KEYS = {
    "storyId",
    "episodeId",
    "candidateId",
    "evidenceIds",
}
_INTERNAL_FREE_TEXT_KEYS = {
    "stateReason",
    "evidenceSummary",
    "notes",
    "reviewer",
}
_FORBIDDEN_PATTERNS = (
    re.compile(r"\.dec\b", re.IGNORECASE),
    re.compile(r"@(ChTalk|Scenario|SpineTalk)\b", re.IGNORECASE),
    re.compile(r"\$num\w*", re.IGNORECASE),
    re.compile(r"(?:https?|file)://", re.IGNORECASE),
    re.compile(r"[A-Za-z]:[\\/]"),
    re.compile(r"/(?:Users|home)/", re.IGNORECASE),
    re.compile(r"\b[0-9a-f]{64}\b", re.IGNORECASE),
)


def _stable_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _mapping_records(mapping: PublicEpisodeMapping) -> list[dict[str, Any]]:
    records = [
        {
            "key": {"storyId": story_id, "episodeId": episode_id},
            "value": record,
        }
        for (story_id, episode_id), record in mapping.items()
    ]
    return sorted(records, key=_stable_value)


def _digest(value: Any) -> str:
    return hashlib.sha256(_stable_value(value).encode("utf-8")).hexdigest()


def canonical_timeline_public_preflight_input_digests(
    document: dict[str, Any],
    projection: dict[str, Any],
    public_episode_mapping: PublicEpisodeMapping,
    public_id_registry: dict[str, Any],
    public_label_source: dict[str, Any],
) -> dict[str, str]:
    """preflight再実行時にpinする5入力のcanonical SHA-256を返す。"""
    return {
        "internalDocument": _digest(document),
        "projection": _digest(projection),
        "publicEpisodeMapping": _digest(_mapping_records(public_episode_mapping)),
        "publicIdRegistry": _digest(public_id_registry),
        "publicLabelSource": _digest(public_label_source),
    }


def _load_validators() -> dict[str, Draft7Validator]:
    return {
        name: Draft7Validator(json.loads(path.read_text(encoding="utf-8")))
        for name, path in _SCHEMA_PATHS.items()
    }


def _aggregate(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for finding in findings:
        counts[finding["rule"]] += finding["count"]
    return [{"rule": rule, "count": counts[rule]} for rule in sorted(counts)]


def _report(findings: list[dict[str, Any]]) -> dict[str, Any]:
    aggregated = _aggregate(findings)
    return {
        "status": "blocked" if aggregated else "clean",
        "publishStatus": "projection_candidate",
        "findings": aggregated,
    }


def _schema_findings(
    document: dict[str, Any],
    projection: dict[str, Any],
    registry: dict[str, Any],
) -> list[dict[str, Any]]:
    validators = _load_validators()
    checks = (
        (INTERNAL_SCHEMA_INVALID, validators["internal"], document),
        (PROJECTION_SCHEMA_INVALID, validators["projection"], projection),
        (REGISTRY_SCHEMA_INVALID, validators["registry"], registry),
    )
    return [
        {"rule": rule, "count": len(errors)}
        for rule, validator, value in checks
        if (errors := list(validator.iter_errors(value)))
    ]


def _registry_findings(
    projection: dict[str, Any], registry: dict[str, Any]
) -> list[dict[str, Any]]:
    story_ids = [story["publicStoryId"] for story in registry["stories"]]
    episode_ids = [
        episode["publicEpisodeId"]
        for story in registry["stories"]
        for episode in story["episodes"]
    ]
    duplicate_count = sum(
        count - 1 for count in Counter(story_ids).values() if count > 1
    )
    duplicate_count += sum(
        count - 1 for count in Counter(episode_ids).values() if count > 1
    )
    findings = []
    if duplicate_count:
        findings.append({"rule": REGISTRY_DUPLICATE, "count": duplicate_count})

    registered_pairs = {
        (story["publicStoryId"], episode["publicEpisodeId"])
        for story in registry["stories"]
        if story["category"] == "event"
        for episode in story["episodes"]
    }
    projected_pairs = {
        (node["publicStoryId"], node["publicEpisodeId"])
        for component in projection["components"]
        for node in component["nodes"]
    }
    mismatch_count = len(projected_pairs - registered_pairs)
    if mismatch_count:
        findings.append({"rule": REGISTRY_MAPPING_MISMATCH, "count": mismatch_count})
    return findings


def _label_findings(
    projection: dict[str, Any], label_source: dict[str, Any]
) -> list[dict[str, Any]]:
    if (
        not isinstance(label_source, dict)
        or set(label_source) != _LABEL_SOURCE_FIELDS
        or not all(
            isinstance(label_source[field], dict) for field in _LABEL_SOURCE_FIELDS
        )
        or not all(
            isinstance(key, str) and isinstance(value, str)
            for field in _LABEL_SOURCE_FIELDS
            for key, value in label_source[field].items()
        )
    ):
        return [{"rule": PUBLIC_LABEL_SOURCE_INVALID, "count": 1}]

    missing = 0
    mismatch = 0
    checked_stories: set[str] = set()
    checked_episodes: set[str] = set()
    for component in projection["components"]:
        for node in component["nodes"]:
            story_id = node["publicStoryId"]
            if story_id not in checked_stories:
                checked_stories.add(story_id)
                expected = label_source["storyLabels"].get(story_id)
                missing += expected is None
                mismatch += expected is not None and expected != node["storyLabel"]
            episode_id = node["publicEpisodeId"]
            if episode_id not in checked_episodes:
                checked_episodes.add(episode_id)
                expected = label_source["episodeLabels"].get(episode_id)
                missing += expected is None
                mismatch += expected is not None and expected != node["episodeLabel"]

    findings = []
    if missing:
        findings.append({"rule": PUBLIC_LABEL_MISSING, "count": missing})
    if mismatch:
        findings.append({"rule": PUBLIC_LABEL_MISMATCH, "count": mismatch})
    return findings


def _collect_values_for_keys(
    value: Any, protected_keys: set[str], *, key: str | None = None
) -> set[str]:
    values: set[str] = set()
    if isinstance(value, dict):
        for child_key, child in value.items():
            values.update(
                _collect_values_for_keys(child, protected_keys, key=child_key)
            )
    elif isinstance(value, list):
        for child in value:
            values.update(_collect_values_for_keys(child, protected_keys, key=key))
    elif key in protected_keys and isinstance(value, str) and value:
        values.add(value)
    return values


def _exposure_count(document: dict[str, Any], projection: dict[str, Any]) -> int:
    text = _stable_value(projection)
    internal_identifiers = _collect_values_for_keys(document, _INTERNAL_IDENTIFIER_KEYS)
    internal_free_text = _collect_values_for_keys(document, _INTERNAL_FREE_TEXT_KEYS)
    public_labels = [
        node[label_field]
        for component in projection["components"]
        for node in component["nodes"]
        for label_field in ("storyLabel", "episodeLabel")
    ]
    count = sum(text.count(value) for value in internal_identifiers)
    count += sum(label in internal_free_text for label in public_labels)
    count += sum(len(pattern.findall(text)) for pattern in _FORBIDDEN_PATTERNS)
    return count


def _valid_digest_inputs(
    public_episode_mapping: Any, expected_input_digests: Any
) -> bool:
    return (
        isinstance(public_episode_mapping, dict)
        and all(
            isinstance(key, tuple)
            and len(key) == 2
            and all(isinstance(part, str) for part in key)
            for key in public_episode_mapping
        )
        and isinstance(expected_input_digests, dict)
        and set(expected_input_digests) == _DIGEST_KEYS
        and all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            for value in expected_input_digests.values()
        )
    )


def preflight_canonical_timeline_public_projection(
    document: dict[str, Any],
    projection: dict[str, Any],
    public_episode_mapping: PublicEpisodeMapping,
    public_id_registry: dict[str, Any],
    public_label_source: dict[str, Any],
    expected_input_digests: dict[str, str],
) -> dict[str, Any]:
    """固定rule/countだけのread-only preflight reportを返す。"""
    if not _valid_digest_inputs(public_episode_mapping, expected_input_digests):
        return _report([{"rule": INPUT_INVALID, "count": 1}])
    actual_digests = canonical_timeline_public_preflight_input_digests(
        document,
        projection,
        public_episode_mapping,
        public_id_registry,
        public_label_source,
    )
    digest_mismatches = sum(
        expected_input_digests.get(key) != actual_digests[key] for key in _DIGEST_KEYS
    )
    if digest_mismatches:
        return _report([{"rule": INPUT_DIGEST_MISMATCH, "count": digest_mismatches}])

    findings = _schema_findings(document, projection, public_id_registry)
    if findings:
        return _report(findings)

    build_result = build_canonical_timeline_public_projection(
        document, public_episode_mapping
    )
    if build_result["report"]["status"] != "clean":
        return _report(build_result["report"]["findings"])

    findings.extend(_registry_findings(projection, public_id_registry))
    findings.extend(_label_findings(projection, public_label_source))
    findings.extend(
        validate_canonical_timeline_public_projection_consistency(
            projection, document, public_episode_mapping
        )
    )
    exposure_count = _exposure_count(document, projection)
    if exposure_count:
        findings.append({"rule": INTERNAL_VALUE_EXPOSURE, "count": exposure_count})
    return _report(findings)
