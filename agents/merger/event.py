"""
DKB Merger - Event Entity Merge
Stage A EventCandidateから Stage B merged event を組み立てる。

merge key優先順位:
1. existingEventId -> canonical IDとして自動merge
2. 無ければ、候補ごとに個別のunresolved entityとする
   (eventNameのみでの自動マージは行わない)

participantCandidates/locationCandidatesのcanonical entity IDへの解決
(participantEntityIds/locationEntityIds) は、candidate ID -> merged
entity IDの対応表 (Merged_Knowledge_Design.md §10.2) を前提とするため、
Relationship merge実装まで見送る (今回は空のまま)。
"""

from __future__ import annotations

from typing import Any

from .entity_base import build_merged_entities


def _event_merge_key(candidate: dict[str, Any]) -> tuple[str, str]:
    existing_id = candidate.get("existingEventId")
    if existing_id:
        return ("id", existing_id)
    return ("unresolved", candidate["id"])


def build_event_entities(
    valid_entries: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    return build_merged_entities(
        valid_entries,
        candidate_array_key="events",
        entity_type="event",
        id_prefix="EVENT",
        merge_key_fn=_event_merge_key,
    )
