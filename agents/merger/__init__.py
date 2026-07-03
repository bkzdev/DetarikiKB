"""
DKB Merger Package

Usage:
    from agents.merger import MergeEngine

Stage A episode_extraction JSON群 (複数ファイル・ディレクトリ・glob
パターンに対応) を検証し、Stage B merged knowledge collectionを生成する。
Character/Location/Organization/Item/Lore/Eventは構造化ID (existing*Id)
がある場合のみ最小ルールでmerged entityへ変換する
(Merged_Knowledge_Design.md §5.1〜§5.6)。Relationshipはsource/targetの
両端をmerged entity IDへ解決できた候補のみ最小ルールでmerged relationship
へ変換する (§6。解決できない候補はreport.warningsに記録し、無理に確定
しない)。Timelineはsource TimelineID/scope+kind+orderValueでの保守的な
merge最小ルールを適用する (§7。Stage Bでは順序の確定・canonical化は行わ
ないため常にstatus: unresolved)。

agents.merger.overrides で、merge後のcollectionへmanual override
(schemas/manual_overrides.schema.json) を適用できる (§8。displayName/
status/canonicalIdの上書き、aliasesの追加・削除のみ対応)。canonical ID
本格割り当て・高度なconflict解決の本格実装はまだ行わない。

merge reportは、type別・入力ファイル別の内訳 (mergedEntityCounts/
unresolvedEntityCounts/conflictCounts/warningCounts/entityTypeSummaries/
inputSummaries) まで含める (§11.2)。

agents.merger.canonical_ids で、canonicalIdの形式・重複をvalidationする
(docs/architecture/06_AI/Canonical_ID_Policy.md)。既存entityへの
canonical ID自動付与・大量生成はまだ行わない。

docs/architecture/06_AI/Merged_Knowledge_Design.md
"""

from .canonical_ids import (
    CANONICAL_ID_SOURCE_MANUAL_OVERRIDE,
    CANONICAL_ID_SOURCE_NONE,
    CANONICAL_ID_SOURCE_STRUCTURED_ID,
    CANONICAL_ID_SOURCE_UNKNOWN,
    ENTITY_TYPE_TO_CANONICAL_PREFIX,
    CanonicalIdValidationResult,
    build_canonical_id,
    classify_canonical_id_source,
    is_valid_canonical_id,
    sanitize_canonical_id_segment,
    validate_canonical_ids,
)
from .character import build_character_entities
from .engine import InputValidationResult, MergeEngine
from .event import build_event_entities
from .input_resolver import ResolvedInputEntry, resolve_input_entries
from .item import build_item_entities
from .location import build_location_entities
from .lore import build_lore_entities
from .models import (
    CANDIDATE_ARRAY_KEYS,
    CANDIDATE_TO_MERGED_KEY,
    COLLECTION_DOCUMENT_TYPE,
    COLLECTION_SCHEMA_VERSION,
    INPUT_STATUS_INVALID,
    INPUT_STATUS_SKIPPED,
    INPUT_STATUS_VALID,
    MERGE_ENGINE_VERSION,
    MERGED_ENTITY_KEYS,
    MERGED_TO_CANDIDATE_KEY,
    InputResult,
    MergeReport,
)
from .organization import build_organization_entities
from .overrides import (
    OverrideResult,
    apply_manual_overrides,
    build_manual_overrides_report,
    load_manual_overrides,
    load_manual_overrides_schema,
    validate_manual_overrides,
)
from .relationship import build_relationship_entities
from .timeline import build_timeline_entities

__all__ = [
    "MergeEngine",
    "MergeReport",
    "InputResult",
    "InputValidationResult",
    "ResolvedInputEntry",
    "resolve_input_entries",
    "build_character_entities",
    "build_location_entities",
    "build_organization_entities",
    "build_item_entities",
    "build_lore_entities",
    "build_event_entities",
    "build_relationship_entities",
    "build_timeline_entities",
    "OverrideResult",
    "load_manual_overrides",
    "load_manual_overrides_schema",
    "validate_manual_overrides",
    "apply_manual_overrides",
    "build_manual_overrides_report",
    "CANDIDATE_ARRAY_KEYS",
    "MERGED_ENTITY_KEYS",
    "CANDIDATE_TO_MERGED_KEY",
    "MERGED_TO_CANDIDATE_KEY",
    "COLLECTION_SCHEMA_VERSION",
    "COLLECTION_DOCUMENT_TYPE",
    "MERGE_ENGINE_VERSION",
    "INPUT_STATUS_VALID",
    "INPUT_STATUS_INVALID",
    "INPUT_STATUS_SKIPPED",
    "CanonicalIdValidationResult",
    "build_canonical_id",
    "classify_canonical_id_source",
    "is_valid_canonical_id",
    "sanitize_canonical_id_segment",
    "validate_canonical_ids",
    "ENTITY_TYPE_TO_CANONICAL_PREFIX",
    "CANONICAL_ID_SOURCE_STRUCTURED_ID",
    "CANONICAL_ID_SOURCE_MANUAL_OVERRIDE",
    "CANONICAL_ID_SOURCE_UNKNOWN",
    "CANONICAL_ID_SOURCE_NONE",
]
