"""
DKB Parser - Compatibility Check Shared Logic
scripts/check_script_compatibility.py（単体実行）と
agents/parser/normalizer.py（normalize_story.py --check-compat経由で
Normalized Story JSONに埋め込まれるcompatibilityReport）の判定が
食い違っていた問題（TASKS.md記載、feature/script-command-coverage時点で
判明）を解消するために、両経路で共有する判定ロジックをここに集約する。

**大規模リファクタはしない**: agents/parser/parser.py の
DIRECTION_TYPE_MAP / STAGE_DIRECTION_COMMANDS、agents/parser/tokenizer.py
の KEYWORD_TOKENS は引き続きハードコードのまま変更しない（実際の
ブロック分類ロジックには一切手を入れない）。ここで共通化するのは、
「どのコマンドが新規会話コマンド候補か」「最終的な互換性ステータスは
compatible/warning/needs_update/blockedのどれか」という**判定ルールのみ**
であり、両経路が同じ入力に対して同じ結論を出せるようにする。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_COMMANDS_CONFIG = (
    Path(__file__).parent.parent.parent / "config" / "script_commands.yaml"
)


def load_command_config(path: str | Path) -> dict[str, Any]:
    """config/script_commands.yaml を読み込む。

    ファイルが無ければ空dictを返す（呼び出し側で警告するかは呼び出し側の
    責任とする。scripts/check_script_compatibility.pyの既存
    load_command_configと同じ方針）。
    """
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_new_speech_hints(config: dict[str, Any]) -> list[str]:
    """新規会話コマンド候補検出ヒント
    (new_speech_detection_hints.name_contains) を返す。"""
    hints = config.get("new_speech_detection_hints", {})
    return hints.get("name_contains", [])


def is_speech_candidate(command: str, hints: list[str]) -> bool:
    """コマンド名が会話コマンド候補かどうか判定する
    (scripts/check_script_compatibility.pyの_is_speech_candidateと同一ロジック)。
    """
    for hint in hints:
        if hint in command:
            return True
    return False


def detect_new_speech_commands(
    unknown_commands: dict[str, int],
    hints: list[str],
) -> list[dict[str, Any]]:
    """既に「未知」と判定済みのコマンド一覧 (command -> count) のうち、
    会話コマンド候補ヒントに合致するものを抽出する。

    scripts/check_script_compatibility.py・agents/parser/normalizer.py
    どちらも「まずunknown commandを検出し、その中から会話コマンド候補を
    絞り込む」という順序で判定しているため、両者はこの関数を共有できる
    (このPRで初めてnormalizer.py側の判定にも使うようになった。
    以前はnewSpeechCommandsが常に空配列でハードコードされていた)。

    戻り値の各要素はschemas/story.schema.jsonのCompatibilityReport.
    newSpeechCommands (command/reason/severity/suggestedType) と同じ形。
    """
    detected: list[dict[str, Any]] = []
    for command in unknown_commands:
        if is_speech_candidate(command, hints):
            detected.append(
                {
                    "command": command,
                    "reason": "Command name contains speech-related keyword.",
                    "severity": "high",
                    "suggestedType": "dialogue",
                }
            )
    return detected


def determine_compatibility_status(
    *,
    has_parse_error: bool = False,
    has_critical_branch_issue: bool = False,
    has_new_speech_commands: bool = False,
    has_changed_command_patterns: bool = False,
    has_high_severity_branch_issue: bool = False,
    has_unknown_commands: bool = False,
    has_unknown_character_ids: bool = False,
    has_control_chars_removed: bool = False,
    has_case_variants: bool = False,
) -> str:
    """互換性ステータス (compatible/warning/needs_update/blocked) を決定する。

    scripts/check_script_compatibility.pyの_determine_compatibilityと
    完全に同じ判定順序・条件をFileCompatibilityResult非依存の形にした
    もの。呼び出し側 (check_script_compatibility.py・normalizer.py) は
    それぞれが持つデータからこれらのbool値を組み立てて渡す。

    agents/parser/のStoryParserは現状branch_issues (孤立した#elseif/
    #else/#endif、閉じられていない#if等) やcase_variants (表記ゆれの
    使用箇所) を追跡していないため、Normalizer側からは
    has_critical_branch_issue/has_high_severity_branch_issue/
    has_case_variantsは常にFalseで呼び出される
    (TASKS.md「保証するフィールド」参照、既知の非対称性)。
    """
    if has_parse_error:
        return "blocked"
    if has_critical_branch_issue:
        return "blocked"

    if has_new_speech_commands:
        return "needs_update"
    if has_changed_command_patterns:
        return "needs_update"
    if has_high_severity_branch_issue:
        return "needs_update"

    if has_unknown_commands:
        return "warning"
    if has_unknown_character_ids:
        return "warning"
    if has_control_chars_removed:
        return "warning"
    if has_case_variants:
        return "warning"

    return "compatible"
