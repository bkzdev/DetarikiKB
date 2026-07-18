"""
tests/summarizer/test_generator.py
agents/summarizer/generator.py (Episode Summary生成: 入力抽出 -> LLM呼び出し
-> hallucination対策の後処理 -> draft組み立て、およびStory Summary合成) の
テスト。

実Ollamaへのネットワーク呼び出しは一切行わない。すべてfake providerで
検証する。合成fixtureのみを使う (実イベント名・実キャラ名・実あらすじ・
実セリフは一切含まない)。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from agents.summarizer.generator import (
    DEFAULT_VERBATIM_THRESHOLD,
    DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX,
    generate_episode_summary,
    generate_story_summary_draft,
    strip_evidence_id_citations,
    synthesize_story_summary,
)
from agents.summarizer.models import EpisodeSummaryDraft
from agents.summarizer.prompt import (
    PROMPT_VERSION,
    REFINE_PROMPT_VERSION_SUFFIX,
    STORY_SUMMARY_PROMPT_VERSION,
    STORY_SUMMARY_PROMPT_VERSION_FALLBACK,
)
from agents.summarizer.provider import (
    LLMCompletion,
    LLMProviderError,
    SummaryLLMProvider,
)

_SCHEMA_PATH = (
    Path(__file__).parent.parent.parent / "schemas" / "story_summary.schema.json"
)


class FakeProvider(SummaryLLMProvider):
    """呼び出しごとにキューから応答を1件ずつ返すfake provider。

    応答がExceptionインスタンスの場合はそのまま送出する
    (LLMProviderError発生ケースの再現用)。
    """

    def __init__(self, responses: list[str | Exception]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def generate(
        self, prompt: str, *, system: str | None = None, format_json: bool = False
    ) -> LLMCompletion:
        self.calls.append(
            {"prompt": prompt, "system": system, "format_json": format_json}
        )
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return LLMCompletion(
            text=response, model_name="fake-model", provider_name="fake"
        )


def _json_response(text: str, evidence_refs: list[str] | None = None) -> str:
    payload: dict = {"text": text}
    if evidence_refs is not None:
        payload["evidenceRefs"] = evidence_refs
    return json.dumps(payload, ensure_ascii=False)


def _dialogue_block(block_id: str, speaker_name: str, text: str) -> dict:
    return {
        "id": block_id,
        "type": "dialogue",
        "text": text,
        "speaker": {
            "speakerId": "CHAR_SYNTHETIC",
            "speakerName": speaker_name,
            "isResolved": True,
        },
        "source": {},
    }


def _narration_block(block_id: str, text: str) -> dict:
    return {"id": block_id, "type": "narration", "text": text, "source": {}}


def _stage_direction_block(block_id: str) -> dict:
    return {
        "id": block_id,
        "type": "stage_direction",
        "directionType": "background",
        "source": {},
    }


def _episode(episode_id: str, blocks: list[dict], **overrides) -> dict:
    episode = {
        "episodeId": episode_id,
        "episodeNumber": 1,
        "metadata": {"publicEpisodeId": f"PUB_{episode_id}"},
        "scenes": [
            {"sceneId": f"{episode_id}_SC001", "sceneNumber": 1, "blocks": blocks}
        ],
    }
    episode.update(overrides)
    return episode


def _document(story_id: str, episodes: list[dict]) -> dict:
    return {
        "schemaVersion": "0.2",
        "documentType": "normalized_story",
        "storyId": story_id,
        "storyCategory": "EVT",
        "metadata": {"publicStoryId": f"PUB_{story_id}"},
        "episodes": episodes,
    }


def _sample_episode(episode_id: str = "EVT_SYNTHETIC_SAMPLE_E01") -> dict:
    return _episode(
        episode_id,
        [
            _dialogue_block(f"{episode_id}_DLG0001", "Speaker A", "台詞テキストです。"),
            _narration_block(f"{episode_id}_NAR0001", "地の文テキストです。"),
        ],
    )


# ----------------------------------------------------------------
# (1) generate_episode_summary: 正常系
# ----------------------------------------------------------------


def test_generate_episode_summary_success_builds_draft():
    episode = _sample_episode()
    provider = FakeProvider(
        [
            _json_response(
                "これは合成のあらすじです。", ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"]
            )
        ]
    )

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is not None
    assert result.draft.episode_id == "EVT_SYNTHETIC_SAMPLE_E01"
    assert result.draft.text == "これは合成のあらすじです。"
    assert result.draft.evidence_refs == ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"]
    assert result.draft.public_episode_id == "PUB_EVT_SYNTHETIC_SAMPLE_E01"
    assert result.draft.episode_number == 1
    assert result.issues == []
    assert result.skipped is False
    assert result.model_provider == "fake"
    assert result.model_name == "fake-model"


def test_generate_episode_summary_sends_system_prompt_and_format_json():
    episode = _sample_episode()
    provider = FakeProvider([_json_response("あらすじ", [])])

    generate_episode_summary(episode, provider=provider)

    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call["format_json"] is True
    assert call["system"] is not None
    assert (
        "[EVT_SYNTHETIC_SAMPLE_E01_DLG0001] Speaker A: 台詞テキストです。"
        in call["prompt"]
    )


# ----------------------------------------------------------------
# (2) hallucination対策: 実在blockId検証・禁止文字列scan・verbatim検出
#     (いずれも非blocking、draftは生成される)
# ----------------------------------------------------------------


def test_generate_episode_summary_unknown_evidence_ref_is_nonblocking_issue():
    episode = _sample_episode()
    provider = FakeProvider(
        [_json_response("あらすじ", ["EVT_SYNTHETIC_SAMPLE_E01_DLG9999"])]
    )

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is not None
    assert result.draft.evidence_refs == ["EVT_SYNTHETIC_SAMPLE_E01_DLG9999"]
    codes = [issue.code for issue in result.issues]
    assert "unknown-evidence-ref" in codes
    matching = [i for i in result.issues if i.code == "unknown-evidence-ref"]
    assert matching[0].blocking is False


def test_generate_episode_summary_forbidden_text_pattern_is_nonblocking_issue():
    episode = _sample_episode()
    provider = FakeProvider(
        [_json_response("あらすじに$num1という禁止文字列が混入。", [])]
    )

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is not None
    codes = [issue.code for issue in result.issues]
    assert "forbidden-text-pattern" in codes


def test_generate_episode_summary_verbatim_quote_detected_at_default_threshold():
    long_text = "これは検証用に用意した30文字以上ある長めの合成セリフ本文です末尾。"
    assert len(long_text) >= DEFAULT_VERBATIM_THRESHOLD
    episode_id = "EVT_SYNTHETIC_SAMPLE_E01"
    episode = _episode(
        episode_id, [_dialogue_block(f"{episode_id}_DLG0001", "Speaker A", long_text)]
    )
    provider = FakeProvider(
        [_json_response(f"あらすじ本文中に{long_text}をそのまま含めた。", [])]
    )

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is not None
    codes = [issue.code for issue in result.issues]
    assert "verbatim-quote" in codes


def test_generate_episode_summary_verbatim_quote_threshold_boundary():
    # 一致部分文字列の長さちょうど30文字を境界とする (閾値以上で検出)。
    matched_substring = "あ" * 30
    episode_id = "EVT_SYNTHETIC_SAMPLE_E01"
    block_text = f"前置き{matched_substring}後書き"
    episode = _episode(
        episode_id, [_dialogue_block(f"{episode_id}_DLG0001", "Speaker A", block_text)]
    )

    provider_at_threshold = FakeProvider(
        [_json_response(f"要約{matched_substring}まとめ", [])]
    )
    result_at_threshold = generate_episode_summary(
        episode, provider=provider_at_threshold, verbatim_threshold=30
    )
    assert any(i.code == "verbatim-quote" for i in result_at_threshold.issues)

    provider_below_threshold = FakeProvider(
        [_json_response(f"要約{matched_substring}まとめ", [])]
    )
    result_below_threshold = generate_episode_summary(
        episode, provider=provider_below_threshold, verbatim_threshold=31
    )
    assert not any(i.code == "verbatim-quote" for i in result_below_threshold.issues)


def test_generate_episode_summary_short_quote_under_threshold_is_not_flagged():
    episode_id = "EVT_SYNTHETIC_SAMPLE_E01"
    episode = _episode(
        episode_id,
        [_dialogue_block(f"{episode_id}_DLG0001", "Speaker A", "短い一言セリフ。")],
    )
    provider = FakeProvider(
        [_json_response("短い一言セリフ。という発言があった。", [])]
    )

    result = generate_episode_summary(episode, provider=provider, verbatim_threshold=30)

    assert not any(i.code == "verbatim-quote" for i in result.issues)


def test_generate_episode_summary_multiple_issues_all_recorded_and_draft_kept():
    episode = _sample_episode()
    provider = FakeProvider(
        [
            _json_response(
                "$numが混入したあらすじ。", ["EVT_SYNTHETIC_SAMPLE_E01_UNKNOWN"]
            )
        ]
    )

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is not None
    codes = {issue.code for issue in result.issues}
    assert {"unknown-evidence-ref", "forbidden-text-pattern"} <= codes
    assert all(not issue.blocking for issue in result.issues)


# ----------------------------------------------------------------
# (3) 生成自体が成立しない致命的ケース (draft=None, blocking issue)
# ----------------------------------------------------------------


def test_generate_episode_summary_no_input_blocks_is_blocking_and_skips_llm():
    episode_id = "EVT_SYNTHETIC_SAMPLE_E01"
    episode = _episode(episode_id, [_stage_direction_block(f"{episode_id}_STAGE0001")])
    provider = FakeProvider([])

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is None
    assert result.skipped is True
    assert len(result.issues) == 1
    assert result.issues[0].code == "no-input-blocks"
    assert result.issues[0].blocking is True
    assert provider.calls == []


def test_generate_episode_summary_input_too_long_is_blocking_and_skips_llm():
    episode = _sample_episode()
    provider = FakeProvider([])

    result = generate_episode_summary(
        episode, provider=provider, max_input_characters=5
    )

    assert result.draft is None
    assert result.issues[0].code == "input-too-long"
    assert result.issues[0].blocking is True
    assert provider.calls == []


def test_generate_episode_summary_llm_provider_error_is_blocking():
    episode = _sample_episode()
    provider = FakeProvider([LLMProviderError("connection failed")])

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is None
    assert result.issues[0].code == "llm-provider-error"
    assert result.issues[0].blocking is True


def test_generate_episode_summary_response_not_json_is_blocking():
    episode = _sample_episode()
    provider = FakeProvider(["not a json response {"])

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is None
    assert result.issues[0].code == "response-not-json"
    assert result.issues[0].blocking is True


def test_generate_episode_summary_response_not_object_is_blocking():
    episode = _sample_episode()
    provider = FakeProvider(["[1, 2, 3]"])

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is None
    assert result.issues[0].code == "response-not-object"
    assert result.issues[0].blocking is True


def test_generate_episode_summary_missing_text_key_is_blocking():
    episode = _sample_episode()
    provider = FakeProvider([json.dumps({"evidenceRefs": []})])

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is None
    assert result.issues[0].code == "missing-text-key"
    assert result.issues[0].blocking is True


def test_generate_episode_summary_blank_text_value_is_blocking():
    episode = _sample_episode()
    provider = FakeProvider([json.dumps({"text": "   ", "evidenceRefs": []})])

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is None
    assert result.issues[0].code == "missing-text-key"


# ----------------------------------------------------------------
# (4) evidenceRefsキー欠落・型不正・要素不正 (非blocking、draftは生成)
# ----------------------------------------------------------------


def test_generate_episode_summary_missing_evidence_refs_key_defaults_to_empty():
    episode = _sample_episode()
    provider = FakeProvider([json.dumps({"text": "あらすじ本文"})])

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is not None
    assert result.draft.evidence_refs == []
    codes = [issue.code for issue in result.issues]
    assert "missing-evidence-refs-key" in codes
    assert all(not issue.blocking for issue in result.issues)


def test_generate_episode_summary_invalid_evidence_refs_type_defaults_to_empty():
    episode = _sample_episode()
    provider = FakeProvider(
        [json.dumps({"text": "あらすじ本文", "evidenceRefs": "not-a-list"})]
    )

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is not None
    assert result.draft.evidence_refs == []
    codes = [issue.code for issue in result.issues]
    assert "invalid-evidence-refs-type" in codes


def test_generate_episode_summary_invalid_evidence_ref_item_is_filtered_out():
    episode = _sample_episode()
    provider = FakeProvider(
        [
            json.dumps(
                {
                    "text": "あらすじ本文",
                    "evidenceRefs": [
                        "EVT_SYNTHETIC_SAMPLE_E01_DLG0001",
                        123,
                        "",
                    ],
                }
            )
        ]
    )

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is not None
    assert result.draft.evidence_refs == ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"]
    codes = [issue.code for issue in result.issues]
    assert codes.count("invalid-evidence-ref-item") == 2


# ----------------------------------------------------------------
# (5) generate_story_summary_draft: end-to-end draft組み立て
# ----------------------------------------------------------------


def _schema():
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _validate(document: dict) -> list[str]:
    errors = sorted(
        Draft7Validator(_schema()).iter_errors(document), key=lambda e: list(e.path)
    )
    return [f"{list(e.path)}: {e.message}" for e in errors]


def test_generate_story_summary_draft_end_to_end_is_schema_valid():
    document = _document(
        "EVT_SYNTHETIC_SAMPLE",
        [
            _sample_episode("EVT_SYNTHETIC_SAMPLE_E01"),
            _sample_episode("EVT_SYNTHETIC_SAMPLE_E02"),
        ],
    )
    provider = FakeProvider(
        [
            _json_response(
                "episode1のあらすじ。", ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"]
            ),
            _json_response(
                "episode2のあらすじ。", ["EVT_SYNTHETIC_SAMPLE_E02_DLG0001"]
            ),
        ]
    )

    # synthesize_story=False: story合成自体を無効化し、episode draft組み立て
    # のみを検証する (story合成のend-to-end検証は(6)/(7)節を参照)。
    result = generate_story_summary_draft(
        document, provider=provider, synthesize_story=False
    )

    assert result.story_id == "EVT_SYNTHETIC_SAMPLE"
    assert result.draft.public_story_id == "PUB_EVT_SYNTHETIC_SAMPLE"
    assert len(result.draft.episode_summaries) == 2
    assert result.draft.story_text is None
    assert result.story_synthesis is None

    document_dict = result.to_document_dict()
    assert document_dict["storySummary"] is None
    assert document_dict["generationStatus"] == "draft"
    assert document_dict["source"]["promptVersion"] == PROMPT_VERSION
    assert _validate(document_dict) == []


def test_generate_story_summary_draft_partial_failure_kept_out_of_episode_summaries():
    failing_episode_id = "EVT_SYNTHETIC_SAMPLE_E02"
    document = _document(
        "EVT_SYNTHETIC_SAMPLE",
        [
            _sample_episode("EVT_SYNTHETIC_SAMPLE_E01"),
            _episode(
                failing_episode_id,
                [_stage_direction_block(f"{failing_episode_id}_STAGE0001")],
            ),
        ],
    )
    provider = FakeProvider(
        [_json_response("episode1のあらすじ。", ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"])]
    )

    result = generate_story_summary_draft(
        document, provider=provider, synthesize_story=False
    )

    assert len(result.draft.episode_summaries) == 1
    assert result.draft.episode_summaries[0].episode_id == "EVT_SYNTHETIC_SAMPLE_E01"
    assert result.has_issues is True
    assert result.total_issue_count == 1
    assert result.draft.notes is not None
    assert failing_episode_id in result.draft.notes

    document_dict = result.to_document_dict()
    assert _validate(document_dict) == []


def test_generate_story_summary_draft_provenance_prompt_version_and_input_refs():
    document = _document("EVT_SYNTHETIC_SAMPLE", [_sample_episode()])
    provider = FakeProvider(
        [_json_response("あらすじ。", ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"])]
    )

    result = generate_story_summary_draft(
        document, provider=provider, synthesize_story=False
    )

    assert result.provenance.prompt_version == PROMPT_VERSION == "episode-summary-v4"
    assert result.provenance.generated_at is not None
    assert result.provenance.input_refs == ["EVT_SYNTHETIC_SAMPLE_E01"]
    assert result.provenance.model_provider == "fake"
    assert result.provenance.model_name == "fake-model"


def test_generate_story_summary_draft_all_episodes_failed_has_no_model_provenance():
    episode_id = "EVT_SYNTHETIC_SAMPLE_E01"
    document = _document(
        "EVT_SYNTHETIC_SAMPLE",
        [_episode(episode_id, [_stage_direction_block(f"{episode_id}_STAGE0001")])],
    )
    provider = FakeProvider([])

    result = generate_story_summary_draft(
        document, provider=provider, synthesize_story=False
    )

    assert result.draft.episode_summaries == []
    assert result.provenance.model_provider is None
    assert result.provenance.model_name is None

    document_dict = result.to_document_dict()
    assert _validate(document_dict) == []


def test_generate_story_summary_draft_no_episodes_is_schema_valid():
    document = _document("EVT_SYNTHETIC_SAMPLE", [])
    provider = FakeProvider([])

    result = generate_story_summary_draft(
        document, provider=provider, synthesize_story=False
    )

    assert result.draft.episode_summaries == []
    assert result.has_issues is False
    document_dict = result.to_document_dict()
    assert _validate(document_dict) == []


# ----------------------------------------------------------------
# (6) synthesize_story_summary: story合成ロジック単体
# ----------------------------------------------------------------


def _story_json_response(text: str) -> str:
    return json.dumps({"text": text}, ensure_ascii=False)


def test_synthesize_story_summary_orders_input_by_episode_number():
    draft_ep2 = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E02", text="episode2の要約", episode_number=2
    )
    draft_ep1 = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01", text="episode1の要約", episode_number=1
    )
    provider = FakeProvider([_story_json_response("story全体のあらすじ")])

    # 呼び出し側が episode_number 降順で渡しても、prompt内ではepisodeNumber
    # 昇順に並べ替えられることを確認する。
    result = synthesize_story_summary([draft_ep2, draft_ep1], provider=provider)

    assert result.story_text == "story全体のあらすじ"
    prompt = provider.calls[0]["prompt"]
    assert prompt.index("[Episode 1] episode1の要約") < prompt.index(
        "[Episode 2] episode2の要約"
    )
    assert provider.calls[0]["system"] is not None
    assert provider.calls[0]["format_json"] is True


def test_synthesize_story_summary_evidence_refs_union_dedup_and_stable_order():
    draft_ep2 = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E02",
        text="episode2の要約",
        evidence_refs=["EVT_E02_DLG0001", "EVT_E01_DLG0001"],
        episode_number=2,
    )
    draft_ep1 = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01",
        text="episode1の要約",
        evidence_refs=["EVT_E01_DLG0001", "EVT_E01_DLG0002"],
        episode_number=1,
    )
    provider = FakeProvider([_story_json_response("story全体のあらすじ")])

    result = synthesize_story_summary([draft_ep2, draft_ep1], provider=provider)

    # episodeNumber順(E01->E02) -> episode内出現順で、重複("EVT_E01_DLG0001")
    # は初出のみ残す。
    assert result.evidence_refs == [
        "EVT_E01_DLG0001",
        "EVT_E01_DLG0002",
        "EVT_E02_DLG0001",
    ]


def test_synthesize_story_summary_no_episode_drafts_is_blocking_and_skips_llm():
    provider = FakeProvider([])

    result = synthesize_story_summary([], provider=provider)

    assert result.story_text is None
    assert result.skipped is True
    assert result.evidence_refs == []
    assert len(result.issues) == 1
    assert result.issues[0].code == "no-episode-summaries"
    assert result.issues[0].blocking is True
    assert provider.calls == []


def test_synthesize_story_summary_input_too_long_is_blocking_and_skips_llm():
    draft = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01",
        text="十分に長い合成episode要約テキストです。" * 3,
        episode_number=1,
    )
    provider = FakeProvider([])

    result = synthesize_story_summary(
        [draft], provider=provider, max_input_characters=5
    )

    assert result.story_text is None
    assert result.issues[0].code == "input-too-long"
    assert result.issues[0].blocking is True
    assert provider.calls == []


def test_synthesize_story_summary_llm_provider_error_is_blocking():
    draft = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01", text="episode要約", episode_number=1
    )
    provider = FakeProvider([LLMProviderError("connection failed")])

    result = synthesize_story_summary([draft], provider=provider)

    assert result.story_text is None
    assert result.issues[0].code == "llm-provider-error"
    assert result.issues[0].blocking is True


def test_synthesize_story_summary_response_not_json_is_blocking():
    draft = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01", text="episode要約", episode_number=1
    )
    provider = FakeProvider(["not a json response {"])

    result = synthesize_story_summary([draft], provider=provider)

    assert result.story_text is None
    assert result.issues[0].code == "response-not-json"
    assert result.issues[0].blocking is True


def test_synthesize_story_summary_missing_text_key_is_blocking():
    draft = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01", text="episode要約", episode_number=1
    )
    provider = FakeProvider([json.dumps({"notText": "oops"})])

    result = synthesize_story_summary([draft], provider=provider)

    assert result.story_text is None
    assert result.issues[0].code == "missing-text-key"
    assert result.issues[0].blocking is True


def test_synthesize_story_summary_blank_text_value_is_blocking():
    draft = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01", text="episode要約", episode_number=1
    )
    provider = FakeProvider([json.dumps({"text": "   "})])

    result = synthesize_story_summary([draft], provider=provider)

    assert result.story_text is None
    assert result.issues[0].code == "missing-text-key"
    assert result.issues[0].blocking is True


def test_synthesize_story_summary_forbidden_text_pattern_is_nonblocking_issue():
    draft = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01", text="episode要約", episode_number=1
    )
    provider = FakeProvider(
        [_story_json_response("story全体のあらすじに$num1という禁止文字列が混入。")]
    )

    result = synthesize_story_summary([draft], provider=provider)

    assert result.story_text is not None
    codes = [issue.code for issue in result.issues]
    assert "forbidden-text-pattern" in codes
    assert all(not issue.blocking for issue in result.issues)


def test_synthesize_story_summary_continues_with_episode_issues_flag():
    draft = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01", text="episode要約", episode_number=1
    )
    provider = FakeProvider([_story_json_response("story全体のあらすじ")])

    result = synthesize_story_summary(
        [draft],
        provider=provider,
        episodes_with_issues=["EVT_SYNTHETIC_SAMPLE_E01"],
    )

    # issueを持つepisodeがあっても合成自体は行う (skipしない)。
    assert result.story_text == "story全体のあらすじ"
    codes = [issue.code for issue in result.issues]
    assert "source-episode-has-issues" in codes
    matching = [i for i in result.issues if i.code == "source-episode-has-issues"]
    assert matching[0].blocking is False


# ----------------------------------------------------------------
# (7) generate_story_summary_draft + story synthesis: end-to-end
# ----------------------------------------------------------------


def test_generate_story_summary_draft_with_synthesis_end_to_end_is_schema_valid():
    document = _document(
        "EVT_SYNTHETIC_SAMPLE",
        [
            _sample_episode("EVT_SYNTHETIC_SAMPLE_E01"),
            _sample_episode("EVT_SYNTHETIC_SAMPLE_E02"),
        ],
    )
    provider = FakeProvider(
        [
            _json_response(
                "episode1のあらすじ。", ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"]
            ),
            _json_response(
                "episode2のあらすじ。", ["EVT_SYNTHETIC_SAMPLE_E02_DLG0001"]
            ),
            _story_json_response("story全体を通したあらすじ。"),
        ]
    )

    # synthesize_storyは既定でTrue (引数省略)。
    result = generate_story_summary_draft(document, provider=provider)

    assert result.story_synthesis is not None
    assert result.story_synthesis.story_text == "story全体を通したあらすじ。"
    assert result.draft.story_text == "story全体を通したあらすじ。"
    assert result.draft.story_evidence_refs == [
        "EVT_SYNTHETIC_SAMPLE_E01_DLG0001",
        "EVT_SYNTHETIC_SAMPLE_E02_DLG0001",
    ]

    document_dict = result.to_document_dict()
    assert document_dict["storySummary"]["text"] == "story全体を通したあらすじ。"
    assert document_dict["storySummary"]["evidenceRefs"] == [
        "EVT_SYNTHETIC_SAMPLE_E01_DLG0001",
        "EVT_SYNTHETIC_SAMPLE_E02_DLG0001",
    ]
    # 既定でstory-summary-v2 (全文直接入力方式) が使われる (合成fixtureの
    # 入力は小さくcontextサイズガードを超えないため)。
    assert (
        document_dict["source"]["promptVersion"]
        == "episode-summary-v4,story-summary-v3"
    )
    assert _validate(document_dict) == []


def test_generate_story_summary_draft_no_story_synthesis_flag_keeps_story_summary_null():  # noqa: E501
    document = _document("EVT_SYNTHETIC_SAMPLE", [_sample_episode()])
    provider = FakeProvider(
        [_json_response("episode1のあらすじ。", ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"])]
    )

    result = generate_story_summary_draft(
        document, provider=provider, synthesize_story=False
    )

    assert result.story_synthesis is None
    assert result.draft.story_text is None
    document_dict = result.to_document_dict()
    assert document_dict["storySummary"] is None
    assert document_dict["source"]["promptVersion"] == "episode-summary-v4"
    assert _validate(document_dict) == []


# ----------------------------------------------------------------
# (8) story-summary-v2: 全文直接入力方式・contextサイズガード
#     (`summary-generation-quality-v2`)
# ----------------------------------------------------------------


def test_synthesize_story_summary_uses_full_text_v2_by_default_when_episodes_given():
    episode_id = "EVT_SYNTHETIC_SAMPLE_E01"
    raw_episode = _episode(
        episode_id,
        [_dialogue_block(f"{episode_id}_DLG0001", "Speaker A", "台詞テキストです。")],
    )
    draft = EpisodeSummaryDraft(
        episode_id=episode_id,
        text="episodeのあらすじ",
        episode_number=1,
        evidence_refs=[f"{episode_id}_DLG0001"],
    )
    provider = FakeProvider([_story_json_response("story全体のあらすじ")])

    result = synthesize_story_summary(
        [draft], provider=provider, episodes=[raw_episode]
    )

    assert result.story_text == "story全体のあらすじ"
    assert result.prompt_version == STORY_SUMMARY_PROMPT_VERSION
    prompt = provider.calls[0]["prompt"]
    assert "=== Episode 1 ===" in prompt
    assert "台詞テキストです。" in prompt
    # v1形式 (Episode Summary再要約) のラベルは使われない。
    assert "[Episode 1] episodeのあらすじ" not in prompt
    assert result.evidence_refs == [f"{episode_id}_DLG0001"]


def test_synthesize_story_summary_falls_back_to_v1_when_context_exceeds_limit():
    episode_id = "EVT_SYNTHETIC_SAMPLE_E01"
    long_text = "十分に長い台詞テキストをここに用意します。" * 3
    raw_episode = _episode(
        episode_id, [_dialogue_block(f"{episode_id}_DLG0001", "Speaker A", long_text)]
    )
    draft = EpisodeSummaryDraft(
        episode_id=episode_id,
        text="episodeのあらすじ",
        episode_number=1,
        evidence_refs=[f"{episode_id}_DLG0001"],
    )
    provider = FakeProvider([_story_json_response("story全体のあらすじ")])

    result = synthesize_story_summary(
        [draft], provider=provider, episodes=[raw_episode], max_context_tokens=1
    )

    assert result.story_text == "story全体のあらすじ"
    assert result.prompt_version == STORY_SUMMARY_PROMPT_VERSION_FALLBACK
    codes = [issue.code for issue in result.issues]
    assert "story-synthesis-context-fallback" in codes
    matching = [
        i for i in result.issues if i.code == "story-synthesis-context-fallback"
    ]
    assert matching[0].blocking is False
    prompt = provider.calls[0]["prompt"]
    assert "[Episode 1] episodeのあらすじ" in prompt
    # evidenceRefsのunion方式はv1/v2いずれでも不変。
    assert result.evidence_refs == [f"{episode_id}_DLG0001"]


def test_synthesize_story_summary_falls_back_to_v1_when_episode_not_found_in_episodes():
    draft = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01",
        text="episodeのあらすじ",
        episode_number=1,
    )
    unrelated_episode = _episode(
        "EVT_OTHER_E01", [_narration_block("EVT_OTHER_E01_NAR0001", "無関係の地の文。")]
    )
    provider = FakeProvider([_story_json_response("story全体のあらすじ")])

    result = synthesize_story_summary(
        [draft], provider=provider, episodes=[unrelated_episode]
    )

    assert result.story_text == "story全体のあらすじ"
    assert result.prompt_version == STORY_SUMMARY_PROMPT_VERSION_FALLBACK
    # 対応episodeが見つからないだけのケースはcontext-fallback issueではない。
    codes = [issue.code for issue in result.issues]
    assert "story-synthesis-context-fallback" not in codes
    prompt = provider.calls[0]["prompt"]
    assert "[Episode 1] episodeのあらすじ" in prompt


def test_synthesize_story_summary_v2_forbidden_text_pattern_is_nonblocking_issue():
    episode_id = "EVT_SYNTHETIC_SAMPLE_E01"
    raw_episode = _episode(
        episode_id, [_narration_block(f"{episode_id}_NAR0001", "地の文テキストです。")]
    )
    draft = EpisodeSummaryDraft(
        episode_id=episode_id, text="episode要約", episode_number=1
    )
    provider = FakeProvider(
        [_story_json_response("story全体のあらすじに$num1という禁止文字列が混入。")]
    )

    result = synthesize_story_summary(
        [draft], provider=provider, episodes=[raw_episode]
    )

    assert result.story_text is not None
    assert result.prompt_version == STORY_SUMMARY_PROMPT_VERSION
    codes = [issue.code for issue in result.issues]
    assert "forbidden-text-pattern" in codes
    assert all(not issue.blocking for issue in result.issues)


# ----------------------------------------------------------------
# (9) 自己推敲パス (`refine`引数、既定OFF、`summary-generation-quality-v2`)
# ----------------------------------------------------------------


def test_generate_episode_summary_refine_true_triggers_second_call_and_replaces_text():
    episode = _sample_episode()
    provider = FakeProvider(
        [
            _json_response("元のあらすじ。", ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"]),
            json.dumps({"text": "推敲後のあらすじ。"}, ensure_ascii=False),
        ]
    )

    result = generate_episode_summary(episode, provider=provider, refine=True)

    assert len(provider.calls) == 2
    assert result.draft is not None
    assert result.draft.text == "推敲後のあらすじ。"
    # evidenceRefsは推敲では変更されない (元の生成結果のまま)。
    assert result.draft.evidence_refs == ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"]


def test_generate_episode_summary_refine_false_by_default_sends_only_one_call():
    episode = _sample_episode()
    provider = FakeProvider([_json_response("あらすじ。", [])])

    result = generate_episode_summary(episode, provider=provider)

    assert len(provider.calls) == 1
    assert result.draft.text == "あらすじ。"


def test_generate_episode_summary_refine_llm_failure_keeps_original_text():
    episode = _sample_episode()
    provider = FakeProvider(
        [
            _json_response("元のあらすじ。", []),
            LLMProviderError("refine failed"),
        ]
    )

    result = generate_episode_summary(episode, provider=provider, refine=True)

    assert result.draft is not None
    assert result.draft.text == "元のあらすじ。"
    codes = [issue.code for issue in result.issues]
    assert "refine-llm-provider-error" in codes
    matching = [i for i in result.issues if i.code == "refine-llm-provider-error"]
    assert matching[0].blocking is False


def test_generate_episode_summary_refine_parse_failure_keeps_original_text():
    episode = _sample_episode()
    provider = FakeProvider(
        [
            _json_response("元のあらすじ。", []),
            "not a json response {",
        ]
    )

    result = generate_episode_summary(episode, provider=provider, refine=True)

    assert result.draft is not None
    assert result.draft.text == "元のあらすじ。"
    codes = [issue.code for issue in result.issues]
    assert "refine-response-not-json" in codes
    matching = [i for i in result.issues if i.code == "refine-response-not-json"]
    assert matching[0].blocking is False


def test_synthesize_story_summary_refine_true_triggers_second_call_and_replaces_text():
    draft = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01", text="episode要約", episode_number=1
    )
    provider = FakeProvider(
        [
            _story_json_response("元のstoryあらすじ"),
            json.dumps({"text": "推敲後のstoryあらすじ"}, ensure_ascii=False),
        ]
    )

    result = synthesize_story_summary([draft], provider=provider, refine=True)

    assert len(provider.calls) == 2
    assert result.story_text == "推敲後のstoryあらすじ"


def test_synthesize_story_summary_refine_failure_keeps_original_text():
    draft = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01", text="episode要約", episode_number=1
    )
    provider = FakeProvider(
        [
            _story_json_response("元のstoryあらすじ"),
            LLMProviderError("refine failed"),
        ]
    )

    result = synthesize_story_summary([draft], provider=provider, refine=True)

    assert result.story_text == "元のstoryあらすじ"
    codes = [issue.code for issue in result.issues]
    assert "refine-llm-provider-error" in codes


def test_generate_story_summary_draft_refine_true_appends_prompt_version_suffix():
    document = _document("EVT_SYNTHETIC_SAMPLE", [_sample_episode()])
    provider = FakeProvider(
        [
            _json_response("episodeのあらすじ。", ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"]),
            json.dumps({"text": "推敲後のepisodeあらすじ。"}, ensure_ascii=False),
            _story_json_response("story全体のあらすじ。"),
            json.dumps({"text": "推敲後のstoryあらすじ。"}, ensure_ascii=False),
        ]
    )

    result = generate_story_summary_draft(document, provider=provider, refine=True)

    assert result.draft.episode_summaries[0].text == "推敲後のepisodeあらすじ。"
    assert result.draft.story_text == "推敲後のstoryあらすじ。"
    assert result.provenance.prompt_version == (
        f"{PROMPT_VERSION},{STORY_SUMMARY_PROMPT_VERSION},"
        f"{REFINE_PROMPT_VERSION_SUFFIX}"
    )
    document_dict = result.to_document_dict()
    assert _validate(document_dict) == []


def test_generate_story_summary_draft_refine_false_by_default_omits_suffix():
    document = _document("EVT_SYNTHETIC_SAMPLE", [_sample_episode()])
    provider = FakeProvider(
        [
            _json_response("episodeのあらすじ。", ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"]),
            _story_json_response("story全体のあらすじ。"),
        ]
    )

    result = generate_story_summary_draft(document, provider=provider)

    assert REFINE_PROMPT_VERSION_SUFFIX not in result.provenance.prompt_version


# ----------------------------------------------------------------
# (10) domain context注入 (`summary-domain-context-injection`)
# ----------------------------------------------------------------

_SYNTHETIC_DOMAIN_CONTEXT = ["合成用ドメイン前提テキスト"]


def test_generate_episode_summary_domain_context_none_leaves_system_prompt_unchanged():
    episode = _sample_episode()
    provider = FakeProvider([_json_response("あらすじ。", [])])

    generate_episode_summary(episode, provider=provider)

    assert _SYNTHETIC_DOMAIN_CONTEXT[0] not in provider.calls[0]["system"]


def test_generate_episode_summary_domain_context_injected_into_system_prompt():
    episode = _sample_episode()
    provider = FakeProvider([_json_response("あらすじ。", [])])

    generate_episode_summary(
        episode, provider=provider, domain_context=_SYNTHETIC_DOMAIN_CONTEXT
    )

    assert _SYNTHETIC_DOMAIN_CONTEXT[0] in provider.calls[0]["system"]


def test_generate_story_summary_draft_domain_context_appends_provenance_marker():
    document = _document("EVT_SYNTHETIC_SAMPLE", [_sample_episode()])
    provider = FakeProvider(
        [
            _json_response("episodeのあらすじ。", ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"]),
            _story_json_response("story全体のあらすじ。"),
        ]
    )

    result = generate_story_summary_draft(
        document, provider=provider, domain_context=_SYNTHETIC_DOMAIN_CONTEXT
    )

    assert DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX in result.provenance.prompt_version
    # episode/story合成いずれのsystem promptにも注入されること。
    assert all(
        _SYNTHETIC_DOMAIN_CONTEXT[0] in call["system"] for call in provider.calls
    )


def test_generate_story_summary_draft_no_domain_context_omits_provenance_marker():
    document = _document("EVT_SYNTHETIC_SAMPLE", [_sample_episode()])
    provider = FakeProvider(
        [
            _json_response("episodeのあらすじ。", ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"]),
            _story_json_response("story全体のあらすじ。"),
        ]
    )

    result = generate_story_summary_draft(document, provider=provider)

    assert DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX not in result.provenance.prompt_version


def test_generate_story_summary_draft_empty_domain_context_omits_provenance_marker():
    # 空リストはNoneと同様に「注入なし」として扱われる (bool([]) is False)。
    document = _document("EVT_SYNTHETIC_SAMPLE", [_sample_episode()])
    provider = FakeProvider(
        [_json_response("episodeのあらすじ。", ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"])]
    )

    result = generate_story_summary_draft(
        document, provider=provider, synthesize_story=False, domain_context=[]
    )

    assert DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX not in result.provenance.prompt_version


# ----------------------------------------------------------------
# (11) 本文中evidence ID引用の機械的除去 (`summary-domain-context-
#      injection`、防御の二重化)
# ----------------------------------------------------------------


def test_strip_evidence_id_citations_removes_bracketed_id_and_counts():
    text = "半裸になったのは班長（EVT_E01_DLG0001）。"
    stripped, count = strip_evidence_id_citations(text)
    assert count == 1
    assert "EVT_E01_DLG0001" not in stripped
    assert "半裸になったのは班長" in stripped


def test_strip_evidence_id_citations_no_match_returns_original():
    text = "括弧書き引用が無い普通のあらすじ文です。"
    stripped, count = strip_evidence_id_citations(text)
    assert count == 0
    assert stripped == text


def test_generate_episode_summary_strips_bracketed_citation_and_records_issue():
    episode = _sample_episode()
    provider = FakeProvider(
        [
            _json_response(
                "半裸になったのは班長（EVT_SYNTHETIC_SAMPLE_E01_DLG0001）。",
                ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"],
            )
        ]
    )

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is not None
    assert "EVT_SYNTHETIC_SAMPLE_E01_DLG0001" not in result.draft.text
    assert result.draft.text == "半裸になったのは班長。"
    codes = [issue.code for issue in result.issues]
    assert "evidence-id-citation-stripped" in codes
    matching = [i for i in result.issues if i.code == "evidence-id-citation-stripped"]
    assert matching[0].blocking is False


def test_generate_episode_summary_no_citation_does_not_record_strip_issue():
    episode = _sample_episode()
    provider = FakeProvider([_json_response("括弧書き引用の無いあらすじ。", [])])

    result = generate_episode_summary(episode, provider=provider)

    codes = [issue.code for issue in result.issues]
    assert "evidence-id-citation-stripped" not in codes


def test_synthesize_story_summary_v2_strips_bracketed_citation():
    episode_id = "EVT_SYNTHETIC_SAMPLE_E01"
    raw_episode = _episode(
        episode_id, [_narration_block(f"{episode_id}_NAR0001", "地の文テキストです。")]
    )
    draft = EpisodeSummaryDraft(
        episode_id=episode_id, text="episode要約", episode_number=1
    )
    provider = FakeProvider(
        [_story_json_response(f"半裸になったのは班長（{episode_id}_NAR0001）。")]
    )

    result = synthesize_story_summary(
        [draft], provider=provider, episodes=[raw_episode]
    )

    assert result.story_text == "半裸になったのは班長。"
    codes = [issue.code for issue in result.issues]
    assert "evidence-id-citation-stripped" in codes


def test_strip_would_empty_text_keeps_original_and_records_issue():
    episode = _sample_episode()
    # あらすじ全体が括弧書き引用のみで構成される極端なケース。
    provider = FakeProvider(
        [_json_response("（EVT_SYNTHETIC_SAMPLE_E01_DLG0001）", [])]
    )

    result = generate_episode_summary(episode, provider=provider)

    assert result.draft is not None
    assert result.draft.text == "（EVT_SYNTHETIC_SAMPLE_E01_DLG0001）"
    codes = [issue.code for issue in result.issues]
    assert "evidence-id-citation-strip-would-empty-text" in codes


if __name__ == "__main__":
    pytest.main([__file__])
