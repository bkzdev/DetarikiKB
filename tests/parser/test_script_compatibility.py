"""
tests/parser/test_script_compatibility.py
互換性チェックのユニットテスト
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts.check_script_compatibility import (
    check_file,
    collect_files,
    compile_name_patterns,
    load_characters,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
CHECK_COMPAT_SCRIPT = PROJECT_ROOT / "scripts" / "check_script_compatibility.py"


@pytest.fixture
def dummy_config():
    return {
        "speech_commands": {
            "@ChTalk",
            "@ChTalkMono",
            "@ChTalkSoundOff",
            "@ChTalkSoundOffMono",
            "@ChTalkName",
        },
        "known_commands": {
            "@ChTalk",
            "@ChTalkMono",
            "@ChTalkSoundOff",
            "@ChTalkSoundOffMono",
            "@ChTalkName",
            "@ScenarioCos",
            "@ScenarioCosLoad",
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
            "@Visible",
            "@VisibleOff",
        },
        "case_variants_map": {"@Visibleoff": "@VisibleOff"},
        "speech_hints": ["Talk", "Mono", "Name"],
        "char_map": {"26": "レイン", "29": "レイヴェル", "1": "赤城陽菜"},
    }


def test_basic_compatibility(dummy_config, tmp_path):
    # テスト用スクリプトの作成
    script_content = """$num0 = 26
@ScenarioCos 1 29
@ChTalk 0
こんにちは。
msg
ナレーションテキスト。
branch A B
#if $branch
@ChTalk 0
選択肢Aのセリフ
#else
@ChTalk 0
選択肢Bのセリフ
#endif
"""
    script_path = tmp_path / "basic.dec"
    script_path.write_text(script_content, encoding="utf-8")

    result = check_file(
        file_path=script_path,
        known_commands=dummy_config["known_commands"],
        speech_commands=dummy_config["speech_commands"],
        case_variants_map=dummy_config["case_variants_map"],
        speech_hints=dummy_config["speech_hints"],
        char_map=dummy_config["char_map"],
    )

    assert result.parser_compatibility == "compatible"
    assert len(result.unknown_commands) == 0
    assert len(result.unknown_character_ids) == 0
    assert len(result.new_speech_commands) == 0
    assert len(result.branch_issues) == 0


def test_unknown_command_and_char(dummy_config, tmp_path):
    # 未知コマンド、未登録キャラクターIDを含むスクリプト
    script_content = """$num0 = 999
@UnknownCommand 1 2 3
@ChTalk 0
セリフ
"""
    script_path = tmp_path / "unknown.dec"
    script_path.write_text(script_content, encoding="utf-8")

    result = check_file(
        file_path=script_path,
        known_commands=dummy_config["known_commands"],
        speech_commands=dummy_config["speech_commands"],
        case_variants_map=dummy_config["case_variants_map"],
        speech_hints=dummy_config["speech_hints"],
        char_map=dummy_config["char_map"],
    )

    # warningになるはず
    assert result.parser_compatibility == "warning"
    assert "@UnknownCommand" in result.unknown_commands
    assert "999" in result.unknown_character_ids


def test_new_speech_command(dummy_config, tmp_path):
    # 新規会話コマンド候補を含むスクリプト
    script_content = """@NewTalkCommand 0
新しい会話コマンドのテスト。
"""
    script_path = tmp_path / "new_speech.dec"
    script_path.write_text(script_content, encoding="utf-8")

    result = check_file(
        file_path=script_path,
        known_commands=dummy_config["known_commands"],
        speech_commands=dummy_config["speech_commands"],
        case_variants_map=dummy_config["case_variants_map"],
        speech_hints=dummy_config["speech_hints"],
        char_map=dummy_config["char_map"],
    )

    # needs_updateになるはず
    assert result.parser_compatibility == "needs_update"
    assert any(c["command"] == "@NewTalkCommand" for c in result.new_speech_commands)


def test_branch_issues(dummy_config, tmp_path):
    # 分岐構文に異常があるスクリプト
    script_content = """branch A B
#if $branch
@ChTalk 0
テキスト
"""
    script_path = tmp_path / "branch_err.dec"
    script_path.write_text(script_content, encoding="utf-8")

    result = check_file(
        file_path=script_path,
        known_commands=dummy_config["known_commands"],
        speech_commands=dummy_config["speech_commands"],
        case_variants_map=dummy_config["case_variants_map"],
        speech_hints=dummy_config["speech_hints"],
        char_map=dummy_config["char_map"],
    )

    # needs_update になるか確認（branch_issues の severity によるが、通常 high 以上）
    assert result.parser_compatibility in ("needs_update", "blocked")
    assert any(issue["type"] == "missing_endif" for issue in result.branch_issues)


# ----------------------------------------------------------------
# collect_files: ファイル名フィルタ
# ----------------------------------------------------------------


def _touch(path: Path) -> Path:
    path.write_text("", encoding="utf-8")
    return path


@pytest.fixture
def mixed_dir(tmp_path):
    """本編系・演出系が混在する合成ディレクトリ"""
    names = [
        "series-episode1.dec",
        "series-episode2.dec",
        "series-episode_EX1.dec",
        "series-main1_tutorial.dec",
        "series-Surprise_3.dec",
        "series-H_scene_01.dec",
        "series-camera_test.dec",
        "series-finish_01.dec",
        "series-spine_test.dec",
        "series-VR_intro.dec",
    ]
    for name in names:
        _touch(tmp_path / name)
    return tmp_path


def test_collect_files_no_patterns_returns_all_and_no_summary(mixed_dir):
    # 未指定時は従来どおり全件走査し、フィルタサマリーは付与されない (後方互換)
    files, summary = collect_files(mixed_dir)

    assert len(files) == 10
    assert summary is None


def test_collect_files_single_include_pattern(mixed_dir):
    patterns = compile_name_patterns([r"-episode\d+\.dec$"])
    files, summary = collect_files(mixed_dir, include_patterns=patterns)

    names = sorted(f.name for f in files)
    assert names == ["series-episode1.dec", "series-episode2.dec"]
    assert summary is not None
    assert summary.total_scanned == 10
    assert summary.collected_count == 2
    assert summary.excluded_count == 8
    assert summary.include_patterns == [r"-episode\d+\.dec$"]
    assert summary.exclude_patterns == []


def test_collect_files_multiple_include_patterns_or_condition(mixed_dir):
    patterns = compile_name_patterns(
        [
            r"-episode\d+\.dec$",
            r"-episode_EX\d+\.dec$",
            r"-main\d+(_tutorial\d*)?(\s*#\d+)?\.dec$",
            r"-Surprise_\d+\.dec$",
        ]
    )
    files, summary = collect_files(mixed_dir, include_patterns=patterns)

    names = {f.name for f in files}
    assert names == {
        "series-episode1.dec",
        "series-episode2.dec",
        "series-episode_EX1.dec",
        "series-main1_tutorial.dec",
        "series-Surprise_3.dec",
    }
    assert summary.collected_count == 5
    assert summary.excluded_count == 5


def test_collect_files_exclude_pattern(mixed_dir):
    # includeなし、excludeのみ: 演出系のうちH_sceneのみ除外
    patterns = compile_name_patterns([r"H_scene"])
    files, summary = collect_files(mixed_dir, exclude_patterns=patterns)

    names = {f.name for f in files}
    assert "series-H_scene_01.dec" not in names
    assert len(files) == 9
    assert summary.total_scanned == 10
    assert summary.collected_count == 9
    assert summary.excluded_count == 1
    assert summary.include_patterns == []
    assert summary.exclude_patterns == ["H_scene"]


def test_collect_files_include_and_exclude_combined(mixed_dir):
    # includeで本編系に絞り込んだ後、excludeで一部をさらに除外する
    include_patterns = compile_name_patterns([r"-episode\d+\.dec$", r"-Surprise_\d+"])
    exclude_patterns = compile_name_patterns([r"episode2"])
    files, summary = collect_files(
        mixed_dir, include_patterns=include_patterns, exclude_patterns=exclude_patterns
    )

    names = sorted(f.name for f in files)
    assert names == ["series-Surprise_3.dec", "series-episode1.dec"]
    assert summary.collected_count == 2


def test_collect_files_matches_basename_only(tmp_path):
    # ディレクトリ名がパターンにマッチしても、ファイル名自体がマッチしなければ
    # 対象にならないこと (マッチ対象はbasenameのみ)
    sub_dir = tmp_path / "episode1_dir"
    sub_dir.mkdir()
    _touch(sub_dir / "unrelated.dec")

    patterns = compile_name_patterns([r"^episode1"])
    files, summary = collect_files(tmp_path, include_patterns=patterns)

    assert files == []
    assert summary.total_scanned == 1
    assert summary.collected_count == 0


def test_collect_files_single_file_target_unaffected_by_extensions(tmp_path):
    # 単一ファイル指定時は、フィルタ未指定なら常にそのファイルを返す
    file_path = _touch(tmp_path / "series-episode1.dec")

    files, summary = collect_files(file_path)

    assert files == [file_path]
    assert summary is None


def test_compile_name_patterns_empty_or_none_returns_empty_list():
    assert compile_name_patterns(None) == []
    assert compile_name_patterns([]) == []


def test_compile_name_patterns_invalid_regex_raises():
    with pytest.raises(re.error):
        compile_name_patterns(["("])


# ----------------------------------------------------------------
# CLI: --include-name-pattern / --exclude-name-pattern
# ----------------------------------------------------------------


def test_cli_invalid_regex_exits_with_config_error_code(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(CHECK_COMPAT_SCRIPT),
            str(tmp_path),
            "--include-name-pattern",
            "(",
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "不正な正規表現" in result.stderr


def test_cli_default_behavior_unchanged_without_patterns(tmp_path):
    script_path = tmp_path / "series-episode1.dec"
    script_path.write_text("$num0 = 26\n@ChTalk 0\nこんにちは。\n", encoding="utf-8")
    output_dir = tmp_path / "reports"

    result = subprocess.run(
        [
            sys.executable,
            str(CHECK_COMPAT_SCRIPT),
            str(tmp_path),
            "--output",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode in (0, 1)

    import json

    report = json.loads(
        (output_dir / "script_compatibility_report.json").read_text(encoding="utf-8")
    )
    assert "nameFilter" not in report["summary"]


def test_cli_report_includes_name_filter_summary_when_pattern_applied(tmp_path):
    (tmp_path / "series-episode1.dec").write_text(
        "$num0 = 26\n@ChTalk 0\nこんにちは。\n", encoding="utf-8"
    )
    (tmp_path / "series-H_scene_01.dec").write_text("camera 0\n", encoding="utf-8")
    output_dir = tmp_path / "reports"

    result = subprocess.run(
        [
            sys.executable,
            str(CHECK_COMPAT_SCRIPT),
            str(tmp_path),
            # 正規表現が "-" で始まるため "=" 付き形式で渡す
            # (argparseが値を別オプションと誤認するのを避けるため)
            r"--include-name-pattern=-episode\d+\.dec$",
            "--output",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode in (0, 1), result.stderr

    import json

    report = json.loads(
        (output_dir / "script_compatibility_report.json").read_text(encoding="utf-8")
    )
    name_filter = report["summary"]["nameFilter"]
    assert name_filter["totalScanned"] == 2
    assert name_filter["collectedCount"] == 1
    assert name_filter["excludedCount"] == 1
    assert name_filter["includePatterns"] == [r"-episode\d+\.dec$"]
    assert name_filter["excludePatterns"] == []
    assert len(report["files"]) == 1
    assert report["files"][0]["file"] == "series-episode1.dec"


# ----------------------------------------------------------------
# load_characters: 拡張子による形式自動判別
# (knowledge/dictionaries/characters.yaml 形式 / レガシー
#  characters_reference.json 形式、scripts/normalize_story.py --characters
#  と同じ方式)
# ----------------------------------------------------------------


def test_load_characters_yaml_format(tmp_path):
    # knowledge/dictionaries/characters.yaml 相当の合成fixture
    characters_path = tmp_path / "characters.yaml"
    characters_path.write_text(
        yaml.safe_dump(
            {
                "schemaVersion": "0.1",
                "characters": [
                    {
                        "sourceCharacterId": "1",
                        "characterId": "CHAR_TEST_ONE",
                        "displayName": "テスト一号",
                        "aliases": [],
                        "status": "confirmed",
                        "notes": None,
                    },
                    {
                        "sourceCharacterId": "2",
                        "characterId": None,
                        "displayName": "テスト二号",
                        "aliases": [],
                        "status": "name_only",
                        "notes": None,
                    },
                ],
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    char_map = load_characters(characters_path)

    assert char_map == {"1": "テスト一号", "2": "テスト二号"}


def test_load_characters_json_format_legacy(tmp_path):
    # characters_reference.json 相当の合成fixture (後方互換)
    characters_path = tmp_path / "characters_reference.json"
    characters_path.write_text(
        '{"1": "レイン", "26": "レイン", "29": "レイヴェル"}',
        encoding="utf-8",
    )

    char_map = load_characters(characters_path)

    assert char_map == {"1": "レイン", "26": "レイン", "29": "レイヴェル"}


def test_load_characters_nonexistent_path_returns_empty(tmp_path):
    assert load_characters(tmp_path / "does_not_exist.yaml") == {}
    assert load_characters(tmp_path / "does_not_exist.json") == {}


def test_load_characters_invalid_yaml_returns_empty(tmp_path, capsys):
    characters_path = tmp_path / "broken.yaml"
    # 不正なYAML (閉じられていないflow mapping)
    characters_path.write_text("characters: [1, 2,\n", encoding="utf-8")

    char_map = load_characters(characters_path)

    assert char_map == {}
    captured = capsys.readouterr()
    assert "警告" in captured.err
