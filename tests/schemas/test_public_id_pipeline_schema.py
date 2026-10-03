"""Public IDの形式がmanifestからWikiまでの3層で一致することを確認する。"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from referencing import Registry, Resource

ROOT = Path(__file__).parent.parent.parent
PUBLIC_ID_FIELDS = ("publicStoryId", "publicEpisodeId")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(params=("normalized", "extraction", "merged"))
def schema_case(request):
    stage = request.param
    if stage == "normalized":
        document = _load_json(
            ROOT
            / "tests"
            / "fixtures"
            / "internal_review_evidence_packet"
            / "generator_input"
            / "normalized"
            / "test_story.json"
        )
        schema = _load_json(ROOT / "schemas" / "story.schema.json")
        validator = Draft7Validator(schema)
        field_locations = {
            "publicStoryId": (document["metadata"], ["metadata", "publicStoryId"]),
            "publicEpisodeId": (
                document["episodes"][0]["metadata"],
                ["episodes", 0, "metadata", "publicEpisodeId"],
            ),
        }
    elif stage == "extraction":
        document = _load_json(
            ROOT
            / "tests"
            / "fixtures"
            / "extraction"
            / "minimal_episode_extraction.json"
        )
        schema = _load_json(ROOT / "schemas" / "extraction.schema.json")
        validator = Draft7Validator(schema)
        field_locations = {field: (document, [field]) for field in PUBLIC_ID_FIELDS}
    else:
        document = _load_json(
            ROOT
            / "tests"
            / "fixtures"
            / "merged_knowledge"
            / "minimal_merged_collection.json"
        )
        schema = _load_json(
            ROOT / "schemas" / "merged_knowledge_collection.schema.json"
        )
        entity_schema = _load_json(ROOT / "schemas" / "merged_knowledge.schema.json")
        registry = Registry().with_resource(
            entity_schema["$id"], Resource.from_contents(entity_schema)
        )
        validator = Draft7Validator(schema, registry=registry)
        field_locations = {
            field: (document["sourceDocuments"][0], ["sourceDocuments", 0, field])
            for field in PUBLIC_ID_FIELDS
        }
    return validator, document, field_locations


@pytest.mark.parametrize("field", PUBLIC_ID_FIELDS)
@pytest.mark.parametrize("value", [None, "PUBLIC_TEST_001", "PUBLIC_TEST_001_E01"])
def test_public_id_valid_values_are_preserved(schema_case, field, value):
    validator, document, locations = schema_case
    target, _ = locations[field]
    target[field] = value

    assert list(validator.iter_errors(document)) == []


@pytest.mark.parametrize("field", PUBLIC_ID_FIELDS)
@pytest.mark.parametrize(
    "value", ["", "../index", r"..\index", "public_test", "PUBLIC-TEST", "PUBLIC TEST"]
)
def test_public_id_invalid_values_are_rejected(schema_case, field, value):
    validator, document, locations = schema_case
    target, expected_path = locations[field]
    target[field] = value

    errors = list(validator.iter_errors(document))
    assert any(list(error.path) == expected_path for error in errors)


@pytest.mark.parametrize("field", PUBLIC_ID_FIELDS)
def test_public_id_fields_remain_optional(schema_case, field):
    validator, document, locations = schema_case
    target, _ = locations[field]
    target.pop(field, None)

    assert list(validator.iter_errors(document)) == []
