import json

import pytest

from agents.wiki_generator.promotion_candidates import (
    EXCLUDED,
    PARSER_IMPROVEMENT_WAIT,
    PROMOTION_CANDIDATE,
    classify_promotion_candidate,
)


def test_unknown_ratio_at_ten_percent_is_acceptable():
    result = classify_promotion_candidate(
        {"dialogue": 70, "unknown": 10, "future_type": 20},
        "compatible",
    )

    assert result.unknown_ratio == 0.10
    assert result.unknown_ratio_acceptable is True
    assert result.classification == PROMOTION_CANDIDATE


def test_unknown_ratio_above_ten_percent_with_warning_waits_for_parser():
    result = classify_promotion_candidate(
        {"dialogue": 70, "unknown": 11, "future_type": 19},
        "warning",
    )

    assert result.unknown_ratio_acceptable is False
    assert result.classification == PARSER_IMPROVEMENT_WAIT


def test_meaningful_ratio_at_seventy_percent_is_acceptable():
    result = classify_promotion_candidate(
        {"dialogue": 50, "narration": 20, "future_type": 30},
        "compatible",
    )

    assert result.meaningful_ratio == 0.70
    assert result.meaningful_ratio_acceptable is True
    assert result.classification == PROMOTION_CANDIDATE


def test_meaningful_ratio_below_seventy_percent_is_excluded():
    result = classify_promotion_candidate(
        {"dialogue": 69, "future_type": 31},
        "compatible",
    )

    assert result.meaningful_ratio_acceptable is False
    assert result.classification == EXCLUDED


@pytest.mark.parametrize(
    ("parser_compatibility", "acceptable", "classification"),
    [
        ("compatible", True, PROMOTION_CANDIDATE),
        ("warning", True, PROMOTION_CANDIDATE),
        ("needs_update", False, EXCLUDED),
        ("blocked", False, EXCLUDED),
    ],
)
def test_all_parser_compatibility_states(
    parser_compatibility,
    acceptable,
    classification,
):
    result = classify_promotion_candidate(
        {"dialogue": 70, "future_type": 30},
        parser_compatibility,
    )

    assert result.parser_compatibility_acceptable is acceptable
    assert result.classification == classification


@pytest.mark.parametrize(
    ("entry_counts", "review_required"),
    [
        ({"dialogue": 420, "unknown": 10, "future_type": 170}, False),
        ({"dialogue": 421, "unknown": 10, "future_type": 170}, True),
    ],
)
def test_entry_count_review_threshold_does_not_change_classification(
    entry_counts,
    review_required,
):
    result = classify_promotion_candidate(entry_counts, "compatible")

    assert result.entry_count_review_required is review_required
    assert result.classification == PROMOTION_CANDIDATE


def test_zero_entries_are_excluded_and_serializable():
    result = classify_promotion_candidate({}, "compatible")

    assert result.total_entry_count == 0
    assert result.unknown_ratio == 0.0
    assert result.meaningful_ratio == 0.0
    assert result.classification == EXCLUDED
    assert json.loads(json.dumps(result.to_dict()))["classification"] == EXCLUDED


def test_other_entries_are_counted_separately():
    result = classify_promotion_candidate(
        {
            "dialogue": 70,
            "unknown": 10,
            "future_type": 15,
            "another_type": 5,
        },
        "compatible",
    )

    assert result.total_entry_count == 100
    assert result.meaningful_entry_count == 70
    assert result.unknown_entry_count == 10
    assert result.other_entry_count == 20


@pytest.mark.parametrize(
    "entry_counts",
    [
        {"dialogue": True},
        {"dialogue": 1.0},
        {"dialogue": -1},
        {"": 1},
    ],
)
def test_invalid_entry_counts_raise_value_error(entry_counts):
    with pytest.raises(ValueError):
        classify_promotion_candidate(entry_counts, "compatible")


def test_non_mapping_entry_counts_raise_value_error():
    with pytest.raises(ValueError):
        classify_promotion_candidate([], "compatible")


def test_invalid_parser_compatibility_raises_value_error():
    with pytest.raises(ValueError):
        classify_promotion_candidate({"dialogue": 1}, "unknown")


def test_187_entries_with_about_one_percent_unknown_is_candidate():
    result = classify_promotion_candidate(
        {"dialogue": 185, "unknown": 2},
        "compatible",
    )

    assert result.total_entry_count == 187
    assert result.unknown_ratio == pytest.approx(2 / 187)
    assert result.classification == PROMOTION_CANDIDATE


def test_2039_entries_with_about_ninety_percent_unknown_waits_for_parser():
    result = classify_promotion_candidate(
        {"dialogue": 205, "unknown": 1834},
        "warning",
    )

    assert result.total_entry_count == 2039
    assert result.unknown_ratio == pytest.approx(1834 / 2039)
    assert result.classification == PARSER_IMPROVEMENT_WAIT
