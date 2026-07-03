"""
DKB Merger - Location Entity Merge
Stage A LocationCandidateから Stage B merged location を組み立てる。

merge key優先順位 (Merged_Knowledge_Design.md §5.2):
1. existingLocationId -> canonical IDとして自動merge
2. 無ければ、候補ごとに個別のunresolved entityとする
   (locationNameのみでの自動マージは行わない。「迷った場合」の
   安全側フォールバックを採用する)
"""

from __future__ import annotations

from typing import Any

from .entity_base import build_merged_entities


def _location_merge_key(candidate: dict[str, Any]) -> tuple[str, str]:
    existing_id = candidate.get("existingLocationId")
    if existing_id:
        return ("id", existing_id)
    return ("unresolved", candidate["id"])


def _location_extra_fields(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    scene_refs: list[str] = []
    for candidate in candidates:
        for scene_id in candidate.get("sceneRefs", []) or []:
            if scene_id not in scene_refs:
                scene_refs.append(scene_id)
    return {"sceneRefs": scene_refs}


def build_location_entities(
    valid_entries: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    return build_merged_entities(
        valid_entries,
        candidate_array_key="locations",
        entity_type="location",
        id_prefix="LOC",
        merge_key_fn=_location_merge_key,
        extra_fields_fn=_location_extra_fields,
    )
