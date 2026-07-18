"""
tests/summarizer/test_prompt.py
agents/summarizer/prompt.py (Episode Summary生成prompt / Story Summary合成
promptの構築) のテスト。

合成fixtureのみを使う。実イベント名・実キャラ名・実あらすじ・実セリフは
一切含まない (docs/architecture/06_AI/Story_Summary_Design.md参照)。
"""

from __future__ import annotations

from agents.summarizer.prompt import (
    CHARACTERS_PER_TOKEN_ESTIMATE,
    DEFAULT_MAX_CONTEXT_TOKENS,
    DEFAULT_MAX_INPUT_CHARACTERS,
    DOMAIN_CONTEXT_BLOCK_HEADER,
    EPISODE_SUMMARY_SYSTEM_PROMPT,
    INCLUDED_BLOCK_TYPES,
    PROMPT_VERSION,
    REFINE_PROMPT_VERSION_SUFFIX,
    REFINE_SYSTEM_PROMPT,
    STORY_SUMMARY_PROMPT_VERSION,
    STORY_SUMMARY_PROMPT_VERSION_FALLBACK,
    STORY_SUMMARY_SYSTEM_PROMPT,
    STORY_SUMMARY_SYSTEM_PROMPT_V2,
    UNRESOLVED_SPEAKER_LABEL,
    EpisodeBlocksInput,
    EpisodeSummaryInput,
    ExtractedBlock,
    build_domain_context_block,
    build_episode_summary_prompt,
    build_episode_summary_system_prompt,
    build_refine_prompt,
    build_refine_system_prompt,
    build_story_summary_prompt,
    build_story_summary_prompt_v2,
    build_story_summary_system_prompt,
    build_story_summary_system_prompt_v2,
    estimate_token_count,
    extract_episode_blocks,
    extract_speaker_names,
    format_block_line,
    format_episode_summary_line,
    render_blocks_text,
    render_episode_summaries_text,
    render_story_full_text,
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


def _unresolved_dialogue_block(
    block_id: str, text: str, speaker_name: str = "不明人物(ID:83)"
) -> dict:
    """isResolved=Falseの未解決話者Block

    (`agents/parser/resolver.py` `Speaker.unknown`が付与する
    `不明人物(ID:NNN)`形式のplaceholderを模したfixture。合成ID・合成本文の
    みで、実データ由来のspeakerIdは含まない)。
    """
    return {
        "id": block_id,
        "type": "dialogue",
        "text": text,
        "speaker": {
            "speakerId": None,
            "speakerName": speaker_name,
            "isResolved": False,
        },
        "source": {},
    }


def _speaker_no_is_resolved_field_block(
    block_id: str, text: str, speaker_name: str
) -> dict:
    """isResolvedフィールド自体が欠落しているspeaker (fallback判定の検証用)。

    schema上`isResolved`はrequiredだが、fallback文字列判定の経路自体を
    独立して検証するためのfixture。
    """
    return {
        "id": block_id,
        "type": "dialogue",
        "text": text,
        "speaker": {"speakerId": None, "speakerName": speaker_name},
        "source": {},
    }


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
# (1b) 未解決話者 (isResolved=False) のspeaker_nameが「話者不明」に
#      置き換わること (Stage 1 small batchレビューで実測された対策)
# ----------------------------------------------------------------


def test_extract_replaces_unresolved_speaker_name_with_placeholder_label():
    episode = _episode(
        [
            _scene(
                [
                    _unresolved_dialogue_block(
                        "EVT_E01_DLG0001", "未解決話者の台詞", "不明人物(ID:83)"
                    ),
                ]
            )
        ]
    )
    blocks = extract_episode_blocks(episode)
    assert blocks[0].speaker_name == UNRESOLVED_SPEAKER_LABEL
    # 内部IDの断片(ID:83)がprompt入力側の話者名に残らないこと。
    assert "83" not in blocks[0].speaker_name


def test_extract_keeps_resolved_speaker_name_as_is():
    episode = _episode(
        [_scene([_dialogue_block("EVT_E01_DLG0001", "Speaker A", "台詞A")])]
    )
    blocks = extract_episode_blocks(episode)
    assert blocks[0].speaker_name == "Speaker A"


def test_extract_falls_back_to_prefix_pattern_when_is_resolved_field_missing():
    # isResolvedフィールド自体が欠落している防御的fallback経路。
    # flagで判定できない場合のみ「不明人物」プレフィックスの文字列判定を使う。
    episode = _episode(
        [
            _scene(
                [
                    _speaker_no_is_resolved_field_block(
                        "EVT_E01_DLG0001", "台詞B", "不明人物(ID:99)"
                    ),
                ]
            )
        ]
    )
    blocks = extract_episode_blocks(episode)
    assert blocks[0].speaker_name == UNRESOLVED_SPEAKER_LABEL


def test_extract_does_not_treat_named_speaker_without_is_resolved_field_as_unresolved():
    # fallback判定は「不明人物」プレフィックス一致時のみ発動し、
    # 通常の話者名を誤って置き換えないこと。
    episode = _episode(
        [
            _scene(
                [
                    _speaker_no_is_resolved_field_block(
                        "EVT_E01_DLG0001", "台詞C", "Speaker A"
                    ),
                ]
            )
        ]
    )
    blocks = extract_episode_blocks(episode)
    assert blocks[0].speaker_name == "Speaker A"


def test_format_block_line_uses_unresolved_placeholder_label():
    block = ExtractedBlock(
        block_id="EVT_E01_DLG0001",
        block_type="dialogue",
        speaker_name=UNRESOLVED_SPEAKER_LABEL,
        text="台詞テキスト",
    )
    assert format_block_line(block) == "[EVT_E01_DLG0001] 話者不明: 台詞テキスト"


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


def test_system_prompt_instructs_not_to_treat_unresolved_placeholder_as_person_name():
    # 「話者不明」はplaceholderラベルであり人物名として要約に書かないことを
    # system promptで明示する (Stage 1 small batchレビューで実測された対策)。
    assert UNRESOLVED_SPEAKER_LABEL in EPISODE_SUMMARY_SYSTEM_PROMPT
    assert "人物名" in EPISODE_SUMMARY_SYSTEM_PROMPT


def test_prompt_version_constant():
    assert PROMPT_VERSION == "episode-summary-v4"


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
    assert STORY_SUMMARY_PROMPT_VERSION == "story-summary-v3"
    assert STORY_SUMMARY_PROMPT_VERSION != PROMPT_VERSION


def test_story_summary_prompt_version_fallback_constant_is_distinct():
    # contextサイズガード超過時にprovenanceへ記録される値
    # (`summary-generation-quality-v2`)。
    assert STORY_SUMMARY_PROMPT_VERSION_FALLBACK == "story-summary-v1-fallback"
    assert STORY_SUMMARY_PROMPT_VERSION_FALLBACK != STORY_SUMMARY_PROMPT_VERSION


# ----------------------------------------------------------------
# (5) episode-summary-v3: 登場人物リスト注入・主語明確化・本文中evidence ID
#     参照禁止 (`summary-generation-quality-v2`)
# ----------------------------------------------------------------


def test_extract_speaker_names_dedups_and_preserves_first_appearance_order():
    blocks = [
        ExtractedBlock("EVT_E01_DLG0001", "dialogue", "Speaker A", "台詞1"),
        ExtractedBlock("EVT_E01_DLG0002", "dialogue", "Speaker B", "台詞2"),
        ExtractedBlock("EVT_E01_DLG0003", "dialogue", "Speaker A", "台詞3"),
    ]
    assert extract_speaker_names(blocks) == ["Speaker A", "Speaker B"]


def test_extract_speaker_names_excludes_unresolved_and_none():
    blocks = [
        ExtractedBlock("EVT_E01_DLG0001", "dialogue", "Speaker A", "台詞1"),
        ExtractedBlock(
            "EVT_E01_DLG0002", "dialogue", UNRESOLVED_SPEAKER_LABEL, "台詞2"
        ),
        ExtractedBlock("EVT_E01_NAR0001", "narration", None, "地の文"),
    ]
    assert extract_speaker_names(blocks) == ["Speaker A"]


def test_build_episode_summary_prompt_injects_character_list():
    blocks = [
        ExtractedBlock("EVT_E01_DLG0001", "dialogue", "Speaker A", "台詞1"),
        ExtractedBlock("EVT_E01_DLG0002", "dialogue", "Speaker B", "台詞2"),
        ExtractedBlock("EVT_E01_DLG0003", "dialogue", "Speaker A", "台詞3"),
    ]
    prompt = build_episode_summary_prompt(blocks)
    assert "登場人物" in prompt
    assert "Speaker A、Speaker B" in prompt
    # 重複した2回目のSpeaker Aは登場人物一覧行には現れない(1回のみ列挙)。
    assert prompt.count("Speaker A、Speaker B") == 1


def test_build_episode_summary_prompt_character_list_excludes_unresolved():
    blocks = [
        ExtractedBlock(
            "EVT_E01_DLG0001", "dialogue", UNRESOLVED_SPEAKER_LABEL, "台詞1"
        ),
    ]
    prompt = build_episode_summary_prompt(blocks)
    assert "登場人物: (解決済みの登場人物なし)" in prompt


def test_build_episode_summary_prompt_requests_subject_clarity():
    blocks = [ExtractedBlock("EVT_E01_NAR0001", "narration", None, "地の文")]
    prompt = build_episode_summary_prompt(blocks)
    assert "主語" in prompt
    assert "指示語" in prompt


def test_build_episode_summary_prompt_forbids_evidence_id_in_body():
    blocks = [ExtractedBlock("EVT_E01_NAR0001", "narration", None, "地の文")]
    prompt = build_episode_summary_prompt(blocks)
    assert "括弧書き" in prompt


def test_episode_summary_system_prompt_requests_subject_clarity_and_forbids_citation():
    assert "主語" in EPISODE_SUMMARY_SYSTEM_PROMPT
    assert "指示語" in EPISODE_SUMMARY_SYSTEM_PROMPT
    assert "括弧書き" in EPISODE_SUMMARY_SYSTEM_PROMPT


# ----------------------------------------------------------------
# (6) story-summary-v2: 全文直接入力方式 (`summary-generation-quality-v2`)
# ----------------------------------------------------------------


def test_render_story_full_text_joins_episodes_in_order_with_headers():
    items = [
        EpisodeBlocksInput(
            episode_number=1,
            blocks=[
                ExtractedBlock("EVT_E01_DLG0001", "dialogue", "Speaker A", "台詞1")
            ],
        ),
        EpisodeBlocksInput(
            episode_number=2,
            blocks=[ExtractedBlock("EVT_E02_NAR0001", "narration", None, "地の文2")],
        ),
    ]
    full_text = render_story_full_text(items)
    assert "=== Episode 1 ===" in full_text
    assert "=== Episode 2 ===" in full_text
    assert "[EVT_E01_DLG0001] Speaker A: 台詞1" in full_text
    assert "[EVT_E02_NAR0001] 地の文2" in full_text
    assert full_text.index("=== Episode 1 ===") < full_text.index("=== Episode 2 ===")


def test_render_story_full_text_uses_placeholder_for_missing_episode_number():
    items = [EpisodeBlocksInput(episode_number=None, blocks=[])]
    assert "=== Episode ? ===" in render_story_full_text(items)


def test_build_story_summary_prompt_v2_embeds_full_episode_text():
    items = [
        EpisodeBlocksInput(
            episode_number=1,
            blocks=[
                ExtractedBlock("EVT_E01_DLG0001", "dialogue", "Speaker A", "台詞1")
            ],
        ),
    ]
    prompt = build_story_summary_prompt_v2(items)
    assert "[EVT_E01_DLG0001] Speaker A: 台詞1" in prompt
    assert '"text"' in prompt


def test_build_story_summary_prompt_v2_requests_text_only_json_output():
    items = [
        EpisodeBlocksInput(
            episode_number=1,
            blocks=[ExtractedBlock("EVT_E01_NAR0001", "narration", None, "地の文")],
        )
    ]
    prompt = build_story_summary_prompt_v2(items)
    assert '"text"' in prompt
    assert '"evidenceRefs"' not in prompt


def test_build_story_summary_prompt_v2_forbids_speculation_and_requests_clarity():
    items = [
        EpisodeBlocksInput(
            episode_number=1,
            blocks=[ExtractedBlock("EVT_E01_NAR0001", "narration", None, "地の文")],
        )
    ]
    prompt = build_story_summary_prompt_v2(items)
    assert "考察" in prompt or "推測" in prompt
    assert "主語" in prompt


def test_story_summary_system_prompt_v2_forbids_speculation_and_requires_json_only():
    assert "考察" in STORY_SUMMARY_SYSTEM_PROMPT_V2
    assert "推測" in STORY_SUMMARY_SYSTEM_PROMPT_V2
    assert "JSON" in STORY_SUMMARY_SYSTEM_PROMPT_V2
    assert UNRESOLVED_SPEAKER_LABEL in STORY_SUMMARY_SYSTEM_PROMPT_V2


def test_estimate_token_count_empty_string_is_zero():
    assert estimate_token_count("") == 0


def test_estimate_token_count_scales_with_characters_per_token_estimate():
    text = "あ" * (CHARACTERS_PER_TOKEN_ESTIMATE * 10)
    assert estimate_token_count(text) == 10


def test_estimate_token_count_rounds_up_partial_token():
    text = "あ" * (CHARACTERS_PER_TOKEN_ESTIMATE + 1)
    assert estimate_token_count(text) == 2


def test_default_max_context_tokens_is_positive():
    assert isinstance(DEFAULT_MAX_CONTEXT_TOKENS, int)
    assert DEFAULT_MAX_CONTEXT_TOKENS > 0


# ----------------------------------------------------------------
# (7) 自己推敲パス (`--refine`、`summary-generation-quality-v2`)
# ----------------------------------------------------------------


def test_build_refine_prompt_embeds_input_text_and_requests_json_only():
    prompt = build_refine_prompt("推敲対象のあらすじ本文")
    assert "推敲対象のあらすじ本文" in prompt
    assert '"text"' in prompt


def test_build_refine_prompt_requests_no_new_facts_and_similar_length():
    prompt = build_refine_prompt("あらすじ本文")
    assert "無い事実" in prompt
    assert "長さ" in prompt


def test_refine_system_prompt_mentions_subject_ambiguity_and_json_only():
    assert "主語" in REFINE_SYSTEM_PROMPT
    assert "JSON" in REFINE_SYSTEM_PROMPT


def test_refine_prompt_version_suffix_constant():
    assert REFINE_PROMPT_VERSION_SUFFIX == "refine-v2"


# ----------------------------------------------------------------
# (10) domain context注入 (`summary-domain-context-injection`)
# ----------------------------------------------------------------


def test_build_domain_context_block_empty_returns_empty_string():
    assert build_domain_context_block(None) == ""
    assert build_domain_context_block([]) == ""


def test_build_domain_context_block_formats_entries_as_bullet_list():
    block = build_domain_context_block(["事実1", "事実2"])
    assert DOMAIN_CONTEXT_BLOCK_HEADER in block
    assert "- 事実1" in block
    assert "- 事実2" in block
    assert block.index("事実1") < block.index("事実2")


def test_build_episode_summary_system_prompt_without_domain_context_matches_base():
    assert build_episode_summary_system_prompt() == EPISODE_SUMMARY_SYSTEM_PROMPT
    assert build_episode_summary_system_prompt([]) == EPISODE_SUMMARY_SYSTEM_PROMPT


def test_build_episode_summary_system_prompt_appends_domain_context():
    prompt = build_episode_summary_system_prompt(["合成用ドメイン前提"])
    assert prompt.startswith(EPISODE_SUMMARY_SYSTEM_PROMPT)
    assert "合成用ドメイン前提" in prompt


def test_build_story_summary_system_prompt_without_domain_context_matches_base():
    assert build_story_summary_system_prompt() == STORY_SUMMARY_SYSTEM_PROMPT
    assert build_story_summary_system_prompt([]) == STORY_SUMMARY_SYSTEM_PROMPT


def test_build_story_summary_system_prompt_appends_domain_context():
    prompt = build_story_summary_system_prompt(["合成用ドメイン前提"])
    assert prompt.startswith(STORY_SUMMARY_SYSTEM_PROMPT)
    assert "合成用ドメイン前提" in prompt


def test_build_story_summary_system_prompt_v2_without_domain_context_matches_base():
    assert build_story_summary_system_prompt_v2() == STORY_SUMMARY_SYSTEM_PROMPT_V2
    assert build_story_summary_system_prompt_v2([]) == STORY_SUMMARY_SYSTEM_PROMPT_V2


def test_build_story_summary_system_prompt_v2_appends_domain_context():
    prompt = build_story_summary_system_prompt_v2(["合成用ドメイン前提"])
    assert prompt.startswith(STORY_SUMMARY_SYSTEM_PROMPT_V2)
    assert "合成用ドメイン前提" in prompt


def test_build_refine_system_prompt_without_domain_context_matches_base():
    assert build_refine_system_prompt() == REFINE_SYSTEM_PROMPT
    assert build_refine_system_prompt([]) == REFINE_SYSTEM_PROMPT


def test_build_refine_system_prompt_appends_domain_context():
    prompt = build_refine_system_prompt(["合成用ドメイン前提"])
    assert prompt.startswith(REFINE_SYSTEM_PROMPT)
    assert "合成用ドメイン前提" in prompt
