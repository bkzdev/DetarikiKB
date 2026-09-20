#!/usr/bin/env python3
"""story manifestとH_scene動的判定からv1 release scopeを一括normalizeする。

出力先は既存pathを拒否し、全episodeのparse・schema検証と匿名report検証が
成功した場合だけ一時directoryをrenameして公開する。実Normalized Storyと
reportはignored workspaceに置き、commitしないこと。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.parser.release_scope import normalize_release_scope  # noqa: E402

DEFAULT_CHARACTERS = _PROJECT_ROOT / "knowledge" / "dictionaries" / "characters.yaml"
DEFAULT_COMMANDS = _PROJECT_ROOT / "config" / "script_commands.yaml"
DEFAULT_STORY_SCHEMA = _PROJECT_ROOT / "schemas" / "story.schema.json"
DEFAULT_MANIFEST_SCHEMA = _PROJECT_ROOT / "schemas" / "story_manifest.schema.json"
DEFAULT_REPORT_SCHEMA = (
    _PROJECT_ROOT / "schemas" / "release_scope_normalization_report.schema.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="v1 release scopeをfail-closedで一括normalizeします"
    )
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--characters", default=str(DEFAULT_CHARACTERS))
    parser.add_argument("--commands", default=str(DEFAULT_COMMANDS))
    parser.add_argument("--story-schema", default=str(DEFAULT_STORY_SCHEMA))
    parser.add_argument("--manifest-schema", default=str(DEFAULT_MANIFEST_SCHEMA))
    parser.add_argument("--report-schema", default=str(DEFAULT_REPORT_SCHEMA))
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--quiet", "-q", action="store_true")
    return parser.parse_args()


def _git(*arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=_PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise ValueError("release source git command is unavailable") from exc
    if result.returncode != 0:
        raise ValueError("release source git command failed")
    return result.stdout.strip()


def _verify_source_revision(source_sha: str) -> None:
    _git(
        "fetch",
        "--quiet",
        "--no-tags",
        "origin",
        "refs/heads/main:refs/remotes/origin/main",
    )
    if _git("status", "--porcelain"):
        raise ValueError("release source worktree is dirty")
    if _git("branch", "--show-current") != "main":
        raise ValueError("release source branch is not main")
    if _git("rev-parse", "HEAD") != source_sha:
        raise ValueError("release source does not match HEAD")
    if _git("rev-parse", "origin/main") != source_sha:
        raise ValueError("release source does not match origin/main")


def main() -> int:
    args = parse_args()
    try:
        _verify_source_revision(args.source_sha)
        report = normalize_release_scope(
            raw_root=Path(args.raw_root),
            manifest_path=Path(args.manifest),
            output_root=Path(args.output),
            characters_path=Path(args.characters),
            commands_path=Path(args.commands),
            story_schema_path=Path(args.story_schema),
            manifest_schema_path=Path(args.manifest_schema),
            report_schema_path=Path(args.report_schema),
            source_revision=args.source_sha,
        )
    except Exception as exc:
        print(f"[release-scope] failed: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        safe_summary = {
            key: report[key]
            for key in (
                "manifestStoryCount",
                "manifestEpisodeCount",
                "dynamicExceptionEpisodeCount",
                "normalizedEpisodeCount",
                "invalidCount",
                "skippedCount",
                "categoryEpisodeCounts",
                "compatibilityStatusCounts",
                "unknownBlockCount",
                "unknownCommandDistinctCount",
                "unknownCharacterIdDistinctCount",
            )
        }
        print(json.dumps(safe_summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
