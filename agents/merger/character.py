"""
DKB Merger - Character Entity Merge
Stage A CharacterCandidateから Stage B merged character を組み立てる。

merge key優先順位 (Merged_Knowledge_Design.md §5.1):
1. existingCharacterId (Parserが既知キャラクター辞書へ解決済み) -> canonical
   IDとして自動merge
2. sourceCharacterId (ゲーム内キャラクター番号。全ストーリーで安定と仮定
   できる) -> 同じ値のcandidate同士は安全にmergeするが、canonical ID
   ではないためstatusはunresolvedのまま
3. どちらも無ければ、候補ごとに個別のunresolved entityとする
   (名前一致だけでの自動マージはしない)

CharacterCandidate (Extraction_Result_Schema.md §6) にはexistingCharacterId/
sourceCharacterId以外の解決済み識別子フィールドが無いため、
「speakerId/characterId相当」を別途優先度3として確認する余地は無い
(existingCharacterIdが既にspeakerId解決結果そのものであるため)。
"""

from __future__ import annotations

from typing import Any

from .entity_base import build_merged_entities


def _character_merge_key(candidate: dict[str, Any]) -> tuple[str, str]:
    existing_id = candidate.get("existingCharacterId")
    if existing_id:
        return ("id", existing_id)

    source_character_id = candidate.get("sourceCharacterId")
    if source_character_id:
        return ("source_char_id", f"SRC_{source_character_id}")

    return ("unresolved", candidate["id"])


def _character_extra_fields(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    source_character_ids: list[str] = []
    for candidate in candidates:
        value = candidate.get("sourceCharacterId")
        if value and value not in source_character_ids:
            source_character_ids.append(value)
    return {"sourceCharacterIds": source_character_ids}


def build_character_entities(
    valid_entries: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    return build_merged_entities(
        valid_entries,
        candidate_array_key="characters",
        entity_type="character",
        id_prefix="CHAR",
        merge_key_fn=_character_merge_key,
        extra_fields_fn=_character_extra_fields,
    )
