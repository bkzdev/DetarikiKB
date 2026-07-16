#!/usr/bin/env python3
"""
Extract Story Script
CLIから Normalized Story JSON を episode_extraction (Stage A) へ変換する入口。

Character/Location/Organization/Item/Lore/Event/Relationship/Timeline の
8種のCandidateを、構造的な手がかりのみからrule-baseで抽出する
(本文の自然文推定は行わない)。LLM呼び出し・OpenAI/Anthropic/Ollama連携・
prompt作成はまだ実装していない。

Usage:
    python scripts/extract_story.py \\
        --input data/normalized/main/MAIN_S01_C02_E01.json \\
        --output data/extracted/_raw/ \\
        --validate

    # 複数documentをまとめて処理する (CHAR_HS本体+例外変種のグループ間
    # 重複ブロックを抽出段階でdedupする、Character_Story_ID_Manifest_
    # Design.md §6.3・§9 PR E)。--input-dir配下の*.jsonを全て入力として
    # 読み込み、hsceneVariantTraceを持つdocumentをbaseEpisodeId単位で
    # グループ化した上で抽出する。トレースの無いdocumentは従来通り
    # 個別に処理される (完全無回帰)。
    python scripts/extract_story.py \\
        --input-dir data/normalized/character/ \\
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

from agents.extractor import Extractor, extract_stories_with_hscene_dedup  # noqa: E402

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
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input",
        "-i",
        help="Normalized Story JSON ファイルのパス (1ファイル)",
    )
    input_group.add_argument(
        "--input-dir",
        help=(
            "Normalized Story JSON ファイルを含むディレクトリ (直下の*.jsonを"
            "全て読み込む)。CHAR_HS本体+例外変種のグループ間重複ブロックを"
            "抽出段階でdedupする場合はこちらを使う"
        ),
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


def _load_story_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), None
    except (OSError, json.JSONDecodeError) as e:
        return None, f"[エラー] JSON読み込み失敗: {path}: {e}"


def _extract_from_dir(
    input_dir_arg: str, quiet: bool
) -> tuple[list[dict] | None, int | None]:
    """--input-dir経路: ディレクトリ直下の*.jsonを全て読み込み、
    hsceneVariantTraceを持つdocumentのグループ間重複ブロックを抽出段階で
    dedupしながらepisode_extractionのリストを返す。
    """
    input_dir = Path(input_dir_arg)
    if not input_dir.is_dir():
        print(
            f"[エラー] 入力ディレクトリが見つかりません: {input_dir}", file=sys.stderr
        )
        return None, 1

    input_paths = sorted(input_dir.glob("*.json"))
    if not input_paths:
        print(
            f"[エラー] {input_dir} に *.json ファイルが見つかりません", file=sys.stderr
        )
        return None, 1

    if not quiet:
        print(f"[DKB] 入力ディレクトリ: {input_dir} ({len(input_paths)} ファイル)")

    story_jsons = []
    for input_path in input_paths:
        story_json, error = _load_story_json(input_path)
        if error is not None:
            print(error, file=sys.stderr)
            return None, 2
        story_jsons.append(story_json)

    return extract_stories_with_hscene_dedup(story_jsons), None


def _extract_from_file(
    input_path_arg: str, quiet: bool
) -> tuple[list[dict] | None, int | None]:
    """--input経路 (単一ファイル、従来通り): dedup非対応の素のExtractorを使う。"""
    input_path = Path(input_path_arg)
    if not input_path.exists():
        print(f"[エラー] 入力ファイルが見つかりません: {input_path}", file=sys.stderr)
        return None, 1

    if not quiet:
        print(f"[DKB] 入力ファイル: {input_path}")

    story_json, error = _load_story_json(input_path)
    if error is not None:
        print(error, file=sys.stderr)
        return None, 2

    return Extractor().extract_story(story_json), None


def main() -> int:
    args = parse_args()

    if not args.quiet:
        print("[DKB] extract_story")

    if args.input_dir:
        extractions, error_code = _extract_from_dir(args.input_dir, args.quiet)
    else:
        extractions, error_code = _extract_from_file(args.input, args.quiet)

    if error_code is not None:
        return error_code

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
