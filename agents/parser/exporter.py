"""
DKB Story Parser - Exporter
Normalized Story JSON をファイルへ出力する。

Phase 8 (Parser_Implementation_Plan.md)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Exporter:
    """
    Normalized Story JSON (dict) をファイルへ出力する。

    出力先ディレクトリは自動生成する。
    """

    def __init__(
        self,
        output_dir: str | Path,
        indent: int = 2,
        overwrite: bool = True,
    ) -> None:
        """
        Args:
            output_dir: 出力先ディレクトリ
            indent: JSON インデント幅
            overwrite: 既存ファイルを上書きするか
        """
        self.output_dir = Path(output_dir)
        self.indent = indent
        self.overwrite = overwrite

    def export(self, story_json: dict[str, Any], filename: str | None = None) -> Path:
        """
        Normalized Story JSON をファイルへ書き出す。

        Args:
            story_json: Normalizer が返した dict
            filename: 出力ファイル名 (None の場合は storyId から自動生成)

        Returns:
            出力ファイルの Path
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            story_id = story_json.get("storyId", "UNKNOWN")
            filename = f"{story_id}.json"

        output_path = self.output_dir / filename

        if not self.overwrite and output_path.exists():
            raise FileExistsError(
                f"出力先ファイルが既に存在します: {output_path}\n"
                "上書きする場合は overwrite=True を指定してください。"
            )

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(story_json, f, ensure_ascii=False, indent=self.indent)

        return output_path

    def export_with_category(
        self,
        story_json: dict[str, Any],
        filename: str | None = None,
    ) -> Path:
        """
        ストーリーカテゴリ別のサブディレクトリへ出力する。

        出力先:
            MAIN     → output_dir/main/
            EVT      → output_dir/event/
            RAID     → output_dir/raid/
            OTHER    → output_dir/other/
            CHAR_*   → output_dir/character/
        """
        category = story_json.get("storyCategory", "OTHER")
        subdir = _category_to_subdir(category)
        original_output_dir = self.output_dir
        self.output_dir = original_output_dir / subdir
        try:
            return self.export(story_json, filename)
        finally:
            self.output_dir = original_output_dir


def _category_to_subdir(category: str) -> str:
    """ストーリーカテゴリからサブディレクトリ名を返す"""
    mapping = {
        "MAIN": "main",
        "EVT": "event",
        "RAID": "raid",
        "OTHER": "other",
        "CHAR_MAIN": "character",
        "CHAR_EXTRA": "character",
        "CHAR_DATE": "character",
    }
    return mapping.get(category, "other")


# ----------------------------------------------------------------
# Convenience function
# ----------------------------------------------------------------


def export_json(
    story_json: dict[str, Any],
    output_dir: str | Path,
    filename: str | None = None,
    indent: int = 2,
    overwrite: bool = True,
) -> Path:
    """Normalized Story JSON をファイルへ書き出すショートカット関数"""
    return Exporter(
        output_dir=output_dir,
        indent=indent,
        overwrite=overwrite,
    ).export(story_json, filename)
