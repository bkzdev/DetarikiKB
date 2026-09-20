"""v1 release scopeの一括normalizeと匿名品質集計。

実データ由来のNormalized Storyと詳細なpath/IDはignored outputにだけ保存し、
公開可能なreportには件数とdigest以外を含めない。manifest episodeに加えて、
CHAR_HSの動的部分集合判定でexceptionになった変種も通常の別episodeとして
取り込む。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import Counter
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

import yaml
from jsonschema import Draft7Validator

from .hscene_variant_judgment import (
    find_hscene_body_files,
    hscene_number,
    judge_body_variants,
)
from .normalizer import Normalizer
from .parser import StoryParser
from .resolver import CharacterDictionary
from .story_manifest import (
    StoryManifestEpisode,
    StoryManifestStory,
    build_manifest_normalization_metadata,
    load_story_manifest,
    resolve_story_category,
)
from .tokenizer import Tokenizer

REPORT_SCHEMA_VERSION = "0.1"
REPORT_DOCUMENT_TYPE = "release_scope_normalization_report"
_CATEGORY_OUTPUT_DIRS = {"MAIN": "main", "EVT": "event", "RAID": "raid"}


@contextmanager
def _reserve_output(output_root: Path) -> Iterator[None]:
    """同じ出力先を使う協調runを排他し、既存出力を上書きしない。"""
    output_root.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output_root.parent / f".{output_root.name}.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise FileExistsError("同じoutput rootの処理が既に実行中です") from exc
    try:
        os.write(lock_fd, b"release scope normalization in progress\n")
        if output_root.exists():
            raise FileExistsError("output rootは既存pathを指定できません")
        yield
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


def _iter_blocks(blocks: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for block in blocks:
        yield block
        if block.get("type") != "choice":
            continue
        for option in block.get("options", []):
            yield from _iter_blocks(option.get("blocks", []))


def _all_blocks(document: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for episode in document.get("episodes", []):
        for scene in episode.get("scenes", []):
            yield from _iter_blocks(scene.get("blocks", []))


def _safe_raw_path(raw_root: Path, raw_path: str) -> Path:
    """manifest rawPathをroot内の実在fileとして解決する。"""
    candidate = raw_root.joinpath(*PurePosixPath(raw_path).parts).resolve()
    try:
        candidate.relative_to(raw_root.resolve())
    except ValueError as exc:
        raise ValueError("manifest rawPathがraw root外を参照しています") from exc
    if not candidate.is_file():
        raise FileNotFoundError("manifest rawPathに対応するfileがありません")
    return candidate


def _safe_raw_directory(raw_root: Path, raw_directory: str) -> Path:
    candidate = raw_root.joinpath(*PurePosixPath(raw_directory).parts).resolve()
    try:
        candidate.relative_to(raw_root.resolve())
    except ValueError as exc:
        raise ValueError("manifest rawDirectoryがraw root外を参照しています") from exc
    if not candidate.is_dir():
        raise FileNotFoundError("manifest rawDirectoryに対応するdirectoryがありません")
    return candidate


def _load_validator(path: Path) -> Draft7Validator:
    with open(path, encoding="utf-8") as stream:
        schema = json.load(stream)
    Draft7Validator.check_schema(schema)
    return Draft7Validator(schema)


def _validate_manifest(manifest_path: Path, schema_path: Path) -> None:
    with open(manifest_path, encoding="utf-8") as stream:
        document = yaml.safe_load(stream) or {}
    errors = sorted(
        _load_validator(schema_path).iter_errors(document),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise ValueError(f"story manifest schema validation failed: {len(errors)}")


def _normalize_document(
    *,
    input_path: Path,
    story_id: str,
    category: str,
    episode_id: str,
    character_dictionary: CharacterDictionary,
    commands_path: Path,
    story_metadata: dict[str, Any] | None = None,
    episode_metadata: dict[str, Any] | None = None,
    manifest_source: dict[str, Any] | None = None,
    variant_trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parser = StoryParser(
        char_dict=character_dictionary,
        preserve_stage_directions=True,
        preserve_unknown=True,
        source_file=input_path.stem,
    )
    parse_result = parser.parse_file(input_path)
    normalizer = Normalizer(
        story_id=story_id,
        story_category=category,
        episode_id=episode_id,
        story_metadata=story_metadata,
        episode_metadata=episode_metadata,
        source_file=input_path.stem,
        source_path=str(input_path),
        preserve_stage_directions=True,
        commands_config_path=commands_path,
        manifest_source=manifest_source,
        variant_trace=variant_trace,
    )
    with open(input_path, encoding="utf-8", errors="ignore") as stream:
        line_count = sum(1 for _ in stream)
    return normalizer.normalize(parse_result, line_count=line_count)


class _Metrics:
    def __init__(self) -> None:
        self.category_counts: Counter[str] = Counter()
        self.compatibility_counts: Counter[str] = Counter()
        self.unknown_commands: set[str] = set()
        self.unknown_command_occurrences = 0
        self.episodes_with_unknown_commands = 0
        self.unknown_character_ids: set[str] = set()
        self.episodes_with_unknown_character_ids = 0
        self.unknown_block_count = 0
        self.episodes_with_unknown_blocks = 0
        self.unresolved_speaker_block_count = 0
        self.episodes_with_unresolved_speakers = 0
        self.non_speaker_numeric_assignment_count = 0
        self.non_literal_speaker_expression_count = 0
        self.branch_issue_count = 0
        self.case_variant_count = 0
        self.control_chars_removed = 0

    def add(self, document: dict[str, Any]) -> None:
        category = document.get("storyCategory", "UNKNOWN")
        self.category_counts[category] += 1
        report = document.get("compatibilityReport", {})
        status = report.get("parserCompatibility", "unknown")
        self.compatibility_counts[status] += 1

        unknown_commands = report.get("unknownCommands", [])
        if unknown_commands:
            self.episodes_with_unknown_commands += 1
        for item in unknown_commands:
            command = item.get("command")
            if isinstance(command, str):
                self.unknown_commands.add(command)
            count = item.get("count", 1)
            self.unknown_command_occurrences += count if isinstance(count, int) else 1

        unknown_ids = report.get("unknownCharacterIds", [])
        if unknown_ids:
            self.episodes_with_unknown_character_ids += 1
        for item in unknown_ids:
            source_id = item.get("sourceCharacterId")
            if isinstance(source_id, str):
                self.unknown_character_ids.add(source_id)

        blocks = list(_all_blocks(document))
        unknown_count = sum(block.get("type") == "unknown" for block in blocks)
        unresolved_count = sum(
            block.get("type") in {"dialogue", "monologue"}
            and block.get("speaker", {}).get("isResolved") is False
            for block in blocks
        )
        self.unknown_block_count += unknown_count
        self.unresolved_speaker_block_count += unresolved_count
        self.episodes_with_unknown_blocks += unknown_count > 0
        self.episodes_with_unresolved_speakers += unresolved_count > 0
        self.non_speaker_numeric_assignment_count += len(
            report.get("nonSpeakerNumericAssignments", [])
        )
        self.non_literal_speaker_expression_count += len(
            report.get("nonLiteralSpeakerExpressions", [])
        )
        self.branch_issue_count += len(report.get("branchIssues", []))
        self.case_variant_count += len(report.get("caseVariants", []))
        removed = report.get("controlCharsRemoved", 0)
        self.control_chars_removed += removed if isinstance(removed, int) else 0

    def as_report(self) -> dict[str, Any]:
        return {
            "categoryEpisodeCounts": dict(sorted(self.category_counts.items())),
            "compatibilityStatusCounts": dict(
                sorted(self.compatibility_counts.items())
            ),
            "unknownBlockCount": self.unknown_block_count,
            "episodesWithUnknownBlocks": self.episodes_with_unknown_blocks,
            "unknownCommandDistinctCount": len(self.unknown_commands),
            "unknownCommandOccurrenceCount": self.unknown_command_occurrences,
            "episodesWithUnknownCommands": self.episodes_with_unknown_commands,
            "unknownCharacterIdDistinctCount": len(self.unknown_character_ids),
            "episodesWithUnknownCharacterIds": (
                self.episodes_with_unknown_character_ids
            ),
            "unresolvedSpeakerBlockCount": self.unresolved_speaker_block_count,
            "episodesWithUnresolvedSpeakers": self.episodes_with_unresolved_speakers,
            "nonSpeakerNumericAssignmentCount": (
                self.non_speaker_numeric_assignment_count
            ),
            "nonLiteralSpeakerExpressionCount": (
                self.non_literal_speaker_expression_count
            ),
            "branchIssueCount": self.branch_issue_count,
            "caseVariantCount": self.case_variant_count,
            "controlCharsRemoved": self.control_chars_removed,
        }


def _write_document(
    document: dict[str, Any],
    output_root: Path,
    validator: Draft7Validator,
    seen_episode_ids: set[str],
) -> None:
    episode_id = document["episodes"][0]["episodeId"]
    if episode_id in seen_episode_ids:
        raise ValueError("duplicate episodeId detected during release normalization")
    errors = list(validator.iter_errors(document))
    if errors:
        raise ValueError(f"normalized story schema validation failed: {len(errors)}")
    seen_episode_ids.add(episode_id)
    category = document["storyCategory"]
    subdir = (
        "character"
        if category.startswith("CHAR_")
        else _CATEGORY_OUTPUT_DIRS.get(category, "other")
    )
    destination = output_root / "normalized" / subdir / f"{episode_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "w", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2)


def _normalize_manifest_episode(
    story: StoryManifestStory,
    episode: StoryManifestEpisode,
    *,
    raw_root: Path,
    manifest_path: Path,
    character_dictionary: CharacterDictionary,
    commands_path: Path,
) -> dict[str, Any]:
    category = resolve_story_category(story.category, story.story_id)
    if category is None:
        raise ValueError(
            "manifest category/storyIdをnormalize categoryへ解決できません"
        )
    input_path = _safe_raw_path(raw_root, episode.raw_path)
    if input_path.name != episode.source_file_name:
        raise ValueError("manifest sourceFileNameとrawPath basenameが一致しません")
    story_metadata, episode_metadata, manifest_source = (
        build_manifest_normalization_metadata(
            story,
            episode,
            manifest_path=str(manifest_path),
            matched_by="raw_path",
        )
    )
    return _normalize_document(
        input_path=input_path,
        story_id=story.story_id,
        category=category,
        episode_id=episode.episode_id,
        character_dictionary=character_dictionary,
        commands_path=commands_path,
        story_metadata=story_metadata,
        episode_metadata=episode_metadata,
        manifest_source=manifest_source,
    )


def _normalize_hscene_exceptions(
    story: StoryManifestStory,
    *,
    raw_root: Path,
    manifest_path: Path,
    character_dictionary: CharacterDictionary,
    commands_path: Path,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    if not story.story_id.startswith("CHAR_HS_"):
        return [], Counter()
    export_dir = _safe_raw_directory(raw_root, story.raw_directory)
    tokenizer = Tokenizer()
    documents: list[dict[str, Any]] = []
    judgments: Counter[str] = Counter()
    manifest_episodes = {episode.episode_id: episode for episode in story.episodes}
    for body_path in find_hscene_body_files(export_dir):
        number = hscene_number(body_path)
        if number is None:
            continue
        base_episode_id = f"{story.story_id}_E{number:02d}"
        base_episode = manifest_episodes.get(base_episode_id)
        if base_episode is None:
            raise ValueError("H_scene bodyに対応するmanifest episodeがありません")
        if _safe_raw_path(raw_root, base_episode.raw_path) != body_path.resolve():
            raise ValueError("H_scene bodyとmanifest rawPathが一致しません")
        body = judge_body_variants(
            body_path,
            base_episode_id=base_episode_id,
            tokenizer=tokenizer,
        )
        for variant in body.variants:
            judgments[variant.judgment] += 1
            if variant.judgment != "exception":
                continue
            if variant.derived_episode_id is None:
                raise ValueError("exception variant episodeIdを導出できません")
            variant_path = variant.variant.path.resolve()
            try:
                variant_path.relative_to(raw_root.resolve())
            except ValueError as exc:
                raise ValueError("H_scene variantがraw root外を参照しています") from exc
            story_metadata, _, _ = build_manifest_normalization_metadata(
                story,
                base_episode,
                manifest_path=str(manifest_path),
                matched_by="raw_path",
            )
            manifest_source = {
                "manifestPath": str(manifest_path),
                "manifestMatched": False,
                "matchedBy": None,
                "sourceFileName": variant_path.name,
                "rawPath": variant_path.relative_to(raw_root.resolve()).as_posix(),
                "publicStoryId": story.public_story_id,
                "publicEpisodeId": None,
                "derivedFromManifestEpisode": base_episode_id,
                "derivationType": "hscene_dynamic_exception",
            }
            trace = {
                "baseEpisodeId": body.base_episode_id,
                "variantPattern": variant.variant.pattern,
                "dupIndex": variant.variant.dup_index,
                "judgment": variant.judgment,
                "bodyIdentifierCount": variant.body_identifier_count,
                "variantIdentifierCount": variant.variant_identifier_count,
                "extraInVariantCount": variant.extra_in_variant_count,
            }
            documents.append(
                _normalize_document(
                    input_path=variant_path,
                    story_id=story.story_id,
                    category="CHAR_HS",
                    episode_id=variant.derived_episode_id,
                    character_dictionary=character_dictionary,
                    commands_path=commands_path,
                    story_metadata=story_metadata,
                    episode_metadata={"metadataStatus": "pending"},
                    manifest_source=manifest_source,
                    variant_trace=trace,
                )
            )
    return documents, judgments


def _normalize_reserved_output(
    *,
    manifest: Any,
    raw_root: Path,
    manifest_path: Path,
    output_root: Path,
    character_dictionary: CharacterDictionary,
    commands_path: Path,
    story_validator: Draft7Validator,
    report_validator: Draft7Validator,
    source_revision: str | None,
) -> dict[str, Any]:
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.tmp-", dir=output_root.parent)
    )
    metrics = _Metrics()
    seen_episode_ids: set[str] = set()
    judgment_counts: Counter[str] = Counter()
    manifest_episode_count = sum(len(story.episodes) for story in manifest.stories)
    dynamic_exception_count = 0
    try:
        for story in manifest.stories:
            for episode in story.episodes:
                document = _normalize_manifest_episode(
                    story,
                    episode,
                    raw_root=raw_root,
                    manifest_path=manifest_path,
                    character_dictionary=character_dictionary,
                    commands_path=commands_path,
                )
                _write_document(
                    document, temporary_root, story_validator, seen_episode_ids
                )
                metrics.add(document)

            exception_documents, story_judgments = _normalize_hscene_exceptions(
                story,
                raw_root=raw_root,
                manifest_path=manifest_path,
                character_dictionary=character_dictionary,
                commands_path=commands_path,
            )
            judgment_counts.update(story_judgments)
            for document in exception_documents:
                _write_document(
                    document, temporary_root, story_validator, seen_episode_ids
                )
                metrics.add(document)
                dynamic_exception_count += 1

        report = {
            "schemaVersion": REPORT_SCHEMA_VERSION,
            "documentType": REPORT_DOCUMENT_TYPE,
            "status": "complete",
            "manifestSha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "manifestStoryCount": len(manifest.stories),
            "manifestEpisodeCount": manifest_episode_count,
            "dynamicExceptionEpisodeCount": dynamic_exception_count,
            "normalizedEpisodeCount": len(seen_episode_ids),
            "invalidCount": 0,
            "skippedCount": 0,
            "hsceneVariantJudgment": {
                "subset": judgment_counts["subset"],
                "exception": judgment_counts["exception"],
                "skippedVr": judgment_counts["skipped_vr"],
            },
            **metrics.as_report(),
        }
        if source_revision is not None:
            report["sourceRevision"] = source_revision
        report_errors = list(report_validator.iter_errors(report))
        if report_errors:
            raise ValueError(
                f"release report schema validation failed: {len(report_errors)}"
            )
        with open(
            temporary_root / "release_scope_normalization_report.json",
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


def normalize_release_scope(
    *,
    raw_root: Path,
    manifest_path: Path,
    output_root: Path,
    characters_path: Path,
    commands_path: Path,
    story_schema_path: Path,
    manifest_schema_path: Path,
    report_schema_path: Path,
    source_revision: str | None = None,
) -> dict[str, Any]:
    """release scopeをno-clobberな一時dirで全件処理し、成功時だけ公開する。"""
    if (
        source_revision is not None
        and re.fullmatch(r"[0-9a-f]{40}", source_revision) is None
    ):
        raise ValueError("source revisionは40文字の小文字SHAである必要があります")
    if not raw_root.is_dir() or not manifest_path.is_file():
        raise FileNotFoundError("raw rootまたはmanifestが見つかりません")
    _validate_manifest(manifest_path, manifest_schema_path)
    manifest = load_story_manifest(manifest_path)
    character_dictionary = CharacterDictionary()
    character_dictionary.load(characters_path)
    story_validator = _load_validator(story_schema_path)
    report_validator = _load_validator(report_schema_path)

    with _reserve_output(output_root):
        return _normalize_reserved_output(
            manifest=manifest,
            raw_root=raw_root,
            manifest_path=manifest_path,
            output_root=output_root,
            character_dictionary=character_dictionary,
            commands_path=commands_path,
            story_validator=story_validator,
            report_validator=report_validator,
            source_revision=source_revision,
        )
