#!/usr/bin/env python3
"""
Render Wiki
merged knowledge collection (schemas/merged_knowledge_collection.schema.json)
からWiki Markdownを生成するCLI (agents/wiki_generator/ のrenderer skeleton
のエントリポイント)。

docs/architecture/07_Wiki/Wiki_Output_Design.md のPhase 1のうち、
Top page / Story index / Episode page (簡易) / Character page /
Unresolved report pageのみを生成する。

**重要**: 実データ由来のmerged knowledge collectionを入力にしてよいが、
出力したMarkdownはcommitしないこと（docs/runbooks/Real_Data_Dry_Run.md
と同じ既存ルール）。出力先は原則 workspace/ 配下 (.gitignore対象) か
tmp_pathを使うこと。

Usage:
    uv run python scripts/render_wiki.py \\
        --input tests/fixtures/wiki/synthetic_merged_collection.json \\
        --output workspace/wiki_preview

    # 入力のschema検証も行う場合
    uv run python scripts/render_wiki.py \\
        --input tests/fixtures/wiki/synthetic_merged_collection.json \\
        --output workspace/wiki_preview --validate

    # 出力先を事前にクリアしてから生成する場合
    uv run python scripts/render_wiki.py \\
        --input tests/fixtures/wiki/synthetic_merged_collection.json \\
        --output workspace/wiki_preview --clean

Exit codes:
    0: 生成成功
    1: 入力ファイルが見つからない、またはJSONとして読み込めない
    2: --validate指定時にschema検証に失敗した
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.wiki_generator import build_pages, write_pages  # noqa: E402

DEFAULT_SCHEMA_PATH = (
    _PROJECT_ROOT / "schemas" / "merged_knowledge_collection.schema.json"
)


def load_collection(path: Path) -> dict | None:
    """merged knowledge collection JSONを読み込む。

    読み込みに失敗した場合はNoneを返す (呼び出し側でexit code 1にする)。
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def validate_collection(collection: dict, schema_path: Path) -> list[str]:
    """merged_knowledge_collection.schema.jsonでcollectionを検証する。

    戻り値: エラーメッセージのリスト (空なら検証OK)。
    """
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(collection), key=lambda e: list(e.path))
    return [f"{list(e.path)}: {e.message}" for e in errors]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "merged knowledge collectionからWiki Markdownを生成する "
            "(agents/wiki_generator/ のrenderer skeleton)"
        ),
    )
    parser.add_argument(
        "--input",
        required=True,
        help="merged knowledge collection JSONのパス",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="生成したMarkdownの出力先ディレクトリ",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="生成前に出力先ディレクトリを削除する",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help=(
            "入力をschemas/merged_knowledge_collection.schema.jsonで"
            "検証してから生成する"
        ),
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

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[エラー] 入力ファイルが見つかりません: {input_path}", file=sys.stderr)
        return 1

    collection = load_collection(input_path)
    if collection is None:
        print(f"[エラー] JSONとして読み込めませんでした: {input_path}", file=sys.stderr)
        return 1

    if args.validate:
        errors = validate_collection(collection, DEFAULT_SCHEMA_PATH)
        if errors:
            print(
                "[エラー] merged knowledge collectionのschema検証に失敗しました:",
                file=sys.stderr,
            )
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 2
        if not args.quiet:
            print("[wiki] schema検証: OK")

    pages = build_pages(collection)
    output_dir = Path(args.output)
    written = write_pages(pages, output_dir, clean=args.clean)

    if not args.quiet:
        print(f"[wiki] {len(written)} 件のMarkdownを生成しました: {output_dir}")
        for path in sorted(written):
            print(f"  - {path.relative_to(output_dir)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
