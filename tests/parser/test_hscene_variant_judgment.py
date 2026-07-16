"""
tests/parser/test_hscene_variant_judgment.py
H_scene変種の動的部分集合判定 (agents/parser/hscene_variant_judgment.py) の
合成fixtureテスト。

実データ・実キャラ名・実セリフは一切使用しない
(docs/runbooks/AI_PR_Playbook.md §4 実装PR「テストは合成fixtureのみ」)。
"""

from __future__ import annotations

from pathlib import Path

from agents.parser.exporter import Exporter
from agents.parser.hscene_variant_judgment import (
    derive_variant_episode_id,
    extract_identifier_set,
    find_hscene_body_files,
    find_variant_candidates,
    hscene_number,
    judge_body_variants,
    judge_subset,
    match_hscene_body_stem,
)
from agents.parser.normalizer import Normalizer
from agents.parser.parser import StoryParser
from agents.parser.resolver import CharacterDictionary
from agents.parser.tokenizer import Tokenizer


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ----------------------------------------------------------------
# extract_identifier_set
# ----------------------------------------------------------------


def test_extract_identifier_set_collects_asset_paths_and_text(tmp_path):
    script = (
        "$num0 = 1\n"
        "@ChTalk 0 test/asset/line001\n"
        "こんにちは、テストです。\n"
        "@ChTalkSoundOff 0\n"
        "音声なしのセリフです。\n"
        "log ----------------- $arg0\tログ行はセリフではありません。\n"
        "mozaiku test_mask 0.018 cutoff\n"
    )
    body_path = _write(tmp_path / "H_scene1.dec", script)

    identifiers = extract_identifier_set(body_path)

    assert "asset:test/asset/line001" in identifiers
    assert "text:こんにちは、テストです。" in identifiers
    assert "text:音声なしのセリフです。" in identifiers
    # @ChTalkSoundOffにはpath引数が無いため、asset識別子は増えない
    assert not any(i.startswith("asset:") and "line001" not in i for i in identifiers)
    # 開発用ログ行・モザイク指定行は除外される
    assert not any("ログ行" in i for i in identifiers)
    assert not any("mozaiku" in i for i in identifiers)


def test_extract_identifier_set_empty_file_is_empty_set(tmp_path):
    body_path = _write(tmp_path / "H_scene2.dec", "")
    assert extract_identifier_set(body_path) == frozenset()


def test_spine_talk_same_asset_path_treated_as_same_identifier(tmp_path):
    """_spine変種が@ChTalkを@SpineTalkへ置換していても、同一アセットpathを
    参照していれば同一識別子として扱われる (§5.3の比較手法)。"""
    body = _write(
        tmp_path / "H_scene3.dec",
        "$num0 = 1\n@ChTalk 0 test/asset/line001\nおなじせりふ\n",
    )
    variant = _write(
        tmp_path / "H_scene3_spine.dec",
        "$num0 = 1\n@SpineTalk $num0 test/asset/line001\nおなじせりふ\n",
    )

    body_ids = extract_identifier_set(body)
    variant_ids = extract_identifier_set(variant)

    assert body_ids == variant_ids
    judgment = judge_subset(body_ids, variant_ids)
    assert judgment.is_subset
    assert judgment.classification == "subset"


# ----------------------------------------------------------------
# judge_subset
# ----------------------------------------------------------------


def test_judge_subset_empty_variant_is_subset():
    body = frozenset({"asset:a", "text:x"})
    variant: frozenset[str] = frozenset()
    judgment = judge_subset(body, variant)
    assert judgment.is_subset
    assert judgment.classification == "subset"
    assert judgment.extra_in_variant_count == 0


def test_judge_subset_reverse_superset_is_exception():
    """変種側が本体側を全て含んだ上でさらに追加内容を持つ (reverse_superset型、
    主に#Nパターン)。"""
    body = frozenset({"asset:a", "text:x"})
    variant = frozenset({"asset:a", "text:x", "asset:b", "text:y"})
    judgment = judge_subset(body, variant)
    assert not judgment.is_subset
    assert judgment.classification == "exception"
    assert judgment.extra_in_variant_count == 2


def test_judge_subset_partial_overlap_is_exception():
    """本体・変種の双方に相手に無い内容がある (partial_overlap型、_n全件・
    _spine大半)。"""
    body = frozenset({"asset:shared", "text:body_only"})
    variant = frozenset({"asset:shared", "text:variant_only"})
    judgment = judge_subset(body, variant)
    assert not judgment.is_subset
    assert judgment.classification == "exception"
    assert judgment.extra_in_variant_count == 1


# ----------------------------------------------------------------
# ファイル名パターン検出
# ----------------------------------------------------------------


def test_match_hscene_body_stem():
    assert match_hscene_body_stem("H_scene14") is not None
    assert match_hscene_body_stem("H_scene14_n") is None
    assert match_hscene_body_stem("H_scene14_spine") is None
    assert match_hscene_body_stem("H_scene14_VR") is None
    assert match_hscene_body_stem("H_scene_s") is None  # 番号無しは本体パターン対象外


def test_hscene_number(tmp_path):
    assert hscene_number(tmp_path / "H_scene14.dec") == 14
    assert hscene_number(tmp_path / "H_scene14_n.dec") is None


def test_find_variant_candidates_all_patterns(tmp_path):
    body = _write(tmp_path / "H_scene1.dec", "")
    _write(tmp_path / "H_scene1_n.dec", "")
    _write(tmp_path / "H_scene1_spine.dec", "")
    _write(tmp_path / "H_scene1 #2.dec", "")
    _write(tmp_path / "H_scene1_n #2.dec", "")
    _write(tmp_path / "H_scene1_spine #2.dec", "")
    _write(tmp_path / "H_scene1_VR.dec", "")
    # 無関係ファイル (本体とは別のH_scene番号、無視されるべき)
    _write(tmp_path / "H_scene11.dec", "")
    _write(tmp_path / "H_scene1_img.dec", "")

    candidates = find_variant_candidates(body)
    patterns = {(c.pattern, c.dup_index) for c in candidates}

    assert patterns == {
        ("n", None),
        ("spine", None),
        ("hash", 2),
        ("n_hash", 2),
        ("spine_hash", 2),
        ("vr", None),
    }
    # H_scene11.dec / H_scene1_img.dec は候補に含まれない
    assert all("H_scene11" not in str(c.path) for c in candidates)
    assert all("_img" not in str(c.path) for c in candidates)


def test_find_hscene_body_files_recursive_directory_scan(tmp_path):
    _write(tmp_path / "char1" / "H_scene1.dec", "")
    _write(tmp_path / "char1" / "H_scene1_n.dec", "")
    _write(tmp_path / "char1" / "H_scene2.dec", "")
    _write(tmp_path / "char2" / "H_scene1.dec", "")
    _write(tmp_path / "char1" / "H_scene_s.dec", "")

    bodies = find_hscene_body_files(tmp_path)
    names = sorted(str(p.relative_to(tmp_path)) for p in bodies)

    assert names == [
        str(Path("char1") / "H_scene1.dec"),
        str(Path("char1") / "H_scene2.dec"),
        str(Path("char2") / "H_scene1.dec"),
    ]


# ----------------------------------------------------------------
# derive_variant_episode_id (§6.2 suffix規則)
# ----------------------------------------------------------------


def test_derive_variant_episode_id_simple_patterns():
    base = "CHAR_HS_TEST_E06"
    assert derive_variant_episode_id(base, "n") == "CHAR_HS_TEST_E06_VN"
    assert derive_variant_episode_id(base, "spine") == "CHAR_HS_TEST_E06_VSP"


def test_derive_variant_episode_id_hash_patterns():
    base = "CHAR_HS_TEST_E06"
    assert derive_variant_episode_id(base, "hash", 2) == "CHAR_HS_TEST_E06_VD2"
    assert derive_variant_episode_id(base, "n_hash", 2) == "CHAR_HS_TEST_E06_VN_D2"
    assert derive_variant_episode_id(base, "spine_hash", 2) == "CHAR_HS_TEST_E06_VSP_D2"


def test_derive_variant_episode_id_hash_pattern_requires_dup_index():
    import pytest

    with pytest.raises(ValueError):
        derive_variant_episode_id("CHAR_HS_TEST_E06", "hash", None)


def test_derive_variant_episode_id_vr_is_unsupported():
    import pytest

    with pytest.raises(ValueError):
        derive_variant_episode_id("CHAR_HS_TEST_E06", "vr")


# ----------------------------------------------------------------
# judge_body_variants (統合)
# ----------------------------------------------------------------


def test_judge_body_variants_subset_variant_is_not_flagged(tmp_path):
    body = _write(
        tmp_path / "H_scene1.dec",
        "$num0 = 1\n@ChTalk 0 a/1\nせりふ1\n@ChTalk 0 a/2\nせりふ2\n",
    )
    _write(tmp_path / "H_scene1_n.dec", "$num0 = 1\n@ChTalk 0 a/1\nせりふ1\n")

    result = judge_body_variants(body, base_episode_id="CHAR_HS_TEST_E01")

    assert len(result.variants) == 1
    v = result.variants[0]
    assert v.judgment == "subset"
    assert v.derived_episode_id is None
    assert result.exception_variants == []


def test_judge_body_variants_exception_variant_gets_episode_id(tmp_path):
    body = _write(tmp_path / "H_scene1.dec", "$num0 = 1\n@ChTalk 0 a/1\nせりふ1\n")
    _write(
        tmp_path / "H_scene1 #9.dec",
        "$num0 = 1\n@ChTalk 0 a/1\nせりふ1\n@ChTalk 0 a/2\n追加のせりふ\n",
    )

    result = judge_body_variants(body, base_episode_id="CHAR_HS_TEST_E01")

    assert len(result.variants) == 1
    v = result.variants[0]
    assert v.judgment == "exception"
    assert v.variant.pattern == "hash"
    assert v.variant.dup_index == 9
    assert v.derived_episode_id == "CHAR_HS_TEST_E01_VD9"
    assert result.exception_variants == [v]


def test_judge_body_variants_vr_always_skipped_even_with_extra_content(tmp_path):
    """_VRは内容に関わらず常にskip対象 (判定対象外) であり、subset/exception
    どちらの判定も行わない。"""
    body = _write(tmp_path / "H_scene1.dec", "$num0 = 1\n@ChTalk 0 a/1\nせりふ1\n")
    _write(
        tmp_path / "H_scene1_VR.dec",
        "$num0 = 1\n@ChTalk 0 a/999\n本体に存在しない内容\n",
    )

    result = judge_body_variants(body, base_episode_id="CHAR_HS_TEST_E01")

    assert len(result.variants) == 1
    v = result.variants[0]
    assert v.judgment == "skipped_vr"
    assert v.derived_episode_id is None


def test_judge_body_variants_compound_n_hash_suffix(tmp_path):
    body = _write(tmp_path / "H_scene5.dec", "$num0 = 1\n@ChTalk 0 a/1\nせりふ1\n")
    _write(
        tmp_path / "H_scene5_n #3.dec",
        "$num0 = 1\n@ChTalk 0 a/1\nせりふ1\n@ChTalk 0 a/extra\n複合パターンの追加\n",
    )

    result = judge_body_variants(body, base_episode_id="CHAR_HS_TEST_E05")

    v = result.variants[0]
    assert v.variant.pattern == "n_hash"
    assert v.variant.dup_index == 3
    assert v.judgment == "exception"
    assert v.derived_episode_id == "CHAR_HS_TEST_E05_VN_D3"


def test_judge_body_variants_without_base_episode_id_no_derivation(tmp_path):
    """base_episode_id未指定時は、exception判定はされてもderived_episode_id
    はNoneのまま (episodeId導出には呼び出し元がstoryIdを明示する必要がある)。"""
    body = _write(tmp_path / "H_scene1.dec", "$num0 = 1\n@ChTalk 0 a/1\nせりふ1\n")
    _write(
        tmp_path / "H_scene1_spine.dec",
        "$num0 = 1\n@SpineTalk $num0 a/1\nせりふ1\n@SpineTalk $num0 a/2\n追加\n",
    )

    result = judge_body_variants(body)

    v = result.variants[0]
    assert v.judgment == "exception"
    assert v.derived_episode_id is None


# ----------------------------------------------------------------
# CHAR_HSカテゴリのnormalize出力 (storyCategory / exporter subdir)
# ----------------------------------------------------------------


def test_char_hs_category_normalizes_and_exports_to_character_subdir(tmp_path):
    char_dict = CharacterDictionary()
    char_dict._name_map = {"1": "テストキャラ"}
    char_dict._id_map = {"1": "CHAR_TEST"}

    script = "$num0 = 1\n@ChTalk 0 test/asset/1\nこんにちは。\n"
    parser = StoryParser(char_dict=char_dict)
    parse_result = parser.parse_text(script, source_file="H_scene1")

    normalizer = Normalizer(
        story_id="CHAR_HS_TEST",
        story_category="CHAR_HS",
        episode_id="CHAR_HS_TEST_E01_VD9",
        source_file="H_scene1 #9",
        variant_trace={
            "baseEpisodeId": "CHAR_HS_TEST_E01",
            "variantPattern": "hash",
            "dupIndex": 9,
            "judgment": "exception",
            "bodyIdentifierCount": 1,
            "variantIdentifierCount": 2,
            "extraInVariantCount": 1,
        },
    )
    story_json = normalizer.normalize(parse_result, line_count=3)

    assert story_json["storyCategory"] == "CHAR_HS"
    assert story_json["source"]["hsceneVariantTrace"]["variantPattern"] == "hash"
    assert story_json["source"]["hsceneVariantTrace"]["judgment"] == "exception"

    exporter = Exporter(output_dir=tmp_path, overwrite=True)
    output_path = exporter.export_with_category(story_json)

    assert output_path.parent.name == "character"
    assert output_path.exists()


def test_default_tokenizer_reused_across_calls(tmp_path):
    """呼び出し側がTokenizerインスタンスを使い回せることの確認
    (judge_hscene_variants.pyのCLIが本体×変種すべてで1つのTokenizerを
    再利用する設計を裏付ける)。"""
    tok = Tokenizer()
    body = _write(tmp_path / "H_scene1.dec", "$num0 = 1\n@ChTalk 0 a/1\nせりふ\n")
    ids1 = extract_identifier_set(body, tokenizer=tok)
    ids2 = extract_identifier_set(body, tokenizer=tok)
    assert ids1 == ids2 == frozenset({"asset:a/1", "text:せりふ"})
