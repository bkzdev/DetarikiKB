"""公開Timelineの識別値とlabelは末尾の改行を受け入れない。"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"

PATTERN_CASES = [
    (
        "canonical_timeline_public_input.schema.json",
        ("properties", "payloadSha256"),
        "a" * 64,
    ),
    (
        "canonical_timeline_public_input.schema.json",
        ("properties", "pushReview", "properties", "reviewedAt"),
        "2099-01-01T00:00:00Z",
    ),
    (
        "canonical_timeline_public_input_review.schema.json",
        ("properties", "reviewedAt"),
        "2099-01-01T00:00:00Z",
    ),
    (
        "canonical_timeline_public_input_review.schema.json",
        ("definitions", "Sha256"),
        "a" * 64,
    ),
    (
        "canonical_timeline_public_preflight_record.schema.json",
        ("definitions", "Sha256"),
        "a" * 64,
    ),
    (
        "canonical_timeline_public_projection.schema.json",
        ("definitions", "PublicLabel"),
        "公開確認済みラベル",
    ),
    (
        "canonical_timeline_public_projection.schema.json",
        ("definitions", "TimelineComponent", "properties", "componentKey"),
        "component-0001",
    ),
]


@pytest.mark.parametrize(("schema_name", "path", "valid"), PATTERN_CASES)
def test_public_timeline_pattern_requires_true_end(schema_name, path, valid):
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    for key in path:
        schema = schema[key]
    validator = Draft7Validator(schema)

    assert validator.is_valid(valid)
    for terminator in ("\n", "\r", "\r\n", "\u2028", "\u2029"):
        assert not validator.is_valid(valid + terminator)
