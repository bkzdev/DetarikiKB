#!/usr/bin/env python3
"""固定workspace内のCanonical Timeline review packetをread-only検証する。"""

from __future__ import annotations

import argparse
import json
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft7Validator, FormatChecker
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.extractor.canonical_timeline_review_packet_consistency import (  # noqa: E402
    validate_canonical_timeline_review_packet_consistency,
)

_PACKET_ROOT = _PROJECT_ROOT / "workspace" / "review_packets" / "canonical_timeline"
_PACKET_SCHEMA_PATH = (
    _PROJECT_ROOT / "schemas" / "canonical_timeline_review_packet.schema.json"
)
_CANONICAL_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "canonical_timeline.schema.json"
_PACKET_NAME_PATTERN = re.compile(
    r"^canonical_timeline_review_[a-z0-9][a-z0-9_-]{0,63}\.json$"
)
_WINDOWS_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9:/\\])[A-Za-z]:[\\/]")
_UNC_PATH = re.compile(r"(?<![A-Za-z0-9\\])\\\\[^\\\s]+[\\/]")
_UNIX_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9:/])/(?!/)[^/\s)]+(?:/[^/\s)]*)*")
_URL = re.compile(r"(?i)\b(?:https?|ftp|file)://")
_RAW_COMMAND = re.compile(r"(?<![A-Za-z0-9_.+-])@[A-Za-z_][A-Za-z0-9_]*")
_RAW_MARKERS = (".dec", "$num", "$value", "<script")
_INTERNAL_ID_CHARACTERS = "A-Za-z0-9_-"


class ConfigError(Exception):
    """入力内容をechoせず固定codeで表す設定エラー。"""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ValidationResult:
    issue_codes: tuple[str, ...]
    edge_count: int = 0
    confirmed_count: int = 0
    pending_count: int = 0
    rejected_count: int = 0
    needs_more_context_count: int = 0

    @property
    def is_valid(self) -> bool:
        return not self.issue_codes


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="workspace内のCanonical Timeline review packetを検証する"
    )
    parser.add_argument(
        "--packet-name",
        required=True,
        help="workspace/review_packets/canonical_timeline直下のbasename",
    )
    parser.add_argument("--quiet", "-q", action="store_true")
    return parser.parse_args(argv)


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError as exc:
        raise ConfigError("git-command-failed") from exc


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ConfigError("path-inspection-failed") from exc
    if stat.S_ISLNK(info.st_mode):
        return True
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(getattr(info, "st_file_attributes", 0) & flag)


def _repo_relative(path: Path) -> Path:
    try:
        return path.absolute().relative_to(_PROJECT_ROOT.absolute())
    except ValueError as exc:
        raise ConfigError("path-outside-repository") from exc


def _check_ancestors(relative: Path) -> None:
    current = _PROJECT_ROOT
    if _is_reparse(current):
        raise ConfigError("reparse-point-rejected")
    for part in relative.parts:
        current = current / part
        if not current.exists():
            break
        if _is_reparse(current):
            raise ConfigError("reparse-point-rejected")


def _check_git_root() -> None:
    result = _run_git(["rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        raise ConfigError("git-command-failed")
    try:
        if Path(result.stdout.strip()).resolve() != _PROJECT_ROOT:
            raise ConfigError("unexpected-git-worktree")
    except OSError as exc:
        raise ConfigError("git-root-inspection-failed") from exc


def _check_git_boundary(relative: Path) -> None:
    relative_text = relative.as_posix()
    ignored = _run_git(["check-ignore", "--no-index", "-q", "--", relative_text])
    if ignored.returncode != 0:
        raise ConfigError("path-is-not-git-ignored")
    tracked = _run_git(["ls-files", "--", relative_text])
    if tracked.returncode != 0:
        raise ConfigError("git-command-failed")
    if tracked.stdout.strip():
        raise ConfigError("tracked-packet-path-rejected")


def packet_path(packet_name: str) -> Path:
    if not _PACKET_NAME_PATTERN.fullmatch(packet_name):
        raise ConfigError("packet-name-invalid")
    path = _PACKET_ROOT / packet_name
    relative = _repo_relative(path)
    _check_ancestors(relative)
    _check_git_root()
    _check_git_boundary(relative)
    return path


def check_repository_input(path: Path) -> None:
    relative = _repo_relative(path)
    _check_ancestors(relative)
    try:
        path.resolve().relative_to(_PROJECT_ROOT)
    except (OSError, ValueError) as exc:
        raise ConfigError("input-outside-repository") from exc
    if not path.is_file() or _is_reparse(path):
        raise ConfigError("packet-file-invalid")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError("schema-unavailable") from exc
    if not isinstance(value, dict):
        raise ConfigError("schema-unavailable")
    return value


def _load_validator() -> Draft7Validator:
    packet_schema = _load_json(_PACKET_SCHEMA_PATH)
    canonical_schema = _load_json(_CANONICAL_SCHEMA_PATH)
    try:
        Draft7Validator.check_schema(packet_schema)
        Draft7Validator.check_schema(canonical_schema)
        registry = Registry().with_resources(
            [
                (packet_schema["$id"], Resource.from_contents(packet_schema)),
                (canonical_schema["$id"], Resource.from_contents(canonical_schema)),
            ]
        )
        return Draft7Validator(
            packet_schema,
            registry=registry,
            format_checker=FormatChecker(),
        )
    except (KeyError, SchemaError, Unresolvable) as exc:
        raise ConfigError("schema-unavailable") from exc


def _append_once(issues: list[str], code: str) -> None:
    if code not in issues:
        issues.append(code)


def _free_text_values(packet: dict[str, Any]) -> Iterable[str]:
    for edge in packet.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        reason = edge.get("stateReason")
        if isinstance(reason, str):
            yield reason
        decision = edge.get("humanDecision")
        if isinstance(decision, dict):
            for key in ("reviewer", "evidenceSummary", "notes"):
                value = decision.get(key)
                if isinstance(value, str):
                    yield value


def _internal_ids(packet: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for story in packet.get("storyPair") or []:
        if isinstance(story, dict) and isinstance(story.get("storyId"), str):
            values.add(story["storyId"])
    for edge in packet.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        for endpoint_key in ("from", "to"):
            _add_episode_ids(values, edge.get(endpoint_key))
        for provenance in edge.get("candidateProvenance") or []:
            _add_provenance_ids(values, provenance)
    return values


def _add_episode_ids(values: set[str], endpoint: Any) -> None:
    if not isinstance(endpoint, dict):
        return
    values.update(
        endpoint[key]
        for key in ("storyId", "episodeId")
        if isinstance(endpoint.get(key), str)
    )


def _add_provenance_ids(values: set[str], provenance: Any) -> None:
    if not isinstance(provenance, dict):
        return
    candidate_id = provenance.get("candidateId")
    if isinstance(candidate_id, str):
        values.add(candidate_id)
    values.update(
        value for value in provenance.get("evidenceIds") or [] if isinstance(value, str)
    )
    for endpoint_key in ("sourceEpisode", "targetEpisode"):
        _add_episode_ids(values, provenance.get(endpoint_key))


def _check_free_text(packet: dict[str, Any], issues: list[str]) -> None:
    internal_id_patterns = tuple(
        re.compile(
            rf"(?<![{_INTERNAL_ID_CHARACTERS}])"
            rf"{re.escape(internal_id)}"
            rf"(?![{_INTERNAL_ID_CHARACTERS}])"
        )
        for internal_id in sorted(_internal_ids(packet))
    )
    for value in _free_text_values(packet):
        lowered = value.lower()
        if (
            _WINDOWS_ABSOLUTE_PATH.search(value)
            or _UNC_PATH.search(value)
            or _UNIX_ABSOLUTE_PATH.search(value)
            or _URL.search(value)
            or _RAW_COMMAND.search(value)
            or any(marker in lowered for marker in _RAW_MARKERS)
        ):
            _append_once(issues, "free-text-sensitive-content")
        if any(pattern.search(value) for pattern in internal_id_patterns):
            _append_once(issues, "free-text-internal-id")


def validate_packet_document(packet: Any) -> ValidationResult:
    validator = _load_validator()
    try:
        if list(validator.iter_errors(packet)):
            return ValidationResult(("packet-schema-invalid",))
    except Unresolvable as exc:
        raise ConfigError("schema-unavailable") from exc

    assert isinstance(packet, dict)
    issues: list[str] = []
    for finding in validate_canonical_timeline_review_packet_consistency(packet):
        _append_once(issues, finding["rule"])
    _check_free_text(packet, issues)

    statuses = [edge["reviewStatus"] for edge in packet["edges"]]
    return ValidationResult(
        tuple(sorted(issues)),
        edge_count=len(statuses),
        confirmed_count=statuses.count("confirmed"),
        pending_count=statuses.count("pending"),
        rejected_count=statuses.count("rejected"),
        needs_more_context_count=statuses.count("needs_more_context"),
    )


def validate_packet_path(path: Path) -> ValidationResult:
    try:
        payload = path.read_bytes()
    except OSError:
        return ValidationResult(("packet-read-failed",))
    try:
        packet = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return ValidationResult(("packet-json-invalid",))
    return validate_packet_document(packet)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        path = packet_path(args.packet_name)
        check_repository_input(path)
        result = validate_packet_path(path)
        if not result.is_valid:
            print(
                "[canonical-timeline-review] status=invalid issues="
                + ",".join(result.issue_codes),
                file=sys.stderr,
            )
            return 1
        if not args.quiet:
            print(
                "[canonical-timeline-review] status=valid "
                f"edges={result.edge_count} confirmed={result.confirmed_count} "
                f"pending={result.pending_count} rejected={result.rejected_count} "
                f"needs_more_context={result.needs_more_context_count}"
            )
        return 0
    except ConfigError as exc:
        print(
            f"[canonical-timeline-review] status=config_error code={exc.code}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
