#!/usr/bin/env python3
"""
Build Story Title/Subtitle Candidates
外部情報源（Wiki story list、公式告知、ゲーム画面メモ等）をCSVへ書き出した
ものから、`story_manifest.yaml`のtitle/subtitle候補
（`documentType: "story_title_subtitle_candidates"`）を組み立てるCLI。

コアロジックは`agents/parser/story_title_subtitle_candidates.py`にある
（このCLIはそのCLIエントリポイント）。

docs/architecture/05_Parser/Story_Manifest_Design.md §11.7・
docs/runbooks/Story_Title_Subtitle_Import.md 参照。

**重要**: このscriptは実source取得（Wiki取得等）を行わない。CSV入力に
書かれた値をそのまま候補として組み立てるのみで、`story_manifest.yaml`
への反映（confirmed化）は一切行わない。すべての候補は
`reviewStatus: "pending"`として出力される。実CSV・生成した候補は
commitしないこと（`.gitignore`参照）。

Usage:
    uv run python scripts/build_story_title_subtitle_candidates.py \\
        --input-csv workspace/story_manifest/title_subtitle_rows.csv \\
        --source-type wiki_story_list \\
        --source-label "デタリキZ攻略Wiki ストーリー一覧" \\
        --manifest workspace/story_manifest/story_manifest_candidates.yaml \\
        --output workspace/story_manifest/title_subtitle_candidates.yaml

Exit codes:
    0: 成功（候補が0件でも成功）
    1: --input-csvが見つからない、または--manifestで指定したファイルが見つからない
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.parser.story_manifest import load_story_manifest  # noqa: E402
from agents.parser.story_title_subtitle_candidates import (  # noqa: E402
    build_candidate_document,
    build_candidates_from_rows,
    read_candidate_rows_from_csv,
)

_SOURCE_TYPE_CHOICES = (
    "manual",
    "official_game_ui",
    "official_announcement",
    "wiki_story_list",
    "wiki_event_page",
    "imported_candidate",
    "unknown",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "外部情報源由来のCSVから、story_manifest.yamlのtitle/subtitle "
            "候補ドキュメントを組み立てる"
        ),
    )
    parser.add_argument(
        "--input-csv",
        required=True,
        help=(
            "候補行のCSVパス (列: storyId/episodeId/episodeNumber/"
            "proposedTitle/proposedDisplayTitle/proposedSubtitle/"
            "confidence/notes)"
        ),
    )
    parser.add_argument(
        "--source-type",
        required=True,
        choices=_SOURCE_TYPE_CHOICES,
        help="このCSV全体の出典種別 (Story_Manifest_Design.md §11.5)",
    )
    parser.add_argument(
        "--source-label",
        default=None,
        help="出典の自由記述ラベル (例: デタリキZ攻略Wiki ストーリー一覧)",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help=(
            "既存のstory_manifest.yaml相当のパス (任意)。指定した場合、"
            "各storyId/episodeIdがmanifestに実在するかをfoundInManifest"
            "として記録する (一致有無に関わらず候補は必ず出力する)"
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help="生成した候補 (YAML) の書き出し先。省略時は件数サマリーのみ表示",
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

    csv_path = Path(args.input_csv)
    if not csv_path.exists():
        print(f"[エラー] --input-csvが見つかりません: {csv_path}", file=sys.stderr)
        return 1

    manifest = None
    if args.manifest:
        manifest_path = Path(args.manifest)
        if not manifest_path.exists():
            print(
                f"[エラー] --manifestファイルが見つかりません: {manifest_path}",
                file=sys.stderr,
            )
            return 1
        manifest = load_story_manifest(manifest_path)

    rows = read_candidate_rows_from_csv(csv_path)
    candidates = build_candidates_from_rows(rows, manifest)
    document = build_candidate_document(candidates, args.source_type, args.source_label)

    episode_count = sum(len(story["episodes"]) for story in candidates)
    unmatched_stories = sum(1 for story in candidates if not story["foundInManifest"])

    if not args.quiet:
        print(
            f"[title-subtitle-candidates] 候補ストーリー数: {len(candidates)} "
            f"(episode候補合計: {episode_count}、manifest未一致story: "
            f"{unmatched_stories})"
        )
        for story in candidates:
            found = "matched" if story["foundInManifest"] else "unmatched"
            print(
                f"  - {story['storyId']} ({len(story['episodes'])} episodes, {found})"
            )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(document, f, allow_unicode=True, sort_keys=False)
        if not args.quiet:
            print(f"[title-subtitle-candidates] 候補を書き出しました: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
