#!/usr/bin/env python3
"""
Compare / Import Character Dictionary Reference
`reference/parser/characters_reference.json`（sourceCharacterId →
displayNameのフラットなレガシー辞書、読み取り専用）と、
`knowledge/dictionaries/characters.yaml`（人手管理の正規辞書）を比較し、
差分を確認する。

既定は dry-run（差分表示のみ、ファイルは一切変更しない）。`--write` を
指定した場合のみ、YAML側に存在しない sourceCharacterId を
`status: name_only` として追記する。

このスクリプトは以下を絶対に行わない
(docs/runbooks/Character_Dictionary_Review.md 参照):
- `characterId`（canonical ID）の自動生成
- `status: confirmed` への昇格
- 既存entry（confirmed/name_only問わず）の上書き・削除
- displayNameが異なる既存entryの書き換え（warningとして報告するのみ）

Usage:
    # dry-run (差分表示のみ、ファイル変更なし)
    uv run python scripts/compare_character_dictionaries.py

    # YAML未登録IDを status: name_only として追記する
    uv run python scripts/compare_character_dictionaries.py --write

    # 入力元を明示指定
    uv run python scripts/compare_character_dictionaries.py \
        --reference-json reference/parser/characters_reference.json \
        --dictionary knowledge/dictionaries/characters.yaml

Exit codes:
    0: 実行成功（差分の有無やwrite実施有無に関わらず）
    1: 入力ファイル（JSON/YAML）の読み込み・検証に失敗した
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.parser.character_dictionary import (  # noqa: E402
    CharacterDictionaryEntry,
    load_character_dictionary,
    validate_character_dictionary,
)

DEFAULT_REFERENCE_JSON = (
    _PROJECT_ROOT / "reference" / "parser" / "characters_reference.json"
)
DEFAULT_DICTIONARY_PATH = (
    _PROJECT_ROOT / "knowledge" / "dictionaries" / "characters.yaml"
)

IMPORT_NOTES = (
    "Imported from reference character dictionary; requires human confirmation."
)


def load_reference_json(path: str | Path) -> dict[str, str]:
    """`characters_reference.json`相当のフラットな
    `{sourceCharacterId: displayName}`形式JSONを読み込む。

    値がdict形式（`{"name": ..., "id": ...}`）の場合は`name`キーのみを
    displayNameとして扱う（`agents/parser/resolver.py`の
    `CharacterDictionary.load_from_json`と同じ許容範囲）。
    """
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    result: dict[str, str] = {}
    for source_id, value in data.items():
        if isinstance(value, str):
            result[str(source_id)] = value
        elif isinstance(value, dict) and "name" in value:
            result[str(source_id)] = str(value["name"])
    return result


@dataclass
class DictionaryDiff:
    """JSON参照辞書とYAML正規辞書の比較結果（実データ本文は含まない）。"""

    json_total: int
    yaml_total: int
    matching_count: int
    missing_from_yaml: dict[str, str] = field(default_factory=dict)
    yaml_only_ids: list[str] = field(default_factory=list)
    display_name_conflicts: list[tuple[str, str, str]] = field(default_factory=list)
    confirmed_count: int = 0
    name_only_count: int = 0


def compute_diff(
    reference: dict[str, str], entries: list[CharacterDictionaryEntry]
) -> DictionaryDiff:
    """JSON参照辞書とYAMLエントリ一覧を比較する（純粋関数、ファイルI/Oなし）。"""
    yaml_by_id = {entry.source_character_id: entry for entry in entries}
    json_ids = set(reference.keys())
    yaml_ids = set(yaml_by_id.keys())

    matching_ids = json_ids & yaml_ids
    missing_from_yaml = {
        sid: reference[sid] for sid in sorted(json_ids - yaml_ids, key=int)
    }
    yaml_only_ids = sorted(yaml_ids - json_ids, key=int)

    conflicts: list[tuple[str, str, str]] = []
    for sid in sorted(matching_ids, key=int):
        json_name = reference[sid]
        yaml_name = yaml_by_id[sid].display_name
        if json_name != yaml_name:
            conflicts.append((sid, json_name, yaml_name))

    return DictionaryDiff(
        json_total=len(reference),
        yaml_total=len(entries),
        matching_count=len(matching_ids),
        missing_from_yaml=missing_from_yaml,
        yaml_only_ids=yaml_only_ids,
        display_name_conflicts=conflicts,
        confirmed_count=sum(1 for e in entries if e.status == "confirmed"),
        name_only_count=sum(1 for e in entries if e.status == "name_only"),
    )


def _quoted_yaml_string(value: str) -> str:
    """YAMLのダブルクォート文字列として安全にエスケープする
    (displayNameは通常の日本語人名のみを想定、バックスラッシュ・
    ダブルクォートのみ最小限エスケープする)。"""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


_LIST_ITEM_INDENT_PATTERN = re.compile(r"^([ \t]*)- ", re.MULTILINE)

# 既存characters.yamlの規約 (先頭2スペースインデント)。ファイル内に
# 既存エントリが1件も無い場合のフォールバックにのみ使う。
_DEFAULT_LIST_ITEM_INDENT = "  "


def _detect_list_item_indent(content: str) -> str:
    """既存YAMLファイル内の`characters:`リスト項目のインデント
    (先頭の空白文字列) を検出する。手書きYAMLはPyYAMLの既定出力
    (インデント無し) と異なる場合があるため、追記する新規エントリを
    既存エントリと同じインデントに揃える必要がある。エントリが1件も
    無ければプロジェクトの既存規約 (2スペース) をデフォルトにする。
    """
    match = _LIST_ITEM_INDENT_PATTERN.search(content)
    if match:
        return match.group(1)
    return _DEFAULT_LIST_ITEM_INDENT


def format_new_entry_yaml(
    source_id: str, display_name: str, indent: str = _DEFAULT_LIST_ITEM_INDENT
) -> str:
    """既存`knowledge/dictionaries/characters.yaml`のエントリ形式と同じ
    見た目のYAMLテキストブロックを組み立てる（`characterId: null`・
    `status: name_only`固定、confirmed化は絶対にしない）。"""
    field_indent = indent + "  "
    return (
        f'{indent}- sourceCharacterId: "{source_id}"\n'
        f"{field_indent}characterId: null\n"
        f"{field_indent}displayName: {_quoted_yaml_string(display_name)}\n"
        f"{field_indent}aliases: []\n"
        f'{field_indent}status: "name_only"\n'
        f"{field_indent}notes: {_quoted_yaml_string(IMPORT_NOTES)}\n"
    )


def write_new_entries(yaml_path: Path, missing_from_yaml: dict[str, str]) -> None:
    """未登録のsourceCharacterIdを`status: name_only`としてYAMLファイル末尾へ
    追記する。既存の行は一切変更しない（テキスト追記のみ、ファイル全体の
    再ダンプはコメント・整形を壊すため行わない）。

    前提: `characters:`リストがファイルの最後の内容であること
    （`knowledge/dictionaries/characters.yaml`の現状の構成と一致）。
    `characters:`より後に別のトップレベルキーがある構成へ変更した場合、
    このシンプルな末尾追記方式は使えなくなる点に注意する。
    """
    if not missing_from_yaml:
        return
    with open(yaml_path, encoding="utf-8") as f:
        content = f.read()
    indent = _detect_list_item_indent(content)
    if not content.endswith("\n"):
        content += "\n"
    for source_id, display_name in missing_from_yaml.items():
        content += format_new_entry_yaml(source_id, display_name, indent=indent)
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(content)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "reference/parser/characters_reference.json と "
            "knowledge/dictionaries/characters.yaml の差分を確認する "
            "(既定はdry-run、--writeでname_only entryのみ追記)"
        ),
    )
    parser.add_argument(
        "--reference-json",
        default=str(DEFAULT_REFERENCE_JSON),
        help=f"参照JSONのパス (デフォルト: {DEFAULT_REFERENCE_JSON})",
    )
    parser.add_argument(
        "--dictionary",
        default=str(DEFAULT_DICTIONARY_PATH),
        help=f"人手管理辞書YAMLのパス (デフォルト: {DEFAULT_DICTIONARY_PATH})",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "YAML未登録のsourceCharacterIdをstatus: name_onlyとして追記する "
            "(指定しない場合はdry-runで差分表示のみ)"
        ),
    )
    return parser.parse_args()


def print_diff_report(diff: DictionaryDiff) -> None:
    print(f"[compare] JSON総件数:  {diff.json_total}")
    print(f"[compare] YAML総件数:  {diff.yaml_total}")
    print(
        f"[compare]   confirmed: {diff.confirmed_count} / "
        f"name_only: {diff.name_only_count}"
    )
    print(f"[compare] sourceCharacterId一致件数: {diff.matching_count}")
    print(f"[compare] YAML未登録件数 (JSONのみ): {len(diff.missing_from_yaml)}")
    if diff.missing_from_yaml:
        for sid in diff.missing_from_yaml:
            print(f"  - {sid}")
    print(f"[compare] JSON未登録件数 (YAMLのみ): {len(diff.yaml_only_ids)}")
    if diff.yaml_only_ids:
        for sid in diff.yaml_only_ids:
            print(f"  - {sid}")
    print(f"[compare] displayName不一致件数: {len(diff.display_name_conflicts)}")
    if diff.display_name_conflicts:
        print(
            "[警告] displayNameが異なるエントリがあります "
            "(自動上書きはしません。人間が確認してください):",
            file=sys.stderr,
        )
        for sid, json_name, yaml_name in diff.display_name_conflicts:
            print(
                f"  - sourceCharacterId '{sid}': JSON='{json_name}' / "
                f"YAML='{yaml_name}'",
                file=sys.stderr,
            )


def main() -> int:
    args = parse_args()

    reference_path = Path(args.reference_json)
    reference = load_reference_json(reference_path)
    if not reference:
        print(f"[エラー] 参照JSONが空か読み込めませんでした: {reference_path}")
        return 1

    dictionary_path = Path(args.dictionary)
    entries = load_character_dictionary(dictionary_path)
    if not entries:
        print(f"[エラー] 辞書が空か読み込めませんでした: {dictionary_path}")
        return 1

    issues = validate_character_dictionary(entries)
    if issues:
        print("[エラー] 辞書の検証に失敗しました:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1

    diff = compute_diff(reference, entries)
    print_diff_report(diff)

    if args.write:
        if diff.missing_from_yaml:
            write_new_entries(dictionary_path, diff.missing_from_yaml)
            print(
                f"[compare] {len(diff.missing_from_yaml)} 件を "
                f"status: name_only として {dictionary_path} へ追記しました"
            )
        else:
            print("[compare] 追記対象なし (差分0件)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
