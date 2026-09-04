"""Review済みCanonical Timeline public input envelopeを構築・検証する。"""

from __future__ import annotations

import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry, Resource

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_NAMES = (
    "canonical_timeline_public_projection.schema.json",
    "canonical_timeline_public_preflight_record.schema.json",
    "canonical_timeline_public_input_review.schema.json",
    "canonical_timeline_public_input.schema.json",
)


class PublicInputError(ValueError):
    """公開入力をfail-closedに拒否した理由をcodeだけで表す。"""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    """whitespaceやobject順に依存しないcanonical JSON bytesを返す。"""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_json_sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


@lru_cache(maxsize=1)
def _validators() -> dict[str, Draft7Validator]:
    schemas = [
        json.loads((_PROJECT_ROOT / "schemas" / name).read_text(encoding="utf-8"))
        for name in _SCHEMA_NAMES
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


def _validate(schema_name: str, value: Any, code: str) -> None:
    schema_id = f"https://detariki-kb/schemas/{schema_name}"
    try:
        errors = list(_validators()[schema_id].iter_errors(value))
    except Exception as exc:
        raise PublicInputError("schema-unavailable") from exc
    if errors:
        raise PublicInputError(code)


def validate_canonical_timeline_public_input(
    document: dict[str, Any],
) -> tuple[str, ...]:
    """Envelopeのschemaとpayload digestを匿名codeで検証する。"""
    findings: list[str] = []
    try:
        _validate(
            "canonical_timeline_public_input.schema.json",
            document,
            "public-input-schema-invalid",
        )
    except PublicInputError as exc:
        return (exc.code,)
    if document["payloadSha256"] != canonical_json_sha256(document["projection"]):
        findings.append("public-input-payload-digest-mismatch")
    return tuple(findings)


def build_canonical_timeline_public_input(
    projection: dict[str, Any],
    review: dict[str, Any],
    preflight_report: dict[str, Any],
    expected_projection_sha256: str,
) -> dict[str, Any]:
    """clean preflightとapproved reviewに束縛されたpublic-safe envelopeを返す。"""
    _validate(
        "canonical_timeline_public_projection.schema.json",
        projection,
        "projection-schema-invalid",
    )
    _validate(
        "canonical_timeline_public_input_review.schema.json",
        review,
        "review-schema-invalid",
    )
    _validate(
        "canonical_timeline_public_preflight_record.schema.json",
        preflight_report,
        "preflight-record-schema-invalid",
    )

    digest = canonical_json_sha256(projection)
    if expected_projection_sha256 != digest:
        raise PublicInputError("expected-projection-digest-mismatch")
    if review["projectionSha256"] != digest:
        raise PublicInputError("review-projection-digest-mismatch")
    if review["preflightInputDigests"]["projection"] != digest:
        raise PublicInputError("preflight-projection-digest-mismatch")
    if review["preflightInputDigests"] != preflight_report["inputDigests"]:
        raise PublicInputError("preflight-input-digests-mismatch")
    if review["decision"] != "approved_for_build":
        raise PublicInputError("review-not-approved")
    if preflight_report["status"] != "clean" or preflight_report["findings"]:
        raise PublicInputError("preflight-not-clean")

    checks = copy.deepcopy(review["checks"])
    document = {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_public_input",
        "visibility": "public",
        "buildStatus": "approved_for_build",
        "contentType": "canonical_timeline_public_projection",
        "payloadSha256": digest,
        "pushReview": {
            "decision": "approved_for_build",
            "reviewedAt": review["reviewedAt"],
            "reviewerType": "human",
            "checks": checks,
        },
        "projection": copy.deepcopy(projection),
    }
    findings = validate_canonical_timeline_public_input(document)
    if findings:
        raise PublicInputError(findings[0])
    return document
