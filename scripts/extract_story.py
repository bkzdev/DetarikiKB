#!/usr/bin/env python3
"""
Extract Story Script
CLIから Normalized Story JSON を episode_extraction (Stage A) へ変換する入口。

LLM呼び出し・OpenAI/Anthropic/Ollama連携・prompt作成はまだ実装していない。
候補配列 (characters/organizations/... 等) は空のまま出力する。

Usage:
    python scripts/extract_story.py \\
        --input data/normalized/main/MAIN_S01_C02_E01.json \\
        --output data/extracted/_raw/ \\
        --validate
"""

import argparse
import json
import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.extractor import Extractor

DEFAULT_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "extraction.schema.json"


# ----------------------------------------------------------------
# Argument Parser
# ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalized Story JSON を episode_extraction (Stage A) へ変換",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python scripts/extract_story.py \\
      --input data/normalized/main/MAIN_S01_C02_E01.json \\
      --output data/extracted/_raw/ \\
      --validate
""",
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Normalized Story JSON ファイルのパス",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(_PROJECT_ROOT / "data" / "extracted" / "_raw"),
        help="出力先ディレクトリ (デフォルト: data/extracted/_raw/)",
    )
    parser.add_argument(
        "--validate",
        "-v",
        action="store_true",
        help="出力 JSON を extraction.schema.json で検証する",
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
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------


def validate_schema(instance: dict, schema_path: Path, quiet: bool = False) -> int:
    """JSON Schema で instance を検証する"""
    try:
        import jsonschema
    except ImportError:
        print(
            "[警告] jsonschema がインストールされていません。スキップします。",
            file=sys.stderr,
        )
        return 0

    if not schema_path.exists():
        print(
            f"[警告] スキーマファイルが見つかりません: {schema_path}", file=sys.stderr
        )
        return 0

    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    validator = jsonschema.Draft7Validator(schema)
    errors = list(validator.iter_errors(instance))

    if errors:
        print(
            f"[エラー] JSON Schema 検証失敗: {len(errors)} 件のエラー", file=sys.stderr
        )
        for err in errors[:5]:
            print(f"  - {err.json_path}: {err.message}", file=sys.stderr)
        return 1

    if not quiet:
        print("[DKB] JSON Schema 検証: OK")
    return 0


def main() -> int:
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[エラー] 入力ファイルが見つかりません: {input_path}", file=sys.stderr)
        return 1

    if not args.quiet:
        print("[DKB] extract_story")
        print(f"[DKB] 入力ファイル: {input_path}")

    try:
        with open(input_path, encoding="utf-8") as f:
            story_json = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[エラー] JSON読み込み失敗: {input_path}: {e}", file=sys.stderr)
        return 2

    extractor = Extractor()
    extractions = extractor.extract_story(story_json)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    for extraction in extractions:
        episode_id = extraction["episodeId"]
        output_path = output_dir / f"{episode_id}.extraction.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(extraction, f, ensure_ascii=False, indent=2)

        if not args.quiet:
            print(f"[DKB] 出力完了: {output_path}")

        if args.validate:
            exit_code = validate_schema(extraction, Path(args.schema), args.quiet)
            if exit_code != 0:
                return exit_code

    if not args.quiet:
        print(f"[DKB] 完了: {len(extractions)} エピソード")

    return 0


if __name__ == "__main__":
    sys.exit(main())
