#!/usr/bin/env python3
"""
Check Invisible Unicode
リポジトリ内のテキストファイルを走査し、危険な不可視Unicode文字
(bidi override/control、zero-width系、BOM、soft hyphen等) を検出する。

GitHubの hidden/bidirectional Unicode warning自体は今後マージブロッカーに
しない (日本語Markdown・全角記号・罫線・矢印・通常のUnicode引用符等を
GitHubの検出器は広めに拾うため)。このスクリプトは「2バイト文字だからNG」
という判定はせず、レビューを欺ける可能性のある本当に危険な文字
(bidi override/control、zero-width space等) だけを機械的に検出する。

Usage:
    # リポジトリ全体を走査
    uv run python scripts/check_invisible_unicode.py

    # 特定のファイル・ディレクトリのみ走査 (複数指定可)
    uv run python scripts/check_invisible_unicode.py --path agents/merger
    uv run python scripts/check_invisible_unicode.py --path some_file.py

Exit codes:
    0: 危険な不可視Unicode文字は見つからなかった
    1: 1件以上検出された
    2: 走査対象の読み込み・列挙に失敗した (存在しないpath指定等)
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_PROJECT_ROOT = Path(__file__).parent.parent

# 走査対象拡張子。日本語・全角記号自体は問題にしないため、テキスト系の
# 拡張子のみを対象にすればよい (バイナリファイルはread_text失敗時に
# scan_fileが静かにスキップする)。
TARGET_EXTENSIONS = frozenset({".py", ".json", ".md", ".yml", ".yaml", ".toml", ".txt"})

# ディレクトリ名として現れたら (走査rootからの相対パスのどの階層でも)
# 除外する。
EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
    }
)

# 走査root相対パスの先頭一致で除外するプレフィックス
# (実データ・生成物置き場。docs/runbooks/Real_Data_Dry_Run.md参照)。
EXCLUDED_DIR_PREFIXES = (
    "data/raw",
    "data/normalized",
    "data/extracted",
    "data/reports",
    "workspace/dry_runs",
)

# Unicode bidirectional category のうち、bidi override/isolate/embedding
# として扱う値 (レビュー表示順を操作しうる制御文字)。
_BIDI_CONTROL_CLASSES = frozenset(
    {"RLO", "LRO", "RLE", "LRE", "PDF", "RLI", "LRI", "FSI", "PDI"}
)

# 明示的に危険とみなすコードポイント。unicodedata実装差異
# (Pythonバージョン間でのcategory/bidirectional値の変化) への保険として、
# category/bidirectionalによる判定と併用する。
_DANGEROUS_CODEPOINTS: dict[int, str] = {
    0x200B: "ZERO WIDTH SPACE",
    0x200C: "ZERO WIDTH NON-JOINER",
    0x200D: "ZERO WIDTH JOINER",
    0x200E: "LEFT-TO-RIGHT MARK",
    0x200F: "RIGHT-TO-LEFT MARK",
    0x202A: "LEFT-TO-RIGHT EMBEDDING",
    0x202B: "RIGHT-TO-LEFT EMBEDDING",
    0x202C: "POP DIRECTIONAL FORMATTING",
    0x202D: "LEFT-TO-RIGHT OVERRIDE",
    0x202E: "RIGHT-TO-LEFT OVERRIDE",
    0x2060: "WORD JOINER",
    0x2061: "FUNCTION APPLICATION",
    0x2062: "INVISIBLE TIMES",
    0x2063: "INVISIBLE SEPARATOR",
    0x2064: "INVISIBLE PLUS",
    0x2066: "LEFT-TO-RIGHT ISOLATE",
    0x2067: "RIGHT-TO-LEFT ISOLATE",
    0x2068: "FIRST STRONG ISOLATE",
    0x2069: "POP DIRECTIONAL ISOLATE",
    0xFEFF: "ZERO WIDTH NO-BREAK SPACE (BOM)",
    0x00AD: "SOFT HYPHEN",
}

_EXCERPT_MAX_LENGTH = 60


@dataclass
class Finding:
    """検出1件分 (file/line/column/codepoint/name/excerpt)。"""

    path: Path
    line: int
    column: int
    codepoint: int
    name: str
    excerpt: str

    def format(self) -> str:
        return (
            f"- {self.path.as_posix()}:{self.line}:{self.column} "
            f"U+{self.codepoint:04X} {self.name}"
        )


def is_dangerous_char(ch: str) -> str | None:
    """危険な不可視文字ならUnicode名を返す。安全な文字ならNoneを返す。

    日本語・全角英数字・全角記号・罫線・矢印・通常のUnicode引用符は
    category Cf でもbidi制御でもないため、ここでは検出されない。
    """
    codepoint = ord(ch)
    if codepoint in _DANGEROUS_CODEPOINTS:
        return _DANGEROUS_CODEPOINTS[codepoint]

    category = unicodedata.category(ch)
    bidi = unicodedata.bidirectional(ch)
    if category == "Cf" or bidi in _BIDI_CONTROL_CLASSES:
        try:
            return unicodedata.name(ch)
        except ValueError:
            return f"UNNAMED (U+{codepoint:04X})"

    return None


def scan_text(path: Path, text: str) -> list[Finding]:
    """テキスト内容から危険な不可視文字を検出する (ファイルI/Oを含まない)。"""
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for col, ch in enumerate(line, start=1):
            name = is_dangerous_char(ch)
            if name is None:
                continue
            excerpt = line.strip()
            if len(excerpt) > _EXCERPT_MAX_LENGTH:
                excerpt = excerpt[: _EXCERPT_MAX_LENGTH - 3] + "..."
            findings.append(Finding(path, lineno, col, ord(ch), name, excerpt))
    return findings


def is_excluded(rel_path: PurePosixPath) -> bool:
    """走査root相対パスが除外対象かどうかを判定する (純粋関数)。"""
    if any(part in EXCLUDED_DIR_NAMES for part in rel_path.parts):
        return True

    rel_str = rel_path.as_posix()
    return any(
        rel_str == prefix or rel_str.startswith(f"{prefix}/")
        for prefix in EXCLUDED_DIR_PREFIXES
    )


def iter_target_files(directory: Path) -> list[Path]:
    """directory配下の走査対象ファイル (対象拡張子・除外パス適用済み) を
    列挙する。
    """
    files: list[Path] = []
    for path in directory.rglob("*"):
        if not path.is_file() or path.suffix not in TARGET_EXTENSIONS:
            continue
        rel = PurePosixPath(path.relative_to(directory).as_posix())
        if is_excluded(rel):
            continue
        files.append(path)
    return sorted(files)


def scan_file(path: Path) -> list[Finding]:
    """1ファイルを走査する。UTF-8として読めないファイル (バイナリ等) は
    静かにスキップする (対象拡張子をテキスト系に絞っているため稀なケース、
    exit code 2の対象にはしない)。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    return scan_text(path, text)


def scan_paths(paths: list[Path]) -> list[Finding]:
    """ファイル・ディレクトリ混在のpathリストを走査する。

    Raises:
        OSError: 指定pathが存在しない場合。
    """
    findings: list[Finding] = []
    for path in paths:
        if path.is_dir():
            targets = iter_target_files(path)
        elif path.is_file():
            targets = [path] if path.suffix in TARGET_EXTENSIONS else []
        else:
            raise OSError(f"path not found: {path}")

        for target in targets:
            findings.extend(scan_file(target))

    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "危険な不可視Unicode文字 (bidi override/control、zero-width系、"
            "BOM、soft hyphen等) を検出する。日本語・全角記号・罫線・矢印は"
            "検出対象にしない。"
        ),
    )
    parser.add_argument(
        "--path",
        "-p",
        action="append",
        dest="paths",
        help=(
            "走査対象のファイル・ディレクトリ (複数指定可、省略時は"
            "リポジトリ全体を走査する)"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = [Path(p) for p in args.paths] if args.paths else [_PROJECT_ROOT]

    try:
        findings = scan_paths(paths)
    except OSError as e:
        print(f"[エラー] {e}", file=sys.stderr)
        return 2

    if findings:
        print("Found invisible Unicode characters:")
        for finding in findings:
            print(finding.format())
            print(f"    excerpt: {finding.excerpt}")
        return 1

    print("No dangerous invisible Unicode characters found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
