"""Release-scope reportのrevisionとdigestは完全終端で照合する。"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"

PATTERN_CASES = [
    (
        "release_scope_normalization_report.schema.json",
        ("properties", "sourceRevision"),
        "a" * 40,
    ),
    (
        "release_scope_normalization_report.schema.json",
        ("properties", "manifestSha256"),
        "b" * 64,
    ),
    (
        "release_scope_knowledge_report.schema.json",
        ("properties", "sourceRevision"),
        "a" * 40,
    ),
    (
        "release_scope_knowledge_report.schema.json",
        ("properties", "normalizationReportSha256"),
        "b" * 64,
    ),
    (
        "release_scope_knowledge_report.schema.json",
        ("properties", "normalizedTreeSha256"),
        "b" * 64,
    ),
    (
        "release_scope_curation_readiness_report.schema.json",
        ("properties", "sourceRevision"),
        "a" * 40,
    ),
    (
        "release_scope_curation_readiness_report.schema.json",
        ("definitions", "digest"),
        "b" * 64,
    ),
]


@pytest.mark.parametrize(("schema_name", "path", "valid"), PATTERN_CASES)
def test_release_scope_report_pattern_requires_true_end(schema_name, path, valid):
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    for key in path:
        schema = schema[key]
    validator = Draft7Validator(schema)

    assert validator.is_valid(valid)
    for terminator in ("\n", "\r", "\r\n", "\u2028", "\u2029"):
        assert not validator.is_valid(valid + terminator)
