#!/usr/bin/env python3
"""生成済みpublic siteを検査しdetached manifest候補を構築する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.wiki_generator.public_site_manifest import (  # noqa: E402
    PublicSiteError,
    build_public_site_manifest,
)

_SECURE_DIR_FD_WRITE_SUPPORTED = all(
    operation in os.supports_dir_fd for operation in (os.open, os.stat, os.unlink)
)


def _identity(item: os.stat_result) -> tuple[int, int, int, int]:
    return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns


def _file_key(item: os.stat_result) -> tuple[int, int]:
    return item.st_dev, item.st_ino


def _is_reparse(item: os.stat_result) -> bool:
    return stat.S_ISLNK(item.st_mode) or bool(
        (getattr(item, "st_file_attributes", 0) or 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="生成済みpublic siteのmanifest / exposure gate（既定dry-run）"
    )
    parser.add_argument("--site-dir", required=True, type=Path)
    parser.add_argument("--public-input", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--lock-file", required=True, type=Path)
    parser.add_argument(
        "--generator-name", required=True, choices=("mkdocs-material", "zensical")
    )
    parser.add_argument("--generator-version", required=True)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument(
        "--write-manifest", action="store_true", help="manifestを新規作成する"
    )
    return parser.parse_args(argv)


def _read_regular(path: Path, code: str) -> bytes:
    try:
        before = path.lstat()
        if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
            raise PublicSiteError(code)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            payload = stream.read()
        after = path.lstat()
        if _identity(before) != _identity(opened) or _identity(opened) != _identity(
            after
        ):
            raise PublicSiteError(code)
        return payload
    except PublicSiteError:
        raise
    except OSError as exc:
        raise PublicSiteError(code) from exc


def _serialize(manifest: dict) -> bytes:
    return (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _open_output_parent(path: Path, site_root: Path) -> int:
    resolved_parent = path.parent.resolve(strict=True)
    resolved_site = site_root.resolve(strict=True)
    resolved_target = resolved_parent / path.name
    if resolved_target == resolved_site or resolved_site in resolved_target.parents:
        raise PublicSiteError("manifest-output-inside-site")
    if not _SECURE_DIR_FD_WRITE_SUPPORTED:
        raise PublicSiteError("manifest-output-secure-write-unavailable")
    parent_before = resolved_parent.lstat()
    if _is_reparse(parent_before) or not stat.S_ISDIR(parent_before.st_mode):
        raise PublicSiteError("manifest-output-unavailable")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(resolved_parent, flags)
    if _identity(parent_before) != _identity(os.fstat(descriptor)):
        os.close(descriptor)
        raise PublicSiteError("manifest-output-unavailable")
    return descriptor


def _remove_created_file(
    parent_descriptor: int, name: str, key: tuple[int, int]
) -> None:
    try:
        current = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        if _file_key(current) == key:
            os.unlink(name, dir_fd=parent_descriptor)
    except OSError:
        pass


def _write_payload(parent_descriptor: int, name: str, payload: bytes) -> None:
    created_file_key: tuple[int, int] | None = None
    completed = False
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(name, flags, 0o600, dir_fd=parent_descriptor)
        with os.fdopen(descriptor, "wb") as stream:
            created_file_key = _file_key(os.fstat(stream.fileno()))
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            written = os.fstat(stream.fileno())
            if written.st_size != len(payload):
                raise OSError("short manifest write")
        after = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        if _identity(after) != _identity(written):
            raise OSError("manifest output changed during write")
        completed = True
    finally:
        if not completed and created_file_key is not None:
            _remove_created_file(parent_descriptor, name, created_file_key)


def _write_new(path: Path, payload: bytes, site_root: Path) -> None:
    parent_descriptor: int | None = None
    try:
        parent_descriptor = _open_output_parent(path, site_root)
        _write_payload(parent_descriptor, path.name, payload)
    except FileExistsError as exc:
        raise PublicSiteError("manifest-output-exists") from exc
    except PublicSiteError:
        raise
    except OSError as exc:
        raise PublicSiteError("manifest-output-unavailable") from exc
    finally:
        if parent_descriptor is not None:
            os.close(parent_descriptor)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.write_manifest != (args.manifest_output is not None):
        print("status=blocked code=manifest-output-arguments-invalid", file=sys.stderr)
        return 2
    try:
        public_input = _read_regular(args.public_input, "public-input-unavailable")
        lock_bytes = _read_regular(args.lock_file, "lock-file-unavailable")
        config_bytes = _read_regular(args.config, "config-file-unavailable")
        manifest = build_public_site_manifest(
            args.site_dir,
            source_sha=args.source_sha,
            lock_bytes=lock_bytes,
            public_input_bytes=public_input,
            generator_name=args.generator_name,
            generator_version=args.generator_version,
            config_bytes=config_bytes,
        )
        payload = _serialize(manifest)
        digest = hashlib.sha256(payload).hexdigest()
        if args.write_manifest:
            _write_new(args.manifest_output, payload, args.site_dir)
            print(f"status=written manifest_sha256={digest}")
        else:
            print(f"status=dry_run manifest_sha256={digest}")
        return 0
    except PublicSiteError as exc:
        print(f"status=blocked code={exc.code}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
