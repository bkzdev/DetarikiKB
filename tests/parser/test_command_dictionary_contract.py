"""Stage Directionコマンド辞書の同期契約テスト。"""

from pathlib import Path

from agents.parser.compatibility import (
    DEFAULT_COMMANDS_CONFIG,
    load_command_config,
)
from agents.parser.parser import DIRECTION_TYPE_MAP, StoryParser
from agents.parser.tokenizer import Tokenizer
from scripts.check_script_compatibility import (
    build_case_variants_map,
    build_known_command_set,
    check_file,
    get_speech_commands,
)

ALLOWED_DIRECTION_TYPES = frozenset(
    {
        "background",
        "camera",
        "character_display",
        "effect",
        "motion",
        "screen",
        "sound",
        "system",
        "ui",
        "unknown",
        "video",
    }
)
NORMALIZED_STORY_DOC = (
    Path(__file__).parents[2]
    / "docs"
    / "architecture"
    / "05_Parser"
    / "Normalized_Story_JSON.md"
)


def _configured_stage_directions() -> list[str]:
    config = load_command_config(DEFAULT_COMMANDS_CONFIG)
    commands = config.get("stage_direction")
    assert isinstance(commands, list), "stage_direction must be a YAML list"
    assert all(isinstance(command, str) and command for command in commands)
    return commands


def test_stage_direction_config_and_parser_map_match_bidirectionally():
    configured = _configured_stage_directions()

    assert len(configured) == len(set(configured)), "duplicate stage_direction entry"

    configured_set = set(configured)
    parser_set = set(DIRECTION_TYPE_MAP)
    assert configured_set == parser_set, (
        f"missing_in_parser={sorted(configured_set - parser_set)!r}; "
        f"missing_in_config={sorted(parser_set - configured_set)!r}"
    )


def test_stage_direction_types_are_documented():
    undocumented = set(DIRECTION_TYPE_MAP.values()) - ALLOWED_DIRECTION_TYPES
    assert not undocumented, f"undocumented direction types: {sorted(undocumented)!r}"

    documentation = NORMALIZED_STORY_DOC.read_text(encoding="utf-8")
    missing_from_documentation = {
        direction_type
        for direction_type in ALLOWED_DIRECTION_TYPES
        if f"| `{direction_type}` |" not in documentation
    }
    assert not missing_from_documentation, (
        "supported direction types missing from documentation: "
        f"{sorted(missing_from_documentation)!r}"
    )


def test_bare_stage_directions_are_tokenizer_keywords():
    bare_commands = {
        command
        for command in _configured_stage_directions()
        if not command.startswith("@")
    }
    missing = bare_commands - Tokenizer.KEYWORD_TOKENS
    assert not missing, (
        f"bare commands missing from KEYWORD_TOKENS: {sorted(missing)!r}"
    )


def test_all_configured_stage_directions_reach_both_consumers(tmp_path: Path):
    configured = _configured_stage_directions()
    config = load_command_config(DEFAULT_COMMANDS_CONFIG)
    known_commands = build_known_command_set(config)

    missing_from_checker = set(configured) - known_commands
    assert not missing_from_checker, (
        "stage directions missing from standalone checker: "
        f"{sorted(missing_from_checker)!r}"
    )

    script_path = tmp_path / "all_stage_directions.dec"
    script_path.write_text(
        "".join(f"{command} 0\n" for command in configured), encoding="utf-8"
    )
    checker_result = check_file(
        script_path,
        known_commands,
        get_speech_commands(config),
        build_case_variants_map(config),
        config.get("new_speech_detection_hints", {}).get("name_contains", []),
        char_map={},
    )
    assert not checker_result.unknown_commands

    for command in configured:
        result = StoryParser(preserve_stage_directions=True).parse_text(
            f"{command} 0\n"
        )
        blocks = result.episodes[0].scenes[0].blocks
        assert len(blocks) == 1, f"unexpected block count for {command!r}: {blocks!r}"
        block = blocks[0]
        assert block.block_type == "stage_direction", (
            f"{command!r} became {block.block_type!r}"
        )
        assert block.raw_command == command
        assert block.direction_type == DIRECTION_TYPE_MAP[command]
