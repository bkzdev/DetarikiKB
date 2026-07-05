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

`--character-profiles`（任意）で`knowledge/dictionaries/character_profiles.yaml`
相当のパスを指定すると、Character pageに「基本プロフィール」section
（`docs/architecture/07_Wiki/Wiki_Output_Design.md` §9.4）を表示する。
未指定でも既存の出力は変わらない（sectionは「プロフィール未登録」表示になる）。
このCLIはWIKIの再取得・自己紹介文の自動取得は一切行わない
(character_profiles.yamlを読み取るのみ)。

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

    # character_profiles.yamlを読み込んで基本プロフィールsectionを表示する場合
    uv run python scripts/render_wiki.py \\
        --input tests/fixtures/wiki/synthetic_merged_collection.json \\
        --output workspace/wiki_preview \\
        --character-profiles knowledge/dictionaries/character_profiles.yaml \\
        --validate

Exit codes:
    0: 生成成功
    1: 入力ファイルが見つからない、またはJSONとして読み込めない
       (--character-profiles指定時、そのファイルが見つからない場合も含む)
    2: --validate指定時にschema検証、またはcharacter_profilesの整合性検証に失敗した
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.parser.character_profiles import (  # noqa: E402
    CharacterProfile,
    build_character_profile_index,
    load_character_profiles,
    validate_character_profiles,
)
from agents.wiki_generator import build_pages, write_pages  # noqa: E402

DEFAULT_SCHEMA_PATH = (
    _PROJECT_ROOT / "schemas" / "merged_knowledge_collection.schema.json"
)
DEFAULT_CHARACTER_PROFILES_SCHEMA_PATH = (
    _PROJECT_ROOT / "schemas" / "character_profiles.schema.json"
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


def validate_character_profiles_schema(
    profiles_path: Path, schema_path: Path
) -> list[str]:
    """character_profiles.yaml相当のファイルをschema検証する
    (scripts/validate_character_profiles.pyと同じ検証ロジックを再利用)。

    戻り値: エラーメッセージのリスト (空なら検証OK)。
    """
    with open(profiles_path, encoding="utf-8") as f:
        raw_data = yaml.safe_load(f) or {}
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(raw_data), key=lambda e: list(e.path))
    return [f"{list(e.path)}: {e.message}" for e in errors]


def load_character_profile_index(
    profiles_path: Path, schema_path: Path, do_validate: bool
) -> tuple[dict[str, CharacterProfile] | None, list[str]]:
    """--character-profilesで指定されたファイルを読み込み、
    characterId -> CharacterProfile の索引を組み立てる。

    `do_validate`がTrueの場合のみ、schema検証と
    (characters.yamlとの突き合わせを伴わない) 基本的な整合性検証
    (重複characterId・形式・birthday範囲等) を行う。戻り値は
    (索引 (エラー時はNone), エラーメッセージのリスト)。
    """
    if do_validate:
        schema_errors = validate_character_profiles_schema(profiles_path, schema_path)
        if schema_errors:
            return None, schema_errors

    profiles = load_character_profiles(profiles_path)

    if do_validate:
        semantic_issues = validate_character_profiles(profiles)
        if semantic_issues:
            return None, semantic_issues

    return build_character_profile_index(profiles), []


def resolve_character_profiles(
    args: argparse.Namespace,
) -> tuple[dict[str, CharacterProfile] | None, int | None]:
    """`--character-profiles`引数を解決する (mainの複雑度を下げるための
    ヘルパー)。

    戻り値は (索引 (未指定ならNone), エラー時のexit code (問題無ければNone))。
    呼び出し側は2つ目の値がNoneでなければ、その値をそのままreturnすること。
    """
    if not args.character_profiles:
        return None, None

    profiles_path = Path(args.character_profiles)
    if not profiles_path.exists():
        print(
            f"[エラー] character-profilesファイルが見つかりません: {profiles_path}",
            file=sys.stderr,
        )
        return None, 1

    character_profiles_index, profile_errors = load_character_profile_index(
        profiles_path, DEFAULT_CHARACTER_PROFILES_SCHEMA_PATH, args.validate
    )
    if character_profiles_index is None:
        print("[エラー] character_profilesの検証に失敗しました:", file=sys.stderr)
        for error in profile_errors:
            print(f"  - {error}", file=sys.stderr)
        return None, 2

    if not args.quiet:
        print(
            f"[wiki] character_profiles: {profiles_path} "
            f"({len(character_profiles_index)} 件)"
        )
    return character_profiles_index, None


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
            "検証してから生成する (--character-profiles指定時はそちらも検証する)"
        ),
    )
    parser.add_argument(
        "--character-profiles",
        default=None,
        help=(
            "knowledge/dictionaries/character_profiles.yaml相当のパス (任意)。"
            "指定した場合のみCharacter pageに基本プロフィールsectionを表示する。"
            "未指定でも既存の生成結果は変わらない"
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

    character_profiles_index, error_code = resolve_character_profiles(args)
    if error_code is not None:
        return error_code

    pages = build_pages(collection, character_profiles=character_profiles_index)
    output_dir = Path(args.output)
    written = write_pages(pages, output_dir, clean=args.clean)

    if not args.quiet:
        print(f"[wiki] {len(written)} 件のMarkdownを生成しました: {output_dir}")
        for path in sorted(written):
            print(f"  - {path.relative_to(output_dir)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
