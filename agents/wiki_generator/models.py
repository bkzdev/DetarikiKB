"""
DKB Wiki Generator - Models / front matter helpers
merged knowledge collection (schemas/merged_knowledge_collection.schema.json)
から生成するMarkdownページの、front matter組み立てとentity種別定数を
まとめる。

docs/architecture/07_Wiki/Wiki_Output_Design.md §10 (front matter方針)
"""

from __future__ import annotations

from typing import Any

# merged knowledge collection の entities 配下キー
# (agents/merger/models.py MERGED_ENTITY_KEYSと同一。Parser層からの
# 独立性を保つため、Wiki生成側でも同じ定数を独立して定義する)。
MERGED_ENTITY_KEYS = (
    "characters",
    "locations",
    "organizations",
    "items",
    "lore",
    "events",
    "relationships",
    "timeline",
)

# entity type (singular) と entities配下キー (plural) の対応
# (front matterのentity_type用)。
ENTITY_KEY_TO_TYPE: dict[str, str] = {
    "characters": "character",
    "locations": "location",
    "organizations": "organization",
    "items": "item",
    "lore": "lore",
    "events": "event",
    "relationships": "relationship",
    "timeline": "timeline_entry",
}

GENERATED_FROM = "merged_knowledge_collection"

# front matterに出力する順序 (Wiki_Output_Design.md §10の例と同じ並び)。
_FRONT_MATTER_KEY_ORDER = (
    "title",
    "entity_type",
    "entity_id",
    "canonical_id",
    "status",
    "generated_from",
)


def _escape_yaml_double_quoted(value: str) -> str:
    """YAMLのダブルクォート文字列として安全にエスケープする。

    displayName等は通常の日本語・英語の人名・用語のみを想定するため、
    バックスラッシュ・ダブルクォートの最小限エスケープのみ行う
    (scripts/compare_character_dictionaries.pyの_quoted_yaml_stringと
    同じ方針)。
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_front_matter(fields: dict[str, Any]) -> str:
    """Markdown front matter (YAML) を組み立てる。

    Noneの値は出力しない (front matterに任意フィールドとして省略する)。
    `title`と`generated_from`は常に含める前提 (呼び出し側が渡すこと)。
    """
    lines = ["---"]
    for key in _FRONT_MATTER_KEY_ORDER:
        if key not in fields:
            continue
        value = fields[key]
        if value is None:
            continue
        lines.append(f"{key}: {_escape_yaml_double_quoted(str(value))}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)
