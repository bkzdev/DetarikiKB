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

`--story-summaries`（任意）で`knowledge/summaries/stories/`相当のfileまたは
directoryを指定すると、Story pageの`## Story Summary`/`## Episode Summaries`
placeholderを、`review.status`が`reviewed`/`approved`・`generationStatus`が
`generated`のSummary本文で置き換える（未指定・非表示条件のSummaryは従来通り
「未生成」のまま、`docs/architecture/06_AI/Story_Summary_Design.md` §6.3）。
Episode pageへのSummary表示はこのCLIでは行わない
(feature/story-summary-renderer-integration)。

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

    # story summaryを読み込んでStory pageのSummaryを表示する場合
    uv run python scripts/render_wiki.py \\
        --input tests/fixtures/wiki/synthetic_merged_collection.json \\
        --output workspace/wiki_preview \\
        --story-summaries tests/fixtures/story_summaries \\
        --validate

Exit codes:
    0: 生成成功
    1: 入力ファイルが見つからない、またはJSONとして読み込めない
       (--character-profiles/--story-summaries指定時、そのパスが
       見つからない場合も含む)
    2: --validate指定時にschema検証、またはcharacter_profiles/
       story_summariesの整合性検証に失敗した
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
from agents.wiki_generator.story_summaries import (  # noqa: E402
    StorySummaryCollection,
    StorySummaryLookup,
    build_story_summary_lookup,
    is_document_displayable,
    load_story_summaries,
    load_story_summary,
    parse_story_summary_document,
    validate_story_summary_collection,
)

DEFAULT_SCHEMA_PATH = (
    _PROJECT_ROOT / "schemas" / "merged_knowledge_collection.schema.json"
)
DEFAULT_CHARACTER_PROFILES_SCHEMA_PATH = (
    _PROJECT_ROOT / "schemas" / "character_profiles.schema.json"
)
DEFAULT_STORY_SUMMARY_SCHEMA_PATH = (
    _PROJECT_ROOT / "schemas" / "story_summary.schema.json"
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


def _load_story_summary_collection_lenient(
    input_path: Path,
) -> StorySummaryCollection:
    """schema検証を行わずにstory summaryを読み込む
    (`--validate`未指定時、`--character-profiles`の既存挙動と同じ
    「検証はしないが読み込みはする」方針)。"""
    if input_path.is_dir():
        return load_story_summaries(input_path)
    document = load_story_summary(input_path)
    return StorySummaryCollection(documents=[document] if document else [])


def _collect_story_summary_yaml_paths(input_path: Path) -> list[Path]:
    """--story-summariesがfileならそれ単体、directoryなら直下の
    *.yaml/*.ymlを返す (scripts/validate_story_summaries.pyと同じ方針)。"""
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.glob("*.yaml")) + sorted(input_path.glob("*.yml"))


def _validate_story_summary_input(
    input_path: Path,
) -> tuple[StorySummaryCollection | None, list[str]]:
    """`--story-summaries`かつ`--validate`指定時のschema検証+整合性検証
    (`scripts/validate_story_summaries.py`と同じロジック)。

    戻り値: (成功時のcollection (エラー時はNone)、エラーメッセージ一覧)。
    """
    with open(DEFAULT_STORY_SUMMARY_SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)

    documents = []
    errors: list[str] = []
    for path in _collect_story_summary_yaml_paths(input_path):
        with open(path, encoding="utf-8") as f:
            raw_data = yaml.safe_load(f) or {}
        if not raw_data:
            continue
        schema_errors = sorted(
            Draft7Validator(schema).iter_errors(raw_data), key=lambda e: list(e.path)
        )
        if schema_errors:
            errors.extend(f"{path}: {list(e.path)}: {e.message}" for e in schema_errors)
            continue
        documents.append(parse_story_summary_document(raw_data))

    if errors:
        return None, errors

    collection = StorySummaryCollection(documents=documents)
    integrity_issues = validate_story_summary_collection(collection)
    if integrity_issues:
        return None, integrity_issues
    return collection, []


def resolve_story_summaries(
    args: argparse.Namespace,
) -> tuple[StorySummaryLookup | None, int | None]:
    """`--story-summaries`引数を解決する (`resolve_character_profiles`と
    同じパターン)。

    戻り値は (lookup (未指定ならNone), エラー時のexit code (問題無ければNone))。
    """
    if not args.story_summaries:
        return None, None

    input_path = Path(args.story_summaries)
    if not input_path.exists():
        print(
            f"[エラー] story-summariesパスが見つかりません: {input_path}",
            file=sys.stderr,
        )
        return None, 1

    if args.validate:
        collection, errors = _validate_story_summary_input(input_path)
        if collection is None:
            print("[エラー] story summariesの検証に失敗しました:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return None, 2
    else:
        collection = _load_story_summary_collection_lenient(input_path)

    lookup = build_story_summary_lookup(collection)
    if not args.quiet:
        displayable = sum(
            1 for doc in collection.documents if is_document_displayable(doc)
        )
        print(
            f"[wiki] story_summaries: {input_path} "
            f"({len(collection.documents)} 件、表示可能 {displayable} 件)"
        )
    return lookup, None


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
        "--story-summaries",
        default=None,
        help=(
            "knowledge/summaries/stories/相当のfileまたはdirectoryのパス (任意)。"
            "指定した場合のみStory pageのStory/Episode Summaryを、"
            "review.statusがreviewed/approved・generationStatusがgeneratedの"
            "Summary本文で表示する。未指定でも既存の生成結果は変わらない"
        ),
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


def resolve_collection(
    args: argparse.Namespace,
) -> tuple[dict | None, int | None]:
    """`--input`/`--validate`を解決し、merged knowledge collectionを返す
    (mainの複雑度を下げるためのヘルパー)。

    戻り値は (collection (エラー時はNone), エラー時のexit code (問題無ければNone))。
    """
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[エラー] 入力ファイルが見つかりません: {input_path}", file=sys.stderr)
        return None, 1

    collection = load_collection(input_path)
    if collection is None:
        print(f"[エラー] JSONとして読み込めませんでした: {input_path}", file=sys.stderr)
        return None, 1

    if args.validate:
        errors = validate_collection(collection, DEFAULT_SCHEMA_PATH)
        if errors:
            print(
                "[エラー] merged knowledge collectionのschema検証に失敗しました:",
                file=sys.stderr,
            )
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return None, 2
        if not args.quiet:
            print("[wiki] schema検証: OK")

    return collection, None


def main() -> int:
    args = parse_args()

    collection, error_code = resolve_collection(args)
    if error_code is not None:
        return error_code

    character_profiles_index, error_code = resolve_character_profiles(args)
    if error_code is not None:
        return error_code

    story_summary_lookup, error_code = resolve_story_summaries(args)
    if error_code is not None:
        return error_code

    pages = build_pages(
        collection,
        character_profiles=character_profiles_index,
        story_summary_lookup=story_summary_lookup,
    )
    output_dir = Path(args.output)
    written = write_pages(pages, output_dir, clean=args.clean)

    if not args.quiet:
        print(f"[wiki] {len(written)} 件のMarkdownを生成しました: {output_dir}")
        for path in sorted(written):
            print(f"  - {path.relative_to(output_dir)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
