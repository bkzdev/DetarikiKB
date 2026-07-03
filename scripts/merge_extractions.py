#!/usr/bin/env python3
"""
Merge Extractions Script
CLIから Stage A episode_extraction JSON (単一ファイル) を検証し、
Stage B merged knowledge collection (skeleton) を生成する入口。

複数ファイル・ディレクトリ入力は今回のskeletonでは対応しない (将来拡張)。
本格的なcandidate merge・canonical ID割り当て・manual override適用・
conflict解決はまだ実装していない。entities配下は空配列のまま出力し、
merge reportに入力集計 (inputFiles/validInputs/invalidInputs/
candidateCounts等) を記録する。

Usage:
    python scripts/merge_extractions.py \\
        --input tests/fixtures/extraction/minimal_episode_extraction.json \\
        --output workspace/merge_preview

Exit codes:
    0: 入力がvalidationを通過し、collectionを出力した
    1: 入力がvalidation (JSON Schema / semantic) に失敗した
    2: 入力ファイルが見つからない、または出力に失敗した
"""

import argparse
import json
import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.merger import MergeEngine  # noqa: E402

DEFAULT_OUTPUT_FILENAME = "merged_knowledge_collection.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stage A episode_extraction JSON (単一ファイル) を検証し、"
            "merged knowledge collection (skeleton) を生成します"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python scripts/merge_extractions.py \\
      --input tests/fixtures/extraction/minimal_episode_extraction.json \\
      --output workspace/merge_preview
""",
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="入力episode_extraction JSONファイル (単一ファイルのみ対応)",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help=f"出力先ディレクトリ ({DEFAULT_OUTPUT_FILENAME} を書き出す)",
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
        return 2
    if input_path.is_dir():
        print(
            "[エラー] ディレクトリ入力は未対応です (単一ファイルを指定してください)",
            file=sys.stderr,
        )
        return 2

    if not args.quiet:
        print("[DKB] merge_extractions (skeleton)")
        print(f"[DKB] 入力ファイル: {input_path}")

    engine = MergeEngine()
    collection = engine.merge_file(input_path)
    report = collection["report"]

    output_dir = Path(args.output)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / DEFAULT_OUTPUT_FILENAME
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(collection, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[エラー] 出力失敗: {output_dir}: {e}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"[DKB] 出力完了: {output_path}")
        print(
            f"[DKB] 検証結果: valid={report['validInputs']} "
            f"invalid={report['invalidInputs']}"
        )

    if report["invalidInputs"] > 0:
        print("[エラー] 入力がvalidationに失敗しました", file=sys.stderr)
        for message in report["errors"][:20]:
            print(f"  - {message}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
