"""Canonical Timeline public projection v0.1 schema contract tests."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = (
    PROJECT_ROOT / "schemas" / "canonical_timeline_public_projection.schema.json"
)
FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "canonical_timeline_public_projection"
    / "valid_projection.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator() -> Draft7Validator:
    return Draft7Validator(_load_json(SCHEMA_PATH))


def _valid_projection() -> dict:
    return _load_json(FIXTURE_PATH)


def _errors(document: dict) -> list:
    return sorted(
        _validator().iter_errors(document), key=lambda error: list(error.path)
    )


def test_schema_is_valid_draft7():
    Draft7Validator.check_schema(_load_json(SCHEMA_PATH))


def test_synthetic_public_projection_fixture_is_valid():
    assert _errors(_valid_projection()) == []


def test_empty_fail_closed_projection_is_valid():
    projection = _valid_projection()
    projection["components"] = []
    projection["unresolvedRelationSummary"] = None

    assert _errors(projection) == []


@pytest.mark.parametrize(
    "field",
    [
        "schemaVersion",
        "documentType",
        "visibility",
        "publishStatus",
        "scope",
        "purpose",
        "coverageNoticeKey",
        "components",
        "unresolvedRelationSummary",
    ],
)
def test_root_profile_fields_are_required(field: str):
    projection = _valid_projection()
    del projection[field]

    assert _errors(projection)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schemaVersion", "0.2"),
        ("documentType", "canonical_timeline"),
        ("visibility", "internal_only"),
        ("publishStatus", "publish_ready"),
        ("scope", "character"),
        ("purpose", "complete_timeline"),
        ("coverageNoticeKey", "complete_timeline"),
    ],
)
def test_root_profile_is_fixed(field: str, value: str):
    projection = _valid_projection()
    projection[field] = value

    assert _errors(projection)


@pytest.mark.parametrize(
    "field",
    ["sourceDigest", "generatedAt", "sourcePath", "canonicalOrder"],
)
def test_root_rejects_non_public_fields(field: str):
    projection = _valid_projection()
    projection[field] = "forbidden"

    assert _errors(projection)


@pytest.mark.parametrize(
    "field",
    [
        "storyId",
        "episodeId",
        "candidateId",
        "evidenceIds",
        "confidence",
        "reviewer",
    ],
)
def test_node_rejects_internal_or_review_fields(field: str):
    projection = _valid_projection()
    projection["components"][0]["nodes"][0][field] = "forbidden"

    assert _errors(projection)


@pytest.mark.parametrize("relation_state", ["unknown", "conflict"])
def test_relation_rejects_unresolved_states(relation_state: str):
    projection = _valid_projection()
    projection["components"][0]["relations"][0]["relationState"] = relation_state

    assert _errors(projection)


@pytest.mark.parametrize(
    "field",
    ["stateReason", "candidateProvenance", "humanDecision", "confidence"],
)
def test_relation_rejects_internal_reason_and_provenance(field: str):
    projection = _valid_projection()
    projection["components"][0]["relations"][0][field] = "forbidden"

    assert _errors(projection)


@pytest.mark.parametrize(
    ("relation_state", "label_key"),
    [
        ("before", "timeline_after"),
        ("after", "timeline_same_time"),
        ("same_time", "timeline_before"),
    ],
)
def test_relation_state_requires_matching_fixed_label_key(
    relation_state: str, label_key: str
):
    projection = _valid_projection()
    relation = projection["components"][0]["relations"][0]
    relation["relationState"] = relation_state
    relation["labelKey"] = label_key

    assert _errors(projection)


@pytest.mark.parametrize(
    ("relation_state", "label_key"),
    [
        ("before", "timeline_before"),
        ("after", "timeline_after"),
        ("same_time", "timeline_same_time"),
    ],
)
def test_relation_state_accepts_its_fixed_label_key(
    relation_state: str, label_key: str
):
    projection = _valid_projection()
    relation = projection["components"][0]["relations"][0]
    relation["relationState"] = relation_state
    relation["labelKey"] = label_key

    assert _errors(projection) == []


def test_public_labels_reject_multiline_and_oversized_values():
    multiline = _valid_projection()
    multiline["components"][0]["nodes"][0]["storyLabel"] = "line 1\nline 2"
    oversized = _valid_projection()
    oversized["components"][0]["nodes"][0]["episodeLabel"] = "x" * 201

    assert _errors(multiline)
    assert _errors(oversized)


def test_public_ids_reject_internal_style_punctuation():
    projection = _valid_projection()
    projection["components"][0]["nodes"][0]["publicStoryId"] = "PUBLIC-EVENT"

    assert _errors(projection)


def test_exact_duplicate_nodes_and_relations_are_rejected():
    duplicate_node = _valid_projection()
    node = duplicate_node["components"][0]["nodes"][0]
    duplicate_node["components"][0]["nodes"].append(copy.deepcopy(node))
    duplicate_relation = _valid_projection()
    relation = duplicate_relation["components"][0]["relations"][0]
    duplicate_relation["components"][0]["relations"].append(copy.deepcopy(relation))

    assert _errors(duplicate_node)
    assert _errors(duplicate_relation)


@pytest.mark.parametrize(
    "field",
    ["storyId", "episodeId", "reason", "provenance", "details"],
)
def test_unresolved_summary_rejects_identifiers_and_free_text(field: str):
    projection = _valid_projection()
    projection["unresolvedRelationSummary"][field] = "forbidden"

    assert _errors(projection)


def test_unresolved_summary_rejects_negative_or_non_integer_counts():
    negative = _valid_projection()
    negative["unresolvedRelationSummary"]["unknownCount"] = -1
    fractional = _valid_projection()
    fractional["unresolvedRelationSummary"]["conflictCount"] = 0.5

    assert _errors(negative)
    assert _errors(fractional)
