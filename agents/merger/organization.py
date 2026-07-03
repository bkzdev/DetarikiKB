"""
DKB Merger - Organization Entity Merge
Stage A OrganizationCandidateから Stage B merged organization を組み立てる。

merge key優先順位 (Merged_Knowledge_Design.md §5.3):
1. existingOrganizationId -> canonical IDとして自動merge
2. 無ければ、候補ごとに個別のunresolved entityとする
   (organizationName/affiliationのみでの自動マージは行わない)
"""

from __future__ import annotations

from typing import Any

from .entity_base import build_merged_entities


def _organization_merge_key(candidate: dict[str, Any]) -> tuple[str, str]:
    existing_id = candidate.get("existingOrganizationId")
    if existing_id:
        return ("id", existing_id)
    return ("unresolved", candidate["id"])


def build_organization_entities(
    valid_entries: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    return build_merged_entities(
        valid_entries,
        candidate_array_key="organizations",
        entity_type="organization",
        id_prefix="ORG",
        merge_key_fn=_organization_merge_key,
    )
