"""
tests/scripts/test_check_story_summary_drafts.py
scripts/check_story_summary_drafts.py のCLIテスト。

AI生成Story/Episode Summary draftがknowledge/summaries/stories/へ昇格可能かを
checkするgatekeeper scriptを検証する。合成データのみを一時ファイルとして
生成して使う。実データ・実データ由来fixtureは一切使わない。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_story_summary_drafts.py"


# ----------------------------------------------------------------
# Fixture builders (合成データのみ)
# ----------------------------------------------------------------


def _minimal_draft(**overrides) -> dict:
    data = {
        "schemaVersion": "0.1.0",
        "documentType": "story_summary",
        "storyId": "EVT_TEST_A",
        "publicStoryId": None,
        "language": "ja",
        "generationStatus": "draft",
        "storySummary": {
            "text": "合成テスト用のStory Summaryです。",
            "confidence": 0.5,
            "evidenceRefs": ["EVT_TEST_A_E01_DLG0001"],
        },
        "episodeSummaries": [
            {
                "episodeId": "EVT_TEST_A_E01",
                "publicEpisodeId": None,
                "episodeNumber": 1,
                "text": "Episode 1のあらすじです。",
                "confidence": 0.5,
                "evidenceRefs": ["EVT_TEST_A_E01_DLG0001"],
            }
        ],
        "source": {
            "sourceType": "ai_generated",
            "model": None,
            "promptVersion": None,
            "generatedAt": None,
            "inputRefs": [],
        },
        "review": {
            "status": "unreviewed",
            "reviewer": None,
            "reviewedAt": None,
            "notes": None,
        },
        "notes": None,
    }
    data.update(overrides)
    return data


def _minimal_dialogue_block(block_id: str, text: str) -> dict:
    return {
        "id": block_id,
        "type": "dialogue",
        "text": text,
        "rawText": None,
        "source": {
            "sourceFile": "test.dec",
            "lineStart": 1,
            "lineEnd": 1,
            "raw": None,
            "parserRule": None,
            "confidence": None,
        },
    }


def _minimal_normalized_story(
    story_id: str, episode_id: str, blocks: list[dict]
) -> dict:
    return {
        "storyId": story_id,
        "episodes": [
            {
                "episodeId": episode_id,
                "episodeNumber": 1,
                "scenes": [
                    {
                        "sceneId": f"{episode_id}_SC001",
                        "sceneNumber": 1,
                        "blocks": blocks,
                    }
                ],
            }
        ],
    }


def _write_yaml(path: Path, data: dict) -> Path:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)
    return path


def _write_json(path: Path, data: dict) -> Path:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def _run_cli(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *extra_args],
        capture_output=True,
        text=True,
    )


# ----------------------------------------------------------------
# Basic pass / config errors
# ----------------------------------------------------------------


def test_valid_draft_passes_without_normalized(tmp_path):
    path = _write_yaml(tmp_path / "draft.yaml", _minimal_draft())
    result = _run_cli("--input", str(path))
    assert result.returncode == 0, result.stderr


def test_missing_input_path_exits_two(tmp_path):
    result = _run_cli("--input", str(tmp_path / "does_not_exist"))
    assert result.returncode == 2


def test_missing_schema_path_exits_two(tmp_path):
    path = _write_yaml(tmp_path / "draft.yaml", _minimal_draft())
    result = _run_cli(
        "--input", str(path), "--schema", str(tmp_path / "does_not_exist.json")
    )
    assert result.returncode == 2


def test_missing_normalized_path_exits_two(tmp_path):
    path = _write_yaml(tmp_path / "draft.yaml", _minimal_draft())
    result = _run_cli(
        "--input", str(path), "--normalized", str(tmp_path / "does_not_exist")
    )
    assert result.returncode == 2


# ----------------------------------------------------------------
# Schema violation
# ----------------------------------------------------------------


def test_schema_violation_fails(tmp_path):
    # storySummary.text は required (minLength 1) -> 空文字はschema違反
    bad = _minimal_draft(
        storySummary={"text": "", "confidence": 0.5, "evidenceRefs": []}
    )
    path = _write_yaml(tmp_path / "bad.yaml", bad)
    result = _run_cli("--input", str(path))
    assert result.returncode == 1
    assert "schema検証" in result.stderr


def test_missing_required_top_level_field_fails(tmp_path):
    bad = _minimal_draft()
    del bad["review"]
    path = _write_yaml(tmp_path / "bad.yaml", bad)
    result = _run_cli("--input", str(path))
    assert result.returncode == 1


# ----------------------------------------------------------------
# evidenceRefs existence (--normalized)
# ----------------------------------------------------------------


def test_evidence_refs_exist_passes(tmp_path):
    draft_path = _write_yaml(tmp_path / "draft.yaml", _minimal_draft())
    normalized_path = _write_json(
        tmp_path / "normalized.json",
        _minimal_normalized_story(
            "EVT_TEST_A",
            "EVT_TEST_A_E01",
            [_minimal_dialogue_block("EVT_TEST_A_E01_DLG0001", "セリフ本文です。")],
        ),
    )
    result = _run_cli("--input", str(draft_path), "--normalized", str(normalized_path))
    assert result.returncode == 0, result.stderr


def test_evidence_refs_missing_fails(tmp_path):
    draft_path = _write_yaml(tmp_path / "draft.yaml", _minimal_draft())
    # 対応するstory/episodeは存在するが、参照blockIdが実在しない
    normalized_path = _write_json(
        tmp_path / "normalized.json",
        _minimal_normalized_story(
            "EVT_TEST_A",
            "EVT_TEST_A_E01",
            [_minimal_dialogue_block("EVT_TEST_A_E01_DLG9999", "別のセリフです。")],
        ),
    )
    result = _run_cli("--input", str(draft_path), "--normalized", str(normalized_path))
    assert result.returncode == 1
    assert "実在しません" in result.stderr


def test_evidence_refs_check_skipped_without_normalized(tmp_path):
    path = _write_yaml(tmp_path / "draft.yaml", _minimal_draft())
    report_path = tmp_path / "report.md"
    result = _run_cli("--input", str(path), "--report", str(report_path))
    assert result.returncode == 0, result.stderr
    content = report_path.read_text(encoding="utf-8")
    assert "skipped (--normalized not specified)" in content


def test_evidence_refs_episode_not_found_is_warning_not_failure(tmp_path):
    draft_path = _write_yaml(tmp_path / "draft.yaml", _minimal_draft())
    # normalizedに対象storyそのものが含まれない
    normalized_path = _write_json(
        tmp_path / "normalized.json",
        _minimal_normalized_story(
            "EVT_OTHER",
            "EVT_OTHER_E01",
            [_minimal_dialogue_block("EVT_OTHER_E01_DLG0001", "別storyのセリフ")],
        ),
    )
    result = _run_cli("--input", str(draft_path), "--normalized", str(normalized_path))
    assert result.returncode == 0, result.stderr
    assert "警告" in result.stdout


# ----------------------------------------------------------------
# Forbidden text pattern scan
# ----------------------------------------------------------------


def test_forbidden_text_in_episode_summary_fails(tmp_path):
    bad = _minimal_draft()
    bad["episodeSummaries"][0]["text"] = "本文に@ChTalkが混入しています。"
    path = _write_yaml(tmp_path / "bad.yaml", bad)
    result = _run_cli("--input", str(path))
    assert result.returncode == 1
    assert "禁止文字列" in result.stderr


def test_forbidden_text_in_story_summary_fails(tmp_path):
    bad = _minimal_draft(
        storySummary={
            "text": "C:\\Users\\example\\raw\\script.dec由来のテキストです。",
            "confidence": 0.5,
            "evidenceRefs": [],
        }
    )
    path = _write_yaml(tmp_path / "bad.yaml", bad)
    result = _run_cli("--input", str(path))
    assert result.returncode == 1
    assert "禁止文字列" in result.stderr


def test_forbidden_text_in_notes_fails(tmp_path):
    bad = _minimal_draft(notes="この文章には $num が混入しています。")
    path = _write_yaml(tmp_path / "bad.yaml", bad)
    result = _run_cli("--input", str(path))
    assert result.returncode == 1


def test_forbidden_text_in_review_notes_fails(tmp_path):
    bad = _minimal_draft(
        review={
            "status": "unreviewed",
            "reviewer": None,
            "reviewedAt": None,
            "notes": "@ScenarioCosLoad由来の値が混入しています。",
        }
    )
    path = _write_yaml(tmp_path / "bad.yaml", bad)
    result = _run_cli("--input", str(path))
    assert result.returncode == 1


# ----------------------------------------------------------------
# 本文中evidence/block ID引用検出 (項目5、`summary-domain-context-
# injection`で追加。--normalizedの有無に関わらず常に実行される)
# ----------------------------------------------------------------


def test_evidence_id_citation_in_episode_summary_text_fails(tmp_path):
    bad = _minimal_draft()
    bad["episodeSummaries"][0]["text"] = (
        "半裸になったのは班長（EVT_TEST_A_E01_DLG0001）。"
    )
    path = _write_yaml(tmp_path / "bad.yaml", bad)
    result = _run_cli("--input", str(path))
    assert result.returncode == 1
    assert "evidence/block ID引用" in result.stderr
    assert "EVT_TEST_A_E01_DLG0001" in result.stderr


def test_evidence_id_citation_in_story_summary_text_fails(tmp_path):
    bad = _minimal_draft(
        storySummary={
            "text": "対策班が集結した（EVT_TEST_A_E01_NAR0003）。",
            "confidence": 0.5,
            "evidenceRefs": [],
        }
    )
    path = _write_yaml(tmp_path / "bad.yaml", bad)
    result = _run_cli("--input", str(path))
    assert result.returncode == 1
    assert "evidence/block ID引用" in result.stderr


def test_evidence_id_citation_check_runs_without_normalized(tmp_path):
    # --normalized未指定でも常に実行される (evidenceRefs実在性検証・
    # verbatim検出とは異なりskipされない)。
    bad = _minimal_draft()
    bad["episodeSummaries"][0]["text"] = "地の文に（EVT_TEST_A_E01_MONO0002）を含む。"
    path = _write_yaml(tmp_path / "bad.yaml", bad)
    report_path = tmp_path / "report.md"
    result = _run_cli("--input", str(path), "--report", str(report_path))
    assert result.returncode == 1
    content = report_path.read_text(encoding="utf-8")
    assert "Evidence ID Citation In Body Check" in content
    assert "- Result: FAIL" in content


def test_evidence_id_citation_in_evidence_refs_field_alone_is_not_flagged(tmp_path):
    # evidenceRefsフィールド自体 (通常の引用形式) はこの検証の対象外
    # (本文textフィールドのみが対象)。
    draft = _minimal_draft()
    path = _write_yaml(tmp_path / "draft.yaml", draft)
    result = _run_cli("--input", str(path))
    assert result.returncode == 0, result.stderr


def test_evidence_id_citation_no_match_passes(tmp_path):
    path = _write_yaml(tmp_path / "draft.yaml", _minimal_draft())
    report_path = tmp_path / "report.md"
    result = _run_cli("--input", str(path), "--report", str(report_path))
    assert result.returncode == 0, result.stderr
    content = report_path.read_text(encoding="utf-8")
    assert "Evidence ID Citation In Body Check" in content
    assert "PASS" in content


# ----------------------------------------------------------------
# 既存の公開済みSummary (knowledge/summaries/stories/) が新規検証で
# 誤検出されないことの確認 (`summary-domain-context-injection`)
# ----------------------------------------------------------------


def test_published_summaries_pass_new_evidence_id_citation_check():
    published_dir = PROJECT_ROOT / "knowledge" / "summaries" / "stories"
    result = _run_cli("--input", str(published_dir))
    assert result.returncode == 0, result.stderr


# ----------------------------------------------------------------
# Verbatim quote detection (threshold boundary, --normalized)
# ----------------------------------------------------------------


def test_verbatim_quote_below_threshold_passes(tmp_path):
    block_text = "0123456789"  # 10 chars
    draft = _minimal_draft()
    # 先頭9文字のみ一致 (閾値10未満)
    draft["episodeSummaries"][0]["text"] = "あらすじ: 012345678 のようなことがあった。"
    draft_path = _write_yaml(tmp_path / "draft.yaml", draft)
    normalized_path = _write_json(
        tmp_path / "normalized.json",
        _minimal_normalized_story(
            "EVT_TEST_A",
            "EVT_TEST_A_E01",
            [_minimal_dialogue_block("EVT_TEST_A_E01_DLG0001", block_text)],
        ),
    )
    result = _run_cli(
        "--input",
        str(draft_path),
        "--normalized",
        str(normalized_path),
        "--verbatim-threshold",
        "10",
    )
    assert result.returncode == 0, result.stderr


def test_verbatim_quote_at_threshold_fails(tmp_path):
    block_text = "0123456789"  # 10 chars
    draft = _minimal_draft()
    # 10文字全部が連続一致 (閾値10ちょうど)
    draft["episodeSummaries"][0]["text"] = "あらすじ: 0123456789 のようなことがあった。"
    draft_path = _write_yaml(tmp_path / "draft.yaml", draft)
    normalized_path = _write_json(
        tmp_path / "normalized.json",
        _minimal_normalized_story(
            "EVT_TEST_A",
            "EVT_TEST_A_E01",
            [_minimal_dialogue_block("EVT_TEST_A_E01_DLG0001", block_text)],
        ),
    )
    result = _run_cli(
        "--input",
        str(draft_path),
        "--normalized",
        str(normalized_path),
        "--verbatim-threshold",
        "10",
    )
    assert result.returncode == 1
    assert "連続一致" in result.stderr


def test_verbatim_quote_skipped_without_normalized(tmp_path):
    draft = _minimal_draft()
    draft["episodeSummaries"][0]["text"] = "あらすじ: 0123456789 のようなことがあった。"
    path = _write_yaml(tmp_path / "draft.yaml", draft)
    report_path = tmp_path / "report.md"
    result = _run_cli("--input", str(path), "--report", str(report_path))
    assert result.returncode == 0, result.stderr
    content = report_path.read_text(encoding="utf-8")
    assert "Verbatim Quote Detection" in content
    assert "skipped (--normalized not specified)" in content


def test_story_level_text_excluded_from_verbatim_check(tmp_path):
    block_text = "0123456789"  # 10 chars
    draft = _minimal_draft(
        storySummary={
            "text": "story全体のあらすじ: 0123456789 という出来事があった。",
            "confidence": 0.5,
            "evidenceRefs": ["EVT_TEST_A_E01_DLG0001"],
        }
    )
    draft_path = _write_yaml(tmp_path / "draft.yaml", draft)
    normalized_path = _write_json(
        tmp_path / "normalized.json",
        _minimal_normalized_story(
            "EVT_TEST_A",
            "EVT_TEST_A_E01",
            [_minimal_dialogue_block("EVT_TEST_A_E01_DLG0001", block_text)],
        ),
    )
    result = _run_cli(
        "--input",
        str(draft_path),
        "--normalized",
        str(normalized_path),
        "--verbatim-threshold",
        "10",
    )
    # storySummary.textはverbatim検出の対象外なのでblockingにならない
    assert result.returncode == 0, result.stderr


# ----------------------------------------------------------------
# File / directory input
# ----------------------------------------------------------------


def test_directory_input_collects_multiple_drafts(tmp_path):
    drafts_dir = tmp_path / "drafts"
    drafts_dir.mkdir()
    _write_yaml(drafts_dir / "a.yaml", _minimal_draft(storyId="EVT_TEST_A"))
    _write_yaml(
        drafts_dir / "b.yaml",
        _minimal_draft(
            storyId="EVT_TEST_B",
            storySummary={
                "text": "story Bのあらすじです。",
                "confidence": 0.5,
                "evidenceRefs": [],
            },
            episodeSummaries=[
                {
                    "episodeId": "EVT_TEST_B_E01",
                    "publicEpisodeId": None,
                    "episodeNumber": 1,
                    "text": "story BのEpisode 1です。",
                    "confidence": 0.5,
                    "evidenceRefs": [],
                }
            ],
        ),
    )
    report_path = tmp_path / "report.md"
    result = _run_cli("--input", str(drafts_dir), "--report", str(report_path))
    assert result.returncode == 0, result.stderr
    content = report_path.read_text(encoding="utf-8")
    assert "File count: 2" in content
    assert "Story count (schema-valid): 2" in content


# ----------------------------------------------------------------
# --report knowledge/ rejection
# ----------------------------------------------------------------


def test_report_under_knowledge_dir_rejected(tmp_path):
    path = _write_yaml(tmp_path / "draft.yaml", _minimal_draft())
    forbidden_report = PROJECT_ROOT / "knowledge" / "_tmp_quality_gate_report.md"
    result = _run_cli("--input", str(path), "--report", str(forbidden_report))
    assert result.returncode == 2
    assert not forbidden_report.exists()


# ----------------------------------------------------------------
# Report content
# ----------------------------------------------------------------


def test_report_markdown_is_generated_with_sections(tmp_path):
    path = _write_yaml(tmp_path / "draft.yaml", _minimal_draft())
    report_path = tmp_path / "report.md"
    result = _run_cli("--input", str(path), "--report", str(report_path))
    assert result.returncode == 0, result.stderr
    content = report_path.read_text(encoding="utf-8")
    assert "Story Summary Draft Quality Gate Check Report" in content
    assert "Schema Validation" in content
    assert "evidenceRefs Existence Check" in content
    assert "Forbidden Text Pattern Scan" in content
    assert "Verbatim Quote Detection" in content
    assert "Out of Scope" in content
    assert "Final Decision" in content
    assert "PASS" in content


def test_report_records_final_decision_fail(tmp_path):
    bad = _minimal_draft()
    bad["episodeSummaries"][0]["text"] = "本文に@ChTalkが混入しています。"
    path = _write_yaml(tmp_path / "bad.yaml", bad)
    report_path = tmp_path / "report.md"
    result = _run_cli("--input", str(path), "--report", str(report_path))
    assert result.returncode == 1
    content = report_path.read_text(encoding="utf-8")
    assert "## Final Decision" in content
    # Final Decisionセクション自体がFAILであることを確認する
    final_section = content.split("## Final Decision", 1)[1]
    assert "FAIL" in final_section


# ----------------------------------------------------------------
# Check-only: 入力不変
# ----------------------------------------------------------------


def test_check_only_does_not_modify_inputs(tmp_path):
    draft_path = _write_yaml(tmp_path / "draft.yaml", _minimal_draft())
    normalized_path = _write_json(
        tmp_path / "normalized.json",
        _minimal_normalized_story(
            "EVT_TEST_A",
            "EVT_TEST_A_E01",
            [_minimal_dialogue_block("EVT_TEST_A_E01_DLG0001", "セリフ本文です。")],
        ),
    )
    draft_before = draft_path.read_bytes()
    normalized_before = normalized_path.read_bytes()

    report_path = tmp_path / "report.md"
    result = _run_cli(
        "--input",
        str(draft_path),
        "--normalized",
        str(normalized_path),
        "--report",
        str(report_path),
    )
    assert result.returncode == 0, result.stderr

    assert draft_path.read_bytes() == draft_before
    assert normalized_path.read_bytes() == normalized_before
