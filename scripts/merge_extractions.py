#!/usr/bin/env python3
"""
Merge Extractions Script
CLIから Stage A episode_extraction JSON群 (複数ファイル・ディレクトリ・
globパターンに対応) を検証し、Stage B merged knowledge collection
(skeleton) を生成する入口。

本格的なcandidate merge・canonical ID割り当て・conflict解決の本格実装は
まだ実装していない。--overridesを指定すると、merge後のcollectionへ
manual override (schemas/manual_overrides.schema.json) を適用できる
(displayName/status/canonicalIdの上書き、aliasesの追加・削除のみ対応。
Merged_Knowledge_Design.md §8)。

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

    # manual overrideを適用
    python scripts/merge_extractions.py \\
        --input data/extracted/_raw/ --output workspace/merge_preview \\
        --overrides overrides/base.json --overrides overrides/characters.json

Exit codes:
    0: すべての入力を解決・検証でき、collectionを出力した
    1: 一部の入力がvalidation失敗、または解決できなかった (invalid/skipped)、
       もしくはoverrideファイルがschema検証に失敗した
    2: 1件も入力ファイルを解決できなかった、overrideファイルが見つからない/
       読み込めない、または出力に失敗した
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
from agents.merger.overrides import (  # noqa: E402
    apply_manual_overrides,
    build_manual_overrides_report,
    load_manual_overrides,
    load_manual_overrides_schema,
    validate_manual_overrides,
)

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

  python scripts/merge_extractions.py \\
      --input data/extracted/_raw/ --output workspace/merge_preview \\
      --overrides overrides/base.json --overrides overrides/characters.json
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
        "--overrides",
        nargs="+",
        default=None,
        help=(
            "manual override JSONファイル (schemas/manual_overrides.schema.json"
            "準拠) を1つ以上指定する。指定しない場合は既存挙動のまま"
            "(merged collectionにreport.manualOverridesは含まれない)"
        ),
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


def _load_and_validate_overrides(
    override_paths: list[str],
) -> tuple[list[str], list[dict]] | None:
    """--overridesで指定された全ファイルを読み込み・schema検証する。

    成功時: (ファイルパス文字列の一覧, overridesエントリの結合リスト)
    失敗時: None (呼び出し側でエラーメッセージ出力・exit済み)
    """
    schema = load_manual_overrides_schema()
    override_files: list[str] = []
    all_overrides: list[dict] = []

    for raw_path in override_paths:
        path = Path(raw_path)
        if not path.exists():
            print(f"[エラー] overrideファイルが見つかりません: {path}", file=sys.stderr)
            return None

        try:
            data = load_manual_overrides(path)
        except (OSError, json.JSONDecodeError) as e:
            print(
                f"[エラー] overrideファイル読み込み失敗: {path}: {e}",
                file=sys.stderr,
            )
            return None

        errors = validate_manual_overrides(data, schema=schema)
        if errors:
            print(
                f"[エラー] overrideファイルのschema検証に失敗しました: {path}",
                file=sys.stderr,
            )
            for message in errors[:10]:
                print(f"  - {message}", file=sys.stderr)
            return None

        override_files.append(str(path))
        all_overrides.extend(data.get("overrides", []) or [])

    return override_files, all_overrides


def main() -> int:  # noqa: C901
    args = parse_args()

    if not args.quiet:
        print("[DKB] merge_extractions (skeleton)")
        print(f"[DKB] 入力引数: {len(args.input)} 件")

    override_files: list[str] = []
    all_overrides: list[dict] = []
    if args.overrides:
        loaded = _load_and_validate_overrides(args.overrides)
        if loaded is None:
            return 1
        override_files, all_overrides = loaded

    engine = MergeEngine()
    collection = engine.merge_inputs(args.input, recursive=args.recursive)
    report = collection["report"]

    if report["resolvedInputFiles"] == 0:
        print("[エラー] 解決できた入力ファイルがありません", file=sys.stderr)
        for result in report["inputResults"]:
            for warning in result["warnings"]:
                print(f"  - {warning}", file=sys.stderr)
        return 2

    if args.overrides:
        collection, override_results = apply_manual_overrides(
            collection, {"overrides": all_overrides}
        )
        manual_overrides_report = build_manual_overrides_report(
            override_files, override_results
        )
        collection["report"]["manualOverrides"] = manual_overrides_report
        # engine自体はoverrideの存在を知らないため (report.warningCountsは
        # merge_inputs時点でskippedOverrides=0のまま)、CLI層でのみ判明する
        # manualOverrides.skippedCountをここで反映する。
        collection["report"]["warningCounts"]["skippedOverrides"] = (
            manual_overrides_report["skippedCount"]
        )
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
            f"[DKB] 検証結果: resolved={report['resolvedInputFiles']} "
            f"valid={report['validInputs']} invalid={report['invalidInputs']} "
            f"skipped={len(report['skippedInputs'])}"
        )
        if args.overrides:
            manual_overrides = report["manualOverrides"]
            print(
                f"[DKB] manual override: applied={manual_overrides['appliedCount']} "
                f"skipped={manual_overrides['skippedCount']} "
                f"error={manual_overrides['errorCount']}"
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
