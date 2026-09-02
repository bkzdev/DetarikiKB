"""Canonical Timeline public Markdown rendererの合成fixtureテスト。"""

from __future__ import annotations

from copy import deepcopy

import pytest

from agents.wiki_generator.canonical_timeline import (
    LINK_MISSING_FROM_MARKDOWN,
    LINK_TARGET_MISSING,
    LINK_UNEXPECTED,
    render_canonical_timeline_page,
    validate_canonical_timeline_page_links,
)
from agents.wiki_generator.paths import canonical_timeline_page_path


def _node(number: int) -> dict[str, str]:
    return {
        "publicStoryId": f"PUBLIC_EVENT_{number:02d}",
        "publicEpisodeId": f"PUBLIC_EVENT_{number:02d}_E01",
        "storyLabel": f"合成イベント{number}",
        "episodeLabel": f"合成エピソード{number}",
    }


def _projection() -> dict[str, object]:
    return {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_public_projection",
        "visibility": "public",
        "publishStatus": "projection_candidate",
        "scope": "event",
        "purpose": "confirmed_relation_navigation",
        "coverageNoticeKey": "partial_confirmed_relations_only",
        "components": [
            {
                "componentKey": "component-0001",
                "nodes": [_node(1), _node(2)],
                "relations": [
                    {
                        "fromPublicEpisodeId": "PUBLIC_EVENT_01_E01",
                        "toPublicEpisodeId": "PUBLIC_EVENT_02_E01",
                        "relationState": "before",
                        "labelKey": "timeline_before",
                    }
                ],
            }
        ],
        "unresolvedRelationSummary": {
            "countScope": "canonical_artifact_only",
            "noticeKey": "unresolved_relations_not_shown",
            "unknownCount": 2,
            "conflictCount": 1,
        },
    }


def _clean_report() -> dict[str, object]:
    return {
        "status": "clean",
        "publishStatus": "projection_candidate",
        "findings": [],
    }


def _available_paths() -> set[str]:
    return {
        "stories/PUBLIC_EVENT_01.md",
        "stories/PUBLIC_EVENT_01_E01.md",
        "stories/PUBLIC_EVENT_02.md",
        "stories/PUBLIC_EVENT_02_E01.md",
    }


def test_timeline_page_path_is_single_aggregate_page() -> None:
    assert canonical_timeline_page_path() == "timelines/index.md"


def test_renderer_outputs_public_labels_links_relations_and_safe_aggregate() -> None:
    page = render_canonical_timeline_page(_projection(), _clean_report())

    assert page.startswith("---\n")
    assert 'page_type: "timeline"' in page
    assert 'status: "projection_candidate"' in page
    assert "# Canonical Timeline" in page
    assert "全出来事の総順序を表すものではありません" in page
    assert "[合成イベント1](../stories/PUBLIC_EVENT_01.md)" in page
    assert "[合成エピソード1](../stories/PUBLIC_EVENT_01_E01.md)" in page
    assert (
        "- [合成エピソード1](../stories/PUBLIC_EVENT_01_E01.md) は "
        "[合成エピソード2](../stories/PUBLIC_EVENT_02_E01.md) **より前**" in page
    )
    assert "- 不明: 2" in page
    assert "- 競合: 1" in page
    assert "確認対象データ内の件数だけを示します" in page
    assert "artifact" not in page
    for forbidden in (
        "storyId",
        "episodeId",
        "candidateId",
        "evidenceIds",
        "humanDecision",
        "component-0001",
    ):
        assert forbidden not in page


@pytest.mark.parametrize(
    "report",
    [
        {"status": "blocked", "publishStatus": "projection_candidate", "findings": []},
        {
            "status": "clean",
            "publishStatus": "projection_candidate",
            "findings": [{"rule": "synthetic", "count": 1}],
        },
        {
            "status": "clean",
            "publishStatus": "projection_candidate",
            "findings": [],
            "extra": True,
        },
    ],
)
def test_renderer_rejects_any_report_other_than_exact_clean_contract(report) -> None:
    with pytest.raises(ValueError, match="preflight is not clean"):
        render_canonical_timeline_page(_projection(), report)


def test_renderer_rejects_non_candidate_projection() -> None:
    projection = _projection()
    projection["publishStatus"] = "published"

    with pytest.raises(ValueError, match="projection is not a candidate"):
        render_canonical_timeline_page(projection, _clean_report())


def test_empty_projection_has_clear_message_and_no_links() -> None:
    projection = _projection()
    projection["components"] = []
    projection["unresolvedRelationSummary"] = {
        "countScope": "canonical_artifact_only",
        "noticeKey": "unresolved_relations_not_shown",
        "unknownCount": 0,
        "conflictCount": 0,
    }

    page = render_canonical_timeline_page(projection, _clean_report())

    assert "表示できる確認済み関係はありません。" in page
    assert "../stories/" not in page
    assert validate_canonical_timeline_page_links(page, projection, set()) == []


def test_renderer_escapes_markdown_and_html_in_public_labels() -> None:
    projection = _projection()
    projection["components"][0]["nodes"][0]["storyLabel"] = "合成[物語] <script>"
    projection["components"][0]["nodes"][0]["episodeLabel"] = "合成\\[話]"

    page = render_canonical_timeline_page(projection, _clean_report())

    assert "合成\\[物語\\] &lt;script&gt;" in page
    assert "合成\\\\\\[話\\]" in page
    assert "<script>" not in page


@pytest.mark.parametrize(
    ("label_key", "expected"),
    [
        (
            "timeline_before",
            "- [合成エピソード1](../stories/PUBLIC_EVENT_01_E01.md) は "
            "[合成エピソード2](../stories/PUBLIC_EVENT_02_E01.md) **より前**",
        ),
        (
            "timeline_after",
            "- [合成エピソード1](../stories/PUBLIC_EVENT_01_E01.md) は "
            "[合成エピソード2](../stories/PUBLIC_EVENT_02_E01.md) **より後**",
        ),
        (
            "timeline_same_time",
            "- [合成エピソード1](../stories/PUBLIC_EVENT_01_E01.md) と "
            "[合成エピソード2](../stories/PUBLIC_EVENT_02_E01.md) は **同時期**",
        ),
    ],
)
def test_renderer_uses_fixed_relation_text(label_key, expected) -> None:
    projection = _projection()
    relation = projection["components"][0]["relations"][0]
    relation["labelKey"] = label_key
    relation["relationState"] = label_key.removeprefix("timeline_")

    page = render_canonical_timeline_page(projection, _clean_report())

    assert expected in page


def test_renderer_is_deterministic_and_does_not_mutate_inputs() -> None:
    projection, report = _projection(), _clean_report()
    original_projection, original_report = deepcopy(projection), deepcopy(report)

    first = render_canonical_timeline_page(projection, report)
    second = render_canonical_timeline_page(projection, report)

    assert first == second
    assert projection == original_projection
    assert report == original_report


def test_link_checker_accepts_all_rendered_story_and_episode_targets() -> None:
    projection = _projection()
    page = render_canonical_timeline_page(projection, _clean_report())

    assert (
        validate_canonical_timeline_page_links(page, projection, _available_paths())
        == []
    )


def test_link_checker_aggregates_missing_markdown_and_page_targets_safely() -> None:
    projection = _projection()
    page = render_canonical_timeline_page(projection, _clean_report()).replace(
        "[合成イベント1](../stories/PUBLIC_EVENT_01.md)", "合成イベント1"
    )
    available = _available_paths() - {"stories/PUBLIC_EVENT_02_E01.md"}

    findings = validate_canonical_timeline_page_links(page, projection, available)

    assert findings == [
        {"rule": LINK_MISSING_FROM_MARKDOWN, "count": 1},
        {"rule": LINK_TARGET_MISSING, "count": 1},
    ]
    assert "PUBLIC_EVENT" not in str(findings)


def test_link_checker_blocks_unexpected_local_markdown_link() -> None:
    projection = _projection()
    page = render_canonical_timeline_page(projection, _clean_report())
    page += "[unexpected](../stories/PUBLIC_EVENT_99.md)\n"

    assert validate_canonical_timeline_page_links(
        page, projection, _available_paths()
    ) == [{"rule": LINK_UNEXPECTED, "count": 1}]


def test_link_checker_normalizes_windows_separators_in_available_paths() -> None:
    projection = _projection()
    page = render_canonical_timeline_page(projection, _clean_report())
    windows_paths = {path.replace("/", "\\") for path in _available_paths()}

    assert validate_canonical_timeline_page_links(page, projection, windows_paths) == []
