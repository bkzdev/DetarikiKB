"""
DKB Merger - Item Entity Merge
Stage A ItemCandidateから Stage B merged item を組み立てる。

merge key優先順位:
1. existingItemId -> canonical IDとして自動merge
2. 無ければ、候補ごとに個別のunresolved entityとする
   (itemNameのみでの自動マージは行わない。「迷った場合」の
   安全側フォールバックを採用する)
"""

from __future__ import annotations

from typing import Any

from .entity_base import build_merged_entities


def _item_merge_key(candidate: dict[str, Any]) -> tuple[str, str]:
    existing_id = candidate.get("existingItemId")
    if existing_id:
        return ("id", existing_id)
    return ("unresolved", candidate["id"])


def build_item_entities(
    valid_entries: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    return build_merged_entities(
        valid_entries,
        candidate_array_key="items",
        entity_type="item",
        id_prefix="ITEM",
        merge_key_fn=_item_merge_key,
    )
