"""
DKB Summarizer - Domain Context Loader
Episode/Story Summary生成prompt (`agents/summarizer/prompt.py`) へ注入する、
人間確認済みのドメイン前提知識
(`knowledge/dictionaries/summary_domain_context.yaml`) を読み込む
(`summary-domain-context-injection`)。

背景（2026-07-19ユーザーレビューで確認された決定的なドメイン知識）:
3世代のdraftで「このゲームの主人公はプレイヤーであり作中で『班長』と
呼ばれる」というゲーム固有の前提をLLMが知らないため、話者不明モノローグの
主体（班長）を近くの名前付きキャラクターへ誤帰属する、という系統的な
帰属誤りが確認された。`Backlog summary-generation-glossary-injection`の
初の具体化として、このファイルをsystem promptへ注入することで対処する。

設計方針（`docs/architecture/06_AI/Story_Summary_Generation_Plan.md` §6.5）:
- 読み込むのは`knowledge/dictionaries/summary_domain_context.yaml`
  (**commit対象**、人間確認済みの事実のみを載せる運用。
  `docs/runbooks/Story_Summary_Generation_Runbook.md`の編集手順を参照)
- ファイルが存在しない、または`entries`が空/未定義の場合は空リストを返す。
  呼び出し側 (`agents/summarizer/prompt.py`の`build_*_system_prompt`系関数)
  はこれを「注入なし・従来のsystem promptのまま」として扱う (後方互換)
- このモジュール自体はprompt文言の組み立てを行わない (I/O・パースのみ)。
  domain contextをsystem promptへ実際に注入する処理は
  `agents/summarizer/prompt.py`の`build_domain_context_block`が担う
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_DOMAIN_CONTEXT_PATH = (
    _PROJECT_ROOT / "knowledge" / "dictionaries" / "summary_domain_context.yaml"
)


def load_domain_context(path: str | Path | None = None) -> list[str]:
    """`knowledge/dictionaries/summary_domain_context.yaml`相当のYAMLファイルを
    読み込み、`entries[].text`を出現順のリストとして返す。

    `path`省略時は`DEFAULT_DOMAIN_CONTEXT_PATH`を使う。ファイルが存在しない
    場合、`entries`が空/未定義の場合はいずれも空リストを返す
    (`agents/parser/character_dictionary.py`の`load_character_dictionary`と
    同じ「ファイル無し=空」の既存方針を踏襲、後方互換のための安全な既定動作)。
    各entryの`text`は、YAML `>-`折り返し等で生じた改行を単一の半角スペースへ
    正規化する (system promptへ1行の前提として埋め込みやすくするため)。
    空文字列/空白のみのtextはskipする。
    """
    p = Path(path) if path is not None else DEFAULT_DOMAIN_CONTEXT_PATH
    if not p.exists():
        return []

    with open(p, encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    texts: list[str] = []
    for raw_entry in data.get("entries", []) or []:
        if not isinstance(raw_entry, dict):
            continue
        text = raw_entry.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(" ".join(text.split()))
    return texts
