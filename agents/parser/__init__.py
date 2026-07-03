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

from .character_dictionary import (
    CharacterDictionaryEntry,
    build_character_dictionary_coverage_report,
    load_character_dictionary,
    resolve_character_by_name,
    resolve_character_by_source_id,
    validate_character_dictionary,
)
from .compatibility import (
    DEFAULT_COMMANDS_CONFIG,
    detect_new_speech_commands,
    determine_compatibility_status,
    get_new_speech_hints,
    is_speech_candidate,
    load_command_config,
)
from .exporter import (
    Exporter,
    export_json,
)
from .normalizer import (
    PARSER_VERSION,
    IdGenerator,
    Normalizer,
)
from .parser import (
    BlockData,
    EpisodeData,
    ParseResult,
    SceneData,
    StoryParser,
)
from .resolver import (
    CharacterDictionary,
    Speaker,
    SpeakerAssignmentRecord,
    SpeakerResolver,
)
from .tokenizer import (
    ScriptToken,
    Tokenizer,
    TokenType,
    tokenize_file,
    tokenize_text,
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
    # character_dictionary
    "CharacterDictionaryEntry",
    "build_character_dictionary_coverage_report",
    "load_character_dictionary",
    "resolve_character_by_name",
    "resolve_character_by_source_id",
    "validate_character_dictionary",
    # compatibility
    "DEFAULT_COMMANDS_CONFIG",
    "detect_new_speech_commands",
    "determine_compatibility_status",
    "get_new_speech_hints",
    "is_speech_candidate",
    "load_command_config",
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
