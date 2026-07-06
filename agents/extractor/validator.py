"""
DKB Extractor - Semantic Validator
episode_extraction (schemas/extraction.schema.json) の、JSON Schemaでは
表現しにくい意味的整合性を検証する。

JSON Schema検証済みのepisode_extraction dictを入力として想定するが、
各チェックはdict.get()で防御的にフィールドへアクセスし、想定外の欠落があっても
例外を投げず「検証できなかった」ではなく該当チェックをスキップする形で扱う。

docs/architecture/06_AI/Extraction_Pipeline.md
docs/architecture/06_AI/Extraction_Result_Schema.md
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

# CandidateEnvelope (Extraction_Result_Schema.md §4.1) を持つ配列キー。
# documentのトップレベルにあるcandidate配列を横断して扱う。
CANDIDATE_ARRAY_KEYS = (
    "characters",
    "organizations",
    "locations",
    "items",
    "lore",
    "events",
    "relationships",
    "timelineCandidates",
    "specialSpeakerLabelCandidates",
)


@dataclass
class SemanticValidationIssue:
    """1件のsemantic validation結果。"""

    rule: str
    severity: str  # "error" | "warning"
    message: str
    candidate_type: str | None = None
    candidate_id: str | None = None
    array_key: str | None = None
    evidence_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "candidateType": self.candidate_type,
            "candidateId": self.candidate_id,
            "arrayKey": self.array_key,
            "evidenceId": self.evidence_id,
        }

    def format(self) -> str:
        """CLI表示用の1行メッセージ。どのcandidate/evidenceIdが原因か含める。"""
        location_parts = [
            part
            for part in (self.array_key, self.candidate_type, self.candidate_id)
            if part
        ]
        location = "/".join(location_parts) if location_parts else "(document)"
        evidence_part = f" evidenceId={self.evidence_id}" if self.evidence_id else ""
        return (
            f"[{self.severity}] {self.rule}: {location}{evidence_part} - {self.message}"
        )


def iter_candidates(document: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """CANDIDATE_ARRAY_KEYS配下の全candidateを (array_key, candidate) として列挙する"""
    for array_key in CANDIDATE_ARRAY_KEYS:
        for candidate in document.get(array_key, []) or []:
            yield array_key, candidate


# ----------------------------------------------------------------
# 1. evidenceIds existence check
# ----------------------------------------------------------------


def check_evidence_ids_exist(document: dict[str, Any]) -> list[SemanticValidationIssue]:
    """各candidateのevidenceIdsがdocument.evidenceIndexに実在するか検証する"""
    evidence_index = document.get("evidenceIndex", {}) or {}

    issues: list[SemanticValidationIssue] = []
    for array_key, candidate in iter_candidates(document):
        for evidence_id in candidate.get("evidenceIds", []) or []:
            if evidence_id not in evidence_index:
                issues.append(
                    SemanticValidationIssue(
                        rule="evidence_id_exists",
                        severity="error",
                        message=(
                            f"evidenceId '{evidence_id}' が"
                            " evidenceIndex に存在しません"
                        ),
                        candidate_type=candidate.get("type"),
                        candidate_id=candidate.get("id"),
                        array_key=array_key,
                        evidence_id=evidence_id,
                    )
                )
    return issues


# ----------------------------------------------------------------
# 2. duplicate candidate id check
# ----------------------------------------------------------------


def check_duplicate_candidate_ids(
    document: dict[str, Any],
) -> list[SemanticValidationIssue]:
    """characters/organizations/.../timelineCandidatesを横断してidが重複しないか検証する"""
    seen_in: dict[str, list[str]] = {}
    for array_key, candidate in iter_candidates(document):
        candidate_id = candidate.get("id")
        if not candidate_id:
            continue
        seen_in.setdefault(candidate_id, []).append(array_key)

    issues: list[SemanticValidationIssue] = []
    for candidate_id, array_keys in seen_in.items():
        if len(array_keys) > 1:
            issues.append(
                SemanticValidationIssue(
                    rule="duplicate_candidate_id",
                    severity="error",
                    message=(
                        f"candidate id '{candidate_id}' が複数箇所で重複しています "
                        f"({', '.join(array_keys)})"
                    ),
                    candidate_id=candidate_id,
                )
            )
    return issues


# ----------------------------------------------------------------
# 3. empty evidenceIndex check
# ----------------------------------------------------------------


def check_empty_evidence_index(
    document: dict[str, Any],
) -> list[SemanticValidationIssue]:
    """candidateが1件以上あるのにevidenceIndexが空でないか検証する"""
    has_candidates = any(True for _ in iter_candidates(document))
    evidence_index = document.get("evidenceIndex", {}) or {}

    if has_candidates and not evidence_index:
        return [
            SemanticValidationIssue(
                rule="empty_evidence_index",
                severity="error",
                message="candidateが存在するのにevidenceIndexが空です",
            )
        ]
    return []


# ----------------------------------------------------------------
# 4. extractionRun consistency check
# ----------------------------------------------------------------


def check_extraction_run_consistency(
    document: dict[str, Any],
) -> list[SemanticValidationIssue]:
    """document直下のextractionRunの有無と、candidate側との一致を検証する

    CandidateEnvelope.extractionRun はdocument側の複製として埋め込まれる
    (Extraction_Result_Schema.md §4.1) ため、値が食い違うのは矛盾とみなす。
    """
    document_run = document.get("extractionRun")
    if document_run is None:
        return [
            SemanticValidationIssue(
                rule="extraction_run_present",
                severity="error",
                message="document直下にextractionRunが存在しません",
            )
        ]

    issues: list[SemanticValidationIssue] = []
    for array_key, candidate in iter_candidates(document):
        candidate_run = candidate.get("extractionRun")
        if candidate_run is None:
            continue
        if candidate_run != document_run:
            issues.append(
                SemanticValidationIssue(
                    rule="extraction_run_consistency",
                    severity="error",
                    message="candidateのextractionRunがdocument直下のextractionRunと一致しません",
                    candidate_type=candidate.get("type"),
                    candidate_id=candidate.get("id"),
                    array_key=array_key,
                )
            )
    return issues


# ----------------------------------------------------------------
# 5. relationship basic check
# ----------------------------------------------------------------


def check_relationship_basic(document: dict[str, Any]) -> list[SemanticValidationIssue]:
    """RelationshipCandidateのsourceCandidate/targetCandidate

    subjectId/objectId相当のフィールドを検証する。
    relationshipTypeの語彙は未確定 (Extraction_Result_Schema.md §16.4) のため、
    ここでは空文字チェックと自己参照の緩い警告にとどめ、厳しすぎる制約は避ける。
    """
    issues: list[SemanticValidationIssue] = []
    for candidate in document.get("relationships", []) or []:
        candidate_id = candidate.get("id")
        source = candidate.get("sourceCandidate")
        target = candidate.get("targetCandidate")

        if source is not None and source.strip() == "":
            issues.append(
                SemanticValidationIssue(
                    rule="relationship_endpoint_not_empty",
                    severity="error",
                    message="sourceCandidateが空文字です",
                    candidate_type="relationship_candidate",
                    candidate_id=candidate_id,
                    array_key="relationships",
                )
            )
        if target is not None and target.strip() == "":
            issues.append(
                SemanticValidationIssue(
                    rule="relationship_endpoint_not_empty",
                    severity="error",
                    message="targetCandidateが空文字です",
                    candidate_type="relationship_candidate",
                    candidate_id=candidate_id,
                    array_key="relationships",
                )
            )

        if source and target and source == target:
            issues.append(
                SemanticValidationIssue(
                    rule="relationship_self_reference",
                    severity="warning",
                    message=f"sourceCandidateとtargetCandidateが同一です ('{source}')",
                    candidate_type="relationship_candidate",
                    candidate_id=candidate_id,
                    array_key="relationships",
                )
            )
    return issues


# ----------------------------------------------------------------
# 6. timeline basic check
# ----------------------------------------------------------------


def check_timeline_basic(document: dict[str, Any]) -> list[SemanticValidationIssue]:
    """TimelineCandidateのkindごとに、最低限期待されるフィールドがあるかを検証する

    relationshipTypeと同様、Timelineの本格的な矛盾検出・順序整合性チェックは
    まだ行わない (Extraction_Result_Schema.md §13, §16.4)。ここではkindと
    付随フィールドの組み合わせが明らかに空であるケースの緩い警告にとどめる。
    """
    issues: list[SemanticValidationIssue] = []
    for candidate in document.get("timelineCandidates", []) or []:
        candidate_id = candidate.get("id")
        kind = candidate.get("kind")

        if kind == "relative_order" and not candidate.get("relativeTo"):
            issues.append(
                SemanticValidationIssue(
                    rule="timeline_relative_order_missing_reference",
                    severity="warning",
                    message="kind: relative_orderですがrelativeToが空です",
                    candidate_type="timeline_candidate",
                    candidate_id=candidate_id,
                    array_key="timelineCandidates",
                )
            )

        if kind == "explicit_order" and (
            candidate.get("orderValue") is None
            and not candidate.get("sourceTimelineId")
            and not candidate.get("nameCandidates")
        ):
            issues.append(
                SemanticValidationIssue(
                    rule="timeline_explicit_order_missing_value",
                    severity="warning",
                    message=(
                        "kind: explicit_orderですがorderValue/sourceTimelineId/"
                        "nameCandidatesがすべて空です"
                    ),
                    candidate_type="timeline_candidate",
                    candidate_id=candidate_id,
                    array_key="timelineCandidates",
                )
            )

        if kind == "temporal_marker" and not candidate.get("markerType"):
            issues.append(
                SemanticValidationIssue(
                    rule="timeline_temporal_marker_missing_type",
                    severity="warning",
                    message="kind: temporal_markerですがmarkerTypeが空です",
                    candidate_type="timeline_candidate",
                    candidate_id=candidate_id,
                    array_key="timelineCandidates",
                )
            )
    return issues


# ----------------------------------------------------------------
# 7. entrypoint
# ----------------------------------------------------------------

_ALL_CHECKS = (
    check_evidence_ids_exist,
    check_duplicate_candidate_ids,
    check_empty_evidence_index,
    check_extraction_run_consistency,
    check_relationship_basic,
    check_timeline_basic,
)


def run_semantic_validation(document: dict[str, Any]) -> list[SemanticValidationIssue]:
    """全semantic validationチェックを実行し、結果を1つのリストにまとめて返す"""
    issues: list[SemanticValidationIssue] = []
    for check in _ALL_CHECKS:
        issues.extend(check(document))
    return issues


def has_errors(issues: list[SemanticValidationIssue]) -> bool:
    """severity: errorの項目が1件でもあるか"""
    return any(issue.severity == "error" for issue in issues)
