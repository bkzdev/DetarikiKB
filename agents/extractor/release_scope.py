"""v1 release scopeのStage A抽出・Stage B merge・匿名品質集計。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from jsonschema import Draft7Validator

from agents.merger import MergeEngine
from agents.merger.models import MERGED_ENTITY_KEYS
from agents.merger.schema_validation import load_merged_collection_validator

from .extractor import Extractor
from .hscene_dedup import extract_stories_with_hscene_dedup

REPORT_SCHEMA_VERSION = "0.1"
REPORT_DOCUMENT_TYPE = "release_scope_knowledge_report"
NORMALIZED_CATEGORIES = (
    "MAIN",
    "EVT",
    "RAID",
    "OTHER",
    "CHAR_MAIN",
    "CHAR_EXTRA",
    "CHAR_DATE",
    "CHAR_HS",
)


@contextmanager
def _reserve_output(output_root: Path) -> Iterator[None]:
    output_root.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output_root.parent / f".{output_root.name}.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise FileExistsError("同じoutput rootの処理が既に実行中です") from exc
    try:
        os.write(lock_fd, b"release scope extraction and merge in progress\n")
        if output_root.exists():
            raise FileExistsError("output rootは既存pathを指定できません")
        yield
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


def _load_validator(path: Path) -> Draft7Validator:
    with open(path, encoding="utf-8") as stream:
        schema = json.load(stream)
    Draft7Validator.check_schema(schema)
    return Draft7Validator(schema)


def _validate_document(
    document: dict[str, Any], validator: Draft7Validator, label: str
) -> None:
    errors = sorted(
        validator.iter_errors(document),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if errors:
        diagnostics = []
        for error in errors[:20]:
            path = ".".join(str(part) for part in error.absolute_path) or "<root>"
            diagnostics.append(f"{path}:{error.validator}")
        raise ValueError(
            f"{label} schema validation failed: {len(errors)} "
            f"({', '.join(diagnostics)})"
        )


def _write_extraction(
    extraction: dict[str, Any],
    *,
    stage_a_dir: Path,
    merge_engine: MergeEngine,
    seen_episode_ids: set[str],
    metrics: Counter[str],
) -> None:
    episode_id = extraction["episodeId"]
    if episode_id in seen_episode_ids:
        raise ValueError("duplicate extraction episodeId detected")
    result = merge_engine.validate_document(extraction, source="generated")
    if not result.is_valid:
        raise ValueError(
            "extraction validation failed: "
            f"schema={len(result.schema_errors)}, "
            f"semantic={len(result.semantic_errors)}"
        )
    metrics["semanticWarnings"] += len(result.semantic_warnings)
    dedup = extraction.get("hsceneDedup")
    if isinstance(dedup, dict):
        role = dedup.get("role")
        if role == "body":
            metrics["hsceneBodyEpisodes"] += 1
        elif role == "variant":
            metrics["hsceneVariantEpisodes"] += 1
            excluded = dedup.get("excludedBlockCount", 0)
            if isinstance(excluded, int):
                metrics["hsceneExcludedBlocks"] += excluded
    seen_episode_ids.add(episode_id)
    destination = stage_a_dir / f"{episode_id}.extraction.json"
    with open(destination, "w", encoding="utf-8") as stream:
        json.dump(extraction, stream, ensure_ascii=False, indent=2)


def _anonymous_report(
    *,
    normalization_report_sha256: str,
    normalized_tree_sha256: str,
    normalized_document_count: int,
    normalized_episode_count: int,
    category_counts: Counter[str],
    extraction_count: int,
    extraction_metrics: Counter[str],
    special_speaker_candidate_count: int,
    merge_report: dict[str, Any],
) -> dict[str, Any]:
    canonical = merge_report.get("canonicalIdSummary", {})
    special = merge_report.get("specialSpeakerLabelSummary", {})
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "documentType": REPORT_DOCUMENT_TYPE,
        "status": "complete",
        "normalizationReportSha256": normalization_report_sha256,
        "normalizedTreeSha256": normalized_tree_sha256,
        "normalizedDocumentCount": normalized_document_count,
        "normalizedEpisodeCount": normalized_episode_count,
        "normalizedCategoryCounts": dict(sorted(category_counts.items())),
        "extractionDocumentCount": extraction_count,
        "extractionInvalidCount": 0,
        "extractionSemanticErrorCount": 0,
        "extractionSemanticWarningCount": extraction_metrics["semanticWarnings"],
        "hsceneDedup": {
            "bodyEpisodeCount": extraction_metrics["hsceneBodyEpisodes"],
            "variantEpisodeCount": extraction_metrics["hsceneVariantEpisodes"],
            "excludedBlockCount": extraction_metrics["hsceneExcludedBlocks"],
        },
        "mergeResolvedInputCount": merge_report["resolvedInputFiles"],
        "mergeValidInputCount": merge_report["validInputs"],
        "mergeInvalidInputCount": merge_report["invalidInputs"],
        "mergeSkippedInputCount": len(merge_report["skippedInputs"]),
        "candidateCounts": merge_report["candidateCounts"],
        "specialSpeakerLabelCandidateCount": special_speaker_candidate_count,
        "mergedEntityCounts": merge_report["mergedEntityCounts"],
        "unresolvedEntityCounts": merge_report["unresolvedEntityCounts"],
        "conflictCount": merge_report["conflictCounts"]["total"],
        "conflictEntityCounts": {
            key: merge_report["conflictCounts"]["byEntityType"].get(key, 0)
            for key in MERGED_ENTITY_KEYS
        },
        "warningCounts": merge_report["warningCounts"],
        "relationshipReviewRecordCount": len(
            merge_report.get("relationshipReviewRecords", [])
        ),
        "canonicalIdSummary": {
            "totalAssigned": canonical.get("totalAssigned", 0),
            "duplicateCount": canonical.get("duplicateCount", 0),
            "invalidCount": canonical.get("invalidCount", 0),
        },
        "specialSpeakerLabelCount": special.get("total", 0),
    }


def _decode_normalized_document(
    raw: bytes, validator: Draft7Validator
) -> tuple[dict[str, Any], str]:
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Normalized Story rootはobjectである必要があります")
    _validate_document(document, validator, "normalized story")
    episodes = document.get("episodes") or []
    if len(episodes) != 1:
        raise ValueError("release scopeでは1 document 1 episodeが必要です")
    return document, episodes[0]["episodeId"]


def _reload_hscene_group(
    entries: list[tuple[Path, bytes]], validator: Draft7Validator
) -> list[dict[str, Any]]:
    documents = []
    for path, expected_digest in sorted(entries):
        raw = path.read_bytes()
        if hashlib.sha256(raw).digest() != expected_digest:
            raise ValueError("CHAR_HS inputが処理中に変更されました")
        document, _ = _decode_normalized_document(raw, validator)
        documents.append(document)
    return documents


def _extract_normalized_scope(
    *,
    paths: list[Path],
    normalized_root: Path,
    stage_a_dir: Path,
    story_validator: Draft7Validator,
    merge_engine: MergeEngine,
) -> tuple[set[str], Counter[str], Counter[str], str]:
    extractor = Extractor()
    normalized_episode_ids: set[str] = set()
    extraction_episode_ids: set[str] = set()
    hscene_paths: dict[str, list[tuple[Path, bytes]]] = defaultdict(list)
    category_counts: Counter[str] = Counter(dict.fromkeys(NORMALIZED_CATEGORIES, 0))
    metrics: Counter[str] = Counter()
    tree_digest = hashlib.sha256()

    def write(extraction: dict[str, Any]) -> None:
        metrics["specialSpeakerCandidates"] += len(
            extraction.get("specialSpeakerLabelCandidates", [])
        )
        _write_extraction(
            extraction,
            stage_a_dir=stage_a_dir,
            merge_engine=merge_engine,
            seen_episode_ids=extraction_episode_ids,
            metrics=metrics,
        )

    for path in paths:
        raw = path.read_bytes()
        relative = path.relative_to(normalized_root).as_posix()
        tree_digest.update(relative.encode("utf-8"))
        tree_digest.update(b"\0")
        content_digest = hashlib.sha256(raw).digest()
        tree_digest.update(content_digest)
        document, episode_id = _decode_normalized_document(raw, story_validator)
        if episode_id in normalized_episode_ids:
            raise ValueError("duplicate normalized episodeId detected")
        normalized_episode_ids.add(episode_id)
        category = document["storyCategory"]
        category_counts[category] += 1
        if category == "CHAR_HS":
            hscene_paths[document["storyId"]].append((path, content_digest))
        else:
            for extraction in extractor.extract_story(document):
                write(extraction)

    for story_id in sorted(hscene_paths):
        documents = _reload_hscene_group(hscene_paths[story_id], story_validator)
        for extraction in extract_stories_with_hscene_dedup(documents):
            write(extraction)

    if normalized_episode_ids != extraction_episode_ids:
        raise ValueError("normalized/extraction episode setが一致しません")
    return normalized_episode_ids, category_counts, metrics, tree_digest.hexdigest()


def _run_reserved(
    *,
    normalized_root: Path,
    output_root: Path,
    story_validator: Draft7Validator,
    extraction_schema_path: Path,
    collection_schema_path: Path,
    report_validator: Draft7Validator,
    normalization_report: dict[str, Any],
    normalization_report_sha256: str,
) -> dict[str, Any]:
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.tmp-", dir=output_root.parent)
    )
    try:
        stage_a_dir = temporary_root / "extracted"
        stage_a_dir.mkdir()
        paths = sorted(normalized_root.rglob("*.json"))
        if not paths:
            raise ValueError("normalized inputが空です")

        merge_engine = MergeEngine(extraction_schema_path)
        episode_ids, category_counts, extraction_metrics, tree_digest = (
            _extract_normalized_scope(
                paths=paths,
                normalized_root=normalized_root,
                stage_a_dir=stage_a_dir,
                story_validator=story_validator,
                merge_engine=merge_engine,
            )
        )
        expected_category_counts = {
            key: value for key, value in category_counts.items() if value
        }
        if (
            normalization_report["status"] != "complete"
            or normalization_report["invalidCount"] != 0
            or normalization_report["skippedCount"] != 0
            or normalization_report["normalizedEpisodeCount"] != len(episode_ids)
            or normalization_report["categoryEpisodeCounts"] != expected_category_counts
        ):
            raise ValueError("M2 normalization reportとNormalized入力が一致しません")

        collection = merge_engine.merge_inputs([str(stage_a_dir)])
        merge_report = collection["report"]
        expected = len(episode_ids)
        if (
            merge_report["resolvedInputFiles"] != expected
            or merge_report["validInputs"] != expected
            or merge_report["invalidInputs"] != 0
            or merge_report["skippedInputs"]
        ):
            raise ValueError("Stage B input gate failed")
        collection_validator = load_merged_collection_validator(collection_schema_path)
        _validate_document(collection, collection_validator, "merged collection")

        merged_dir = temporary_root / "merged"
        reports_dir = temporary_root / "reports"
        merged_dir.mkdir()
        reports_dir.mkdir()
        with open(
            merged_dir / "merged_knowledge_collection.json", "w", encoding="utf-8"
        ) as stream:
            json.dump(collection, stream, ensure_ascii=False, indent=2)
        with open(reports_dir / "merge_report.json", "w", encoding="utf-8") as stream:
            json.dump(merge_report, stream, ensure_ascii=False, indent=2)

        report = _anonymous_report(
            normalization_report_sha256=normalization_report_sha256,
            normalized_tree_sha256=tree_digest,
            normalized_document_count=len(paths),
            normalized_episode_count=len(episode_ids),
            category_counts=category_counts,
            extraction_count=expected,
            extraction_metrics=extraction_metrics,
            special_speaker_candidate_count=extraction_metrics[
                "specialSpeakerCandidates"
            ],
            merge_report=merge_report,
        )
        _validate_document(report, report_validator, "release scope knowledge report")
        with open(
            temporary_root / "release_scope_knowledge_report.json",
            "w",
            encoding="utf-8",
        ) as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)

        if output_root.exists():
            raise FileExistsError("処理中にoutput rootが作成されました")
        os.rename(temporary_root, output_root)
        return report
    except Exception:
        resolved_temp = temporary_root.resolve()
        if (
            resolved_temp.parent == output_root.parent.resolve()
            and resolved_temp.name.startswith(f".{output_root.name}.tmp-")
        ):
            shutil.rmtree(resolved_temp)
        raise


def build_release_scope_knowledge(
    *,
    normalized_root: Path,
    output_root: Path,
    story_schema_path: Path,
    extraction_schema_path: Path,
    collection_schema_path: Path,
    report_schema_path: Path,
    normalization_report_path: Path,
    normalization_report_schema_path: Path,
) -> dict[str, Any]:
    """Normalized全件からStage A/Bを生成し、成功時だけまとめて公開する。"""
    if not normalized_root.is_dir():
        raise FileNotFoundError("normalized rootが見つかりません")
    story_validator = _load_validator(story_schema_path)
    report_validator = _load_validator(report_schema_path)
    normalization_report_raw = normalization_report_path.read_bytes()
    normalization_report = json.loads(normalization_report_raw.decode("utf-8"))
    if not isinstance(normalization_report, dict):
        raise ValueError("M2 normalization report rootはobjectである必要があります")
    _validate_document(
        normalization_report,
        _load_validator(normalization_report_schema_path),
        "M2 normalization report",
    )
    with _reserve_output(output_root):
        return _run_reserved(
            normalized_root=normalized_root,
            output_root=output_root,
            story_validator=story_validator,
            extraction_schema_path=extraction_schema_path,
            collection_schema_path=collection_schema_path,
            report_validator=report_validator,
            normalization_report=normalization_report,
            normalization_report_sha256=hashlib.sha256(
                normalization_report_raw
            ).hexdigest(),
        )
