"""Commit済みpublic inputだけからbuild用Markdown treeを構築する。"""

from __future__ import annotations

import html
import json
from typing import Any

from agents.extractor.canonical_timeline_public_input import (
    validate_canonical_timeline_public_input,
)
from agents.wiki_generator.canonical_timeline import (
    render_canonical_timeline_page,
    validate_canonical_timeline_page_links,
)
from agents.wiki_generator.models import build_front_matter

_CLEAN_PREFLIGHT = {
    "status": "clean",
    "publishStatus": "projection_candidate",
    "findings": [],
}


class PublicBuildError(ValueError):
    """Hosted public buildを匿名codeで拒否する。"""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _stable_value(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _component_is_connected(
    node_ids: set[str], relations: list[dict[str, Any]]
) -> bool:
    adjacent = {node_id: set() for node_id in node_ids}
    for relation in relations:
        left = relation["fromPublicEpisodeId"]
        right = relation["toPublicEpisodeId"]
        if left in adjacent and right in adjacent:
            adjacent[left].add(right)
            adjacent[right].add(left)
    visited: set[str] = set()
    pending = [next(iter(node_ids))]
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        pending.extend(adjacent[current] - visited)
    return visited == node_ids


def _record_component_nodes(
    component: dict[str, Any],
    episode_ids: set[str],
    story_labels: dict[str, str],
) -> tuple[set[str], set[str]]:
    findings: set[str] = set()
    local_ids = {node["publicEpisodeId"] for node in component["nodes"]}
    if len(local_ids) != len(component["nodes"]):
        findings.add("public-build-episode-id-duplicate")
    for node in component["nodes"]:
        episode_id = node["publicEpisodeId"]
        story_id = node["publicStoryId"]
        if episode_id in episode_ids:
            findings.add("public-build-episode-id-duplicate")
        episode_ids.add(episode_id)
        if story_id in story_labels and story_labels[story_id] != node["storyLabel"]:
            findings.add("public-build-story-label-conflict")
        story_labels[story_id] = node["storyLabel"]
    return local_ids, findings


def _component_relation_findings(
    component: dict[str, Any], local_ids: set[str]
) -> set[str]:
    findings: set[str] = set()
    relation_keys: set[tuple[str, str, str]] = set()
    pair_states: dict[tuple[str, str], set[tuple[str, str, str]]] = {}
    for relation in component["relations"]:
        left = relation["fromPublicEpisodeId"]
        right = relation["toPublicEpisodeId"]
        if left not in local_ids or right not in local_ids:
            findings.add("public-build-relation-endpoint-missing")
        if left == right:
            findings.add("public-build-self-relation")
        if relation["relationState"] == "before":
            key = (left, right, "ordered")
        elif relation["relationState"] == "after":
            key = (right, left, "ordered")
        else:
            first, second = sorted((left, right))
            key = (first, second, "same_time")
        if key in relation_keys:
            findings.add("public-build-relation-duplicate")
        relation_keys.add(key)
        pair = tuple(sorted((left, right)))
        pair_states.setdefault(pair, set()).add(key)
    if any(len(states) > 1 for states in pair_states.values()):
        findings.add("public-build-relation-conflict")
    if not _component_is_connected(local_ids, component["relations"]):
        findings.add("public-build-component-disconnected")
    return findings


def validate_public_build_projection(projection: dict[str, Any]) -> tuple[str, ...]:
    """Public input単独で検証できる構造・link意味論を固定codeで返す。"""
    findings: set[str] = set()
    episode_ids: set[str] = set()
    story_labels: dict[str, str] = {}
    expected_component_keys = [
        f"component-{number:04d}"
        for number in range(1, len(projection["components"]) + 1)
    ]
    if [
        item["componentKey"] for item in projection["components"]
    ] != expected_component_keys:
        findings.add("public-build-component-order-invalid")

    for component in projection["components"]:
        if component["nodes"] != sorted(component["nodes"], key=_stable_value):
            findings.add("public-build-node-order-invalid")
        if component["relations"] != sorted(component["relations"], key=_stable_value):
            findings.add("public-build-relation-order-invalid")
        local_ids, node_findings = _record_component_nodes(
            component, episode_ids, story_labels
        )
        findings.update(node_findings)
        findings.update(_component_relation_findings(component, local_ids))
    if {item.casefold() for item in story_labels} & {
        item.casefold() for item in episode_ids
    }:
        findings.add("public-build-page-path-collision")
    return tuple(sorted(findings))


def _safe_heading(value: str) -> str:
    escaped = html.escape(value, quote=True).replace("\\", "\\\\")
    for marker in "`*_{}[]()#+-.!|>":
        escaped = escaped.replace(marker, f"\\{marker}")
    return escaped


def _stub_page(title: str, page_type: str, description: str) -> str:
    safe_title = html.escape(title, quote=True)
    front_matter = build_front_matter(
        {
            "title": safe_title,
            "page_type": page_type,
            "status": "projection_candidate",
            "generated_from": "canonical_timeline_public_projection",
        }
    )
    return f"{front_matter}# {_safe_heading(title)}\n\n{description}\n"


def build_public_source_files(public_input: dict[str, Any]) -> dict[str, bytes]:
    """検証済みenvelopeから決定的なpublic-only source file群を返す。"""
    if validate_canonical_timeline_public_input(public_input):
        raise PublicBuildError("public-build-input-invalid")
    projection = public_input["projection"]
    if findings := validate_public_build_projection(projection):
        raise PublicBuildError(findings[0])

    files: dict[str, bytes] = {}
    nodes = [
        node for component in projection["components"] for node in component["nodes"]
    ]
    for story_id in sorted({node["publicStoryId"] for node in nodes}):
        node = next(item for item in nodes if item["publicStoryId"] == story_id)
        files[f"stories/{story_id}.md"] = _stub_page(
            node["storyLabel"],
            "story",
            "確認済み関係に含まれる合成公開ストーリーです。",
        ).encode("utf-8")
    for node in sorted(nodes, key=lambda item: item["publicEpisodeId"]):
        files[f"stories/{node['publicEpisodeId']}.md"] = _stub_page(
            node["episodeLabel"],
            "episode",
            "確認済み関係に含まれる合成公開エピソードです。",
        ).encode("utf-8")

    available = set(files)
    timeline = render_canonical_timeline_page(projection, _CLEAN_PREFLIGHT)
    if validate_canonical_timeline_page_links(timeline, projection, available):
        raise PublicBuildError("public-build-link-validation-failed")
    files["timelines/index.md"] = timeline.encode("utf-8")
    files["index.md"] = (
        "# 合成公開ビルド\n\n"
        "公開用ビルド経路を検証する合成ページです。\n\n"
        "[Canonical Timeline](timelines/index.md)\n"
    ).encode("utf-8")
    return dict(sorted(files.items(), key=lambda item: item[0].encode("utf-8")))


__all__ = [
    "PublicBuildError",
    "build_public_source_files",
    "validate_public_build_projection",
]
