"""
DKB Merger - Lore Entity Merge
Stage A LoreCandidateから Stage B merged lore entry を組み立てる。

merge key優先順位:
1. existingLoreId -> canonical IDとして自動merge
2. 無ければ、候補ごとに個別のunresolved entityとする
   (termName/loreNameのみでの自動マージは行わない)

LoreCandidateは他のCandidateと異なり名前候補配列が`termCandidates`
(Extraction_Result_Schema.md §10) であるため、entity_base.build_merged_entities
の`name_field`引数でそれを指定する。
"""

from __future__ import annotations

from typing import Any

from .entity_base import build_merged_entities


def _lore_merge_key(candidate: dict[str, Any]) -> tuple[str, str]:
    existing_id = candidate.get("existingLoreId")
    if existing_id:
        return ("id", existing_id)
    return ("unresolved", candidate["id"])


def build_lore_entities(
    valid_entries: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    return build_merged_entities(
        valid_entries,
        candidate_array_key="lore",
        entity_type="lore",
        id_prefix="LORE",
        merge_key_fn=_lore_merge_key,
        name_field="termCandidates",
    )
