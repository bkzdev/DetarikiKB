"""release scope Stage A/B一括runnerの合成データテスト。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator

from agents.extractor.release_scope import build_release_scope_knowledge
from agents.parser.normalizer import Normalizer
from agents.parser.parser import StoryParser

PROJECT_ROOT = Path(__file__).parent.parent.parent


def _normalized(
    script: str,
    *,
    story_id: str,
    episode_id: str,
    category: str,
    variant_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed = StoryParser().parse_text(script, source_file="synthetic_secret.dec")
    return Normalizer(
        story_id=story_id,
        story_category=category,
        episode_id=episode_id,
        source_file="synthetic_secret.dec",
        variant_trace=variant_trace,
    ).normalize(parsed)


def _write_normalized_inputs(tmp_path: Path) -> Path:
    normalized_root = tmp_path / "normalized"
    normalized_root.mkdir()
    documents = [
        _normalized(
            "@ChTalk 0 voice/event/a.ogg\n秘密のイベント本文\nmsg\n",
            story_id="EVT_SECRET",
            episode_id="EVT_SECRET_E01",
            category="EVT",
        ),
        _normalized(
            "@ChTalk 0 voice/body/a.ogg\n基準本文\nmsg\n",
            story_id="CHAR_HS_SECRET",
            episode_id="CHAR_HS_SECRET_E01",
            category="CHAR_HS",
        ),
        _normalized(
            "@ChTalk 0 voice/body/a.ogg\n基準本文\nmsg\n"
            "@ChTalk 0 voice/variant/b.ogg\n固有本文\nmsg\n",
            story_id="CHAR_HS_SECRET",
            episode_id="CHAR_HS_SECRET_E01_VN",
            category="CHAR_HS",
            variant_trace={
                "baseEpisodeId": "CHAR_HS_SECRET_E01",
                "variantPattern": "n",
                "dupIndex": None,
                "judgment": "exception",
                "bodyIdentifierCount": 2,
                "variantIdentifierCount": 4,
                "extraInVariantCount": 2,
            },
        ),
    ]
    for index, document in enumerate(documents):
        (normalized_root / f"input_{index}.json").write_text(
            json.dumps(document, ensure_ascii=False), encoding="utf-8"
        )
    return normalized_root


def _write_normalization_report(tmp_path: Path, *, normalized_count: int = 3) -> Path:
    report = {
        "schemaVersion": "0.1",
        "documentType": "release_scope_normalization_report",
        "status": "complete",
        "manifestSha256": "0" * 64,
        "manifestStoryCount": 2,
        "manifestEpisodeCount": 2,
        "dynamicExceptionEpisodeCount": 1,
        "normalizedEpisodeCount": normalized_count,
        "invalidCount": 0,
        "skippedCount": 0,
        "categoryEpisodeCounts": {"EVT": 1, "CHAR_HS": 2},
        "compatibilityStatusCounts": {"compatible": 3},
        "unknownBlockCount": 0,
        "episodesWithUnknownBlocks": 0,
        "unknownCommandDistinctCount": 0,
        "unknownCommandOccurrenceCount": 0,
        "episodesWithUnknownCommands": 0,
        "unknownCharacterIdDistinctCount": 0,
        "episodesWithUnknownCharacterIds": 0,
        "unresolvedSpeakerBlockCount": 0,
        "episodesWithUnresolvedSpeakers": 0,
        "nonSpeakerNumericAssignmentCount": 0,
        "nonLiteralSpeakerExpressionCount": 0,
        "branchIssueCount": 0,
        "caseVariantCount": 0,
        "controlCharsRemoved": 0,
        "hsceneVariantJudgment": {"subset": 0, "exception": 1, "skippedVr": 0},
    }
    path = tmp_path / "release_scope_normalization_report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def _build(
    *, normalized_root: Path, output_root: Path, normalization_report_path: Path
) -> dict:
    return build_release_scope_knowledge(
        normalized_root=normalized_root,
        output_root=output_root,
        story_schema_path=PROJECT_ROOT / "schemas" / "story.schema.json",
        extraction_schema_path=PROJECT_ROOT / "schemas" / "extraction.schema.json",
        collection_schema_path=(
            PROJECT_ROOT / "schemas" / "merged_knowledge_collection.schema.json"
        ),
        report_schema_path=(
            PROJECT_ROOT / "schemas" / "release_scope_knowledge_report.schema.json"
        ),
        normalization_report_path=normalization_report_path,
        normalization_report_schema_path=(
            PROJECT_ROOT / "schemas" / "release_scope_normalization_report.schema.json"
        ),
    )


def _run(tmp_path: Path, output_name: str = "knowledge") -> tuple[dict, Path]:
    normalized_root = _write_normalized_inputs(tmp_path)
    normalization_report_path = _write_normalization_report(tmp_path)
    output_root = tmp_path / output_name
    report = _build(
        normalized_root=normalized_root,
        output_root=output_root,
        normalization_report_path=normalization_report_path,
    )
    return report, output_root


def test_release_scope_extracts_merges_and_emits_anonymous_report(tmp_path):
    report, output_root = _run(tmp_path)

    assert report["normalizedDocumentCount"] == 3
    assert report["normalizedEpisodeCount"] == 3
    assert report["normalizedCategoryCounts"] == {
        "CHAR_DATE": 0,
        "CHAR_EXTRA": 0,
        "CHAR_HS": 2,
        "CHAR_MAIN": 0,
        "EVT": 1,
        "MAIN": 0,
        "OTHER": 0,
        "RAID": 0,
    }
    assert report["extractionDocumentCount"] == 3
    assert report["mergeResolvedInputCount"] == 3
    assert report["mergeValidInputCount"] == 3
    assert report["hsceneDedup"] == {
        "bodyEpisodeCount": 1,
        "variantEpisodeCount": 1,
        "excludedBlockCount": 1,
    }
    assert set(report["conflictEntityCounts"]) == {
        "characters",
        "locations",
        "organizations",
        "items",
        "lore",
        "events",
        "relationships",
        "timeline",
    }

    report_text = (output_root / "release_scope_knowledge_report.json").read_text(
        encoding="utf-8"
    )
    assert "SECRET" not in report_text
    assert "秘密" not in report_text
    schema = json.loads(
        (
            PROJECT_ROOT / "schemas" / "release_scope_knowledge_report.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert not list(Draft7Validator(schema).iter_errors(report))
    assert len(list((output_root / "extracted").glob("*.json"))) == 3
    assert (output_root / "merged" / "merged_knowledge_collection.json").is_file()
    assert (output_root / "reports" / "merge_report.json").is_file()


def test_release_scope_rejects_existing_output_without_modifying_it(tmp_path):
    normalized_root = _write_normalized_inputs(tmp_path)
    normalization_report_path = _write_normalization_report(tmp_path)
    output_root = tmp_path / "knowledge"
    output_root.mkdir()
    marker = output_root / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(FileExistsError, match="既存path"):
        _build(
            normalized_root=normalized_root,
            output_root=output_root,
            normalization_report_path=normalization_report_path,
        )

    assert marker.read_text(encoding="utf-8") == "keep"


def test_release_scope_rejects_active_lock(tmp_path):
    normalized_root = _write_normalized_inputs(tmp_path)
    normalization_report_path = _write_normalization_report(tmp_path)
    output_root = tmp_path / "knowledge"
    lock = tmp_path / ".knowledge.lock"
    lock.write_text("busy", encoding="utf-8")

    with pytest.raises(FileExistsError, match="既に実行中"):
        _build(
            normalized_root=normalized_root,
            output_root=output_root,
            normalization_report_path=normalization_report_path,
        )

    assert lock.read_text(encoding="utf-8") == "busy"
    assert not output_root.exists()


def test_release_scope_cleans_temporary_output_after_invalid_input(tmp_path):
    normalized_root = _write_normalized_inputs(tmp_path)
    normalization_report_path = _write_normalization_report(tmp_path)
    invalid_path = next(normalized_root.glob("*.json"))
    invalid = json.loads(invalid_path.read_text(encoding="utf-8"))
    invalid["schemaVersion"] = "invalid"
    invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
    output_root = tmp_path / "knowledge"

    with pytest.raises(ValueError, match="schema validation failed"):
        _build(
            normalized_root=normalized_root,
            output_root=output_root,
            normalization_report_path=normalization_report_path,
        )

    assert not output_root.exists()
    assert not list(tmp_path.glob(".knowledge.tmp-*"))
    assert not (tmp_path / ".knowledge.lock").exists()


def test_release_scope_rejects_normalized_count_mismatch(tmp_path):
    normalized_root = _write_normalized_inputs(tmp_path)
    normalization_report_path = _write_normalization_report(
        tmp_path, normalized_count=4
    )
    output_root = tmp_path / "knowledge"

    with pytest.raises(ValueError, match="M2 normalization report"):
        _build(
            normalized_root=normalized_root,
            output_root=output_root,
            normalization_report_path=normalization_report_path,
        )

    assert not output_root.exists()
    assert not list(tmp_path.glob(".knowledge.tmp-*"))
