#!/usr/bin/env python3
"""
Build Story Manifest Candidates
ローカルのraw DECファイル配置（`EVENT`カテゴリのみ）から、
`story_manifest.yaml`候補（`schemas/story_manifest.schema.json`準拠）を
機械的に生成するCLI。

コアロジックは`agents/parser/story_manifest_candidates.py`にある
(このCLIはそのCLIエントリポイント)。

docs/architecture/05_Parser/Story_Manifest_Design.md 参照。

**重要**: このscriptはDEC本文を一切読まない（ファイル名・ディレクトリ名の
文字列処理のみ）。title/subtitle/displayTitleは常にnull、metadataStatusは
常にpendingとして出力する（DEC本文からタイトル・サブタイトルを推測する処理は
一切行わない）。実DECファイル・生成したmanifest候補はcommitしないこと
（`.gitignore`のworkspace/story_manifest/・story_manifest_candidates_*
パターンを参照）。

対応するraw配置（EVENTカテゴリのみ、他カテゴリは未対応）:

    EVENT/csl_script_event_{sourceKey}_export/
        CAB-csl_script_event_{sourceKey}-episode{N}.dec

Usage:
    uv run python scripts/build_story_manifest_candidates.py \\
        --raw-root /path/to/local/raw/root

    uv run python scripts/build_story_manifest_candidates.py \\
        --raw-root /path/to/local/raw/root \\
        --output workspace/story_manifest/candidates.yaml

Exit codes:
    0: 成功（該当するストーリーが0件でも成功）
    1: --raw-rootが存在しない、またはディレクトリでない
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.parser.story_manifest_candidates import (  # noqa: E402
    build_candidate_document,
    build_story_manifest_candidates,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "ローカルのraw DECファイル配置 (EVENTカテゴリのみ) から "
            "story_manifest.yaml候補を機械的に生成する"
        ),
    )
    parser.add_argument(
        "--raw-root",
        required=True,
        help="raw DECファイル群のルートディレクトリ (EVENT/等を直下に含む)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="生成したmanifest候補 (YAML) の書き出し先。省略時は件数サマリーのみ表示",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    raw_root = Path(args.raw_root)
    if not raw_root.is_dir():
        print(
            f"[エラー] --raw-rootがディレクトリとして見つかりません: {raw_root}",
            file=sys.stderr,
        )
        return 1

    candidates = build_story_manifest_candidates(raw_root)
    document = build_candidate_document(candidates)
    episode_count = sum(len(story["episodes"]) for story in candidates)

    if not args.quiet:
        print(
            f"[story-manifest] 検出したストーリー数: {len(candidates)} "
            f"(episode合計: {episode_count})"
        )
        for story in candidates:
            print(f"  - {story['storyId']} ({len(story['episodes'])} episodes)")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(document, f, allow_unicode=True, sort_keys=False)
        if not args.quiet:
            print(f"[story-manifest] 候補を書き出しました: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
