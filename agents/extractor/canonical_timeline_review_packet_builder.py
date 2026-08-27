"""検証済みStage A候補からCanonical Timeline review packetを構築する。"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .cross_story_constraint_inventory import (
    build_cross_story_constraint_inventory,
)

RETENTION_DAYS = 90


@dataclass(frozen=True)
class PacketBuildError(ValueError):
    """内部値を含まない固定codeのbuilder error。"""

    code: str
    available_story_pairs: int = 0

    def __str__(self) -> str:
        return self.code


def _stable_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _format_timestamp(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _episode_ref(story_id: str, episode_id: str) -> dict[str, str]:
    return {
        "storyId": story_id,
        "episodeId": episode_id,
        "storyCategory": "EVT",
    }


def _candidate_provenance(
    observation: dict[str, Any],
    target_ref: dict[str, Any],
) -> dict[str, Any]:
    return {
        "candidateId": observation["candidateId"],
        "sourceEpisode": _episode_ref(
            observation["sourceStoryId"], observation["sourceEpisodeId"]
        ),
        "targetEpisode": _episode_ref(target_ref["storyId"], target_ref["episodeId"]),
        "observedRelation": observation["relation"],
        "evidenceIds": list(observation["evidenceIds"]),
        "sourceType": observation["sourceType"],
        "confidence": observation["confidence"],
        "extractionRun": dict(observation["extractionRun"]),
    }


def _target_ref(observation: dict[str, Any]) -> dict[str, Any]:
    refs = observation["targetDocumentRefs"]
    if not refs:
        raise PacketBuildError("target-reference-missing")
    episode_keys = {
        (ref.get("storyId"), ref.get("episodeId"), ref.get("storyCategory"))
        for ref in refs
    }
    if len(episode_keys) != 1:
        raise PacketBuildError("target-reference-ambiguous")
    return refs[0]


def _review_edges(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    edge_shapes: dict[str, tuple[dict[str, str], dict[str, str], str]] = {}

    for observation in candidates:
        target = _target_ref(observation)
        source_episode = _episode_ref(
            observation["sourceStoryId"], observation["sourceEpisodeId"]
        )
        target_episode = _episode_ref(target["storyId"], target["episodeId"])
        relation = observation["relation"]
        group_key = _stable_value(
            {
                "from": source_episode,
                "to": target_episode,
                "relationState": relation,
            }
        )
        edge_shapes[group_key] = (source_episode, target_episode, relation)
        grouped[group_key].append(_candidate_provenance(observation, target))

    edges: list[dict[str, Any]] = []
    for edge_number, group_key in enumerate(sorted(grouped), start=1):
        source_episode, target_episode, relation = edge_shapes[group_key]
        edges.append(
            {
                "reviewEdgeKey": f"edge-{edge_number:04d}",
                "from": source_episode,
                "to": target_episode,
                "relationState": relation,
                "stateReason": None,
                "reviewStatus": "pending",
                "candidateProvenance": sorted(grouped[group_key], key=_stable_value),
                "humanDecision": None,
            }
        )
    return edges


def _packet_id(
    created_at: datetime,
    review_batch_id: str,
    story_ids: list[str],
    edges: list[dict[str, Any]],
) -> str:
    compact_timestamp = created_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    digest_input = _stable_value(
        {
            "createdAt": _format_timestamp(created_at),
            "reviewBatchId": review_batch_id,
            # local pathを含まないpacket内容だけを使い、候補変更時の衝突を避ける。
            "storyPair": story_ids,
            "edges": edges,
        }
    )
    digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:8]
    return f"ctrp-{compact_timestamp}-{digest}"


def build_canonical_timeline_review_packet(
    documents: list[tuple[str, dict[str, Any]]],
    *,
    story_pair_index: int,
    review_batch_id: str,
    created_at: datetime,
) -> dict[str, Any]:
    """明示的なcross-story候補1 pairをpending v0.2 packetへ変換する。

    `story_pair_index`は決定的にsortされたinventoryの1-based indexである。
    relationの推定・反転・採否・promotionは行わない。
    """
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise PacketBuildError("created-at-timezone-required")

    inventory = build_cross_story_constraint_inventory(documents)
    story_pairs = inventory["storyPairs"]
    if story_pair_index < 1 or story_pair_index > len(story_pairs):
        raise PacketBuildError(
            "story-pair-index-unavailable",
            available_story_pairs=len(story_pairs),
        )

    story_pair = story_pairs[story_pair_index - 1]
    created_at_utc = created_at.astimezone(timezone.utc).replace(microsecond=0)
    expires_at = created_at_utc + timedelta(days=RETENTION_DAYS)
    edges = _review_edges(story_pair["candidates"])
    if not edges:
        raise PacketBuildError("selected-story-pair-empty")

    return {
        "schemaVersion": "0.2",
        "documentType": "canonical_timeline_review_packet",
        "packetId": _packet_id(
            created_at_utc,
            review_batch_id,
            list(story_pair["storyIds"]),
            edges,
        ),
        "reviewBatchId": review_batch_id,
        "classification": "local_internal",
        "commitAllowed": False,
        "scopeStoryCategory": "EVT",
        "visibility": "internal_only",
        "createdAt": _format_timestamp(created_at_utc),
        "expiresAt": _format_timestamp(expires_at),
        "storyPair": [
            {"storyId": story_id, "storyCategory": "EVT"}
            for story_id in story_pair["storyIds"]
        ],
        "edges": edges,
    }
