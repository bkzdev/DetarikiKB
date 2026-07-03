#!/usr/bin/env python3
"""
Script Compatibility Checker
DKB Parser Phase 1 - Script_Compatibility_Check.md 準拠

Usage:
    # ディレクトリ指定 (再帰)
    python scripts/check_script_compatibility.py data/raw/

    # 単一ファイル指定
    python scripts/check_script_compatibility.py data/raw/main/example.dec

    # 出力先指定
    python scripts/check_script_compatibility.py data/raw/ --output data/reports/

    # キャラクター辞書指定
    python scripts/check_script_compatibility.py data/raw/ --characters reference/parser/characters_reference.json

Output:
    data/reports/script_compatibility_report.json
    data/reports/script_compatibility_report.md
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# プロジェクトルートを sys.path に追加
# (agents.parser.compatibility の共有判定ロジックを使うため。
# feature/compatibility-check-consistency: normalize_story.py --check-compat
# 経由の判定と揃えるため、新規会話コマンド候補判定・最終ステータス決定を
# agents/parser/compatibility.py と共有する)
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.parser.compatibility import (  # noqa: E402
    determine_compatibility_status,
    get_new_speech_hints,
    is_speech_candidate,
)

# ----------------------------------------------------------------
# Constants
# ----------------------------------------------------------------

SCHEMA_VERSION = "0.1"
DEFAULT_COMMANDS_CONFIG = (
    Path(__file__).parent.parent / "config" / "script_commands.yaml"
)
DEFAULT_CHARACTERS_PATH = (
    Path(__file__).parent.parent / "reference" / "parser" / "characters_reference.json"
)
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "reports"

# 制御文字パターン (U+0000-U+0008, U+000B, U+000C, U+000E-U+001F, U+007F)
CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# ハイフン行パターン (演出命令の補助指定)
HYPHEN_LINE_PATTERN = re.compile(r"^-\s+\S")

# $numX = ID
NUM_VAR_PATTERN = re.compile(r"^\$num(\d+)\s*=\s*(\d+)")
# $valueX = ID
VALUE_VAR_PATTERN = re.compile(r"^\$value(\d+)\s*=\s*(\d+)")
# @ScenarioCos slot id
SCENARIO_COS_PATTERN = re.compile(r"^@ScenarioCos\s+(\d+)\s+(\d+)")
# @ScenarioCosLoad slot var
SCENARIO_COS_LOAD_PATTERN = re.compile(r"^@ScenarioCosLoad\s+(\d+)\s+(\$[\w\d]+)")

# 日本語文字を含む行の検出 (会話本文の可能性)
JAPANESE_TEXT_PATTERN = re.compile(
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]"
)


# ----------------------------------------------------------------
# Config Loader
# ----------------------------------------------------------------


def load_command_config(config_path: Path) -> dict[str, Any]:
    """script_commands.yaml を読み込む"""
    if not config_path.exists():
        print(f"[警告] コマンド辞書が見つかりません: {config_path}", file=sys.stderr)
        return {}
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_characters(characters_path: Path) -> dict[str, str]:
    """characters_reference.json を読み込む。
    Returns: {sourceCharacterId: speakerName}
    """
    if not characters_path.exists():
        return {}
    try:
        with open(characters_path, encoding="utf-8") as f:
            data = json.load(f)
        # characters_reference.json 形式: {"1": "レイン", "26": "レイン", ...}
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        return {}
    except Exception as e:
        print(f"[警告] キャラクター辞書の読み込みに失敗しました: {e}", file=sys.stderr)
        return {}


def build_known_command_set(config: dict[str, Any]) -> set[str]:
    """既知コマンドの全セットを返す"""
    known: set[str] = set()
    skip_keys = {"case_variants", "new_speech_detection_hints"}
    for key, commands in config.items():
        if key in skip_keys:
            continue
        if isinstance(commands, list):
            for cmd in commands:
                if cmd:
                    known.add(cmd)
    return known


def build_case_variants_map(config: dict[str, Any]) -> dict[str, str]:
    """表記ゆれ → 正規形 のマップを返す"""
    return config.get("case_variants", {})


def get_speech_commands(config: dict[str, Any]) -> set[str]:
    """speech カテゴリのコマンドセットを返す"""
    return set(config.get("speech", []))


# get_new_speech_hints は agents/parser/compatibility.py に集約し、
# normalize_story.py --check-compat 経由の判定と共有する
# (feature/compatibility-check-consistency、上部のimportを参照)。


# ----------------------------------------------------------------
# File Scanner
# ----------------------------------------------------------------


def collect_files(
    target: Path, extensions: tuple[str, ...] = (".dec", ".txt")
) -> list[Path]:
    """ディレクトリまたは単一ファイルから対象ファイルを収集する"""
    if target.is_file():
        return [target]
    files: list[Path] = []
    for ext in extensions:
        files.extend(target.rglob(f"*{ext}"))
    return sorted(files)


# ----------------------------------------------------------------
# Single File Checker
# ----------------------------------------------------------------


class FileCompatibilityResult:
    """1ファイルの互換性チェック結果"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file_name = file_path.name
        self.line_count = 0
        self.parse_error: str | None = None

        # 検出項目
        self.unknown_commands: dict[str, dict] = {}  # command -> {count, sample_lines}
        self.new_speech_commands: list[dict] = []
        self.changed_command_patterns: list[dict] = []
        self.unknown_character_ids: dict[
            str, dict
        ] = {}  # char_id -> {count, sample_lines}
        self.branch_issues: list[dict] = []
        self.control_chars_removed: int = 0
        self.case_variants: dict[str, set] = defaultdict(
            set
        )  # normalized -> {variants}
        self.hyphen_option_lines: int = 0

        # 最終ステータス
        self.parser_compatibility: str = "compatible"


def check_file(
    file_path: Path,
    known_commands: set[str],
    speech_commands: set[str],
    case_variants_map: dict[str, str],
    speech_hints: list[str],
    char_map: dict[str, str],
) -> FileCompatibilityResult:
    """1ファイルを解析して互換性チェック結果を返す"""
    result = FileCompatibilityResult(file_path)

    # ファイル読み込み
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            raw_lines = f.readlines()
    except Exception as e:
        result.parse_error = str(e)
        result.parser_compatibility = "blocked"
        return result

    result.line_count = len(raw_lines)

    # 分岐スタック
    branch_stack: list[int] = []
    branch_options: list[str] = []
    last_command: str | None = None
    pending_speech: bool = False  # 直前が会話コマンドか

    for line_number, raw_line in enumerate(raw_lines, start=1):
        # 1. 制御文字除去
        cleaned = CONTROL_CHARS_PATTERN.sub("", raw_line)
        removed_count = len(raw_line) - len(cleaned)
        if removed_count > 0:
            result.control_chars_removed += removed_count
        line = cleaned.strip()

        # 2. 空行・コメントはスキップ
        if not line or line.startswith("//"):
            pending_speech = False
            continue

        # 3. ハイフン行 (演出補助)
        if HYPHEN_LINE_PATTERN.match(line):
            result.hyphen_option_lines += 1
            pending_speech = False
            continue

        # 4. 先頭トークンを取得
        parts = line.split()
        first_token = parts[0] if parts else ""

        # 5. 変数割り当て ($numX / $valueX) → キャラクターID検出
        num_match = NUM_VAR_PATTERN.match(line)
        if num_match:
            char_id = num_match.group(2)
            _record_character_id(result, char_id, char_map, line_number, line)
            pending_speech = False
            continue

        val_match = VALUE_VAR_PATTERN.match(line)
        if val_match:
            char_id = val_match.group(2)
            _record_character_id(result, char_id, char_map, line_number, line)
            pending_speech = False
            continue

        # 6. @ScenarioCos → キャラクターID検出
        sc_match = SCENARIO_COS_PATTERN.match(line)
        if sc_match:
            char_id = sc_match.group(2)
            _record_character_id(result, char_id, char_map, line_number, line)
            pending_speech = False
            continue

        # 7. @ScenarioCosLoad → スキップ (変数経由のため char_id 直接取得不可)
        if SCENARIO_COS_LOAD_PATTERN.match(line):
            pending_speech = False
            continue

        # 8. 分岐構文チェック
        if first_token == "branch":
            # branch の後に選択肢テキストが続くはず
            opts = line.replace("branch", "", 1).strip().split()
            branch_options = opts
            if not opts:
                result.branch_issues.append(
                    {
                        "type": "empty_branch",
                        "lineNumber": line_number,
                        "raw": line,
                        "severity": "medium",
                    }
                )
            pending_speech = False
            continue

        if first_token == "#if":
            branch_stack.append(line_number)
            pending_speech = False
            continue

        if first_token == "#elseif":
            if not branch_stack:
                result.branch_issues.append(
                    {
                        "type": "orphan_elseif",
                        "lineNumber": line_number,
                        "raw": line,
                        "severity": "high",
                    }
                )
            pending_speech = False
            continue

        if first_token == "#else":
            if not branch_stack:
                result.branch_issues.append(
                    {
                        "type": "orphan_else",
                        "lineNumber": line_number,
                        "raw": line,
                        "severity": "high",
                    }
                )
            pending_speech = False
            continue

        if first_token == "#endif":
            if branch_stack:
                branch_stack.pop()
            else:
                result.branch_issues.append(
                    {
                        "type": "orphan_endif",
                        "lineNumber": line_number,
                        "raw": line,
                        "severity": "high",
                    }
                )
            pending_speech = False
            continue

        if first_token.startswith("#"):
            # その他の # 系はスキップ
            pending_speech = False
            continue

        # 9. コマンド行の判定 (@ で始まる / 既知キーワード)
        is_command_line = (
            first_token.startswith("@")
            or first_token.startswith("$")
            or first_token in known_commands
            or NUM_VAR_PATTERN.match(line) is not None
        )

        if is_command_line:
            # 9a. 表記ゆれチェック
            normalized = case_variants_map.get(first_token)
            if normalized and normalized != first_token:
                result.case_variants[normalized].add(first_token)

            # 9b. 正規化後のコマンド名で既知チェック
            check_token = normalized if normalized else first_token

            if check_token not in known_commands:
                # 未知コマンド記録
                _record_unknown_command(result, first_token, line_number, line)

                # 新規会話コマンド候補検出
                if is_speech_candidate(first_token, speech_hints):
                    _record_new_speech_command(result, first_token, line_number, line)

            # 会話コマンドなら次の本文行に備えてフラグを立てる
            if check_token in speech_commands or first_token in speech_commands:
                pending_speech = True
            else:
                pending_speech = False

            last_command = first_token
            continue

        # 10. 本文行 (コマンド行でない)
        pending_speech = False

    # 11. 分岐スタックが残っている → missing #endif
    for open_line in branch_stack:
        result.branch_issues.append(
            {
                "type": "missing_endif",
                "lineNumber": open_line,
                "raw": "#if (unclosed)",
                "severity": "high",
            }
        )

    # 12. 最終ステータス決定
    result.parser_compatibility = _determine_compatibility(result)

    return result


def _record_character_id(
    result: FileCompatibilityResult,
    char_id: str,
    char_map: dict[str, str],
    line_number: int,
    raw: str,
) -> None:
    """キャラクターIDを記録 (未登録の場合 unknownCharacterIds へ)"""
    if char_id not in char_map:
        if char_id not in result.unknown_character_ids:
            result.unknown_character_ids[char_id] = {
                "sourceCharacterId": char_id,
                "count": 0,
                "sampleLines": [],
            }
        entry = result.unknown_character_ids[char_id]
        entry["count"] += 1
        if len(entry["sampleLines"]) < 3:
            entry["sampleLines"].append({"lineNumber": line_number, "raw": raw})


def _record_unknown_command(
    result: FileCompatibilityResult,
    command: str,
    line_number: int,
    raw: str,
) -> None:
    """未知コマンドを記録する"""
    if command not in result.unknown_commands:
        result.unknown_commands[command] = {
            "command": command,
            "count": 0,
            "sampleLines": [],
        }
    entry = result.unknown_commands[command]
    entry["count"] += 1
    if len(entry["sampleLines"]) < 3:
        entry["sampleLines"].append({"lineNumber": line_number, "raw": raw})


def _record_new_speech_command(
    result: FileCompatibilityResult,
    command: str,
    line_number: int,
    raw: str,
) -> None:
    """新規会話コマンド候補を記録する (重複は1件のみ)"""
    existing = {e["command"] for e in result.new_speech_commands}
    if command not in existing:
        result.new_speech_commands.append(
            {
                "command": command,
                "reason": "Command name contains speech-related keyword.",
                "severity": "high",
                "suggestedType": "dialogue",
                "sampleLine": {"lineNumber": line_number, "raw": raw},
            }
        )


def _determine_compatibility(result: FileCompatibilityResult) -> str:
    """チェック結果から互換性ステータスを決定する。

    判定ルール自体はagents/parser/compatibility.pyのdetermine_compatibility_status
    に集約し、normalize_story.py --check-compat経由 (agents/parser/normalizer.py)
    と共有する (feature/compatibility-check-consistency)。ここでは
    FileCompatibilityResultから必要なbool値を組み立てるだけ。
    """
    has_critical_branch = any(
        i.get("severity") == "critical" for i in result.branch_issues
    )
    has_high_branch = any(i.get("severity") in ("high",) for i in result.branch_issues)

    return determine_compatibility_status(
        has_parse_error=bool(result.parse_error),
        has_critical_branch_issue=has_critical_branch,
        has_new_speech_commands=bool(result.new_speech_commands),
        has_changed_command_patterns=bool(result.changed_command_patterns),
        has_high_severity_branch_issue=has_high_branch,
        has_unknown_commands=bool(result.unknown_commands),
        has_unknown_character_ids=bool(result.unknown_character_ids),
        has_control_chars_removed=result.control_chars_removed > 0,
        has_case_variants=bool(result.case_variants),
    )


# ----------------------------------------------------------------
# Report Builder
# ----------------------------------------------------------------


def build_json_report(
    target_files: list[Path],
    results: list[FileCompatibilityResult],
) -> dict[str, Any]:
    """JSON レポートを構築する"""
    # 全体ステータス決定
    STATUS_ORDER = ["compatible", "warning", "needs_update", "blocked"]
    overall_status = "compatible"
    for r in results:
        if STATUS_ORDER.index(r.parser_compatibility) > STATUS_ORDER.index(
            overall_status
        ):
            overall_status = r.parser_compatibility

    total_lines = sum(r.line_count for r in results)
    total_unknown_commands = sum(len(r.unknown_commands) for r in results)
    total_new_speech = sum(len(r.new_speech_commands) for r in results)
    total_unknown_char_ids = sum(len(r.unknown_character_ids) for r in results)
    total_control_chars = sum(r.control_chars_removed for r in results)

    # ファイルレポート
    file_reports = []
    for r in results:
        file_report: dict[str, Any] = {
            "file": r.file_name,
            "filePath": str(r.file_path),
            "parserCompatibility": r.parser_compatibility,
            "lineCount": r.line_count,
            "unknownCommands": list(r.unknown_commands.values()),
            "newSpeechCommands": r.new_speech_commands,
            "changedCommandPatterns": r.changed_command_patterns,
            "unknownCharacterIds": list(r.unknown_character_ids.values()),
            "branchIssues": r.branch_issues,
            "controlCharsRemoved": r.control_chars_removed,
            "caseVariants": [
                {
                    "normalizedCommand": normalized,
                    "variants": sorted(variants),
                    "count": len(variants),
                }
                for normalized, variants in r.case_variants.items()
            ],
            "hyphenOptionLines": r.hyphen_option_lines,
        }
        if r.parse_error:
            file_report["parseError"] = r.parse_error
        file_reports.append(file_report)

    report = {
        "schemaVersion": SCHEMA_VERSION,
        "documentType": "script_compatibility_report",
        "generatedAt": datetime.now(tz=timezone.utc).isoformat(),
        "targetFiles": [str(p) for p in target_files],
        "summary": {
            "totalFiles": len(results),
            "totalLines": total_lines,
            "parserCompatibility": overall_status,
            "unknownCommandCount": total_unknown_commands,
            "newSpeechCommandCount": total_new_speech,
            "unknownCharacterIdCount": total_unknown_char_ids,
            "controlCharsRemoved": total_control_chars,
        },
        "files": file_reports,
    }
    return report


def build_markdown_report(report: dict[str, Any]) -> str:
    """Markdown レポートを構築する"""
    lines: list[str] = []
    summary = report["summary"]
    generated_at = report.get("generatedAt", "")
    ts = generated_at[:19].replace("T", " ") if generated_at else ""

    lines.append("# Script Compatibility Report")
    lines.append("")
    lines.append(f"生成日時: {ts} UTC")
    lines.append("")

    # サマリー
    status = summary["parserCompatibility"]
    status_emoji = {
        "compatible": "✅",
        "warning": "⚠️",
        "needs_update": "🔶",
        "blocked": "🚫",
    }.get(status, "❓")
    lines.append("## サマリー")
    lines.append("")
    lines.append("| 項目 | 値 |")
    lines.append("|---|---|")
    lines.append(f"| 総合互換性 | {status_emoji} **{status}** |")
    lines.append(f"| ファイル数 | {summary['totalFiles']} |")
    lines.append(f"| 総行数 | {summary['totalLines']} |")
    lines.append(f"| 未知コマンド種類 | {summary['unknownCommandCount']} |")
    lines.append(f"| 新規会話コマンド候補 | {summary['newSpeechCommandCount']} |")
    lines.append(f"| 未登録キャラクターID | {summary['unknownCharacterIdCount']} |")
    lines.append(f"| 制御文字除去件数 | {summary['controlCharsRemoved']} |")
    lines.append("")

    # ファイル別
    lines.append("## ファイル別結果")
    lines.append("")
    lines.append(
        "| ファイル | 互換性 | 行数 | 未知Cmd | 新規会話 | 未登録ID | 制御文字 |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for f in report["files"]:
        st = f["parserCompatibility"]
        em = {
            "compatible": "✅",
            "warning": "⚠️",
            "needs_update": "🔶",
            "blocked": "🚫",
        }.get(st, "❓")
        lines.append(
            f"| {f['file']} | {em} {st} | {f['lineCount']} | "
            f"{len(f['unknownCommands'])} | {len(f['newSpeechCommands'])} | "
            f"{len(f['unknownCharacterIds'])} | {f['controlCharsRemoved']} |"
        )
    lines.append("")

    # 新規会話コマンド候補 (全ファイル)
    all_new_speech: dict[str, dict] = {}
    for f in report["files"]:
        for cmd in f["newSpeechCommands"]:
            if cmd["command"] not in all_new_speech:
                all_new_speech[cmd["command"]] = cmd
    if all_new_speech:
        lines.append("## 🔶 新規会話コマンド候補")
        lines.append("")
        lines.append(
            "これらのコマンドは本文抽出に影響する可能性があります。辞書への追加を検討してください。"
        )
        lines.append("")
        for cmd, info in all_new_speech.items():
            lines.append(
                f"- `{cmd}` — {info['reason']} (severity: **{info['severity']}**)"
            )
        lines.append("")

    # 未知コマンド (全ファイル集計)
    all_unknown: dict[str, dict] = {}
    for f in report["files"]:
        for cmd_info in f["unknownCommands"]:
            cmd = cmd_info["command"]
            if cmd not in all_unknown:
                all_unknown[cmd] = {"command": cmd, "count": 0, "sampleLines": []}
            all_unknown[cmd]["count"] += cmd_info["count"]
            if len(all_unknown[cmd]["sampleLines"]) < 2:
                all_unknown[cmd]["sampleLines"].extend(cmd_info.get("sampleLines", []))
    if all_unknown:
        lines.append("## ⚠️ 未知コマンド一覧")
        lines.append("")
        lines.append("| コマンド | 出現回数 | サンプル行 |")
        lines.append("|---|---:|---|")
        for cmd, info in sorted(all_unknown.items(), key=lambda x: -x[1]["count"]):
            sample = ""
            if info["sampleLines"]:
                sl = info["sampleLines"][0]
                sample = f"L{sl['lineNumber']}: `{sl['raw'][:60]}`"
            lines.append(f"| `{cmd}` | {info['count']} | {sample} |")
        lines.append("")

    # 未登録キャラクターID (全ファイル集計)
    all_unknown_chars: dict[str, dict] = {}
    for f in report["files"]:
        for char_info in f["unknownCharacterIds"]:
            cid = char_info["sourceCharacterId"]
            if cid not in all_unknown_chars:
                all_unknown_chars[cid] = {
                    "sourceCharacterId": cid,
                    "count": 0,
                    "files": set(),
                    "sampleLines": [],
                }
            all_unknown_chars[cid]["count"] += char_info["count"]
            all_unknown_chars[cid]["files"].add(f["file"])
            if len(all_unknown_chars[cid]["sampleLines"]) < 2:
                all_unknown_chars[cid]["sampleLines"].extend(
                    char_info.get("sampleLines", [])
                )
    if all_unknown_chars:
        lines.append("## ⚠️ 未登録キャラクターID")
        lines.append("")
        lines.append("| キャラクターID | 出現回数 | サンプル行 |")
        lines.append("|---|---:|---|")
        for cid, info in sorted(
            all_unknown_chars.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0
        ):
            sample = ""
            if info["sampleLines"]:
                sl = info["sampleLines"][0]
                sample = f"L{sl['lineNumber']}: `{sl['raw'][:60]}`"
            lines.append(f"| `{cid}` | {info['count']} | {sample} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*このレポートは DKB Script Compatibility Checker が自動生成しました。*"
    )
    lines.append("")

    return "\n".join(lines)


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DKB Script Compatibility Checker — Raw Script の互換性をチェックします",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python scripts/check_script_compatibility.py data/raw/
  python scripts/check_script_compatibility.py data/raw/main/example.dec
  python scripts/check_script_compatibility.py data/raw/ --output data/reports/ --characters reference/parser/characters_reference.json
""",
    )
    parser.add_argument(
        "target",
        help="チェック対象のファイルまたはディレクトリ",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"レポート出力先ディレクトリ (デフォルト: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--commands",
        "-c",
        default=str(DEFAULT_COMMANDS_CONFIG),
        help=f"コマンド辞書YAMLのパス (デフォルト: {DEFAULT_COMMANDS_CONFIG})",
    )
    parser.add_argument(
        "--characters",
        default=str(DEFAULT_CHARACTERS_PATH),
        help=f"キャラクター辞書JSONのパス (デフォルト: {DEFAULT_CHARACTERS_PATH})",
    )
    parser.add_argument(
        "--no-md",
        action="store_true",
        help="Markdownレポートを出力しない",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    target = Path(args.target)
    if not target.exists():
        print(f"[エラー] 対象が見つかりません: {target}", file=sys.stderr)
        return 1

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 設定読み込み
    config = load_command_config(Path(args.commands))
    char_map = load_characters(Path(args.characters))
    known_commands = build_known_command_set(config)
    case_variants_map = build_case_variants_map(config)
    speech_commands = get_speech_commands(config)
    speech_hints = get_new_speech_hints(config)

    if not args.quiet:
        print("[DKB] Script Compatibility Checker")
        print(f"[DKB] 対象: {target}")
        print(f"[DKB] 既知コマンド数: {len(known_commands)}")
        print(f"[DKB] 登録キャラクター数: {len(char_map)}")

    # ファイル収集
    files = collect_files(target)
    if not files:
        print(f"[警告] 対象ファイルが見つかりませんでした: {target}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"[DKB] 対象ファイル数: {len(files)}")

    # チェック実行
    results: list[FileCompatibilityResult] = []
    for file_path in files:
        if not args.quiet:
            print(f"  チェック中: {file_path.name}")
        result = check_file(
            file_path,
            known_commands,
            speech_commands,
            case_variants_map,
            speech_hints,
            char_map,
        )
        results.append(result)

    # レポート生成
    json_report = build_json_report(files, results)
    md_report = build_markdown_report(json_report)

    # JSON 出力
    json_path = output_dir / "script_compatibility_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)

    # Markdown 出力
    if not args.no_md:
        md_path = output_dir / "script_compatibility_report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_report)

    # サマリー表示
    summary = json_report["summary"]
    status = summary["parserCompatibility"]
    status_label = {
        "compatible": "compatible",
        "warning": "warning",
        "needs_update": "needs_update",
        "blocked": "blocked",
    }.get(status, status)

    print("")
    print(f"[DKB] 総合互換性: {status_label}")
    print(f"[DKB] 未知コマンド種類: {summary['unknownCommandCount']}")
    print(f"[DKB] 新規会話コマンド候補: {summary['newSpeechCommandCount']}")
    print(f"[DKB] 未登録キャラクターID: {summary['unknownCharacterIdCount']}")
    print(f"[DKB] 制御文字除去件数: {summary['controlCharsRemoved']}")
    print(f"[DKB] JSON レポート: {json_path}")
    if not args.no_md:
        print(f"[DKB] MD レポート:   {md_path}")

    # 終了コード: blocked → 2, needs_update → 1, それ以外 → 0
    if status == "blocked":
        return 2
    if status == "needs_update":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
