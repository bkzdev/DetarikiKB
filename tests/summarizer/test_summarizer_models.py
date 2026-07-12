"""
tests/summarizer/test_summarizer_models.py
agents/summarizer/models.py の最小skeleton (LLM呼び出しなし) のテスト。

合成fixtureのみを使う。実イベント名・実キャラ名・実あらすじ・実セリフは
一切含まない (docs/architecture/06_AI/Story_Summary_Design.md参照)。
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

from agents.summarizer import (
    DOCUMENT_TYPE,
    DRAFT_GENERATION_STATUS,
    DRAFT_LANGUAGE,
    DRAFT_REVIEW_STATUS,
    DRAFT_SOURCE_TYPE,
    SCHEMA_VERSION,
    EpisodeSummaryDraft,
    StorySummaryDraft,
    SummaryProvenance,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "story_summary.schema.json"


def _load_schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _validate(document: dict) -> list[str]:
    errors = sorted(
        Draft7Validator(_load_schema()).iter_errors(document),
        key=lambda e: list(e.path),
    )
    return [f"{list(e.path)}: {e.message}" for e in errors]


# ----------------------------------------------------------------
# (1) dataclass構築とdefault値
# ----------------------------------------------------------------


def test_episode_summary_draft_requires_episode_id_and_text():
    draft = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01", text="合成テキスト"
    )
    assert draft.episode_id == "EVT_SYNTHETIC_SAMPLE_E01"
    assert draft.text == "合成テキスト"


def test_episode_summary_draft_defaults():
    draft = EpisodeSummaryDraft(
        episode_id="EVT_SYNTHETIC_SAMPLE_E01", text="合成テキスト"
    )
    assert draft.evidence_refs == []
    assert draft.confidence is None
    assert draft.public_episode_id is None
    assert draft.episode_number is None


def test_episode_summary_draft_default_evidence_refs_are_independent_instances():
    # dataclass default_factoryが正しく機能し、複数インスタンス間でlistが
    # 共有されないことを確認する (mutable default trapの回避確認)。
    draft_a = EpisodeSummaryDraft(episode_id="EVT_A_E01", text="A")
    draft_b = EpisodeSummaryDraft(episode_id="EVT_B_E01", text="B")
    draft_a.evidence_refs.append("EVT_A_E01_DLG0001")
    assert draft_b.evidence_refs == []


def test_story_summary_draft_requires_story_id():
    draft = StorySummaryDraft(story_id="EVT_SYNTHETIC_SAMPLE")
    assert draft.story_id == "EVT_SYNTHETIC_SAMPLE"


def test_story_summary_draft_defaults():
    draft = StorySummaryDraft(story_id="EVT_SYNTHETIC_SAMPLE")
    assert draft.public_story_id is None
    assert draft.language == "ja"
    assert draft.story_text is None
    assert draft.story_evidence_refs == []
    assert draft.episode_summaries == []
    assert draft.notes is None


def test_draft_language_default_matches_module_constant():
    draft = StorySummaryDraft(story_id="EVT_SYNTHETIC_SAMPLE")
    assert draft.language == DRAFT_LANGUAGE == "ja"


def test_summary_provenance_defaults():
    provenance = SummaryProvenance()
    assert provenance.model_provider is None
    assert provenance.model_name is None
    assert provenance.prompt_version is None
    assert provenance.generated_at is None
    assert provenance.input_refs == []


def test_summary_provenance_model_label_combines_provider_and_name():
    provenance = SummaryProvenance(model_provider="ollama", model_name="llama3")
    assert provenance.model_label() == "ollama/llama3"


def test_summary_provenance_model_label_falls_back_to_single_value():
    assert SummaryProvenance(model_name="llama3").model_label() == "llama3"
    assert SummaryProvenance(model_provider="ollama").model_label() == "ollama"
    assert SummaryProvenance().model_label() is None


# ----------------------------------------------------------------
# (2) to_document_dict()がschemas/story_summary.schema.jsonに対してvalid
# ----------------------------------------------------------------


def test_to_document_dict_minimal_draft_is_schema_valid():
    draft = StorySummaryDraft(story_id="EVT_SYNTHETIC_SAMPLE")
    document = draft.to_document_dict(SummaryProvenance())
    assert _validate(document) == []


def test_to_document_dict_full_draft_is_schema_valid():
    draft = StorySummaryDraft(
        story_id="EVT_SYNTHETIC_SAMPLE",
        public_story_id="EVT_260101_001",
        story_text="これは合成のStory Summary draftです。",
        story_evidence_refs=["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"],
        episode_summaries=[
            EpisodeSummaryDraft(
                episode_id="EVT_SYNTHETIC_SAMPLE_E01",
                text="これは合成のEpisode Summary draftです。",
                evidence_refs=["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"],
                confidence=0.6,
                public_episode_id="EVT_260101_001_E01",
                episode_number=1,
            )
        ],
        notes="Synthetic draft entry only.",
    )
    provenance = SummaryProvenance(
        model_provider="ollama",
        model_name="llama3",
        prompt_version="v0",
        generated_at="2026-07-13T00:00:00Z",
        input_refs=["EVT_SYNTHETIC_SAMPLE_E01"],
    )
    document = draft.to_document_dict(provenance)
    assert _validate(document) == []


def test_to_document_dict_sets_draft_status_fields():
    draft = StorySummaryDraft(story_id="EVT_SYNTHETIC_SAMPLE")
    document = draft.to_document_dict(SummaryProvenance())

    assert document["schemaVersion"] == SCHEMA_VERSION
    assert document["documentType"] == DOCUMENT_TYPE == "story_summary"
    assert document["generationStatus"] == DRAFT_GENERATION_STATUS == "draft"
    assert document["source"]["sourceType"] == DRAFT_SOURCE_TYPE == "ai_generated"
    assert document["review"]["status"] == DRAFT_REVIEW_STATUS == "unreviewed"
    assert document["language"] == "ja"


def test_to_document_dict_combines_provenance_model_fields():
    draft = StorySummaryDraft(story_id="EVT_SYNTHETIC_SAMPLE")
    provenance = SummaryProvenance(model_provider="ollama", model_name="llama3")
    document = draft.to_document_dict(provenance)
    assert document["source"]["model"] == "ollama/llama3"


def test_to_document_dict_episode_summary_entry_fields():
    draft = StorySummaryDraft(
        story_id="EVT_SYNTHETIC_SAMPLE",
        episode_summaries=[
            EpisodeSummaryDraft(
                episode_id="EVT_SYNTHETIC_SAMPLE_E01",
                text="合成テキスト",
                evidence_refs=["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"],
                confidence=0.5,
                public_episode_id="PUB_E01",
                episode_number=1,
            )
        ],
    )
    document = draft.to_document_dict(SummaryProvenance())
    entry = document["episodeSummaries"][0]

    assert entry["episodeId"] == "EVT_SYNTHETIC_SAMPLE_E01"
    assert entry["publicEpisodeId"] == "PUB_E01"
    assert entry["episodeNumber"] == 1
    assert entry["text"] == "合成テキスト"
    assert entry["confidence"] == 0.5
    assert entry["evidenceRefs"] == ["EVT_SYNTHETIC_SAMPLE_E01_DLG0001"]


# ----------------------------------------------------------------
# (3) 境界ケース: episodeSummaries空配列・story_text無し
# ----------------------------------------------------------------


def test_to_document_dict_with_no_story_text_has_null_story_summary():
    draft = StorySummaryDraft(story_id="EVT_SYNTHETIC_SAMPLE", story_text=None)
    document = draft.to_document_dict(SummaryProvenance())
    assert document["storySummary"] is None
    assert _validate(document) == []


def test_to_document_dict_with_empty_episode_summaries_is_valid():
    draft = StorySummaryDraft(
        story_id="EVT_SYNTHETIC_SAMPLE",
        story_text="Story Summaryのみ先に生成されるケース。",
        episode_summaries=[],
    )
    document = draft.to_document_dict(SummaryProvenance())
    assert document["episodeSummaries"] == []
    assert _validate(document) == []


def test_to_document_dict_with_story_text_and_no_evidence_refs_is_valid():
    # story_evidence_refsを指定しなくても (空list) schemaはPASSする
    # (evidenceRefsは必須ではない、Story_Summary_Design.md §9)。
    draft = StorySummaryDraft(
        story_id="EVT_SYNTHETIC_SAMPLE",
        story_text="根拠refsが空の合成Story Summary draftです。",
    )
    document = draft.to_document_dict(SummaryProvenance())
    assert document["storySummary"]["evidenceRefs"] == []
    assert _validate(document) == []


def test_to_document_dict_with_neither_story_text_nor_episodes_is_valid():
    # 完全に空のdraft (未着手の初期状態相当) でもschema上はvalid。
    draft = StorySummaryDraft(story_id="EVT_SYNTHETIC_SAMPLE")
    document = draft.to_document_dict(SummaryProvenance())
    assert document["storySummary"] is None
    assert document["episodeSummaries"] == []
    assert _validate(document) == []
