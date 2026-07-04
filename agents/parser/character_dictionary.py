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


def _validate_alias_duplicates(entries: list[CharacterDictionaryEntry]) -> list[str]:
    """aliasesの重複を検出する。

    aliasesは検索補助 (resolve_character_by_name) にのみ使われ、同一人物
    確定の根拠にはしない方針だが、重複値があると「最初に一致した方が
    採用される」曖昧さが黙って発生するため、以下2種類を検出する。

    - 同一エントリ内でaliasesの値が重複している
    - 同じalias値が複数エントリ (sourceCharacterId違い) で使われている
    """
    issues: list[str] = []
    alias_owners: dict[str, list[str]] = {}

    for entry in entries:
        if len(entry.aliases) != len(set(entry.aliases)):
            issues.append(
                f"sourceCharacterId '{entry.source_character_id}': "
                "aliasesに重複した値があります"
            )
        for alias in entry.aliases:
            alias_owners.setdefault(alias, []).append(entry.source_character_id)

    for alias, owners in alias_owners.items():
        if len(owners) > 1:
            issues.append(
                f"alias '{alias}' が複数キャラクター "
                f"({', '.join(owners)}) で重複しています"
            )

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
    issues.extend(_validate_alias_duplicates(entries))
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
    こと（Real_Data_Dry_Run.md参照、docs/runbooks/Character_Dictionary_Review.md
    §dry-run後のcoverage report確認手順）。

    knownCount/coveragePercentageは「辞書に登録済み (statusを問わない)」の
    割合であることに注意する。confirmed (existingCharacterIdとして解決され
    mergeされる) とname_only (displayNameのみ、mergeではunresolvedのまま)
    は意味が異なるため、confirmedObservedCount/nameOnlyObservedCountで
    内訳を分けて確認できるようにしている
    （名前一致だけでconfirmed扱いにしないルールの遵守状況を、辞書全体の
    状態からも確認できるようにするため）。
    """
    status_by_id = {entry.source_character_id: entry.status for entry in entries}
    known_ids = set(status_by_id.keys())
    observed_ids = set(observed_source_ids.keys())

    known_observed = observed_ids & known_ids
    unknown_observed = observed_ids - known_ids

    observed_count = len(observed_ids)
    known_count = len(known_observed)
    unknown_count = len(unknown_observed)
    confirmed_observed_count = sum(
        1 for sid in known_observed if status_by_id[sid] == STATUS_CONFIRMED
    )
    name_only_observed_count = sum(
        1 for sid in known_observed if status_by_id[sid] == STATUS_NAME_ONLY
    )

    def _percentage(numerator: int) -> float:
        return round(100.0 * numerator / observed_count, 1) if observed_count else 100.0

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
        "coveragePercentage": _percentage(known_count),
        "confirmedObservedCount": confirmed_observed_count,
        "nameOnlyObservedCount": name_only_observed_count,
        "confirmedCoveragePercentage": _percentage(confirmed_observed_count),
        "nameOnlyCoveragePercentage": _percentage(name_only_observed_count),
        "dictionaryTotalCount": len(entries),
        "dictionaryConfirmedCount": sum(
            1 for s in status_by_id.values() if s == STATUS_CONFIRMED
        ),
        "dictionaryNameOnlyCount": sum(
            1 for s in status_by_id.values() if s == STATUS_NAME_ONLY
        ),
        "topUnknownIds": top_unknown,
    }


def build_review_candidates(
    observed_source_ids: dict[str, int],
    known_ids: set[str],
) -> list[dict[str, Any]]:
    """未登録sourceCharacterId (辞書に無いID) を、人間確認用テンプレートの
    1エントリ形式で出現回数の降順に列挙する。

    戻り値の各要素は displayName・本文などの実データ内容を含まず、
    ID番号・出現回数と空のプレースホルダーのみで構成される。呼び出し側
    (scripts/check_character_dictionary_coverage.py の
    --review-template-output) は、これをcommit対象外のローカルパス
    (workspace/dry_runs/配下等) へ書き出すこと
    (docs/runbooks/Character_Dictionary_Review.md 参照)。
    """
    unknown = {
        sid: count for sid, count in observed_source_ids.items() if sid not in known_ids
    }
    return [
        {
            "sourceCharacterId": sid,
            "observedCount": count,
            "suggestedDisplayName": None,
            "confirmedCharacterId": None,
            "status": STATUS_NAME_ONLY,
            "reviewerNotes": None,
        }
        for sid, count in sorted(unknown.items(), key=lambda kv: kv[1], reverse=True)
    ]


def build_character_review_packet(
    collection: dict[str, Any],
    entries: list[CharacterDictionaryEntry],
) -> list[dict[str, Any]]:
    """merged knowledge collectionのcharacter entityから、人間が
    sourceCharacterId -> characterId mappingを確認・記入しやすい
    review packetの1エントリ形式を組み立てる (scripts/build_character_review_packet.py
    から呼ばれる)。

    既にstatus: mergedのentity (= 実運用ではstatus: confirmedの辞書エントリに
    よって解決済み)、および辞書側で既にstatus: confirmedになっている
    sourceCharacterIdは、再レビューが不要なため除外する。それ以外
    (name_only、または辞書に一切登録が無いunknown) のみを対象とし、
    observedCount (evidenceRefs件数) の降順で返す。

    戻り値の各要素は sourceCharacterId・displayName・辞書の既存状態・
    件数統計・空のレビュー用プレースホルダーのみで構成され、元セリフ・
    raw payload・merged collection全文は含まない。
    """
    dict_by_source_id = {entry.source_character_id: entry for entry in entries}
    packets_by_source_id: dict[str, dict[str, Any]] = {}
    episode_ids_by_source_id: dict[str, set[str]] = {}
    document_ids_by_source_id: dict[str, set[str]] = {}

    for entity in collection.get("entities", {}).get("characters", []) or []:
        # merged knowledge collection側の"merged" (Wiki層のSTATUS_MERGEDと
        # 同じ値だが、Parser層をWiki/Merger層から独立させるためここでは
        # 文字列リテラルで比較する)。
        if entity.get("status") == "merged":
            continue
        source_ids = entity.get("sourceCharacterIds") or []
        if not source_ids:
            continue

        evidence_refs = entity.get("evidenceRefs") or []
        episode_ids = {
            ref.get("episodeId") for ref in evidence_refs if ref.get("episodeId")
        }
        document_ids = {
            ref.get("sourceDocumentId")
            for ref in evidence_refs
            if ref.get("sourceDocumentId")
        }
        display_name = entity.get("displayName")

        for source_id in source_ids:
            source_id = str(source_id)
            dict_entry = dict_by_source_id.get(source_id)
            if dict_entry is not None and dict_entry.status == STATUS_CONFIRMED:
                continue

            packet = packets_by_source_id.setdefault(
                source_id,
                {
                    "sourceCharacterId": source_id,
                    "displayName": None,
                    "existingDictionaryStatus": (
                        dict_entry.status if dict_entry else "unknown"
                    ),
                    "existingCharacterId": (
                        dict_entry.character_id if dict_entry else None
                    ),
                    "aliases": list(dict_entry.aliases) if dict_entry else [],
                    "observedCount": 0,
                    "appearedEpisodeCount": 0,
                    "sourceDocumentCount": 0,
                    "humanReviewStatus": "pending",
                    "humanConfirmedCharacterId": None,
                    "notes": "",
                },
            )
            if not packet["displayName"] and display_name:
                packet["displayName"] = display_name
            packet["observedCount"] += len(evidence_refs)
            episode_ids_by_source_id.setdefault(source_id, set()).update(episode_ids)
            document_ids_by_source_id.setdefault(source_id, set()).update(document_ids)

    packets = list(packets_by_source_id.values())
    for packet in packets:
        source_id = packet["sourceCharacterId"]
        packet["appearedEpisodeCount"] = len(
            episode_ids_by_source_id.get(source_id, set())
        )
        packet["sourceDocumentCount"] = len(
            document_ids_by_source_id.get(source_id, set())
        )

    packets.sort(key=lambda p: p["observedCount"], reverse=True)
    return packets
