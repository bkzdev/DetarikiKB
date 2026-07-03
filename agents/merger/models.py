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

# CANDIDATE_ARRAY_KEYS <-> MERGED_ENTITY_KEYS の相互対応表 (両方とも同じ順序の
# 8種、timelineCandidates <-> timeline のみ名前が異なる)。
# entityTypeSummaries等、candidate件数とmerged件数を同じtype単位で
# 突き合わせる集計で使う。
CANDIDATE_TO_MERGED_KEY = dict(
    zip(CANDIDATE_ARRAY_KEYS, MERGED_ENTITY_KEYS, strict=True)
)
MERGED_TO_CANDIDATE_KEY = dict(
    zip(MERGED_ENTITY_KEYS, CANDIDATE_ARRAY_KEYS, strict=True)
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

    conflictsCount/unresolvedCountは既存の全体合算値 (後方互換のため維持)。
    unresolvedEntityCounts/conflictCounts/warningCounts/entityTypeSummaries/
    inputSummariesはmerge report強化 (feature/merge-report-enhancements) で
    追加した、entity type別・入力別の内訳。
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
    unresolved_entity_counts: dict[str, int] = field(
        default_factory=lambda: dict.fromkeys(MERGED_ENTITY_KEYS, 0)
    )
    conflict_counts: dict[str, Any] = field(
        default_factory=lambda: {
            "total": 0,
            "bySeverity": {},
            "byType": {},
            "byEntityType": {},
        }
    )
    warning_counts: dict[str, int] = field(
        default_factory=lambda: {
            "total": 0,
            "unresolvedRelationships": 0,
            "skippedOverrides": 0,
            "other": 0,
        }
    )
    entity_type_summaries: dict[str, dict[str, int]] = field(default_factory=dict)
    input_summaries: list[dict[str, Any]] = field(default_factory=list)
    relationship_type_summary: dict[str, Any] = field(
        default_factory=lambda: {
            "knownTypes": {},
            "unknownTypes": {},
            "normalizedTypes": {},
        }
    )
    canonical_id_summary: dict[str, Any] = field(
        default_factory=lambda: {
            "totalAssigned": 0,
            "duplicateCount": 0,
            "invalidCount": 0,
            "warnings": [],
        }
    )
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
            "unresolvedEntityCounts": dict(self.unresolved_entity_counts),
            "conflictCounts": {
                "total": self.conflict_counts["total"],
                "bySeverity": dict(self.conflict_counts["bySeverity"]),
                "byType": dict(self.conflict_counts["byType"]),
                "byEntityType": dict(self.conflict_counts["byEntityType"]),
            },
            "warningCounts": dict(self.warning_counts),
            "entityTypeSummaries": {
                key: dict(summary)
                for key, summary in self.entity_type_summaries.items()
            },
            "inputSummaries": [dict(s) for s in self.input_summaries],
            "relationshipTypeSummary": {
                "knownTypes": dict(self.relationship_type_summary["knownTypes"]),
                "unknownTypes": dict(self.relationship_type_summary["unknownTypes"]),
                "normalizedTypes": dict(
                    self.relationship_type_summary["normalizedTypes"]
                ),
            },
            "canonicalIdSummary": {
                "totalAssigned": self.canonical_id_summary["totalAssigned"],
                "duplicateCount": self.canonical_id_summary["duplicateCount"],
                "invalidCount": self.canonical_id_summary["invalidCount"],
                "warnings": list(self.canonical_id_summary["warnings"]),
            },
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "inputResults": [r.to_dict() for r in self.input_results],
        }
