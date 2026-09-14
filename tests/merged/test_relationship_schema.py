"""Relationship public v1 standalone schema tests."""

import json
from pathlib import Path

from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "relationship.schema.json"


def _validator() -> Draft7Validator:
    with open(SCHEMA_PATH, encoding="utf-8") as file:
        schema = json.load(file)
    Draft7Validator.check_schema(schema)
    return Draft7Validator(schema)


def _relationship(**overrides):
    value = {
        "relationshipType": "MEMBER_OF",
        "normalizedRelationshipType": "member_of",
        "taxonomyState": "formal_v1",
        "sourceEntityType": "character",
        "targetEntityType": "organization",
        "direction": "source_to_target",
        "sourceType": "script",
        "publicationStatus": "eligible",
    }
    value.update(overrides)
    return value


def test_public_v1_contract_accepts_eligible_member_of():
    assert list(_validator().iter_errors(_relationship())) == []


def test_eligible_relationship_rejects_ai_source():
    errors = list(_validator().iter_errors(_relationship(sourceType="ai_extracted")))
    assert errors


def test_review_required_preserves_unrecognized_free_string():
    value = _relationship(
        relationshipType="SOME_FUTURE_TYPE",
        normalizedRelationshipType="some_future_type",
        taxonomyState="unrecognized",
        sourceEntityType="event",
        targetEntityType="lore",
        direction="bidirectional",
        sourceType="ai_inferred",
        publicationStatus="review_required",
    )
    assert list(_validator().iter_errors(value)) == []
