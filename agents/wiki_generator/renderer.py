"""
DKB Wiki Generator - Renderer skeleton
merged knowledge collection (schemas/merged_knowledge_collection.schema.json)
から、最小限のWiki Markdownを生成する。

docs/architecture/07_Wiki/Wiki_Output_Design.md のPhase 1のうち、
Top page / Story index / Episode page (簡易) / Character page /
Unresolved report page のみを実装する (Location/Organization/Item/Lore/
Event page、Relationship section、Timeline page、AI analysis pageは
Non-goals。将来のPRで拡張する)。

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

import shutil
from pathlib import Path
from typing import Any

from .models import (
    ENTITY_KEY_TO_TYPE,
    GENERATED_FROM,
    MERGED_ENTITY_KEYS,
    build_front_matter,
)
from .paths import character_page_path, episode_page_path, is_page_eligible


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
        lines.append(f"- {conflict_type}（severity: {severity}, {resolution}）")
    lines.append("")
    return lines


def render_character_page(entity: dict[str, Any]) -> str:
    """Character pageを生成する (Wiki_Output_Design.md §9.4)。

    呼び出し側は`is_page_eligible(entity)`がTrueの場合のみこの関数を
    呼ぶこと (canonicalId未確定のentityを渡さない)。
    """
    display_name = entity.get("displayName") or entity.get("id", "")
    front_matter = build_front_matter(
        {
            "title": display_name,
            "entity_type": "character",
            "entity_id": entity.get("id"),
            "canonical_id": entity.get("canonicalId"),
            "status": entity.get("status"),
            "generated_from": GENERATED_FROM,
        }
    )

    lines = [front_matter, f"# {display_name}", ""]

    aliases = entity.get("aliases") or []
    lines.append("## 抽出情報")
    lines.append("")
    lines.append("| 項目 | 値 |")
    lines.append("|---|---|")
    lines.append(f"| 表示名 | {display_name} |")
    lines.append(f"| 別名 | {', '.join(aliases) if aliases else '(なし)'} |")
    lines.append(f"| ステータス | {entity.get('status', '')} |")
    lines.append(f"| 情報源区分 | {', '.join(entity.get('sourceTypes') or [])} |")
    lines.append(f"| 確度 (confidence) | {entity.get('confidence', '')} |")
    lines.append(f"| 由来candidate数 | {len(entity.get('sourceCandidates') or [])} |")
    lines.append("")

    lines.extend(_render_evidence_section(entity))
    lines.extend(_render_conflicts_section(entity))

    return "\n".join(lines).rstrip() + "\n"


def render_unresolved_report(collection: dict[str, Any]) -> str:
    """Unresolved report page (reports/unresolved.md) を生成する
    (Wiki_Output_Design.md §9.12)。

    canonicalId未確定、またはstatusがmerged以外の全entity種別
    (character/location/organization/item/lore/event/relationship/
    timeline) を対象とする。件数が0の種別はセクションごと省略する。
    """
    entities = collection.get("entities", {}) or {}
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
        lines.append("| entity id | displayName | status | reason | evidence件数 |")
        lines.append("|---|---|---|---|---|")
        for e in unresolved:
            reason = (
                "canonicalId未確定"
                if not e.get("canonicalId")
                else f"status: {e.get('status')}"
            )
            lines.append(
                f"| {e.get('id', '?')} "
                f"| {e.get('displayName') or '(不明)'} "
                f"| {e.get('status', '')} "
                f"| {reason} "
                f"| {len(e.get('evidenceRefs') or [])} |"
            )
        lines.append("")

    if total_unresolved == 0:
        lines.append("未解決のentityはありません。")
        lines.append("")

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

    lines.append("| storyId | episodeId | category |")
    lines.append("|---|---|---|")
    for doc in source_documents:
        episode_path = episode_page_path(doc)
        episode_id = doc.get("episodeId") or doc.get("documentId") or "?"
        episode_link = f"[{episode_id}]({episode_path})" if episode_path else episode_id
        lines.append(
            f"| {doc.get('storyId', '?')} "
            f"| {episode_link} "
            f"| {doc.get('storyCategory', '')} |"
        )
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_episode_page(source_document: dict[str, Any]) -> str:
    """Episode pageを生成する (Wiki_Output_Design.md §9.3)。

    現時点のmerged knowledge collectionにはepisode本文相当の情報が
    無いため、sourceDocumentsエントリ (candidateCounts等) から組み立てる
    簡易ページとする。本文セリフは生成しない。
    """
    episode_id = source_document.get("episodeId") or source_document.get("documentId")
    front_matter = build_front_matter(
        {
            "title": episode_id,
            "entity_type": "episode",
            "entity_id": episode_id,
            "generated_from": GENERATED_FROM,
        }
    )
    candidate_counts = source_document.get("candidateCounts", {}) or {}

    lines = [
        front_matter,
        f"# {episode_id}",
        "",
        "## 基本情報",
        "",
        "| 項目 | 値 |",
        "|---|---|",
        f"| Episode ID | {episode_id} |",
        f"| Story ID | {source_document.get('storyId', '')} |",
        f"| カテゴリ | {source_document.get('storyCategory', '')} |",
        "",
        "## Candidate件数",
        "",
        "| 種別 | 件数 |",
        "|---|---|",
    ]
    for key, count in candidate_counts.items():
        lines.append(f"| {key} | {count} |")
    lines.append("")
    lines.append(
        "本文セリフはこのページに掲載しません (Wiki_Output_Design.md §4、§9.3)。"
    )
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_pages(collection: dict[str, Any]) -> dict[str, str]:
    """merged knowledge collectionから、生成するページ全体を組み立てる。

    戻り値は {相対パス (posix区切り): Markdown文字列}。ファイルへの
    書き出しは行わない (呼び出し側がwrite_pagesを使う)。
    """
    pages: dict[str, str] = {
        "index.md": render_index_page(collection),
        "stories/index.md": render_story_index_page(collection),
        "reports/unresolved.md": render_unresolved_report(collection),
    }

    for source_document in collection.get("sourceDocuments", []) or []:
        path = episode_page_path(source_document)
        if path is not None:
            pages[path] = render_episode_page(source_document)

    for entity in collection.get("entities", {}).get("characters", []) or []:
        path = character_page_path(entity)
        if path is not None:
            pages[path] = render_character_page(entity)

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
