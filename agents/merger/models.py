"""
DKB Merger - Models
Stage B merge engine skeleton の出力に使う定数・データ構造。

本格的なcandidate merge・canonical ID割り当て・manual override適用・
conflict解決はまだ実装しない。skeletonが出力するのは、検証済み入力の
集計と空のmerged collection構造のみ。

docs/architecture/06_AI/Merged_Knowledge_Design.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

COLLECTION_SCHEMA_VERSION = "0.1.0"
COLLECTION_DOCUMENT_TYPE = "merged_knowledge_collection"
MERGE_ENGINE_VERSION = "0.1.0"

# Stage A episode_extraction のcandidate配列キー (extraction.schema.json)。
# candidateCountsの集計キーとしてそのまま使う。
CANDIDATE_ARRAY_KEYS = (
    "characters",
    "locations",
    "organizations",
    "items",
    "lore",
    "events",
    "relationships",
    "timelineCandidates",
)

# merged collection の entities 配下キー。
# Stage A配列キーとの対応: timelineCandidates -> timeline
# (Merged_Knowledge_Design.md §7: Stage B側はtimeline entriesの集約)。
MERGED_ENTITY_KEYS = (
    "characters",
    "locations",
    "organizations",
    "items",
    "lore",
    "events",
    "relationships",
    "timeline",
)


@dataclass
class MergeReport:
    """merge report骨格 (Merged_Knowledge_Design.md §11.2)。

    将来: conflicts / unresolved candidates / manual override summary /
    merge decisions を追加する。
    """

    input_files: int = 0
    valid_inputs: int = 0
    invalid_inputs: int = 0
    skipped_inputs: list[str] = field(default_factory=list)
    candidate_counts: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(CANDIDATE_ARRAY_KEYS, 0)
    )
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputFiles": self.input_files,
            "validInputs": self.valid_inputs,
            "invalidInputs": self.invalid_inputs,
            "skippedInputs": list(self.skipped_inputs),
            "candidateCounts": dict(self.candidate_counts),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }
