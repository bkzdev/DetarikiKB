"""
DKB - Character Profile Wiki Import
デタリキZ攻略Wikiのメンバー一覧テーブル (HTML) から、
knowledge/dictionaries/character_profiles.yaml へ投入可能な中間形式
(import candidate) を組み立てる純粋関数群。

**重要**:
- HTML取得・fetch自体は `scripts/import_character_profiles_from_wiki.py`
  (CLI) の責務。このモジュールはHTML文字列を受け取ってからの
  パース・変換・照合のみを行う (ネットワークアクセスを含まない)。
- characterIdは自動生成しない。confirmed済みcharacterIdへの
  displayName完全一致のみを自動matchとし、それ以外はunmatchedとして
  人間確認に回す (docs/runbooks/Character_Profile_Wiki_Import.md 参照)。
- 標準ライブラリ (html.parser) のみで実装し、新規依存は追加しない。
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from .character_dictionary import CharacterDictionaryEntry

# WIKI側の列見出し (表記ゆれを含む) -> character_profiles.yaml側のキーの対応。
# 「実装日」等、character_profiles.yamlに対応項目が無い列は意図的にマッピング
# しない (無視される)。
_HEADER_ALIASES: dict[str, str] = {
    "キャラ名": "displayName",
    "名前": "displayName",
    "キャラクター名": "displayName",
    "よみがな": "kana",
    "ふりがな": "kana",
    "所属": "affiliation",
    "身長(cm)": "heightCm",
    "身長": "heightCm",
    "誕生日": "birthday",
    "血液型": "bloodType",
    "特記事項": "profileHighlight",
    "CV": "cv",
}

# メンバー一覧テーブルとして認識するために必要な、認識済み列見出しの最小数。
# WIKIページ内の無関係なテーブル (ナビゲーション等) を誤検出しないための閾値。
_MIN_RECOGNIZED_HEADERS = 3

_HIGHLIGHT_LABEL_PATTERN = re.compile(
    r"^[【\[](?P<label>[^】\]]+)[】\]]\s*(?P<value>.*)$"
)
_BIRTHDAY_PATTERN = re.compile(r"^\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$")


class _TableHTMLParser(HTMLParser):
    """`<table>`要素を`list[list[str]]` (行×セルの生テキスト) へ変換する
    最小限のHTMLパーサー。ネストしたtableは正しく扱えない (シンプルな
    Wikiテーブルのみを対象とする既知の制約)。
    """

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._current_table: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._in_table = True
            self._current_table = []
        elif tag == "tr" and self._in_table:
            self._in_row = True
            self._current_row = []
        elif tag in ("td", "th") and self._in_row:
            self._in_cell = True
            self._current_cell_text = []
        elif tag == "br" and self._in_cell:
            self._current_cell_text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._in_table:
            self._in_table = False
            self.tables.append(self._current_table)
        elif tag == "tr" and self._in_row:
            self._in_row = False
            self._current_table.append(self._current_row)
        elif tag in ("td", "th") and self._in_cell:
            self._in_cell = False
            self._current_row.append("".join(self._current_cell_text).strip())

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell_text.append(data)


def extract_tables(html: str) -> list[list[list[str]]]:
    """HTML文字列から全`<table>`要素を`list[list[str]]`の一覧として返す。"""
    parser = _TableHTMLParser()
    parser.feed(html)
    return parser.tables


def normalize_header(raw_header: str) -> str | None:
    """WIKI側の列見出しを character_profiles.yaml側のキーへ変換する。
    対応が無い見出し (実装日等) はNoneを返す (その列は無視される)。
    """
    return _HEADER_ALIASES.get(raw_header.strip())


def find_member_table(tables: list[list[list[str]]]) -> list[list[str]] | None:
    """複数のtableの中から、メンバー一覧テーブルらしきものを1つ選ぶ。

    認識済み見出し (_HEADER_ALIASES) の一致数が最も多いtableを選び、
    最小一致数 (_MIN_RECOGNIZED_HEADERS) に満たない場合はNoneを返す
    (無関係なナビゲーションtable等の誤検出を避けるため)。
    """
    best_table: list[list[str]] | None = None
    best_score = 0
    for table in tables:
        if not table:
            continue
        header_row = table[0]
        score = sum(1 for h in header_row if normalize_header(h) is not None)
        if score > best_score:
            best_score = score
            best_table = table
    if best_score < _MIN_RECOGNIZED_HEADERS:
        return None
    return best_table


def rows_to_dicts(table: list[list[str]]) -> list[dict[str, str]]:
    """テーブル (先頭行=見出し) を、正規化済みキーの行dict一覧へ変換する。"""
    header_row = table[0]
    keys = [normalize_header(h) for h in header_row]
    rows: list[dict[str, str]] = []
    for raw_row in table[1:]:
        row_dict: dict[str, str] = {}
        for key, value in zip(keys, raw_row, strict=False):
            if key is not None:
                row_dict[key] = value
        rows.append(row_dict)
    return rows


def parse_height_cm(raw: str | None) -> int | None:
    """ "153"/"153cm"を153へ、空欄・不明はNoneへ変換する。"""
    if not raw:
        return None
    digits = re.sub(r"[^0-9]", "", raw)
    if not digits:
        return None
    return int(digits)


def parse_birthday(raw: str | None) -> dict[str, Any] | None:
    """ "4/23"/"04/23"を{month, day, display}へ変換する。不明・空欄・
    範囲外の値はNoneを返す。"""
    if not raw:
        return None
    match = _BIRTHDAY_PATTERN.match(raw)
    if not match:
        return None
    month, day = int(match.group(1)), int(match.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return {"month": month, "day": day, "display": raw.strip()}


def parse_profile_highlight(raw: str | None) -> dict[str, str] | None:
    """ "【好きなこと】値"を{label: "好きなこと", value: "値"}へ変換する。
    ラベル無し (括弧無し) の場合は label: "特記事項" として扱う。
    空欄・「特になし」等の実質空値も含め、値が空ならNoneを返す。
    """
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    match = _HIGHLIGHT_LABEL_PATTERN.match(text)
    if match and match.group("value").strip():
        return {
            "label": match.group("label").strip(),
            "value": match.group("value").strip(),
        }
    return {"label": "特記事項", "value": text}


def parse_reading(raw: str | None) -> dict[str, str | None] | None:
    """よみがな列を{kana, romaji}へ変換する。romajiは一覧テーブルには
    無いため常にNone。"""
    if not raw or not raw.strip():
        return None
    return {"kana": raw.strip(), "romaji": None}


def parse_affiliation(raw: str | None) -> list[str]:
    """所属列を文字列配列へ変換する (1件でも配列で保持する方針)。"""
    if not raw or not raw.strip():
        return []
    return [raw.strip()]


def _clean_optional_text(raw: str | None) -> str | None:
    if raw and raw.strip():
        return raw.strip()
    return None


def build_profile_from_row(row: dict[str, str], source_label: str) -> dict[str, Any]:
    """1行分のWIKIデータを、character_profiles.yamlのCharacterProfileに
    近い形のdictへ変換する。selfIntroductionは一覧テーブルに存在しない
    ため常にNone (個別ページからの取得は別タスク、
    docs/runbooks/Character_Profile_Wiki_Import.md 参照)。
    """
    return {
        "displayName": (row.get("displayName") or "").strip(),
        "reading": parse_reading(row.get("kana")),
        "affiliation": parse_affiliation(row.get("affiliation")),
        "heightCm": parse_height_cm(row.get("heightCm")),
        "birthday": parse_birthday(row.get("birthday")),
        "bloodType": _clean_optional_text(row.get("bloodType")),
        "cv": _clean_optional_text(row.get("cv")),
        "profileHighlight": parse_profile_highlight(row.get("profileHighlight")),
        "selfIntroduction": None,
        "source": {
            "sourceType": "wiki_member_table",
            "label": source_label,
            "referenceId": None,
            "notes": None,
        },
        "status": "draft",
        "notes": "Imported candidate. Needs human review.",
    }


def match_candidates(
    rows: list[dict[str, str]],
    character_dictionary: list[CharacterDictionaryEntry],
    source_label: str,
) -> list[dict[str, Any]]:
    """WIKI行一覧を、characters.yamlのconfirmed済みcharacterIdとdisplayName
    完全一致でmatchし、import candidateの一覧を組み立てる。

    - confirmed済みのcharacterIdにのみ候補を紐づける (name_only/unknown
      なentityとは絶対にmatchさせない)
    - displayNameの完全一致のみを自動matchとする (表記ゆれ・空白差分・
      旧字体差分等はunmatchedとして人間確認に回す)
    - characterIdは自動生成しない
    """
    confirmed_by_name = {
        entry.display_name: entry
        for entry in character_dictionary
        if entry.status == "confirmed" and entry.character_id
    }

    candidates: list[dict[str, Any]] = []
    for row in rows:
        display_name = (row.get("displayName") or "").strip()
        if not display_name:
            continue

        entry = confirmed_by_name.get(display_name)
        if entry is not None:
            candidates.append(
                {
                    "matchStatus": "matched",
                    "characterId": entry.character_id,
                    "sourceDisplayName": display_name,
                    "profile": build_profile_from_row(row, source_label),
                }
            )
        else:
            candidates.append(
                {
                    "matchStatus": "unmatched",
                    "characterId": None,
                    "sourceDisplayName": display_name,
                    "reason": "No confirmed characterId matched by exact displayName.",
                }
            )
    return candidates


def build_candidate_document(
    candidates: list[dict[str, Any]],
    source_url: str | None,
    fetched_at: str,
) -> dict[str, Any]:
    """import candidateの一覧を、書き出し用のdocument dictへ組み立てる。"""
    return {
        "schemaVersion": "0.1.0",
        "documentType": "character_profile_import_candidates",
        "source": {
            "sourceType": "wiki_member_table",
            "sourceUrl": source_url,
            "fetchedAt": fetched_at,
        },
        "candidates": candidates,
    }
