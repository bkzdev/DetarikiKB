"""
DKB Merger - Special Speaker Label Entity Merge
Stage A SpecialSpeakerLabelCandidateから、通常のCharacter merged entityとは
別枠のspecial speaker labelエンティティを組み立てる。

merge key: rawLabel (sanitizeしたもの)。同一rawLabelを持つcandidate同士は
episodeをまたいで1件へ統合するが、canonical IDには一切解決しない
(status: unresolvedのまま固定、Merged_Knowledge_Design.md §4.1原則2と同じ
「名前一致だけで確定しない」方針をここでも徹底する)。

docs/architecture/06_AI/Merged_Knowledge_Design.md (Speaker Label Normalization設計)
"""

from __future__ import annotations

from typing import Any

from .entity_base import build_merged_entities

SPECIAL_SPEAKER_LABEL_CANDIDATE_ARRAY_KEY = "specialSpeakerLabelCandidates"
SPECIAL_SPEAKER_LABEL_ENTITY_TYPE = "special_speaker_label"
SPECIAL_SPEAKER_LABEL_ID_PREFIX = "SSL"


def _special_speaker_label_merge_key(candidate: dict[str, Any]) -> tuple[str, str]:
    """candidate単位で個別のunresolved entityとする。

    kind="unresolved"を返すことで、entity_base側の_resolve_entity_identity
    が常にstatus: unresolved・canonicalId: null・連番IDを割り当てる
    (自動でconfirmed昇格しない、§4参照)。rawLabelは日本語を含むため
    sanitize_id_segmentへ通すとほぼ確実に空文字列 (フォールバック値
    "UNKNOWN") に潰れて別ラベル同士が衝突する。character.pyの名前のみ
    candidate (_character_merge_key の第3分岐) と同じ、candidate IDを
    そのままkey_valueに使う安全な方式を踏襲する (エピソードをまたいだ
    同一rawLabelの自動統合はしない。unresolved characterの名前一致と
    同じ理由、Merged_Knowledge_Design.md §4.1原則2)。
    """
    return ("unresolved", candidate["id"])


def _special_speaker_label_extra_fields(
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """rawLabel/labelType/components/modifier/inferredSpeakers/
    resolutionStatusを、代表candidate (先頭) からそのまま引き継ぐ。

    同一merge key (sanitizeされたrawLabel) を持つcandidate群は、
    speaker_labels.analyze_speaker_labelの構造化結果が決定的に同じになる
    ため、代表値をそのまま採用してよい。
    """
    first = candidates[0]
    return {
        "displayName": first.get("rawLabel"),
        "rawLabel": first.get("rawLabel"),
        "labelSource": first.get("labelSource"),
        "labelType": first.get("labelType"),
        "components": list(first.get("components") or []),
        "modifier": first.get("modifier"),
        "baseLabel": first.get("baseLabel"),
        "inferredSpeakers": list(first.get("inferredSpeakers") or []),
        "resolutionStatus": first.get("resolutionStatus"),
    }


def build_special_speaker_label_entities(
    valid_entries: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """SpecialSpeakerLabelCandidateから special speaker label entityを
    組み立てる。

    通常のCharacter merged entity (`entities.characters`) には一切混ぜず、
    呼び出し側 (merge engine) が別キー (`entities.specialSpeakerLabels`)
    として保持すること。canonicalIdは常にnull、statusは常にunresolvedの
    ままとなる (merge_key_fnがkind="raw_label"を返すため)。
    """
    return build_merged_entities(
        valid_entries,
        candidate_array_key=SPECIAL_SPEAKER_LABEL_CANDIDATE_ARRAY_KEY,
        entity_type=SPECIAL_SPEAKER_LABEL_ENTITY_TYPE,
        id_prefix=SPECIAL_SPEAKER_LABEL_ID_PREFIX,
        merge_key_fn=_special_speaker_label_merge_key,
        extra_fields_fn=_special_speaker_label_extra_fields,
    )


def summarize_special_speaker_labels(
    entities: list[dict[str, Any]],
) -> dict[str, Any]:
    """special speaker label entity一覧から、report.specialSpeakerLabelSummary
    用の集計を作る (labelType別/resolutionStatus別の件数)。

    resolutionStatusは常にnot_applicable/needs_review/inferredのいずれかで
    あり (自動でconfirmedにはならない、build_special_speaker_label_entities
    参照)、この集計自体もconfirmed件数を作り出すものではない。
    """
    by_label_type: dict[str, int] = {}
    by_resolution_status: dict[str, int] = {}
    for entity in entities:
        label_type = entity.get("labelType") or "unknown"
        resolution_status = entity.get("resolutionStatus") or "needs_review"
        by_label_type[label_type] = by_label_type.get(label_type, 0) + 1
        by_resolution_status[resolution_status] = (
            by_resolution_status.get(resolution_status, 0) + 1
        )
    return {
        "total": len(entities),
        "byLabelType": by_label_type,
        "byResolutionStatus": by_resolution_status,
    }
