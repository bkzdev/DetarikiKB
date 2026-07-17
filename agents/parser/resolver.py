"""
DKB Story Parser - Speaker Resolver
キャラクターID・話者スロット・強制話者名を解決する。

Phase 5 (Parser_Implementation_Plan.md)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .speaker_labels import SpeakerLabelAnalysis

# sourceCharacterIdとして妥当な「ID形式」(数字のみ) の正規表現。
# knowledge/dictionaries/characters.yamlの全confirmedエントリのsourceCharacterId
# が数字のみの文字列であることを前提とする
# (Character_Story_ID_Manifest_Design.md §9.1.2発見③の根本原因調査で確認)。
_CHARACTER_ID_FORMAT = re.compile(r"^\d+$")


def _is_literal_character_id(value: str) -> bool:
    """sourceCharacterIdがID形式 (数字のみ) かどうかを判定する。

    tokenizer.pyのVARIABLE_PATTERN ($numX=/$valueX=) はRHS全体を`\\S+`として
    緩く捕捉する (カメラ座標等の$valueX代入をそのまま保持するための意図的な
    設計。スロット自動バインド挙動自体の変更は本関数のスコープ外、Backlog
    「parser-auto-bind-non-speaker-slot-review」参照)。このため、
    `$num1 = $split(0,$value11)`のような未評価の関数呼び出し式や、
    `$value0 = 11.2,-7.7,-24`のような座標様の数値列(カンマ区切り)が、
    そのままsource_character_idへ渡ってくることがある。
    これらはID形式ではないため未登録キャラクターID候補として扱わない
    (`_resolve_character_id`参照)。
    """
    return bool(_CHARACTER_ID_FORMAT.match(value))


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

    label_source: str | None = None
    """speakerNameの由来 (例: "name_command"/"ch_talk_name")。
    キャラクターID経由で解決した場合はNoneのまま
    (agents/parser/speaker_labels.py SOURCE_NAME_COMMAND等)。"""

    label_analysis: "SpeakerLabelAnalysis | None" = None
    """label_sourceがある場合の構造化結果 (speaker_labels.analyze_speaker_label)。
    speaker_group/speaker_with_modifier/generic_speaker等の判定・
    inferredSpeakersを保持する。"""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "speakerId": self.speaker_id,
            "speakerName": self.speaker_name,
            "sourceCharacterId": self.source_character_id,
            "slot": self.slot,
            "isResolved": self.is_resolved,
        }
        if self.label_source is not None:
            result["labelSource"] = self.label_source
        if self.label_analysis is not None:
            result["labelAnalysis"] = self.label_analysis.to_dict()
        return result

    @classmethod
    def unknown(
        cls, slot: str | None = None, source_character_id: str | None = None
    ) -> "Speaker":
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
        characters_reference.json 形式 (読み取り専用のレガシー参照辞書、
        表示名のみ。CLAUDE.md記載の通りこのファイル自体は直接改造しない):
            {"1": "赤城陽菜", "26": "レイン", ...}

        knowledge/dictionaries/characters.yaml 形式 (人手管理の正規辞書、
        characterId <-> sourceCharacterId の対応も持てる。
        `load_from_dictionary_yaml`/`load` 経由で読み込む):
            characters:
              - sourceCharacterId: "26"
                characterId: "CHAR_RAIN"
                displayName: "レイン"
                aliases: []
                status: "confirmed"
    """

    def __init__(self) -> None:
        # sourceCharacterId (str) → speakerName (str)
        self._name_map: dict[str, str] = {}
        # sourceCharacterId (str) → speakerId (str) — DKB正規ID
        self._id_map: dict[str, str] = {}
        # displayName/alias (str) → characterId (str) — confirmedエントリのみ。
        # speaker_labels.attach_inferred_speakersの参考情報生成にのみ使う
        # (通常の自動話者解決には一切使わない、character_dictionary.py
        # resolve_character_by_nameと同じ注意事項)。
        self._confirmed_name_to_id: dict[str, str] = {}
        # displayName/alias (str) の集合 — status不問 (confirmed/name_only)。
        # confirmed一致が無い場合の低confidence候補判定にのみ使う。
        self._known_names: set[str] = set()

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

    def load_from_dictionary_yaml(self, path: str | Path) -> None:
        """knowledge/dictionaries/characters.yaml 相当の人手管理辞書を
        読み込む (agents/parser/character_dictionary.py 参照)。

        displayNameがあれば常に_name_mapへ、characterId (canonical ID)
        が設定されているエントリのみ_id_mapへ反映する。名前一致による
        自動解決は行わない (load_character_dictionaryの制約と同じ)。
        """
        from .character_dictionary import load_character_dictionary

        for entry in load_character_dictionary(path):
            if entry.display_name:
                self._name_map[entry.source_character_id] = entry.display_name
                self._known_names.add(entry.display_name)
            if entry.character_id:
                self._id_map[entry.source_character_id] = entry.character_id
                if entry.display_name:
                    self._confirmed_name_to_id[entry.display_name] = entry.character_id
                for alias in entry.aliases:
                    self._confirmed_name_to_id.setdefault(alias, entry.character_id)
            for alias in entry.aliases:
                self._known_names.add(alias)

    def load(self, path: str | Path) -> None:
        """拡張子からフォーマットを判定して読み込む
        (.yaml/.yml → load_from_dictionary_yaml、それ以外 → load_from_json)。
        """
        p = Path(path)
        if p.suffix.lower() in (".yaml", ".yml"):
            self.load_from_dictionary_yaml(p)
        else:
            self.load_from_json(p)

    def get_name(self, source_character_id: str) -> str | None:
        """キャラクター番号から表示名を取得する"""
        return self._name_map.get(str(source_character_id))

    def get_speaker_id(self, source_character_id: str) -> str | None:
        """キャラクター番号から DKB 正規 ID を取得する"""
        return self._id_map.get(str(source_character_id))

    def is_known(self, source_character_id: str) -> bool:
        return str(source_character_id) in self._name_map

    def find_confirmed_id_by_name(self, name: str) -> str | None:
        """displayName/aliasの完全一致から、confirmedエントリのcharacterId
        を返す (name_onlyエントリはNone)。

        **警告**: 名前一致のみによる解決であり、同名の別人が存在しうる
        ため、この結果を自動的にresolved/confirmed話者として扱っては
        ならない。speaker_labels.attach_inferred_speakersの参考情報
        生成にのみ使うこと (character_dictionary.py
        resolve_character_by_nameと同じ注意事項)。
        """
        return self._confirmed_name_to_id.get(name)

    def has_known_name(self, name: str) -> bool:
        """displayName/aliasとして辞書に登録済みか (status不問)。"""
        return name in self._known_names

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

        # 未登録キャラクターID の消費文脈シグナル (feature/resolver-consumption-
        # context-report、scripts/check_script_compatibility.pyの#141
        # (_simulate_id_consumption/_classify_and_record_character_ids)と
        # 対称化)。sourceCharacterId (str) -> {"speaker": bool, "hasOccurrence": bool}。
        # - hasOccurrence: $numX/$valueX代入または@ScenarioCos直接指定のように、
        #   代入行から直接IDを取得できる形で記録されたか
        #   (checker側のoccurrencesに相当)。
        # - speaker: 話者スロットとして実際に消費 (@ChTalk系コマンドからの
        #   resolve_slot呼び出しで解決、または@ScenarioCos直接指定/
        #   @ScenarioCosLoad/@ScenarioCos変数経由のように代入コマンド自体が
        #   話者スロット専用の意味を持つ場合は即時) されたか。
        # 最終的な分類 (unresolved_character_ids / non_speaker_numeric_
        # assignment_ids) は hasOccurrence かつ speaker の有無で決まる
        # (hasOccurrence=Falseのものはchecker側と同様どちらのバケットにも
        # 含めない)。スロット自動バインド挙動・resolve_slot/assign_*が返す
        # Speakerの内容自体はこのシグナル記録によって一切変化しない。
        self._unresolved_char_id_signals: dict[str, dict[str, bool]] = {}

        # 非ID形式 (非リテラル) のsourceCharacterId文字列の消費文脈シグナル
        # (feature/non-literal-character-id-handling、
        # Character_Story_ID_Manifest_Design.md §9.1.2発見③の解消)。
        # `_unresolved_char_id_signals`と同じ{speaker, hasOccurrence}構造だが、
        # `_is_literal_character_id`がFalseを返す値 (関数呼び出し式・座標様
        # 数値列等) はこちらへ分離して記録する。不破棄不変則により削除は
        # せず、compatibilityReport.nonLiteralSpeakerExpressions
        # (unknownCharacterIds/nonSpeakerNumericAssignmentsとは別の情報
        # フィールド) として保持する。
        self._non_literal_speaker_expression_signals: dict[str, dict[str, bool]] = {}

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

        checker側`_apply_scenario_cos`のdirect-id分岐と同じ意味論:
        @ScenarioCosによる直接キャラクターID指定はそれ自体が話者スロット
        束縛を意味するため、hasOccurrence/speakerともに即時Trueとして
        記録する。
        """
        speaker = self._resolve_character_id(
            source_character_id, slot, has_occurrence=True, immediate_speaker=True
        )
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

        checker側`_apply_num_var_assignment`/`_apply_value_var_assignment`と
        同じ意味論: $numX/$valueX代入は「代入行からIDを直接取得できる」
        (hasOccurrence=True) が、話者スロットとして消費されるかどうかは
        未確定 (immediate_speaker=False、後続の実際の@ChTalk系コマンドに
        よるresolve_slot呼び出しでのみspeaker=Trueとなる)。
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

        speaker = self._resolve_character_id(
            source_character_id, slot, has_occurrence=True, immediate_speaker=False
        )
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

        checker側`_apply_scenario_cos_load`/`_apply_scenario_cos`の変数経由
        分岐と同じ意味論: @ScenarioCosLoad (および@ScenarioCosの変数経由
        呼び出し、agents/parser/parser.py参照) は変数から間接的にIDを
        解決するため「代入行から直接IDを取得できる」形ではない
        (hasOccurrence=False、checker側コメント「char_id直接取得不可の
        ためoccurrencesには追加しない」と同じ)。ただし、このコマンド自体は
        話者スロット束縛を意味するためspeakerは即時True
        (解決できた場合のみ。変数未定義でsource_character_idがNoneの
        場合はシグナル自体を記録しない)。
        """
        source_character_id = self._variable_map.get(variable_name)
        if source_character_id is None:
            # 変数未定義 → unknown speaker
            speaker = Speaker.unknown(slot=str(slot))
            self._slot_map[str(slot)] = speaker
        else:
            speaker = self._resolve_character_id(
                source_character_id,
                str(slot),
                has_occurrence=False,
                immediate_speaker=True,
            )
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

    def assign_costume_character(
        self,
        slot: str,
        second_arg: str,
        line_start: int | None = None,
        raw: str | None = None,
    ) -> Speaker | None:
        """
        `ch N` (表示スロットN指定の裸コマンド) 直後の
        `costume <衣装ID> <キャラID> [ON]` に対応する、スロットNの
        再束縛 (feature/costume-slot-binding-fix)。

        実データパターン: `$numX = <キャラID>`・`$numY = <衣装ID>`等の
        代入後、`ch N`→直後の`costume $numY $numX [ON]`（第1引数=衣装ID・
        **第2引数=キャラID**）でスロットNのキャラクターが決まる。呼び出し元
        (agents/parser/parser.py) は`ch N`出現時のNを覚えておき、その直後
        (間に別の`ch`が現れるまでの範囲) に出現する`costume`の第2引数
        (second_arg) をこのメソッドへ渡す。

        `@ScenarioCos`と同等の意味論のスロット再束縛として扱う:
        second_argが`$`始まりの変数なら`assign_from_variable`と同じ
        (has_occurrence=False、変数解決できた場合のみimmediate_speaker=True)、
        数字のみのリテラルなら`assign_character`と同じ
        (has_occurrence=True、immediate_speaker=True)。

        second_argが未定義変数、または数値でも$変数でもない場合は
        一切束縛を行わず (既存の`$numX`自動バインド等によるスロット状態を
        変更せず) Noneを返す。「不明情報を破棄しない」不変則により、
        解決できない`costume`引数によって既存の正しいスロット束縛を
        破壊してはならないため。
        """
        if second_arg.startswith("$"):
            resolved = self._variable_map.get(second_arg)
            if resolved is None:
                return None
            speaker = self._resolve_character_id(
                resolved, slot, has_occurrence=False, immediate_speaker=True
            )
        elif _is_literal_character_id(second_arg):
            resolved = second_arg
            speaker = self._resolve_character_id(
                resolved, slot, has_occurrence=True, immediate_speaker=True
            )
        else:
            return None

        self._slot_map[str(slot)] = speaker

        rec = SpeakerAssignmentRecord(
            slot=str(slot),
            source_character_id=resolved,
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

        agents/parser/parser.pyでは@ChTalk系の会話コマンド文脈からのみ
        呼ばれる (話者スロットとしての消費)。返すSpeakerの内容自体は
        変更しないが、未登録source_character_idについては消費文脈シグナル
        のspeakerフラグをTrueへ更新する (checker側
        `_apply_speech_command_consumption`と同じ意味論)。
        """
        speaker = self._slot_map.get(str(slot), Speaker.unknown(slot=str(slot)))
        if not speaker.is_resolved and speaker.source_character_id is not None:
            signals = (
                self._unresolved_char_id_signals
                if _is_literal_character_id(speaker.source_character_id)
                else self._non_literal_speaker_expression_signals
            )
            sig = signals.setdefault(
                speaker.source_character_id,
                {"speaker": False, "hasOccurrence": False},
            )
            sig["speaker"] = True
        return speaker

    def resolve_from_command_name(
        self,
        speaker_name: str,
        slot: str | None = None,
        label_source: str | None = None,
        label_analysis: "SpeakerLabelAnalysis | None" = None,
    ) -> Speaker:
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
            label_source=label_source,
            label_analysis=label_analysis,
        )

    def has_forced_name(self) -> bool:
        return self._forced_name is not None

    # ----------------------------------------------------------------
    # 内部ヘルパー
    # ----------------------------------------------------------------

    def _resolve_character_id(
        self,
        source_character_id: str,
        slot: str | None = None,
        *,
        has_occurrence: bool = True,
        immediate_speaker: bool = False,
    ) -> Speaker:
        """
        source_character_id から Speaker を生成する。
        辞書に存在すれば is_resolved=True、なければ False。

        未登録の場合は即座に`unresolved_character_ids`へ記録するのではなく、
        消費文脈シグナル (`_unresolved_char_id_signals`) のみを更新する
        (feature/resolver-consumption-context-report)。最終的な分類
        (話者として実消費されたか) は`unresolved_character_ids`/
        `non_speaker_numeric_assignment_ids`プロパティで判定時に導出する。
        has_occurrence/immediate_speakerの意味は呼び出し元
        (assign_character/assign_variable/assign_from_variable) の
        docstringおよびクラス冒頭の`_unresolved_char_id_signals`コメント
        を参照。
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
            # 未登録キャラクターID: 消費文脈シグナルを更新する。
            # ID形式 (数字のみ) でない値 ($split(...)等の未評価式・座標様
            # 数値列) は、未登録キャラクターID候補ではないため別バケットへ
            # 分離する (§9.1.2発見③、_is_literal_character_id参照)。
            signals = (
                self._unresolved_char_id_signals
                if _is_literal_character_id(source_character_id)
                else self._non_literal_speaker_expression_signals
            )
            sig = signals.setdefault(
                source_character_id, {"speaker": False, "hasOccurrence": False}
            )
            if has_occurrence:
                sig["hasOccurrence"] = True
            if immediate_speaker:
                sig["speaker"] = True
            return Speaker.unknown(slot=slot, source_character_id=source_character_id)

    # ----------------------------------------------------------------
    # 未登録キャラクターID の分類 (消費文脈ベース)
    # ----------------------------------------------------------------

    @property
    def unresolved_character_ids(self) -> set[str]:
        """話者スロットとして実際に消費された未登録キャラクターID。

        scripts/check_script_compatibility.pyの#141
        (`_classify_and_record_character_ids`) が`unknown_character_ids`
        (話者消費あり) へ分類する条件 (occurrencesあり かつ speaker=True)
        と同じ意味論。agents/parser/normalizer.pyが
        compatibilityReport.unknownCharacterIdsを組み立てる際に参照する
        (feature/resolver-consumption-context-report)。
        """
        return {
            cid
            for cid, sig in self._unresolved_char_id_signals.items()
            if sig["hasOccurrence"] and sig["speaker"]
        }

    @property
    def non_speaker_numeric_assignment_ids(self) -> set[str]:
        """話者スロットとして一度も消費されなかった未登録の数値代入。

        scripts/check_script_compatibility.pyの#141が
        `non_speaker_numeric_assignments` (話者消費なし) へ分類する条件
        (occurrencesあり かつ speaker=False) と同じ意味論。costume/mo/fa等の
        非話者引数専用消費・完全未消費のいずれも含む。「不明情報を破棄
        しない」不変則 (AI_CONTEXT.md §3.2) により削除はせず、判定への
        影響を持たない情報保持用フィールドとして残す。
        """
        return {
            cid
            for cid, sig in self._unresolved_char_id_signals.items()
            if sig["hasOccurrence"] and not sig["speaker"]
        }

    @property
    def non_literal_speaker_expressions(self) -> dict[str, bool]:
        """ID形式 (数字のみ) でないsourceCharacterId文字列
        (`$split(...)`等の未評価の関数呼び出し式・座標様の数値列等)。

        `unresolved_character_ids`/`non_speaker_numeric_assignment_ids`とは
        独立した軸 (「ID形式かどうか」) での分類であり、これらの値は
        未登録キャラクターID候補として`compatibilityReport.
        unknownCharacterIds`/`nonSpeakerNumericAssignments`へは計上しない
        (Character_Story_ID_Manifest_Design.md §9.1.2発見③)。
        「不明情報を破棄しない」不変則により削除はせず、
        `compatibilityReport.nonLiteralSpeakerExpressions`として保持する。
        戻り値: sourceCharacterId文字列 -> 話者スロットとして実際に消費
        されたか (True/False)。代入行から直接値を取得できなかった
        (hasOccurrence=False) ものはchecker側の`occurrences`空判定と同様
        対象外とする。
        """
        return {
            cid: sig["speaker"]
            for cid, sig in self._non_literal_speaker_expression_signals.items()
            if sig["hasOccurrence"]
        }

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
