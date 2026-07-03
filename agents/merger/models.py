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

# inputResultsの1エントリが取りうる状態。
# valid: 検証を通過しmergeに含まれた / invalid: 読み込めたが検証に失敗した /
# skipped: 入力を解決できなかった (存在しないパス・無マッチのglob等)。
INPUT_STATUS_VALID = "valid"
INPUT_STATUS_INVALID = "invalid"
INPUT_STATUS_SKIPPED = "skipped"


@dataclass
class InputResult:
    """1入力ファイル (またはraw引数) の処理結果 (merge report内のinputResults
    の1エントリ)。
    """

    path: str
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass
class MergeReport:
    """merge report骨格 (Merged_Knowledge_Design.md §11.2)。

    inputFiles: raw --input引数の件数 (ディレクトリ/glob展開前)
    resolvedInputFiles: 展開・重複排除後に実際に見つかったファイル件数
        (validInputs + invalidInputs と一致する)
    skippedInputs: 1件もファイルへ解決できなかったraw引数の一覧

    将来: conflicts / unresolved candidates / manual override summary /
    merge decisions を追加する。
    """

    input_files: int = 0
    resolved_input_files: int = 0
    valid_inputs: int = 0
    invalid_inputs: int = 0
    skipped_inputs: list[str] = field(default_factory=list)
    candidate_counts: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(CANDIDATE_ARRAY_KEYS, 0)
    )
    merged_entity_counts: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(MERGED_ENTITY_KEYS, 0)
    )
    conflicts_count: int = 0
    unresolved_count: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    input_results: list[InputResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputFiles": self.input_files,
            "resolvedInputFiles": self.resolved_input_files,
            "validInputs": self.valid_inputs,
            "invalidInputs": self.invalid_inputs,
            "skippedInputs": list(self.skipped_inputs),
            "candidateCounts": dict(self.candidate_counts),
            "mergedEntityCounts": dict(self.merged_entity_counts),
            "conflictsCount": self.conflicts_count,
            "unresolvedCount": self.unresolved_count,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "inputResults": [r.to_dict() for r in self.input_results],
        }
