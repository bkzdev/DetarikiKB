"""
DKB Wiki Generator Package

merged knowledge collection (schemas/merged_knowledge_collection.schema.json)
からWiki Markdownを生成する。

docs/architecture/07_Wiki/Wiki_Output_Design.md のPhase 1のうち、
Top page / Story index / Episode page (簡易) / Character page / Location page /
Item page / Lore page / Event page / Unresolved report pageを実装するrenderer。
Organization page、Relationship section、Timeline page、
AI analysis pageは未実装。
テンプレートエンジン (Jinja2等) の依存追加はまだ行っていない。

Usage:
    from agents.wiki_generator import build_pages, write_pages
"""

from .canonical_timeline import (
    render_canonical_timeline_page,
    validate_canonical_timeline_page_links,
)
from .models import build_front_matter
from .paths import (
    canonical_timeline_page_path,
    character_page_path,
    episode_page_path,
    event_page_path,
    evidence_page_path,
    is_page_eligible,
    item_page_path,
    location_page_path,
    lore_page_path,
    story_page_path,
)
from .renderer import (
    build_pages,
    render_character_index_page,
    render_character_page,
    render_episode_page,
    render_event_index_page,
    render_event_page,
    render_evidence_page,
    render_index_page,
    render_item_index_page,
    render_item_page,
    render_location_index_page,
    render_location_page,
    render_lore_index_page,
    render_lore_page,
    render_story_index_page,
    render_story_page,
    render_unresolved_report,
    write_pages,
)

__all__ = [
    "build_front_matter",
    "canonical_timeline_page_path",
    "character_page_path",
    "episode_page_path",
    "event_page_path",
    "evidence_page_path",
    "is_page_eligible",
    "item_page_path",
    "location_page_path",
    "lore_page_path",
    "story_page_path",
    "build_pages",
    "render_character_index_page",
    "render_canonical_timeline_page",
    "render_character_page",
    "render_episode_page",
    "render_event_index_page",
    "render_event_page",
    "render_evidence_page",
    "render_index_page",
    "render_item_index_page",
    "render_item_page",
    "render_location_index_page",
    "render_location_page",
    "render_lore_index_page",
    "render_lore_page",
    "render_story_index_page",
    "render_story_page",
    "render_unresolved_report",
    "write_pages",
    "validate_canonical_timeline_page_links",
]
