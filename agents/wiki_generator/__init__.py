"""
DKB Wiki Generator Package

merged knowledge collection (schemas/merged_knowledge_collection.schema.json)
からWiki Markdownを生成する。

docs/architecture/07_Wiki/Wiki_Output_Design.md のPhase 1のうち、
Top page / Story index / Episode page (簡易) / Character page /
Unresolved report pageのみを実装するrenderer skeleton
(feature/wiki-renderer-skeleton)。Location/Organization/Item/Lore/Event
page、Relationship section、Timeline page、AI analysis pageは未実装。
テンプレートエンジン (Jinja2等) の依存追加はまだ行っていない。

Usage:
    from agents.wiki_generator import build_pages, write_pages
"""

from .models import build_front_matter
from .paths import (
    character_page_path,
    episode_page_path,
    is_page_eligible,
    story_page_path,
)
from .renderer import (
    build_pages,
    render_character_index_page,
    render_character_page,
    render_episode_page,
    render_index_page,
    render_story_index_page,
    render_story_page,
    render_unresolved_report,
    write_pages,
)

__all__ = [
    "build_front_matter",
    "character_page_path",
    "episode_page_path",
    "is_page_eligible",
    "story_page_path",
    "build_pages",
    "render_character_index_page",
    "render_character_page",
    "render_episode_page",
    "render_index_page",
    "render_story_index_page",
    "render_story_page",
    "render_unresolved_report",
    "write_pages",
]
