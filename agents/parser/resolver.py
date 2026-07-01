"""
DKB Story Parser - Speaker Resolver
キャラクターID・話者スロット・強制話者名を解決する。

Phase 5 (Parser_Implementation_Plan.md)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ----------------------------------------------------------------
# Speaker データクラス
# ----------------------------------------------------------------

@dataclass
class Speaker:
    """解決済み話者情報"""

    speaker_id: str | None
    """解決済み Character ID (例: CHAR_RAIN)。未解決時は None"""

    speaker_name: str
    """表示用話者名"""

    source_character_id: str | None
    """元スクリプト上のキャラクター番号"""

    slot: str | None
    """スクリプト上の話者スロット"""

    is_resolved: bool
    """正規キャラクターへ解決できたか"""

    def to_dict(self) -> dict[str, Any]:
        return {
            "speakerId": self.speaker_id,
            "speakerName": self.speaker_name,
            "sourceCharacterId": self.source_character_id,
            "slot": self.slot,
            "isResolved": self.is_resolved,
        }

    @classmethod
    def unknown(cls, slot: str | None = None, source_character_id: str | None = None) -> "Speaker":
        """未解決話者を生成する"""
        if source_character_id:
            name = f"不明人物(ID:{source_character_id})"
        elif slot is not None:
            name = f"不明人物(ID:slot{slot})"
        else:
            name = "不明人物"
        return cls(
            speaker_id=None,
            speaker_name=name,
            source_character_id=source_character_id,
            slot=slot,
            is_resolved=False,
        )


# ----------------------------------------------------------------
# CharacterDictionary
# ----------------------------------------------------------------

class CharacterDictionary:
    """
    キャラクター辞書。

    入力:
        characters_reference.json 形式:
            {"1": "赤城陽菜", "26": "レイン", ...}

    将来的には knowledge/dictionaries/characters.yaml へ移行する。
    """

    def __init__(self) -> None:
        # sourceCharacterId (str) → speakerName (str)
        self._name_map: dict[str, str] = {}
        # sourceCharacterId (str) → speakerId (str) — DKB正規ID
        self._id_map: dict[str, str] = {}

    def load_from_json(self, path: str | Path) -> None:
        """characters_reference.json を読み込む"""
        p = Path(path)
        if not p.exists():
            return
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        for char_id, value in data.items():
            # value が文字列 (speakerName) または dict の場合に対応
            if isinstance(value, str):
                self._name_map[str(char_id)] = value
            elif isinstance(value, dict):
                self._name_map[str(char_id)] = value.get("name", f"ID:{char_id}")
                if "id" in value:
                    self._id_map[str(char_id)] = value["id"]

    def get_name(self, source_character_id: str) -> str | None:
        """キャラクター番号から表示名を取得する"""
        return self._name_map.get(str(source_character_id))

    def get_speaker_id(self, source_character_id: str) -> str | None:
        """キャラクター番号から DKB 正規 ID を取得する"""
        return self._id_map.get(str(source_character_id))

    def is_known(self, source_character_id: str) -> bool:
        return str(source_character_id) in self._name_map

    def all_ids(self) -> list[str]:
        return list(self._name_map.keys())

    def size(self) -> int:
        return len(self._name_map)


# ----------------------------------------------------------------
# SpeakerAssignment 記録
# ----------------------------------------------------------------

@dataclass
class SpeakerAssignmentRecord:
    """話者スロット割り当て記録 (Episode.speakerAssignments 用)"""

    slot: str
    source_character_id: str | None
    speaker_id: str | None
    speaker_name: str | None
    line_start: int | None
    line_end: int | None
    raw: str | None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"slot": self.slot}
        if self.source_character_id is not None:
            result["sourceCharacterId"] = self.source_character_id
        if self.speaker_id is not None:
            result["speakerId"] = self.speaker_id
        if self.speaker_name is not None:
            result["speakerName"] = self.speaker_name
        if self.line_start is not None or self.raw is not None:
            result["source"] = {
                "lineStart": self.line_start,
                "lineEnd": self.line_end,
                "raw": self.raw,
            }
        return result


# ----------------------------------------------------------------
# SpeakerResolver
# ----------------------------------------------------------------

class SpeakerResolver:
    """
    スクリプト内の話者割り当てを追跡し、スロット→話者を解決する。

    サポートする構文:
        $numX = character_id
        $valueX = character_id
        @ScenarioCos slot character_id
        @ScenarioCosLoad slot variable
        name 話者名
        @ChTalkName slot 話者名 path
    """

    def __init__(self, char_dict: CharacterDictionary | None = None) -> None:
        self.char_dict = char_dict or CharacterDictionary()

        # スロット → Speaker (slot: str)
        self._slot_map: dict[str, Speaker] = {}

        # 変数名 → source_character_id ($num1, $value0 など)
        self._variable_map: dict[str, str] = {}

        # $numX のインデックス上限 (ScenarioCosLoad で使用)
        self._max_num_index: int = -1

        # 強制話者名 (name コマンド)
        self._forced_name: str | None = None

        # 割り当て記録ログ
        self.assignment_records: list[SpeakerAssignmentRecord] = []

        # 未登録キャラクターID の記録
        self.unresolved_character_ids: set[str] = set()

    # ----------------------------------------------------------------
    # 割り当てメソッド
    # ----------------------------------------------------------------

    def assign_character(
        self,
        slot: str,
        source_character_id: str,
        line_start: int | None = None,
        raw: str | None = None,
    ) -> Speaker:
        """
        @ScenarioCos slot character_id に対応。
        スロットへキャラクターを直接割り当てる。
        """
        speaker = self._resolve_character_id(source_character_id, slot)
        self._slot_map[str(slot)] = speaker

        rec = SpeakerAssignmentRecord(
            slot=str(slot),
            source_character_id=source_character_id,
            speaker_id=speaker.speaker_id,
            speaker_name=speaker.speaker_name,
            line_start=line_start,
            line_end=line_start,
            raw=raw,
        )
        self.assignment_records.append(rec)
        return speaker

    def assign_variable(
        self,
        variable_name: str,
        source_character_id: str,
        num_index: int | None = None,
        value_index: int | None = None,
        line_start: int | None = None,
        raw: str | None = None,
    ) -> Speaker:
        """
        $numX = character_id / $valueX = character_id に対応。
        変数マップに記録し、スロットも自動割り当てする。
        """
        self._variable_map[variable_name] = source_character_id

        if num_index is not None:
            # $numX → スロット = X
            slot = str(num_index)
            if num_index > self._max_num_index:
                self._max_num_index = num_index
        elif value_index is not None:
            # $valueX → スロット = max_num_index + 1 + X
            slot = str(self._max_num_index + 1 + value_index)
        else:
            slot = variable_name  # フォールバック

        speaker = self._resolve_character_id(source_character_id, slot)
        self._slot_map[slot] = speaker

        rec = SpeakerAssignmentRecord(
            slot=slot,
            source_character_id=source_character_id,
            speaker_id=speaker.speaker_id,
            speaker_name=speaker.speaker_name,
            line_start=line_start,
            line_end=line_start,
            raw=raw,
        )
        self.assignment_records.append(rec)
        return speaker

    def assign_from_variable(
        self,
        slot: str,
        variable_name: str,
        line_start: int | None = None,
        raw: str | None = None,
    ) -> Speaker:
        """
        @ScenarioCosLoad slot variable に対応。
        変数マップからキャラクターIDを引き、スロットに割り当てる。
        """
        source_character_id = self._variable_map.get(variable_name)
        if source_character_id is None:
            # 変数未定義 → unknown speaker
            speaker = Speaker.unknown(slot=str(slot))
            self._slot_map[str(slot)] = speaker
        else:
            speaker = self._resolve_character_id(source_character_id, str(slot))
            self._slot_map[str(slot)] = speaker

        rec = SpeakerAssignmentRecord(
            slot=str(slot),
            source_character_id=source_character_id,
            speaker_id=speaker.speaker_id,
            speaker_name=speaker.speaker_name,
            line_start=line_start,
            line_end=line_start,
            raw=raw,
        )
        self.assignment_records.append(rec)
        return speaker

    def set_forced_name(self, name: str) -> None:
        """name コマンドによる強制話者名をセットする"""
        self._forced_name = name if name.strip() else None

    def consume_forced_name(self) -> str | None:
        """強制話者名を取得してリセットする"""
        name = self._forced_name
        self._forced_name = None
        return name

    # ----------------------------------------------------------------
    # 解決メソッド
    # ----------------------------------------------------------------

    def resolve_slot(self, slot: str) -> Speaker:
        """
        スロット番号から話者を解決する。
        スロットが未割り当ての場合は unknown speaker を返す。
        """
        return self._slot_map.get(str(slot), Speaker.unknown(slot=str(slot)))

    def resolve_from_command_name(self, speaker_name: str, slot: str | None = None) -> Speaker:
        """
        @ChTalkName コマンドから直接話者名を取得する場合。
        speakerId は null、isResolved は False とする。
        """
        return Speaker(
            speaker_id=None,
            speaker_name=speaker_name,
            source_character_id=None,
            slot=slot,
            is_resolved=False,
        )

    def has_forced_name(self) -> bool:
        return self._forced_name is not None

    # ----------------------------------------------------------------
    # 内部ヘルパー
    # ----------------------------------------------------------------

    def _resolve_character_id(self, source_character_id: str, slot: str | None = None) -> Speaker:
        """
        source_character_id から Speaker を生成する。
        辞書に存在すれば is_resolved=True、なければ False。
        """
        name = self.char_dict.get_name(source_character_id)
        speaker_id = self.char_dict.get_speaker_id(source_character_id)

        if name is not None:
            return Speaker(
                speaker_id=speaker_id,
                speaker_name=name,
                source_character_id=source_character_id,
                slot=slot,
                is_resolved=True,
            )
        else:
            # 未登録キャラクターID として記録
            self.unresolved_character_ids.add(source_character_id)
            return Speaker.unknown(slot=slot, source_character_id=source_character_id)

    # ----------------------------------------------------------------
    # 状態リセット (エピソード切り替え時など)
    # ----------------------------------------------------------------

    def reset(self) -> None:
        """話者割り当て状態をリセットする"""
        self._slot_map.clear()
        self._variable_map.clear()
        self._max_num_index = -1
        self._forced_name = None
        self.assignment_records.clear()

    # ----------------------------------------------------------------
    # デバッグ用
    # ----------------------------------------------------------------

    def current_assignments(self) -> dict[str, str]:
        """現在のスロット → 話者名マップを返す (デバッグ用)"""
        return {slot: sp.speaker_name for slot, sp in self._slot_map.items()}
