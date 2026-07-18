"""
tests/scripts/test_generate_story_summaries.py
scripts/generate_story_summaries.py のCLIテスト。

Normalized Story JSON (合成fixture) からEpisode Summary draft、および
(既定で) Episode Summary群から合成したStory Summaryを生成するCLIを検証する。
**実Ollamaへのネットワーク呼び出しは一切行わない**。
config error系 (--input/--schema欠落、--output/--reportのknowledge/配下
拒否) はsubprocess経由 (provider構築前にexitするため安全)、実際の生成系は
importlib経由でモジュールをin-processロードし、`main(argv,
provider_factory=...)`にfake providerを注入して検証する
(`agents.summarizer.provider.OllamaProvider`は一切構築・呼び出ししない)。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "generate_story_summaries.py"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "story_summary.schema.json"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_story_summaries", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module() -> ModuleType:
    return _load_module()


def _run_cli(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *extra_args],
        capture_output=True,
        text=True,
    )


# ----------------------------------------------------------------
# synthetic Normalized Story JSON builders (合成fixture、実データ不使用)
# ----------------------------------------------------------------


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


def _episode(
    episode_id: str, blocks: list[dict], *, episode_number: int | None = 1
) -> dict:
    episode: dict = {
        "episodeId": episode_id,
        "episodeNumber": episode_number,
        "metadata": {"publicEpisodeId": f"PUB_{episode_id}"},
        "scenes": [
            {"sceneId": f"{episode_id}_SC001", "sceneNumber": 1, "blocks": blocks}
        ],
    }
    return episode


def _sample_episode(episode_id: str = "EVT_CLI_SAMPLE_E01") -> dict:
    return _episode(
        episode_id,
        [
            _dialogue_block(f"{episode_id}_DLG0001", "Speaker A", "台詞テキストです。"),
            _narration_block(f"{episode_id}_NAR0001", "地の文テキストです。"),
        ],
    )


def _document(
    story_id: str, episodes: list[dict], *, public_story_id: str | None = None
) -> dict:
    return {
        "schemaVersion": "0.2",
        "documentType": "normalized_story",
        "storyId": story_id,
        "storyCategory": "EVT",
        "metadata": {"publicStoryId": public_story_id or f"PUB_{story_id}"},
        "parser": {
            "parserName": "DKB Story Parser",
            "parserVersion": "0.2.0",
            "parserMode": "game_script",
            "preserveStageDirections": True,
        },
        "source": {"sourceFile": "synthetic_cli_story", "sourceFormat": "game_script"},
        "episodes": episodes,
    }


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _json_response(text: str, evidence_refs: list[str] | None = None) -> str:
    payload: dict = {"text": text}
    if evidence_refs is not None:
        payload["evidenceRefs"] = evidence_refs
    return json.dumps(payload, ensure_ascii=False)


class _FakeProvider:
    """呼び出しごとにキューから応答を1件ずつ返すfake provider。"""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def generate(self, prompt, *, system=None, format_json=False):
        from agents.summarizer.provider import LLMCompletion

        self.calls.append(
            {"prompt": prompt, "system": system, "format_json": format_json}
        )
        return LLMCompletion(
            text=self._responses.pop(0), model_name="fake-model", provider_name="fake"
        )


def _validate_schema(document: dict) -> list[str]:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    errors = sorted(
        Draft7Validator(schema).iter_errors(document), key=lambda e: list(e.path)
    )
    return [f"{list(e.path)}: {e.message}" for e in errors]


# ----------------------------------------------------------------
# (1) config error系: --output/--reportのknowledge/配下拒否、
#     --input/--schema欠落 (subprocess経由、provider構築前にexit)
# ----------------------------------------------------------------


def test_cli_rejects_output_under_knowledge_dir(tmp_path: Path):
    input_path = _write_json(
        tmp_path / "story.json", _document("EVT_CLI_SAMPLE", [_sample_episode()])
    )
    forbidden_output = (
        PROJECT_ROOT / "knowledge" / "summaries" / "stories" / "__test_tmp__"
    )
    report_path = tmp_path / "report.md"

    result = _run_cli(
        "--input",
        str(input_path),
        "--output",
        str(forbidden_output),
        "--model",
        "unused-model",
        "--report",
        str(report_path),
    )

    assert result.returncode == 2
    assert "knowledge" in result.stderr
    assert not forbidden_output.exists()


def test_cli_rejects_report_under_knowledge_dir(tmp_path: Path):
    input_path = _write_json(
        tmp_path / "story.json", _document("EVT_CLI_SAMPLE", [_sample_episode()])
    )
    output_dir = tmp_path / "drafts"
    forbidden_report = PROJECT_ROOT / "knowledge" / "__test_tmp_report__.md"

    result = _run_cli(
        "--input",
        str(input_path),
        "--output",
        str(output_dir),
        "--model",
        "unused-model",
        "--report",
        str(forbidden_report),
    )

    assert result.returncode == 2
    assert "knowledge" in result.stderr
    assert not forbidden_report.exists()


def test_cli_missing_input_path_returns_2(tmp_path: Path):
    result = _run_cli(
        "--input",
        str(tmp_path / "does_not_exist.json"),
        "--output",
        str(tmp_path / "drafts"),
        "--model",
        "unused-model",
        "--report",
        str(tmp_path / "report.md"),
    )
    assert result.returncode == 2


def test_cli_missing_schema_path_returns_2(tmp_path: Path):
    input_path = _write_json(
        tmp_path / "story.json", _document("EVT_CLI_SAMPLE", [_sample_episode()])
    )
    result = _run_cli(
        "--input",
        str(input_path),
        "--output",
        str(tmp_path / "drafts"),
        "--model",
        "unused-model",
        "--report",
        str(tmp_path / "report.md"),
        "--schema",
        str(tmp_path / "no_such_schema.json"),
    )
    assert result.returncode == 2


# ----------------------------------------------------------------
# (2) 生成系: in-process + fake providerで検証
# ----------------------------------------------------------------


def test_generate_writes_schema_valid_draft_and_report(
    module: ModuleType, tmp_path: Path
):
    input_path = _write_json(
        tmp_path / "story.json",
        _document("EVT_CLI_SAMPLE", [_sample_episode()]),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    # story合成は既定で有効: episode応答1件 + story合成応答1件を消費する。
    fake_provider = _FakeProvider(
        [
            _json_response(
                "これはCLI合成テストのあらすじです。", ["EVT_CLI_SAMPLE_E01_DLG0001"]
            ),
            json.dumps(
                {"text": "story全体のCLI合成あらすじです。"}, ensure_ascii=False
            ),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    draft_path = output_dir / "EVT_CLI_SAMPLE.yaml"
    assert draft_path.exists()
    with open(draft_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert document["generationStatus"] == "draft"
    assert (
        document["episodeSummaries"][0]["text"] == "これはCLI合成テストのあらすじです。"
    )
    # story合成 (既定で有効): storySummaryが埋まり、evidenceRefsはepisode側の
    # 機械的unionになる。
    assert document["storySummary"]["text"] == "story全体のCLI合成あらすじです。"
    assert document["storySummary"]["evidenceRefs"] == ["EVT_CLI_SAMPLE_E01_DLG0001"]
    assert _validate_schema(document) == []

    report_text = report_path.read_text(encoding="utf-8")
    assert "EVT_CLI_SAMPLE" in report_text
    assert "Episodes generated: 1" in report_text
    assert "Story synthesis" in report_text
    assert "Synthesized: True" in report_text


def test_generate_records_hallucination_issues_in_report_and_notes(
    module: ModuleType, tmp_path: Path
):
    input_path = _write_json(
        tmp_path / "story.json",
        _document("EVT_CLI_SAMPLE", [_sample_episode()]),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    fake_provider = _FakeProvider(
        [
            _json_response("$numが混入したあらすじ。", ["EVT_CLI_SAMPLE_E01_DLG9999"]),
            json.dumps({"text": "story全体のあらすじ。"}, ensure_ascii=False),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
        ],
        provider_factory=lambda args: fake_provider,
    )

    # hallucination issueは非blockingなので生成自体は成功する。
    assert exit_code == 0
    report_text = report_path.read_text(encoding="utf-8")
    assert "forbidden-text-pattern" in report_text
    assert "unknown-evidence-ref" in report_text
    # issueを持つepisodeがあってもstory合成自体は行われ、その旨がissueとして
    # 記録される (Plan §11)。
    assert "source-episode-has-issues" in report_text

    draft_path = output_dir / "EVT_CLI_SAMPLE.yaml"
    with open(draft_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert document["episodeSummaries"][0]["text"] == "$numが混入したあらすじ。"
    assert document["storySummary"]["text"] == "story全体のあらすじ。"
    assert _validate_schema(document) == []


def test_generate_no_story_synthesis_flag_keeps_story_summary_null(
    module: ModuleType, tmp_path: Path
):
    input_path = _write_json(
        tmp_path / "story.json",
        _document("EVT_CLI_SAMPLE", [_sample_episode()]),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    # --no-story-synthesis: episode応答1件のみ消費する (story合成呼び出し無し)。
    fake_provider = _FakeProvider(
        [_json_response("あらすじ。", ["EVT_CLI_SAMPLE_E01_DLG0001"])]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
            "--no-story-synthesis",
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    # LLM呼び出しはepisode分の1回のみ (story合成promptは呼ばれない)。
    assert len(fake_provider.calls) == 1
    draft_path = output_dir / "EVT_CLI_SAMPLE.yaml"
    with open(draft_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert document["storySummary"] is None
    assert _validate_schema(document) == []

    report_text = report_path.read_text(encoding="utf-8")
    assert "Synthesized: skipped (--no-story-synthesis)" in report_text


def test_generate_refine_flag_triggers_extra_calls_and_records_prompt_version(
    module: ModuleType, tmp_path: Path
):
    input_path = _write_json(
        tmp_path / "story.json",
        _document("EVT_CLI_SAMPLE", [_sample_episode()]),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    # --refine: episode生成+推敲、story合成+推敲の計4回消費する。
    fake_provider = _FakeProvider(
        [
            _json_response(
                "これはCLI合成テストのあらすじです。", ["EVT_CLI_SAMPLE_E01_DLG0001"]
            ),
            json.dumps({"text": "推敲後のepisodeあらすじです。"}, ensure_ascii=False),
            json.dumps(
                {"text": "story全体のCLI合成あらすじです。"}, ensure_ascii=False
            ),
            json.dumps({"text": "推敲後のstoryあらすじです。"}, ensure_ascii=False),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
            "--refine",
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    assert len(fake_provider.calls) == 4
    draft_path = output_dir / "EVT_CLI_SAMPLE.yaml"
    with open(draft_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert document["episodeSummaries"][0]["text"] == "推敲後のepisodeあらすじです。"
    assert document["storySummary"]["text"] == "推敲後のstoryあらすじです。"
    assert document["source"]["promptVersion"].endswith(",refine-v1")
    assert _validate_schema(document) == []


def test_generate_story_synthesis_max_context_tokens_forces_fallback(
    module: ModuleType, tmp_path: Path
):
    input_path = _write_json(
        tmp_path / "story.json",
        _document("EVT_CLI_SAMPLE", [_sample_episode()]),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    fake_provider = _FakeProvider(
        [
            _json_response(
                "これはCLI合成テストのあらすじです。", ["EVT_CLI_SAMPLE_E01_DLG0001"]
            ),
            json.dumps(
                {"text": "story全体のCLI合成あらすじです。"}, ensure_ascii=False
            ),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
            "--story-synthesis-max-context-tokens",
            "1",
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    # story合成promptがv1形式 (Episode Summary再要約) にフォールバックする。
    story_prompt = fake_provider.calls[-1]["prompt"]
    assert "[Episode 1] これはCLI合成テストのあらすじです。" in story_prompt

    report_text = report_path.read_text(encoding="utf-8")
    assert "story-synthesis-context-fallback" in report_text
    assert "story-summary-v1-fallback" in report_text


def test_generate_story_synthesis_skip_recorded_when_no_episode_summaries(
    module: ModuleType, tmp_path: Path
):
    # 入力Blockが無いepisodeのみ -> Episode Summaryが0件 -> story合成は
    # no-episode-summariesでskipされ、reportに記録される。
    episode_id = "EVT_CLI_SAMPLE_E01"
    input_path = _write_json(
        tmp_path / "story.json",
        _document(
            "EVT_CLI_SAMPLE",
            [_episode(episode_id, [_stage_direction_block(f"{episode_id}_STAGE0001")])],
        ),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    fake_provider = _FakeProvider([])

    exit_code = module.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    assert fake_provider.calls == []
    draft_path = output_dir / "EVT_CLI_SAMPLE.yaml"
    with open(draft_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert document["storySummary"] is None
    assert _validate_schema(document) == []

    report_text = report_path.read_text(encoding="utf-8")
    assert "Synthesized: False" in report_text
    assert "no-episode-summaries" in report_text


def test_generate_clean_removes_existing_output_files(
    module: ModuleType, tmp_path: Path
):
    input_path = _write_json(
        tmp_path / "story.json",
        _document("EVT_CLI_SAMPLE", [_sample_episode()]),
    )
    output_dir = tmp_path / "drafts"
    output_dir.mkdir(parents=True)
    stale_file = output_dir / "stale_leftover.yaml"
    stale_file.write_text("leftover: true\n", encoding="utf-8")
    report_path = tmp_path / "report.md"
    fake_provider = _FakeProvider(
        [
            _json_response("あらすじ。", ["EVT_CLI_SAMPLE_E01_DLG0001"]),
            json.dumps({"text": "story全体のあらすじ。"}, ensure_ascii=False),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
            "--clean",
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    assert not stale_file.exists()
    assert (output_dir / "EVT_CLI_SAMPLE.yaml").exists()


def test_generate_all_input_load_errors_returns_2(module: ModuleType, tmp_path: Path):
    invalid_input = tmp_path / "broken.json"
    invalid_input.write_text("{not valid json", encoding="utf-8")

    exit_code = module.main(
        [
            "--input",
            str(invalid_input),
            "--output",
            str(tmp_path / "drafts"),
            "--model",
            "unused-model",
            "--report",
            str(tmp_path / "report.md"),
        ],
        provider_factory=lambda args: _FakeProvider([]),
    )

    assert exit_code == 2


def test_generate_partial_load_errors_warns_and_continues(
    module: ModuleType, tmp_path: Path, capsys
):
    input_dir = tmp_path / "inputs"
    _write_json(
        input_dir / "valid.json", _document("EVT_CLI_SAMPLE", [_sample_episode()])
    )
    (input_dir / "broken.json").write_text("{not valid json", encoding="utf-8")
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    fake_provider = _FakeProvider(
        [
            _json_response("あらすじ。", ["EVT_CLI_SAMPLE_E01_DLG0001"]),
            json.dumps({"text": "story全体のあらすじ。"}, ensure_ascii=False),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "警告" in captured.err
    assert (output_dir / "EVT_CLI_SAMPLE.yaml").exists()


def test_generate_invalid_story_id_fails_schema_validation_returns_1(
    module: ModuleType, tmp_path: Path
):
    # story_summary.schema.jsonのstoryIdパターン (^[A-Z][A-Z0-9_]*$) に
    # 違反する小文字storyIdを与え、schema検証失敗 (exit code 1) を確認する。
    input_path = _write_json(
        tmp_path / "story.json",
        _document(
            "evt_lowercase_invalid", [_sample_episode("evt_lowercase_invalid_E01")]
        ),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    fake_provider = _FakeProvider(
        [
            _json_response("あらすじ。", []),
            json.dumps({"text": "story全体のあらすじ。"}, ensure_ascii=False),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_path),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 1
    assert not (output_dir / "evt_lowercase_invalid.yaml").exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "schemaValid: false" in report_text


def test_default_provider_factory_builds_ollama_provider(module: ModuleType):
    from agents.summarizer.provider import OllamaProvider

    args = module.parse_args(
        [
            "--input",
            "unused",
            "--output",
            "unused",
            "--model",
            "llama3",
            "--report",
            "unused",
            "--host",
            "http://example:11434",
        ]
    )
    provider = module._default_provider_factory(args)
    assert isinstance(provider, OllamaProvider)
    assert provider.model == "llama3"
    assert provider.host == "http://example:11434"


# ----------------------------------------------------------------
# (3) storyId単位のグルーピング (PoC実施中に発見されたバグの修正、
#     summary-generation-multi-episode-grouping)
#
# Phase 1 parserは1 episode 1ファイルのため、複数episodeを持つstoryは
# 複数のNormalized Story JSONファイルに分かれる。以前はファイルごとに
# 別story documentとして処理され、同じ`{storyId}.yaml`へ順に書き出す
# ため、後のepisodeのdraftが前のepisodeのdraftを黙って上書きしていた。
# ----------------------------------------------------------------


def test_generate_groups_same_story_id_files_into_one_draft(
    module: ModuleType, tmp_path: Path
):
    story_id = "EVT_MULTI_EP"
    ep1_id = f"{story_id}_E01"
    ep2_id = f"{story_id}_E02"
    input_dir = tmp_path / "inputs"
    _write_json(
        input_dir / "ep1.json",
        _document(
            story_id,
            [
                _episode(
                    ep1_id,
                    [
                        _dialogue_block(
                            f"{ep1_id}_DLG0001", "Speaker A", "第1話の台詞。"
                        )
                    ],
                    episode_number=1,
                )
            ],
        ),
    )
    _write_json(
        input_dir / "ep2.json",
        _document(
            story_id,
            [
                _episode(
                    ep2_id,
                    [
                        _dialogue_block(
                            f"{ep2_id}_DLG0001", "Speaker B", "第2話の台詞。"
                        )
                    ],
                    episode_number=2,
                )
            ],
        ),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    # storyId単位でグルーピングされ1 story documentとして処理される:
    # episode応答2件 (episodeNumber順) + story合成応答1件。
    fake_provider = _FakeProvider(
        [
            _json_response("第1話のあらすじ。", [f"{ep1_id}_DLG0001"]),
            _json_response("第2話のあらすじ。", [f"{ep2_id}_DLG0001"]),
            json.dumps({"text": "story全体のあらすじ。"}, ensure_ascii=False),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    # 2ファイルとも同一storyId -> 1 draftファイルのみに統合される
    # (以前は後発episodeのdraftが先発episodeのdraftを黙って上書きしていた)。
    draft_files = sorted(output_dir.glob("*.yaml"))
    assert len(draft_files) == 1
    assert draft_files[0].name == f"{story_id}.yaml"

    with open(draft_files[0], encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert _validate_schema(document) == []
    assert len(document["episodeSummaries"]) == 2
    assert document["episodeSummaries"][0]["episodeId"] == ep1_id
    assert document["episodeSummaries"][0]["text"] == "第1話のあらすじ。"
    assert document["episodeSummaries"][1]["episodeId"] == ep2_id
    assert document["episodeSummaries"][1]["text"] == "第2話のあらすじ。"
    assert document["storySummary"]["text"] == "story全体のあらすじ。"

    report_text = report_path.read_text(encoding="utf-8")
    assert "Story count: 1" in report_text
    assert "Episode count: 2" in report_text


def test_generate_episode_order_fallback_to_episode_id_when_no_number(
    module: ModuleType, tmp_path: Path
):
    story_id = "EVT_MULTI_NONUM"
    ep_a = f"{story_id}_E01"  # episodeId辞書順ではep_aが先
    ep_b = f"{story_id}_E02"
    input_dir = tmp_path / "inputs"
    # わざとepisodeNumberを与えず (fallback発火)、ファイル書き込み順序を
    # episodeIdの辞書順とは逆にする (E02を先に書く)。
    _write_json(
        input_dir / "a_first.json",
        _document(
            story_id,
            [
                _episode(
                    ep_b,
                    [_dialogue_block(f"{ep_b}_DLG0001", "Speaker B", "第2話の台詞。")],
                    episode_number=None,
                )
            ],
        ),
    )
    _write_json(
        input_dir / "b_second.json",
        _document(
            story_id,
            [
                _episode(
                    ep_a,
                    [_dialogue_block(f"{ep_a}_DLG0001", "Speaker A", "第1話の台詞。")],
                    episode_number=None,
                )
            ],
        ),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    fake_provider = _FakeProvider(
        [
            _json_response("第1話のあらすじ。", [f"{ep_a}_DLG0001"]),
            _json_response("第2話のあらすじ。", [f"{ep_b}_DLG0001"]),
            json.dumps({"text": "story全体のあらすじ。"}, ensure_ascii=False),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    draft_path = output_dir / f"{story_id}.yaml"
    with open(draft_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    # episodeNumberが無いため、episodeIdの辞書順 (E01 -> E02) にfallbackする。
    assert document["episodeSummaries"][0]["episodeId"] == ep_a
    assert document["episodeSummaries"][1]["episodeId"] == ep_b


def test_generate_metadata_conflict_blocks_story_and_returns_1(
    module: ModuleType, tmp_path: Path
):
    story_id = "EVT_CONFLICT"
    input_dir = tmp_path / "inputs"
    _write_json(
        input_dir / "a.json",
        _document(
            story_id,
            [_sample_episode(f"{story_id}_E01")],
            public_story_id="PUB_CONFLICT_A",
        ),
    )
    _write_json(
        input_dir / "b.json",
        _document(
            story_id,
            [_sample_episode(f"{story_id}_E02")],
            public_story_id="PUB_CONFLICT_B",
        ),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    fake_provider = _FakeProvider([])

    exit_code = module.main(
        [
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 1
    # metadata矛盾によりblockされ、LLMは一切呼ばれず、draftも書き出されない。
    assert fake_provider.calls == []
    assert not (output_dir / f"{story_id}.yaml").exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "Metadata Conflicts" in report_text
    assert story_id in report_text
    assert "PUB_CONFLICT_A" in report_text
    assert "PUB_CONFLICT_B" in report_text
    assert "Metadata conflicts (blocked): 1" in report_text


def test_generate_multiple_distinct_story_ids_processed_independently(
    module: ModuleType, tmp_path: Path
):
    story_a = "EVT_MULTI_A"
    story_b = "EVT_MULTI_B"
    input_dir = tmp_path / "inputs"
    _write_json(
        input_dir / "a.json",
        _document(story_a, [_sample_episode(f"{story_a}_E01")]),
    )
    _write_json(
        input_dir / "b.json",
        _document(story_b, [_sample_episode(f"{story_b}_E01")]),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    fake_provider = _FakeProvider(
        [
            _json_response("Aのあらすじ。", [f"{story_a}_E01_DLG0001"]),
            json.dumps({"text": "story Aのあらすじ。"}, ensure_ascii=False),
            _json_response("Bのあらすじ。", [f"{story_b}_E01_DLG0001"]),
            json.dumps({"text": "story Bのあらすじ。"}, ensure_ascii=False),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    assert (output_dir / f"{story_a}.yaml").exists()
    assert (output_dir / f"{story_b}.yaml").exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "Story count: 2" in report_text


def test_generate_report_counts_unique_story_id_with_mixed_grouping(
    module: ModuleType, tmp_path: Path
):
    story_multi = "EVT_MIX_MULTI"
    story_single = "EVT_MIX_SINGLE"
    ep1 = f"{story_multi}_E01"
    ep2 = f"{story_multi}_E02"
    input_dir = tmp_path / "inputs"
    _write_json(
        input_dir / "multi_ep1.json",
        _document(
            story_multi,
            [
                _episode(
                    ep1,
                    [_dialogue_block(f"{ep1}_DLG0001", "Speaker A", "台詞1。")],
                    episode_number=1,
                )
            ],
        ),
    )
    _write_json(
        input_dir / "multi_ep2.json",
        _document(
            story_multi,
            [
                _episode(
                    ep2,
                    [_dialogue_block(f"{ep2}_DLG0001", "Speaker B", "台詞2。")],
                    episode_number=2,
                )
            ],
        ),
    )
    _write_json(
        input_dir / "single.json",
        _document(story_single, [_sample_episode(f"{story_single}_E01")]),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    fake_provider = _FakeProvider(
        [
            _json_response("台詞1のあらすじ。", [f"{ep1}_DLG0001"]),
            _json_response("台詞2のあらすじ。", [f"{ep2}_DLG0001"]),
            json.dumps({"text": "multi storyのあらすじ。"}, ensure_ascii=False),
            _json_response("singleのあらすじ。", [f"{story_single}_E01_DLG0001"]),
            json.dumps({"text": "single storyのあらすじ。"}, ensure_ascii=False),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    draft_files = sorted(p.name for p in output_dir.glob("*.yaml"))
    assert draft_files == [f"{story_multi}.yaml", f"{story_single}.yaml"]
    report_text = report_path.read_text(encoding="utf-8")
    assert "Input files: 3" in report_text
    assert "Story count: 2" in report_text


def test_write_drafts_blocks_duplicate_output_path_defense(
    module: ModuleType, tmp_path: Path
):
    """`_write_drafts`単体の防御策テスト: storyIdグルーピング後は本来
    発生しないはずだが、万一同一story_idの結果が2件渡された場合でも
    2件目を黙って上書きせずblocking errorとして記録することを確認する。
    """
    from agents.summarizer import (
        EpisodeSummaryDraft,
        StorySummaryDraft,
        StorySummaryGenerationResult,
        SummaryProvenance,
    )

    def _minimal_result(story_id: str) -> StorySummaryGenerationResult:
        draft = StorySummaryDraft(
            story_id=story_id,
            episode_summaries=[
                EpisodeSummaryDraft(
                    episode_id=f"{story_id}_E01", text="あらすじ。", evidence_refs=[]
                )
            ],
        )
        provenance = SummaryProvenance(
            model_provider="fake",
            model_name="fake-model",
            prompt_version="episode-summary-v1",
            generated_at="2026-01-01T00:00:00Z",
            input_refs=[],
        )
        return StorySummaryGenerationResult(
            story_id=story_id, draft=draft, provenance=provenance, episode_results=[]
        )

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    output_dir = tmp_path / "drafts"

    results = [_minimal_result("EVT_DUP"), _minimal_result("EVT_DUP")]
    written_paths, schema_issues = module._write_drafts(
        results, schema=schema, output_dir=output_dir, clean=False
    )

    assert len(written_paths) == 1
    assert len(schema_issues) == 1
    assert "2回目の書き込み" in schema_issues[0]
    assert list(output_dir.glob("*.yaml")) == [output_dir / "EVT_DUP.yaml"]


# ----------------------------------------------------------------
# (4) episodeNumberのrenumber
#
# Phase 1 parserは1ファイル1 episodeで、各episodeの`episodeNumber`を常に
# `1`として出力する。そのためstoryId単位マージ後、複数episodeを持つ
# storyでは`episodeNumber`が全episode共通で`1`のまま重複していた
# (`summary-generation-poc`のPoC実施中に発見された2件目のバグ、
# `summary-generation-episode-renumbering`で修正)。
# ----------------------------------------------------------------


def test_generate_renumbers_duplicate_episode_numbers_after_merge(
    module: ModuleType, tmp_path: Path
):
    # Phase 1 parserの実挙動を再現: 各episodeファイルのepisodeNumberは常に1。
    story_id = "EVT_DUP_NUM"
    ep1_id = f"{story_id}_E01"
    ep2_id = f"{story_id}_E02"
    input_dir = tmp_path / "inputs"
    _write_json(
        input_dir / "ep1.json",
        _document(
            story_id,
            [
                _episode(
                    ep1_id,
                    [
                        _dialogue_block(
                            f"{ep1_id}_DLG0001", "Speaker A", "第1話の台詞。"
                        )
                    ],
                    episode_number=1,
                )
            ],
        ),
    )
    _write_json(
        input_dir / "ep2.json",
        _document(
            story_id,
            [
                _episode(
                    ep2_id,
                    [
                        _dialogue_block(
                            f"{ep2_id}_DLG0001", "Speaker B", "第2話の台詞。"
                        )
                    ],
                    episode_number=1,
                )
            ],
        ),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    fake_provider = _FakeProvider(
        [
            _json_response("第1話のあらすじ。", [f"{ep1_id}_DLG0001"]),
            _json_response("第2話のあらすじ。", [f"{ep2_id}_DLG0001"]),
            json.dumps({"text": "story全体のあらすじ。"}, ensure_ascii=False),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    draft_path = output_dir / f"{story_id}.yaml"
    with open(draft_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert _validate_schema(document) == []
    # 重複していたepisodeNumber (1, 1) がソート済み順に1, 2へrenumberされる。
    assert document["episodeSummaries"][0]["episodeId"] == ep1_id
    assert document["episodeSummaries"][0]["episodeNumber"] == 1
    assert document["episodeSummaries"][1]["episodeId"] == ep2_id
    assert document["episodeSummaries"][1]["episodeNumber"] == 2

    # story合成prompt (既定でstory-summary-v2、全文直接入力方式) の
    # episode見出しにもrenumber後の値が反映される (重複した
    # === Episode 1 ===が2つ現れることはない)。
    story_prompt = fake_provider.calls[-1]["prompt"]
    assert "=== Episode 1 ===" in story_prompt
    assert "=== Episode 2 ===" in story_prompt
    assert f"[{ep1_id}_DLG0001] Speaker A: 第1話の台詞。" in story_prompt
    assert f"[{ep2_id}_DLG0001] Speaker B: 第2話の台詞。" in story_prompt
    assert story_prompt.index("=== Episode 1 ===") < story_prompt.index(
        "=== Episode 2 ==="
    )

    report_text = report_path.read_text(encoding="utf-8")
    assert "Episode numbers renumbered (story count): 1" in report_text
    assert story_id in report_text
    assert "Episode numbers renumbered:" in report_text


def test_generate_renumbers_when_episode_number_none_mixed_with_int(
    module: ModuleType, tmp_path: Path
):
    story_id = "EVT_NONE_MIX_NUM"
    ep_a = f"{story_id}_E01"
    ep_b = f"{story_id}_E02"
    input_dir = tmp_path / "inputs"
    _write_json(
        input_dir / "a.json",
        _document(
            story_id,
            [
                _episode(
                    ep_a,
                    [_dialogue_block(f"{ep_a}_DLG0001", "Speaker A", "第1話の台詞。")],
                    episode_number=1,
                )
            ],
        ),
    )
    _write_json(
        input_dir / "b.json",
        _document(
            story_id,
            [
                _episode(
                    ep_b,
                    [_dialogue_block(f"{ep_b}_DLG0001", "Speaker B", "第2話の台詞。")],
                    episode_number=None,
                )
            ],
        ),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    fake_provider = _FakeProvider(
        [
            _json_response("第1話のあらすじ。", [f"{ep_a}_DLG0001"]),
            _json_response("第2話のあらすじ。", [f"{ep_b}_DLG0001"]),
            json.dumps({"text": "story全体のあらすじ。"}, ensure_ascii=False),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    draft_path = output_dir / f"{story_id}.yaml"
    with open(draft_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert _validate_schema(document) == []
    # episodeNumber=1のepisodeがtier0で先頭、Noneのepisodeはtier1(episodeId
    # fallback)へ回る。None混在のため一意な昇順とは判定されずrenumberされる。
    assert document["episodeSummaries"][0]["episodeId"] == ep_a
    assert document["episodeSummaries"][0]["episodeNumber"] == 1
    assert document["episodeSummaries"][1]["episodeId"] == ep_b
    assert document["episodeSummaries"][1]["episodeNumber"] == 2

    report_text = report_path.read_text(encoding="utf-8")
    assert "Episode numbers renumbered (story count): 1" in report_text


def test_generate_keeps_existing_unique_ascending_episode_numbers_with_gaps(
    module: ModuleType, tmp_path: Path
):
    # manifest由来などで既に一意な昇順 (飛び番を含む) の場合は、正しい
    # metadataを上書きせずそのまま維持する (renumberしない)。
    story_id = "EVT_GAP_NUM"
    ep1_id = f"{story_id}_E02"
    ep2_id = f"{story_id}_E05"
    ep3_id = f"{story_id}_E09"
    input_dir = tmp_path / "inputs"
    _write_json(
        input_dir / "ep1.json",
        _document(
            story_id,
            [
                _episode(
                    ep1_id,
                    [
                        _dialogue_block(
                            f"{ep1_id}_DLG0001", "Speaker A", "第2話の台詞。"
                        )
                    ],
                    episode_number=2,
                )
            ],
        ),
    )
    _write_json(
        input_dir / "ep2.json",
        _document(
            story_id,
            [
                _episode(
                    ep2_id,
                    [
                        _dialogue_block(
                            f"{ep2_id}_DLG0001", "Speaker B", "第5話の台詞。"
                        )
                    ],
                    episode_number=5,
                )
            ],
        ),
    )
    _write_json(
        input_dir / "ep3.json",
        _document(
            story_id,
            [
                _episode(
                    ep3_id,
                    [
                        _dialogue_block(
                            f"{ep3_id}_DLG0001", "Speaker C", "第9話の台詞。"
                        )
                    ],
                    episode_number=9,
                )
            ],
        ),
    )
    output_dir = tmp_path / "drafts"
    report_path = tmp_path / "report.md"
    fake_provider = _FakeProvider(
        [
            _json_response("第2話のあらすじ。", [f"{ep1_id}_DLG0001"]),
            _json_response("第5話のあらすじ。", [f"{ep2_id}_DLG0001"]),
            _json_response("第9話のあらすじ。", [f"{ep3_id}_DLG0001"]),
            json.dumps({"text": "story全体のあらすじ。"}, ensure_ascii=False),
        ]
    )

    exit_code = module.main(
        [
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
            "--model",
            "unused-model",
            "--report",
            str(report_path),
        ],
        provider_factory=lambda args: fake_provider,
    )

    assert exit_code == 0
    draft_path = output_dir / f"{story_id}.yaml"
    with open(draft_path, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert _validate_schema(document) == []
    assert [e["episodeNumber"] for e in document["episodeSummaries"]] == [2, 5, 9]

    report_text = report_path.read_text(encoding="utf-8")
    assert "Episode numbers renumbered" not in report_text


if __name__ == "__main__":
    pytest.main([__file__])
