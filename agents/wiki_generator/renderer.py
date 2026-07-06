"""
DKB Wiki Generator - Renderer skeleton
merged knowledge collection (schemas/merged_knowledge_collection.schema.json)
から、最小限のWiki Markdownを生成する。

docs/architecture/07_Wiki/Wiki_Output_Design.md のPhase 1のうち、
Top page / Story index / Characters index / Episode page (簡易) /
Character page / Unresolved report page のみを実装する
(Location/Organization/Item/Lore/Event page、Relationship section、
Timeline page、AI analysis pageはNon-goals。将来のPRで拡張する)。

**重要な制約**:
- 元セリフ全文は一切出力しない。evidenceRefsはevidenceId/episodeId/
  sceneId/blockIdの参照情報のみを表示する (Wiki_Output_Design.md §4)。
- canonicalIdが確定し status: mergedのentityのみ個別ページを生成する。
  それ以外 (canonicalId未確定、status: unresolved/conflict/deprecated)
  は個別ページを生成せず、reports/unresolved.mdへ集約する (§5)。
- テンプレートエンジン (Jinja2等) の依存追加はまだ行わない。将来の
  差し替えを見据え、ページ種別ごとに独立した関数へ分割してある
  (Wiki_Output_Design.md §12.2)。
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from agents.parser.character_profiles import Birthday, CharacterProfile, Reading

from .models import (
    ENTITY_KEY_TO_TYPE,
    GENERATED_FROM,
    MERGED_ENTITY_KEYS,
    build_front_matter,
)
from .paths import character_page_path, episode_page_path, is_page_eligible

CharacterProfileIndex = dict[str, CharacterProfile]


def _format_evidence_ref(ref: dict[str, Any]) -> str:
    """1件のevidenceRefを、参照情報のみの1行に整形する
    (evidenceId/episodeId/sceneId/blockId。textExcerpt等の本文は含めない)。
    """
    parts = [f"evidenceId: {ref.get('evidenceId', '?')}"]
    if ref.get("episodeId"):
        parts.append(f"episodeId: {ref['episodeId']}")
    if ref.get("sceneId"):
        parts.append(f"sceneId: {ref['sceneId']}")
    if ref.get("blockId"):
        parts.append(f"blockId: {ref['blockId']}")
    return " / ".join(parts)


def _render_evidence_section(entity: dict[str, Any]) -> list[str]:
    evidence_refs = entity.get("evidenceRefs") or []
    lines = ["## Evidence", ""]
    if not evidence_refs:
        lines.append("(evidenceRefsがありません)")
        lines.append("")
        return lines
    lines.append(f"{len(evidence_refs)} 件の参照:")
    lines.append("")
    for ref in evidence_refs:
        lines.append(f"- {_format_evidence_ref(ref)}")
    lines.append("")
    return lines


def _render_conflicts_section(entity: dict[str, Any]) -> list[str]:
    conflicts = entity.get("conflicts") or []
    lines = ["## Conflicts", ""]
    if not conflicts:
        lines.append("記録されている矛盾はありません。")
        lines.append("")
        return lines
    lines.append(f"{len(conflicts)} 件の矛盾が記録されています:")
    lines.append("")
    for conflict in conflicts:
        conflict_type = conflict.get("conflictType", "unknown")
        severity = conflict.get("severity", "unknown")
        resolution = conflict.get("resolutionStatus", "unresolved")
        field = conflict.get("field")
        field_part = f", field: {field}" if field else ""
        lines.append(
            f"- {conflict_type}（severity: {severity}{field_part}, {resolution}）"
        )
    lines.append("")
    return lines


def _render_aliases_section(entity: dict[str, Any]) -> list[str]:
    aliases = entity.get("aliases") or []
    lines = ["## Aliases", ""]
    if not aliases:
        lines.append("別名は登録されていません。")
        lines.append("")
        return lines
    for alias in aliases:
        lines.append(f"- {alias}")
    lines.append("")
    return lines


def _format_source_candidate(candidate: dict[str, Any]) -> str:
    """1件のsourceCandidateを、summaryのみの1行に整形する
    (candidateId/candidateType/episodeId/evidenceIds件数/
    sourceDocumentId。元candidateの本文・raw payloadは含めない)。
    """
    parts = [f"candidateId: {candidate.get('candidateId', '?')}"]
    if candidate.get("candidateType"):
        parts.append(f"candidateType: {candidate['candidateType']}")
    if candidate.get("episodeId"):
        parts.append(f"episodeId: {candidate['episodeId']}")
    parts.append(f"evidenceIds件数: {len(candidate.get('evidenceIds') or [])}")
    if candidate.get("sourceDocumentId"):
        parts.append(f"sourceDocumentId: {candidate['sourceDocumentId']}")
    return " / ".join(parts)


def _render_source_candidates_section(entity: dict[str, Any]) -> list[str]:
    candidates = entity.get("sourceCandidates") or []
    lines = ["## Source Candidates", ""]
    if not candidates:
        lines.append("由来candidateはありません。")
        lines.append("")
        return lines
    lines.append(f"{len(candidates)} 件のcandidateから統合:")
    lines.append("")
    for candidate in candidates:
        lines.append(f"- {_format_source_candidate(candidate)}")
    lines.append("")
    return lines


def _format_or_placeholder(value: str | None) -> str:
    return value if value else "未登録"


def _format_code(value: str | None) -> str:
    """値をcode表示 (`value`) にする。値が無ければ「未登録」
    (IDやpath等、横長tableの代わりに箇条書きで使う際の共通ヘルパー)。"""
    if not value:
        return "未登録"
    return f"`{value}`"


def _render_key_value_list(items: list[tuple[str, str]]) -> list[str]:
    """(ラベル, 値) のリストを箇条書き (definition list風) へ変換する
    共通ヘルパー。長い値 (ID・path・タイトル等) が横長tableの1セルに
    収まらず横スクロールを招く問題を避けるため、tableの代わりに使う
    (manual visual review 001での指摘、Wiki_Output_Design.md §9.3)。"""
    lines = [f"- {label}: {value}" for label, value in items]
    lines.append("")
    return lines


# story_manifest.yaml由来のmetadataStatus (Story_Manifest_Design.md §12) を
# 表示用に補足する。未知の値が来ても破棄せずそのまま表示する。
_METADATA_STATUS_LABELS: dict[str, str] = {
    "pending": "pending（未確認）",
    "confirmed": "confirmed（確認済み）",
    "title_unknown": "title_unknown（タイトル不明と判明）",
    "deprecated": "deprecated（廃止）",
}


def _missing_value_label() -> str:
    """値が未登録・未設定であることを示す共通プレースホルダー。"""
    return "未登録"


def _format_metadata_status(status: str | None) -> str:
    """story_manifest.yaml由来のmetadataStatusを表示用に整形する。

    pending/confirmed/title_unknown/deprecatedには日本語の補足を付ける。
    未知の値もそのまま表示し (破棄しない)、Noneの場合は未登録扱いとする。
    """
    if not status:
        return _missing_value_label()
    return _METADATA_STATUS_LABELS.get(status, status)


def _get_episode_display_title(source_document: dict[str, Any]) -> str:
    """このepisodeの一覧表示用タイトルを優先順位に従って解決する。

    displayTitle > episodeSubtitle > storyTitle > episodeId
    (Story_Manifest_Design.md §11.3のfallback方針をStory index等の一覧
    表示に適用したもの)。いずれも未設定の場合は既存どおりepisodeIdを
    返す。DEC本文からの推測やAI生成titleは行わない。
    """
    for key in ("displayTitle", "episodeSubtitle", "storyTitle"):
        value = source_document.get(key)
        if value:
            return value
    return source_document.get("episodeId") or source_document.get("documentId") or "?"


def _format_affiliation(affiliation: list[str]) -> str:
    if not affiliation:
        return "未登録"
    return "、".join(affiliation)


def _format_height_cm(height_cm: int | None) -> str:
    if height_cm is None:
        return "未登録"
    return f"{height_cm}cm"


def _format_birthday(birthday: Birthday | None) -> str:
    """birthday.displayを優先し、無ければmonth/dayから組み立てる
    (Character_Profile_Dictionary_Design.md §7)。"""
    if birthday is None:
        return "未登録"
    if birthday.display:
        return birthday.display
    if birthday.month is not None and birthday.day is not None:
        return f"{birthday.month}/{birthday.day}"
    return "未登録"


def _format_reading(reading: Reading | None) -> tuple[str, str]:
    if reading is None:
        return "未登録", "未登録"
    return (
        _format_or_placeholder(reading.kana),
        _format_or_placeholder(reading.romaji),
    )


def _format_profile_highlight(highlight: Any) -> str:
    """profileHighlightを「【label】value」形式の1行へ整形する
    (Wiki記載と同じ雰囲気の表示、Character_Profile_Dictionary_Design.md
    §7)。基本プロフィール表の「特記事項」行として使う。

    label/valueの両方があれば「【label】value」、labelのみなら
    「【label】」、valueのみならvalueそのもの、どちらも無い・highlight
    自体がNoneの場合は「未登録」(既存の他フィールドと同じfallback表記)。
    """
    if highlight is None:
        return "未登録"
    label = highlight.label or None
    value = highlight.value or None
    if label and value:
        return f"【{label}】{value}"
    if label:
        return f"【{label}】"
    if value:
        return value
    return "未登録"


def _render_self_introduction_lines(self_introduction: str | None) -> list[str]:
    """selfIntroductionは複数行を想定するため、そのままMarkdown本文として
    表示する (AI要約・AI考察とは別sectionとして分離、Character_Profile_
    Dictionary_Design.md §7)。"""
    lines = ["### 自己紹介", ""]
    if not self_introduction:
        lines.append("自己紹介は登録されていません。")
    else:
        lines.append(self_introduction)
    lines.append("")
    return lines


def _render_basic_profile_section(
    entity: dict[str, Any], character_profiles: CharacterProfileIndex | None
) -> list[str]:
    """「基本プロフィール」sectionを組み立てる (Wiki_Output_Design.md §9.4、
    Character_Profile_Dictionary_Design.md §7)。

    entityのcanonicalId (= characters.yamlのconfirmed済みcharacterId) と
    character_profiles.yamlのcharacterIdが一致した場合のみプロフィールを
    表示する。該当プロフィールが無い場合は「プロフィール未登録」と表示し、
    section自体は省略しない。AI抽出・merge由来の`## Summary`等とは
    明確に区別する。
    """
    lines = ["## 基本プロフィール", ""]

    canonical_id = entity.get("canonicalId")
    profile = (
        character_profiles.get(canonical_id)
        if character_profiles and canonical_id
        else None
    )
    if profile is None:
        lines.append("プロフィール未登録")
        lines.append("")
        return lines

    kana, romaji = _format_reading(profile.reading)

    lines.append("| 項目 | 値 |")
    lines.append("|---|---|")
    lines.append(f"| 名前 | {profile.display_name} |")
    lines.append(f"| ふりがな | {kana} |")
    lines.append(f"| ローマ字 | {romaji} |")
    lines.append(f"| 所属 | {_format_affiliation(profile.affiliation)} |")
    lines.append(f"| 身長 | {_format_height_cm(profile.height_cm)} |")
    lines.append(f"| 誕生日 | {_format_birthday(profile.birthday)} |")
    lines.append(f"| 血液型 | {_format_or_placeholder(profile.blood_type)} |")
    lines.append(f"| CV | {_format_or_placeholder(profile.cv)} |")
    lines.append(
        f"| 特記事項 | {_format_profile_highlight(profile.profile_highlight)} |"
    )
    lines.append(f"| Status | {profile.status} |")
    lines.append("")
    # profile source (出典) はcharacter_profiles.yaml側にはデータとして
    # 保持するが、Wiki表示上は出さない方針 (manual visual reviewでの
    # ユーザー要望)。source情報自体の削除・schema変更は行っていない。

    lines.extend(_render_self_introduction_lines(profile.self_introduction))

    return lines


def render_character_page(
    entity: dict[str, Any],
    character_profiles: CharacterProfileIndex | None = None,
) -> str:
    """Character pageを生成する (Wiki_Output_Design.md §9.4)。

    呼び出し側は`is_page_eligible(entity)`がTrueの場合のみこの関数を
    呼ぶこと (canonicalId未確定のentityを渡さない)。

    `character_profiles`は`characterId -> CharacterProfile`の索引
    (`agents.parser.character_profiles.build_character_profile_index`の
    戻り値)。Noneの場合は「基本プロフィール」sectionを「プロフィール
    未登録」表示のまま出力する (呼び出し元が`--character-profiles`を
    指定しなかった場合も既存の出力を壊さない)。
    """
    display_name = entity.get("displayName") or entity.get("id", "")
    source_types = entity.get("sourceTypes") or []
    front_matter = build_front_matter(
        {
            "title": display_name,
            "entity_type": "character",
            "entity_id": entity.get("id"),
            "canonical_id": entity.get("canonicalId"),
            "status": entity.get("status"),
            "confidence": entity.get("confidence"),
            "source_types": ", ".join(source_types) if source_types else None,
            "generated_from": GENERATED_FROM,
        }
    )

    lines = [front_matter, f"# {display_name}", ""]

    lines.append("## Summary")
    lines.append("")
    lines.append("| 項目 | 値 |")
    lines.append("|---|---|")
    lines.append(f"| Entity ID | {entity.get('id', '')} |")
    lines.append(f"| Canonical ID | {entity.get('canonicalId', '')} |")
    lines.append(f"| Status | {entity.get('status', '')} |")
    lines.append(f"| Confidence | {entity.get('confidence', '')} |")
    source_types_display = (
        ", ".join(source_types) if source_types else "情報源区分は記録されていません。"
    )
    lines.append(f"| Source types | {source_types_display} |")
    lines.append("")

    lines.extend(_render_basic_profile_section(entity, character_profiles))
    lines.extend(_render_aliases_section(entity))
    lines.extend(_render_evidence_section(entity))
    lines.extend(_render_source_candidates_section(entity))
    lines.extend(_render_conflicts_section(entity))

    return "\n".join(lines).rstrip() + "\n"


# report.warnings / canonicalIdSummary.warningsを表示する際の最大件数。
# 超過分は件数のみ「...他N件」として要約する (生ログを丸ごと出さない方針)。
_MAX_WARNINGS_DISPLAYED = 10

# 1件のwarningメッセージとして表示する最大文字数。実データ由来の長い
# 引用が万一混入していても、丸ごと転載しないための安全策。
_MAX_WARNING_MESSAGE_LENGTH = 200


def _render_overview_section(collection: dict[str, Any]) -> list[str]:
    """Unresolved reportの概要 (Overview) セクションを組み立てる。

    report.unresolvedEntityCounts / conflictCounts.total /
    warningCounts.total / canonicalIdSummary.invalidCount・duplicateCount
    から集計する (Wiki_Output_Design.md §9.12拡張)。
    """
    report = collection.get("report", {}) or {}
    unresolved_counts = report.get("unresolvedEntityCounts") or {}
    total_unresolved = sum(unresolved_counts.values())
    total_conflicts = (report.get("conflictCounts") or {}).get(
        "total", report.get("conflictsCount", 0)
    )
    total_warnings = (report.get("warningCounts") or {}).get("total", 0)
    canonical_id_summary = report.get("canonicalIdSummary") or {}
    invalid_count = canonical_id_summary.get("invalidCount", 0)
    duplicate_count = canonical_id_summary.get("duplicateCount", 0)

    return [
        "## Overview",
        "",
        "| Field | Value |",
        "|---|---:|",
        f"| Total unresolved entities | {total_unresolved} |",
        f"| Total conflicts | {total_conflicts} |",
        f"| Total warnings | {total_warnings} |",
        f"| Invalid canonical IDs | {invalid_count} |",
        f"| Duplicate canonical IDs | {duplicate_count} |",
        "",
    ]


def _render_entity_type_sections(collection: dict[str, Any]) -> tuple[list[str], int]:
    """entity種別ごとのunresolved一覧セクション群を組み立てる。

    Canonical ID列を持つ表を、種別 (Character/Location/...) ごとに出力
    する。戻り値は (行リスト, 総unresolved件数)。件数が0の種別はセクション
    ごと省略する。EvidenceとSource Candidatesはそれぞれ独立した列だと
    横長になる (manual visual review 001での指摘) ため、「Refs」列へ
    「evidence件数/source candidate件数」の形式で統合する
    (件数情報自体は失わない)。
    """
    entities = collection.get("entities", {}) or {}
    lines: list[str] = []
    total_unresolved = 0
    for entity_key in MERGED_ENTITY_KEYS:
        unresolved = [
            e for e in (entities.get(entity_key) or []) if not is_page_eligible(e)
        ]
        if not unresolved:
            continue
        total_unresolved += len(unresolved)
        entity_type = ENTITY_KEY_TO_TYPE[entity_key]
        lines.append(f"## {entity_type} ({len(unresolved)} 件)")
        lines.append("")
        lines.append("| Display Name | Entity ID | Status | Canonical ID | Refs |")
        lines.append("|---|---|---|---|---:|")
        for e in unresolved:
            evidence_count = len(e.get("evidenceRefs") or [])
            candidate_count = len(e.get("sourceCandidates") or [])
            lines.append(
                f"| {e.get('displayName') or '(不明)'} "
                f"| {_format_code(e.get('id'))} "
                f"| {e.get('status', '')} "
                f"| {_format_code(e.get('canonicalId'))} "
                f"| {evidence_count}/{candidate_count} |"
            )
        lines.append("")
    return lines, total_unresolved


def _render_conflict_summary_section(collection: dict[str, Any]) -> list[str]:
    """Conflict summaryセクションを組み立てる。

    report.conflictCounts.bySeverity/byType/byEntityTypeを
    | Group | Value | Count | の表で表示する。自動解決は行わない。
    """
    conflict_counts = (collection.get("report", {}) or {}).get("conflictCounts") or {}
    lines = ["## Conflict Summary", ""]
    if not conflict_counts.get("total"):
        lines.append("記録されている矛盾はありません。")
        lines.append("")
        return lines

    lines.append("| Group | Value | Count |")
    lines.append("|---|---|---:|")
    for group_label, group_key in (
        ("Severity", "bySeverity"),
        ("Type", "byType"),
        ("Entity Type", "byEntityType"),
    ):
        for value, count in (conflict_counts.get(group_key) or {}).items():
            lines.append(f"| {group_label} | {value} | {count} |")
    lines.append("")
    return lines


def _render_warning_summary_section(collection: dict[str, Any]) -> list[str]:
    """Warning summaryセクションを組み立てる。

    report.warningCounts (total/unresolvedRelationships/skippedOverrides/
    other) を表で示し、report.warningsは先頭_MAX_WARNINGS_DISPLAYED件のみ
    列挙する (生payload・長い引用は出さない)。
    """
    report = collection.get("report", {}) or {}
    warning_counts = report.get("warningCounts") or {}
    unresolved_relationships = warning_counts.get("unresolvedRelationships", 0)
    lines = [
        "## Warning Summary",
        "",
        "| Field | Value |",
        "|---|---:|",
        f"| Total | {warning_counts.get('total', 0)} |",
        f"| Unresolved Relationships | {unresolved_relationships} |",
        f"| Skipped Overrides | {warning_counts.get('skippedOverrides', 0)} |",
        f"| Other | {warning_counts.get('other', 0)} |",
        "",
    ]
    lines.extend(_render_capped_list(report.get("warnings") or []))
    return lines


def _truncate_message(message: str) -> str:
    """1件のwarningメッセージが長すぎる場合に切り詰める。

    実データ由来のwarningメッセージに万一長い引用が混入していても、
    reportが実データ本文を大量に転載しないようにするための安全策。
    """
    if len(message) <= _MAX_WARNING_MESSAGE_LENGTH:
        return message
    return message[:_MAX_WARNING_MESSAGE_LENGTH] + "...(省略)"


def _render_capped_list(items: list[str]) -> list[str]:
    """文字列リストを先頭_MAX_WARNINGS_DISPLAYED件のみ列挙し、超過分は
    件数のみ要約する共通ヘルパー (warnings / canonicalIdSummary.warnings
    双方で使う)。各項目が長すぎる場合は_truncate_messageで切り詰める。
    """
    if not items:
        return []
    lines = []
    for item in items[:_MAX_WARNINGS_DISPLAYED]:
        lines.append(f"- {_truncate_message(str(item))}")
    remaining = len(items) - _MAX_WARNINGS_DISPLAYED
    if remaining > 0:
        lines.append(f"- ...他 {remaining} 件")
    lines.append("")
    return lines


def _render_canonical_id_summary_section(collection: dict[str, Any]) -> list[str]:
    """Canonical ID summaryセクションを組み立てる。

    report.canonicalIdSummaryはschema上任意フィールドのため、無い場合は
    セクション自体を省略する (Validationセクションと同じ方針)。
    """
    canonical_id_summary = (collection.get("report", {}) or {}).get(
        "canonicalIdSummary"
    )
    if canonical_id_summary is None:
        return []
    lines = [
        "## Canonical ID Summary",
        "",
        "| Field | Value |",
        "|---|---:|",
        f"| Total Assigned | {canonical_id_summary.get('totalAssigned', 0)} |",
        f"| Duplicate Count | {canonical_id_summary.get('duplicateCount', 0)} |",
        f"| Invalid Count | {canonical_id_summary.get('invalidCount', 0)} |",
        "",
    ]
    lines.extend(_render_capped_list(canonical_id_summary.get("warnings") or []))
    return lines


def _render_relationship_type_summary_section(
    collection: dict[str, Any],
) -> list[str]:
    """Relationship type summaryセクションを組み立てる。

    report.relationshipTypeSummaryはschema上任意フィールドのため、無い
    場合はセクション自体を省略する。unknownTypesは自動修正せず、目立つ
    見出しで一覧表示するのみ (Wiki_Output_Design.md方針)。
    """
    relationship_type_summary = (collection.get("report", {}) or {}).get(
        "relationshipTypeSummary"
    )
    if relationship_type_summary is None:
        return []
    known_types = relationship_type_summary.get("knownTypes") or {}
    unknown_types = relationship_type_summary.get("unknownTypes") or {}
    normalized_types = relationship_type_summary.get("normalizedTypes") or {}

    lines = [
        "## Relationship Type Summary",
        "",
        "| Field | Count |",
        "|---|---:|",
        f"| Known Types | {len(known_types)} |",
        f"| Unknown Types | {len(unknown_types)} |",
        f"| Normalized Types | {len(normalized_types)} |",
        "",
    ]
    if unknown_types:
        lines.append("**Unknown Types（未知のrelationshipType。要確認）:**")
        lines.append("")
        for type_name, count in unknown_types.items():
            lines.append(f"- {type_name}（{count} 件）")
        lines.append("")
    return lines


def render_unresolved_report(collection: dict[str, Any]) -> str:
    """Unresolved report page (reports/unresolved.md) を生成する
    (Wiki_Output_Design.md §9.12)。

    canonicalId未確定、またはstatusがmerged以外の全entity種別
    (character/location/organization/item/lore/event/relationship/
    timeline) を対象とする。件数が0の種別はセクションごと省略する。
    Overview / entity種別別一覧 / Conflict summary / Warning summary /
    Canonical ID summary / Relationship type summaryを表示する。
    いずれも自動解決・自動修正は行わず、集計値と参照情報のみを示す。
    """
    front_matter = build_front_matter(
        {
            "title": "Unresolved Entities Report",
            "generated_from": GENERATED_FROM,
        }
    )
    lines = [
        front_matter,
        "# Unresolved Entities Report",
        "",
        (
            "canonicalIdが未確定、または解決状態にないentityの一覧です。"
            "個別ページはまだ生成されていません。"
        ),
        "",
    ]

    lines.extend(_render_overview_section(collection))

    entity_section_lines, total_unresolved = _render_entity_type_sections(collection)
    lines.extend(entity_section_lines)
    if total_unresolved == 0:
        lines.append("未解決のentityはありません。")
        lines.append("")

    lines.extend(_render_conflict_summary_section(collection))
    lines.extend(_render_warning_summary_section(collection))
    lines.extend(_render_canonical_id_summary_section(collection))
    lines.extend(_render_relationship_type_summary_section(collection))

    return "\n".join(lines).rstrip() + "\n"


def render_index_page(collection: dict[str, Any]) -> str:
    """Top page (index.md) を生成する (Wiki_Output_Design.md §9.1)。"""
    report = collection.get("report", {}) or {}
    merged_counts = report.get("mergedEntityCounts", {}) or {}
    unresolved_counts = report.get("unresolvedEntityCounts", {}) or {}
    source_documents = collection.get("sourceDocuments", []) or []

    front_matter = build_front_matter(
        {"title": "Detariki Knowledge Base Wiki", "generated_from": GENERATED_FROM}
    )
    lines = [
        front_matter,
        "# Detariki Knowledge Base Wiki",
        "",
        "## サマリー",
        "",
        "| 項目 | 値 |",
        "|---|---|",
        f"| 収録エピソード数 | {len(source_documents)} |",
    ]
    for entity_key in MERGED_ENTITY_KEYS:
        entity_type = ENTITY_KEY_TO_TYPE[entity_key]
        lines.append(
            f"| {entity_type} (merged / unresolved) "
            f"| {merged_counts.get(entity_key, 0)} / "
            f"{unresolved_counts.get(entity_key, 0)} |"
        )
    lines.append("")
    lines.append("## リンク")
    lines.append("")
    lines.append("- [Story index](stories/index.md)")
    lines.append("- [Characters](characters/index.md)")
    lines.append("- [Unresolved report](reports/unresolved.md)")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_story_index_page(collection: dict[str, Any]) -> str:
    """Story index page (stories/index.md) を生成する
    (Wiki_Output_Design.md §9.2)。
    """
    source_documents = collection.get("sourceDocuments", []) or []
    front_matter = build_front_matter(
        {"title": "Story Index", "generated_from": GENERATED_FROM}
    )
    lines = [front_matter, "# Story Index", ""]

    if not source_documents:
        lines.append("収録されているエピソードはありません。")
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    # 列数を最小限にする (manual visual review 001での「表が横長すぎる」
    # 指摘)。documentId (通常episodeIdと同値) とcandidate合計 (Episode
    # pageのCandidate Counts sectionで確認できる詳細情報) は表から外す。
    # 情報自体は失わず、Episode page側で引き続き確認できる。
    lines.append("| storyId | Episode | Display Title | status | category |")
    lines.append("|---|---|---|---|---|")
    for doc in source_documents:
        episode_path = episode_page_path(doc)
        # stories/index.md自身がstories/配下にあるため、episode_page_pathが
        # 返す"stories/{episodeId}.md"をそのままリンク先にすると
        # "stories/stories/{episodeId}.md"という壊れた相対リンクになる。
        # ファイル名部分だけをリンク先にする (MkDocsでの相対リンク切れ対策)。
        episode_filename = episode_path.rsplit("/", 1)[-1] if episode_path else None
        episode_id = doc.get("episodeId") or doc.get("documentId") or "?"
        episode_link = (
            f"[{episode_id}]({episode_filename})" if episode_filename else episode_id
        )
        display_title = _get_episode_display_title(doc)
        input_result = _find_input_result(collection, doc)
        status = input_result.get("status", "") if input_result else ""
        lines.append(
            f"| {doc.get('storyId', '?')} "
            f"| {episode_link} "
            f"| {display_title} "
            f"| {status} "
            f"| {doc.get('storyCategory', '')} |"
        )
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _has_registered_profile(
    entity: dict[str, Any], character_profiles: CharacterProfileIndex | None
) -> bool:
    """entityのcanonicalIdに一致するprofileがcharacter_profilesに
    登録されているかを判定する (`_render_basic_profile_section`と同じ
    照合ロジック)。"""
    canonical_id = entity.get("canonicalId")
    if not character_profiles or not canonical_id:
        return False
    return character_profiles.get(canonical_id) is not None


def render_character_index_page(
    characters: list[dict[str, Any]],
    character_profiles: CharacterProfileIndex | None = None,
) -> str:
    """Characters index page (characters/index.md) を生成する
    (Wiki_Output_Design.md §9.4、Top pageからCharacter pageへの導線)。

    `is_page_eligible`がTrueのcharacterのみを一覧表示する。unresolved・
    canonicalId未確定・status不一致のcharacterはここには載せず、
    `reports/unresolved.md`側でのみ確認できるようにする (§5)。表は列数を
    抑え、横スクロールが発生しにくい構成にする
    （詳細な可読性改善は`feature/wiki-renderer-readability-improvements`）。
    """
    eligible = sorted(
        (c for c in characters if is_page_eligible(c)),
        key=lambda c: c.get("canonicalId") or "",
    )
    with_profile_count = sum(
        1 for c in eligible if _has_registered_profile(c, character_profiles)
    )
    without_profile_count = len(eligible) - with_profile_count

    front_matter = build_front_matter(
        {"title": "Characters", "generated_from": GENERATED_FROM}
    )
    lines = [front_matter, "# キャラクター一覧", ""]

    lines.append("## Overview")
    lines.append("")
    lines.append("| 項目 | 値 |")
    lines.append("|---|---:|")
    lines.append(f"| Character pages | {len(eligible)} |")
    lines.append(f"| プロフィール登録あり | {with_profile_count} |")
    lines.append(f"| プロフィール未登録 | {without_profile_count} |")
    lines.append("")
    lines.append(
        "未解決キャラクターは[Unresolved report](../reports/unresolved.md)"
        "を参照してください。"
    )
    lines.append("")

    lines.append("## Character List")
    lines.append("")
    if not eligible:
        lines.append("登録されているCharacter pageはありません。")
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    lines.append("| Character | Profile | ID |")
    lines.append("|---|---|---|")
    for entity in eligible:
        canonical_id = entity.get("canonicalId")
        display_name = entity.get("displayName") or canonical_id
        page_path = character_page_path(entity)
        # characters/index.md自身がcharacters/配下にあるため、
        # character_page_pathが返す"characters/{canonicalId}.md"を
        # そのままリンク先にすると"characters/characters/..."という
        # 壊れた相対リンクになる (stories/index.mdと同じ既知の対策)。
        filename = page_path.rsplit("/", 1)[-1] if page_path else None
        name_link = f"[{display_name}]({filename})" if filename else display_name
        profile_label = (
            "登録あり"
            if _has_registered_profile(entity, character_profiles)
            else "未登録"
        )
        lines.append(f"| {name_link} | {profile_label} | `{canonical_id}` |")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# sourceDocuments[].candidateCounts / report.candidateCountsのキー ->
# 表示ラベル (Wiki_Output_Design.md §13対応表と同じ8種、順序も揃える)。
_CANDIDATE_COUNT_LABELS: tuple[tuple[str, str], ...] = (
    ("characters", "Characters"),
    ("locations", "Locations"),
    ("organizations", "Organizations"),
    ("items", "Items"),
    ("lore", "Lore"),
    ("events", "Events"),
    ("relationships", "Relationships"),
    ("timelineCandidates", "Timeline"),
)


def _render_candidate_counts_section(source_document: dict[str, Any]) -> list[str]:
    candidate_counts = source_document.get("candidateCounts") or {}
    lines = ["## Candidate Counts", "", "| Type | Count |", "|---|---:|"]
    for key, label in _CANDIDATE_COUNT_LABELS:
        lines.append(f"| {label} | {candidate_counts.get(key, 0)} |")
    lines.append("")
    return lines


def _character_relates_to_episode(entity: dict[str, Any], episode_id: str) -> bool:
    """このcharacter entityが指定episodeIdに関係するかを判定する。

    evidenceRefs.episodeId / sourceCandidates.episodeId /
    extractionRunRefsのキーのいずれかにepisodeIdが現れれば関係ありと
    みなす (Wiki_Output_Design.md §13、Episode page拡張時のrelated
    entity summary方針)。
    """
    for ref in entity.get("evidenceRefs") or []:
        if ref.get("episodeId") == episode_id:
            return True
    for candidate in entity.get("sourceCandidates") or []:
        if candidate.get("episodeId") == episode_id:
            return True
    return episode_id in (entity.get("extractionRunRefs") or {})


def _find_related_characters(
    collection: dict[str, Any], episode_id: str
) -> list[dict[str, Any]]:
    characters = collection.get("entities", {}).get("characters", []) or []
    return [c for c in characters if _character_relates_to_episode(c, episode_id)]


def _format_related_character(entity: dict[str, Any]) -> str:
    """関連キャラクター1件をsummary形式で整形する。

    canonicalIdが確定しページが生成されるentityはcanonicalIdを、
    Character pageへの相対リンク（`stories/{episodeId}.md`からの相対パス、
    MkDocsでのプレビュー時にクリックできるようにするため）とともに表示する。
    unresolvedのentityは内部id（`unresolved`と明記）を表示し、
    通常Character pageが無いためリンクは張らない。
    """
    display_name = entity.get("displayName") or entity.get("id", "")
    if is_page_eligible(entity):
        canonical_id = entity.get("canonicalId")
        relative_path = f"../{character_page_path(entity)}"
        return f"{display_name}（[`{canonical_id}`]({relative_path})）"
    return f"{display_name}（`{entity.get('id')}`, unresolved）"


def _render_related_characters_section(
    collection: dict[str, Any], episode_id: str
) -> list[str]:
    related = _find_related_characters(collection, episode_id)
    lines = ["## Related Characters", ""]
    if not related:
        lines.append("関連するキャラクターは記録されていません。")
        lines.append("")
        return lines
    for entity in related:
        lines.append(f"- {_format_related_character(entity)}")
    lines.append("")
    return lines


def _find_input_result(
    collection: dict[str, Any], source_document: dict[str, Any]
) -> dict[str, Any] | None:
    """sourceDocumentに対応するreport.inputResultsのエントリを、pathで
    突き合わせて探す (どちらも同じpath文字列を持つ、既存のmerge engine実装
    の出力形式に基づく)。見つからない場合はNoneを返す。
    """
    path = source_document.get("path")
    if not path:
        return None
    for result in collection.get("report", {}).get("inputResults", []) or []:
        if result.get("path") == path:
            return result
    return None


def _render_validation_section(
    collection: dict[str, Any], source_document: dict[str, Any]
) -> list[str]:
    """このepisodeのinputResultが取れる場合のみ、input status/errors件数/
    warnings件数を表示する。取れない場合はセクション自体を省略する
    (report全体を出しすぎない方針、Wiki_Output_Design.md §13)。
    """
    input_result = _find_input_result(collection, source_document)
    if input_result is None:
        return []
    lines = [
        "## Validation",
        "",
        "| 項目 | 値 |",
        "|---|---|",
        f"| Input status | {input_result.get('status', '')} |",
        f"| Errors | {len(input_result.get('errors') or [])} |",
        f"| Warnings | {len(input_result.get('warnings') or [])} |",
        "",
    ]
    return lines


# ローカル絶対パス判定用 (Windowsドライブレター形式 "C:/..." のみ。
# UNC "//host/share" とPOSIX絶対パス "/..." は先頭の"/"で判定する)。
_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:/")


def _sanitize_source_path(path: str | None) -> str:
    """`source_document.path`がローカル絶対パスの場合、ファイル名のみへ
    縮約して表示する。

    実データローカルdry-run時、`sourceDocuments[].path`にはExtractor/Merger
    実行時のローカル絶対パス（環境依存、`C:\\Users\\...`等）がそのまま
    入ることがある。Wiki Markdownへ環境依存の絶対パスを晒さないための
    安全策（`docs/runbooks/MkDocs_Local_Preview_Dry_Run.md` source text
    exposure check参照）。相対パスはそのまま表示する。
    """
    if not path:
        return ""
    normalized = path.replace("\\", "/")
    is_absolute = bool(
        _WINDOWS_DRIVE_PATTERN.match(normalized)
    ) or normalized.startswith("/")
    if not is_absolute:
        return path
    name = normalized.rsplit("/", 1)[-1]
    return f"{name}（ローカル絶対パスのため縮約表示）"


def render_episode_page(
    source_document: dict[str, Any], collection: dict[str, Any]
) -> str:
    """Episode pageを生成する (Wiki_Output_Design.md §9.3)。

    現時点のmerged knowledge collectionにはepisode本文相当の情報が
    無いため、sourceDocumentsエントリ (candidateCounts等) から組み立てる
    簡易ページとする。本文セリフは生成しない。collectionを渡すのは、
    このepisodeに関係するcharacter entity summary・inputResultを
    探すため。
    """
    episode_id = source_document.get("episodeId") or source_document.get("documentId")
    document_id = source_document.get("documentId")
    story_id = source_document.get("storyId")

    front_matter = build_front_matter(
        {
            "title": episode_id,
            "page_type": "episode",
            "episode_id": episode_id,
            "story_id": story_id,
            "document_id": document_id,
            "generated_from": GENERATED_FROM,
        }
    )

    story_title = _format_or_placeholder(source_document.get("storyTitle"))
    episode_subtitle = _format_or_placeholder(source_document.get("episodeSubtitle"))
    display_title = _format_or_placeholder(source_document.get("displayTitle"))
    metadata_status = _format_metadata_status(source_document.get("metadataStatus"))

    # Summary は横長tableではなく箇条書き (definition list風) にする
    # (manual visual review 001での指摘、長いID・path・タイトルが1つの
    # table セルに収まらず横スクロールを招いていたため)。人間が見て
    # 重要な項目 (ID/タイトル系) を先に、内部provenance情報
    # (Document ID/Source Path/Extraction Version/Category) を後に置く。
    summary_items = [
        ("Episode ID", _format_code(episode_id)),
        ("Story ID", _format_code(story_id)),
        ("Display Title", display_title),
        ("Story Title", story_title),
        ("Episode Subtitle", episode_subtitle),
        ("Metadata Status", metadata_status),
        ("Document ID", _format_code(document_id)),
        (
            "Source Path",
            _format_code(_sanitize_source_path(source_document.get("path"))),
        ),
        ("Extraction Version", source_document.get("extractionVersion") or "未登録"),
        ("Category", source_document.get("storyCategory") or "未登録"),
    ]

    lines = [front_matter, f"# {episode_id}", "", "## Summary", ""]
    lines.extend(_render_key_value_list(summary_items))

    lines.extend(_render_candidate_counts_section(source_document))
    if episode_id:
        lines.extend(_render_related_characters_section(collection, episode_id))
    lines.extend(_render_validation_section(collection, source_document))

    lines.append(
        "本文セリフはこのページに掲載しません (Wiki_Output_Design.md §4、§9.3)。"
    )
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_pages(
    collection: dict[str, Any],
    character_profiles: CharacterProfileIndex | None = None,
) -> dict[str, str]:
    """merged knowledge collectionから、生成するページ全体を組み立てる。

    戻り値は {相対パス (posix区切り): Markdown文字列}。ファイルへの
    書き出しは行わない (呼び出し側がwrite_pagesを使う)。

    `character_profiles`は`characterId -> CharacterProfile`の索引
    (省略時は全Character pageの「基本プロフィール」sectionが
    「プロフィール未登録」表示になる)。
    """
    characters = collection.get("entities", {}).get("characters", []) or []
    pages: dict[str, str] = {
        "index.md": render_index_page(collection),
        "stories/index.md": render_story_index_page(collection),
        "characters/index.md": render_character_index_page(
            characters, character_profiles
        ),
        "reports/unresolved.md": render_unresolved_report(collection),
    }

    for source_document in collection.get("sourceDocuments", []) or []:
        path = episode_page_path(source_document)
        if path is not None:
            pages[path] = render_episode_page(source_document, collection)

    for entity in characters:
        path = character_page_path(entity)
        if path is not None:
            pages[path] = render_character_page(entity, character_profiles)

    return pages


def write_pages(
    pages: dict[str, str], output_dir: str | Path, clean: bool = False
) -> list[Path]:
    """build_pagesが返したページ群を、output_dir配下へ実際に書き出す。

    実データ由来のWiki生成物をcommitしないルールは呼び出し側
    (scripts/render_wiki.py) の責任とする。ここではファイル書き出しのみ
    行う (docs/runbooks/Real_Data_Dry_Run.md §14と同様、出力先の掃除は
    呼び出し側の判断)。
    """
    output_path = Path(output_dir)
    if clean and output_path.exists():
        shutil.rmtree(output_path)

    written: list[Path] = []
    for relative_path, content in pages.items():
        full_path = output_path / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        written.append(full_path)
    return written
