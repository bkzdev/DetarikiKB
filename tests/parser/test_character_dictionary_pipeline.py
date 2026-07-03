"""
tests/parser/test_character_dictionary_pipeline.py
knowledge/dictionaries/characters.yaml 相当の人手管理辞書が、
Parser -> Extractor -> Merger のパイプライン全体でどう扱われるかを
確認する統合テスト。

StoryParser (実データではなく合成スクリプト文字列) -> Normalizer ->
Extractor -> agents/merger/character.build_character_entities の順に
実際に通し、以下を確認する。

- 辞書でcharacterId (confirmed) が解決済みのsourceCharacterIdは、
  CharacterCandidate.existingCharacterIdが設定され、mergeでstatus:merged
  になる
- 辞書にsourceCharacterId自体が無いものは、CharacterCandidate.
  existingCharacterIdがNoneのまま、mergeでもstatus:unresolvedのまま
- 名前 (displayName) が分かっているだけ (status: name_only) の
  キャラクターも、名前一致だけでは絶対にresolved/mergedにならない
- evidenceRefs/sourceCandidatesが両ケースとも壊れず残る

実データ由来のfixtureは一切使わない (script本文は合成、キャラクター名は
テスト用の合成データ)。
"""

from __future__ import annotations

import yaml

from agents.extractor import Extractor
from agents.merger.character import build_character_entities
from agents.parser.normalizer import Normalizer
from agents.parser.parser import StoryParser
from agents.parser.resolver import CharacterDictionary


def _write_yaml_dictionary(tmp_path, characters):
    path = tmp_path / "characters.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"schemaVersion": "0.1", "characters": characters}, f)
    return path


def _build_normalized_story(char_dict: CharacterDictionary) -> dict:
    script = """$num0 = 9001
$num1 = 9999
@ChTalk 0
確定済みキャラクターのセリフ
@ChTalk 1
未登録キャラクターのセリフ
"""
    parser = StoryParser(char_dict=char_dict)
    parse_result = parser.parse_text(script)

    normalizer = Normalizer(story_id="TEST_STORY", story_category="OTHER")
    return normalizer.normalize(parse_result)


def test_confirmed_character_resolved_through_full_pipeline(tmp_path):
    dictionary_path = _write_yaml_dictionary(
        tmp_path,
        [
            {
                "sourceCharacterId": "9001",
                "characterId": "CHAR_TEST_PIPELINE_A",
                "displayName": "Test Pipeline Character A",
                "aliases": [],
                "status": "confirmed",
            },
        ],
    )
    char_dict = CharacterDictionary()
    char_dict.load(dictionary_path)

    story_json = _build_normalized_story(char_dict)
    extraction = Extractor().extract_story(story_json)[0]

    candidates_by_source = {c["sourceCharacterId"]: c for c in extraction["characters"]}

    confirmed_candidate = candidates_by_source["9001"]
    assert confirmed_candidate["existingCharacterId"] == "CHAR_TEST_PIPELINE_A"
    assert confirmed_candidate["confidence"] == 0.9
    assert confirmed_candidate["evidenceIds"]

    unknown_candidate = candidates_by_source["9999"]
    assert unknown_candidate["existingCharacterId"] is None
    assert unknown_candidate["confidence"] == 0.5
    assert unknown_candidate["evidenceIds"]

    valid_entries = [("test_episode.json", extraction)]
    entities = build_character_entities(valid_entries)
    entities_by_id = {e["id"]: e for e in entities}

    merged = entities_by_id["CHAR_TEST_PIPELINE_A"]
    assert merged["status"] == "merged"
    assert merged["canonicalId"] == "CHAR_TEST_PIPELINE_A"
    assert merged["evidenceRefs"]
    assert merged["sourceCandidates"]

    unresolved_entries = [e for e in entities if e["id"] != "CHAR_TEST_PIPELINE_A"]
    assert len(unresolved_entries) == 1
    unresolved = unresolved_entries[0]
    assert unresolved["status"] == "unresolved"
    assert unresolved["canonicalId"] is None
    assert unresolved["evidenceRefs"]
    assert unresolved["sourceCandidates"]


def test_name_only_character_never_auto_resolved(tmp_path):
    """status: name_only (characterId未設定) のキャラクターは、
    表示名が分かっていても構造化IDが無いため、merge後も必ずunresolvedの
    ままであることを確認する (名前一致だけでの自動確定禁止)。"""
    dictionary_path = _write_yaml_dictionary(
        tmp_path,
        [
            {
                "sourceCharacterId": "9002",
                "characterId": None,
                "displayName": "Test Pipeline Character B",
                "aliases": [],
                "status": "name_only",
            },
        ],
    )
    char_dict = CharacterDictionary()
    char_dict.load(dictionary_path)

    script = """$num0 = 9002
@ChTalk 0
名前だけ判明しているキャラクターのセリフ
"""
    parser = StoryParser(char_dict=char_dict)
    parse_result = parser.parse_text(script)
    normalizer = Normalizer(story_id="TEST_STORY_B", story_category="OTHER")
    story_json = normalizer.normalize(parse_result)

    extraction = Extractor().extract_story(story_json)[0]
    candidate = extraction["characters"][0]

    # 表示名は解決されているが、canonical IDは無い
    assert candidate["existingCharacterId"] is None
    assert candidate["sourceCharacterId"] == "9002"

    entities = build_character_entities([("test_episode_b.json", extraction)])
    assert len(entities) == 1
    assert entities[0]["status"] == "unresolved"
    assert entities[0]["canonicalId"] is None
