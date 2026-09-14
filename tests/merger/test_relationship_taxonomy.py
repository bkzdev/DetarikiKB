"""
tests/merger/test_relationship_taxonomy.py
agents/merger/relationship_taxonomy.py (normalize_relationship_type) の
単体テスト。

relationshipTypeの表記ゆれ (大文字小文字・区切り文字) が安全に正規化され、
意味aliasは提案だけに留まること、未知の値がエラーにならず
安全なslugとして保持されること (isKnown: False) を重点的に確認する。
"""

from agents.merger.relationship_taxonomy import (
    FORMAL_V1_RELATIONSHIP_TYPES,
    KNOWN_RELATIONSHIP_TYPES,
    PROVISIONAL_RELATIONSHIP_TYPES,
    REVIEW_REQUIRED_ALIASES,
    normalize_relationship_type,
)

# ----------------------------------------------------------------
# 1. 既知typeの大文字小文字・区切り文字違いの正規化
# ----------------------------------------------------------------


def test_uppercase_underscore_normalizes_to_known_type():
    result = normalize_relationship_type("MEMBER_OF")
    assert result.normalized_value == "member_of"
    assert result.is_known is True
    assert result.original_value == "MEMBER_OF"
    assert result.warnings == []


def test_hyphenated_variant_normalizes_to_known_type():
    result = normalize_relationship_type("member-of")
    assert result.normalized_value == "member_of"
    assert result.is_known is True


def test_space_separated_variant_normalizes_to_known_type():
    result = normalize_relationship_type("member of")
    assert result.normalized_value == "member_of"
    assert result.is_known is True


def test_affiliated_with_normalizes():
    result = normalize_relationship_type("AFFILIATED_WITH")
    assert result.normalized_value == "affiliated_with"
    assert result.is_known is True


def test_related_to_normalizes():
    result = normalize_relationship_type("RELATED_TO")
    assert result.normalized_value == "related_to"
    assert result.is_known is True
    assert result.taxonomy_state == "provisional"


def test_already_lowercase_canonical_value_is_unchanged():
    result = normalize_relationship_type("member_of")
    assert result.normalized_value == "member_of"
    assert result.is_known is True


# ----------------------------------------------------------------
# 2. 意味aliasは自動変換せずreview提案に留める
# ----------------------------------------------------------------


def test_semantic_alias_is_not_automatically_normalized():
    result = normalize_relationship_type("belongs_to")
    assert result.normalized_value == "belongs_to"
    assert result.is_known is False
    assert result.taxonomy_state == "unrecognized"
    assert result.suggested_type == "member_of"
    assert any("自動変換せず" in warning for warning in result.warnings)


def test_all_review_required_aliases_point_to_known_type():
    for alias, canonical in REVIEW_REQUIRED_ALIASES.items():
        assert canonical in KNOWN_RELATIONSHIP_TYPES, (alias, canonical)


# ----------------------------------------------------------------
# 3. 未知typeは破棄されず、安全なslugとして保持される
# ----------------------------------------------------------------


def test_unknown_type_is_slugified_and_marked_not_known():
    result = normalize_relationship_type("rival-ish")
    assert result.normalized_value == "rival_ish"
    assert result.is_known is False
    assert result.original_value == "rival-ish"
    assert result.warnings != []


def test_unknown_type_warning_mentions_original_value():
    result = normalize_relationship_type("SOME_NOT_YET_STANDARDIZED_RELATION")
    assert any("SOME_NOT_YET_STANDARDIZED_RELATION" in w for w in result.warnings)


def test_unknown_type_is_never_discarded():
    result = normalize_relationship_type("TRUSTS")
    assert result.normalized_value  # 空文字列にならない (破棄されない)
    assert result.original_value == "TRUSTS"


# ----------------------------------------------------------------
# 4. taxonomy定義そのもの
# ----------------------------------------------------------------


def test_known_relationship_types_are_all_lowercase_snake_case():
    for value in KNOWN_RELATIONSHIP_TYPES:
        assert value == value.lower()
        assert " " not in value
        assert "-" not in value


def test_taxonomy_states_are_disjoint_and_cover_known_types():
    assert FORMAL_V1_RELATIONSHIP_TYPES.isdisjoint(PROVISIONAL_RELATIONSHIP_TYPES)
    assert (
        FORMAL_V1_RELATIONSHIP_TYPES | PROVISIONAL_RELATIONSHIP_TYPES
        == KNOWN_RELATIONSHIP_TYPES
    )
