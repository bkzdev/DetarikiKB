#!/usr/bin/env python3
"""
Validate Story Summaries
`knowledge/summaries/stories/{storyId}.yaml`（Story Summary/Episode Summary）を
schema検証し、duplicate storyId/episodeId・raw text禁止文字列・evidenceRefs形式
等の整合性を確認する補助スクリプト。

**重要**: 要約本文の品質判断・AI推測は一切行わない。schema・重複・禁止文字列・
ID形式のみを機械的に検証する
(docs/architecture/06_AI/Story_Summary_Design.md 参照)。

Usage:
    # 単一ファイル
    uv run python scripts/validate_story_summaries.py \\
        --input knowledge/summaries/stories/EVT_SAMPLE.yaml

    # directory (直下の *.yaml/*.yml を収集)
    uv run python scripts/validate_story_summaries.py \\
        --input knowledge/summaries/stories

    # knowledge/summaries/配下を検証する場合、review.statusが
    # reviewed/approvedでないファイルをエラーにする
    uv run python scripts/validate_story_summaries.py \\
        --input knowledge/summaries/stories --require-reviewed

Exit codes:
    0: 検証成功
    1: schema検証、または整合性検証に失敗した
    2: 入力パスが見つからない、またはIOエラー
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

from agents.wiki_generator.story_summaries import (  # noqa: E402
    DISPLAYABLE_REVIEW_STATUSES,
    StorySummaryCollection,
    parse_story_summary_document,
    validate_story_summary_collection,
)

DEFAULT_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "story_summary.schema.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "story summary YAML (単一ファイルまたはdirectory) をschema検証し、"
            "duplicate storyId/episodeId・raw text禁止文字列・"
            "evidenceRefs形式を確認する"
        ),
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="story summary YAMLファイル、またはdirectoryのパス",
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help=f"JSON Schemaのパス (デフォルト: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--require-reviewed",
        action="store_true",
        help=(
            "review.statusがreviewed/approvedでないファイルをエラーにする"
            " (knowledge/summaries/stories/を検証する際に指定する想定。"
            "workspace/summary_drafts/等のdraft置き場を検証する場合は指定しない)"
        ),
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


def _collect_yaml_paths(input_path: Path) -> list[Path] | None:
    """--inputがファイルならそれ単体、directoryなら直下の*.yaml/*.ymlを返す。

    入力パスが存在しない場合はNoneを返す。
    """
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.glob("*.yaml")) + sorted(input_path.glob("*.yml"))
    return None


def _validate_schema_for_file(
    path: Path, schema: dict
) -> tuple[dict | None, list[str]]:
    """1ファイルをschema検証する。

    戻り値: (パース済みraw dict (schema検証失敗時はNone), エラーメッセージ一覧)
    """
    try:
        with open(path, encoding="utf-8") as f:
            raw_data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        return None, [f"{path}: 読み込み失敗: {e}"]

    errors = sorted(
        Draft7Validator(schema).iter_errors(raw_data), key=lambda e: list(e.path)
    )
    if errors:
        return None, [f"{path}: {list(e.path)}: {e.message}" for e in errors]
    return raw_data, []


def _check_require_reviewed(raw_documents: list[tuple[Path, dict]]) -> list[str]:
    """--require-reviewed指定時、review.statusがreviewed/approved以外の
    ファイルをエラーとして報告する (Story_Summary_Design.md §6.3)。"""
    issues: list[str] = []
    for path, raw in raw_documents:
        review_status = (raw.get("review") or {}).get("status")
        if review_status not in DISPLAYABLE_REVIEW_STATUSES:
            issues.append(
                f"{path}: review.statusが'{review_status}'です "
                f"(--require-reviewed指定時はreviewed/approvedのみ許可)"
            )
    return issues


def _validate_all_schemas(
    yaml_paths: list[Path], schema: dict
) -> tuple[list[tuple[Path, dict]], list[str]]:
    """全ファイルをschema検証する。戻り値: (成功したraw documents一覧, エラー一覧)。"""
    schema_errors: list[str] = []
    raw_documents: list[tuple[Path, dict]] = []
    for path in yaml_paths:
        raw_data, errors = _validate_schema_for_file(path, schema)
        if errors:
            schema_errors.extend(errors)
        else:
            raw_documents.append((path, raw_data))
    return raw_documents, schema_errors


def main() -> int:
    args = parse_args()

    input_path = Path(args.input)
    yaml_paths = _collect_yaml_paths(input_path)
    if yaml_paths is None:
        print(f"[エラー] 入力パスが見つかりません: {input_path}", file=sys.stderr)
        return 2

    schema_path = Path(args.schema)
    if not schema_path.exists():
        print(
            f"[エラー] schemaファイルが見つかりません: {schema_path}", file=sys.stderr
        )
        return 2
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    raw_documents, schema_errors = _validate_all_schemas(yaml_paths, schema)
    if schema_errors:
        print("[エラー] story summaryのschema検証に失敗しました:", file=sys.stderr)
        for message in schema_errors:
            print(f"  - {message}", file=sys.stderr)
        return 1

    collection = StorySummaryCollection(
        documents=[parse_story_summary_document(raw) for _, raw in raw_documents]
    )
    issues = validate_story_summary_collection(collection)
    if args.require_reviewed:
        issues.extend(_check_require_reviewed(raw_documents))

    if issues:
        print("[エラー] story summaryの整合性検証に失敗しました:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"[validate] story_summaries: {input_path} ({len(raw_documents)} 件)")
        print("[validate] schema検証・整合性検証: OK")

    return 0


if __name__ == "__main__":
    sys.exit(main())
