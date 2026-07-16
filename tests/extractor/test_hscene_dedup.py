"""
tests/extractor/test_hscene_dedup.py
agents/extractor/hscene_dedup.py (Character_Story_ID_Manifest_Design.md
§6.3・§9 PR E) の合成fixtureテスト。

CHAR_HS本体episode・例外変種episode間 (および例外変種同士) の重複ブロックが
アセットpath同一性で抽出段階から除外マークされること、Normalized Story JSON
自体は変更されないこと (フィクスチャのstory_json辞書がテスト前後で不変)、
除外件数・重複先episodeIdがepisode_extraction出力へ記録されること、トレース
の無い通常episode・本体不在ケースが完全無回帰であることを検証する。

実データは使わず、StoryParser().parse_text() + Normalizer().normalize() で
インラインスクリプトから生成した合成Normalized Story JSONのみを使う
(tests/extractor/test_extractor_skeleton.py と同じ方式)。
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator

from agents.extractor import Extractor, extract_stories_with_hscene_dedup
from agents.parser.normalizer import Normalizer
from agents.parser.parser import StoryParser

PROJECT_ROOT = Path(__file__).parent.parent.parent
EXTRACTION_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "extraction.schema.json"


def _build_story_json(
    script: str,
    story_id: str,
    episode_id: str,
    category: str = "CHAR_HS",
    variant_trace: dict | None = None,
) -> dict[str, Any]:
    parser = StoryParser()
    parse_result = parser.parse_text(script, source_file="test_hscene_dedup")
    normalizer = Normalizer(
        story_id=story_id,
        story_category=category,
        episode_id=episode_id,
        source_file="test_hscene_dedup",
        variant_trace=variant_trace,
    )
    return normalizer.normalize(parse_result)


def _blocks(story_json: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        block
        for episode in story_json["episodes"]
        for scene in episode["scenes"]
        for block in scene["blocks"]
    ]


def _block_id_by_text(story_json: dict[str, Any], text: str) -> str:
    for block in _blocks(story_json):
        if block.get("text") == text:
            return block["id"]
    raise AssertionError(f"text={text!r} を持つBlockが見つかりません")


def _extraction_for(
    extractions: list[dict[str, Any]], episode_id: str
) -> dict[str, Any]:
    for extraction in extractions:
        if extraction["episodeId"] == episode_id:
            return extraction
    raise AssertionError(f"episodeId={episode_id!r} の抽出結果が見つかりません")


@pytest.fixture
def extraction_validator() -> Draft7Validator:
    with open(EXTRACTION_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    return Draft7Validator(schema)


# ----------------------------------------------------------------
# reverse_superset相当 (変種が本体を完全に包含した上で新規内容を追加)
# ----------------------------------------------------------------

BASE_STORY_ID = "CHAR_HS_TESTCHAR"
BODY_EPISODE_ID = "CHAR_HS_TESTCHAR_E06"
VARIANT_SUPERSET_EPISODE_ID = "CHAR_HS_TESTCHAR_E06_VN"

BODY_SCRIPT = """@ChTalk 0 voice/body/a.ogg
たいせつな夜ですね
msg
@ChTalk 0 voice/body/b.ogg
おやすみなさい
msg
"""

VARIANT_SUPERSET_SCRIPT = """@ChTalk 0 voice/body/a.ogg
たいせつな夜ですね
msg
@ChTalk 0 voice/body/b.ogg
おやすみなさい
msg
@ChTalk 0 voice/variant/c.ogg
あたらしい台詞です
msg
"""


@pytest.fixture
def body_story_json() -> dict[str, Any]:
    return _build_story_json(BODY_SCRIPT, BASE_STORY_ID, BODY_EPISODE_ID)


@pytest.fixture
def variant_superset_story_json() -> dict[str, Any]:
    return _build_story_json(
        VARIANT_SUPERSET_SCRIPT,
        BASE_STORY_ID,
        VARIANT_SUPERSET_EPISODE_ID,
        variant_trace={
            "baseEpisodeId": BODY_EPISODE_ID,
            "variantPattern": "n",
            "dupIndex": None,
            "judgment": "exception",
            "bodyIdentifierCount": 4,
            "variantIdentifierCount": 6,
            "extraInVariantCount": 2,
        },
    )


def test_reverse_superset_variant_dedups_shared_blocks_keeps_new_block(
    body_story_json, variant_superset_story_json
):
    a_id = _block_id_by_text(body_story_json, "たいせつな夜ですね")
    b_id = _block_id_by_text(body_story_json, "おやすみなさい")
    variant_a_id = _block_id_by_text(variant_superset_story_json, "たいせつな夜ですね")
    variant_b_id = _block_id_by_text(variant_superset_story_json, "おやすみなさい")
    c_id = _block_id_by_text(variant_superset_story_json, "あたらしい台詞です")

    extractions = extract_stories_with_hscene_dedup(
        [body_story_json, variant_superset_story_json]
    )

    body_extraction = _extraction_for(extractions, BODY_EPISODE_ID)
    variant_extraction = _extraction_for(extractions, VARIANT_SUPERSET_EPISODE_ID)

    # 本体は常にフル抽出 (2件とも evidenceIndex に残る)
    assert set(body_extraction["evidenceIndex"].keys()) == {a_id, b_id}
    assert body_extraction["hsceneDedup"] == {
        "role": "body",
        "groupBaseEpisodeId": BODY_EPISODE_ID,
        "variantEpisodeIds": [VARIANT_SUPERSET_EPISODE_ID],
    }

    # 変種は本体と重複する2ブロックが除外され、新規ブロックのみ残る
    assert set(variant_extraction["evidenceIndex"].keys()) == {c_id}
    dedup = variant_extraction["hsceneDedup"]
    assert dedup["role"] == "variant"
    assert dedup["groupBaseEpisodeId"] == BODY_EPISODE_ID
    assert dedup["baseEpisodeAvailable"] is True
    assert dedup["excludedBlockCount"] == 2
    assert sorted(dedup["excludedBlockIds"]) == sorted([variant_a_id, variant_b_id])
    assert dedup["dedupedAgainstEpisodeIds"] == [BODY_EPISODE_ID]


def test_dedup_does_not_mutate_normalized_story_json(
    body_story_json, variant_superset_story_json
):
    """不破棄不変則: 入力のNormalized Story JSON辞書は一切変更されない"""
    before_body = copy.deepcopy(body_story_json)
    before_variant = copy.deepcopy(variant_superset_story_json)

    extract_stories_with_hscene_dedup([body_story_json, variant_superset_story_json])

    assert body_story_json == before_body
    assert variant_superset_story_json == before_variant
    # 変種側のブロック数もJSON上は減っていない (除外はextraction出力側のみ)
    assert len(_blocks(variant_superset_story_json)) == 3


def test_dedup_extraction_validates_against_extraction_schema(
    body_story_json, variant_superset_story_json, extraction_validator
):
    extractions = extract_stories_with_hscene_dedup(
        [body_story_json, variant_superset_story_json]
    )
    for extraction in extractions:
        errors = list(extraction_validator.iter_errors(extraction))
        assert not errors, [e.message for e in errors]


# ----------------------------------------------------------------
# partial_overlap相当 (本体・変種の双方が固有内容を持ち、一部だけ共有)
# ----------------------------------------------------------------

PARTIAL_STORY_ID = "CHAR_HS_TESTCHAR2"
PARTIAL_BODY_EPISODE_ID = "CHAR_HS_TESTCHAR2_E10"
PARTIAL_VARIANT_EPISODE_ID = "CHAR_HS_TESTCHAR2_E10_VSP"

PARTIAL_BODY_SCRIPT = """@ChTalk 0 voice/shared/a.ogg
きょうつうシーンです
msg
@ChTalk 0 voice/body_only/d.ogg
ほんたいのみのないよう
msg
"""

PARTIAL_VARIANT_SCRIPT = """@ChTalk 0 voice/shared/a.ogg
きょうつうシーンです
msg
@ChTalk 0 voice/variant_only/c.ogg
へんしゅのみのないよう
msg
"""


@pytest.fixture
def partial_body_story_json() -> dict[str, Any]:
    return _build_story_json(
        PARTIAL_BODY_SCRIPT, PARTIAL_STORY_ID, PARTIAL_BODY_EPISODE_ID
    )


@pytest.fixture
def partial_variant_story_json() -> dict[str, Any]:
    return _build_story_json(
        PARTIAL_VARIANT_SCRIPT,
        PARTIAL_STORY_ID,
        PARTIAL_VARIANT_EPISODE_ID,
        variant_trace={
            "baseEpisodeId": PARTIAL_BODY_EPISODE_ID,
            "variantPattern": "spine",
            "dupIndex": None,
            "judgment": "exception",
            "bodyIdentifierCount": 4,
            "variantIdentifierCount": 4,
            "extraInVariantCount": 2,
        },
    )


def test_partial_overlap_keeps_both_unique_contents_dedups_shared_only(
    partial_body_story_json, partial_variant_story_json
):
    shared_body_id = _block_id_by_text(partial_body_story_json, "きょうつうシーンです")
    body_only_id = _block_id_by_text(partial_body_story_json, "ほんたいのみのないよう")
    shared_variant_id = _block_id_by_text(
        partial_variant_story_json, "きょうつうシーンです"
    )
    variant_only_id = _block_id_by_text(
        partial_variant_story_json, "へんしゅのみのないよう"
    )

    extractions = extract_stories_with_hscene_dedup(
        [partial_body_story_json, partial_variant_story_json]
    )

    body_extraction = _extraction_for(extractions, PARTIAL_BODY_EPISODE_ID)
    variant_extraction = _extraction_for(extractions, PARTIAL_VARIANT_EPISODE_ID)

    # 本体固有内容 (body_only) は本体側にそのまま残る
    assert set(body_extraction["evidenceIndex"].keys()) == {
        shared_body_id,
        body_only_id,
    }

    # 変種固有内容 (variant_only) は残り、共有ブロックのみ除外される
    assert set(variant_extraction["evidenceIndex"].keys()) == {variant_only_id}
    dedup = variant_extraction["hsceneDedup"]
    assert dedup["excludedBlockCount"] == 1
    assert dedup["excludedBlockIds"] == [shared_variant_id]
    assert dedup["dedupedAgainstEpisodeIds"] == [PARTIAL_BODY_EPISODE_ID]


# ----------------------------------------------------------------
# 変種同士の重複 (初出のみ抽出対象、二重計上しない)
# ----------------------------------------------------------------

SIBLING_STORY_ID = "CHAR_HS_TESTCHAR3"
SIBLING_BODY_EPISODE_ID = "CHAR_HS_TESTCHAR3_E02"
SIBLING_VARIANT_N_EPISODE_ID = "CHAR_HS_TESTCHAR3_E02_VN"
SIBLING_VARIANT_SP_EPISODE_ID = "CHAR_HS_TESTCHAR3_E02_VSP"

SIBLING_BODY_SCRIPT = """@ChTalk 0 voice/sibling_body/a.ogg
もとのシーンです
msg
"""

# 両方のvariantが全く同じ新規内容 (bodyには存在しない) を持つ
SIBLING_SHARED_NEW_SCRIPT = """@ChTalk 0 voice/sibling_shared/x.ogg
きょうつう変種内容です
msg
"""


@pytest.fixture
def sibling_body_story_json() -> dict[str, Any]:
    return _build_story_json(
        SIBLING_BODY_SCRIPT, SIBLING_STORY_ID, SIBLING_BODY_EPISODE_ID
    )


def _sibling_variant_trace(dup_index=None, pattern="n") -> dict:
    return {
        "baseEpisodeId": SIBLING_BODY_EPISODE_ID,
        "variantPattern": pattern,
        "dupIndex": dup_index,
        "judgment": "exception",
        "bodyIdentifierCount": 2,
        "variantIdentifierCount": 2,
        "extraInVariantCount": 2,
    }


@pytest.fixture
def sibling_variant_n_story_json() -> dict[str, Any]:
    return _build_story_json(
        SIBLING_SHARED_NEW_SCRIPT,
        SIBLING_STORY_ID,
        SIBLING_VARIANT_N_EPISODE_ID,
        variant_trace=_sibling_variant_trace(pattern="n"),
    )


@pytest.fixture
def sibling_variant_sp_story_json() -> dict[str, Any]:
    return _build_story_json(
        SIBLING_SHARED_NEW_SCRIPT,
        SIBLING_STORY_ID,
        SIBLING_VARIANT_SP_EPISODE_ID,
        variant_trace=_sibling_variant_trace(pattern="spine"),
    )


def test_sibling_variants_dedup_against_each_other_first_occurrence_only(
    sibling_body_story_json, sibling_variant_n_story_json, sibling_variant_sp_story_json
):
    shared_n_id = _block_id_by_text(
        sibling_variant_n_story_json, "きょうつう変種内容です"
    )
    shared_sp_id = _block_id_by_text(
        sibling_variant_sp_story_json, "きょうつう変種内容です"
    )

    # 入力順をわざと逆 (SP, N) にしても、episodeIdの辞書順
    # (_VN < _VSP) で決定的に処理されることを確認する
    extractions = extract_stories_with_hscene_dedup(
        [
            sibling_body_story_json,
            sibling_variant_sp_story_json,
            sibling_variant_n_story_json,
        ]
    )

    n_extraction = _extraction_for(extractions, SIBLING_VARIANT_N_EPISODE_ID)
    sp_extraction = _extraction_for(extractions, SIBLING_VARIANT_SP_EPISODE_ID)

    # 初出 (_VN、episodeId辞書順で先) は保持される
    n_dedup = n_extraction["hsceneDedup"]
    assert n_dedup["excludedBlockCount"] == 0
    assert shared_n_id in n_extraction["evidenceIndex"]

    # 後続 (_VSP) は _VN 側の同一内容と重複するため除外される
    sp_dedup = sp_extraction["hsceneDedup"]
    assert sp_dedup["excludedBlockCount"] == 1
    assert sp_dedup["excludedBlockIds"] == [shared_sp_id]
    assert sp_dedup["dedupedAgainstEpisodeIds"] == [SIBLING_VARIANT_N_EPISODE_ID]
    assert shared_sp_id not in sp_extraction["evidenceIndex"]


# ----------------------------------------------------------------
# 無回帰: トレースの無い通常episode
# ----------------------------------------------------------------


def test_episode_without_trace_has_no_hscene_dedup_field_and_matches_extract_story():
    script = """@ChTalk 0
これは通常エピソードの会話です。
msg
"""
    story_json = _build_story_json(
        script, "MAIN_S01_C01", "MAIN_S01_C01_E01", category="MAIN"
    )

    via_dedup = extract_stories_with_hscene_dedup([story_json])[0]
    via_plain = Extractor().extract_story(story_json)[0]

    assert "hsceneDedup" not in via_dedup
    assert via_dedup == via_plain


# ----------------------------------------------------------------
# 本体不在: dedupを実施せずその旨を記録する
# ----------------------------------------------------------------


def test_variant_without_body_in_input_skips_dedup_and_records_it():
    only_variant = _build_story_json(
        VARIANT_SUPERSET_SCRIPT,
        BASE_STORY_ID,
        VARIANT_SUPERSET_EPISODE_ID,
        variant_trace={
            "baseEpisodeId": BODY_EPISODE_ID,
            "variantPattern": "n",
            "dupIndex": None,
            "judgment": "exception",
            "bodyIdentifierCount": 4,
            "variantIdentifierCount": 6,
            "extraInVariantCount": 2,
        },
    )

    extractions = extract_stories_with_hscene_dedup([only_variant])
    extraction = _extraction_for(extractions, VARIANT_SUPERSET_EPISODE_ID)

    all_block_ids = {block["id"] for block in _blocks(only_variant)}

    dedup = extraction["hsceneDedup"]
    assert dedup["role"] == "variant"
    assert dedup["groupBaseEpisodeId"] == BODY_EPISODE_ID
    assert dedup["baseEpisodeAvailable"] is False
    assert dedup["excludedBlockCount"] == 0
    assert dedup["excludedBlockIds"] == []
    assert dedup["dedupedAgainstEpisodeIds"] == []
    # 本体不在のため、変種のブロックは一切除外されずフル抽出される
    assert set(extraction["evidenceIndex"].keys()) == all_block_ids


# ----------------------------------------------------------------
# CHAR_HS以外のカテゴリでの無回帰 (念のため明示的に確認)
# ----------------------------------------------------------------


def test_non_char_hs_category_is_unaffected_even_with_multiple_documents(
    body_story_json,
):
    other_script = """@ChTalk 0
別カテゴリの会話です。
msg
"""
    other_story_json = _build_story_json(
        other_script, "EVT_TEST_001", "EVT_TEST_001_E01", category="EVT"
    )

    extractions = extract_stories_with_hscene_dedup([body_story_json, other_story_json])
    other_extraction = _extraction_for(extractions, "EVT_TEST_001_E01")
    assert "hsceneDedup" not in other_extraction
