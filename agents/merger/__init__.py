"""
DKB Merger Package

Usage:
    from agents.merger import MergeEngine

Stage A episode_extraction JSON群 (複数ファイル・ディレクトリ・glob
パターンに対応) を検証し、Stage B merged knowledge collectionの最小構造と
merge report骨格を生成する (merge engine skeleton)。本格的なcandidate
merge・canonical ID割り当て・manual override適用・conflict解決はまだ
実装しない。

docs/architecture/06_AI/Merged_Knowledge_Design.md
"""

from .engine import InputValidationResult, MergeEngine
from .input_resolver import ResolvedInputEntry, resolve_input_entries
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

__all__ = [
    "MergeEngine",
    "MergeReport",
    "InputResult",
    "InputValidationResult",
    "ResolvedInputEntry",
    "resolve_input_entries",
    "CANDIDATE_ARRAY_KEYS",
    "MERGED_ENTITY_KEYS",
    "COLLECTION_SCHEMA_VERSION",
    "COLLECTION_DOCUMENT_TYPE",
    "MERGE_ENGINE_VERSION",
    "INPUT_STATUS_VALID",
    "INPUT_STATUS_INVALID",
    "INPUT_STATUS_SKIPPED",
]
