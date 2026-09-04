"""Commit済みpublic inputからのbuild source契約テスト。"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from agents.extractor.canonical_timeline_public_input import canonical_json_sha256
from agents.wiki_generator.public_build import (
    PublicBuildError,
    build_public_source_files,
    validate_public_build_projection,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
INPUT_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "canonical_timeline_public_input"
    / "approved_synthetic_input.json"
)


def _input() -> dict:
    return json.loads(INPUT_PATH.read_text(encoding="utf-8"))


def _refresh_digest(document: dict) -> None:
    document["payloadSha256"] = canonical_json_sha256(document["projection"])


def test_build_source_is_deterministic_complete_and_input_immutable() -> None:
    document = _input()
    original = copy.deepcopy(document)
    first = build_public_source_files(document)
    second = build_public_source_files(document)

    assert first == second
    assert document == original
    assert list(first) == sorted(first)
    assert set(first) == {
        "index.md",
        "stories/PUBLIC_EVENT_ALPHA.md",
        "stories/PUBLIC_EVENT_ALPHA_E01.md",
        "stories/PUBLIC_EVENT_BETA.md",
        "stories/PUBLIC_EVENT_BETA_E01.md",
        "timelines/index.md",
    }
    assert b"../stories/PUBLIC_EVENT_ALPHA.md" in first["timelines/index.md"]


@pytest.mark.parametrize(
    ("mutate", "code"),
    (
        (
            lambda projection: projection["components"][0].update(
                {"componentKey": "component-0002"}
            ),
            "public-build-component-order-invalid",
        ),
        (
            lambda projection: projection["components"][0]["relations"][0].update(
                {"toPublicEpisodeId": "PUBLIC_MISSING"}
            ),
            "public-build-relation-endpoint-missing",
        ),
        (
            lambda projection: projection["components"][0]["relations"][0].update(
                {"toPublicEpisodeId": "PUBLIC_EVENT_ALPHA_E01"}
            ),
            "public-build-self-relation",
        ),
    ),
)
def test_public_only_semantic_failures_are_anonymous(mutate, code) -> None:
    document = _input()
    mutate(document["projection"])
    _refresh_digest(document)
    assert code in validate_public_build_projection(document["projection"])
    with pytest.raises(PublicBuildError) as captured:
        build_public_source_files(document)
    assert captured.value.code.startswith("public-build-")
    assert "PUBLIC_" not in str(captured.value)


def test_story_label_conflict_and_page_path_collision_are_blocked() -> None:
    document = _input()
    nodes = document["projection"]["components"][0]["nodes"]
    nodes[1]["publicStoryId"] = nodes[0]["publicStoryId"]
    findings = validate_public_build_projection(document["projection"])
    assert "public-build-story-label-conflict" in findings

    nodes[1]["publicEpisodeId"] = nodes[0]["publicStoryId"]
    findings = validate_public_build_projection(document["projection"])
    assert "public-build-page-path-collision" in findings


def test_equivalent_duplicate_and_conflicting_relations_are_blocked() -> None:
    document = _input()
    relations = document["projection"]["components"][0]["relations"]
    relations.append(
        {
            "fromPublicEpisodeId": "PUBLIC_EVENT_BETA_E01",
            "toPublicEpisodeId": "PUBLIC_EVENT_ALPHA_E01",
            "relationState": "after",
            "labelKey": "timeline_after",
        }
    )
    findings = validate_public_build_projection(document["projection"])
    assert "public-build-relation-duplicate" in findings

    relations[-1].update(
        {
            "relationState": "before",
            "labelKey": "timeline_before",
        }
    )
    findings = validate_public_build_projection(document["projection"])
    assert "public-build-relation-conflict" in findings


def test_node_and_relation_order_are_canonical() -> None:
    document = _input()
    component = document["projection"]["components"][0]
    component["nodes"].reverse()
    assert "public-build-node-order-invalid" in validate_public_build_projection(
        document["projection"]
    )


def test_public_label_is_escaped_in_stub_heading() -> None:
    document = _input()
    node = document["projection"]["components"][0]["nodes"][0]
    node["storyLabel"] = '<script data-value="x">[label](target)</script>'
    _refresh_digest(document)
    files = build_public_source_files(document)
    page = files["stories/PUBLIC_EVENT_ALPHA.md"].decode("utf-8")
    assert "<script" not in page
    assert "&lt;script" in page
    assert "\\[label\\]\\(target\\)" in page


def test_invalid_envelope_is_blocked() -> None:
    document = _input()
    document["payloadSha256"] = "0" * 64
    with pytest.raises(PublicBuildError, match="public-build-input-invalid"):
        build_public_source_files(document)
