"""公開build・release recordの識別子とpathは末尾改行を許容しない。"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

SCHEMAS = Path(__file__).parent.parent.parent / "schemas"

PATTERN_CASES = [
    (
        "public_site_manifest.schema.json",
        ("properties", "sourceRevision", "properties", "value"),
        "a" * 40,
    ),
    (
        "public_site_manifest.schema.json",
        ("properties", "generator", "properties", "version"),
        "0.0.57",
    ),
    (
        "public_site_manifest.schema.json",
        ("properties", "output", "properties", "routes", "items"),
        "/stories/PUBLIC_TEST/",
    ),
    (
        "public_site_manifest.schema.json",
        ("properties", "output", "properties", "files", "items", "properties", "path"),
        "stories/PUBLIC_TEST/index.html",
    ),
    ("public_site_manifest.schema.json", ("definitions", "Sha256"), "b" * 64),
    ("public_rollback_record.schema.json", ("properties", "sourceSha"), "a" * 40),
    ("public_rollback_record.schema.json", ("properties", "treeSha256"), "b" * 64),
    (
        "public_rollback_record.schema.json",
        ("properties", "publicUrl"),
        "https://example.invalid/",
    ),
    (
        "v1_release_candidate_record.schema.json",
        (
            "properties",
            "production",
            "properties",
            "knownRollback",
            "properties",
            "publicUrl",
        ),
        "https://example.invalid/",
    ),
    ("v1_release_candidate_record.schema.json", ("definitions", "sha1"), "a" * 40),
    ("v1_release_candidate_record.schema.json", ("definitions", "sha256"), "b" * 64),
    (
        "v1_release_candidate_record.schema.json",
        ("definitions", "runUrl"),
        "https://github.com/example/repo/actions/runs/123",
    ),
]


@pytest.mark.parametrize(("schema_name", "path", "valid"), PATTERN_CASES)
def test_public_release_pattern_requires_true_end(schema_name, path, valid):
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    for key in path:
        schema = schema[key]
    validator = Draft7Validator(schema)

    assert validator.is_valid(valid)
    for terminator in ("\n", "\r", "\r\n", "\u2028", "\u2029"):
        assert not validator.is_valid(valid + terminator)


@pytest.mark.parametrize("path", ["/index.html", "../index.html", "a/../index.html"])
def test_public_site_file_path_still_rejects_absolute_and_parent_paths(path):
    schema = json.loads(
        (SCHEMAS / "public_site_manifest.schema.json").read_text(encoding="utf-8")
    )
    file_path_schema = schema["properties"]["output"]["properties"]["files"]["items"][
        "properties"
    ]["path"]

    assert not Draft7Validator(file_path_schema).is_valid(path)
