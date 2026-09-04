#!/usr/bin/env python3
"""MkDocs / Zensicalのdetached public site manifestを比較する。"""

from __future__ import annotations

import argparse
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
    validate_public_site_manifest_pair,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="public site manifest dual-build比較")
    parser.add_argument("--mkdocs-manifest", required=True, type=Path)
    parser.add_argument("--zensical-manifest", required=True, type=Path)
    return parser.parse_args(argv)


def _identity(item: os.stat_result) -> tuple[int, int, int, int]:
    return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns


def _is_reparse(item: os.stat_result) -> bool:
    return stat.S_ISLNK(item.st_mode) or bool(
        (getattr(item, "st_file_attributes", 0) or 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _load(path: Path) -> dict:
    try:
        before = path.lstat()
        if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
            raise PublicSiteError("public-site-manifest-input-unavailable")
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
            raise PublicSiteError("public-site-manifest-input-unavailable")
        value = json.loads(payload.decode("utf-8"))
        if not isinstance(value, dict):
            raise PublicSiteError("public-site-manifest-input-invalid")
        return value
    except PublicSiteError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublicSiteError("public-site-manifest-input-invalid") from exc


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        mkdocs_manifest = _load(args.mkdocs_manifest)
        zensical_manifest = _load(args.zensical_manifest)
        if findings := validate_public_site_manifest_pair(
            mkdocs_manifest, zensical_manifest
        ):
            raise PublicSiteError(findings[0])
        print("status=clean")
        return 0
    except PublicSiteError as exc:
        print(f"status=blocked code={exc.code}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
