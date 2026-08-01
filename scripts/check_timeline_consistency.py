#!/usr/bin/env python3
"""Stage A episode_extraction群のtimeline矛盾を横断検出する。

Exit codes:
    0: 入力がすべてvalidで矛盾なし
    1: 矛盾あり、またはinvalid/skipped inputあり
    2: 入力を1件も解決できない、設定・report出力失敗
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.extractor.timeline_consistency import (  # noqa: E402
    analyze_timeline_consistency,
)
from agents.merger.engine import MergeEngine  # noqa: E402
from agents.merger.input_resolver import resolve_input_entries  # noqa: E402

REPORT_SCHEMA_PATH = (
    _PROJECT_ROOT / "schemas" / "timeline_consistency_report.schema.json"
)
_DRY_RUN_ROOT = (_PROJECT_ROOT / "workspace" / "dry_runs").resolve()
_GLOB_CHARS = "*?["


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "複数のStage A episode_extraction JSONからrelative_orderの"
            "same_time class内矛盾・有向循環、episode metadata順序値の競合、"
            "canonicalOrderと同一story内相対制約の不整合を検出します"
        )
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        nargs="+",
        help="入力JSONファイル、ディレクトリ、globパターンを1つ以上指定",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="ディレクトリ・glob入力を再帰探索する",
    )
    parser.add_argument(
        "--report-output",
        metavar="FILE",
        help=(
            "JSON report出力先。repo内ではworkspace/dry_runs配下のみ可。"
            "既存ファイルは上書きしない"
        ),
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="集計メッセージを抑制する",
    )
    return parser.parse_args()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_report_output(path: Path, protected_inputs: list[Path]) -> None:
    lexical = path.absolute()
    resolved = path.resolve()
    target_is_in_dry_run = _is_relative_to(lexical, _DRY_RUN_ROOT) and _is_relative_to(
        resolved, _DRY_RUN_ROOT
    )
    if not target_is_in_dry_run:
        raise ValueError("report-outputはworkspace/dry_runs配下に指定してください")

    for input_path in protected_inputs:
        protected = input_path.resolve()
        if protected.is_dir() and _is_relative_to(resolved, protected):
            raise ValueError("report-outputを入力ディレクトリ内には指定できません")
        if protected.is_file() and resolved == protected:
            raise ValueError("report-outputを入力ファイルと同じ場所には指定できません")
    if path.exists():
        raise ValueError("report-outputは既に存在します")


def _validate_report(report: dict[str, Any]) -> None:
    schema = json.loads(REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(
        Draft7Validator(schema).iter_errors(report), key=lambda error: list(error.path)
    )
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.path) or "(root)"
        raise ValueError(
            f"report schema validation failed: {location}: {first.message}"
        )


def _write_report(
    path: Path, report: dict[str, Any], protected_inputs: list[Path]
) -> None:
    _validate_report_output(path, protected_inputs)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as report_file:
        json.dump(report, report_file, ensure_ascii=False, indent=2)
        report_file.write("\n")


def _collect_protected_inputs(raw_inputs: list[str]) -> list[Path]:
    protected_inputs: list[Path] = []
    for raw in raw_inputs:
        raw_path = Path(raw)
        if raw_path.exists():
            protected_inputs.append(raw_path)
            continue
        wildcard_positions = [raw.find(char) for char in _GLOB_CHARS if char in raw]
        if not wildcard_positions:
            continue
        static_prefix = raw[: min(wildcard_positions)]
        prefix_path = Path(static_prefix)
        glob_root = (
            prefix_path if static_prefix.endswith(("/", "\\")) else prefix_path.parent
        )
        if glob_root.exists():
            protected_inputs.append(glob_root)
    return protected_inputs


def _invalid_result_errors(result: Any) -> list[str]:
    errors: list[str] = []
    if result.load_error is not None:
        errors.append(f"load failed: {result.load_error}")
    errors.extend(f"schema: {message}" for message in result.schema_errors)
    errors.extend(issue.format() for issue in result.semantic_errors)
    return errors


def _build_report(
    raw_inputs: list[str], recursive: bool
) -> tuple[dict[str, Any], list[Path]]:
    engine = MergeEngine()
    entries = resolve_input_entries(raw_inputs, recursive=recursive)
    valid_documents: list[tuple[str, dict[str, Any]]] = []
    input_results: list[dict[str, Any]] = []
    skipped_inputs: list[str] = []
    protected_inputs = _collect_protected_inputs(raw_inputs)
    resolved_count = 0
    valid_count = 0
    invalid_count = 0

    for entry in entries:
        if entry.path is None:
            skipped_inputs.append(entry.raw)
            input_results.append(
                {
                    "path": entry.raw,
                    "status": "skipped",
                    "errors": [],
                    "warnings": ["入力を解決できませんでした"],
                }
            )
            continue

        protected_inputs.append(entry.path)
        resolved_count += 1
        result = engine.validate_file(entry.path)
        if result.is_valid:
            valid_count += 1
            assert result.document is not None
            valid_documents.append((result.source, result.document))
            input_results.append(
                {
                    "path": result.source,
                    "status": "valid",
                    "errors": [],
                    "warnings": [issue.format() for issue in result.semantic_warnings],
                }
            )
            continue

        invalid_count += 1
        input_results.append(
            {
                "path": result.source,
                "status": "invalid",
                "errors": _invalid_result_errors(result),
                "warnings": [issue.format() for issue in result.semantic_warnings],
            }
        )

    analysis = analyze_timeline_consistency(valid_documents)
    if invalid_count or skipped_inputs:
        status = "invalid_input"
    elif (
        analysis["findingCount"]
        or analysis["numericFindingCount"]
        or analysis["canonicalConstraintFindingCount"]
    ):
        status = "needs_review"
    else:
        status = "passed"

    report = {
        "schemaVersion": "0.4",
        "documentType": "timeline_consistency_report",
        "status": status,
        "inputFiles": len(raw_inputs),
        "resolvedInputFiles": resolved_count,
        "validInputs": valid_count,
        "invalidInputs": invalid_count,
        "skippedInputs": skipped_inputs,
        "inputResults": input_results,
        **analysis,
    }
    _validate_report(report)
    return report, protected_inputs


def main() -> int:
    args = parse_args()
    try:
        report, protected_inputs = _build_report(args.input, args.recursive)
        if report["resolvedInputFiles"] == 0:
            return 2
        if args.report_output:
            _write_report(Path(args.report_output), report, protected_inputs)
    except (OSError, ValueError) as exc:
        print(f"[エラー] Timeline整合性checkに失敗しました: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(
            "[Timeline consistency] "
            f"status={report['status']} "
            f"resolved={report['resolvedInputFiles']} "
            f"valid={report['validInputs']} "
            f"invalid={report['invalidInputs']} "
            f"checked={report['checkedCandidateCount']} "
            f"same_time={report['checkedSameTimeCandidateCount']} "
            f"ignored={report['ignoredCandidateCount']} "
            f"findings={report['findingCount']} "
            f"numeric_checked={report['numericEpisodeObservationCount']} "
            f"numeric_ignored={report['numericIgnoredObservationCount']} "
            f"numeric_findings={report['numericFindingCount']} "
            f"canonical_checked={report['canonicalConstraintCheckedCount']} "
            f"canonical_ignored={report['canonicalConstraintIgnoredCount']} "
            f"canonical_findings={report['canonicalConstraintFindingCount']}"
        )
        if args.report_output:
            print(f"[Timeline consistency] report={args.report_output}")

    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
