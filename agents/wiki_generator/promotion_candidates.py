"""Pure classification logic for Evidence Index promotion candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

PROMOTION_CANDIDATE = "promotion-candidate"
PARSER_IMPROVEMENT_WAIT = "parser-improvement-wait"
EXCLUDED = "excluded"

VALID_CLASSIFICATIONS = frozenset(
    {PROMOTION_CANDIDATE, PARSER_IMPROVEMENT_WAIT, EXCLUDED}
)
UNKNOWN_RATIO_ACCEPTABLE = "acceptable"
UNKNOWN_RATIO_HUMAN_REVIEW_REQUIRED = "human-review-required"
UNKNOWN_RATIO_BLOCKING = "blocking"
VALID_PARSER_COMPATIBILITIES = frozenset(
    {"compatible", "warning", "needs_update", "blocked"}
)
MEANINGFUL_EVIDENCE_TYPES = frozenset({"dialogue", "monologue", "narration", "choice"})

UNKNOWN_RATIO_MAX_PERCENT = 10
UNKNOWN_RATIO_HUMAN_REVIEW_MAX_PERCENT = 30
MEANINGFUL_RATIO_MIN_PERCENT = 70
ENTRY_COUNT_REVIEW_THRESHOLD = 600


@dataclass(frozen=True)
class PromotionCandidateResult:
    """Calculated metrics and classification for one story."""

    total_entry_count: int
    unknown_entry_count: int
    unknown_ratio: float
    meaningful_entry_count: int
    meaningful_ratio: float
    other_entry_count: int
    unknown_ratio_acceptable: bool
    unknown_ratio_band: str
    meaningful_ratio_acceptable: bool
    parser_compatibility: str
    parser_compatibility_acceptable: bool
    entry_count_review_required: bool
    human_review_required: bool
    decision_reason_codes: tuple[str, ...]
    classification: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "totalEntryCount": self.total_entry_count,
            "unknownEntryCount": self.unknown_entry_count,
            "unknownRatio": self.unknown_ratio,
            "meaningfulEntryCount": self.meaningful_entry_count,
            "meaningfulRatio": self.meaningful_ratio,
            "otherEntryCount": self.other_entry_count,
            "unknownRatioAcceptable": self.unknown_ratio_acceptable,
            "unknownRatioBand": self.unknown_ratio_band,
            "meaningfulRatioAcceptable": self.meaningful_ratio_acceptable,
            "parserCompatibility": self.parser_compatibility,
            "parserCompatibilityAcceptable": self.parser_compatibility_acceptable,
            "entryCountReviewRequired": self.entry_count_review_required,
            "humanReviewRequired": self.human_review_required,
            "decisionReasonCodes": list(self.decision_reason_codes),
            "classification": self.classification,
        }


def _validated_counts(
    entries_by_evidence_type: Mapping[str, int],
) -> dict[str, int]:
    if not isinstance(entries_by_evidence_type, Mapping):
        raise ValueError("entries_by_evidence_type must be a mapping")

    counts: dict[str, int] = {}
    for evidence_type, count in entries_by_evidence_type.items():
        if not isinstance(evidence_type, str) or not evidence_type:
            raise ValueError("evidence type keys must be non-empty strings")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(
                f"count for evidence type {evidence_type!r} must be a "
                "non-negative integer"
            )
        counts[evidence_type] = count
    return counts


def classify_promotion_candidate(
    entries_by_evidence_type: Mapping[str, int],
    parser_compatibility: str,
) -> PromotionCandidateResult:
    """Classify one story using Batch Promotion Policy sections 4.3.1-4.3.2.

    Ratio thresholds are compared with integer arithmetic so exact boundary
    values are not affected by floating-point rounding. Unknown evidence types
    are retained in ``other_entry_count`` rather than discarded.
    """

    counts = _validated_counts(entries_by_evidence_type)
    if parser_compatibility not in VALID_PARSER_COMPATIBILITIES:
        raise ValueError(
            "parser_compatibility must be one of: "
            + ", ".join(sorted(VALID_PARSER_COMPATIBILITIES))
        )

    total = sum(counts.values())
    unknown = counts.get("unknown", 0)
    meaningful = sum(counts.get(name, 0) for name in MEANINGFUL_EVIDENCE_TYPES)
    other = total - unknown - meaningful

    unknown_ratio = unknown / total if total else 0.0
    meaningful_ratio = meaningful / total if total else 0.0
    unknown_acceptable = (
        total > 0 and unknown * 100 <= total * UNKNOWN_RATIO_MAX_PERCENT
    )
    unknown_ratio_band = (
        UNKNOWN_RATIO_ACCEPTABLE
        if unknown_acceptable
        else UNKNOWN_RATIO_HUMAN_REVIEW_REQUIRED
        if total > 0 and unknown * 100 <= total * UNKNOWN_RATIO_HUMAN_REVIEW_MAX_PERCENT
        else UNKNOWN_RATIO_BLOCKING
    )
    meaningful_acceptable = (
        total > 0 and meaningful * 100 >= total * MEANINGFUL_RATIO_MIN_PERCENT
    )
    parser_acceptable = parser_compatibility == "compatible" or (
        parser_compatibility == "warning"
        and unknown_acceptable
        and meaningful_acceptable
    )

    if parser_compatibility in {"needs_update", "blocked"}:
        classification = EXCLUDED
        human_review_required = False
        decision_reason_codes = (f"parser-compatibility-{parser_compatibility}",)
    elif unknown_ratio_band == UNKNOWN_RATIO_HUMAN_REVIEW_REQUIRED:
        classification = None
        human_review_required = True
        decision_reason_codes = ("unknown-ratio-human-review-required",)
    elif (
        total > 0 and unknown_acceptable and meaningful_acceptable and parser_acceptable
    ):
        classification = PROMOTION_CANDIDATE
        human_review_required = False
        decision_reason_codes = ("all-automatic-criteria-satisfied",)
    elif (
        unknown_ratio_band == UNKNOWN_RATIO_BLOCKING
        and parser_compatibility == "warning"
    ):
        classification = PARSER_IMPROVEMENT_WAIT
        human_review_required = False
        decision_reason_codes = ("unknown-ratio-blocking-with-parser-warning",)
    else:
        classification = EXCLUDED
        human_review_required = False
        decision_reason_codes = ("automatic-criteria-not-satisfied",)

    return PromotionCandidateResult(
        total_entry_count=total,
        unknown_entry_count=unknown,
        unknown_ratio=unknown_ratio,
        meaningful_entry_count=meaningful,
        meaningful_ratio=meaningful_ratio,
        other_entry_count=other,
        unknown_ratio_acceptable=unknown_acceptable,
        unknown_ratio_band=unknown_ratio_band,
        meaningful_ratio_acceptable=meaningful_acceptable,
        parser_compatibility=parser_compatibility,
        parser_compatibility_acceptable=parser_acceptable,
        entry_count_review_required=total > ENTRY_COUNT_REVIEW_THRESHOLD,
        human_review_required=human_review_required,
        decision_reason_codes=decision_reason_codes,
        classification=classification,
    )
