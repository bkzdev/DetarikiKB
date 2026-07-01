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
        """1行をトークン化する。None を返すと除外。"""
        # 改行除去
        original_raw = raw_line.rstrip("\r\n")

        # 制御文字除去
        control_chars_removed = 0
        if self.strip_control_chars:
            cleaned = CONTROL_CHARS_PATTERN.sub("", original_raw)
            control_chars_removed = len(original_raw) - len(cleaned)
            line = cleaned.strip()
        else:
            line = original_raw.strip()

        # 空行
        if not line:
            if self.keep_empty:
                return ScriptToken(
                    line_number=line_number,
                    raw=line,
                    original_raw=original_raw,
                    token_type=TokenType.EMPTY,
                    control_chars_removed=control_chars_removed,
                )
            return None

        # コメント行
        if line.startswith("//"):
            if self.keep_comments:
                return ScriptToken(
                    line_number=line_number,
                    raw=line,
                    original_raw=original_raw,
                    token_type=TokenType.COMMENT,
                    text=line[2:].strip(),
                    control_chars_removed=control_chars_removed,
                )
            return None

        # ハイフン行 (- speed 0.1 など)
        if HYPHEN_LINE_PATTERN.match(line):
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

        # $numX = ID
        num_match = NUM_VAR_PATTERN.match(line)
        if num_match:
            return ScriptToken(
                line_number=line_number,
                raw=line,
                original_raw=original_raw,
                token_type=TokenType.VARIABLE,
                command=f"$num{num_match.group(1)}",
                args=[num_match.group(2)],
                control_chars_removed=control_chars_removed,
            )

        # $valueX = ID
        val_match = VALUE_VAR_PATTERN.match(line)
        if val_match:
            return ScriptToken(
                line_number=line_number,
                raw=line,
                original_raw=original_raw,
                token_type=TokenType.VARIABLE,
                command=f"$value{val_match.group(1)}",
                args=[val_match.group(2)],
                control_chars_removed=control_chars_removed,
            )

        # 先頭トークン分解
        parts = line.split()
        first = parts[0]
        rest_args = parts[1:]

        # @ で始まるコマンド
        if first.startswith("@"):
            return ScriptToken(
                line_number=line_number,
                raw=line,
                original_raw=original_raw,
                token_type=TokenType.COMMAND,
                command=first,
                args=rest_args,
                control_chars_removed=control_chars_removed,
            )

        # $ で始まる未分類変数行 (NUM/VALUE_VAR_PATTERN で捕捉できなかったもの)
        if first.startswith("$"):
            return ScriptToken(
                line_number=line_number,
                raw=line,
                original_raw=original_raw,
                token_type=TokenType.VARIABLE,
                command=first,
                args=rest_args,
                control_chars_removed=control_chars_removed,
            )

        # # で始まる分岐キーワード
        if first.startswith("#"):
            return ScriptToken(
                line_number=line_number,
                raw=line,
                original_raw=original_raw,
                token_type=TokenType.KEYWORD,
                command=first,
                args=rest_args,
                control_chars_removed=control_chars_removed,
            )

        # 既知キーワード
        if first in self.KEYWORD_TOKENS:
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

        # 日本語テキストを含む行 → 本文とみなす
        if JAPANESE_PATTERN.search(line):
            return ScriptToken(
                line_number=line_number,
                raw=line,
                original_raw=original_raw,
                token_type=TokenType.TEXT,
                text=line,
                control_chars_removed=control_chars_removed,
            )

        # 純粋な英数字の行 (ラベル・ファイル名など)
        # → UNKNOWN として保持
        return ScriptToken(
            line_number=line_number,
            raw=line,
            original_raw=original_raw,
            token_type=TokenType.UNKNOWN,
            command=first if parts else None,
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
