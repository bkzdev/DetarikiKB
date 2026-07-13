"""
tests/summarizer/test_prompt.py
agents/summarizer/prompt.py (Episode Summary生成prompt / Story Summary合成
promptの構築) のテスト。

合成fixtureのみを使う。実イベント名・実キャラ名・実あらすじ・実セリフは
一切含まない (docs/architecture/06_AI/Story_Summary_Design.md参照)。
"""

from __future__ import annotations

from agents.summarizer.prompt import (
    DEFAULT_MAX_INPUT_CHARACTERS,
    EPISODE_SUMMARY_SYSTEM_PROMPT,
    INCLUDED_BLOCK_TYPES,
    PROMPT_VERSION,
    STORY_SUMMARY_PROMPT_VERSION,
    STORY_SUMMARY_SYSTEM_PROMPT,
    EpisodeSummaryInput,
    ExtractedBlock,
    build_episode_summary_prompt,
    build_story_summary_prompt,
    extract_episode_blocks,
    format_block_line,
    format_episode_summary_line,
    render_blocks_text,
    render_episode_summaries_text,
)


def _dialogue_block(block_id: str, speaker_name: str | None, text: str) -> dict:
    block = {
        "id": block_id,
        "type": "dialogue",
        "text": text,
        "source": {},
    }
    if speaker_name is not None:
        block["speaker"] = {
            "speakerId": "CHAR_SYNTHETIC",
            "speakerName": speaker_name,
            "isResolved": True,
        }
    return block


def _monologue_block(block_id: str, text: str) -> dict:
    return {
        "id": block_id,
        "type": "monologue",
        "text": text,
        "speaker": {"speakerId": None, "speakerName": None, "isResolved": False},
        "source": {},
    }


def _narration_block(block_id: str, text: str) -> dict:
    return {"id": block_id, "type": "narration", "text": text, "source": {}}


def _choice_block(block_id: str, choice_text: str | None, options: list[dict]) -> dict:
    return {
        "id": block_id,
        "type": "choice",
        "choiceText": choice_text,
        "options": options,
        "source": {},
    }


def _stage_direction_block(block_id: str) -> dict:
    return {
        "id": block_id,
        "type": "stage_direction",
        "directionType": "background",
        "rawCommand": "bg",
        "source": {},
    }


def _unknown_block(block_id: str) -> dict:
    return {"id": block_id, "type": "unknown", "rawText": "unclassified", "source": {}}


def _episode(scenes: list[dict]) -> dict:
    return {
        "episodeId": "EVT_SYNTHETIC_SAMPLE_E01",
        "episodeNumber": 1,
        "metadata": {"publicEpisodeId": "PUB_SYNTHETIC_SAMPLE_E01"},
        "scenes": scenes,
    }


def _scene(blocks: list[dict]) -> dict:
    return {
        "sceneId": "EVT_SYNTHETIC_SAMPLE_E01_SC001",
        "sceneNumber": 1,
        "blocks": blocks,
    }


# ----------------------------------------------------------------
# (1) extract_episode_blocks: 対象type抽出、除外type、id無しblock、
#     choice option内のnested block、空/whitespace本文の除外
# ----------------------------------------------------------------


def test_extract_includes_dialogue_monologue_narration_choice():
    episode = _episode(
        [
            _scene(
                [
                    _dialogue_block("EVT_E01_DLG0001", "Speaker A", "台詞A"),
                    _monologue_block("EVT_E01_MONO0001", "独白B"),
                    _narration_block("EVT_E01_NAR0001", "地の文C"),
                    _choice_block("EVT_E01_CHOICE0001", "選択肢の問い", []),
                ]
            )
        ]
    )
    blocks = extract_episode_blocks(episode)
    block_ids = [b.block_id for b in blocks]
    assert block_ids == [
        "EVT_E01_DLG0001",
        "EVT_E01_MONO0001",
        "EVT_E01_NAR0001",
        "EVT_E01_CHOICE0001",
    ]


def test_extract_excludes_stage_direction_and_unknown():
    episode = _episode(
        [
            _scene(
                [
                    _dialogue_block("EVT_E01_DLG0001", "Speaker A", "台詞A"),
                    _stage_direction_block("EVT_E01_STAGE0001"),
                    _unknown_block("EVT_E01_UNKNOWN0001"),
                ]
            )
        ]
    )
    blocks = extract_episode_blocks(episode)
    assert [b.block_id for b in blocks] == ["EVT_E01_DLG0001"]
    assert INCLUDED_BLOCK_TYPES == frozenset(
        {"dialogue", "monologue", "narration", "choice"}
    )


def test_extract_skips_blocks_without_id():
    episode = _episode(
        [
            _scene(
                [
                    {"type": "dialogue", "text": "id無しなのでskip", "source": {}},
                    _dialogue_block("EVT_E01_DLG0001", "Speaker A", "台詞A"),
                ]
            )
        ]
    )
    blocks = extract_episode_blocks(episode)
    assert [b.block_id for b in blocks] == ["EVT_E01_DLG0001"]


def test_extract_skips_blank_or_missing_text():
    episode = _episode(
        [
            _scene(
                [
                    _narration_block("EVT_E01_NAR0001", "   "),
                    {"id": "EVT_E01_NAR0002", "type": "narration", "source": {}},
                    _narration_block("EVT_E01_NAR0003", "有効な地の文"),
                ]
            )
        ]
    )
    blocks = extract_episode_blocks(episode)
    assert [b.block_id for b in blocks] == ["EVT_E01_NAR0003"]


def test_extract_recurses_into_choice_options_and_keeps_nested_types():
    inner_dialogue = _dialogue_block("EVT_E01_DLG0002", "Speaker A", "選択肢A内の台詞")
    inner_stage = _stage_direction_block("EVT_E01_STAGE0001")
    option_a = {
        "optionId": "EVT_E01_CHOICE0001_OPT01",
        "optionText": "選択肢A",
        "blocks": [inner_dialogue, inner_stage],
    }
    option_b = {
        "optionId": "EVT_E01_CHOICE0001_OPT02",
        "optionText": "選択肢B",
        "blocks": [],
    }
    episode = _episode(
        [
            _scene(
                [
                    _choice_block(
                        "EVT_E01_CHOICE0001", "分岐の問い", [option_a, option_b]
                    )
                ]
            )
        ]
    )
    blocks = extract_episode_blocks(episode)
    block_ids = [b.block_id for b in blocks]
    # choiceブロック自体 + option A内のdialogue (nested stage_directionは除外)
    assert block_ids == ["EVT_E01_CHOICE0001", "EVT_E01_DLG0002"]


def test_extract_uses_choice_text_field_not_text_field_for_choice_blocks():
    episode = _episode(
        [_scene([_choice_block("EVT_E01_CHOICE0001", "分岐の問い本文", [])])]
    )
    blocks = extract_episode_blocks(episode)
    assert blocks[0].text == "分岐の問い本文"


def test_extract_returns_empty_list_for_episode_with_no_scenes():
    assert extract_episode_blocks({"episodeId": "EVT_E01", "scenes": []}) == []
    assert extract_episode_blocks({"episodeId": "EVT_E01"}) == []


def test_extract_speaker_name_none_when_speaker_missing_or_unresolved_without_name():
    episode = _episode(
        [
            _scene(
                [
                    _monologue_block("EVT_E01_MONO0001", "話者名なしの独白"),
                    _narration_block("EVT_E01_NAR0001", "話者情報を持たない地の文"),
                ]
            )
        ]
    )
    blocks = extract_episode_blocks(episode)
    assert all(b.speaker_name is None for b in blocks)


# ----------------------------------------------------------------
# (2) format_block_line / render_blocks_text: blockId埋め込み表現
# ----------------------------------------------------------------


def test_format_block_line_with_speaker_name():
    block = ExtractedBlock(
        block_id="EVT_E01_DLG0001",
        block_type="dialogue",
        speaker_name="Speaker A",
        text="台詞テキスト",
    )
    assert format_block_line(block) == "[EVT_E01_DLG0001] Speaker A: 台詞テキスト"


def test_format_block_line_without_speaker_name():
    block = ExtractedBlock(
        block_id="EVT_E01_NAR0001",
        block_type="narration",
        speaker_name=None,
        text="地の文テキスト",
    )
    assert format_block_line(block) == "[EVT_E01_NAR0001] 地の文テキスト"


def test_render_blocks_text_joins_with_newlines_in_order():
    blocks = [
        ExtractedBlock("EVT_E01_DLG0001", "dialogue", "Speaker A", "台詞1"),
        ExtractedBlock("EVT_E01_NAR0001", "narration", None, "地の文1"),
    ]
    rendered = render_blocks_text(blocks)
    assert rendered == "[EVT_E01_DLG0001] Speaker A: 台詞1\n[EVT_E01_NAR0001] 地の文1"


# ----------------------------------------------------------------
# (3) build_episode_summary_prompt: 埋め込み・出力形式指示・引用強制
# ----------------------------------------------------------------


def test_build_episode_summary_prompt_embeds_block_lines():
    blocks = [
        ExtractedBlock("EVT_E01_DLG0001", "dialogue", "Speaker A", "台詞テキスト"),
    ]
    prompt = build_episode_summary_prompt(blocks)
    assert "[EVT_E01_DLG0001] Speaker A: 台詞テキスト" in prompt


def test_build_episode_summary_prompt_requests_json_output_format():
    blocks = [ExtractedBlock("EVT_E01_NAR0001", "narration", None, "地の文")]
    prompt = build_episode_summary_prompt(blocks)
    assert '"text"' in prompt
    assert '"evidenceRefs"' in prompt


def test_build_episode_summary_prompt_requests_block_id_citation():
    blocks = [ExtractedBlock("EVT_E01_NAR0001", "narration", None, "地の文")]
    prompt = build_episode_summary_prompt(blocks)
    assert "blockId" in prompt


def test_build_episode_summary_prompt_forbids_speculation_and_long_quotes():
    blocks = [ExtractedBlock("EVT_E01_NAR0001", "narration", None, "地の文")]
    prompt = build_episode_summary_prompt(blocks)
    assert "考察" in prompt or "推測" in prompt
    assert "引用" in prompt


def test_system_prompt_forbids_speculation():
    assert "考察" in EPISODE_SUMMARY_SYSTEM_PROMPT
    assert "推測" in EPISODE_SUMMARY_SYSTEM_PROMPT


def test_prompt_version_constant():
    assert PROMPT_VERSION == "episode-summary-v1"


def test_default_max_input_characters_is_positive_and_reasonable():
    assert isinstance(DEFAULT_MAX_INPUT_CHARACTERS, int)
    assert DEFAULT_MAX_INPUT_CHARACTERS > 0


# ----------------------------------------------------------------
# (4) Story Summary合成prompt (Plan §11)
# ----------------------------------------------------------------


def test_format_episode_summary_line_with_number():
    item = EpisodeSummaryInput(episode_number=3, text="episode3の合成要約")
    assert format_episode_summary_line(item) == "[Episode 3] episode3の合成要約"


def test_format_episode_summary_line_without_number_uses_placeholder():
    item = EpisodeSummaryInput(episode_number=None, text="番号なし要約")
    assert format_episode_summary_line(item) == "[Episode ?] 番号なし要約"


def test_render_episode_summaries_text_joins_in_given_order():
    items = [
        EpisodeSummaryInput(episode_number=1, text="要約1"),
        EpisodeSummaryInput(episode_number=2, text="要約2"),
    ]
    rendered = render_episode_summaries_text(items)
    assert rendered == "[Episode 1] 要約1\n[Episode 2] 要約2"


def test_build_story_summary_prompt_embeds_episode_summary_lines_in_order():
    items = [
        EpisodeSummaryInput(episode_number=1, text="episode1の合成要約"),
        EpisodeSummaryInput(episode_number=2, text="episode2の合成要約"),
    ]
    prompt = build_story_summary_prompt(items)
    assert "[Episode 1] episode1の合成要約" in prompt
    assert "[Episode 2] episode2の合成要約" in prompt
    assert prompt.index("[Episode 1]") < prompt.index("[Episode 2]")


def test_build_story_summary_prompt_requests_text_only_json_output():
    items = [EpisodeSummaryInput(episode_number=1, text="要約")]
    prompt = build_story_summary_prompt(items)
    assert '"text"' in prompt
    # story-level出力にevidenceRefsは求めない (機械的unionで決めるため)。
    assert '"evidenceRefs"' not in prompt


def test_build_story_summary_prompt_does_not_request_block_id_citation():
    items = [EpisodeSummaryInput(episode_number=1, text="要約")]
    prompt = build_story_summary_prompt(items)
    # story-level textにblockId引用は求めない (Plan §11)。
    assert "blockId" not in prompt


def test_build_story_summary_prompt_forbids_speculation_and_long_quotes():
    items = [EpisodeSummaryInput(episode_number=1, text="要約")]
    prompt = build_story_summary_prompt(items)
    assert "考察" in prompt or "推測" in prompt
    assert "引用" in prompt


def test_story_summary_system_prompt_forbids_speculation_and_requires_json_only():
    assert "考察" in STORY_SUMMARY_SYSTEM_PROMPT
    assert "推測" in STORY_SUMMARY_SYSTEM_PROMPT
    assert "JSON" in STORY_SUMMARY_SYSTEM_PROMPT


def test_story_summary_prompt_version_constant_is_distinct_from_episode_version():
    assert STORY_SUMMARY_PROMPT_VERSION == "story-summary-v1"
    assert STORY_SUMMARY_PROMPT_VERSION != PROMPT_VERSION
