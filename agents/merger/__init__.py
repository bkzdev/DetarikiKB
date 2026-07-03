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
ないため常にstatus: unresolved)。canonical ID本格割り当て・manual override
適用・conflict解決の本格実装はまだ行わない。

docs/architecture/06_AI/Merged_Knowledge_Design.md
"""

from .character import build_character_entities
from .engine import InputValidationResult, MergeEngine
from .event import build_event_entities
from .input_resolver import ResolvedInputEntry, resolve_input_entries
from .item import build_item_entities
from .location import build_location_entities
from .lore import build_lore_entities
from .models import (
    CANDIDATE_ARRAY_KEYS,
    COLLECTION_DOCUMENT_TYPE,
    COLLECTION_SCHEMA_VERSION,
    INPUT_STATUS_INVALID,
    INPUT_STATUS_SKIPPED,
    INPUT_STATUS_VALID,
    MERGE_ENGINE_VERSION,
    MERGED_ENTITY_KEYS,
    InputResult,
    MergeReport,
)
from .organization import build_organization_entities
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
    "CANDIDATE_ARRAY_KEYS",
    "MERGED_ENTITY_KEYS",
    "COLLECTION_SCHEMA_VERSION",
    "COLLECTION_DOCUMENT_TYPE",
    "MERGE_ENGINE_VERSION",
    "INPUT_STATUS_VALID",
    "INPUT_STATUS_INVALID",
    "INPUT_STATUS_SKIPPED",
]
