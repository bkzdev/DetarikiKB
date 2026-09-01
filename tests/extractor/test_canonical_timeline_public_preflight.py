"""Canonical Timeline public preflightの合成fixtureテスト。"""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from agents.extractor.canonical_timeline_public_preflight import (
    INPUT_DIGEST_MISMATCH,
    INPUT_INVALID,
    INTERNAL_SCHEMA_INVALID,
    INTERNAL_VALUE_EXPOSURE,
    PROJECTION_SCHEMA_INVALID,
    PUBLIC_LABEL_MISMATCH,
    PUBLIC_LABEL_MISSING,
    PUBLIC_LABEL_SOURCE_INVALID,
    REGISTRY_DUPLICATE,
    REGISTRY_MAPPING_MISMATCH,
    REGISTRY_SCHEMA_INVALID,
    canonical_timeline_public_preflight_input_digests,
    preflight_canonical_timeline_public_projection,
)
from agents.extractor.canonical_timeline_public_projection import (
    PROJECTION_MISMATCH,
    PUBLIC_MAPPING_MISSING,
    build_canonical_timeline_public_projection,
)


def _episode(number: int) -> dict[str, str]:
    story_id = f"EVT_TEST_STORY_{number:02d}"
    return {
        "storyId": story_id,
        "episodeId": f"{story_id}_E01",
        "storyCategory": "EVT",
    }


def _edge() -> dict[str, object]:
    source, target = _episode(1), _episode(2)
    return {
        "from": deepcopy(source),
        "to": deepcopy(target),
        "relationState": "before",
        "stateReason": None,
        "adoptionStatus": "canonical",
        "reviewStatus": "confirmed",
        "candidateProvenance": [
            {
                "candidateId": "TEST_CANDIDATE_001",
                "sourceEpisode": deepcopy(source),
                "targetEpisode": deepcopy(target),
                "observedRelation": "before",
                "evidenceIds": ["TEST_EVIDENCE_001"],
                "sourceType": "manual",
                "confidence": 1.0,
                "extractionRun": {
                    "extractionVersion": "test-0.1",
                    "extractionMethod": "manual",
                    "modelProvider": None,
                    "modelName": None,
                    "promptVersion": None,
                    "extractedAt": "2099-01-01T00:00:00Z",
                    "parserCompatibilityAtExtraction": "compatible",
                },
            }
        ],
        "humanDecision": {
            "reviewer": "TEST_REVIEWER",
            "decidedAt": "2099-01-02T00:00:00Z",
            "evidenceSummary": "Synthetic decision.",
            "notes": None,
        },
    }


def _document() -> dict[str, object]:
    return {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline",
        "scopeStoryCategory": "EVT",
        "visibility": "internal_only",
        "nodes": [_episode(1), _episode(2)],
        "edges": [_edge()],
    }


def _mapping() -> dict[tuple[str, str], dict[str, str]]:
    return {
        (_episode(number)["storyId"], _episode(number)["episodeId"]): {
            "publicStoryId": f"PUBLIC_EVENT_{number:02d}",
            "publicEpisodeId": f"PUBLIC_EVENT_{number:02d}_E01",
            "storyLabel": f"合成イベント{number}",
            "episodeLabel": f"合成エピソード{number}",
        }
        for number in (1, 2)
    }


def _registry() -> dict[str, object]:
    return {
        "registryVersion": 1,
        "stories": [
            {
                "publicStoryId": f"PUBLIC_EVENT_{number:02d}",
                "category": "event",
                "episodes": [
                    {
                        "publicEpisodeId": f"PUBLIC_EVENT_{number:02d}_E01",
                        "episodeOrder": 1,
                    }
                ],
            }
            for number in (1, 2)
        ],
    }


def _labels() -> dict[str, dict[str, str]]:
    return {
        "storyLabels": {
            f"PUBLIC_EVENT_{number:02d}": f"合成イベント{number}" for number in (1, 2)
        },
        "episodeLabels": {
            f"PUBLIC_EVENT_{number:02d}_E01": f"合成エピソード{number}"
            for number in (1, 2)
        },
    }


def _inputs() -> tuple[dict, dict, dict, dict, dict, dict]:
    document = _document()
    mapping = _mapping()
    projection = build_canonical_timeline_public_projection(document, mapping)[
        "projection"
    ]
    registry = _registry()
    labels = _labels()
    digests = canonical_timeline_public_preflight_input_digests(
        document, projection, mapping, registry, labels
    )
    return document, projection, mapping, registry, labels, digests


def _run(inputs: tuple[dict, dict, dict, dict, dict, dict]) -> dict:
    return preflight_canonical_timeline_public_projection(*inputs)


def _repin(inputs: tuple[dict, dict, dict, dict, dict, dict]) -> tuple:
    document, projection, mapping, registry, labels, _digests = inputs
    digests = canonical_timeline_public_preflight_input_digests(
        document, projection, mapping, registry, labels
    )
    return document, projection, mapping, registry, labels, digests


def test_clean_preflight_keeps_projection_candidate_and_inputs_immutable() -> None:
    inputs = _inputs()
    original = deepcopy(inputs)

    assert _run(inputs) == {
        "status": "clean",
        "publishStatus": "projection_candidate",
        "findings": [],
    }
    assert inputs == original


def test_digest_pin_mismatch_blocks_before_other_checks_without_digest_exposure() -> (
    None
):
    inputs = _inputs()
    inputs[-1]["projection"] = "0" * 64

    result = _run(inputs)

    assert result["findings"] == [{"rule": INPUT_DIGEST_MISMATCH, "count": 1}]
    assert "000000" not in json.dumps(result)


@pytest.mark.parametrize(
    ("mapping", "digests"),
    [
        (None, None),
        ({"invalid-key": {}}, {}),
        ({}, {"projection": "not-a-digest"}),
    ],
)
def test_invalid_digest_or_mapping_shape_fails_closed(mapping, digests) -> None:
    document, projection, _mapping_value, registry, labels, _digests = _inputs()

    result = preflight_canonical_timeline_public_projection(
        document, projection, mapping, registry, labels, digests
    )

    assert result["findings"] == [{"rule": INPUT_INVALID, "count": 1}]


@pytest.mark.parametrize(
    ("index", "mutate", "rule"),
    [
        (0, lambda value: value.pop("visibility"), INTERNAL_SCHEMA_INVALID),
        (1, lambda value: value.pop("scope"), PROJECTION_SCHEMA_INVALID),
        (3, lambda value: value.pop("registryVersion"), REGISTRY_SCHEMA_INVALID),
    ],
)
def test_schema_errors_block_with_counts_only(index, mutate, rule) -> None:
    inputs = list(_inputs())
    mutate(inputs[index])

    result = _run(_repin(tuple(inputs)))

    assert result["status"] == "blocked"
    assert result["findings"] == [{"rule": rule, "count": 1}]


def test_projector_blocking_finding_is_forwarded_safely() -> None:
    inputs = list(_inputs())
    inputs[2].pop((_episode(2)["storyId"], _episode(2)["episodeId"]))

    result = _run(_repin(tuple(inputs)))

    assert result["findings"] == [{"rule": PUBLIC_MAPPING_MISSING, "count": 1}]
    assert "EVT_TEST" not in json.dumps(result)


def test_registry_duplicate_blocks_without_identifiers() -> None:
    inputs = list(_inputs())
    inputs[3]["stories"].append(deepcopy(inputs[3]["stories"][0]))

    result = _run(_repin(tuple(inputs)))

    assert result["findings"] == [{"rule": REGISTRY_DUPLICATE, "count": 2}]
    assert "PUBLIC_EVENT" not in json.dumps(result)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda registry: registry["stories"][0].update({"category": "raid"}),
        lambda registry: registry["stories"][0]["episodes"][0].update(
            {"publicEpisodeId": "PUBLIC_EVENT_01_E99"}
        ),
    ],
)
def test_registry_mapping_or_event_category_mismatch_blocks(mutate) -> None:
    inputs = list(_inputs())
    mutate(inputs[3])

    result = _run(_repin(tuple(inputs)))

    assert result["findings"] == [{"rule": REGISTRY_MAPPING_MISMATCH, "count": 1}]


def test_invalid_label_source_blocks() -> None:
    inputs = list(_inputs())
    inputs[4] = {"storyLabels": []}

    assert _run(_repin(tuple(inputs)))["findings"] == [
        {"rule": PUBLIC_LABEL_SOURCE_INVALID, "count": 1}
    ]


def test_missing_and_mismatched_labels_are_aggregated() -> None:
    inputs = list(_inputs())
    inputs[4]["storyLabels"].pop("PUBLIC_EVENT_01")
    inputs[4]["episodeLabels"]["PUBLIC_EVENT_02_E01"] = "不一致"

    assert _run(_repin(tuple(inputs)))["findings"] == [
        {"rule": PUBLIC_LABEL_MISMATCH, "count": 1},
        {"rule": PUBLIC_LABEL_MISSING, "count": 1},
    ]


def test_cross_document_change_blocks_even_when_schema_valid() -> None:
    inputs = list(_inputs())
    inputs[1]["components"][0]["componentKey"] = "component-9999"

    assert _run(_repin(tuple(inputs)))["findings"] == [
        {"rule": PROJECTION_MISMATCH, "count": 1}
    ]


@pytest.mark.parametrize(
    "exposed_label",
    [
        "EVT_TEST_STORY_01_E01",
        "https://example.test/timeline",
        "C:\\synthetic\\timeline.dec",
        "a" * 64,
        "@ChTalk synthetic",
    ],
)
def test_internal_values_and_forbidden_markers_block_exposure(exposed_label) -> None:
    inputs = list(_inputs())
    mapping_key = (_episode(1)["storyId"], _episode(1)["episodeId"])
    inputs[2][mapping_key]["episodeLabel"] = exposed_label
    inputs[1] = build_canonical_timeline_public_projection(inputs[0], inputs[2])[
        "projection"
    ]
    inputs[4]["episodeLabels"]["PUBLIC_EVENT_01_E01"] = exposed_label

    result = _run(_repin(tuple(inputs)))

    assert result["status"] == "blocked"
    assert result["findings"][0]["rule"] == INTERNAL_VALUE_EXPOSURE
    assert set(result["findings"][0]) == {"rule", "count"}


def test_short_internal_free_text_cannot_be_reused_as_public_label() -> None:
    inputs = list(_inputs())
    inputs[0]["edges"][0]["humanDecision"]["evidenceSummary"] = "abc"
    mapping_key = (_episode(1)["storyId"], _episode(1)["episodeId"])
    inputs[2][mapping_key]["episodeLabel"] = "abc"
    inputs[1] = build_canonical_timeline_public_projection(inputs[0], inputs[2])[
        "projection"
    ]
    inputs[4]["episodeLabels"]["PUBLIC_EVENT_01_E01"] = "abc"

    assert _run(_repin(tuple(inputs)))["findings"] == [
        {"rule": INTERNAL_VALUE_EXPOSURE, "count": 1}
    ]
