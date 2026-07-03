"""
tests/parser/test_compatibility.py
agents/parser/compatibility.py のユニットテスト

check_script_compatibility.py単体実行とnormalize_story.py --check-compat
経由の互換性判定を揃えるための共有ロジック
(feature/compatibility-check-consistency) を検証する。
すべて合成データのみ使用する。
"""

from __future__ import annotations

import yaml

from agents.parser.compatibility import (
    detect_new_speech_commands,
    determine_compatibility_status,
    get_new_speech_hints,
    is_speech_candidate,
    load_command_config,
)

# ----------------------------------------------------------------
# load_command_config / get_new_speech_hints
# ----------------------------------------------------------------


def test_load_command_config_missing_file_returns_empty(tmp_path):
    assert load_command_config(tmp_path / "does_not_exist.yaml") == {}


def test_load_command_config_reads_yaml(tmp_path):
    path = tmp_path / "commands.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"speech": ["@ChTalk"]}, f)
    config = load_command_config(path)
    assert config == {"speech": ["@ChTalk"]}


def test_get_new_speech_hints_extracts_name_contains():
    config = {"new_speech_detection_hints": {"name_contains": ["Talk", "Voice"]}}
    assert get_new_speech_hints(config) == ["Talk", "Voice"]


def test_get_new_speech_hints_missing_key_returns_empty():
    assert get_new_speech_hints({}) == []


# ----------------------------------------------------------------
# is_speech_candidate
# ----------------------------------------------------------------


def test_is_speech_candidate_matches_substring():
    hints = ["Talk", "Mono", "Name", "Voice", "Speech", "Speak"]
    assert is_speech_candidate("@ChTalkNewVariant", hints) is True
    assert is_speech_candidate("@NewVoiceCommand", hints) is True


def test_is_speech_candidate_no_match():
    hints = ["Talk", "Mono", "Name", "Voice", "Speech", "Speak"]
    assert is_speech_candidate("@Camera3", hints) is False
    assert is_speech_candidate("camera", hints) is False


def test_is_speech_candidate_matches_command_named_with_talk_but_not_speech():
    """@TalkCamera3のような、"Talk"を含むが実際は演出コマンドの名前でも
    ヒント判定自体はcommand containsのみを見るため合致する
    (=新規会話コマンド候補として一度は挙がる)。この挙動自体はPR #29の
    仕様通り。PR #30後は@TalkCamera3自体がconfig/script_commands.yamlの
    既知コマンドになっているため、is_speech_candidateへ到達する前に
    unknown判定から除外される（既知コマンドはそもそも候補にならない）。"""
    hints = ["Talk", "Mono", "Name", "Voice", "Speech", "Speak"]
    assert is_speech_candidate("@TalkCamera3", hints) is True


# ----------------------------------------------------------------
# detect_new_speech_commands
# ----------------------------------------------------------------


def test_detect_new_speech_commands_filters_by_hint():
    hints = ["Talk", "Mono", "Name", "Voice", "Speech", "Speak"]
    unknown_commands = {
        "@TalkSomethingNew": 3,
        "@TotallyUnknownCommand123": 1,
        "@NewVoiceLine": 2,
    }
    result = detect_new_speech_commands(unknown_commands, hints)
    commands = {item["command"] for item in result}
    assert commands == {"@TalkSomethingNew", "@NewVoiceLine"}


def test_detect_new_speech_commands_shape_matches_schema():
    hints = ["Talk"]
    result = detect_new_speech_commands({"@TalkFoo": 1}, hints)
    assert result == [
        {
            "command": "@TalkFoo",
            "reason": "Command name contains speech-related keyword.",
            "severity": "high",
            "suggestedType": "dialogue",
        }
    ]


def test_detect_new_speech_commands_empty_when_no_unknown_commands():
    assert detect_new_speech_commands({}, ["Talk"]) == []


def test_detect_new_speech_commands_empty_when_no_hints_match():
    result = detect_new_speech_commands({"@Whatever": 1}, ["Talk", "Voice"])
    assert result == []


# ----------------------------------------------------------------
# determine_compatibility_status
# ----------------------------------------------------------------


def test_status_compatible_when_nothing_flagged():
    assert determine_compatibility_status() == "compatible"


def test_status_blocked_on_parse_error():
    assert determine_compatibility_status(has_parse_error=True) == "blocked"


def test_status_blocked_on_critical_branch_issue():
    assert determine_compatibility_status(has_critical_branch_issue=True) == "blocked"


def test_status_needs_update_on_new_speech_commands():
    assert (
        determine_compatibility_status(has_new_speech_commands=True) == "needs_update"
    )


def test_status_needs_update_on_changed_command_patterns():
    assert (
        determine_compatibility_status(has_changed_command_patterns=True)
        == "needs_update"
    )


def test_status_needs_update_on_high_severity_branch_issue():
    assert (
        determine_compatibility_status(has_high_severity_branch_issue=True)
        == "needs_update"
    )


def test_status_warning_on_unknown_commands():
    assert determine_compatibility_status(has_unknown_commands=True) == "warning"


def test_status_warning_on_unknown_character_ids():
    assert determine_compatibility_status(has_unknown_character_ids=True) == "warning"


def test_status_warning_on_control_chars_removed():
    assert determine_compatibility_status(has_control_chars_removed=True) == "warning"


def test_status_warning_on_case_variants():
    assert determine_compatibility_status(has_case_variants=True) == "warning"


def test_status_blocked_takes_priority_over_everything():
    assert (
        determine_compatibility_status(
            has_parse_error=True,
            has_new_speech_commands=True,
            has_unknown_commands=True,
        )
        == "blocked"
    )


def test_status_needs_update_takes_priority_over_warning():
    assert (
        determine_compatibility_status(
            has_new_speech_commands=True,
            has_unknown_commands=True,
            has_control_chars_removed=True,
        )
        == "needs_update"
    )
