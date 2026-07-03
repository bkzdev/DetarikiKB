"""
DKB Merger - Input Resolver
--input引数群 (ファイルパス / ディレクトリパス / globパターン文字列) を、
処理対象のJSONファイル群へ解決する。

- ファイルパス: そのまま1件
- ディレクトリパス: 直下 (デフォルト) または再帰的 (recursive=True) に *.json を収集
- globパターン (*, ?, [ を含む文字列): Python glob モジュールで展開する
  (シェル展開に依存しないため、Windows shell / PowerShellでの挙動差を避ける)
- 存在しない、または1件もマッチしないraw引数はpathをNoneとしたエントリとして
  残す (黙って無視せず、呼び出し側が「解決できなかった入力」として報告できる
  ようにする)
- 複数のraw引数が同じファイルを指しても、そのファイルは1回だけ処理する
  (重複排除)
- 出力順序はraw引数の指定順 → 各raw引数内はパス文字列順で安定させる

docs/architecture/06_AI/Merged_Knowledge_Design.md
"""

from __future__ import annotations

import glob as glob_module
from dataclasses import dataclass
from pathlib import Path

_GLOB_CHARS = frozenset("*?[")


@dataclass
class ResolvedInputEntry:
    """1件の解決結果。

    pathがNoneの場合、rawは1件もJSONファイルへ解決できなかったことを示す
    (存在しないパス、空ディレクトリ、無マッチのglobパターン等)。
    """

    raw: str
    path: Path | None


def _looks_like_glob_pattern(raw: str) -> bool:
    return any(ch in raw for ch in _GLOB_CHARS)


def _expand_one(raw: str, recursive: bool) -> list[Path]:
    if _looks_like_glob_pattern(raw):
        matches = glob_module.glob(raw, recursive=recursive)
        return sorted(
            (
                Path(m)
                for m in matches
                if Path(m).is_file() and Path(m).suffix == ".json"
            ),
            key=str,
        )

    path = Path(raw)
    if path.is_dir():
        pattern = "**/*.json" if recursive else "*.json"
        return sorted(path.glob(pattern), key=str)
    if path.is_file():
        return [path]
    return []


def resolve_input_entries(
    inputs: list[str], recursive: bool = False
) -> list[ResolvedInputEntry]:
    """--input引数群を解決する。

    同じファイルが複数raw引数から重複して指定された場合は、最初に登場した
    箇所でのみ1回処理する (以降のraw引数からは除外される)。
    """
    entries: list[ResolvedInputEntry] = []
    seen: set[Path] = set()

    for raw in inputs:
        matches = _expand_one(raw, recursive=recursive)
        if not matches:
            entries.append(ResolvedInputEntry(raw=raw, path=None))
            continue

        for path in matches:
            key = path.resolve()
            if key in seen:
                continue
            seen.add(key)
            entries.append(ResolvedInputEntry(raw=raw, path=path))

    return entries
