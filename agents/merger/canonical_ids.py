"""
DKB Merger - Canonical ID Policy Helpers
Stage B merged knowledgeにおける canonicalId の形式検証・分類helper。

docs/architecture/06_AI/Canonical_ID_Policy.md で定義した方針の実装側。
最重要の方針: **このモジュールはcanonicalIdを既存entityへ自動付与しない。**
提供するのは、(1) 既に存在するcanonicalIdの形式・重複を検証するvalidation、
(2) 将来「人間が確認したキーからcanonical IDを機械的に組み立てる」ツールの
土台となるhelper関数のみ。merge pipeline (character.py/location.py/.../
relationship.py/timeline.py) からは呼び出されない。

canonicalIdとして信頼できるのは、Parserの既知キャラクター辞書等
人間管理下の構造化ID (existing*Id) から解決された値、または
manual override (agents/merger/overrides.py) で人間が明示指定した値のみ
(Merged_Knowledge_Design.md §4.1)。名前一致だけの自動付与は行わない。

docs/architecture/06_AI/Canonical_ID_Policy.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .entity_base import sanitize_id_segment
from .models import MERGED_ENTITY_KEYS

# canonical IDとして許容する文字集合
# (docs/architecture/05_Parser/Identifier_Specification.md §2.3、
# schemas/merged_knowledge.schema.jsonのIdString定義と同一パターン)。
_CANONICAL_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_-]+$")

# entity.type (EntityType enum, schemas/merged_knowledge.schema.json) ->
# canonical IDの暫定prefix (Identifier_Specification.md §6, §7、
# Canonical_ID_Policy.md §9)。relationship/timeline_entryはcanonicalId
# を当面付与しない方針だが、将来設定された場合の形式チェック用に含める。
ENTITY_TYPE_TO_CANONICAL_PREFIX: dict[str, str] = {
    "character": "CHAR",
    "location": "LOC",
    "organization": "ORG",
    "item": "ITEM",
    "lore": "LORE",
    "event": "EVENT",
    "relationship": "REL",
    "timeline_entry": "TL",
}

_KNOWN_CANONICAL_PREFIXES = tuple(
    f"{prefix}_" for prefix in ENTITY_TYPE_TO_CANONICAL_PREFIX.values()
)

CANONICAL_ID_SOURCE_STRUCTURED_ID = "structured_id"
CANONICAL_ID_SOURCE_MANUAL_OVERRIDE = "manual_override"
CANONICAL_ID_SOURCE_UNKNOWN = "unknown"
CANONICAL_ID_SOURCE_NONE = "none"


def sanitize_canonical_id_segment(value: str) -> str:
    """canonical ID (`CHAR_<SLUG>`等) の`<SLUG>`部分に使える安全な断片へ変換する。

    agents/merger/entity_base.pyのsanitize_id_segmentと同じ正規化
    (非英数字->アンダースコア、大文字化) を再利用する
    (Identifier_Specification.md §2.3の許可文字集合に合わせるため)。
    """
    return sanitize_id_segment(value)


def build_canonical_id(entity_type: str, key: str) -> str:
    """人間が確認した安定キー (ローマ字表記等) からcanonical ID文字列を
    組み立てる。

    この関数はmerge pipelineから自動的には呼び出されない
    (Canonical_ID_Policy.md §6)。将来のmanual override作成支援ツール等の
    土台として提供するhelperであり、呼び出し元は人間の確認を経た`key`を
    渡す責任を持つ。

    Raises:
        ValueError: entity_typeがENTITY_TYPE_TO_CANONICAL_PREFIXに無い場合。
    """
    prefix = ENTITY_TYPE_TO_CANONICAL_PREFIX.get(entity_type)
    if prefix is None:
        raise ValueError(f"unknown entity_type for canonical ID: {entity_type!r}")

    segment = sanitize_canonical_id_segment(key)
    return f"{prefix}_{segment}"


def is_valid_canonical_id(value: Any) -> bool:
    """canonical IDとして形式上妥当かどうかを判定する。

    Identifier_Specification.md §2.3の許可文字集合 (A-Z, 0-9, _, -)、
    かつ既知のtype別prefix (CHAR_/LOC_/ORG_/ITEM_/LORE_/EVENT_/REL_/TL_)
    のいずれかで始まっていることを確認する。意味的な正しさ (実在する
    エンティティを正しく指しているか等) までは検証しない。
    """
    if not isinstance(value, str) or not value:
        return False
    if not _CANONICAL_ID_PATTERN.match(value):
        return False
    return value.startswith(_KNOWN_CANONICAL_PREFIXES)


def classify_canonical_id_source(entity: dict[str, Any]) -> str:
    """既存entityのcanonicalIdがどこから来たかをベストエフォートで分類する。

    per-fieldの正確な由来追跡は行っていない (fieldValues.canonicalId相当の
    provenanceをまだ持たないため)。以下の優先順位で推測する。

    1. canonicalId未設定 -> "none"
    2. status: merged かつ id == canonicalId -> "structured_id"
       (existing*Id経由でそのまま採用されたケース、entity_base.py
       _resolve_entity_identity参照)
    3. manualOverridesApplied が空でない -> "manual_override"
       (canonicalId自体が上書き対象だったとは限らないが、他に手がかりが
       無いため保守的にこう分類する)
    4. それ以外 -> "unknown" (status: unresolvedなのにcanonicalIdがある等、
       validate_canonical_idsがwarningとして検出すべきケース)
    """
    canonical_id = entity.get("canonicalId")
    if not canonical_id:
        return CANONICAL_ID_SOURCE_NONE

    if entity.get("status") == "merged" and entity.get("id") == canonical_id:
        return CANONICAL_ID_SOURCE_STRUCTURED_ID

    if entity.get("manualOverridesApplied"):
        return CANONICAL_ID_SOURCE_MANUAL_OVERRIDE

    return CANONICAL_ID_SOURCE_UNKNOWN


@dataclass
class CanonicalIdValidationResult:
    """validate_canonical_idsの結果 (report.canonicalIdSummaryに対応)。"""

    total_assigned: int = 0
    duplicate_count: int = 0
    invalid_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "totalAssigned": self.total_assigned,
            "duplicateCount": self.duplicate_count,
            "invalidCount": self.invalid_count,
            "warnings": list(self.warnings),
        }


def _check_single_canonical_id(
    entity: dict[str, Any], result: CanonicalIdValidationResult
) -> None:
    canonical_id = entity["canonicalId"]
    entity_id = entity.get("id", "?")
    entity_type = entity.get("type", "")

    if not is_valid_canonical_id(canonical_id):
        result.invalid_count += 1
        result.warnings.append(
            f"{entity_id}: canonicalId '{canonical_id}' の形式が不正です"
        )
    else:
        expected_prefix = ENTITY_TYPE_TO_CANONICAL_PREFIX.get(entity_type)
        if expected_prefix and not canonical_id.startswith(f"{expected_prefix}_"):
            result.invalid_count += 1
            result.warnings.append(
                f"{entity_id}: canonicalId '{canonical_id}' はentity type "
                f"'{entity_type}' に期待される接頭辞 '{expected_prefix}_' で"
                "始まっていません"
            )

    if entity.get("status") == "unresolved":
        result.warnings.append(
            f"{entity_id}: status=unresolvedのentityにcanonicalId "
            f"'{canonical_id}' が設定されています"
        )


def validate_canonical_ids(collection: dict[str, Any]) -> CanonicalIdValidationResult:
    """collection内のcanonicalIdについて、形式・重複・unresolvedとの整合性を
    検証する (Canonical_ID_Policy.md §9)。

    検証するのは既に存在するcanonicalIdのみで、未設定のentityへ新たに
    canonicalIdを付与することはしない。
    """
    result = CanonicalIdValidationResult()
    entities_by_key: dict[str, list[dict[str, Any]]] = collection.get("entities", {})

    seen_within_type: dict[str, dict[str, int]] = {}
    seen_global: dict[str, int] = {}

    for array_key in MERGED_ENTITY_KEYS:
        for entity in entities_by_key.get(array_key, []) or []:
            canonical_id = entity.get("canonicalId")
            if not canonical_id:
                continue

            result.total_assigned += 1
            _check_single_canonical_id(entity, result)

            entity_type = entity.get("type", "")
            type_bucket = seen_within_type.setdefault(entity_type, {})
            type_bucket[canonical_id] = type_bucket.get(canonical_id, 0) + 1
            seen_global[canonical_id] = seen_global.get(canonical_id, 0) + 1

    duplicate_ids: set[str] = set()
    for entity_type, bucket in seen_within_type.items():
        for canonical_id, count in bucket.items():
            if count > 1:
                duplicate_ids.add(canonical_id)
                result.warnings.append(
                    f"canonicalId '{canonical_id}' がentity type "
                    f"'{entity_type}' 内で{count}件重複しています"
                )
    for canonical_id, count in seen_global.items():
        if count > 1 and canonical_id not in duplicate_ids:
            duplicate_ids.add(canonical_id)
            result.warnings.append(
                f"canonicalId '{canonical_id}' が複数のentity typeにまたがって"
                f"{count}件重複しています"
            )

    result.duplicate_count = len(duplicate_ids)
    return result
