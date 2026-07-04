"""
DKB Wiki Generator - Path / URL helpers
Wiki出力のURL・slug方針 (docs/architecture/07_Wiki/Wiki_Output_Design.md §14)
を実装する。

**名前ベースslugは使わない。** canonicalIdが確定しているentityのみ
個別ページのパスを持つ。canonicalId未確定 (status: unresolved/conflict/
deprecated、またはcanonicalId自体が無い) entityは個別ページを生成せず、
reports/unresolved.mdへ集約する (Wiki_Output_Design.md §5)。
"""

from __future__ import annotations

from typing import Any

# このentityが個別ページを生成してよい (= canonicalIdが確定し、
# status: mergedである) かどうかの判定。Phase 1スケルトンでは
# Character pageのみ実装するが、この判定自体は全entity種別で共通に
# 使える (Wiki_Output_Design.md §5の表と同じ条件)。
STATUS_MERGED = "merged"


def is_page_eligible(entity: dict[str, Any]) -> bool:
    """個別ページを生成してよいentityかどうかを判定する。

    条件: canonicalIdが設定されており、かつstatusがmergedであること。
    どちらか一方でも欠ける場合は、reports/unresolved.mdへの集約対象とする
    (Wiki_Output_Design.md §5)。
    """
    return bool(entity.get("canonicalId")) and entity.get("status") == STATUS_MERGED


def character_page_path(entity: dict[str, Any]) -> str | None:
    """Character pageの出力先相対パスを返す。個別ページを生成すべきで
    なければNoneを返す (呼び出し側はNoneならunresolved reportへ回す)。
    """
    if not is_page_eligible(entity):
        return None
    return f"characters/{entity['canonicalId']}.md"


def episode_page_path(source_document: dict[str, Any]) -> str | None:
    """Episode pageの出力先相対パスを返す。episodeId/documentIdが
    どちらも無ければNoneを返す。

    Wiki_Output_Design.md §14はstories/{storyId}/{episodeId}.mdという
    ネスト構成を示しているが、このPR (wiki renderer skeleton) では
    scriptで指示された簡易フラット構成 stories/{episodeId}.md を採用する
    (将来のepisode page renderer拡張PRでネスト構成へ移行してよい)。
    """
    episode_id = source_document.get("episodeId") or source_document.get("documentId")
    if not episode_id:
        return None
    return f"stories/{episode_id}.md"
