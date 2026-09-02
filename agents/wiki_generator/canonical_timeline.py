"""Public-safe Canonical Timeline projectionのMarkdown renderer。"""

from __future__ import annotations

import html
import re
from typing import Any

from agents.wiki_generator.models import build_front_matter
from agents.wiki_generator.paths import canonical_timeline_page_path

LINK_MISSING_FROM_MARKDOWN = "canonical_timeline_page_link_missing_from_markdown"
LINK_TARGET_MISSING = "canonical_timeline_page_link_target_missing"
LINK_UNEXPECTED = "canonical_timeline_page_link_unexpected"

_CLEAN_PREFLIGHT = {
    "status": "clean",
    "publishStatus": "projection_candidate",
    "findings": [],
}
_MARKDOWN_LINK_TARGET = re.compile(r"\]\(([^)\s]+)\)")


def _escape_link_text(value: str) -> str:
    escaped = html.escape(value, quote=False).replace("\\", "\\\\")
    return escaped.replace("[", "\\[").replace("]", "\\]")


def _story_target(public_story_id: str) -> str:
    return f"../stories/{public_story_id}.md"


def _episode_target(public_episode_id: str) -> str:
    return f"../stories/{public_episode_id}.md"


def _link(label: str, target: str) -> str:
    return f"[{_escape_link_text(label)}]({target})"


def _relation_line(source_link: str, target_link: str, label_key: str) -> str:
    if label_key == "timeline_before":
        return f"- {source_link} は {target_link} **より前**"
    if label_key == "timeline_after":
        return f"- {source_link} は {target_link} **より後**"
    return f"- {source_link} と {target_link} は **同時期**"


def _node_lookup(projection: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        node["publicEpisodeId"]: node
        for component in projection["components"]
        for node in component["nodes"]
    }


def _render_component(
    component: dict[str, Any], number: int, nodes_by_episode: dict[str, dict[str, str]]
) -> list[str]:
    lines = [f"## 関係グループ {number}", "", "### エピソード", ""]
    for node in component["nodes"]:
        story_link = _link(node["storyLabel"], _story_target(node["publicStoryId"]))
        episode_link = _link(
            node["episodeLabel"], _episode_target(node["publicEpisodeId"])
        )
        lines.append(f"- {story_link} — {episode_link}")

    lines.extend(["", "### 確認済み関係", ""])
    for relation in component["relations"]:
        source = nodes_by_episode[relation["fromPublicEpisodeId"]]
        target = nodes_by_episode[relation["toPublicEpisodeId"]]
        source_link = _link(
            source["episodeLabel"], _episode_target(source["publicEpisodeId"])
        )
        target_link = _link(
            target["episodeLabel"], _episode_target(target["publicEpisodeId"])
        )
        lines.append(_relation_line(source_link, target_link, relation["labelKey"]))
    lines.append("")
    return lines


def render_canonical_timeline_page(
    projection: dict[str, Any], preflight_report: dict[str, Any]
) -> str:
    """preflight cleanなprojection candidateから単一Timeline pageを作る。"""
    if preflight_report != _CLEAN_PREFLIGHT:
        raise ValueError("canonical timeline public preflight is not clean")
    if projection.get("publishStatus") != "projection_candidate":
        raise ValueError("canonical timeline projection is not a candidate")

    front_matter = build_front_matter(
        {
            "title": "Canonical Timeline",
            "page_type": "timeline",
            "status": "projection_candidate",
            "generated_from": "canonical_timeline_public_projection",
        }
    )
    lines = [
        front_matter,
        "# Canonical Timeline",
        "",
        "> 確認済みの関係だけを辿るための補助ページです。"
        "全出来事の総順序を表すものではありません。",
        "",
        "表示対象は公開確認済みの関係に限られ、未確認の関係は掲載しません。",
        "",
    ]
    nodes_by_episode = _node_lookup(projection)
    if not projection["components"]:
        lines.extend(
            ["## 確認済み関係", "", "表示できる確認済み関係はありません。", ""]
        )
    else:
        for number, component in enumerate(projection["components"], start=1):
            lines.extend(_render_component(component, number, nodes_by_episode))

    summary = projection["unresolvedRelationSummary"]
    if summary is not None:
        lines.extend(
            [
                "## 未解決関係",
                "",
                "未解決関係の個別内容は公開せず、確認対象データ内の件数だけを示します。",
                "",
                f"- 不明: {summary['unknownCount']}",
                f"- 競合: {summary['conflictCount']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _expected_links(projection: dict[str, Any]) -> set[str]:
    links: set[str] = set()
    for component in projection["components"]:
        for node in component["nodes"]:
            links.add(_story_target(node["publicStoryId"]))
            links.add(_episode_target(node["publicEpisodeId"]))
    return links


def validate_canonical_timeline_page_links(
    markdown: str,
    projection: dict[str, Any],
    available_page_paths: set[str],
) -> list[dict[str, Any]]:
    """Timeline Markdownのlocal linkと生成対象存在をsafe countで検査する。"""
    expected = _expected_links(projection)
    observed = set(_MARKDOWN_LINK_TARGET.findall(markdown))
    available_targets = {
        f"../{path.replace('\\', '/')}" for path in available_page_paths
    }
    findings = []
    if missing_from_markdown := len(expected - observed):
        findings.append(
            {"rule": LINK_MISSING_FROM_MARKDOWN, "count": missing_from_markdown}
        )
    if missing_targets := len(expected - available_targets):
        findings.append({"rule": LINK_TARGET_MISSING, "count": missing_targets})
    if unexpected := len(observed - expected):
        findings.append({"rule": LINK_UNEXPECTED, "count": unexpected})
    return sorted(findings, key=lambda finding: finding["rule"])


__all__ = [
    "LINK_MISSING_FROM_MARKDOWN",
    "LINK_TARGET_MISSING",
    "LINK_UNEXPECTED",
    "canonical_timeline_page_path",
    "render_canonical_timeline_page",
    "validate_canonical_timeline_page_links",
]
