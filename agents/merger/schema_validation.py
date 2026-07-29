"""Cross-file JSON Schema validation helpers for merged collections."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource

DRAFT7_SCHEMA_ID = "http://json-schema.org/draft-07/schema#"
MERGED_COLLECTION_SCHEMA_ID = (
    "https://detariki-kb/schemas/merged_knowledge_collection.schema.json"
)
MERGED_ENTITY_SCHEMA_ID = "https://detariki-kb/schemas/merged_knowledge.schema.json"


class MergedSchemaConfigurationError(ValueError):
    """Raised when the merged collection schema set cannot be configured."""


def _require_schema_id(
    schema: dict[str, Any],
    *,
    expected_id: str,
    label: str,
) -> None:
    schema_id = schema.get("$id")
    if schema_id != expected_id:
        raise MergedSchemaConfigurationError(
            f"{label} schema $id must be {expected_id!r}, got {schema_id!r}"
        )


def _require_schema_dialect(
    schema: dict[str, Any],
    *,
    label: str,
) -> None:
    schema_dialect = schema.get("$schema")
    if schema_dialect != DRAFT7_SCHEMA_ID:
        raise MergedSchemaConfigurationError(
            f"{label} schema $schema must be "
            f"{DRAFT7_SCHEMA_ID!r}, got {schema_dialect!r}"
        )


def build_merged_collection_validator(
    collection_schema: dict[str, Any],
    merged_entity_schema: dict[str, Any],
) -> Draft7Validator:
    """Build an offline validator with the merged entity schema registered."""
    _require_schema_id(
        collection_schema,
        expected_id=MERGED_COLLECTION_SCHEMA_ID,
        label="merged collection",
    )
    _require_schema_id(
        merged_entity_schema,
        expected_id=MERGED_ENTITY_SCHEMA_ID,
        label="merged entity",
    )
    _require_schema_dialect(collection_schema, label="merged collection")
    _require_schema_dialect(merged_entity_schema, label="merged entity")
    try:
        Draft7Validator.check_schema(collection_schema)
        Draft7Validator.check_schema(merged_entity_schema)
    except SchemaError as exc:
        raise MergedSchemaConfigurationError(
            f"invalid merged schema configuration: {exc.message}"
        ) from exc

    registry = Registry().with_resource(
        MERGED_ENTITY_SCHEMA_ID,
        Resource.from_contents(merged_entity_schema),
    )
    return Draft7Validator(collection_schema, registry=registry)


def _load_schema(path: Path, *, label: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as file:
            schema = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise MergedSchemaConfigurationError(
            f"could not load {label} schema: {exc}"
        ) from exc
    if not isinstance(schema, dict):
        raise MergedSchemaConfigurationError(f"{label} schema root must be an object")
    return schema


def load_merged_collection_validator(
    collection_schema_path: Path,
    merged_entity_schema_path: Path | None = None,
) -> Draft7Validator:
    """Load sibling schemas and build an offline merged collection validator."""
    entity_path = merged_entity_schema_path or collection_schema_path.with_name(
        "merged_knowledge.schema.json"
    )
    collection_schema = _load_schema(
        collection_schema_path,
        label="merged collection",
    )
    merged_entity_schema = _load_schema(
        entity_path,
        label="merged entity",
    )
    return build_merged_collection_validator(
        collection_schema,
        merged_entity_schema,
    )
