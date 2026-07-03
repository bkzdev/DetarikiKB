#!/usr/bin/env python3
"""
Normalize Story Script
CLI から Raw Script を Normalized Story JSON へ変換する入口。

Phase 9 (Parser_Implementation_Plan.md)

Usage:
    python scripts/normalize_story.py \\
        --input data/raw/main/CAB-csl_script_mainstory_chapter68-main1.dec \\
        --story-id MAIN_S03_C68 \\
        --episode-id MAIN_S03_C68_E01 \\
        --category MAIN \\
        --output data/normalized/main/

    # JSON Schema 検証付き
    python scripts/normalize_story.py \\
        --input data/raw/event/example.dec \\
        --story-id EVT_0162 \\
        --episode-id EVT_0162_E01 \\
        --category EVT \\
        --output data/normalized/event/ \\
        --validate

    # 互換性チェック付き
    python scripts/normalize_story.py \\
        --input data/raw/main/example.dec \\
        --story-id MAIN_S01_C02 \\
        --episode-id MAIN_S01_C02_E01 \\
        --category MAIN \\
        --output data/normalized/main/ \\
        --check-compat
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# プロジェクトルートを sys.path に追加
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.parser import (  # noqa: E402
    CharacterDictionary,
    Exporter,
    Normalizer,
    StoryParser,
)

DEFAULT_CHARACTERS_PATH = (
    _PROJECT_ROOT / "knowledge" / "dictionaries" / "characters.yaml"
)
# レガシー辞書 (読み取り専用、CLAUDE.md記載の通り直接改造しない)。
# --check-compat のcheck_script_compatibility.py呼び出しは、この辞書 (フラット
# な{sourceCharacterId: name}のJSON) しか理解できないため、--characters に
# YAMLパスが指定されている場合の互換性チェックはこちらへフォールバックする。
LEGACY_CHARACTERS_PATH = (
    _PROJECT_ROOT / "reference" / "parser" / "characters_reference.json"
)
DEFAULT_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "story.schema.json"
DEFAULT_COMMANDS_CONFIG = _PROJECT_ROOT / "config" / "script_commands.yaml"


# ----------------------------------------------------------------
# Argument Parser
# ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DKB Raw Script を Normalized Story JSON へ変換します",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python scripts/normalize_story.py \\
      --input data/raw/main/example.dec \\
      --story-id MAIN_S03_C68 \\
      --episode-id MAIN_S03_C68_E01 \\
      --category MAIN \\
      --output data/normalized/main/

  python scripts/normalize_story.py \\
      --input data/raw/event/example.dec \\
      --story-id EVT_0162 \\
      --episode-id EVT_0162_E01 \\
      --category EVT \\
      --validate
""",
    )

    # 必須引数
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="変換する Raw Script ファイルのパス (.dec / .txt)",
    )
    parser.add_argument(
        "--story-id",
        required=True,
        help="Story ID (例: MAIN_S03_C68, EVT_0162)",
    )
    parser.add_argument(
        "--category",
        required=True,
        choices=[
            "MAIN",
            "EVT",
            "RAID",
            "OTHER",
            "CHAR_MAIN",
            "CHAR_EXTRA",
            "CHAR_DATE",
        ],
        help="ストーリーカテゴリ",
    )

    # オプション引数
    parser.add_argument(
        "--episode-id",
        default=None,
        help="Episode ID (省略時は --story-id + _E01 を自動設定)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(_PROJECT_ROOT / "data" / "normalized"),
        help="出力先ディレクトリ (デフォルト: data/normalized/)",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="出力ファイル名 (省略時は episode_id.json を自動設定)",
    )
    parser.add_argument(
        "--characters",
        default=str(DEFAULT_CHARACTERS_PATH),
        help=(
            "キャラクター辞書 (.yaml: knowledge/dictionaries/characters.yaml "
            "形式 / .json: characters_reference.json形式、拡張子で自動判別。"
            f"デフォルト: {DEFAULT_CHARACTERS_PATH})"
        ),
    )
    parser.add_argument(
        "--validate",
        "-v",
        action="store_true",
        help="出力 JSON を story.schema.json で検証する",
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help=f"JSON Schema ファイルパス (デフォルト: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--check-compat",
        action="store_true",
        help="互換性チェックも実行する",
    )
    parser.add_argument(
        "--commands",
        default=str(DEFAULT_COMMANDS_CONFIG),
        help=f"コマンド辞書 YAML (デフォルト: {DEFAULT_COMMANDS_CONFIG})",
    )
    parser.add_argument(
        "--story-title",
        default=None,
        help="ストーリータイトル (メタデータ)",
    )
    parser.add_argument(
        "--episode-title",
        default=None,
        help="エピソードタイトル (メタデータ)",
    )
    parser.add_argument(
        "--no-stage-directions",
        action="store_true",
        help="演出命令を出力しない",
    )
    parser.add_argument(
        "--category-subdir",
        action="store_true",
        help="--category に応じたサブディレクトリへ出力する (main/ event/ など)",
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


def _print_startup_info(
    args: argparse.Namespace, input_path: Path, episode_id: str, preserve_stage: bool
) -> None:
    if args.quiet:
        return
    print("[DKB] normalize_story")
    print(f"[DKB] 入力ファイル: {input_path}")
    print(f"[DKB] story_id:     {args.story_id}")
    print(f"[DKB] episode_id:   {episode_id}")
    print(f"[DKB] category:     {args.category}")
    print(f"[DKB] 演出命令保持: {preserve_stage}")


def _load_character_dict(args: argparse.Namespace) -> CharacterDictionary:
    """キャラクター辞書を読み込む (見つからない場合は空の辞書のまま警告を表示)"""
    char_dict = CharacterDictionary()
    char_path = Path(args.characters)
    if char_path.exists():
        char_dict.load(char_path)
        if not args.quiet:
            print(f"[DKB] キャラクター辞書: {char_dict.size()} 件")
    else:
        print(f"[警告] キャラクター辞書が見つかりません: {char_path}", file=sys.stderr)
    return char_dict


def _run_compatibility_check(args: argparse.Namespace, input_path: Path) -> int | None:
    """--check-compat 指定時に互換性チェックを実行する。
    blocked の場合は中断すべき終了コード(2)を返し、それ以外はNoneを返す。
    """
    if not args.check_compat:
        return None

    if not args.quiet:
        print("[DKB] 互換性チェック実行中...")
    try:
        import subprocess

        # check_script_compatibility.pyは{sourceCharacterId: name}の
        # フラットなJSON形式しか理解できないため、--charactersにYAML
        # (knowledge/dictionaries/characters.yaml形式) が指定されている
        # 場合はレガシーJSON辞書にフォールバックする。
        compat_characters_path = args.characters
        if Path(args.characters).suffix.lower() in (".yaml", ".yml"):
            compat_characters_path = str(LEGACY_CHARACTERS_PATH)

        result = subprocess.run(
            [
                sys.executable,
                str(_PROJECT_ROOT / "scripts" / "check_script_compatibility.py"),
                str(input_path),
                "--commands",
                args.commands,
                "--characters",
                compat_characters_path,
                "--quiet",
            ],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout)
        if result.returncode == 2:
            print(
                "[エラー] 互換性チェック結果: blocked - 処理を中断します",
                file=sys.stderr,
            )
            return 2
    except Exception as e:
        print(f"[警告] 互換性チェックの実行に失敗しました: {e}", file=sys.stderr)

    return None


def _parse_story_file(
    args: argparse.Namespace,
    char_dict: CharacterDictionary,
    preserve_stage: bool,
    input_path: Path,
) -> tuple[Any, int]:
    """Raw Script を解析する。失敗時は (None, 1) を返す。"""
    if not args.quiet:
        print("[DKB] 解析中...")

    story_parser = StoryParser(
        char_dict=char_dict,
        preserve_stage_directions=preserve_stage,
        preserve_unknown=True,
        source_file=input_path.stem,
    )

    try:
        return story_parser.parse_file(input_path), 0
    except Exception as e:
        print(f"[エラー] 解析中にエラーが発生しました: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return None, 1


def _normalize_story(
    args: argparse.Namespace,
    parse_result: Any,
    episode_id: str,
    input_path: Path,
) -> tuple[dict, int]:
    """解析結果をNormalized Story JSONへ変換する。失敗時は ({}, 1) を返す。"""
    if not args.quiet:
        print("[DKB] 正規化中...")

    story_metadata: dict = {}
    if args.story_title:
        story_metadata["storyTitle"] = args.story_title

    episode_metadata: dict = {}
    if args.episode_title:
        episode_metadata["episodeTitle"] = args.episode_title

    normalizer = Normalizer(
        story_id=args.story_id,
        story_category=args.category,
        episode_id=episode_id,
        story_metadata=story_metadata,
        episode_metadata=episode_metadata,
        source_file=input_path.stem,
        source_path=str(input_path),
        preserve_stage_directions=not args.no_stage_directions,
        commands_config_path=args.commands,
    )

    try:
        with open(input_path, encoding="utf-8", errors="ignore") as f:
            line_count = sum(1 for _ in f)

        return normalizer.normalize(parse_result, line_count=line_count), 0
    except Exception as e:
        print(f"[エラー] 正規化中にエラーが発生しました: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return {}, 1


def _export_story(
    args: argparse.Namespace, story_json: dict, episode_id: str
) -> tuple[Path | None, int]:
    """Normalized Story JSONをファイルへ出力する。失敗時は (None, 1) を返す。"""
    output_dir = Path(args.output)
    exporter = Exporter(output_dir=output_dir, overwrite=True)
    output_filename = args.output_file or f"{episode_id}.json"

    try:
        if args.category_subdir:
            output_path = exporter.export_with_category(story_json, output_filename)
        else:
            output_path = exporter.export(story_json, output_filename)
    except Exception as e:
        print(f"[エラー] 出力中にエラーが発生しました: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return None, 1

    if not args.quiet:
        print(f"[DKB] 出力完了: {output_path}")
    return output_path, 0


def _print_completion_summary(
    args: argparse.Namespace, story_json: dict, output_path: Path
) -> None:
    if args.quiet:
        return

    compat = story_json.get("compatibilityReport", {})
    status = compat.get("parserCompatibility", "unknown")
    status_label = {
        "compatible": "compatible",
        "warning": "warning",
        "needs_update": "needs_update",
        "blocked": "blocked",
    }.get(status, status)

    total_blocks = 0
    for ep in story_json.get("episodes", []):
        for sc in ep.get("scenes", []):
            total_blocks += len(sc.get("blocks", []))

    print("")
    print("[DKB] 完了:")
    print(f"  互換性:       {status_label}")
    print(f"  エピソード数: {len(story_json.get('episodes', []))}")
    print(f"  総ブロック数: {total_blocks}")
    print(f"  制御文字除去: {compat.get('controlCharsRemoved', 0)} 件")
    print(f"  未知コマンド: {len(compat.get('unknownCommands', []))} 種類")
    print(f"  未登録Char:   {len(compat.get('unknownCharacterIds', []))} ID")
    print(f"  出力先:       {output_path}")


def main() -> int:
    """CLIエントリポイント。各フェーズは _load_character_dict / _run_compatibility_check
    / _parse_story_file / _normalize_story / _export_story などのヘルパーへ切り出し、
    ここでは各フェーズを順に呼び出し、失敗時の終了コードを判定するだけの
    薄いオーケストレーションのみを担う
    (挙動は分割前と同一、ruffのC901複雑度対策でのリファクタリング)。
    """
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[エラー] 入力ファイルが見つかりません: {input_path}", file=sys.stderr)
        return 1

    episode_id = args.episode_id or f"{args.story_id}_E01"
    preserve_stage = not args.no_stage_directions

    _print_startup_info(args, input_path, episode_id, preserve_stage)

    char_dict = _load_character_dict(args)

    compat_exit_code = _run_compatibility_check(args, input_path)
    if compat_exit_code is not None:
        return compat_exit_code

    parse_result, exit_code = _parse_story_file(
        args, char_dict, preserve_stage, input_path
    )
    if exit_code != 0:
        return exit_code

    story_json, exit_code = _normalize_story(args, parse_result, episode_id, input_path)
    if exit_code != 0:
        return exit_code

    output_path, exit_code = _export_story(args, story_json, episode_id)
    if exit_code != 0:
        return exit_code

    if args.validate:
        if not args.quiet:
            print("[DKB] JSON Schema 検証中...")
        exit_code = validate_schema(story_json, Path(args.schema), args.quiet)
        if exit_code != 0:
            return exit_code

    _print_completion_summary(args, story_json, output_path)

    return 0


def validate_schema(story_json: dict, schema_path: Path, quiet: bool = False) -> int:
    """JSON Schema で story_json を検証する"""
    try:
        import jsonschema
    except ImportError:
        print(
            "[警告] jsonschema がインストールされていません。スキップします。",
            file=sys.stderr,
        )
        print("       pip install jsonschema でインストールできます。", file=sys.stderr)
        return 0

    if not schema_path.exists():
        print(
            f"[警告] スキーマファイルが見つかりません: {schema_path}", file=sys.stderr
        )
        return 0

    try:
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)

        validator = jsonschema.Draft7Validator(schema)
        errors = list(validator.iter_errors(story_json))

        if errors:
            print(
                f"[エラー] JSON Schema 検証失敗: {len(errors)} 件のエラー",
                file=sys.stderr,
            )
            for err in errors[:5]:  # 最大5件表示
                print(f"  - {err.json_path}: {err.message}", file=sys.stderr)
            return 1
        else:
            if not quiet:
                print("[DKB] JSON Schema 検証: 成功")
            return 0

    except Exception as e:
        print(
            f"[エラー] JSON Schema 検証中にエラーが発生しました: {e}", file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
