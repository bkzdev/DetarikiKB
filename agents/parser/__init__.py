"""
DKB Story Parser Package

Usage:
    from agents.parser import StoryParser, CharacterDictionary, Normalizer, Exporter
    from agents.parser import tokenize_file, tokenize_text

Phase 1 モジュール:
    tokenizer  - Raw Script → ScriptToken 変換
    resolver   - キャラクターID・話者スロット解決
    parser     - Token → 中間構造 (ParseResult) 変換
    normalizer - 中間構造 → Normalized Story JSON 変換
    exporter   - JSON ファイル出力
"""

from .tokenizer import (
    ScriptToken,
    TokenType,
    Tokenizer,
    tokenize_file,
    tokenize_text,
)
from .resolver import (
    CharacterDictionary,
    Speaker,
    SpeakerAssignmentRecord,
    SpeakerResolver,
)
from .parser import (
    BlockData,
    EpisodeData,
    ParseResult,
    SceneData,
    StoryParser,
)
from .normalizer import (
    IdGenerator,
    Normalizer,
    PARSER_VERSION,
)
from .exporter import (
    Exporter,
    export_json,
)

__all__ = [
    # tokenizer
    "ScriptToken",
    "TokenType",
    "Tokenizer",
    "tokenize_file",
    "tokenize_text",
    # resolver
    "CharacterDictionary",
    "Speaker",
    "SpeakerAssignmentRecord",
    "SpeakerResolver",
    # parser
    "BlockData",
    "EpisodeData",
    "ParseResult",
    "SceneData",
    "StoryParser",
    # normalizer
    "IdGenerator",
    "Normalizer",
    "PARSER_VERSION",
    # exporter
    "Exporter",
    "export_json",
]
