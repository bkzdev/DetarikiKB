"""
DKB Parser - Character Dictionary Loader
人手管理のキャラクター辞書 (knowledge/dictionaries/characters.yaml 相当) を
読み込み・検証し、sourceCharacterId解決・カバレッジレポート作成を行う。

`reference/parser/characters_reference.json`（読み取り専用、表示名のみの
フラットな`{sourceCharacterId: name}`形式）とは異なり、この辞書は
`characterId`（正規Character ID、`CHAR_{ROMANIZED_NAME}`形式）も
人手で管理できる形式にする（docs/architecture/06_AI/Canonical_ID_Policy.md、
docs/architecture/06_AI/Merged_Knowledge_Design.md §2.4）。

**重要**: `resolve_character_by_name` は名前一致のみでの解決手段として
提供するが、`agents/parser/resolver.py` の自動話者解決や
`agents/merger/` の自動merge判定からは一切呼び出さない
（Merged_Knowledge_Design.md §4.1 原則2: 名前一致だけで自動確定しない）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# CharacterIdの許容パターン (Identifier_Specification.md §6.1: CHAR_{ROMANIZED_NAME}、
# §2.3のIdString許可文字集合と同一。agents/merger/canonical_ids.pyの
# _CANONICAL_ID_PATTERNと同じ規則だが、Parser層からMerger層への逆依存を
# 避けるためここでは独立して定義する)。
CHARACTER_ID_PATTERN = re.compile(r"^CHAR_[A-Z0-9_-]+$")

# 許可するstatus値
STATUS_CONFIRMED = "confirmed"
"""characterId (canonical ID) が人手確認済み"""

STATUS_NAME_ONLY = "name_only"
"""表示名のみ判明しており、canonical IDはまだ未確定"""

VALID_STATUSES = frozenset({STATUS_CONFIRMED, STATUS_NAME_ONLY})


@dataclass
class CharacterDictionaryEntry:
    """辞書内の1キャラクターエントリ"""

    source_character_id: str
    display_name: str
    character_id: str | None = None
    aliases: list[str] = field(default_factory=list)
    status: str = STATUS_NAME_ONLY
    notes: str | None = None


def load_character_dictionary(path: str | Path) -> list[CharacterDictionaryEntry]:
    """`knowledge/dictionaries/characters.yaml`相当のYAMLファイルを読み込む。

    ファイルが存在しない場合は空リストを返す（呼び出し側で警告するかは
    呼び出し側の責任とする、既存のCharacterDictionary.load_from_jsonと
    同じ方針）。
    """
    p = Path(path)
    if not p.exists():
        return []

    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    entries: list[CharacterDictionaryEntry] = []
    for raw in data.get("characters", []) or []:
        entries.append(
            CharacterDictionaryEntry(
                source_character_id=str(raw.get("sourceCharacterId", "")),
                display_name=raw.get("displayName", ""),
                character_id=raw.get("characterId"),
                aliases=list(raw.get("aliases", []) or []),
                status=raw.get("status", STATUS_NAME_ONLY),
                notes=raw.get("notes"),
            )
        )
    return entries


def _validate_single_entry(index: int, entry: CharacterDictionaryEntry) -> list[str]:
    """1エントリ分の整合性を検証する (validate_character_dictionaryの複雑度
    を下げるためのヘルパー、重複IDチェックは呼び出し側でまとめて行う)。"""
    issues: list[str] = []

    if not entry.source_character_id:
        return [f"[{index}] sourceCharacterIdが空です"]

    if not entry.display_name:
        issues.append(
            f"sourceCharacterId '{entry.source_character_id}': displayNameが空です"
        )

    if entry.status not in VALID_STATUSES:
        issues.append(
            f"sourceCharacterId '{entry.source_character_id}': "
            f"未知のstatus '{entry.status}' "
            f"(許可値: {sorted(VALID_STATUSES)})"
        )

    if entry.character_id is not None:
        if not CHARACTER_ID_PATTERN.match(entry.character_id):
            issues.append(
                f"sourceCharacterId '{entry.source_character_id}': "
                f"characterId '{entry.character_id}' の形式が不正です "
                f"(CHAR_{{ROMANIZED_NAME}}形式である必要があります)"
            )
        if entry.status != STATUS_CONFIRMED:
            issues.append(
                f"sourceCharacterId '{entry.source_character_id}': "
                f"characterIdが設定されていますが status が "
                f"'{STATUS_CONFIRMED}' ではありません ('{entry.status}')"
            )
    elif entry.status == STATUS_CONFIRMED:
        issues.append(
            f"sourceCharacterId '{entry.source_character_id}': "
            f"status が '{STATUS_CONFIRMED}' ですが characterId が"
            "設定されていません"
        )

    return issues


def _validate_duplicates(entries: list[CharacterDictionaryEntry]) -> list[str]:
    """sourceCharacterId/characterIdの重複を検出する。"""
    issues: list[str] = []
    seen_source_ids: dict[str, int] = {}
    seen_character_ids: dict[str, int] = {}

    for entry in entries:
        if entry.source_character_id:
            seen_source_ids[entry.source_character_id] = (
                seen_source_ids.get(entry.source_character_id, 0) + 1
            )
        if entry.character_id is not None:
            seen_character_ids[entry.character_id] = (
                seen_character_ids.get(entry.character_id, 0) + 1
            )

    for source_id, count in seen_source_ids.items():
        if count > 1:
            issues.append(f"sourceCharacterId '{source_id}' が{count}件重複しています")

    for character_id, count in seen_character_ids.items():
        if count > 1:
            issues.append(f"characterId '{character_id}' が{count}件重複しています")

    return issues


def validate_character_dictionary(
    entries: list[CharacterDictionaryEntry],
) -> list[str]:
    """辞書エントリ一覧の整合性を検証する。

    戻り値: 問題を説明する人間可読な文字列のリスト（空なら問題無し）。
    schema検証のように例外を送出せず、呼び出し側が全件まとめて確認できる
    ようにする（agents/merger/canonical_ids.pyのvalidate_canonical_idsと
    同じ設計方針）。
    """
    issues: list[str] = []
    for i, entry in enumerate(entries):
        issues.extend(_validate_single_entry(i, entry))
    issues.extend(_validate_duplicates(entries))
    return issues


def resolve_character_by_source_id(
    entries: list[CharacterDictionaryEntry], source_id: str
) -> CharacterDictionaryEntry | None:
    """sourceCharacterIdから辞書エントリを解決する（構造化ID解決、安全）。"""
    target = str(source_id)
    for entry in entries:
        if entry.source_character_id == target:
            return entry
    return None


def resolve_character_by_name(
    entries: list[CharacterDictionaryEntry], name: str
) -> CharacterDictionaryEntry | None:
    """displayName/aliasesの完全一致から辞書エントリを解決する。

    **警告**: これは名前一致のみによる解決であり、同名の別人が存在しうる
    ため、この結果を自動的にresolved/mergedとして扱ってはならない
    （Canonical_ID_Policy.md §5、Merged_Knowledge_Design.md §4.1原則2）。
    呼び出し側は人間のレビューを前提とした補助的な検索用途にのみ使うこと。
    """
    for entry in entries:
        if entry.display_name == name or name in entry.aliases:
            return entry
    return None


def build_character_dictionary_coverage_report(
    entries: list[CharacterDictionaryEntry],
    observed_source_ids: dict[str, int],
) -> dict[str, Any]:
    """実データ（等）から観測されたsourceCharacterIdの出現回数と、辞書の
    登録状況を突き合わせたカバレッジレポートを作る。

    Args:
        entries: load_character_dictionaryで読み込んだ辞書エントリ
        observed_source_ids: {sourceCharacterId: 出現回数}

    戻り値のキーは実データの内容（本文・IDの生一覧）を含まないよう
    最小限にとどめる。呼び出し側がこれをそのままcommitしないよう注意する
    こと（Real_Data_Dry_Run.md参照）。
    """
    known_ids = {entry.source_character_id for entry in entries}
    observed_ids = set(observed_source_ids.keys())

    known_observed = observed_ids & known_ids
    unknown_observed = observed_ids - known_ids

    observed_count = len(observed_ids)
    known_count = len(known_observed)
    unknown_count = len(unknown_observed)
    coverage_percentage = (
        round(100.0 * known_count / observed_count, 1) if observed_count else 100.0
    )

    top_unknown = sorted(
        (
            {"sourceCharacterId": sid, "count": observed_source_ids[sid]}
            for sid in unknown_observed
        ),
        key=lambda item: item["count"],
        reverse=True,
    )[:20]

    return {
        "observedCount": observed_count,
        "knownCount": known_count,
        "unknownCount": unknown_count,
        "coveragePercentage": coverage_percentage,
        "topUnknownIds": top_unknown,
    }
