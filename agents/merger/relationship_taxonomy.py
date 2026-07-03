"""
DKB Merger - Relationship Type Taxonomy
RelationshipCandidate/merged relationshipの`relationshipType`表記ゆれを
安全に扱うための、暫定taxonomyと正規化レイヤー。

taxonomyはまだ確定していない (docs/architecture/04_Knowledge_Graph/
Relationships.md 未確定、Merged_Knowledge_Design.md §6.3)。そのため
relationshipTypeをenumで強制せず、未知の値も破棄せず保持する。既知の
表記ゆれ（大文字小文字・区切り文字違い、代表的な同義語）だけを
canonical typeへ正規化する。

自然文からの関係推定・LLMによる分類はここでは一切行わない
(大文字小文字/区切り文字の正規化と、既知の同義語テーブルのみ)。

docs/architecture/06_AI/Merged_Knowledge_Design.md §6.3
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# 暫定taxonomy (Merged_Knowledge_Design.md §6.3の暫定語彙 MEMBER_OF/
# AFFILIATED_WITH/RELATED_TO/APPEARS_WITHを含む拡張版)。正規化後の値は
# すべてこのsnake_case形式に揃える。taxonomy確定はここでは行わない
# (docs/architecture/04_Knowledge_Graph/Relationships.md確定後に見直す)。
KNOWN_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {
        "member_of",
        "affiliated_with",
        "ally_of",
        "enemy_of",
        "family_of",
        "friend_of",
        "mentor_of",
        "subordinate_of",
        "superior_of",
        "appears_with",
        "related_to",
        "located_in",
        "owns",
        "uses",
        "knows",
        "unknown",
    }
)

# 既知の同義語 -> canonical typeの対応表。大文字小文字・区切り文字違いは
# _slugifyだけで吸収できるため、ここに載せるのは表記ゆれではなく別の語彙
# (例: "belongs_to" -> "member_of") のみ。方向が入れ替わる可能性のある
# 同義語 (owned_by等) は誤変換の元になるため意図的に含めない。
ALIASES: dict[str, str] = {
    "belongs_to": "member_of",
    "part_of": "member_of",
    "affiliate_of": "affiliated_with",
    "affiliation": "affiliated_with",
    "allied_with": "ally_of",
    "ally": "ally_of",
    "hostile_to": "enemy_of",
    "rival_of": "enemy_of",
    "friend": "friend_of",
    "mentor": "mentor_of",
    "subordinate": "subordinate_of",
    "superior": "superior_of",
    "seen_with": "appears_with",
    "connected_to": "related_to",
    "located_at": "located_in",
}


def _slugify(value: str) -> str:
    """大文字小文字・区切り文字 (アンダースコア/ハイフン/空白等) の違いを
    吸収し、snake_caseのslugへ変換する。値そのものの意味は変えない
    (agents/merger/entity_base.pyのsanitize_id_segmentと同種の正規化だが、
    ID用の大文字化ではなくtaxonomy比較用の小文字化を行う)。
    """
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", value).strip("_").lower()
    return slug


@dataclass
class NormalizedRelationshipType:
    """relationshipType 1件の正規化結果。"""

    original_value: str
    normalized_value: str
    is_known: bool
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "originalValue": self.original_value,
            "normalizedValue": self.normalized_value,
            "isKnown": self.is_known,
            "warnings": list(self.warnings),
        }


def normalize_relationship_type(value: str) -> NormalizedRelationshipType:
    """relationshipTypeの表記ゆれを正規化する。

    未知の値をエラーにはせず、安全にslug化した値をnormalizedValueとして
    保持する (isKnown: False、warningsにその旨を記録)。元の値
    (originalValue) は失わない。

    呼び出し側 (agents/merger/relationship.py) は、この関数の戻り値の
    normalizedValueをmerge keyに使うが、entity.relationshipType自体は
    元の値をそのまま保持する (Merged_Knowledge_Design.md §6.3: taxonomy
    確定前に自由文字列を書き換えない、既存挙動を壊さないため)。
    """
    stripped = (value or "").strip()
    if not stripped:
        return NormalizedRelationshipType(
            original_value=value,
            normalized_value="",
            is_known=False,
            warnings=["relationshipTypeが空です"],
        )

    slug = _slugify(stripped) or "unknown"
    canonical = ALIASES.get(slug, slug)
    is_known = canonical in KNOWN_RELATIONSHIP_TYPES

    warnings: list[str] = []
    if not is_known:
        warnings.append(
            f"未知のrelationshipType '{value}' はtaxonomy未登録のため "
            f"'{canonical}' として保持しました (破棄はしていません)"
        )

    return NormalizedRelationshipType(
        original_value=value,
        normalized_value=canonical,
        is_known=is_known,
        warnings=warnings,
    )
