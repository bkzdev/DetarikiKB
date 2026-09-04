#!/usr/bin/env python3
"""Commit済みpublic inputから一時build source/configを準備する。"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.wiki_generator.public_build import (  # noqa: E402
    PublicBuildError,
    build_public_source_files,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="commit済みpublic inputから一時build treeを準備する"
    )
    parser.add_argument("--public-input", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    return parser.parse_args(argv)


def _identity(item: os.stat_result) -> tuple[int, int, int, int]:
    return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns


def _is_reparse(item: os.stat_result) -> bool:
    return stat.S_ISLNK(item.st_mode) or bool(
        (getattr(item, "st_file_attributes", 0) or 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _read_regular(path: Path) -> bytes:
    try:
        before = path.lstat()
        if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
            raise PublicBuildError("public-build-input-unavailable")
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
            raise PublicBuildError("public-build-input-unavailable")
        return payload
    except PublicBuildError:
        raise
    except OSError as exc:
        raise PublicBuildError("public-build-input-unavailable") from exc


def _config(site_dir: str, *, zensical: bool) -> bytes:
    config: dict = {
        "site_name": "Detariki Knowledge Base",
        "site_description": "Synthetic public build verification.",
        "docs_dir": "source",
        "site_dir": site_dir,
        "theme": {"name": "material"},
    }
    if zensical:
        config["theme"]["variant"] = "classic"
        config["plugins"] = ["search"]
    return yaml.safe_dump(config, allow_unicode=True, sort_keys=False).encode("utf-8")


def _write_new(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)


def _prepare(output_root: Path, files: dict[str, bytes]) -> None:
    try:
        resolved_parent = output_root.parent.resolve(strict=True)
        target = resolved_parent / output_root.name
        if target == _PROJECT_ROOT or _PROJECT_ROOT in target.parents:
            raise PublicBuildError("public-build-output-inside-repository")
        target.mkdir(mode=0o700)
        source = target / "source"
        for relative, payload in files.items():
            _write_new(source / relative, payload)
        _write_new(
            target / "mkdocs-public.yml",
            _config("site-mkdocs", zensical=False),
        )
        _write_new(
            target / "zensical-public.yml",
            _config("site-zensical", zensical=True),
        )
        (target / "manifests").mkdir()
    except PublicBuildError:
        raise
    except FileExistsError as exc:
        raise PublicBuildError("public-build-output-exists") from exc
    except OSError as exc:
        raise PublicBuildError("public-build-output-unavailable") from exc


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = _read_regular(args.public_input)
        try:
            public_input = json.loads(payload.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise PublicBuildError("public-build-input-invalid") from exc
        if not isinstance(public_input, dict):
            raise PublicBuildError("public-build-input-invalid")
        files = build_public_source_files(public_input)
        _prepare(args.output_root, files)
        print(f"status=prepared file_count={len(files)}")
        return 0
    except PublicBuildError as exc:
        print(f"status=blocked code={exc.code}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
