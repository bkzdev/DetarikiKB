#!/usr/bin/env python3
"""Manual production gate用source commitを匿名・fail-closedに検証する。"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
_SOURCE_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
_MAIN_REF = "origin/main"


def _git_succeeds(*arguments: str) -> bool:
    result = subprocess.run(
        ["git", *arguments],
        cwd=_PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def check_source(source_sha: str) -> str | None:
    """Return an anonymous blocking code, or ``None`` when the source is valid."""

    if _SOURCE_SHA_PATTERN.fullmatch(source_sha) is None:
        return "production-source-sha-invalid"

    try:
        if not _git_succeeds("rev-parse", "--verify", f"{_MAIN_REF}^{{commit}}"):
            return "production-main-ref-unavailable"
        if not _git_succeeds("cat-file", "-e", f"{source_sha}^{{commit}}"):
            return "production-source-commit-unavailable"
        if not _git_succeeds("merge-base", "--is-ancestor", source_sha, _MAIN_REF):
            return "production-source-not-on-main"
    except OSError:
        return "production-git-unavailable"
    return None


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("status=blocked code=production-source-sha-invalid")
        return 1
    code = check_source(arguments[0])
    if code is not None:
        print(f"status=blocked code={code}")
        return 1
    print("status=clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
