"""
DKB Merger Package

Usage:
    from agents.merger import MergeEngine

Stage A episode_extraction JSON群 (複数ファイル・ディレクトリ・glob
パターンに対応) を検証し、Stage B merged knowledge collectionを生成する。
Character/Location/Organizationは構造化ID (existing*Id) がある場合のみ
最小ルールでmerged entityへ変換する (Merged_Knowledge_Design.md §5.1〜
§5.3)。Item/Lore/Event/Relationship/Timelineの本格merge・canonical ID
本格割り当て・manual override適用・conflict解決の本格実装はまだ行わない。

docs/architecture/06_AI/Merged_Knowledge_Design.md
"""

from .character import build_character_entities
from .engine import InputValidationResult, MergeEngine
from .input_resolver import ResolvedInputEntry, resolve_input_entries
from .location import build_location_entities
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
    "CANDIDATE_ARRAY_KEYS",
    "MERGED_ENTITY_KEYS",
    "COLLECTION_SCHEMA_VERSION",
    "COLLECTION_DOCUMENT_TYPE",
    "MERGE_ENGINE_VERSION",
    "INPUT_STATUS_VALID",
    "INPUT_STATUS_INVALID",
    "INPUT_STATUS_SKIPPED",
]
