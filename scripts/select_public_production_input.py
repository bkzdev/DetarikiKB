#!/usr/bin/env python3
"""Production buildで使うcommit済みpublic inputをfail-closedに選ぶ。"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
_MAIN_REF = "origin/main"
REAL_INPUT_INTRODUCTION_SHA = "bb37a6274e79f504e5ddc3e240e2c4420196ca70"
REVIEWED_INPUT_PATH = "knowledge/public/timelines/canonical_timeline_public_input.json"
LEGACY_INPUT_PATH = (
    "tests/fixtures/canonical_timeline_public_input/approved_synthetic_input.json"
)


@dataclass(frozen=True)
class InputSelection:
    path: str
    profile: str


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=_PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _resolve_commit(revision: str) -> str | None:
    result = _git("rev-parse", "--verify", f"{revision}^{{commit}}")
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value if _SHA_PATTERN.fullmatch(value) else None


def _tree_has_blob(revision: str, path: str) -> bool:
    result = _git("cat-file", "-t", f"{revision}:{path}")
    return result.returncode == 0 and result.stdout.strip() == "blob"


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    return _git("merge-base", "--is-ancestor", ancestor, descendant).returncode == 0


def select_input(
    source_sha: str, expected_tree_sha256: str
) -> tuple[InputSelection | None, str | None]:
    """選択結果、または匿名blocking codeを返す。"""
    if _SHA_PATTERN.fullmatch(source_sha) is None:
        return None, "production-source-sha-invalid"
    try:
        trusted_main_sha = _resolve_commit(_MAIN_REF)
        introduction_sha = _resolve_commit(REAL_INPUT_INTRODUCTION_SHA)
        if trusted_main_sha is None or introduction_sha is None:
            return None, "production-public-input-boundary-unavailable"
        if _tree_has_blob(source_sha, REVIEWED_INPUT_PATH):
            return InputSelection(REVIEWED_INPUT_PATH, "reviewed-public-input"), None
        legacy_allowed = (
            source_sha != trusted_main_sha
            and source_sha != introduction_sha
            and bool(expected_tree_sha256)
            and _is_ancestor(source_sha, introduction_sha)
            and _tree_has_blob(source_sha, LEGACY_INPUT_PATH)
        )
        if legacy_allowed:
            return InputSelection(LEGACY_INPUT_PATH, "legacy-synthetic-rollback"), None
        return None, "production-public-input-unavailable"
    except OSError:
        return None, "production-git-unavailable"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="production revisionのcommit済みpublic inputを選択する"
    )
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--expected-tree-sha256", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    selection, code = select_input(args.source_sha, args.expected_tree_sha256)
    if code is not None:
        print(f"status=blocked code={code}")
        return 1
    assert selection is not None
    print(json.dumps(asdict(selection), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
