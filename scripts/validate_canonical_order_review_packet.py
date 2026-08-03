#!/usr/bin/env python3
"""Canonical order review packetを固定local root内で安全に検証する。"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft7Validator, FormatChecker
from jsonschema.exceptions import SchemaError

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
_PACKET_ROOT = _PROJECT_ROOT / "workspace" / "review_packets" / "canonical_order"
_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "canonical_order_review_packet.schema.json"
_PACKET_NAME_PATTERN = re.compile(
    r"^canonical_order_review_[a-z0-9][a-z0-9_-]{0,63}\.yaml$"
)
_WINDOWS_ABSOLUTE_PATH = re.compile(r"(?:^|\s)[A-Za-z]:[\\/]")
_UNC_PATH = re.compile(r"(?:^|\s)\\\\[^\\\s]+[\\/]")
_UNIX_ABSOLUTE_PATH = re.compile(r"(?:^|\s)/(?:[^/\s]+/)+[^\s]*")
_RAW_MARKERS = (".dec", "@", "$num", "$value", "<script")


class ConfigError(Exception):
    """内容をechoしてはいけないCLI設定エラー。"""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ValidationResult:
    issue_codes: tuple[str, ...]
    episode_count: int = 0
    confirmed_count: int = 0
    pending_count: int = 0

    @property
    def is_valid(self) -> bool:
        return not self.issue_codes


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="workspace内のcanonical order review packetを検証する"
    )
    parser.add_argument(
        "--packet-name",
        required=True,
        help="workspace/review_packets/canonical_order直下のbasename",
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


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


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
    repo = _run_git(["rev-parse", "--show-toplevel"])
    if repo.returncode != 0:
        raise ConfigError("git-command-failed")
    try:
        if Path(repo.stdout.strip()).resolve() != _PROJECT_ROOT:
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


def _check_fixed_root(path: Path) -> None:
    relative = _repo_relative(path)
    _check_ancestors(relative)
    _check_git_root()
    _check_git_boundary(relative)


def check_repository_input(path: Path) -> None:
    """repo内入力のleafと既存祖先にreparse pointが無いことを確認する。"""
    relative = _repo_relative(path)
    _check_ancestors(relative)
    try:
        path.resolve().relative_to(_PROJECT_ROOT)
    except (OSError, ValueError) as exc:
        raise ConfigError("input-outside-repository") from exc
    if not path.is_file() or _is_reparse(path):
        raise ConfigError("input-file-invalid")


def packet_path(packet_name: str) -> Path:
    if not _PACKET_NAME_PATTERN.fullmatch(packet_name):
        raise ConfigError("packet-name-invalid")
    path = _PACKET_ROOT / packet_name
    _check_fixed_root(path)
    return path


def _load_schema() -> dict[str, Any]:
    try:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
        return schema
    except (OSError, UnicodeError, json.JSONDecodeError, SchemaError) as exc:
        raise ConfigError("schema-unavailable") from exc


def _append_once(issues: list[str], code: str) -> None:
    if code not in issues:
        issues.append(code)


def _free_text_values(packet: dict[str, Any]) -> Iterable[str]:
    for episode in packet.get("episodes") or []:
        if not isinstance(episode, dict):
            continue
        for key in ("evidenceSummary", "reviewerNotes"):
            value = episode.get(key)
            if isinstance(value, str):
                yield value
        for key in (
            "currentCanonicalOrderSource",
            "candidateSource",
            "humanConfirmedSource",
        ):
            source = episode.get(key)
            if isinstance(source, dict) and isinstance(source.get("note"), str):
                yield source["note"]


def _contains_forbidden_free_text(value: str) -> bool:
    lowered = value.lower()
    return (
        _WINDOWS_ABSOLUTE_PATH.search(value) is not None
        or _UNC_PATH.search(value) is not None
        or _UNIX_ABSOLUTE_PATH.search(value) is not None
        or any(marker in lowered for marker in _RAW_MARKERS)
    )


def _check_episode_inventory(
    story: dict[str, Any], episodes: list[dict[str, Any]], issues: list[str]
) -> None:
    if story["episodeCount"] != len(episodes):
        _append_once(issues, "episode-count-mismatch")

    episode_ids = [episode["episodeId"] for episode in episodes]
    review_keys = [episode["reviewEpisodeKey"] for episode in episodes]
    manifest_indexes = [episode["manifestEpisodeIndex"] for episode in episodes]
    if len(set(episode_ids)) != len(episode_ids):
        _append_once(issues, "episode-id-duplicate")
    if len(set(review_keys)) != len(review_keys):
        _append_once(issues, "review-episode-key-duplicate")
    if len(set(manifest_indexes)) != len(manifest_indexes):
        _append_once(issues, "manifest-episode-index-duplicate")

    for position, episode in enumerate(episodes, start=1):
        if episode["reviewEpisodeKey"] != f"episode-{position:04d}":
            _append_once(issues, "review-episode-key-order-invalid")
        if episode["manifestEpisodeIndex"] != position:
            _append_once(issues, "manifest-episode-index-order-invalid")


def _check_free_text(
    packet: dict[str, Any],
    story: dict[str, Any],
    episodes: list[dict[str, Any]],
    issues: list[str],
) -> None:
    episode_ids = [episode["episodeId"] for episode in episodes]
    internal_ids = {story["storyId"], *episode_ids}
    for value in _free_text_values(packet):
        if _contains_forbidden_free_text(value):
            _append_once(issues, "free-text-sensitive-content")
        if any(internal_id in value for internal_id in internal_ids):
            _append_once(issues, "free-text-internal-id")


def _check_retention_window(packet: dict[str, Any], issues: list[str]) -> None:
    try:
        created_at = datetime.fromisoformat(packet["createdAt"].replace("Z", "+00:00"))
        expires_at = datetime.fromisoformat(packet["expiresAt"].replace("Z", "+00:00"))
        if expires_at <= created_at:
            _append_once(issues, "retention-window-invalid")
        elif expires_at <= datetime.now(timezone.utc):
            _append_once(issues, "packet-expired")
    except (TypeError, ValueError):
        _append_once(issues, "packet-timestamp-invalid")


def validate_packet_document(packet: Any) -> ValidationResult:
    issues: list[str] = []
    schema = _load_schema()
    if list(
        Draft7Validator(schema, format_checker=FormatChecker()).iter_errors(packet)
    ):
        return ValidationResult(("packet-schema-invalid",))

    assert isinstance(packet, dict)
    episodes = packet["episodes"]
    story = packet["story"]
    _check_episode_inventory(story, episodes, issues)
    _check_free_text(packet, story, episodes, issues)
    _check_retention_window(packet, issues)

    statuses = [episode["humanReviewStatus"] for episode in episodes]
    return ValidationResult(
        tuple(issues),
        episode_count=len(episodes),
        confirmed_count=statuses.count("confirmed"),
        pending_count=statuses.count("pending"),
    )


def validate_packet_path(path: Path) -> ValidationResult:
    try:
        payload = path.read_bytes()
    except OSError:
        return ValidationResult(("packet-read-failed",))
    try:
        packet = yaml.safe_load(payload.decode("utf-8"))
    except (UnicodeError, yaml.YAMLError):
        return ValidationResult(("packet-yaml-invalid",))
    return validate_packet_document(packet)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        path = packet_path(args.packet_name)
        if not path.is_file() or _is_reparse(path):
            raise ConfigError("packet-file-invalid")
        result = validate_packet_path(path)
        if not result.is_valid:
            print(
                "[canonical-order-review] status=invalid issues="
                + ",".join(result.issue_codes),
                file=sys.stderr,
            )
            return 1
        if not args.quiet:
            print(
                "[canonical-order-review] status=valid "
                f"episodes={result.episode_count} "
                f"confirmed={result.confirmed_count} pending={result.pending_count}"
            )
        return 0
    except ConfigError as exc:
        print(
            f"[canonical-order-review] status=config_error code={exc.code}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
