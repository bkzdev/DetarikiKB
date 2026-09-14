"""
DKB Merger - Relationship Type Taxonomy
RelationshipCandidate/merged relationshipの`relationshipType`表記ゆれを
安全に扱うための、公開v1 taxonomyと正規化レイヤー。

relationshipTypeは後方互換のため自由文字列を維持し、未知の値も破棄しない。
公開v1として確定した型、将来検討用の暫定型、未登録型を区別する。自動正規化は
大文字小文字・区切り文字の差だけに限定し、意味を変える同義語変換は行わない。

自然文からの関係推定・LLMによる分類はここでは一切行わない
(大文字小文字/区切り文字の正規化と、review用の同義語提案テーブルのみ)。

docs/architecture/06_AI/Merged_Knowledge_Design.md §6.3
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# 公開v1で意味・endpoint・方向を確定した型。
FORMAL_V1_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {"member_of", "affiliated_with"}
)

# 語彙候補として保持するが、公開関係には使わない暫定型。
PROVISIONAL_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {
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

KNOWN_RELATIONSHIP_TYPES = FORMAL_V1_RELATIONSHIP_TYPES | PROVISIONAL_RELATIONSHIP_TYPES

# 意味上の同義語候補。自動mergeには使わずreview時の提案だけに使う。
REVIEW_REQUIRED_ALIASES: dict[str, str] = {
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

TAXONOMY_FORMAL_V1 = "formal_v1"
TAXONOMY_PROVISIONAL = "provisional"
TAXONOMY_UNRECOGNIZED = "unrecognized"


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
    taxonomy_state: str
    suggested_type: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "originalValue": self.original_value,
            "normalizedValue": self.normalized_value,
            "isKnown": self.is_known,
            "taxonomyState": self.taxonomy_state,
            "suggestedType": self.suggested_type,
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
            taxonomy_state=TAXONOMY_UNRECOGNIZED,
            warnings=["relationshipTypeが空です"],
        )

    slug = _slugify(stripped) or "unknown"
    normalized = slug
    is_known = normalized in KNOWN_RELATIONSHIP_TYPES
    if normalized in FORMAL_V1_RELATIONSHIP_TYPES:
        taxonomy_state = TAXONOMY_FORMAL_V1
    elif normalized in PROVISIONAL_RELATIONSHIP_TYPES:
        taxonomy_state = TAXONOMY_PROVISIONAL
    else:
        taxonomy_state = TAXONOMY_UNRECOGNIZED
    suggested_type = REVIEW_REQUIRED_ALIASES.get(normalized)

    warnings: list[str] = []
    if not is_known:
        warnings.append(
            f"未知のrelationshipType '{value}' はtaxonomy未登録のため "
            f"'{normalized}' として保持しました (破棄はしていません)"
        )
    if suggested_type is not None:
        warnings.append(
            f"'{value}' は '{suggested_type}' の同義語候補ですが、自動変換せず"
            "review対象として保持しました"
        )

    return NormalizedRelationshipType(
        original_value=value,
        normalized_value=normalized,
        is_known=is_known,
        taxonomy_state=taxonomy_state,
        suggested_type=suggested_type,
        warnings=warnings,
    )
