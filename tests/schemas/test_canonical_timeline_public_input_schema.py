"""Canonical Timeline public input / review schemaの合成契約テスト。"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry, Resource

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMA_DIR = PROJECT_ROOT / "schemas"
PROJECTION_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "canonical_timeline_public_projection"
    / "valid_projection.json"
)
REVIEW_TEMPLATE_PATH = (
    PROJECT_ROOT
    / "docs"
    / "templates"
    / "canonical_timeline_public_input_review_template.json"
)
PREFLIGHT_TEMPLATE_PATH = (
    PROJECT_ROOT
    / "docs"
    / "templates"
    / "canonical_timeline_public_preflight_record_template.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(value: dict) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validators() -> dict[str, Draft7Validator]:
    schemas = [
        _load(SCHEMA_DIR / name)
        for name in (
            "canonical_timeline_public_projection.schema.json",
            "canonical_timeline_public_preflight_record.schema.json",
            "canonical_timeline_public_input_review.schema.json",
            "canonical_timeline_public_input.schema.json",
        )
    ]
    registry = Registry().with_resources(
        [(schema["$id"], Resource.from_contents(schema)) for schema in schemas]
    )
    return {
        schema["$id"]: Draft7Validator(
            schema, registry=registry, format_checker=FormatChecker()
        )
        for schema in schemas
    }


def _errors(schema_name: str, value: dict) -> list:
    schema_id = f"https://detariki-kb/schemas/{schema_name}"
    return list(_validators()[schema_id].iter_errors(value))


def _approved_review(projection: dict) -> dict:
    review = _load(REVIEW_TEMPLATE_PATH)
    digest = _digest(projection)
    review.update(
        {
            "decision": "approved_for_build",
            "preflightStatus": "clean",
            "projectionSha256": digest,
        }
    )
    review["preflightInputDigests"]["projection"] = digest
    review["checks"] = dict.fromkeys(review["checks"], True)
    return review


def _public_input() -> dict:
    projection = _load(PROJECTION_PATH)
    review = _approved_review(projection)
    return {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_public_input",
        "visibility": "public",
        "buildStatus": "approved_for_build",
        "contentType": "canonical_timeline_public_projection",
        "payloadSha256": _digest(projection),
        "pushReview": {
            "decision": review["decision"],
            "reviewedAt": review["reviewedAt"],
            "reviewerType": review["reviewerType"],
            "checks": review["checks"],
        },
        "projection": projection,
    }


def test_template_is_valid_but_not_approved() -> None:
    template = _load(REVIEW_TEMPLATE_PATH)
    assert _errors("canonical_timeline_public_input_review.schema.json", template) == []
    assert template["decision"] == "needs_revision"
    assert template["commitAllowed"] is False
    preflight = _load(PREFLIGHT_TEMPLATE_PATH)
    assert (
        _errors("canonical_timeline_public_preflight_record.schema.json", preflight)
        == []
    )
    assert preflight["status"] == "blocked"


def test_approved_review_and_public_input_are_valid() -> None:
    projection = _load(PROJECTION_PATH)
    assert (
        _errors(
            "canonical_timeline_public_input_review.schema.json",
            _approved_review(projection),
        )
        == []
    )
    assert _errors("canonical_timeline_public_input.schema.json", _public_input()) == []


def test_preflight_record_binds_five_digests_and_clean_findings() -> None:
    projection = _load(PROJECTION_PATH)
    review = _approved_review(projection)
    record = {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_public_preflight_record",
        "classification": "local_internal",
        "commitAllowed": False,
        "status": "clean",
        "publishStatus": "projection_candidate",
        "inputDigests": review["preflightInputDigests"],
        "findings": [],
    }
    assert (
        _errors("canonical_timeline_public_preflight_record.schema.json", record) == []
    )
    record["findings"] = [{"rule": "synthetic", "count": 1}]
    assert _errors("canonical_timeline_public_preflight_record.schema.json", record)


@pytest.mark.parametrize(
    "field", ("reviewerName", "notes", "storyId", "internalDocument")
)
def test_review_rejects_non_allowlisted_fields(field: str) -> None:
    review = _approved_review(_load(PROJECTION_PATH))
    review[field] = "TEST_FORBIDDEN"
    assert _errors("canonical_timeline_public_input_review.schema.json", review)


@pytest.mark.parametrize("check", tuple(_load(REVIEW_TEMPLATE_PATH)["checks"]))
def test_approved_review_requires_every_check(check: str) -> None:
    review = _approved_review(_load(PROJECTION_PATH))
    review["checks"][check] = False
    assert _errors("canonical_timeline_public_input_review.schema.json", review)


def test_approved_review_requires_clean_preflight() -> None:
    review = _approved_review(_load(PROJECTION_PATH))
    review["preflightStatus"] = "blocked"
    assert _errors("canonical_timeline_public_input_review.schema.json", review)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("buildStatus", "publish_ready"),
        ("visibility", "internal_only"),
        ("contentType", "internal_timeline"),
    ],
)
def test_public_input_rejects_status_and_scope_expansion(
    field: str, value: str
) -> None:
    document = _public_input()
    document[field] = value
    assert _errors("canonical_timeline_public_input.schema.json", document)


def test_nested_projection_still_rejects_internal_fields() -> None:
    document = _public_input()
    document["projection"]["storyId"] = "EVT_TEST_INTERNAL"
    assert _errors("canonical_timeline_public_input.schema.json", document)


def test_public_input_rejects_review_identity_and_internal_digests() -> None:
    for field in ("reviewerName", "notes", "preflightInputDigests"):
        document = _public_input()
        document["pushReview"][field] = copy.deepcopy({})
        assert _errors("canonical_timeline_public_input.schema.json", document)
