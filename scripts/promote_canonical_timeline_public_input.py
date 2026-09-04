#!/usr/bin/env python3
"""Review済みCanonical Timeline projectionをpublic inputへ安全に昇格する。"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.extractor.canonical_timeline_public_input import (  # noqa: E402
    PublicInputError,
    build_canonical_timeline_public_input,
    canonical_json_sha256,
    validate_canonical_timeline_public_input,
)

_WORKSPACE_ROOT = _PROJECT_ROOT / "workspace" / "public_wiki_inputs"
_TARGET = (
    _PROJECT_ROOT
    / "knowledge"
    / "public"
    / "timelines"
    / "canonical_timeline_public_input.json"
)
_NAMES = {
    "projection": re.compile(
        r"^canonical_timeline_public_projection_[a-z0-9][a-z0-9_-]{0,63}\.json$"
    ),
    "review": re.compile(
        r"^canonical_timeline_public_input_review_[a-z0-9][a-z0-9_-]{0,63}\.json$"
    ),
    "preflight": re.compile(
        r"^canonical_timeline_public_preflight_[a-z0-9][a-z0-9_-]{0,63}\.json$"
    ),
}


def _secure_dir_fd_supported() -> bool:
    return os.name != "nt" and all(
        function in os.supports_dir_fd
        for function in (os.open, os.link, os.stat, os.unlink)
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "review済みCanonical Timeline projectionをpublic build inputへ昇格する"
            "（既定はdry-run）"
        )
    )
    parser.add_argument("--projection-name", required=True)
    parser.add_argument("--review-name", required=True)
    parser.add_argument("--preflight-name", required=True)
    parser.add_argument("--expected-projection-sha256", required=True)
    parser.add_argument(
        "--execute", action="store_true", help="固定targetへ新規作成する"
    )
    return parser.parse_args(argv)


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError as exc:
        raise PublicInputError("path-inspection-failed") from exc
    return stat.S_ISLNK(info.st_mode) or bool(
        (getattr(info, "st_file_attributes", 0) or 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _relative(path: Path) -> Path:
    try:
        return path.absolute().relative_to(_PROJECT_ROOT.absolute())
    except ValueError as exc:
        raise PublicInputError("path-outside-repository") from exc


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
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
        raise PublicInputError("git-command-failed") from exc


def _check_ancestors(path: Path) -> None:
    current = _PROJECT_ROOT
    if _is_reparse(current):
        raise PublicInputError("reparse-point-rejected")
    for part in _relative(path).parts:
        current = current / part
        if not current.exists():
            break
        if _is_reparse(current):
            raise PublicInputError("reparse-point-rejected")


def _workspace_input(kind: str, name: str) -> Path:
    if not _NAMES[kind].fullmatch(name):
        raise PublicInputError(f"{kind}-name-invalid")
    path = _WORKSPACE_ROOT / name
    _check_ancestors(path)
    if not path.is_file() or _is_reparse(path):
        raise PublicInputError(f"{kind}-file-invalid")
    relative = _relative(path).as_posix()
    tracked = _git(["ls-files", "--", relative])
    ignored = _git(["check-ignore", "--no-index", "-q", "--", relative])
    if tracked.returncode or tracked.stdout.strip() or ignored.returncode:
        raise PublicInputError(f"{kind}-workspace-boundary-invalid")
    return path


def _read_regular_bytes(path: Path, code: str) -> tuple[bytes, os.stat_result]:
    if _secure_dir_fd_supported():
        return _read_regular_bytes_at_directory(path, code)
    return _read_regular_bytes_by_path(path, code)


def _open_stable_directory(path: Path, code: str) -> int:
    try:
        before = path.lstat()
        if _is_reparse(path) or not stat.S_ISDIR(before.st_mode):
            raise PublicInputError(code)
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        after = path.lstat()
        if not _same_identity(before, opened) or not _same_identity(opened, after):
            os.close(descriptor)
            raise PublicInputError(code)
        return descriptor
    except PublicInputError:
        raise
    except OSError as exc:
        raise PublicInputError(code) from exc


def _read_regular_bytes_at_directory(
    path: Path, code: str
) -> tuple[bytes, os.stat_result]:
    directory = _open_stable_directory(path.parent, code)
    try:
        before = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise PublicInputError(code)
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path.name, flags, dir_fd=directory)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            payload = stream.read()
        after = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        if not _same_identity(before, opened) or not _same_identity(opened, after):
            raise PublicInputError(code)
        return payload, opened
    except PublicInputError:
        raise
    except OSError as exc:
        raise PublicInputError(code) from exc
    finally:
        os.close(directory)


def _read_regular_bytes_by_path(path: Path, code: str) -> tuple[bytes, os.stat_result]:
    before: os.stat_result
    try:
        before = path.lstat()
        if _is_reparse(path) or not stat.S_ISREG(before.st_mode):
            raise PublicInputError(code)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            payload = stream.read()
        after = path.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or _is_reparse(path)
            or not _same_identity(before, opened)
            or not _same_identity(opened, after)
        ):
            raise PublicInputError(code)
        return payload, opened
    except PublicInputError:
        raise
    except OSError as exc:
        raise PublicInputError(code) from exc


def _load(path: Path, code: str) -> dict[str, Any]:
    try:
        payload, _identity = _read_regular_bytes(path, code)
        value = json.loads(payload.decode("utf-8"))
    except PublicInputError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PublicInputError(code) from exc
    if not isinstance(value, dict):
        raise PublicInputError(code)
    return value


def _build(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    projection = _load(
        _workspace_input("projection", args.projection_name),
        "projection-json-invalid",
    )
    review = _load(_workspace_input("review", args.review_name), "review-json-invalid")
    preflight = _load(
        _workspace_input("preflight", args.preflight_name),
        "preflight-json-invalid",
    )
    document = build_canonical_timeline_public_input(
        projection, review, preflight, args.expected_projection_sha256
    )
    return document, canonical_json_sha256(projection)


def _serialize(document: dict[str, Any]) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _target_is_tracked() -> bool:
    relative = _relative(_TARGET).as_posix()
    result = _git(["ls-files", "--error-unmatch", "--", relative])
    if result.returncode not in (0, 1):
        raise PublicInputError("target-tracking-check-failed")
    return result.returncode == 0


def _same_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _remove_created_target(directory: int, created: os.stat_result) -> None:
    try:
        current = os.stat(_TARGET.name, dir_fd=directory, follow_symlinks=False)
        if not stat.S_ISREG(current.st_mode) or not _same_identity(created, current):
            raise PublicInputError("post-write-cleanup-unsafe")
        os.unlink(_TARGET.name, dir_fd=directory)
    except PublicInputError:
        raise
    except OSError as exc:
        raise PublicInputError("post-write-cleanup-failed") from exc


def _write_temporary_file(directory: int, temp_name: str, payload: bytes) -> None:
    try:
        descriptor = os.open(
            temp_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
    except OSError as exc:
        raise PublicInputError("temporary-file-unavailable") from exc
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _cleanup_temporary_file(
    directory: int, temp_name: str, created: os.stat_result | None
) -> None:
    try:
        os.unlink(temp_name, dir_fd=directory)
    except FileNotFoundError:
        return
    except OSError as exc:
        if created is not None:
            _remove_created_target(directory, created)
        raise PublicInputError("temporary-cleanup-failed") from exc


def _create_target(directory: int, payload: bytes) -> os.stat_result:
    temp_name = f".{_TARGET.name}.{secrets.token_hex(8)}.tmp"
    created: os.stat_result | None = None
    try:
        _write_temporary_file(directory, temp_name, payload)
        temp_identity = os.stat(temp_name, dir_fd=directory, follow_symlinks=False)
        os.link(
            temp_name,
            _TARGET.name,
            src_dir_fd=directory,
            dst_dir_fd=directory,
            follow_symlinks=False,
        )
        created = os.stat(_TARGET.name, dir_fd=directory, follow_symlinks=False)
        if not stat.S_ISREG(created.st_mode) or not _same_identity(
            temp_identity, created
        ):
            raise PublicInputError("written-file-invalid")
    except FileExistsError as exc:
        raise PublicInputError("target-exists") from exc
    except PublicInputError as exc:
        if created is not None:
            _remove_created_target(directory, created)
        raise exc
    except OSError as exc:
        if created is not None:
            _remove_created_target(directory, created)
        raise PublicInputError("atomic-publish-failed") from exc
    finally:
        _cleanup_temporary_file(directory, temp_name, created)
    if created is None:
        raise PublicInputError("atomic-publish-failed")
    return created


def _read_written(directory: int) -> tuple[bytes, os.stat_result]:
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_BINARY", 0)
    descriptor = os.open(_TARGET.name, flags, dir_fd=directory)
    with os.fdopen(descriptor, "rb") as stream:
        identity = os.fstat(stream.fileno())
        return stream.read(), identity


def _validate_written(directory: int, payload: bytes, created: os.stat_result) -> None:
    try:
        written_bytes, opened = _read_written(directory)
        current = os.stat(_TARGET.name, dir_fd=directory, follow_symlinks=False)
        if written_bytes != payload:
            raise PublicInputError("written-bytes-mismatch")
        written = json.loads(written_bytes.decode("utf-8"))
        if (
            not stat.S_ISREG(current.st_mode)
            or not _same_identity(created, opened)
            or not _same_identity(opened, current)
        ):
            raise PublicInputError("written-file-changed")
        if not isinstance(written, dict) or validate_canonical_timeline_public_input(
            written
        ):
            raise PublicInputError("written-input-invalid")
    except PublicInputError as exc:
        _remove_created_target(directory, created)
        raise exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _remove_created_target(directory, created)
        raise PublicInputError("written-input-unavailable") from exc


def _publish(payload: bytes) -> None:
    if not _secure_dir_fd_supported():
        raise PublicInputError("secure-directory-api-unavailable")
    _check_ancestors(_TARGET)
    if _target_is_tracked():
        raise PublicInputError("target-tracked")
    try:
        _TARGET.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PublicInputError("target-directory-unavailable") from exc
    _check_ancestors(_TARGET)
    directory = _open_stable_directory(_TARGET.parent, "target-directory-invalid")
    try:
        try:
            os.stat(_TARGET.name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise PublicInputError("target-exists")
        created = _create_target(directory, payload)
        _validate_written(directory, payload, created)
    finally:
        os.close(directory)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{64}", args.expected_projection_sha256):
        print("status=blocked code=expected-projection-digest-invalid", file=sys.stderr)
        return 2
    try:
        document, digest = _build(args)
        payload = _serialize(document)
        if not args.execute:
            print(f"status=dry_run projection_sha256={digest}")
            return 0
        if not _secure_dir_fd_supported():
            raise PublicInputError("secure-directory-api-unavailable")

        # execute直前に固定workspace入力を再読込し、review/digest/gateを再検査する。
        current_document, current_digest = _build(args)
        current_payload = _serialize(current_document)
        if current_digest != digest or current_payload != payload:
            raise PublicInputError("input-changed-before-execute")
        _publish(current_payload)
        print(f"status=written projection_sha256={digest}")
        return 0
    except PublicInputError as exc:
        print(f"status=blocked code={exc.code}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
