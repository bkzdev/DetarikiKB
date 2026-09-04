"""Canonical Timeline public input envelopeの合成契約テスト。"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from agents.extractor.canonical_timeline_public_input import (
    PublicInputError,
    build_canonical_timeline_public_input,
    canonical_json_sha256,
    validate_canonical_timeline_public_input,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
PROJECTION_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "canonical_timeline_public_projection"
    / "valid_projection.json"
)


def _projection() -> dict:
    return json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))


def _review(projection: dict, **overrides: object) -> dict:
    digest = canonical_json_sha256(projection)
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
        "preflightInputDigests": {
            "internalDocument": "1" * 64,
            "projection": digest,
            "publicEpisodeMapping": "2" * 64,
            "publicIdRegistry": "3" * 64,
            "publicLabelSource": "4" * 64,
        },
        "checks": {
            "projectionSchemaValid": True,
            "projectionSemanticsReviewed": True,
            "internalExposureClear": True,
            "visualReviewCompleted": True,
        },
    }
    review.update(overrides)
    return review


def _preflight(projection: dict | None = None) -> dict:
    projection = projection or _projection()
    return {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_public_preflight_record",
        "classification": "local_internal",
        "commitAllowed": False,
        "status": "clean",
        "publishStatus": "projection_candidate",
        "inputDigests": _review(projection)["preflightInputDigests"],
        "findings": [],
    }


def _build(projection: dict | None = None, review: dict | None = None) -> dict:
    projection = projection or _projection()
    review = review or _review(projection)
    return build_canonical_timeline_public_input(
        projection,
        review,
        _preflight(projection),
        canonical_json_sha256(projection),
    )


def test_build_is_deterministic_input_immutable_and_public_safe() -> None:
    projection = _projection()
    review = _review(projection)
    original = copy.deepcopy((projection, review))

    first = _build(projection, review)
    second = _build(projection, review)

    assert first == second
    assert (projection, review) == original
    assert validate_canonical_timeline_public_input(first) == ()
    assert first["buildStatus"] == "approved_for_build"
    assert first["projection"]["publishStatus"] == "projection_candidate"
    serialized = json.dumps(first)
    for forbidden in (
        "preflightInputDigests",
        "classification",
        "commitAllowed",
        "reviewerName",
        "notes",
        "publish_ready",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda review: review.update({"decision": "rejected"}), "review-not-approved"),
        (
            lambda review: review.update({"projectionSha256": "f" * 64}),
            "review-projection-digest-mismatch",
        ),
        (
            lambda review: review["preflightInputDigests"].update(
                {"projection": "e" * 64}
            ),
            "preflight-projection-digest-mismatch",
        ),
    ],
)
def test_review_and_digest_mismatches_fail_closed(mutation, code) -> None:
    projection = _projection()
    review = _review(projection)
    mutation(review)
    with pytest.raises(PublicInputError, match=code):
        _build(projection, review)


def test_expected_digest_and_preflight_are_required() -> None:
    projection = _projection()
    review = _review(projection)
    with pytest.raises(PublicInputError, match="expected-projection-digest-mismatch"):
        build_canonical_timeline_public_input(
            projection, review, _preflight(projection), "0" * 64
        )

    blocked = _preflight()
    blocked["status"] = "blocked"
    blocked["findings"] = [{"rule": "synthetic", "count": 1}]
    with pytest.raises(PublicInputError, match="preflight-not-clean"):
        build_canonical_timeline_public_input(
            projection, review, blocked, canonical_json_sha256(projection)
        )


def test_preflight_record_must_bind_all_five_review_digests() -> None:
    projection = _projection()
    review = _review(projection)
    preflight = _preflight(projection)
    preflight["inputDigests"]["publicLabelSource"] = "9" * 64
    with pytest.raises(PublicInputError, match="preflight-input-digests-mismatch"):
        build_canonical_timeline_public_input(
            projection, review, preflight, canonical_json_sha256(projection)
        )


@pytest.mark.parametrize("field", ("reviewerName", "notes", "storyId"))
def test_review_allowlist_rejects_identity_free_text_and_internal_fields(field) -> None:
    projection = _projection()
    review = _review(projection)
    review[field] = "TEST_FORBIDDEN"
    with pytest.raises(PublicInputError, match="review-schema-invalid"):
        _build(projection, review)


def test_envelope_schema_and_digest_validation_fail_closed() -> None:
    document = _build()
    document["payloadSha256"] = "0" * 64
    assert validate_canonical_timeline_public_input(document) == (
        "public-input-payload-digest-mismatch",
    )

    document = _build()
    document["publishStatus"] = "publish_ready"
    assert validate_canonical_timeline_public_input(document) == (
        "public-input-schema-invalid",
    )
