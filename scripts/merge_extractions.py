#!/usr/bin/env python3
"""
Merge Extractions Script
CLIから Stage A episode_extraction JSON群 (複数ファイル・ディレクトリ・
globパターンに対応) を検証し、Stage B merged knowledge collection
(skeleton) を生成する入口。

本格的なcandidate merge・canonical ID割り当て・manual override適用・
conflict解決はまだ実装していない。entities配下は空配列のまま出力し、
merge reportに入力集計 (inputFiles/resolvedInputFiles/validInputs/
invalidInputs/skippedInputs/candidateCounts/inputResults等) を記録する。

Usage:
    # 複数ファイル
    python scripts/merge_extractions.py \\
        --input data/extracted/_raw/EP01.extraction.json \\
                data/extracted/_raw/EP02.extraction.json \\
        --output workspace/merge_preview

    # ディレクトリ (直下の *.json を収集。--recursive でサブディレクトリも)
    python scripts/merge_extractions.py \\
        --input data/extracted/_raw/ --output workspace/merge_preview

    # globパターン (Python側で展開するため、シェルのクォート推奨)
    python scripts/merge_extractions.py \\
        --input "tests/fixtures/extraction/*.json" \\
        --output workspace/merge_preview

Exit codes:
    0: すべての入力を解決・検証でき、collectionを出力した
    1: 一部の入力がvalidation失敗、または解決できなかった (invalid/skipped)
    2: 1件も入力ファイルを解決できなかった、または出力に失敗した
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
            "Stage A episode_extraction JSON群 (複数ファイル/ディレクトリ/"
            "globパターン) を検証し、merged knowledge collection "
            "(skeleton) を生成します"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python scripts/merge_extractions.py \\
      --input file1.json file2.json --output workspace/merge_preview

  python scripts/merge_extractions.py \\
      --input data/extracted/_raw/ --output workspace/merge_preview

  python scripts/merge_extractions.py \\
      --input "tests/fixtures/extraction/*.json" \\
      --output workspace/merge_preview
""",
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        nargs="+",
        help=(
            "入力episode_extraction JSON。ファイルパス・ディレクトリパス・"
            "globパターン文字列を1つ以上指定できる"
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help=f"出力先ディレクトリ ({DEFAULT_OUTPUT_FILENAME} を書き出す)",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="ディレクトリ入力・globパターンをサブディレクトリまで再帰的に探索する",
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

    if not args.quiet:
        print("[DKB] merge_extractions (skeleton)")
        print(f"[DKB] 入力引数: {len(args.input)} 件")

    engine = MergeEngine()
    collection = engine.merge_inputs(args.input, recursive=args.recursive)
    report = collection["report"]

    if report["resolvedInputFiles"] == 0:
        print("[エラー] 解決できた入力ファイルがありません", file=sys.stderr)
        for result in report["inputResults"]:
            for warning in result["warnings"]:
                print(f"  - {warning}", file=sys.stderr)
        return 2

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
            f"[DKB] 検証結果: resolved={report['resolvedInputFiles']} "
            f"valid={report['validInputs']} invalid={report['invalidInputs']} "
            f"skipped={len(report['skippedInputs'])}"
        )

    if report["invalidInputs"] > 0 or report["skippedInputs"]:
        print(
            "[エラー] 一部の入力がvalidationに失敗、または解決できませんでした",
            file=sys.stderr,
        )
        for message in report["errors"][:20]:
            print(f"  - {message}", file=sys.stderr)
        for raw in report["skippedInputs"]:
            print(f"  - skipped: {raw}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
