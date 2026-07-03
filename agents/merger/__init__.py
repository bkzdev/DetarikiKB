"""
DKB Merger Package

Usage:
    from agents.merger import MergeEngine

Stage A episode_extraction JSON (単一ファイル) を検証し、Stage B merged
knowledge collectionの最小構造とmerge report骨格を生成する
(merge engine skeleton)。本格的なcandidate merge・canonical ID割り当て・
manual override適用・conflict解決はまだ実装しない。

docs/architecture/06_AI/Merged_Knowledge_Design.md
"""

from .engine import InputValidationResult, MergeEngine
from .models import (
    CANDIDATE_ARRAY_KEYS,
    COLLECTION_DOCUMENT_TYPE,
    COLLECTION_SCHEMA_VERSION,
    MERGE_ENGINE_VERSION,
    MERGED_ENTITY_KEYS,
    MergeReport,
)

__all__ = [
    "MergeEngine",
    "MergeReport",
    "InputValidationResult",
    "CANDIDATE_ARRAY_KEYS",
    "MERGED_ENTITY_KEYS",
    "COLLECTION_SCHEMA_VERSION",
    "COLLECTION_DOCUMENT_TYPE",
    "MERGE_ENGINE_VERSION",
]
