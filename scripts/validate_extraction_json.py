#!/usr/bin/env python3
"""
Validate Extraction JSON
Extraction Phase の episode_extraction JSON を schemas/extraction.schema.json で検証する。

Usage:
    # 単一ファイル
    python scripts/validate_extraction_json.py --input data/extracted/_raw/MAIN_S01_C02_E01.extraction.json

    # ディレクトリ (再帰的に *.json を検証)
    python scripts/validate_extraction_json.py --input data/extracted/_raw/

    # テスト用フィクスチャの検証
    python scripts/validate_extraction_json.py --input tests/fixtures/extraction/minimal_episode_extraction.json

Exit codes:
    0: すべて検証成功
    1: 1件以上のスキーマ検証エラー
    2: ファイル/JSON読み込みエラー、またはスキーマ読み込みエラー
"""

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

DEFAULT_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "extraction.schema.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="episode_extraction JSON を schemas/extraction.schema.json で検証します",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python scripts/validate_extraction_json.py --input data/extracted/_raw/
  python scripts/validate_extraction_json.py --input tests/fixtures/extraction/minimal_episode_extraction.json
""",
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="検証対象のJSONファイル、または *.json を再帰的に検証するディレクトリ",
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help=f"JSON Schema ファイルパス (デフォルト: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="成功時のメッセージを抑制する (失敗時は常に出力する)",
    )
    return parser.parse_args()


def load_schema(schema_path: Path) -> dict:
    if not schema_path.exists():
        print(f"[エラー] スキーマファイルが見つかりません: {schema_path}", file=sys.stderr)
        raise SystemExit(2)
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def collect_target_files(input_path: Path) -> list[Path]:
    if input_path.is_dir():
        return sorted(input_path.rglob("*.json"))
    return [input_path]


def validate_file(path: Path, validator: Draft7Validator, quiet: bool) -> bool:
    """1ファイルを検証する。成功時True、失敗時Falseを返す"""
    try:
        with open(path, encoding="utf-8") as f:
            instance = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[エラー] JSON読み込み失敗: {path}: {e}", file=sys.stderr)
        return False

    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        print(f"[NG] {path}: {len(errors)} 件のエラー", file=sys.stderr)
        for err in errors[:10]:
            path_str = "/".join(str(p) for p in err.path) or "(root)"
            print(f"  - {path_str}: {err.message}", file=sys.stderr)
        return False

    if not quiet:
        print(f"[OK] {path}")
    return True


def main() -> int:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[エラー] 入力パスが見つかりません: {input_path}", file=sys.stderr)
        return 2

    schema = load_schema(Path(args.schema))
    validator = Draft7Validator(schema)

    targets = collect_target_files(input_path)
    if not targets:
        print(f"[警告] 検証対象のJSONファイルが見つかりません: {input_path}", file=sys.stderr)
        return 0

    all_valid = True
    for target in targets:
        if not validate_file(target, validator, args.quiet):
            all_valid = False

    if not args.quiet:
        status = "すべて成功" if all_valid else "失敗あり"
        print(f"[DKB] 検証結果: {status} ({len(targets)} ファイル)")

    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
