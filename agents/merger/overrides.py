"""
DKB Merger - Manual Overrides Loader
Stage B merged knowledge collectionに対して、人間が用意したmanual override
JSON (schemas/manual_overrides.schema.json) を読み込み・検証し、最小限の
補正を適用する。

manual overrideは、AI抽出・rule-based抽出やmerge結果を直接書き換えるのでは
なく、「人間が明示した補正レイヤー」として後から重ねて適用するものとして
扱う。適用してもevidenceRefs/sourceCandidates/extractionRunRefs/conflicts
(根拠情報) は消さない (Merged_Knowledge_Design.md §8.1, §8.3)。

対象entityの特定は保守的に行う。優先順位:
1. merged entity id (entity["id"]) が一致
2. canonicalId (entity["canonicalId"]) が一致
3. 元Stage A candidate id (entity["sourceCandidates"][].candidateId) が一致
名前 (displayName/aliases) 一致だけでは絶対に適用しない (誤爆防止)。

今回サポートするoperationはset_field/add_alias/remove_aliasのみ。
merge_entities/split_entity/ignore_candidate/resolve_conflict/
set_relationship_type/set_timeline_orderは今回のスコープ外 (TASKS.md参照)。

docs/architecture/06_AI/Merged_Knowledge_Design.md §8
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

_PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_OVERRIDES_SCHEMA_PATH = (
    _PROJECT_ROOT / "schemas" / "manual_overrides.schema.json"
)

# manual_overrides.schema.jsonのtargetType -> merged knowledge collectionの
# entities配下キー (schemas/merged_knowledge_collection.schema.json)
_TARGET_TYPE_TO_ENTITIES_KEY = {
    "character": "characters",
    "location": "locations",
    "organization": "organizations",
    "item": "items",
    "lore": "lore",
    "event": "events",
    "relationship": "relationships",
    "timeline_entry": "timeline",
}

# 今回サポートするoperation (schemas/manual_overrides.schema.jsonのenumの
# うち一部)。他のoperationはschema上は許容されるが、今回のloaderでは
# "サポート外"としてskip扱いにする。
_SUPPORTED_OPERATIONS = frozenset({"set_field", "add_alias", "remove_alias"})

# set_fieldで直接上書きを許可するトップレベルフィールド。
# aliasesはadd_alias/remove_alias専用操作があるため、set_fieldでの直接指定
# は許可しない (配列の重複・整合性をここで一元管理するため)。
_ALLOWED_SET_FIELDS = frozenset({"displayName", "status", "canonicalId"})

_VALID_STATUSES = frozenset({"merged", "unresolved", "conflict", "deprecated"})

_FIELD_VALUES_PREFIX = "fieldValues."


@dataclass
class OverrideResult:
    """1件のoverride適用結果 (merge report内のmanualOverrides.resultsの
    1エントリに対応)。
    """

    override_id: str
    target_id: str | None
    status: str  # "applied" | "skipped" | "error"
    reason: str
    fields_changed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overrideId": self.override_id,
            "targetId": self.target_id,
            "status": self.status,
            "reason": self.reason,
            "fieldsChanged": list(self.fields_changed),
        }


def load_manual_overrides_schema(
    schema_path: Path = DEFAULT_OVERRIDES_SCHEMA_PATH,
) -> dict[str, Any]:
    """manual_overrides.schema.jsonを読み込む。"""
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def load_manual_overrides(path: Path) -> dict[str, Any]:
    """manual override JSONファイルを読み込む。

    ファイルI/O・JSONパースエラーは呼び出し側 (CLI) で処理する想定のため、
    ここでは例外を握りつぶさない。
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_manual_overrides(
    data: dict[str, Any],
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """manual override JSONをschemas/manual_overrides.schema.jsonで検証する。

    戻り値はエラーメッセージの一覧 (空リストなら検証成功)。
    """
    if schema is None:
        schema = load_manual_overrides_schema()
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return [
        f"{'/'.join(str(p) for p in err.path) or '(root)'}: {err.message}"
        for err in errors
    ]


def _resolve_override_target(
    collection: dict[str, Any], target_type: str | None, target_id: str | None
) -> dict[str, Any] | None:
    """override対象のentityを、mergedId/canonicalId/candidate idの優先順位で
    保守的に特定する。名前 (displayName/aliases) では絶対に探さない。
    """
    entities_key = _TARGET_TYPE_TO_ENTITIES_KEY.get(target_type or "")
    if entities_key is None or not target_id:
        return None

    candidates = collection.get("entities", {}).get(entities_key, []) or []

    for entity in candidates:
        if entity.get("id") == target_id:
            return entity
    for entity in candidates:
        if entity.get("canonicalId") == target_id:
            return entity
    for entity in candidates:
        for source_candidate in entity.get("sourceCandidates", []) or []:
            if source_candidate.get("candidateId") == target_id:
                return entity

    return None


def _apply_set_field(
    entity: dict[str, Any], override: dict[str, Any]
) -> tuple[str, str, list[str]]:
    """set_field operationを適用する。戻り値: (status, reason, fieldsChanged)。"""
    field_name = override.get("field")
    value = override.get("value")

    if field_name in _ALLOWED_SET_FIELDS:
        if field_name == "status" and value not in _VALID_STATUSES:
            return "error", f"invalid status value: {value!r}", []
        entity[field_name] = value
        return "applied", "set_field", [field_name]

    if field_name and field_name.startswith(_FIELD_VALUES_PREFIX):
        key = field_name[len(_FIELD_VALUES_PREFIX) :]
        if not key:
            return "error", "fieldValues.<key> requires a non-empty key", []
        entity.setdefault("fieldValues", {})[key] = {
            "value": value,
            "sourceType": "manual",
            "confidence": 1.0,
            "isManualOverride": True,
        }
        return "applied", "set_field", [field_name]

    return "error", f"field '{field_name}' is not allowed for set_field", []


def _apply_add_alias(
    entity: dict[str, Any], override: dict[str, Any]
) -> tuple[str, str, list[str]]:
    alias = override.get("alias")
    if not alias:
        return "error", "add_alias requires 'alias'", []

    aliases = entity.setdefault("aliases", [])
    if alias not in aliases:
        aliases.append(alias)
    return "applied", "add_alias", ["aliases"]


def _apply_remove_alias(
    entity: dict[str, Any], override: dict[str, Any]
) -> tuple[str, str, list[str]]:
    alias = override.get("alias")
    if not alias:
        return "error", "remove_alias requires 'alias'", []

    aliases = entity.get("aliases", []) or []
    if alias in aliases:
        aliases.remove(alias)
        return "applied", "remove_alias", ["aliases"]
    return "skipped", f"alias '{alias}' is not present", []


_OPERATION_HANDLERS = {
    "set_field": _apply_set_field,
    "add_alias": _apply_add_alias,
    "remove_alias": _apply_remove_alias,
}


def _apply_one_override(
    collection: dict[str, Any], override: dict[str, Any]
) -> OverrideResult:
    override_id = override.get("overrideId", "UNKNOWN")
    operation = override.get("operation")
    target_type = override.get("targetType")
    target_id = override.get("targetId")

    if operation not in _SUPPORTED_OPERATIONS:
        return OverrideResult(
            override_id,
            target_id,
            "skipped",
            f"operation '{operation}' is not supported by this loader yet",
        )

    entity = _resolve_override_target(collection, target_type, target_id)
    if entity is None:
        return OverrideResult(
            override_id,
            target_id,
            "skipped",
            f"target not found (targetType={target_type!r}, targetId={target_id!r})",
        )

    handler = _OPERATION_HANDLERS[operation]
    status, reason, fields_changed = handler(entity, override)

    if status == "applied":
        entity.setdefault("manualOverridesApplied", [])
        if override_id not in entity["manualOverridesApplied"]:
            entity["manualOverridesApplied"].append(override_id)

    return OverrideResult(override_id, target_id, status, reason, fields_changed)


def apply_manual_overrides(
    collection: dict[str, Any], overrides_data: dict[str, Any]
) -> tuple[dict[str, Any], list[OverrideResult]]:
    """merged knowledge collectionにmanual overrideを適用する。

    元のcollectionは変更せず (deepcopyして返す)、evidenceRefs/
    sourceCandidates/extractionRunRefs/conflictsは一切変更しない。
    戻り値: (適用後のcollection, override結果一覧)。
    """
    updated = copy.deepcopy(collection)
    results = [
        _apply_one_override(updated, override)
        for override in overrides_data.get("overrides", []) or []
    ]
    return updated, results


def build_manual_overrides_report(
    override_files: list[str], results: list[OverrideResult]
) -> dict[str, Any]:
    """merge reportへ埋め込むmanualOverridesブロックを組み立てる。"""
    applied = sum(1 for r in results if r.status == "applied")
    skipped = sum(1 for r in results if r.status == "skipped")
    errors = sum(1 for r in results if r.status == "error")
    return {
        "enabled": True,
        "overrideFiles": list(override_files),
        "appliedCount": applied,
        "skippedCount": skipped,
        "errorCount": errors,
        "results": [r.to_dict() for r in results],
    }
