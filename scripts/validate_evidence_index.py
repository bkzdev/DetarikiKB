#!/usr/bin/env python3
"""
Validate Evidence Index
`knowledge/evidence/stories/{storyId}.yaml`（Public Evidence Index）を
schema検証し、duplicate evidenceId・raw text禁止文字列・
`visibility.rawTextIncluded`等の整合性を確認する補助スクリプト。

**重要**: このスクリプトはPublic Evidence Indexのみを対象とする。raw text
を含みうるInternal Review Evidence Packet（`workspace/review_packets/
evidence/`相当）は対象外であり、混同しないこと
(docs/architecture/06_AI/Evidence_Index_Design.md 参照)。

Usage:
    # 単一ファイル
    uv run python scripts/validate_evidence_index.py \\
        --input knowledge/evidence/stories/EVT_SAMPLE.yaml

    # directory (直下の *.yaml/*.yml を収集)
    uv run python scripts/validate_evidence_index.py \\
        --input knowledge/evidence/stories

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

from agents.wiki_generator.evidence_index import (  # noqa: E402
    EvidenceIndexCollection,
    parse_evidence_index_document,
    validate_evidence_index_collection,
)

DEFAULT_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "evidence_index.schema.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "evidence index YAML (単一ファイルまたはdirectory) をschema検証し、"
            "duplicate evidenceId・raw text禁止文字列・"
            "visibility.rawTextIncludedを確認する"
        ),
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="evidence index YAMLファイル、またはdirectoryのパス",
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help=f"JSON Schemaのパス (デフォルト: {DEFAULT_SCHEMA_PATH})",
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
        print("[エラー] evidence indexのschema検証に失敗しました:", file=sys.stderr)
        for message in schema_errors:
            print(f"  - {message}", file=sys.stderr)
        return 1

    collection = EvidenceIndexCollection(
        documents=[parse_evidence_index_document(raw) for _, raw in raw_documents]
    )
    issues = validate_evidence_index_collection(collection)

    if issues:
        print("[エラー] evidence indexの整合性検証に失敗しました:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1

    if not args.quiet:
        entry_count = sum(len(doc.entries) for doc in collection.documents)
        print(
            f"[validate] evidence_index: {input_path} "
            f"({len(raw_documents)} ファイル、{entry_count} entries)"
        )
        print("[validate] schema検証・整合性検証: OK")

    return 0


if __name__ == "__main__":
    sys.exit(main())
