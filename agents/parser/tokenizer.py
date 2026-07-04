"""
DKB Story Parser - Tokenizer
Raw Script を行単位・コマンド単位の Token へ分解する。

Phase 4 (Parser_Implementation_Plan.md)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# ----------------------------------------------------------------
# 制御文字パターン (U+0000-U+0008, U+000B, U+000C, U+000E-U+001F, U+007F)
# ----------------------------------------------------------------
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# ハイフン行パターン (演出命令の補助指定)
HYPHEN_LINE_PATTERN = re.compile(r"^-\s+\S")

# $numX = ID
NUM_VAR_PATTERN = re.compile(r"^\$num(\d+)\s*=\s*(\S+)")
# $valueX = ID
VALUE_VAR_PATTERN = re.compile(r"^\$value(\d+)\s*=\s*(\S+)")

# 日本語・全角文字を含む行の検出
JAPANESE_PATTERN = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]")


# ----------------------------------------------------------------
# Token 種別
# ----------------------------------------------------------------


class TokenType:
    COMMAND = "command"  # @ChTalk など @ 始まりコマンド
    VARIABLE = "variable"  # $numX = ID / $valueX = ID
    KEYWORD = "keyword"  # msg / name / branch / #if など
    TEXT = "text"  # 日本語本文
    EMPTY = "empty"  # 空行
    COMMENT = "comment"  # // で始まるコメント行
    CONTROL_CHAR = "control_char"  # 制御文字が含まれていた行
    HYPHEN_OPTION = "hyphen_option"  # - speed 0.1 などの演出補助行
    UNKNOWN = "unknown"  # 上記に分類できない行


# ----------------------------------------------------------------
# ScriptToken
# ----------------------------------------------------------------


@dataclass
class ScriptToken:
    """Raw Script の 1 行から生成されるトークン"""

    line_number: int
    """元ファイルの行番号 (1始まり)"""

    raw: str
    """元行 (改行除去・制御文字除去済み)"""

    original_raw: str
    """元行 (改行除去のみ、制御文字除去前)"""

    token_type: str
    """TokenType のいずれか"""

    command: str | None = None
    """コマンド名 (@ChTalk, msg, branch, #if, $num1 など)"""

    args: list[str] = field(default_factory=list)
    """コマンド引数リスト"""

    text: str | None = None
    """本文 (TextトークンまたはKeyword後の続き本文)"""

    control_chars_removed: int = 0
    """除去した制御文字の数"""

    def __repr__(self) -> str:
        return (
            f"ScriptToken(L{self.line_number}, {self.token_type!r}, "
            f"command={self.command!r}, args={self.args}, text={self.text!r})"
        )

    @property
    def is_speech_command(self) -> bool:
        """会話コマンドかどうか"""
        return self.token_type == TokenType.COMMAND and self.command in {
            "@ChTalk",
            "@ChTalkMono",
            "@ChTalkSoundOff",
            "@ChTalkSoundOffMono",
            "@ChTalkName",
        }

    @property
    def is_narration(self) -> bool:
        """ナレーションコマンドかどうか"""
        return self.token_type == TokenType.KEYWORD and self.command == "msg"

    @property
    def is_text(self) -> bool:
        """本文行かどうか"""
        return self.token_type == TokenType.TEXT

    @property
    def is_empty(self) -> bool:
        return self.token_type == TokenType.EMPTY

    @property
    def is_comment(self) -> bool:
        return self.token_type == TokenType.COMMENT


def _split_first_token(line: str) -> tuple[str, list[str]]:
    """空白区切りの先頭トークンと残りの引数リストを返す。

    呼び出し側 (Tokenizer._classify_*) は line が非空・非空白文字列である
    ことを保証済みのため、line.split() は必ず1要素以上を返す。
    """
    parts = line.split()
    return parts[0], parts[1:]


# ----------------------------------------------------------------
# Tokenizer
# ----------------------------------------------------------------


class Tokenizer:
    """Raw Script ファイルを ScriptToken のリストに変換する"""

    # 既知のキーワード (コマンドではないが特殊扱いする先頭トークン)
    KEYWORD_TOKENS: frozenset[str] = frozenset(
        {
            "msg",
            "name",
            "branch",
            "#if",
            "#elseif",
            "#else",
            "#endif",
            "bg",
            "bgm",
            "se",
            "segmentCorrection",
            "visibleAccessory",
            # 実データdry-run trialで見つかった@なし演出コマンド群
            # (docs/runbooks/Real_Data_Dry_Run_Result_Template.md §3.2)。
            # 意味を完全解析せず、stage_direction として保持するために
            # KEYWORD として認識する。agents/parser/parser.py の
            # DIRECTION_TYPE_MAP と対にして追加すること。
            "ch",
            "pos",
            "euler",
            "wait",
            "camera",
            "fov",
            "ui",
            "rdraw",
            "hide",
            "uniq",
            "mo",
            "visible",
            "sound",
            "vo",
            "prefab",
            "set",
            "click",
            "nf",
            "screen",
            "scale",
            "remove",
            "wType",
            "loading",
            "active",
            "color",
            "wset",
            "parent",
            "light",
            "image",
            "distance",
            "shake",
            # branch/choice included dry-run (feature/branch-choice-dry-run)
            # で見つかった@なし演出コマンド。agents/parser/parser.py の
            # DIRECTION_TYPE_MAP と対にして追加すること。@付きコマンド
            # (@TalkPosR等) はここへの追加不要 (先頭が@なら自動でCOMMAND)。
            "costume",
            "fa",
        }
    )

    def __init__(
        self,
        strip_control_chars: bool = True,
        keep_comments: bool = False,
        keep_empty: bool = False,
    ) -> None:
        """
        Args:
            strip_control_chars: 制御文字を除去するかどうか (デフォルト True)
            keep_comments: コメント行をトークンに含めるか (デフォルト False)
            keep_empty: 空行をトークンに含めるか (デフォルト False)
        """
        self.strip_control_chars = strip_control_chars
        self.keep_comments = keep_comments
        self.keep_empty = keep_empty

    def tokenize_file(self, file_path: str | Path) -> list[ScriptToken]:
        """ファイルを読み込んでトークンリストを返す"""
        path = Path(file_path)
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return self.tokenize_lines(lines)

    def tokenize_lines(self, lines: list[str]) -> list[ScriptToken]:
        """行リストをトークンリストに変換する"""
        tokens: list[ScriptToken] = []
        for line_number, raw_line in enumerate(lines, start=1):
            token = self._tokenize_line(line_number, raw_line)
            if token is None:
                continue
            tokens.append(token)
        return tokens

    def tokenize_text(self, text: str) -> list[ScriptToken]:
        """文字列をトークンリストに変換する"""
        return self.tokenize_lines(text.splitlines(keepends=True))

    def _tokenize_line(self, line_number: int, raw_line: str) -> ScriptToken | None:
        """1行をトークン化する。None を返すと除外。

        各行分類は独立した _classify_* ヘルパーへ切り出し、ここでは
        「空行/コメント行 (keep_empty/keep_comments次第で除外)」→
        「その他の分類を順番に試す」という制御フローのみを担う
        (挙動は分割前と同一、ruffのC901複雑度対策でのリファクタリング)。
        """
        original_raw = raw_line.rstrip("\r\n")
        line, control_chars_removed = self._clean_line(original_raw)

        if not line:
            return (
                self._empty_token(line_number, original_raw, control_chars_removed)
                if self.keep_empty
                else None
            )

        if line.startswith("//"):
            return (
                self._comment_token(
                    line_number, line, original_raw, control_chars_removed
                )
                if self.keep_comments
                else None
            )

        classifiers = (
            self._classify_hyphen_option,
            self._classify_num_variable,
            self._classify_value_variable,
            self._classify_at_command,
            self._classify_dollar_variable,
            self._classify_hash_keyword,
            self._classify_known_keyword,
            self._classify_text,
        )
        for classify in classifiers:
            token = classify(line_number, line, original_raw, control_chars_removed)
            if token is not None:
                return token

        return self._unknown_token(
            line_number, line, original_raw, control_chars_removed
        )

    def _clean_line(self, original_raw: str) -> tuple[str, int]:
        """制御文字除去・前後空白除去を行い、
        (整形後の行, 除去した制御文字数) を返す。"""
        if self.strip_control_chars:
            cleaned = CONTROL_CHARS_PATTERN.sub("", original_raw)
            return cleaned.strip(), len(original_raw) - len(cleaned)
        return original_raw.strip(), 0

    def _empty_token(
        self, line_number: int, original_raw: str, control_chars_removed: int
    ) -> ScriptToken:
        return ScriptToken(
            line_number=line_number,
            raw="",
            original_raw=original_raw,
            token_type=TokenType.EMPTY,
            control_chars_removed=control_chars_removed,
        )

    def _comment_token(
        self,
        line_number: int,
        line: str,
        original_raw: str,
        control_chars_removed: int,
    ) -> ScriptToken:
        return ScriptToken(
            line_number=line_number,
            raw=line,
            original_raw=original_raw,
            token_type=TokenType.COMMENT,
            text=line[2:].strip(),
            control_chars_removed=control_chars_removed,
        )

    def _classify_hyphen_option(
        self,
        line_number: int,
        line: str,
        original_raw: str,
        control_chars_removed: int,
    ) -> ScriptToken | None:
        """- speed 0.1 などの演出補助行"""
        if not HYPHEN_LINE_PATTERN.match(line):
            return None
        parts = line.split(maxsplit=1)
        return ScriptToken(
            line_number=line_number,
            raw=line,
            original_raw=original_raw,
            token_type=TokenType.HYPHEN_OPTION,
            command="-",
            args=parts[1].split() if len(parts) > 1 else [],
            control_chars_removed=control_chars_removed,
        )

    def _classify_num_variable(
        self,
        line_number: int,
        line: str,
        original_raw: str,
        control_chars_removed: int,
    ) -> ScriptToken | None:
        """$numX = ID"""
        num_match = NUM_VAR_PATTERN.match(line)
        if not num_match:
            return None
        return ScriptToken(
            line_number=line_number,
            raw=line,
            original_raw=original_raw,
            token_type=TokenType.VARIABLE,
            command=f"$num{num_match.group(1)}",
            args=[num_match.group(2)],
            control_chars_removed=control_chars_removed,
        )

    def _classify_value_variable(
        self,
        line_number: int,
        line: str,
        original_raw: str,
        control_chars_removed: int,
    ) -> ScriptToken | None:
        """$valueX = ID"""
        val_match = VALUE_VAR_PATTERN.match(line)
        if not val_match:
            return None
        return ScriptToken(
            line_number=line_number,
            raw=line,
            original_raw=original_raw,
            token_type=TokenType.VARIABLE,
            command=f"$value{val_match.group(1)}",
            args=[val_match.group(2)],
            control_chars_removed=control_chars_removed,
        )

    def _classify_at_command(
        self,
        line_number: int,
        line: str,
        original_raw: str,
        control_chars_removed: int,
    ) -> ScriptToken | None:
        """@ で始まるコマンド"""
        first, rest_args = _split_first_token(line)
        if not first.startswith("@"):
            return None
        return ScriptToken(
            line_number=line_number,
            raw=line,
            original_raw=original_raw,
            token_type=TokenType.COMMAND,
            command=first,
            args=rest_args,
            control_chars_removed=control_chars_removed,
        )

    def _classify_dollar_variable(
        self,
        line_number: int,
        line: str,
        original_raw: str,
        control_chars_removed: int,
    ) -> ScriptToken | None:
        """$ で始まる未分類変数行 (NUM/VALUE_VAR_PATTERN で捕捉できなかったもの)"""
        first, rest_args = _split_first_token(line)
        if not first.startswith("$"):
            return None
        return ScriptToken(
            line_number=line_number,
            raw=line,
            original_raw=original_raw,
            token_type=TokenType.VARIABLE,
            command=first,
            args=rest_args,
            control_chars_removed=control_chars_removed,
        )

    def _classify_hash_keyword(
        self,
        line_number: int,
        line: str,
        original_raw: str,
        control_chars_removed: int,
    ) -> ScriptToken | None:
        """# で始まる分岐キーワード"""
        first, rest_args = _split_first_token(line)
        if not first.startswith("#"):
            return None
        return ScriptToken(
            line_number=line_number,
            raw=line,
            original_raw=original_raw,
            token_type=TokenType.KEYWORD,
            command=first,
            args=rest_args,
            control_chars_removed=control_chars_removed,
        )

    def _classify_known_keyword(
        self,
        line_number: int,
        line: str,
        original_raw: str,
        control_chars_removed: int,
    ) -> ScriptToken | None:
        """既知キーワード (msg/name/branch など)"""
        first, rest_args = _split_first_token(line)
        if first not in self.KEYWORD_TOKENS:
            return None
        # name や branch はコマンド後に引数として本文が続く場合がある
        text_part = " ".join(rest_args) if rest_args else None
        return ScriptToken(
            line_number=line_number,
            raw=line,
            original_raw=original_raw,
            token_type=TokenType.KEYWORD,
            command=first,
            args=rest_args,
            text=text_part,
            control_chars_removed=control_chars_removed,
        )

    def _classify_text(
        self,
        line_number: int,
        line: str,
        original_raw: str,
        control_chars_removed: int,
    ) -> ScriptToken | None:
        """日本語テキストを含む行、またはASCII以外の文字を含む行
        (句読点・省略記号のみの間「……」等、JAPANESE_PATTERNの範囲外の
        Unicodeブロックだけで構成される本文行を含む) → 本文とみなす。
        実データdry-run trialで「……」のみの行がJAPANESE_PATTERNに一致せず
        UNKNOWNになり、対応するモノローグの本文が欠落する不具合を発見した
        (feature/branch-choice-dry-run)。
        """
        if not (JAPANESE_PATTERN.search(line) or not line.isascii()):
            return None
        return ScriptToken(
            line_number=line_number,
            raw=line,
            original_raw=original_raw,
            token_type=TokenType.TEXT,
            text=line,
            control_chars_removed=control_chars_removed,
        )

    def _unknown_token(
        self,
        line_number: int,
        line: str,
        original_raw: str,
        control_chars_removed: int,
    ) -> ScriptToken:
        """純粋な英数字の行 (ラベル・ファイル名など) → UNKNOWN として保持"""
        first, rest_args = _split_first_token(line)
        return ScriptToken(
            line_number=line_number,
            raw=line,
            original_raw=original_raw,
            token_type=TokenType.UNKNOWN,
            command=first or None,
            args=rest_args,
            control_chars_removed=control_chars_removed,
        )


# ----------------------------------------------------------------
# Utility
# ----------------------------------------------------------------


def tokenize_file(file_path: str | Path, **kwargs) -> list[ScriptToken]:
    """ファイルをトークン化するショートカット関数"""
    return Tokenizer(**kwargs).tokenize_file(file_path)


def tokenize_text(text: str, **kwargs) -> list[ScriptToken]:
    """テキストをトークン化するショートカット関数"""
    return Tokenizer(**kwargs).tokenize_text(text)
