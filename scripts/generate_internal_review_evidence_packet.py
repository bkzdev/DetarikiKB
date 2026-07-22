#!/usr/bin/env python3
"""Internal Review Evidence Packet v1 を固定local rootへ安全に生成する。

このCLIはraw text・内部IDを扱う。入力内容や任意pathをconsoleへ出さず、
書込先を検査してtemporary bundleを作成してから入力を読む。成功したbundle
だけをno-clobberのatomic renameで公開する。
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import errno
import hashlib
import importlib
import io
import json
import os
import secrets
import shutil
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

packet_validator = importlib.import_module(
    "scripts.validate_internal_review_evidence_packet"
)
extraction_validator = importlib.import_module("agents.extractor.validator")
evidence_index_loader = importlib.import_module("agents.wiki_generator.evidence_index")


_PACKET_ROOT = _PROJECT_ROOT / "workspace" / "review_packets" / "evidence"
_SELECTION_ROOT = (
    _PROJECT_ROOT / "workspace" / "local_inputs" / "evidence_packet_selection"
)
_SCHEMA_PATHS = {
    "normalized": _PROJECT_ROOT / "schemas" / "story.schema.json",
    "candidate": _PROJECT_ROOT / "schemas" / "evidence_index.schema.json",
    "extraction": _PROJECT_ROOT / "schemas" / "extraction.schema.json",
    "registry": _PROJECT_ROOT / "schemas" / "public_id_registry.schema.json",
}
_PUBLIC_DEFAULT_TYPES = frozenset(
    {"dialogue", "monologue", "narration", "choice", "unknown"}
)
_MIN_FORBIDDEN_INTERNAL_ID_LENGTH = 4
_BLOCK_TYPE_TO_EVIDENCE_TYPE = {
    "dialogue": "dialogue",
    "monologue": "monologue",
    "narration": "narration",
    "choice": "choice",
    "stage_direction": "stage_direction",
    "unknown": "unknown",
}


class ConfigError(Exception):
    """安全なcodeだけをCLI層へ渡す設定・I/O失敗。"""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ContentError(Exception):
    """入力内容の検証失敗。値を外部出力しない。"""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Internal Review Evidence Packet v1を固定local rootへ生成する"
    )
    parser.add_argument("--normalized-input", required=True)
    parser.add_argument("--public-candidate", required=True)
    parser.add_argument("--projection-mapping", required=True)
    parser.add_argument("--extractions")
    parser.add_argument("--registry")
    parser.add_argument(
        "--selection-file",
        help="workspace/local_inputs/evidence_packet_selection/直下のbasenameのみ",
    )
    parser.add_argument("--retention-days", type=int, default=14)
    parser.add_argument("--quiet", "-q", action="store_true")
    return parser.parse_args(argv)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _utc_z(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _packet_id(created: datetime) -> str:
    return f"erp-{created.strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ConfigError("path-inspection-failed") from exc
    if stat.S_ISLNK(info.st_mode):
        return True
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", None)
    if os.name == "nt" and flag is None:
        raise ConfigError("reparse-inspection-unavailable")
    return bool(getattr(info, "st_file_attributes", 0) & (flag or 0))


def _check_ancestors(path: Path) -> None:
    try:
        relative = path.absolute().relative_to(_PROJECT_ROOT.absolute())
    except ValueError as exc:
        raise ConfigError("path-outside-repository") from exc
    current = _PROJECT_ROOT
    if _is_reparse(current):
        raise ConfigError("reparse-point-rejected")
    for part in relative.parts:
        current = current / part
        if not _lexists(current):
            return
        if _is_reparse(current):
            raise ConfigError("reparse-point-rejected")


def _check_tree_no_links(root: Path) -> None:
    stack = [root]
    while stack:
        current = stack.pop()
        if _is_reparse(current):
            raise ConfigError("reparse-point-rejected")
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    if _is_reparse(child):
                        raise ConfigError("reparse-point-rejected")
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(child)
        except ConfigError:
            raise
        except OSError as exc:
            raise ConfigError("path-inspection-failed") from exc


def _run_git(args: list[str]) -> str:
    try:
        result = packet_validator._run_git(args)
    except packet_validator.ConfigError as exc:
        raise ConfigError(exc.code) from exc
    if result.returncode != 0:
        raise ConfigError("git-command-failed")
    return result.stdout


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(_PROJECT_ROOT).as_posix()
    except (OSError, ValueError) as exc:
        raise ConfigError("path-outside-repository") from exc


def _check_git_paths(paths: Iterable[Path]) -> None:
    top = _run_git(["rev-parse", "--show-toplevel"])
    try:
        if Path(top.strip()).resolve() != _PROJECT_ROOT:
            raise ConfigError("unexpected-git-worktree")
    except OSError as exc:
        raise ConfigError("git-root-inspection-failed") from exc
    for path in paths:
        relative = _repo_relative(path)
        try:
            check = packet_validator._run_git(
                ["check-ignore", "--no-index", "-q", "--", relative]
            )
        except packet_validator.ConfigError as exc:
            raise ConfigError(exc.code) from exc
        if check.returncode != 0:
            raise ConfigError("path-is-not-git-ignored")
        tracked = _run_git(["ls-files", "--", relative])
        if tracked.strip():
            raise ConfigError("tracked-packet-path-rejected")


def _ensure_packet_root() -> None:
    _check_ancestors(_PACKET_ROOT)
    _check_git_paths([_PACKET_ROOT])
    try:
        _PACKET_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigError("packet-root-create-failed") from exc
    _check_ancestors(_PACKET_ROOT)
    if _is_reparse(_PACKET_ROOT) or not _PACKET_ROOT.is_dir():
        raise ConfigError("reparse-point-rejected")
    _check_git_paths([_PACKET_ROOT])


def _preflight_output(packet_id: str) -> Path:
    final = _PACKET_ROOT / packet_id
    _ensure_packet_root()
    _check_ancestors(final)
    _check_git_paths([_PACKET_ROOT, final])
    if _lexists(final):
        raise ConfigError("packet-id-collision")
    return final


def _create_temp(packet_id: str, final: Path) -> Path:
    temp = _PACKET_ROOT / f".tmp-{packet_id}"
    try:
        _check_ancestors(temp)
        _check_git_paths([_PACKET_ROOT, temp, final])
        temp.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise ConfigError("temporary-path-collision") from exc
    except OSError as exc:
        raise ConfigError("temporary-create-failed") from exc
    try:
        _check_ancestors(temp)
        _check_git_paths([_PACKET_ROOT, temp, final])
        if _is_reparse(temp) or not temp.is_dir() or _lexists(final):
            raise ConfigError("temporary-preflight-failed")
    except Exception:
        _cleanup_temp(temp)
        raise
    return temp


def _cleanup_temp(temp: Path) -> bool:
    """確認できたexact temporary directoryだけを削除する。"""
    try:
        if (
            temp.parent != _PACKET_ROOT
            or not temp.name.startswith(".tmp-")
            or not packet_validator._PACKET_ID_PATTERN.fullmatch(temp.name[5:])
        ):
            return False
        if not _lexists(temp):
            return True
        _check_ancestors(temp)
        _check_git_paths([_PACKET_ROOT, temp])
        _check_tree_no_links(temp)
        shutil.rmtree(temp)
        return not _lexists(temp)
    except (ConfigError, OSError):
        return False


def _preflight_input(path: Path, *, allow_directory: bool) -> None:
    _check_ancestors(path)
    if not _lexists(path) or _is_reparse(path):
        raise ConfigError("input-path-invalid")
    try:
        path.resolve().relative_to(_PROJECT_ROOT)
    except (OSError, ValueError) as exc:
        raise ConfigError("input-outside-repository") from exc
    if path.is_dir():
        if not allow_directory:
            raise ConfigError("input-file-required")
        _check_tree_no_links(path)
    elif not path.is_file():
        raise ConfigError("input-file-required")


def _read_bytes_once(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ConfigError("input-read-failed") from exc


def _load_schema(name: str) -> dict[str, Any]:
    try:
        schema = json.loads(_read_bytes_once(_SCHEMA_PATHS[name]).decode("utf-8"))
        Draft7Validator.check_schema(schema)
    except (KeyError, UnicodeError, json.JSONDecodeError, SchemaError) as exc:
        raise ConfigError("schema-unavailable") from exc
    return schema


def _schema_ok(data: Any, schema: dict[str, Any], code: str) -> None:
    if list(Draft7Validator(schema).iter_errors(data)):
        raise ContentError(code)


def _parse_json(data: bytes, code: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContentError(code) from exc
    if not isinstance(value, dict):
        raise ContentError(code)
    return value


def _parse_yaml(data: bytes, code: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(data.decode("utf-8"))
    except (UnicodeError, yaml.YAMLError) as exc:
        raise ContentError(code) from exc
    if not isinstance(value, dict):
        raise ContentError(code)
    return value


def _collect_files(path: Path, suffixes: set[str]) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() not in suffixes:
            raise ContentError("input-file-type-invalid")
        return [path]
    files = sorted(
        p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in suffixes
    )
    if not files:
        raise ContentError("input-files-missing")
    return files


def _load_documents(
    path: Path, *, suffixes: set[str], parser, schema_name: str, invalid_code: str
) -> tuple[list[dict[str, Any]], list[bytes]]:
    _preflight_input(path, allow_directory=True)
    schema = _load_schema(schema_name)
    documents: list[dict[str, Any]] = []
    payloads: list[bytes] = []
    for file in _collect_files(path, suffixes):
        _preflight_input(file, allow_directory=False)
        payload = _read_bytes_once(file)
        document = parser(payload, invalid_code)
        _schema_ok(document, schema, invalid_code)
        documents.append(document)
        payloads.append(payload)
    return documents, payloads


def _aggregate_digest(payloads: list[bytes]) -> str:
    digests = sorted(hashlib.sha256(payload).digest() for payload in payloads)
    return hashlib.sha256(b"".join(digests)).hexdigest()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_mapping(path: Path) -> tuple[list[dict[str, str]], bytes]:
    _preflight_input(path, allow_directory=False)
    if path.suffix.lower() != ".csv":
        raise ContentError("mapping-file-type-invalid")
    payload = _read_bytes_once(path)
    try:
        text = payload.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if reader.fieldnames != packet_validator._MAPPING_FIELDNAMES:
            raise ContentError("mapping-header-invalid")
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ContentError("mapping-csv-invalid") from exc
    if any(
        set(row) != set(packet_validator._MAPPING_FIELDNAMES)
        or any(not isinstance(row.get(name), str) for name in reader.fieldnames)
        for row in rows
    ):
        raise ContentError("mapping-row-shape-invalid")
    _mapping_by_key, issues = packet_validator._validate_mapping_rows(rows)
    if issues:
        raise ContentError(issues[0].code)
    return rows, payload


def _load_selection(filename: str | None) -> set[str] | None:
    if filename is None:
        return None
    if not packet_validator._SELECTION_FILENAME_PATTERN.fullmatch(filename):
        raise ConfigError("selection-filename-invalid")
    path = _SELECTION_ROOT / filename
    _preflight_input(path, allow_directory=False)
    try:
        packet_validator._check_git_boundary(_SELECTION_ROOT, path)
    except packet_validator.ConfigError as exc:
        raise ConfigError(exc.code) from exc
    document = _parse_json(_read_bytes_once(path), "selection-json-invalid")
    schema = packet_validator._load_schema("selection")
    if packet_validator._schema_issues(
        document,
        schema,
        code="selection-schema-invalid",
        component_path="selection.json",
    ):
        raise ContentError("selection-schema-invalid")
    return set(document["evidenceIds"])


def _index_blocks(
    blocks: list[dict[str, Any]],
    *,
    scene_id: str,
    document: dict[str, Any],
    episode: dict[str, Any],
    index: dict[tuple[str, str, str], dict[str, Any]],
) -> None:
    story_id = document["storyId"]
    episode_id = episode["episodeId"]
    for block in blocks:
        block_id = block.get("id")
        if isinstance(block_id, str):
            key = (story_id, episode_id, block_id)
            if key in index:
                raise ContentError("normalized-block-duplicate")
            index[key] = {
                "block": block,
                "sceneId": scene_id,
                "episode": episode,
                "document": document,
            }
        if block.get("type") == "choice":
            for option in block.get("options") or []:
                if isinstance(option, dict):
                    _index_blocks(
                        option.get("blocks") or [],
                        scene_id=scene_id,
                        document=document,
                        episode=episode,
                        index=index,
                    )


def _block_index(
    documents: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    episode_keys: set[tuple[str, str]] = set()
    public_story_ids: dict[str, str] = {}
    for document in documents:
        story_id = document["storyId"]
        public_story_id = document.get("metadata", {}).get("publicStoryId") or ""
        existing_public_story_id = public_story_ids.setdefault(
            story_id, public_story_id
        )
        if existing_public_story_id != public_story_id:
            raise ContentError("normalized-public-story-id-conflict")
        for episode in document["episodes"]:
            episode_key = (story_id, episode["episodeId"])
            if episode_key in episode_keys:
                raise ContentError("normalized-episode-duplicate")
            episode_keys.add(episode_key)
            for scene in episode["scenes"]:
                _index_blocks(
                    scene.get("blocks") or [],
                    scene_id=scene["sceneId"],
                    document=document,
                    episode=episode,
                    index=index,
                )
    return index


def _candidate_entries(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = [entry for doc in documents for entry in doc.get("entries", [])]
    keys: set[tuple[str, str, str, str]] = set()
    if any(document.get("generatedFrom") is not None for document in documents):
        raise ContentError("candidate-not-public-safe")
    for entry in entries:
        if entry.get("evidenceType") not in _PUBLIC_DEFAULT_TYPES:
            raise ContentError("candidate-type-invalid")
        visibility = entry.get("visibility")
        if not isinstance(visibility, dict) or visibility.get("public") is not True:
            raise ContentError("candidate-visibility-invalid")
        public = (
            entry.get("publicStoryId"),
            entry.get("publicEpisodeId"),
            entry.get("publicEvidenceId"),
        )
        if not all(isinstance(value, str) and value for value in public):
            raise ContentError("candidate-public-id-missing")
        if (
            entry.get("storyId"),
            entry.get("episodeId"),
            entry.get("evidenceId"),
        ) != public:
            raise ContentError("candidate-not-public-safe")
        if (
            entry.get("sceneId") is not None
            or entry.get("blockId") is not None
            or entry.get("referencedBy") is not None
            or visibility.get("rawTextIncluded") is not False
        ):
            raise ContentError("candidate-not-public-safe")
        key = (*public, entry["evidenceType"])
        if key in keys:
            raise ContentError("candidate-public-key-duplicate")
        keys.add(key)
    return entries


def _candidate_has_unsafe_value(
    documents: list[dict[str, Any]], rows: list[dict[str, str]]
) -> bool:
    public_ids = {
        value
        for row in rows
        for name in ("publicStoryId", "publicEpisodeId", "publicEvidenceId")
        if (value := row[name])
    }
    internal_ids = {
        value
        for row in rows
        for name in ("storyId", "episodeId", "evidenceId", "sceneId", "blockId")
        if (value := row[name])
        and value not in public_ids
        and len(value) >= _MIN_FORBIDDEN_INTERNAL_ID_LENGTH
    }
    for document in documents:
        for value in packet_validator._iter_strings(document):
            if packet_validator._contains_forbidden_path(value):
                return True
            if any(
                pattern in value
                for pattern in evidence_index_loader.FORBIDDEN_TEXT_PATTERNS
            ):
                return True
            if any(
                value == internal_id
                or (
                    len(internal_id) >= 6
                    and internal_id in value
                    and internal_id != value
                )
                for internal_id in internal_ids
            ):
                return True
    return False


def _registry_lookup(registry: dict[str, Any]) -> dict[tuple[str, int], str]:
    lookup: dict[tuple[str, int], str] = {}
    for story in registry["stories"]:
        for episode in story["episodes"]:
            key = (story["publicStoryId"], episode["episodeOrder"])
            if key in lookup:
                raise ContentError("registry-episode-duplicate")
            lookup[key] = episode["publicEpisodeId"]
    return lookup


def _mapping_has_registry_metadata(row: dict[str, str]) -> bool:
    return (
        row["publicEpisodeIdSource"] == "registry"
        or row["registryMatched"] != "False"
        or row["registryConflict"] != "False"
        or bool(row["registryPublicEpisodeId"])
    )


def _validate_registry_row(
    row: dict[str, str], lookup: dict[tuple[str, int], str]
) -> None:
    expected = lookup.get((row["publicStoryId"], int(row["episodeOrder"])))
    source = row["publicEpisodeIdSource"]
    if row["registryConflict"] != "False":
        raise ContentError("mapping-registry-mismatch")
    if source == "registry":
        if (
            not expected
            or row["registryMatched"] != "True"
            or row["publicEpisodeId"] != expected
            or row["registryPublicEpisodeId"] != expected
        ):
            raise ContentError("mapping-registry-mismatch")
    elif source == "input":
        if row["registryMatched"] != "False" or not row["publicEpisodeId"]:
            raise ContentError("mapping-registry-mismatch")
        if expected and row["publicEpisodeId"] != expected:
            raise ContentError("mapping-registry-mismatch")
        if row["registryPublicEpisodeId"] and row["registryPublicEpisodeId"] != (
            expected or ""
        ):
            raise ContentError("mapping-registry-mismatch")
    elif source == "missing":
        if (
            expected
            or row["registryMatched"] != "False"
            or row["publicEpisodeId"]
            or row["registryPublicEpisodeId"]
        ):
            raise ContentError("mapping-registry-mismatch")
    else:
        raise ContentError("mapping-registry-mismatch")


def _validate_registry(
    rows: list[dict[str, str]], registry: dict[str, Any] | None
) -> None:
    if registry is None:
        if any(_mapping_has_registry_metadata(row) for row in rows):
            raise ContentError("mapping-registry-input-missing")
        return
    lookup = _registry_lookup(registry)
    for row in rows:
        _validate_registry_row(row, lookup)


def _normalized_public_episode_matches(
    row: dict[str, str], normalized_public_episode_id: str
) -> bool:
    source = row["publicEpisodeIdSource"]
    if source == "registry":
        return not normalized_public_episode_id and bool(row["publicEpisodeId"])
    return row["publicEpisodeId"] == normalized_public_episode_id


def _validate_cross_reference(
    rows: list[dict[str, str]],
    candidates: list[dict[str, Any]],
    blocks: dict[tuple[str, str, str], dict[str, Any]],
) -> None:
    candidate_keys = {
        (
            entry["publicStoryId"],
            entry["publicEpisodeId"],
            entry["publicEvidenceId"],
            entry["evidenceType"],
        )
        for entry in candidates
    }
    mapping_candidate_keys: set[tuple[str, str, str, str]] = set()
    for row in rows:
        key = (row["storyId"], row["episodeId"], row["evidenceId"])
        located = blocks.get(key)
        if located is None:
            raise ContentError("mapping-normalized-block-missing")
        block = located["block"]
        episode = located["episode"]
        document = located["document"]
        expected_story = document.get("metadata", {}).get("publicStoryId") or ""
        expected_episode = episode.get("metadata", {}).get("publicEpisodeId") or ""
        expected_evidence_type = _BLOCK_TYPE_TO_EVIDENCE_TYPE.get(block.get("type"))
        if (
            row["publicStoryId"] != expected_story
            or not _normalized_public_episode_matches(row, expected_episode)
            or row["sceneId"] != located["sceneId"]
            or row["blockId"] != block.get("id", "")
            or row["evidenceType"] != expected_evidence_type
        ):
            raise ContentError("mapping-normalized-mismatch")
        if row["publicEvidenceId"]:
            mapping_candidate_keys.add(
                (
                    row["publicStoryId"],
                    row["publicEpisodeId"],
                    row["publicEvidenceId"],
                    row["evidenceType"],
                )
            )
    if mapping_candidate_keys != candidate_keys:
        raise ContentError("mapping-candidate-set-mismatch")


def _extraction_candidates(
    documents: list[dict[str, Any]] | None, selected: set[tuple[str, str, str]]
) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    if documents is None:
        return {}
    types = {
        "characters": "character_candidate",
        "organizations": "organization_candidate",
        "locations": "location_candidate",
        "items": "item_candidate",
        "lore": "lore_candidate",
        "events": "event_candidate",
        "relationships": "relationship_candidate",
        "timelineCandidates": "timeline_candidate",
        "specialSpeakerLabelCandidates": "special_speaker_label_candidate",
    }
    result: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for document in documents:
        story_id, episode_id = document["storyId"], document["episodeId"]
        for field, candidate_type in types.items():
            for candidate in document.get(field, []) or []:
                for evidence_id in candidate.get("evidenceIds", []) or []:
                    key = (story_id, episode_id, evidence_id)
                    if key in selected:
                        result.setdefault(key, []).append(
                            {
                                "candidateId": candidate["id"],
                                "candidateType": candidate_type,
                                "confidence": candidate.get("confidence"),
                            }
                        )
    return result


def _validate_extraction_documents(
    documents: list[dict[str, Any]] | None,
    normalized_documents: list[dict[str, Any]],
    blocks: dict[tuple[str, str, str], dict[str, Any]],
) -> None:
    if documents is None:
        return
    normalized_episodes = {
        (document["storyId"], episode["episodeId"])
        for document in normalized_documents
        for episode in document["episodes"]
    }
    extraction_episodes: set[tuple[str, str]] = set()
    for document in documents:
        if extraction_validator.has_errors(
            extraction_validator.run_semantic_validation(document)
        ):
            raise ContentError("extraction-semantic-invalid")
        key = (document["storyId"], document["episodeId"])
        if key in extraction_episodes:
            raise ContentError("extraction-episode-duplicate")
        if key not in normalized_episodes:
            raise ContentError("extraction-normalized-episode-missing")
        extraction_episodes.add(key)
        for evidence_id, evidence in document.get("evidenceIndex", {}).items():
            located = blocks.get((key[0], key[1], evidence_id))
            if located is None or (
                evidence.get("sourceId") != evidence_id
                or evidence.get("storyId") != key[0]
                or evidence.get("episodeId") != key[1]
                or evidence.get("sceneId") != located["sceneId"]
            ):
                raise ContentError("extraction-normalized-block-mismatch")


def _raw_content(block: dict[str, Any]) -> dict[str, Any] | None:
    text = next(
        (
            value
            for value in (
                block.get("text"),
                block.get("rawText"),
                block.get("choiceText"),
            )
            if isinstance(value, str) and value
        ),
        None,
    )
    raw_command = block.get("rawCommand")
    command = raw_command if isinstance(raw_command, str) and raw_command else None
    raw_arguments = block.get("args", [])
    if raw_arguments is None:
        raw_arguments = []
    if not isinstance(raw_arguments, list) or any(
        not isinstance(value, str) for value in raw_arguments
    ):
        raise ContentError("raw-arguments-invalid")
    if raw_arguments and command is None:
        raise ContentError("raw-arguments-without-command")
    if text is None and command is None:
        return None
    return {
        "reason": "parser-diagnostic" if command else "evidence-review",
        "text": text,
        "rawCommand": command,
        "arguments": raw_arguments if command else [],
    }


def _speaker(block: dict[str, Any]) -> dict[str, Any] | None:
    source = block.get("speaker")
    if not isinstance(source, dict):
        return None
    speaker_id = (
        source.get("speakerId") if isinstance(source.get("speakerId"), str) else None
    )
    return {
        "sourceLabel": source.get("speakerName")
        if isinstance(source.get("speakerName"), str)
        else None,
        "sourceCharacterId": source.get("sourceCharacterId")
        if isinstance(source.get("sourceCharacterId"), str)
        else None,
        "speakerId": speaker_id,
        "resolutionStatus": "resolved"
        if source.get("isResolved") is True and speaker_id
        else "unresolved",
    }


def _write_json(path: Path, value: dict[str, Any]) -> bytes:
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(payload)
    except OSError as exc:
        raise ConfigError("temporary-write-failed") from exc
    return payload


def _write_mapping(path: Path, rows: list[dict[str, str]]) -> bytes:
    rendered = io.StringIO(newline="")
    writer = csv.DictWriter(rendered, fieldnames=packet_validator._MAPPING_FIELDNAMES)
    writer.writeheader()
    writer.writerows(rows)
    payload = rendered.getvalue().encode("utf-8")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(payload)
        return payload
    except OSError as exc:
        raise ConfigError("temporary-write-failed") from exc


def _rename_no_replace(source: Path, destination: Path) -> None:
    if os.name == "nt":
        try:
            os.rename(source, destination)
        except FileExistsError as exc:
            raise ConfigError("packet-id-collision") from exc
        except OSError as exc:
            raise ConfigError("atomic-rename-failed") from exc
        return
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            raise ConfigError("atomic-rename-unavailable")
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
        if result != 0:
            if ctypes.get_errno() == errno.EEXIST:
                raise ConfigError("packet-id-collision")
            raise ConfigError("atomic-rename-failed")
        return
    raise ConfigError("atomic-rename-unavailable")


def _publish(temp: Path, final: Path) -> None:
    _check_ancestors(temp)
    _check_ancestors(final)
    _check_tree_no_links(temp)
    _check_git_paths([_PACKET_ROOT, temp, final])
    if _lexists(final):
        raise ConfigError("packet-id-collision")
    _rename_no_replace(temp, final)


def _load_registry_input(
    filename: str | None,
) -> tuple[dict[str, Any] | None, bytes | None]:
    if filename is None:
        return None, None
    path = Path(filename)
    _preflight_input(path, allow_directory=False)
    if path.suffix.lower() not in {".yaml", ".yml"}:
        raise ContentError("registry-file-type-invalid")
    payload = _read_bytes_once(path)
    registry = _parse_yaml(payload, "registry-schema-invalid")
    _schema_ok(registry, _load_schema("registry"), "registry-schema-invalid")
    return registry, payload


def _load_extraction_inputs(
    filename: str | None,
) -> tuple[list[dict[str, Any]] | None, list[bytes]]:
    if filename is None:
        return None, []
    return _load_documents(
        Path(filename),
        suffixes={".json"},
        parser=_parse_json,
        schema_name="extraction",
        invalid_code="extraction-schema-invalid",
    )


def _select_rows(
    rows: list[dict[str, str]],
    candidates: list[dict[str, Any]],
    selection: set[str] | None,
) -> tuple[list[dict[str, str]], str]:
    if selection is None:
        selected_rows = [row for row in rows if row["publicEvidenceId"]]
        selection_mode = "public-candidate"
    else:
        selected_rows = [row for row in rows if row["evidenceId"] in selection]
        if len(selected_rows) != len(selection):
            raise ContentError("selection-mapping-missing")
        candidate_public = {
            (
                entry["publicStoryId"],
                entry["publicEpisodeId"],
                entry["publicEvidenceId"],
                entry["evidenceType"],
            )
            for entry in candidates
        }
        for row in selected_rows:
            if row["evidenceType"] not in _PUBLIC_DEFAULT_TYPES:
                continue
            key = (
                row["publicStoryId"],
                row["publicEpisodeId"],
                row["publicEvidenceId"],
                row["evidenceType"],
            )
            if not row["publicEvidenceId"] or key not in candidate_public:
                raise ContentError("selection-public-candidate-missing")
        selection_mode = "explicit-entry-list"
    if not selected_rows:
        raise ContentError("selection-empty")
    return selected_rows, selection_mode


def _write_story_components(
    temp: Path,
    selected_rows: list[dict[str, str]],
    blocks: dict[tuple[str, str, str], dict[str, Any]],
    extraction: dict[tuple[str, str, str], list[dict[str, Any]]],
) -> list[tuple[str, bytes, int]]:
    by_story: dict[str, list[dict[str, str]]] = {}
    for row in selected_rows:
        by_story.setdefault(row["storyId"], []).append(row)
    stories: list[tuple[str, bytes, int]] = []
    entry_number = 1
    for story_number, (story_id, story_rows) in enumerate(by_story.items(), start=1):
        entries: list[dict[str, Any]] = []
        for row in story_rows:
            key = (row["storyId"], row["episodeId"], row["evidenceId"])
            located = blocks[key]
            entry = {
                "reviewEntryId": f"entry-{entry_number:06d}",
                "identifiers": {
                    "internal": {
                        "episodeId": row["episodeId"],
                        "evidenceId": row["evidenceId"],
                        "sceneId": row["sceneId"] or None,
                        "blockId": row["blockId"] or None,
                    },
                    "public": {
                        "publicEpisodeId": row["publicEpisodeId"] or None,
                        "publicEvidenceId": row["publicEvidenceId"] or None,
                    },
                },
                "evidenceType": row["evidenceType"],
                "rawContent": _raw_content(located["block"]),
                "context": {"before": [], "after": []},
                "speaker": _speaker(located["block"]),
                "extraction": {"candidates": extraction[key]}
                if extraction.get(key)
                else None,
                "diagnostics": [],
            }
            entries.append(entry)
            entry_number += 1
        story_key = f"story-{story_number:04d}"
        document = {
            "packetVersion": 1,
            "reviewStoryKey": story_key,
            "identifiers": {
                "internal": {"storyId": story_id},
                "public": {"publicStoryId": story_rows[0]["publicStoryId"] or None},
            },
            "entries": entries,
        }
        payload = _write_json(temp / "stories" / f"{story_key}.json", document)
        stories.append((f"stories/{story_key}.json", payload, len(entries)))
    return stories


def _build_bundle(
    args: argparse.Namespace, packet_id: str, created: datetime, temp: Path
) -> tuple[int, int, int]:
    normalized, normalized_bytes = _load_documents(
        Path(args.normalized_input),
        suffixes={".json"},
        parser=_parse_json,
        schema_name="normalized",
        invalid_code="normalized-schema-invalid",
    )
    candidate_docs, candidate_bytes = _load_documents(
        Path(args.public_candidate),
        suffixes={".yaml", ".yml"},
        parser=_parse_yaml,
        schema_name="candidate",
        invalid_code="candidate-schema-invalid",
    )
    rows, mapping_bytes = _read_mapping(Path(args.projection_mapping))
    registry, registry_bytes = _load_registry_input(args.registry)
    extraction_docs, extraction_bytes = _load_extraction_inputs(args.extractions)

    candidates = _candidate_entries(candidate_docs)
    if _candidate_has_unsafe_value(candidate_docs, rows):
        raise ContentError("candidate-unsafe-value")
    blocks = _block_index(normalized)
    _validate_registry(rows, registry)
    _validate_cross_reference(rows, candidates, blocks)
    _validate_extraction_documents(extraction_docs, normalized, blocks)
    selection = _load_selection(args.selection_file)
    selected_rows, selection_mode = _select_rows(rows, candidates, selection)

    selected_keys = {
        (row["storyId"], row["episodeId"], row["evidenceId"]) for row in selected_rows
    }
    extraction = _extraction_candidates(extraction_docs, selected_keys)

    mapping_payload = _write_mapping(
        temp / "mappings" / "evidence-id-map.csv", selected_rows
    )
    stories = _write_story_components(temp, selected_rows, blocks, extraction)

    component_count = 2 + len(stories)
    report = {
        "reportVersion": 1,
        "packetVersion": 1,
        "packetId": packet_id,
        "status": "valid",
        "validatedAt": _utc_z(_utc_now()),
        "storyCount": len(stories),
        "entryCount": len(selected_rows),
        "componentCount": component_count,
        "errorCount": 0,
        "warningCount": 0,
        "issues": [],
    }
    report_payload = _write_json(temp / "reports" / "validation.json", report)
    components = [
        {
            "relativePath": "mappings/evidence-id-map.csv",
            "mediaType": "text/csv",
            "recordCount": len(selected_rows),
            "sha256": _sha256(mapping_payload),
        }
    ]
    components.extend(
        {
            "relativePath": path,
            "mediaType": "application/json",
            "recordCount": count,
            "sha256": _sha256(payload),
        }
        for path, payload, count in stories
    )
    components.append(
        {
            "relativePath": "reports/validation.json",
            "mediaType": "application/json",
            "recordCount": 0,
            "sha256": _sha256(report_payload),
        }
    )
    manifest = {
        "packetVersion": 1,
        "packetId": packet_id,
        "classification": "internal-review-local",
        "purpose": "evidence-review",
        "selectionMode": selection_mode,
        "commitAllowed": False,
        "retentionClass": "ephemeral",
        "generatorVersion": "internal-review-evidence-packet-generator-1",
        "createdAt": _utc_z(created),
        "expiresAt": _utc_z(created + timedelta(days=args.retention_days)),
        "sourceSnapshot": {
            "normalizedStoryFileCount": len(normalized),
            "normalizedStoryDigest": _aggregate_digest(normalized_bytes),
            "extractionDigest": _aggregate_digest(extraction_bytes)
            if extraction_docs is not None
            else None,
            "projectionMappingDigest": _sha256(mapping_bytes),
            "publicCandidateDigest": _aggregate_digest(candidate_bytes),
            "registryDigest": _sha256(registry_bytes)
            if registry_bytes is not None
            else None,
            "projectionMode": "public-safe",
            "projectionPolicy": "public-default",
        },
        "components": components,
    }
    _write_json(temp / "manifest.json", manifest)
    result = packet_validator.validate_packet_directory(temp, packet_id)
    if result.errors:
        raise ContentError("generated-bundle-invalid")
    return len(stories), len(selected_rows), len(components)


def _print_error(code: str, *, temp: Path | None = None) -> None:
    suffix = f" temporary={temp.name}" if temp is not None else ""
    print(f"[packet] status=failed code={code}{suffix}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 1 <= args.retention_days <= 30:
        _print_error("retention-days-invalid")
        return 2
    created = _utc_now()
    packet_id = _packet_id(created)
    temp: Path | None = None
    try:
        final = _preflight_output(packet_id)
        temp = _create_temp(packet_id, final)
        stories, entries, components = _build_bundle(args, packet_id, created, temp)
        _publish(temp, final)
        temp = None
        if not args.quiet:
            print(
                f"[packet] packet={packet_id} status=valid stories={stories} "
                f"entries={entries} components={components}"
            )
        return 0
    except ContentError as exc:
        if temp is not None and not _cleanup_temp(temp):
            _print_error("temporary-cleanup-failed", temp=temp)
            return 2
        _print_error(exc.code)
        return 1
    except ConfigError as exc:
        if temp is not None and not _cleanup_temp(temp):
            _print_error("temporary-cleanup-failed", temp=temp)
            return 2
        _print_error(exc.code)
        return 2
    except Exception:
        if temp is not None and not _cleanup_temp(temp):
            _print_error("temporary-cleanup-failed", temp=temp)
            return 2
        _print_error("unexpected-failure")
        return 2


if __name__ == "__main__":
    sys.exit(main())
