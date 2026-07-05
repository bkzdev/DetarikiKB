#!/usr/bin/env python3
"""
Validate Character Profiles
`knowledge/dictionaries/character_profiles.yaml`（公式プロフィール辞書）を
schema検証し、`knowledge/dictionaries/characters.yaml`（ID解決用辞書）との
整合性を確認する補助スクリプト。

**重要**: プロフィール本文の品質判断・AI推測は一切行わない。schema・
重複・characters.yamlとの整合性のみを機械的に検証する
(docs/architecture/06_AI/Character_Profile_Dictionary_Design.md 参照)。

Usage:
    uv run python scripts/validate_character_profiles.py \\
        --profiles knowledge/dictionaries/character_profiles.yaml \\
        --characters knowledge/dictionaries/characters.yaml

Exit codes:
    0: 検証成功
    1: 入力ファイルが見つからない
    2: schema検証、または整合性検証に失敗した
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

from agents.parser.character_dictionary import load_character_dictionary  # noqa: E402
from agents.parser.character_profiles import (  # noqa: E402
    STATUS_CONFIRMED,
    STATUS_DEPRECATED,
    STATUS_DRAFT,
    load_character_profiles,
    validate_character_profiles,
)

DEFAULT_PROFILES_PATH = (
    _PROJECT_ROOT / "knowledge" / "dictionaries" / "character_profiles.yaml"
)
DEFAULT_CHARACTERS_PATH = (
    _PROJECT_ROOT / "knowledge" / "dictionaries" / "characters.yaml"
)
DEFAULT_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "character_profiles.schema.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "character_profiles.yamlをschema検証し、characters.yamlとの整合性"
            "(confirmed済みcharacterIdへの紐づけ) を確認する"
        ),
    )
    parser.add_argument(
        "--profiles",
        default=str(DEFAULT_PROFILES_PATH),
        help=f"character_profiles.yamlのパス (デフォルト: {DEFAULT_PROFILES_PATH})",
    )
    parser.add_argument(
        "--characters",
        default=str(DEFAULT_CHARACTERS_PATH),
        help=f"characters.yamlのパス (デフォルト: {DEFAULT_CHARACTERS_PATH})",
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


def main() -> int:
    args = parse_args()

    profiles_path = Path(args.profiles)
    if not profiles_path.exists():
        print(
            f"[エラー] 入力ファイルが見つかりません: {profiles_path}", file=sys.stderr
        )
        return 1

    with open(profiles_path, encoding="utf-8") as f:
        raw_data = yaml.safe_load(f) or {}

    schema_path = Path(args.schema)
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    schema_errors = sorted(
        Draft7Validator(schema).iter_errors(raw_data), key=lambda e: list(e.path)
    )
    if schema_errors:
        print("[エラー] character_profilesのschema検証に失敗しました:", file=sys.stderr)
        for e in schema_errors:
            print(f"  - {list(e.path)}: {e.message}", file=sys.stderr)
        return 2

    profiles = load_character_profiles(profiles_path)
    character_dictionary = load_character_dictionary(args.characters)

    issues = validate_character_profiles(profiles, character_dictionary)
    if issues:
        print("[エラー] character_profilesの整合性検証に失敗しました:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 2

    if not args.quiet:
        status_counts = {
            STATUS_DRAFT: sum(1 for p in profiles if p.status == STATUS_DRAFT),
            STATUS_CONFIRMED: sum(1 for p in profiles if p.status == STATUS_CONFIRMED),
            STATUS_DEPRECATED: sum(
                1 for p in profiles if p.status == STATUS_DEPRECATED
            ),
        }
        print(f"[validate] character_profiles: {profiles_path} ({len(profiles)} 件)")
        print(
            f"[validate]   status内訳: draft={status_counts[STATUS_DRAFT]} / "
            f"confirmed={status_counts[STATUS_CONFIRMED]} / "
            f"deprecated={status_counts[STATUS_DEPRECATED]}"
        )
        print("[validate] schema検証・整合性検証: OK")

    return 0


if __name__ == "__main__":
    sys.exit(main())
