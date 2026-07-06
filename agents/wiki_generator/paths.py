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


def resolve_episode_path_id(source_document: dict[str, Any]) -> str | None:
    """Episode pageのURL/filenameに使うIDを解決する。

    `publicEpisodeId`が設定されていればそれを優先し (公開Wiki URL用の
    安定ID、Story_ID_Policy_Decision.md §7)、無い場合・空文字列・
    whitespaceのみの場合は既存の`episodeId`（無ければ`documentId`）へ
    fallbackする。既存manifest（public IDフィールドを含まない）を使う
    場合の出力は従来と完全に同じになる。
    """
    public_episode_id = source_document.get("publicEpisodeId")
    if isinstance(public_episode_id, str) and public_episode_id.strip():
        return public_episode_id.strip()
    return source_document.get("episodeId") or source_document.get("documentId")


def resolve_story_path_id(story_id: str, public_story_id: str | None = None) -> str:
    """Story pageのURL/filenameに使うIDを解決する。

    `publicStoryId`が設定されていればそれを優先し (公開Wiki URL用の
    安定ID、Story_ID_Policy_Decision.md §7)、無い場合・空文字列・
    whitespaceのみの場合は既存の`storyId`へfallbackする
    (`resolve_episode_path_id`と同じ方針、feature/wiki-story-page-renderer)。
    """
    if isinstance(public_story_id, str) and public_story_id.strip():
        return public_story_id.strip()
    return story_id


def story_page_path(story_id: str, public_story_id: str | None = None) -> str:
    """Story pageの出力先相対パスを返す。

    短期方針はflat構造維持 (`Story_Page_Design.md` §10 候補A)。
    `stories/{storyId}/index.md`のようなnested構成へはまだ移行しない。
    Episode pageと同じ`stories/`ディレクトリに置くが、`episodeId`は常に
    `storyId`+`_E{number}`形式のためファイル名は衝突しない。
    """
    return f"stories/{resolve_story_path_id(story_id, public_story_id)}.md"


def episode_page_path(source_document: dict[str, Any]) -> str | None:
    """Episode pageの出力先相対パスを返す。`resolve_episode_path_id`が
    Noneを返す場合 (publicEpisodeId/episodeId/documentIdがいずれも無い)
    はNoneを返す。

    Wiki_Output_Design.md §14はstories/{storyId}/{episodeId}.mdという
    ネスト構成を示しているが、このPR (wiki renderer skeleton) では
    scriptで指示された簡易フラット構成 stories/{episodeId}.md を採用する
    (将来のepisode page renderer拡張PRでネスト構成へ移行してよい)。

    `publicEpisodeId`が設定されている場合は`stories/{publicEpisodeId}.md`
    を返す (feature/story-manifest-public-id-renderer-switch)。
    """
    episode_path_id = resolve_episode_path_id(source_document)
    if not episode_path_id:
        return None
    return f"stories/{episode_path_id}.md"
