#!/usr/bin/env python3
"""
Merge Extractions Script
CLIから Stage A episode_extraction JSON群 (複数ファイル・ディレクトリ・
globパターンに対応) を検証し、Stage B merged knowledge collection
(skeleton) と、任意で独立merge report artifactを生成する入口。

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
        --report-output workspace/merge_preview/merge_report.json \\
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
from agents.merger.canonical_ids import validate_canonical_ids  # noqa: E402
from agents.merger.overrides import (  # noqa: E402
    apply_manual_overrides,
    build_manual_overrides_report,
    load_manual_overrides,
    load_manual_overrides_schema,
    validate_manual_overrides,
)

DEFAULT_OUTPUT_FILENAME = "merged_knowledge_collection.json"
RECOMMENDED_REPORT_OUTPUT = "data/extracted/reports/merge_report.json"


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
      --report-output workspace/merge_preview/merge_report.json \\
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
        "--report-output",
        default=None,
        metavar="FILE",
        help=(
            "collection内の最終reportを独立JSONとして書き出すファイルパス "
            f"(任意、正式運用の推奨先: {RECOMMENDED_REPORT_OUTPUT})"
        ),
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


def _report_path_conflicts_with_collection(
    output_dir: Path,
    output_path: Path,
    report_output_path: Path,
) -> bool:
    """reportをfileとして作れないcollection出力pathとの衝突を判定する。"""
    resolved_output_dir = output_dir.resolve()
    resolved_output_path = output_path.resolve()
    resolved_report_path = report_output_path.resolve()
    return (
        resolved_report_path == resolved_output_dir
        or resolved_report_path in resolved_output_dir.parents
        or resolved_report_path == resolved_output_path
        or resolved_output_path in resolved_report_path.parents
    )


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
        # manual overrideはcanonicalIdを書き換えうる (operation: set_field,
        # field: "canonicalId") ため、override適用後のcollectionで
        # canonicalIdSummaryを再計算する (Canonical_ID_Policy.md §7)。
        # invalidなcanonicalIdがoverrideで指定された場合もexit codeは
        # 変更せず、report warningとして記録するに留める。
        collection["report"]["canonicalIdSummary"] = validate_canonical_ids(
            collection
        ).to_dict()
        report = collection["report"]

    output_dir = Path(args.output)
    output_path = output_dir / DEFAULT_OUTPUT_FILENAME
    report_output_path = (
        Path(args.report_output) if args.report_output is not None else None
    )
    if report_output_path is not None and _report_path_conflicts_with_collection(
        output_dir, output_path, report_output_path
    ):
        print(
            "[エラー] --report-outputはmerged collectionの出力先と"
            "衝突しないファイルパスを指定してください",
            file=sys.stderr,
        )
        return 2
    if report_output_path is not None and report_output_path.is_dir():
        print(
            f"[エラー] --report-outputにはファイルパスを指定してください: "
            f"{report_output_path}",
            file=sys.stderr,
        )
        return 2

    try:
        # 設定・親directory作成の失敗では、どちらのartifactも書き出さない。
        output_dir.mkdir(parents=True, exist_ok=True)
        if report_output_path is not None:
            report_output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(report_output_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(collection, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[エラー] 出力失敗: {e}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"[DKB] 出力完了: {output_path}")
        if report_output_path is not None:
            print(f"[DKB] merge report出力完了: {report_output_path}")
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
