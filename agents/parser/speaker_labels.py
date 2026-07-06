"""
DKB Parser - Speaker Label Analysis
`name` コマンド / `@ChTalkName` 由来のspeaker labelを構造化する。

キャラクターID (sourceCharacterId) 由来の話者とは異なり、これらは
スクリプト上に表示名として直接書かれたラベル文字列である。「セイナ＆イヴ」
のようなspeaker group、「紬（小声）」のようなmodifier付き表記、「？？？」
のようなgeneric/ambiguousな表記が混在するため、通常のunresolved character
としては扱わず、この構造化情報を経由してWiki側で別枠表示できるようにする。

**自動でconfirmed character解決はしない**。`attach_inferred_speakers`が
`characters.yaml`のconfirmed/name_onlyエントリと名前が一致するかを見るのは、
あくまで参考情報 (`inferredSpeakers`) を added するだけであり、
`resolutionStatus`は常に`not_applicable`/`needs_review`/`inferred`のいずれか
に留める (`confirmed`は将来の人間レビュー結果取り込み用として予約するのみ)。

docs/architecture/06_AI/Extraction_Result_Schema.md (Speaker Label Normalization設計)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .resolver import CharacterDictionary

# ----------------------------------------------------------------
# 定数
# ----------------------------------------------------------------

SOURCE_NAME_COMMAND = "name_command"
"""`name` キーワードによる強制話者名由来"""

SOURCE_CH_TALK_NAME = "ch_talk_name"
"""`@ChTalkName` コマンド引数由来"""

_SOURCE_UNSPECIFIED = "unspecified"
"""classify_speaker_labelの内部呼び出し専用 (sourceを問わない分類確認用)"""

LABEL_TYPE_SINGLE_SPEAKER = "single_speaker"
LABEL_TYPE_SPEAKER_GROUP = "speaker_group"
LABEL_TYPE_SPEAKER_WITH_MODIFIER = "speaker_with_modifier"
LABEL_TYPE_SPEAKER_GROUP_WITH_MODIFIER = "speaker_group_with_modifier"
LABEL_TYPE_GENERIC_SPEAKER = "generic_speaker"
LABEL_TYPE_AMBIGUOUS_SPEAKER = "ambiguous_speaker"
LABEL_TYPE_UNKNOWN = "unknown"

# 通常の単独キャラクター名 (single_speaker) は「特殊」扱いしない。それ以外は
# 通常のCharacterCandidateとは別枠 (special speaker label) として扱う対象。
# unknown (空ラベル等、実運用ではほぼ発生しない) も安全側に倒し特殊枠へ含める
# (不明情報を破棄しない方針、AI_CONTEXT.md §13.3)。
SPECIAL_LABEL_TYPES = frozenset(
    {
        LABEL_TYPE_SPEAKER_GROUP,
        LABEL_TYPE_SPEAKER_WITH_MODIFIER,
        LABEL_TYPE_SPEAKER_GROUP_WITH_MODIFIER,
        LABEL_TYPE_GENERIC_SPEAKER,
        LABEL_TYPE_AMBIGUOUS_SPEAKER,
        LABEL_TYPE_UNKNOWN,
    }
)

RESOLUTION_STATUS_NOT_APPLICABLE = "not_applicable"
RESOLUTION_STATUS_NEEDS_REVIEW = "needs_review"
RESOLUTION_STATUS_INFERRED = "inferred"
RESOLUTION_STATUS_CONFIRMED = "confirmed"
"""将来、人間レビュー結果を取り込む場合のために予約するのみ。
このモジュールが自動でこの値を設定することはない。"""

_LABEL_TYPE_RESOLUTION_STATUS: dict[str, str] = {
    LABEL_TYPE_SINGLE_SPEAKER: RESOLUTION_STATUS_NOT_APPLICABLE,
    LABEL_TYPE_SPEAKER_GROUP: RESOLUTION_STATUS_INFERRED,
    LABEL_TYPE_SPEAKER_WITH_MODIFIER: RESOLUTION_STATUS_INFERRED,
    LABEL_TYPE_SPEAKER_GROUP_WITH_MODIFIER: RESOLUTION_STATUS_INFERRED,
    LABEL_TYPE_GENERIC_SPEAKER: RESOLUTION_STATUS_NEEDS_REVIEW,
    LABEL_TYPE_AMBIGUOUS_SPEAKER: RESOLUTION_STATUS_NEEDS_REVIEW,
    LABEL_TYPE_UNKNOWN: RESOLUTION_STATUS_NEEDS_REVIEW,
}

# 明確な区切り記号のみをspeaker group判定に使う。「・」は人名の一部
# (表記上のミドルネーム的区切り等) にも使われるため、誤検出しやすく
# 意図的に外している (ambiguous_speaker側で別途拾う)。
GROUP_DELIMITERS: tuple[str, ...] = ("＆", "&", "／", "/", "、")

# 「・」区切りは人名の一部との衝突が多く確信を持てないため、speaker_groupには
# 昇格させず、ambiguous_speakerとしてreview-needed扱いに留める
# (manual visual review 002で観測された「イヴ・セイナ」のケース)。
AMBIGUOUS_DELIMITER = "・"

# 発話演出modifier等、末尾の括弧書きを抽出する。全角/半角どちらの括弧も
# 対象とする。
_MODIFIER_PATTERN = re.compile(r"^(?P<base>.*?)[（(](?P<modifier>[^（）()]+)[）)]$")

# 特定の名前ではなく、演出上の一時的な話者表記であることが明らかなラベル。
# 単独名としては扱わず、review-needed (generic_speaker) とする。
GENERIC_SPEAKER_LABELS = frozenset(
    {
        "？？？",
        "???",
        "謎の声",
        "一同",
        "全員",
        "女性",
        "男性",
        "少女",
        "声",
    }
)

MATCH_STATUS_DICTIONARY_CONFIRMED = "dictionary_confirmed"
MATCH_STATUS_DICTIONARY_NAME_ONLY = "dictionary_name_only"

CONFIDENCE_HIGH = "high"
CONFIDENCE_LOW = "low"


# ----------------------------------------------------------------
# SpeakerLabelAnalysis
# ----------------------------------------------------------------


@dataclass
class SpeakerLabelAnalysis:
    """1件のspeaker labelを構造化した結果。"""

    raw_label: str
    source: str
    label_type: str
    components: list[str] = field(default_factory=list)
    modifier: str | None = None
    base_label: str | None = None
    resolution_status: str = RESOLUTION_STATUS_NOT_APPLICABLE
    inferred_speakers: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rawLabel": self.raw_label,
            "source": self.source,
            "labelType": self.label_type,
            "components": list(self.components),
            "modifier": self.modifier,
            "baseLabel": self.base_label,
            "inferredSpeakers": [dict(s) for s in self.inferred_speakers],
            "resolutionStatus": self.resolution_status,
        }

    @property
    def is_special(self) -> bool:
        return self.label_type in SPECIAL_LABEL_TYPES


# ----------------------------------------------------------------
# 構造化ヘルパー
# ----------------------------------------------------------------


def extract_trailing_modifier(label: str) -> tuple[str, str | None]:
    """末尾の括弧書きをmodifier候補として抽出する。

    「紬（小声）」→ ("紬", "小声")。括弧の中身が空、またはbase部分が空に
    なる場合 (例: "（小声）"単体) はmodifier無しとして扱う。
    """
    stripped = label.strip()
    match = _MODIFIER_PATTERN.match(stripped)
    if not match:
        return stripped, None
    base = match.group("base").strip()
    modifier = match.group("modifier").strip()
    if not base or not modifier:
        return stripped, None
    return base, modifier


def split_speaker_group(label: str) -> list[str]:
    """明確な区切り記号 (＆/&/／//、) でspeaker groupを分割する。

    2件以上の非空要素に分割できた場合のみ結果を返す。「・」はここでは
    扱わない (誤検出しやすいため、ambiguous_speaker側の判定に譲る)。
    """
    for delimiter in GROUP_DELIMITERS:
        if delimiter in label:
            parts = [part.strip() for part in label.split(delimiter) if part.strip()]
            if len(parts) >= 2:
                return parts
    return []


def _split_ambiguous_group(label: str) -> list[str]:
    """「・」区切りのgroup候補を分割する (ambiguous_speaker用、内部ヘルパー)。"""
    if AMBIGUOUS_DELIMITER in label:
        parts = [
            part.strip() for part in label.split(AMBIGUOUS_DELIMITER) if part.strip()
        ]
        if len(parts) >= 2:
            return parts
    return []


def classify_speaker_label(label: str) -> str:
    """ラベル文字列単体からlabelTypeのみを判定する (source情報を持たない
    簡易呼び出し用。sourceが必要な場合はanalyze_speaker_labelを使う)。"""
    return analyze_speaker_label(label, source=_SOURCE_UNSPECIFIED).label_type


def analyze_speaker_label(raw_label: str, source: str) -> SpeakerLabelAnalysis:
    """speaker labelを構造化する。

    判定順序:
      1. 空文字列 → unknown
      2. 末尾modifierの抽出
      3. modifier除去後のbaseがgeneric/ambiguousな固定表記 → generic_speaker
      4. 明確な区切り記号での分割に成功 → speaker_group
         (modifierがあればspeaker_group_with_modifier)
      5. 「・」区切りでの分割に成功 → ambiguous_speaker (review-needed)
      6. modifierのみ残る → speaker_with_modifier
      7. それ以外 → single_speaker (通常の単独キャラクター名、特殊扱いしない)
    """
    label = (raw_label or "").strip()
    if not label:
        return SpeakerLabelAnalysis(
            raw_label=raw_label,
            source=source,
            label_type=LABEL_TYPE_UNKNOWN,
            resolution_status=_LABEL_TYPE_RESOLUTION_STATUS[LABEL_TYPE_UNKNOWN],
        )

    base, modifier = extract_trailing_modifier(label)
    if not base:
        return SpeakerLabelAnalysis(
            raw_label=raw_label,
            source=source,
            label_type=LABEL_TYPE_UNKNOWN,
            modifier=modifier,
            resolution_status=_LABEL_TYPE_RESOLUTION_STATUS[LABEL_TYPE_UNKNOWN],
        )

    if base in GENERIC_SPEAKER_LABELS:
        return SpeakerLabelAnalysis(
            raw_label=raw_label,
            source=source,
            label_type=LABEL_TYPE_GENERIC_SPEAKER,
            modifier=modifier,
            resolution_status=_LABEL_TYPE_RESOLUTION_STATUS[LABEL_TYPE_GENERIC_SPEAKER],
        )

    group_components = split_speaker_group(base)
    if group_components:
        label_type = (
            LABEL_TYPE_SPEAKER_GROUP_WITH_MODIFIER
            if modifier
            else LABEL_TYPE_SPEAKER_GROUP
        )
        return SpeakerLabelAnalysis(
            raw_label=raw_label,
            source=source,
            label_type=label_type,
            components=group_components,
            modifier=modifier,
            resolution_status=_LABEL_TYPE_RESOLUTION_STATUS[label_type],
        )

    ambiguous_components = _split_ambiguous_group(base)
    if ambiguous_components:
        return SpeakerLabelAnalysis(
            raw_label=raw_label,
            source=source,
            label_type=LABEL_TYPE_AMBIGUOUS_SPEAKER,
            components=ambiguous_components,
            modifier=modifier,
            resolution_status=_LABEL_TYPE_RESOLUTION_STATUS[
                LABEL_TYPE_AMBIGUOUS_SPEAKER
            ],
        )

    if modifier:
        return SpeakerLabelAnalysis(
            raw_label=raw_label,
            source=source,
            label_type=LABEL_TYPE_SPEAKER_WITH_MODIFIER,
            components=[base],
            modifier=modifier,
            base_label=base,
            resolution_status=_LABEL_TYPE_RESOLUTION_STATUS[
                LABEL_TYPE_SPEAKER_WITH_MODIFIER
            ],
        )

    return SpeakerLabelAnalysis(
        raw_label=raw_label,
        source=source,
        label_type=LABEL_TYPE_SINGLE_SPEAKER,
        components=[base],
        resolution_status=_LABEL_TYPE_RESOLUTION_STATUS[LABEL_TYPE_SINGLE_SPEAKER],
    )


def is_special_label_type(label_type: str) -> bool:
    """通常のCharacterCandidateとは別枠で扱うべきlabelTypeかどうか。"""
    return label_type in SPECIAL_LABEL_TYPES


def attach_inferred_speakers(
    analysis: SpeakerLabelAnalysis, char_dict: CharacterDictionary | None
) -> None:
    """`analysis.components`をconfirmed character dictionaryと突き合わせ、
    `inferredSpeakers`を埋める (副作用でanalysisを更新する)。

    **自動でconfirmed character解決はしない。** ここで付与するのは
    あくまで参考情報であり、`analysis.resolution_status`は変更しない
    (常にinferred/needs_review/not_applicableのまま)。confirmed dictionary
    に一致すればcharacterId付きの高confidence候補、name_only登録のみに
    一致すればcharacterId無し・低confidenceの候補として記録する。
    """
    if char_dict is None or not analysis.components:
        return

    inferred: list[dict[str, Any]] = []
    for name in analysis.components:
        character_id = char_dict.find_confirmed_id_by_name(name)
        if character_id:
            inferred.append(
                {
                    "matchedName": name,
                    "characterId": character_id,
                    "matchStatus": MATCH_STATUS_DICTIONARY_CONFIRMED,
                    "confidence": CONFIDENCE_HIGH,
                }
            )
        elif char_dict.has_known_name(name):
            inferred.append(
                {
                    "matchedName": name,
                    "characterId": None,
                    "matchStatus": MATCH_STATUS_DICTIONARY_NAME_ONLY,
                    "confidence": CONFIDENCE_LOW,
                }
            )
    analysis.inferred_speakers = inferred
