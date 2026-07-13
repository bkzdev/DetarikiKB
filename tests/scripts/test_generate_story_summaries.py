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


def _episode(episode_id: str, blocks: list[dict]) -> dict:
    return {
        "episodeId": episode_id,
        "episodeNumber": 1,
        "metadata": {"publicEpisodeId": f"PUB_{episode_id}"},
        "scenes": [
            {"sceneId": f"{episode_id}_SC001", "sceneNumber": 1, "blocks": blocks}
        ],
    }


def _sample_episode(episode_id: str = "EVT_CLI_SAMPLE_E01") -> dict:
    return _episode(
        episode_id,
        [
            _dialogue_block(f"{episode_id}_DLG0001", "Speaker A", "台詞テキストです。"),
            _narration_block(f"{episode_id}_NAR0001", "地の文テキストです。"),
        ],
    )


def _document(story_id: str, episodes: list[dict]) -> dict:
    return {
        "schemaVersion": "0.2",
        "documentType": "normalized_story",
        "storyId": story_id,
        "storyCategory": "EVT",
        "metadata": {"publicStoryId": f"PUB_{story_id}"},
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


if __name__ == "__main__":
    pytest.main([__file__])
