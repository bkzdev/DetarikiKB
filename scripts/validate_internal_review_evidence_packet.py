#!/usr/bin/env python3
"""Internal Review Evidence Packet v1を安全に検証するread-only CLI。

Packetはraw text・内部IDを含みうるため、入力は固定root配下のopaqueな
``packetId``でのみ指定する。path/Git/reparse point境界を確認する前に
Packet内容を読み込まず、consoleにもraw内容・内部ID・local pathを出さない。

Exit codes:
    0: schema・bundle内semantic validation成功（期限切れwarningを含みうる）
    1: Packet/selectionの内容検証失敗
    2: CLI設定、path/Git境界、schema読込、IO error
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
_PACKET_ROOT = _PROJECT_ROOT / "workspace" / "review_packets" / "evidence"
_SELECTION_ROOT = (
    _PROJECT_ROOT / "workspace" / "local_inputs" / "evidence_packet_selection"
)

_SCHEMA_PATHS = {
    "manifest": (
        _PROJECT_ROOT
        / "schemas"
        / "internal_review_evidence_packet_manifest.schema.json"
    ),
    "story": (
        _PROJECT_ROOT / "schemas" / "internal_review_evidence_packet_story.schema.json"
    ),
    "selection": (
        _PROJECT_ROOT
        / "schemas"
        / "internal_review_evidence_packet_selection.schema.json"
    ),
    "report": (
        _PROJECT_ROOT
        / "schemas"
        / "internal_review_evidence_packet_validation_report.schema.json"
    ),
}

_PACKET_ID_PATTERN = re.compile(r"^erp-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")
_SELECTION_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.json$")
_INTERNAL_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_PUBLIC_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_STORY_COMPONENT_PATTERN = re.compile(r"^stories/story-[0-9]{4}\.json$")

_MAPPING_PATH = "mappings/evidence-id-map.csv"
_REPORT_PATH = "reports/validation.json"
_MAPPING_FIELDNAMES = [
    "storyId",
    "publicStoryId",
    "episodeId",
    "publicEpisodeId",
    "evidenceId",
    "publicEvidenceId",
    "evidenceType",
    "sceneId",
    "blockId",
    "episodeOrder",
    "publicEpisodeIdSource",
    "registryMatched",
    "registryConflict",
    "registryPublicEpisodeId",
]
_EVIDENCE_TYPES = {
    "dialogue",
    "monologue",
    "narration",
    "choice",
    "stage_direction",
    "speaker_label",
    "scene",
    "episode",
    "story",
    "unknown",
}
_PUBLIC_DEFAULT_TYPES = {
    "dialogue",
    "monologue",
    "narration",
    "choice",
    "unknown",
}

_WINDOWS_ABSOLUTE_PATH = re.compile(r"(?i)(?:^|[\s\"'(<])(?:[A-Z]:[\\/])")
_UNC_PATH = re.compile(r"\\\\[^\\\s]+\\[^\\\s]+")
_POSIX_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9:/])/(?:[^/\s]+/)+[^/\s]*")


@dataclass(frozen=True)
class ValidationIssue:
    """consoleへ安全に出せる構造化issue。秘密値や自由記述を持たない。"""

    code: str
    severity: str = "error"
    component_path: str | None = None
    review_story_key: str | None = None
    review_entry_id: str | None = None


@dataclass
class PacketValidationResult:
    packet_id: str
    story_count: int
    entry_count: int
    component_count: int
    issues: list[ValidationIssue]

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]


class ConfigError(Exception):
    """messageを外部出力せず、安全なcodeだけを運ぶconfig/IO error。"""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Internal Review Evidence Packet v1、またはlocal selection JSONを"
            "read-onlyで検証する"
        )
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--packet-id",
        help="固定root配下のopaque packetId（pathは指定しない）",
    )
    target.add_argument(
        "--selection-file",
        help=(
            "workspace/local_inputs/evidence_packet_selection/直下のJSON file名"
            "（pathは指定しない）"
        ),
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="成功時のconsole出力を抑制する",
    )
    return parser.parse_args()


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(_PROJECT_ROOT), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise ConfigError("git-command-unavailable") from exc


def _repo_relative_posix(path: Path) -> str:
    try:
        return path.resolve().relative_to(_PROJECT_ROOT).as_posix()
    except (OSError, ValueError) as exc:
        raise ConfigError("path-outside-repository") from exc


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ConfigError("path-inspection-failed") from exc
    if stat.S_ISLNK(info.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


def _check_existing_ancestors(path: Path) -> None:
    try:
        relative = path.absolute().relative_to(_PROJECT_ROOT.absolute())
    except ValueError as exc:
        raise ConfigError("path-outside-repository") from exc
    current = _PROJECT_ROOT
    if _is_link_or_reparse(current):
        raise ConfigError("reparse-point-rejected")
    for part in relative.parts:
        current = current / part
        if not current.exists():
            break
        if _is_link_or_reparse(current):
            raise ConfigError("reparse-point-rejected")


def _check_tree_has_no_links(root: Path) -> None:
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    if _is_link_or_reparse(child):
                        raise ConfigError("reparse-point-rejected")
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(child)
        except ConfigError:
            raise
        except OSError as exc:
            raise ConfigError("path-inspection-failed") from exc


def _check_git_boundary(fixed_root: Path, target: Path) -> None:
    top_level = _run_git(["rev-parse", "--show-toplevel"])
    if top_level.returncode != 0:
        raise ConfigError("not-a-git-worktree")
    try:
        actual_root = Path(top_level.stdout.strip()).resolve()
    except OSError as exc:
        raise ConfigError("git-root-inspection-failed") from exc
    if actual_root != _PROJECT_ROOT:
        raise ConfigError("unexpected-git-worktree")

    for path in (fixed_root, target):
        relative = _repo_relative_posix(path)
        ignored = _run_git(["check-ignore", "--no-index", "-q", "--", relative])
        if ignored.returncode != 0:
            raise ConfigError("path-is-not-git-ignored")

    tracked_root = _run_git(["ls-files", "--", _repo_relative_posix(fixed_root)])
    tracked_target = _run_git(["ls-files", "--", _repo_relative_posix(target)])
    if tracked_root.returncode != 0 or tracked_target.returncode != 0:
        raise ConfigError("git-tracked-check-failed")
    if tracked_root.stdout.strip() or tracked_target.stdout.strip():
        raise ConfigError("tracked-packet-path-rejected")


def _preflight_existing_path(fixed_root: Path, target: Path) -> None:
    _check_existing_ancestors(fixed_root)
    _check_existing_ancestors(target)
    try:
        resolved_root = fixed_root.resolve()
        resolved_target = target.resolve()
        resolved_target.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise ConfigError("path-outside-fixed-root") from exc
    if not target.exists():
        raise ConfigError("input-not-found")
    _check_git_boundary(fixed_root, target)
    if target.is_dir():
        _check_tree_has_no_links(target)
    elif _is_link_or_reparse(target):
        raise ConfigError("reparse-point-rejected")


def _load_schema(schema_name: str) -> dict[str, Any]:
    try:
        with _SCHEMA_PATHS[schema_name].open(encoding="utf-8") as handle:
            schema = json.load(handle)
        Draft7Validator.check_schema(schema)
    except (KeyError, OSError, UnicodeError, json.JSONDecodeError, SchemaError) as exc:
        raise ConfigError("schema-unavailable") from exc
    return schema


def _load_json_document(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise ConfigError("component-read-failed") from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("component-json-invalid") from exc
    if not isinstance(data, dict):
        raise ValueError("component-json-invalid")
    return data


def _schema_issues(
    data: dict[str, Any],
    schema: dict[str, Any],
    *,
    code: str,
    component_path: str,
) -> list[ValidationIssue]:
    errors = sorted(
        Draft7Validator(schema).iter_errors(data), key=lambda error: list(error.path)
    )
    if not errors:
        return []
    return [ValidationIssue(code=code, component_path=component_path) for _ in errors]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_component_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ConfigError("component-read-failed") from exc


def _safe_component_target(packet_dir: Path, relative_path: str) -> Path:
    pure = PurePosixPath(relative_path)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise ConfigError("component-path-invalid")
    target = packet_dir.joinpath(*pure.parts)
    try:
        target.resolve().relative_to(packet_dir.resolve())
    except (OSError, ValueError) as exc:
        raise ConfigError("component-path-invalid") from exc
    return target


def _contains_forbidden_path(value: str) -> bool:
    return bool(
        _WINDOWS_ABSOLUTE_PATH.search(value)
        or _UNC_PATH.search(value)
        or _POSIX_ABSOLUTE_PATH.search(value)
        or ".dec" in value.lower()
    )


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_strings(child)


def _parse_utc_z(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except (TypeError, ValueError):
        return None


def _validate_retention(manifest: dict[str, Any]) -> list[ValidationIssue]:
    created = _parse_utc_z(manifest.get("createdAt"))
    expires = _parse_utc_z(manifest.get("expiresAt"))
    if created is None or expires is None:
        return [ValidationIssue("retention-timestamp-invalid")]
    duration = expires - created
    issues: list[ValidationIssue] = []
    if duration < timedelta(days=1) or duration > timedelta(days=30):
        issues.append(ValidationIssue("retention-window-invalid"))
    if datetime.now(timezone.utc) > expires:
        issues.append(ValidationIssue("packet-expired", severity="warning"))
    return issues


def _actual_component_files(packet_dir: Path) -> set[str]:
    files: set[str] = set()
    try:
        for path in packet_dir.rglob("*"):
            if path.is_file():
                relative = path.relative_to(packet_dir).as_posix()
                if relative != "manifest.json":
                    files.add(relative)
    except OSError as exc:
        raise ConfigError("component-enumeration-failed") from exc
    return files


def _validate_component_manifest(
    packet_dir: Path, manifest: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    components: dict[str, dict[str, Any]] = {}
    for component in manifest.get("components", []):
        relative = component.get("relativePath")
        if relative in components:
            issues.append(
                ValidationIssue("duplicate-component-path", component_path=relative)
            )
            continue
        components[relative] = component

    required_paths = {_MAPPING_PATH, _REPORT_PATH}
    if not required_paths.issubset(components):
        issues.append(ValidationIssue("required-component-missing"))
    if not any(_STORY_COMPONENT_PATTERN.fullmatch(path) for path in components):
        issues.append(ValidationIssue("story-component-missing"))

    expected = set(components)
    actual = _actual_component_files(packet_dir)
    if expected != actual:
        issues.append(ValidationIssue("component-file-set-mismatch"))

    for relative, component in components.items():
        target = _safe_component_target(packet_dir, relative)
        if not target.is_file():
            continue
        digest = _sha256_bytes(_read_component_bytes(target))
        if digest != component.get("sha256"):
            issues.append(
                ValidationIssue("component-digest-mismatch", component_path=relative)
            )
        expected_media = "text/csv" if relative == _MAPPING_PATH else "application/json"
        if component.get("mediaType") != expected_media:
            issues.append(
                ValidationIssue("component-media-type-invalid", component_path=relative)
            )
    return components, issues


def _read_mapping_rows(
    path: Path,
) -> tuple[list[dict[str, str]], list[ValidationIssue]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != _MAPPING_FIELDNAMES:
                return [], [
                    ValidationIssue(
                        "mapping-header-invalid", component_path=_MAPPING_PATH
                    )
                ]
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        if isinstance(exc, OSError):
            raise ConfigError("component-read-failed") from exc
        return [], [
            ValidationIssue("mapping-csv-invalid", component_path=_MAPPING_PATH)
        ]
    expected_fields = set(_MAPPING_FIELDNAMES)
    if any(
        set(row) != expected_fields
        or any(not isinstance(row.get(name), str) for name in _MAPPING_FIELDNAMES)
        for row in rows
    ):
        return [], [
            ValidationIssue("mapping-row-shape-invalid", component_path=_MAPPING_PATH)
        ]
    return rows, []


def _valid_internal_id(value: str) -> bool:
    return bool(_INTERNAL_ID_PATTERN.fullmatch(value))


def _valid_public_id_or_empty(value: str) -> bool:
    return not value or bool(_PUBLIC_ID_PATTERN.fullmatch(value))


def _mapping_issue(code: str) -> ValidationIssue:
    return ValidationIssue(code, component_path=_MAPPING_PATH)


def _validate_mapping_row_fields(row: dict[str, str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    required_internal_ids = (row["storyId"], row["episodeId"], row["evidenceId"])
    optional_internal_ids = (row["sceneId"], row["blockId"])
    public_ids = (
        row["publicStoryId"],
        row["publicEpisodeId"],
        row["publicEvidenceId"],
        row["registryPublicEpisodeId"],
    )
    if not all(_valid_internal_id(value) for value in required_internal_ids) or any(
        value and not _valid_internal_id(value) for value in optional_internal_ids
    ):
        issues.append(_mapping_issue("mapping-internal-id-invalid"))
    if not all(_valid_public_id_or_empty(value) for value in public_ids):
        issues.append(_mapping_issue("mapping-public-id-invalid"))
    if row["evidenceType"] not in _EVIDENCE_TYPES:
        issues.append(_mapping_issue("mapping-evidence-type-invalid"))
    try:
        valid_episode_order = int(row["episodeOrder"]) >= 1
    except ValueError:
        valid_episode_order = False
    if not valid_episode_order:
        issues.append(_mapping_issue("mapping-episode-order-invalid"))
    if any(_contains_forbidden_path(value) for value in row.values()):
        issues.append(_mapping_issue("mapping-path-like-value"))
    return issues


def _validate_mapping_registry_fields(row: dict[str, str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    source = row["publicEpisodeIdSource"]
    matched = row["registryMatched"]
    conflict = row["registryConflict"]
    if source not in {"input", "registry", "missing"}:
        issues.append(_mapping_issue("mapping-public-id-source-invalid"))
    if matched not in {"True", "False"} or conflict not in {"True", "False"}:
        issues.append(_mapping_issue("mapping-boolean-invalid"))
    if conflict == "True":
        issues.append(_mapping_issue("mapping-registry-conflict"))

    registry_expected = source == "registry"
    if (matched == "True") != registry_expected:
        issues.append(_mapping_issue("mapping-registry-match-invalid"))
    public_episode_id = row["publicEpisodeId"]
    registry_episode_id = row["registryPublicEpisodeId"]
    source_id_inconsistent = (
        source == "missing" and (public_episode_id or registry_episode_id)
    ) or (source in {"input", "registry"} and not public_episode_id)
    registry_id_inconsistent = (registry_expected and not registry_episode_id) or (
        registry_episode_id and registry_episode_id != public_episode_id
    )
    if source_id_inconsistent or registry_id_inconsistent:
        issues.append(_mapping_issue("mapping-registry-id-invalid"))
    return issues


def _register_mapping_value(
    values: dict[Any, Any],
    key: Any,
    value: Any,
) -> bool:
    if key not in values:
        values[key] = value
        return True
    return values[key] == value


def _validate_mapping_scope_consistency(
    rows: list[dict[str, str]],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    story_to_public: dict[str, str] = {}
    episode_to_metadata: dict[tuple[str, str], tuple[str, ...]] = {}
    public_story_to_internal: dict[str, str] = {}
    public_episode_to_internal: dict[str, tuple[str, str]] = {}

    for row in rows:
        internal_story = row["storyId"]
        internal_episode = (internal_story, row["episodeId"])
        if not _register_mapping_value(
            story_to_public, internal_story, row["publicStoryId"]
        ) or not _register_mapping_value(
            episode_to_metadata,
            internal_episode,
            (
                row["publicEpisodeId"],
                row["episodeOrder"],
                row["publicEpisodeIdSource"],
                row["registryMatched"],
                row["registryConflict"],
                row["registryPublicEpisodeId"],
            ),
        ):
            issues.append(_mapping_issue("mapping-story-episode-conflict"))

        public_story = row["publicStoryId"]
        public_episode = row["publicEpisodeId"]
        if public_story and not _register_mapping_value(
            public_story_to_internal, public_story, internal_story
        ):
            issues.append(_mapping_issue("mapping-public-story-id-conflict"))
        if public_episode and not _register_mapping_value(
            public_episode_to_internal, public_episode, internal_episode
        ):
            issues.append(_mapping_issue("mapping-public-episode-id-conflict"))
    return issues


def _validate_mapping_rows(
    rows: list[dict[str, str]],
) -> tuple[dict[tuple[str, str, str], dict[str, str]], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    by_internal_key: dict[tuple[str, str, str], dict[str, str]] = {}
    public_evidence_ids: set[str] = set()

    for row in rows:
        key = (row["storyId"], row["episodeId"], row["evidenceId"])
        if key in by_internal_key:
            issues.append(_mapping_issue("mapping-internal-key-duplicate"))
        else:
            by_internal_key[key] = row
        issues.extend(_validate_mapping_row_fields(row))
        issues.extend(_validate_mapping_registry_fields(row))
        public_evidence_id = row["publicEvidenceId"]
        if public_evidence_id:
            if public_evidence_id in public_evidence_ids:
                issues.append(_mapping_issue("mapping-public-evidence-id-duplicate"))
            public_evidence_ids.add(public_evidence_id)
    issues.extend(_validate_mapping_scope_consistency(rows))
    return by_internal_key, issues


def _validate_entry_semantics(
    entry: dict[str, Any],
    *,
    story_key: str,
) -> list[ValidationIssue]:
    entry_id = entry.get("reviewEntryId")
    component_path = f"stories/{story_key}.json"
    issues: list[ValidationIssue] = []
    raw_content = entry.get("rawContent")
    if isinstance(raw_content, dict):
        if sum(len(value) for value in raw_content.get("arguments", [])) > 2048:
            issues.append(
                ValidationIssue(
                    "raw-arguments-total-too-long",
                    component_path=component_path,
                    review_story_key=story_key,
                    review_entry_id=entry_id,
                )
            )

    for side in ("before", "after"):
        for context in (entry.get("context") or {}).get(side, []):
            truncated = context.get("truncated")
            digest = context.get("originalTextSha256")
            if (truncated is True and not _SHA256_PATTERN.fullmatch(digest or "")) or (
                truncated is False and digest is not None
            ):
                issues.append(
                    ValidationIssue(
                        "context-digest-rule-invalid",
                        component_path=component_path,
                        review_story_key=story_key,
                        review_entry_id=entry_id,
                    )
                )

    for diagnostic in entry.get("diagnostics", []):
        if diagnostic.get("reviewEntryId") != entry_id:
            issues.append(
                ValidationIssue(
                    "diagnostic-entry-key-mismatch",
                    component_path=component_path,
                    review_story_key=story_key,
                    review_entry_id=entry_id,
                )
            )

    if any(_contains_forbidden_path(value) for value in _iter_strings(entry)):
        issues.append(
            ValidationIssue(
                "entry-path-like-value",
                component_path=component_path,
                review_story_key=story_key,
                review_entry_id=entry_id,
            )
        )
    return issues


def _validate_story_mapping_cross_reference(
    story: dict[str, Any],
    mapping_by_key: dict[tuple[str, str, str], dict[str, str]],
    *,
    selection_mode: str,
) -> tuple[set[tuple[str, str, str]], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    matched: set[tuple[str, str, str]] = set()
    story_key = story["reviewStoryKey"]
    internal_story = story["identifiers"]["internal"]["storyId"]
    public_story = story["identifiers"]["public"]["publicStoryId"]

    for entry in story["entries"]:
        entry_id = entry["reviewEntryId"]
        internal = entry["identifiers"]["internal"]
        public = entry["identifiers"]["public"]
        key = (internal_story, internal["episodeId"], internal["evidenceId"])
        row = mapping_by_key.get(key)
        issue_fields = {
            "component_path": f"stories/{story_key}.json",
            "review_story_key": story_key,
            "review_entry_id": entry_id,
        }
        if row is None:
            issues.append(ValidationIssue("entry-mapping-missing", **issue_fields))
            continue
        matched.add(key)
        comparisons = {
            "publicStoryId": public_story,
            "publicEpisodeId": public["publicEpisodeId"],
            "publicEvidenceId": public["publicEvidenceId"],
            "evidenceType": entry["evidenceType"],
            "sceneId": internal["sceneId"],
            "blockId": internal["blockId"],
        }
        if any(
            (row[name] or None) != expected for name, expected in comparisons.items()
        ):
            issues.append(ValidationIssue("entry-mapping-mismatch", **issue_fields))
        if entry["evidenceType"] in _PUBLIC_DEFAULT_TYPES and any(
            value is None
            for value in (
                public_story,
                public["publicEpisodeId"],
                public["publicEvidenceId"],
            )
        ):
            issues.append(ValidationIssue("public-id-required", **issue_fields))
        if (
            selection_mode == "public-candidate"
            and entry["evidenceType"] not in _PUBLIC_DEFAULT_TYPES
        ):
            issues.append(
                ValidationIssue("public-candidate-type-invalid", **issue_fields)
            )
    return matched, issues


def _validate_report_semantics(
    report: dict[str, Any],
    *,
    packet_id: str,
    story_count: int,
    entry_count: int,
    component_count: int,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    expected = {
        "packetId": packet_id,
        "storyCount": story_count,
        "entryCount": entry_count,
        "componentCount": component_count,
    }
    if any(report.get(name) != value for name, value in expected.items()):
        issues.append(
            ValidationIssue("safe-report-count-mismatch", component_path=_REPORT_PATH)
        )
    if report.get("warningCount") != len(report.get("issues", [])):
        issues.append(
            ValidationIssue(
                "safe-report-warning-count-mismatch", component_path=_REPORT_PATH
            )
        )
    if any(_contains_forbidden_path(value) for value in _iter_strings(report)):
        issues.append(
            ValidationIssue("safe-report-path-like-value", component_path=_REPORT_PATH)
        )
    return issues


def _collect_bundle_internal_ids(
    mapping_by_key: dict[tuple[str, str, str], dict[str, str]],
    stories: list[dict[str, Any]],
) -> set[str]:
    internal_ids: set[str] = set()
    mapping_fields = ("storyId", "episodeId", "evidenceId", "sceneId", "blockId")
    for row in mapping_by_key.values():
        internal_ids.update(row[name] for name in mapping_fields if row[name])

    for story in stories:
        internal_ids.update(_iter_strings(story["identifiers"]["internal"]))
        for entry in story["entries"]:
            internal_ids.update(_iter_strings(entry["identifiers"]["internal"]))
            speaker = entry.get("speaker")
            if isinstance(speaker, dict):
                internal_ids.update(
                    value
                    for name in ("sourceCharacterId", "speakerId")
                    if isinstance((value := speaker.get(name)), str) and value
                )
            extraction = entry.get("extraction")
            if isinstance(extraction, dict):
                internal_ids.update(
                    candidate["candidateId"]
                    for candidate in extraction["candidates"]
                    if candidate["candidateId"]
                )
    return internal_ids


def _safe_component_contains_internal_id(
    component: dict[str, Any],
    internal_ids: set[str],
) -> bool:
    safe_strings = tuple(_iter_strings(component))
    for internal_id in internal_ids:
        for value in safe_strings:
            if value == internal_id:
                return True
            if (
                len(internal_id) >= 6
                and _INTERNAL_ID_PATTERN.fullmatch(internal_id)
                and internal_id in value
            ):
                return True
    return False


def _validate_safe_components(
    manifest: dict[str, Any],
    report: dict[str, Any] | None,
    internal_ids: set[str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if _safe_component_contains_internal_id(manifest, internal_ids):
        issues.append(
            ValidationIssue(
                "safe-component-internal-id-exposed",
                component_path="manifest.json",
            )
        )
    if report is not None and _safe_component_contains_internal_id(
        report, internal_ids
    ):
        issues.append(
            ValidationIssue(
                "safe-component-internal-id-exposed",
                component_path=_REPORT_PATH,
            )
        )
    return issues


def _load_manifest_for_validation(
    packet_dir: Path,
    packet_id: str,
    schema: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[ValidationIssue]]:
    manifest_path = packet_dir / "manifest.json"
    if not manifest_path.is_file():
        return None, [ValidationIssue("manifest-missing")]
    try:
        manifest = _load_json_document(manifest_path)
    except ValueError:
        return None, [ValidationIssue("manifest-json-invalid")]
    issues = _schema_issues(
        manifest,
        schema,
        code="manifest-schema-invalid",
        component_path="manifest.json",
    )
    if issues:
        return None, issues
    if manifest["packetId"] != packet_id:
        issues.append(ValidationIssue("manifest-packet-id-mismatch"))
    issues.extend(_validate_retention(manifest))
    if any(_contains_forbidden_path(value) for value in _iter_strings(manifest)):
        issues.append(ValidationIssue("manifest-path-like-value"))
    return manifest, issues


def _load_mapping_component(
    packet_dir: Path,
    components: dict[str, dict[str, Any]],
) -> tuple[dict[tuple[str, str, str], dict[str, str]], list[ValidationIssue]]:
    if _MAPPING_PATH not in components:
        return {}, []
    mapping_path = _safe_component_target(packet_dir, _MAPPING_PATH)
    if not mapping_path.is_file():
        return {}, []

    rows, issues = _read_mapping_rows(mapping_path)
    mapping_by_key, mapping_issues = _validate_mapping_rows(rows)
    issues.extend(mapping_issues)
    if components[_MAPPING_PATH].get("recordCount") != len(rows):
        issues.append(_mapping_issue("component-record-count-mismatch"))
    return mapping_by_key, issues


def _validate_story_identity(
    story: dict[str, Any],
    relative: str,
    review_story_keys: set[str],
    review_entry_ids: set[str],
    internal_story_ids: set[str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    story_key = story["reviewStoryKey"]
    if relative != f"stories/{story_key}.json":
        issues.append(
            ValidationIssue(
                "story-key-path-mismatch",
                component_path=relative,
                review_story_key=story_key,
            )
        )
    if story_key in review_story_keys:
        issues.append(
            ValidationIssue(
                "review-story-key-duplicate",
                component_path=relative,
                review_story_key=story_key,
            )
        )
    review_story_keys.add(story_key)
    internal_story_id = story["identifiers"]["internal"]["storyId"]
    if internal_story_id in internal_story_ids:
        issues.append(
            ValidationIssue(
                "internal-story-id-duplicate",
                component_path=relative,
                review_story_key=story_key,
            )
        )
    internal_story_ids.add(internal_story_id)

    for entry in story["entries"]:
        entry_id = entry["reviewEntryId"]
        if entry_id in review_entry_ids:
            issues.append(
                ValidationIssue(
                    "review-entry-id-duplicate",
                    component_path=relative,
                    review_story_key=story_key,
                    review_entry_id=entry_id,
                )
            )
        review_entry_ids.add(entry_id)
        issues.extend(_validate_entry_semantics(entry, story_key=story_key))
    return issues


def _load_story_components(
    packet_dir: Path,
    components: dict[str, dict[str, Any]],
    schema: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    stories: list[dict[str, Any]] = []
    review_story_keys: set[str] = set()
    review_entry_ids: set[str] = set()
    internal_story_ids: set[str] = set()
    story_paths = sorted(
        path for path in components if _STORY_COMPONENT_PATTERN.fullmatch(path)
    )

    for relative in story_paths:
        target = _safe_component_target(packet_dir, relative)
        if not target.is_file():
            continue
        try:
            story = _load_json_document(target)
        except ValueError:
            issues.append(
                ValidationIssue("story-json-invalid", component_path=relative)
            )
            continue
        schema_issues = _schema_issues(
            story,
            schema,
            code="story-schema-invalid",
            component_path=relative,
        )
        issues.extend(schema_issues)
        if schema_issues:
            continue
        issues.extend(
            _validate_story_identity(
                story,
                relative,
                review_story_keys,
                review_entry_ids,
                internal_story_ids,
            )
        )
        if components[relative].get("recordCount") != len(story["entries"]):
            issues.append(
                ValidationIssue(
                    "component-record-count-mismatch", component_path=relative
                )
            )
        stories.append(story)
    return stories, issues


def _validate_story_mapping_set(
    stories: list[dict[str, Any]],
    mapping_by_key: dict[tuple[str, str, str], dict[str, str]],
    *,
    selection_mode: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    matched_mapping_keys: set[tuple[str, str, str]] = set()
    for story in stories:
        matched, cross_issues = _validate_story_mapping_cross_reference(
            story,
            mapping_by_key,
            selection_mode=selection_mode,
        )
        matched_mapping_keys.update(matched)
        issues.extend(cross_issues)
    if matched_mapping_keys != set(mapping_by_key):
        issues.append(_mapping_issue("mapping-entry-set-mismatch"))
    return issues


def _validate_report_component(
    packet_dir: Path,
    components: dict[str, dict[str, Any]],
    schema: dict[str, Any],
    *,
    packet_id: str,
    story_count: int,
    entry_count: int,
) -> tuple[dict[str, Any] | None, list[ValidationIssue]]:
    if _REPORT_PATH not in components:
        return None, []
    report_path = _safe_component_target(packet_dir, _REPORT_PATH)
    if not report_path.is_file():
        return None, []
    try:
        report = _load_json_document(report_path)
    except ValueError:
        return None, [
            ValidationIssue("safe-report-json-invalid", component_path=_REPORT_PATH),
        ]

    issues = _schema_issues(
        report,
        schema,
        code="safe-report-schema-invalid",
        component_path=_REPORT_PATH,
    )
    if issues:
        return report, issues
    issues.extend(
        _validate_report_semantics(
            report,
            packet_id=packet_id,
            story_count=story_count,
            entry_count=entry_count,
            component_count=len(components),
        )
    )
    if components[_REPORT_PATH].get("recordCount") != len(report["issues"]):
        issues.append(
            ValidationIssue(
                "component-record-count-mismatch",
                component_path=_REPORT_PATH,
            )
        )
    return report, issues


def validate_packet_directory(
    packet_dir: Path, packet_id: str
) -> PacketValidationResult:
    """境界確認済みPacket directoryのschema・semantic整合性を検証する。"""
    schemas = {name: _load_schema(name) for name in ("manifest", "story", "report")}
    manifest, issues = _load_manifest_for_validation(
        packet_dir,
        packet_id,
        schemas["manifest"],
    )
    if manifest is None:
        return PacketValidationResult(packet_id, 0, 0, 0, issues)

    components, component_issues = _validate_component_manifest(packet_dir, manifest)
    issues.extend(component_issues)
    mapping_by_key, mapping_issues = _load_mapping_component(packet_dir, components)
    issues.extend(mapping_issues)
    stories, story_issues = _load_story_components(
        packet_dir,
        components,
        schemas["story"],
    )
    issues.extend(story_issues)
    issues.extend(
        _validate_story_mapping_set(
            stories,
            mapping_by_key,
            selection_mode=manifest["selectionMode"],
        )
    )
    entry_count = sum(len(story["entries"]) for story in stories)
    report, report_issues = _validate_report_component(
        packet_dir,
        components,
        schemas["report"],
        packet_id=packet_id,
        story_count=len(stories),
        entry_count=entry_count,
    )
    issues.extend(report_issues)
    internal_ids = _collect_bundle_internal_ids(mapping_by_key, stories)
    issues.extend(_validate_safe_components(manifest, report, internal_ids))

    return PacketValidationResult(
        packet_id=packet_id,
        story_count=len(stories),
        entry_count=entry_count,
        component_count=len(components),
        issues=issues,
    )


def validate_selection_document(selection_path: Path) -> list[ValidationIssue]:
    schema = _load_schema("selection")
    try:
        selection = _load_json_document(selection_path)
    except ValueError:
        return [ValidationIssue("selection-json-invalid")]
    return _schema_issues(
        selection,
        schema,
        code="selection-schema-invalid",
        component_path="selection.json",
    )


def _print_issue(issue: ValidationIssue) -> None:
    fields = [f"code={issue.code}", f"severity={issue.severity}"]
    if issue.component_path is not None:
        fields.append(f"component={issue.component_path}")
    if issue.review_story_key is not None:
        fields.append(f"story={issue.review_story_key}")
    if issue.review_entry_id is not None:
        fields.append(f"entry={issue.review_entry_id}")
    print("  - " + " ".join(fields), file=sys.stderr)


def _print_config_error(code: str) -> None:
    print(f"[validate] status=config-error code={code}", file=sys.stderr)


def _validate_packet_cli(packet_id: str, quiet: bool) -> int:
    if not _PACKET_ID_PATTERN.fullmatch(packet_id):
        _print_config_error("packet-id-invalid")
        return 2
    packet_dir = _PACKET_ROOT / packet_id
    _preflight_existing_path(_PACKET_ROOT, packet_dir)
    result = validate_packet_directory(packet_dir, packet_id)
    if result.errors:
        print(
            f"[validate] packet={packet_id} status=invalid "
            f"errors={len(result.errors)} warnings={len(result.warnings)}",
            file=sys.stderr,
        )
        for issue in result.issues:
            _print_issue(issue)
        return 1
    if not quiet:
        print(
            f"[validate] packet={packet_id} status=valid "
            f"stories={result.story_count} entries={result.entry_count} "
            f"components={result.component_count} warnings={len(result.warnings)}"
        )
        for issue in result.warnings:
            fields = [f"code={issue.code}", "severity=warning"]
            print("  - " + " ".join(fields))
    return 0


def _validate_selection_cli(filename: str, quiet: bool) -> int:
    if not _SELECTION_FILENAME_PATTERN.fullmatch(filename):
        _print_config_error("selection-filename-invalid")
        return 2
    selection_path = _SELECTION_ROOT / filename
    _preflight_existing_path(_SELECTION_ROOT, selection_path)
    issues = validate_selection_document(selection_path)
    if issues:
        print(
            f"[validate] selection status=invalid errors={len(issues)}",
            file=sys.stderr,
        )
        for issue in issues:
            _print_issue(issue)
        return 1
    if not quiet:
        print("[validate] selection status=valid")
    return 0


def main() -> int:
    args = parse_args()
    try:
        if args.packet_id is not None:
            return _validate_packet_cli(args.packet_id, args.quiet)
        return _validate_selection_cli(args.selection_file, args.quiet)
    except ConfigError as exc:
        _print_config_error(exc.code)
        return 2


if __name__ == "__main__":
    sys.exit(main())
