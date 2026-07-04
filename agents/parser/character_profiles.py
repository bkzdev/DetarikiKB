"""
DKB Parser - Character Profile Dictionary Loader
公式プロフィール辞書 (knowledge/dictionaries/character_profiles.yaml相当) を
読み込み・検証する。

knowledge/dictionaries/characters.yaml (ID解決用辞書、
agents/parser/character_dictionary.py) とは別物であり、公式プロフィール
情報 (読み仮名/所属/身長/誕生日/血液型/CV/キャラ別特記事項/自己紹介文) を
保持する (docs/architecture/06_AI/Character_Profile_Dictionary_Design.md 参照)。

**重要**: このモジュールはプロフィール本文の品質判断・AI推測は行わない。
schema・重複・characters.yamlとの整合性のみを機械的に検証する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .character_dictionary import CHARACTER_ID_PATTERN, CharacterDictionaryEntry

STATUS_DRAFT = "draft"
"""人間未確認、下書き状態"""

STATUS_CONFIRMED = "confirmed"
"""人間確認済み"""

STATUS_DEPRECATED = "deprecated"
"""廃止済み"""

VALID_STATUSES = frozenset({STATUS_DRAFT, STATUS_CONFIRMED, STATUS_DEPRECATED})

_MAX_SELF_INTRODUCTION_LENGTH = 500
_MAX_PROFILE_HIGHLIGHT_VALUE_LENGTH = 200


@dataclass
class Reading:
    """読み仮名 (kana/romaji)。ID解決用のローマ字表記とは別軸の情報。"""

    kana: str | None = None
    romaji: str | None = None


@dataclass
class Birthday:
    """誕生日 (month/dayのみ保持し、年は扱わない)。"""

    month: int | None = None
    day: int | None = None
    display: str | None = None


@dataclass
class ProfileHighlight:
    """【好きなこと】等のキャラ別特記事項 (キャラごとに1件のlabel/value)。"""

    label: str
    value: str


@dataclass
class ProfileSource:
    """プロフィール情報の出典。"""

    source_type: str = "unknown"
    label: str | None = None
    reference_id: str | None = None
    notes: str | None = None


@dataclass
class CharacterProfile:
    """1キャラクター分の公式プロフィール。"""

    character_id: str
    display_name: str
    status: str = STATUS_DRAFT
    reading: Reading | None = None
    affiliation: list[str] = field(default_factory=list)
    height_cm: int | None = None
    birthday: Birthday | None = None
    blood_type: str | None = None
    cv: str | None = None
    profile_highlight: ProfileHighlight | None = None
    self_introduction: str | None = None
    source: ProfileSource | None = None
    notes: str | None = None


def _parse_reading(raw: dict[str, Any] | None) -> Reading | None:
    if raw is None:
        return None
    return Reading(kana=raw.get("kana"), romaji=raw.get("romaji"))


def _parse_birthday(raw: dict[str, Any] | None) -> Birthday | None:
    if raw is None:
        return None
    return Birthday(
        month=raw.get("month"), day=raw.get("day"), display=raw.get("display")
    )


def _parse_profile_highlight(raw: dict[str, Any] | None) -> ProfileHighlight | None:
    if raw is None:
        return None
    return ProfileHighlight(label=raw.get("label", ""), value=raw.get("value", ""))


def _parse_source(raw: dict[str, Any] | None) -> ProfileSource | None:
    if raw is None:
        return None
    return ProfileSource(
        source_type=raw.get("sourceType", "unknown"),
        label=raw.get("label"),
        reference_id=raw.get("referenceId"),
        notes=raw.get("notes"),
    )


def load_character_profiles(path: str | Path) -> list[CharacterProfile]:
    """`knowledge/dictionaries/character_profiles.yaml`相当のYAMLを読み込む。

    ファイルが存在しない場合は空リストを返す
    (agents/parser/character_dictionary.pyのload_character_dictionaryと同じ方針)。
    """
    p = Path(path)
    if not p.exists():
        return []

    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    profiles: list[CharacterProfile] = []
    for raw in data.get("profiles", []) or []:
        profiles.append(
            CharacterProfile(
                character_id=raw.get("characterId", ""),
                display_name=raw.get("displayName", ""),
                status=raw.get("status", STATUS_DRAFT),
                reading=_parse_reading(raw.get("reading")),
                affiliation=list(raw.get("affiliation", []) or []),
                height_cm=raw.get("heightCm"),
                birthday=_parse_birthday(raw.get("birthday")),
                blood_type=raw.get("bloodType"),
                cv=raw.get("cv"),
                profile_highlight=_parse_profile_highlight(raw.get("profileHighlight")),
                self_introduction=raw.get("selfIntroduction"),
                source=_parse_source(raw.get("source")),
                notes=raw.get("notes"),
            )
        )
    return profiles


def _validate_birthday(profile: CharacterProfile) -> list[str]:
    if profile.birthday is None:
        return []
    issues: list[str] = []
    month = profile.birthday.month
    if month is not None and not (1 <= month <= 12):
        issues.append(
            f"characterId '{profile.character_id}': "
            f"birthday.monthが範囲外です ({month}、1-12である必要があります)"
        )
    day = profile.birthday.day
    if day is not None and not (1 <= day <= 31):
        issues.append(
            f"characterId '{profile.character_id}': "
            f"birthday.dayが範囲外です ({day}、1-31である必要があります)"
        )
    return issues


def _validate_profile_highlight(profile: CharacterProfile) -> list[str]:
    highlight = profile.profile_highlight
    if highlight is None:
        return []
    if not highlight.label or not highlight.value:
        return [
            f"characterId '{profile.character_id}': "
            "profileHighlightのlabel/valueは空にできません"
        ]
    if len(highlight.value) > _MAX_PROFILE_HIGHLIGHT_VALUE_LENGTH:
        return [
            f"characterId '{profile.character_id}': "
            f"profileHighlight.valueが{_MAX_PROFILE_HIGHLIGHT_VALUE_LENGTH}文字を"
            "超えています"
        ]
    return []


def _validate_self_introduction(profile: CharacterProfile) -> list[str]:
    if (
        profile.self_introduction
        and len(profile.self_introduction) > _MAX_SELF_INTRODUCTION_LENGTH
    ):
        return [
            f"characterId '{profile.character_id}': "
            f"selfIntroductionが{_MAX_SELF_INTRODUCTION_LENGTH}文字を超えています"
        ]
    return []


def _validate_single_profile(index: int, profile: CharacterProfile) -> list[str]:
    """1エントリ分の整合性を検証する (validate_character_profilesの複雑度を
    下げるためのヘルパー、重複チェックは呼び出し側でまとめて行う)。"""
    if not profile.character_id:
        return [f"[{index}] characterIdが空です"]

    issues: list[str] = []

    if not CHARACTER_ID_PATTERN.match(profile.character_id):
        issues.append(
            f"characterId '{profile.character_id}': "
            "形式が不正です (CHAR_{ROMANIZED_NAME}形式である必要があります)"
        )

    if not profile.display_name:
        issues.append(f"characterId '{profile.character_id}': displayNameが空です")

    if profile.status not in VALID_STATUSES:
        issues.append(
            f"characterId '{profile.character_id}': "
            f"未知のstatus '{profile.status}' (許可値: {sorted(VALID_STATUSES)})"
        )

    if profile.height_cm is not None and not isinstance(profile.height_cm, int):
        issues.append(
            f"characterId '{profile.character_id}': heightCmは整数である必要があります"
        )

    issues.extend(_validate_birthday(profile))
    issues.extend(_validate_profile_highlight(profile))
    issues.extend(_validate_self_introduction(profile))

    return issues


def _validate_duplicates(profiles: list[CharacterProfile]) -> list[str]:
    issues: list[str] = []
    seen: dict[str, int] = {}
    for profile in profiles:
        if profile.character_id:
            seen[profile.character_id] = seen.get(profile.character_id, 0) + 1
    for character_id, count in seen.items():
        if count > 1:
            issues.append(f"characterId '{character_id}' が{count}件重複しています")
    return issues


def _validate_against_character_dictionary(
    profiles: list[CharacterProfile],
    character_dictionary: list[CharacterDictionaryEntry],
) -> list[str]:
    """characters.yaml (ID解決用辞書) との整合性を検証する。

    characterIdがcharacters.yamlに存在しない、またはstatus: confirmedで
    ない場合はエラーとする (Character_Profile_Dictionary_Design.md §4:
    プロフィールはconfirmed済みcharacterIdにのみ紐づけてよい)。
    """
    dict_by_character_id = {
        entry.character_id: entry
        for entry in character_dictionary
        if entry.character_id
    }
    issues: list[str] = []
    for profile in profiles:
        if not profile.character_id:
            continue
        entry = dict_by_character_id.get(profile.character_id)
        if entry is None:
            issues.append(
                f"characterId '{profile.character_id}': "
                "knowledge/dictionaries/characters.yamlに存在しません"
            )
        elif entry.status != "confirmed":
            issues.append(
                f"characterId '{profile.character_id}': "
                f"characters.yaml上でconfirmedではありません (status: {entry.status})"
            )
    return issues


def validate_character_profiles(
    profiles: list[CharacterProfile],
    character_dictionary: list[CharacterDictionaryEntry] | None = None,
) -> list[str]:
    """プロフィールエントリ一覧の整合性を検証する。

    戻り値: 問題を説明する人間可読な文字列のリスト（空なら問題無し）。
    `character_dictionary`を渡した場合のみ、characters.yamlとの整合性
    (confirmed済みcharacterIdへの紐づけ) も検証する。
    """
    issues: list[str] = []
    for i, profile in enumerate(profiles):
        issues.extend(_validate_single_profile(i, profile))
    issues.extend(_validate_duplicates(profiles))
    if character_dictionary is not None:
        issues.extend(
            _validate_against_character_dictionary(profiles, character_dictionary)
        )
    return issues


def build_character_profile_index(
    profiles: list[CharacterProfile],
) -> dict[str, CharacterProfile]:
    """characterId -> CharacterProfile の索引を組み立てる。"""
    return {
        profile.character_id: profile for profile in profiles if profile.character_id
    }


def get_character_profile(
    index: dict[str, CharacterProfile], character_id: str
) -> CharacterProfile | None:
    """索引から1件のプロフィールを取得する (存在しなければNone)。"""
    return index.get(character_id)
