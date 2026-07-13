#!/usr/bin/env python3
r"""
Script Compatibility Checker
DKB Parser Phase 1 - Script_Compatibility_Check.md 準拠

Usage:
    # ディレクトリ指定 (再帰)
    python scripts/check_script_compatibility.py data/raw/

    # 単一ファイル指定
    python scripts/check_script_compatibility.py data/raw/main/example.dec

    # 出力先指定
    python scripts/check_script_compatibility.py data/raw/ --output data/reports/

    # キャラクター辞書指定 (既定は knowledge/dictionaries/characters.yaml。
    # 拡張子で形式を自動判別する: .yaml/.yml は正規辞書形式、
    # .json はレガシー characters_reference.json 形式)
    python scripts/check_script_compatibility.py data/raw/ \
        --characters knowledge/dictionaries/characters.yaml
    python scripts/check_script_compatibility.py data/raw/ \
        --characters reference/parser/characters_reference.json

    # ファイル名フィルタ (本編系scriptのみを対象にする例)
    # 未指定時は従来どおり data/raw/ 配下の全 .dec/.txt を走査する。
    # 注意: 正規表現が "-" で始まる場合、argparseに別オプションと誤認されない
    # よう "--include-name-pattern=<regex>" の "=" 付き形式で指定すること。
    python scripts/check_script_compatibility.py data/raw/ \
        --include-name-pattern="-episode\d+\.dec$" \
        --include-name-pattern="-episode_EX\d+\.dec$" \
        --include-name-pattern="-main\d+(_tutorial\d*)?(\s*#\d+)?\.dec$" \
        --include-name-pattern="-Surprise_\d+\.dec$"

    # 除外パターンとの併用 (includeの後に適用される)
    python scripts/check_script_compatibility.py data/raw/ \
        --include-name-pattern="-episode\d+\.dec$" \
        --exclude-name-pattern="_debug"

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

from agents.parser.character_dictionary import (  # noqa: E402
    load_character_dictionary,
)
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
    Path(__file__).parent.parent / "knowledge" / "dictionaries" / "characters.yaml"
)
# レガシー辞書 (読み取り専用、CLAUDE.md記載の通り直接改造しない)。
# 拡張子が .json の場合の後方互換読み込み先としてのみ参照する
# (scripts/normalize_story.py の LEGACY_CHARACTERS_PATH と同じ位置づけ)。
LEGACY_CHARACTERS_PATH = (
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
    """キャラクター辞書を読み込む。拡張子で形式を自動判別する
    (scripts/normalize_story.py --characters と同じ方式)。
    Returns: {sourceCharacterId: speakerName}

    - `.yaml`/`.yml`: `knowledge/dictionaries/characters.yaml` 形式
      (`characters[].sourceCharacterId`/`displayName`、
      `agents/parser/character_dictionary.py` の
      `load_character_dictionary` を再利用する)
    - `.json`: レガシー `characters_reference.json` 形式
      (`{"1": "レイン", "26": "レイン", ...}`のフラットな辞書)
    """
    if not characters_path.exists():
        return {}

    suffix = characters_path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        try:
            entries = load_character_dictionary(characters_path)
        except Exception as e:
            print(
                f"[警告] キャラクター辞書の読み込みに失敗しました: {e}",
                file=sys.stderr,
            )
            return {}
        return {
            entry.source_character_id: entry.display_name
            for entry in entries
            if entry.source_character_id
        }

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


class NameFilterSummary:
    """ファイル名フィルタ (--include-name-pattern/--exclude-name-pattern)
    適用結果のサマリー。未指定時 (フィルタなし) は生成されない。
    """

    def __init__(
        self,
        include_patterns: list[str],
        exclude_patterns: list[str],
        total_scanned: int,
        collected_count: int,
    ) -> None:
        self.include_patterns = include_patterns
        self.exclude_patterns = exclude_patterns
        self.total_scanned = total_scanned
        self.collected_count = collected_count
        self.excluded_count = total_scanned - collected_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "includePatterns": self.include_patterns,
            "excludePatterns": self.exclude_patterns,
            "totalScanned": self.total_scanned,
            "collectedCount": self.collected_count,
            "excludedCount": self.excluded_count,
        }


def compile_name_patterns(
    pattern_strings: list[str] | None,
) -> list[re.Pattern[str]]:
    """パターン文字列のリストをコンパイル済み正規表現のリストへ変換する。

    不正な正規表現があった場合は re.error をそのまま送出する
    (呼び出し側でconfig errorとして扱い、exit code 2にする)。
    """
    if not pattern_strings:
        return []
    return [re.compile(p) for p in pattern_strings]


def collect_files(
    target: Path,
    extensions: tuple[str, ...] = (".dec", ".txt"),
    include_patterns: list[re.Pattern[str]] | None = None,
    exclude_patterns: list[re.Pattern[str]] | None = None,
) -> tuple[list[Path], "NameFilterSummary | None"]:
    """ディレクトリまたは単一ファイルから対象ファイルを収集する。

    include_patterns/exclude_patternsはファイル名 (basename、フルパスではない)
    に対して re.search で判定する。
    - include_patterns: いずれか1つ以上にマッチするファイルのみを対象とする
      (複数指定はOR条件)。
    - exclude_patterns: いずれか1つでもマッチするファイルを除外する。
      include適用後に適用される。
    include_patterns/exclude_patternsのいずれも指定されない (Noneまたは空)
    場合は、従来どおり全件を走査し、戻り値の NameFilterSummary は None になる
    (後方互換: 既存の挙動・exit code・レポート形式は不変)。
    """
    if target.is_file():
        candidates = [target]
    else:
        candidates = []
        for ext in extensions:
            candidates.extend(target.rglob(f"*{ext}"))
        candidates = sorted(candidates)

    if not include_patterns and not exclude_patterns:
        return candidates, None

    total_scanned = len(candidates)
    collected: list[Path] = []
    for file_path in candidates:
        name = file_path.name
        if include_patterns and not any(p.search(name) for p in include_patterns):
            continue
        if exclude_patterns and any(p.search(name) for p in exclude_patterns):
            continue
        collected.append(file_path)

    summary = NameFilterSummary(
        include_patterns=[p.pattern for p in (include_patterns or [])],
        exclude_patterns=[p.pattern for p in (exclude_patterns or [])],
        total_scanned=total_scanned,
        collected_count=len(collected),
    )
    return collected, summary


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


def _strip_control_chars(raw_line: str, result: FileCompatibilityResult) -> str:
    """制御文字を除去し、除去件数をresultへ加算した上でstrip済みの行を返す"""
    cleaned = CONTROL_CHARS_PATTERN.sub("", raw_line)
    removed_count = len(raw_line) - len(cleaned)
    if removed_count > 0:
        result.control_chars_removed += removed_count
    return cleaned.strip()


def _check_character_id_line(
    line: str,
    line_number: int,
    char_map: dict[str, str],
    result: FileCompatibilityResult,
) -> bool:
    """$numX / $valueX / @ScenarioCos / @ScenarioCosLoad 行を処理する。
    処理済み (これ以上の分類が不要) ならTrueを返す。
    """
    num_match = NUM_VAR_PATTERN.match(line)
    if num_match:
        _record_character_id(result, num_match.group(2), char_map, line_number, line)
        return True

    val_match = VALUE_VAR_PATTERN.match(line)
    if val_match:
        _record_character_id(result, val_match.group(2), char_map, line_number, line)
        return True

    sc_match = SCENARIO_COS_PATTERN.match(line)
    if sc_match:
        _record_character_id(result, sc_match.group(2), char_map, line_number, line)
        return True

    if SCENARIO_COS_LOAD_PATTERN.match(line):
        # 変数経由のため char_id 直接取得不可
        return True

    return False


def _check_branch_keyword(
    first_token: str,
    line: str,
    line_number: int,
    result: FileCompatibilityResult,
) -> bool:
    """branch キーワード行 (選択肢) をチェックする。処理済みならTrueを返す。"""
    if first_token != "branch":
        return False

    # branch の後に選択肢テキストが続くはず
    opts = line.replace("branch", "", 1).strip().split()
    if not opts:
        result.branch_issues.append(
            {
                "type": "empty_branch",
                "lineNumber": line_number,
                "raw": line,
                "severity": "medium",
            }
        )
    return True


def _check_conditional_directive(
    first_token: str,
    line: str,
    line_number: int,
    branch_stack: list[int],
    result: FileCompatibilityResult,
) -> bool:
    """#if/#elseif/#else/#endif/その他#系の構文チェックを行う。
    処理済みならTrueを返す。
    """
    if first_token == "#if":
        branch_stack.append(line_number)
        return True

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
        return True

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
        return True

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
        return True

    if first_token.startswith("#"):
        # その他の # 系はスキップ
        return True

    return False


def _check_branch_syntax(
    first_token: str,
    line: str,
    line_number: int,
    branch_stack: list[int],
    result: FileCompatibilityResult,
) -> bool:
    """branch/#if/#elseif/#else/#endif/その他#系の構文チェックを行う。
    処理済みならTrueを返す。
    """
    if _check_branch_keyword(first_token, line, line_number, result):
        return True
    return _check_conditional_directive(
        first_token, line, line_number, branch_stack, result
    )


def _check_command_line(
    first_token: str,
    line: str,
    line_number: int,
    known_commands: set[str],
    case_variants_map: dict[str, str],
    speech_hints: list[str],
    result: FileCompatibilityResult,
) -> bool:
    """@ で始まる / 既知キーワードのコマンド行を判定し、未知コマンド・新規
    会話コマンド候補を記録する。コマンド行として処理済みならTrueを返す。
    """
    is_command_line = (
        first_token.startswith("@")
        or first_token.startswith("$")
        or first_token in known_commands
        or NUM_VAR_PATTERN.match(line) is not None
    )
    if not is_command_line:
        return False

    # 表記ゆれチェック
    normalized = case_variants_map.get(first_token)
    if normalized and normalized != first_token:
        result.case_variants[normalized].add(first_token)

    # 正規化後のコマンド名で既知チェック
    check_token = normalized if normalized else first_token

    if check_token not in known_commands:
        _record_unknown_command(result, first_token, line_number, line)

        if is_speech_candidate(first_token, speech_hints):
            _record_new_speech_command(result, first_token, line_number, line)

    return True


def _process_line(
    line_number: int,
    raw_line: str,
    branch_stack: list[int],
    known_commands: set[str],
    case_variants_map: dict[str, str],
    speech_hints: list[str],
    char_map: dict[str, str],
    result: FileCompatibilityResult,
) -> None:
    """1行を解析し、検出結果をresultへ記録する。
    各行分類は独立したヘルパーへ切り出し、ここでは「制御文字除去/空行・
    コメントスキップ」→「その他の分類を順番に試す」という制御フローのみを
    担う (挙動は分割前と同一、ruffのC901複雑度対策でのリファクタリング)。
    """
    line = _strip_control_chars(raw_line, result)

    if not line or line.startswith("//"):
        return

    if HYPHEN_LINE_PATTERN.match(line):
        result.hyphen_option_lines += 1
        return

    parts = line.split()
    first_token = parts[0] if parts else ""

    if _check_character_id_line(line, line_number, char_map, result):
        return

    if _check_branch_syntax(first_token, line, line_number, branch_stack, result):
        return

    _check_command_line(
        first_token,
        line,
        line_number,
        known_commands,
        case_variants_map,
        speech_hints,
        result,
    )
    # 本文行 (コマンド行でない場合はここで何もしない)


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

    for line_number, raw_line in enumerate(raw_lines, start=1):
        _process_line(
            line_number,
            raw_line,
            branch_stack,
            known_commands,
            case_variants_map,
            speech_hints,
            char_map,
            result,
        )

    # 分岐スタックが残っている → missing #endif
    for open_line in branch_stack:
        result.branch_issues.append(
            {
                "type": "missing_endif",
                "lineNumber": open_line,
                "raw": "#if (unclosed)",
                "severity": "high",
            }
        )

    # 最終ステータス決定
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
    name_filter_summary: "NameFilterSummary | None" = None,
) -> dict[str, Any]:
    """JSON レポートを構築する。

    name_filter_summaryは--include-name-pattern/--exclude-name-pattern
    適用時のみ渡される。渡された場合のみ summary.nameFilter を追加する
    (既存フィールドは変更しない)。
    """
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
    if name_filter_summary is not None:
        report["summary"]["nameFilter"] = name_filter_summary.to_dict()
    return report


def _status_emoji(status: str) -> str:
    return {
        "compatible": "✅",
        "warning": "⚠️",
        "needs_update": "🔶",
        "blocked": "🚫",
    }.get(status, "❓")


def _build_summary_section(report: dict[str, Any]) -> list[str]:
    """サマリーテーブルのMarkdown行を構築する"""
    summary = report["summary"]
    status = summary["parserCompatibility"]
    lines = ["## サマリー", "", "| 項目 | 値 |", "|---|---|"]
    lines.append(f"| 総合互換性 | {_status_emoji(status)} **{status}** |")
    lines.append(f"| ファイル数 | {summary['totalFiles']} |")
    lines.append(f"| 総行数 | {summary['totalLines']} |")
    lines.append(f"| 未知コマンド種類 | {summary['unknownCommandCount']} |")
    lines.append(f"| 新規会話コマンド候補 | {summary['newSpeechCommandCount']} |")
    lines.append(f"| 未登録キャラクターID | {summary['unknownCharacterIdCount']} |")
    lines.append(f"| 制御文字除去件数 | {summary['controlCharsRemoved']} |")
    lines.append("")

    name_filter = summary.get("nameFilter")
    if name_filter:
        lines.append("### ファイル名フィルタ")
        lines.append("")
        lines.append("| 項目 | 値 |")
        lines.append("|---|---|")
        lines.append(f"| 走査対象数 | {name_filter['totalScanned']} |")
        lines.append(f"| 収集対象数 | {name_filter['collectedCount']} |")
        lines.append(f"| フィルタで除外された数 | {name_filter['excludedCount']} |")
        if name_filter["includePatterns"]:
            include_str = ", ".join(f"`{p}`" for p in name_filter["includePatterns"])
            lines.append(f"| 適用パターン (include) | {include_str} |")
        if name_filter["excludePatterns"]:
            exclude_str = ", ".join(f"`{p}`" for p in name_filter["excludePatterns"])
            lines.append(f"| 適用パターン (exclude) | {exclude_str} |")
        lines.append("")
    return lines


def _build_file_results_section(report: dict[str, Any]) -> list[str]:
    """ファイル別結果テーブルのMarkdown行を構築する"""
    lines = ["## ファイル別結果", ""]
    lines.append(
        "| ファイル | 互換性 | 行数 | 未知Cmd | 新規会話 | 未登録ID | 制御文字 |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for f in report["files"]:
        st = f["parserCompatibility"]
        em = _status_emoji(st)
        lines.append(
            f"| {f['file']} | {em} {st} | {f['lineCount']} | "
            f"{len(f['unknownCommands'])} | {len(f['newSpeechCommands'])} | "
            f"{len(f['unknownCharacterIds'])} | {f['controlCharsRemoved']} |"
        )
    lines.append("")
    return lines


def _collect_new_speech_commands(report: dict[str, Any]) -> dict[str, dict]:
    all_new_speech: dict[str, dict] = {}
    for f in report["files"]:
        for cmd in f["newSpeechCommands"]:
            if cmd["command"] not in all_new_speech:
                all_new_speech[cmd["command"]] = cmd
    return all_new_speech


def _build_new_speech_section(report: dict[str, Any]) -> list[str]:
    """新規会話コマンド候補セクションのMarkdown行を構築する (該当なしなら空)"""
    all_new_speech = _collect_new_speech_commands(report)
    if not all_new_speech:
        return []
    lines = ["## 🔶 新規会話コマンド候補", ""]
    lines.append(
        "これらのコマンドは本文抽出に影響する可能性があります。辞書への追加を検討してください。"
    )
    lines.append("")
    for cmd, info in all_new_speech.items():
        lines.append(f"- `{cmd}` — {info['reason']} (severity: **{info['severity']}**)")
    lines.append("")
    return lines


def _collect_unknown_commands(report: dict[str, Any]) -> dict[str, dict]:
    all_unknown: dict[str, dict] = {}
    for f in report["files"]:
        for cmd_info in f["unknownCommands"]:
            cmd = cmd_info["command"]
            if cmd not in all_unknown:
                all_unknown[cmd] = {"command": cmd, "count": 0, "sampleLines": []}
            all_unknown[cmd]["count"] += cmd_info["count"]
            if len(all_unknown[cmd]["sampleLines"]) < 2:
                all_unknown[cmd]["sampleLines"].extend(cmd_info.get("sampleLines", []))
    return all_unknown


def _build_unknown_commands_section(report: dict[str, Any]) -> list[str]:
    """未知コマンド一覧セクションのMarkdown行を構築する (該当なしなら空)"""
    all_unknown = _collect_unknown_commands(report)
    if not all_unknown:
        return []
    lines = ["## ⚠️ 未知コマンド一覧", ""]
    lines.append("| コマンド | 出現回数 | サンプル行 |")
    lines.append("|---|---:|---|")
    for cmd, info in sorted(all_unknown.items(), key=lambda x: -x[1]["count"]):
        sample = ""
        if info["sampleLines"]:
            sl = info["sampleLines"][0]
            sample = f"L{sl['lineNumber']}: `{sl['raw'][:60]}`"
        lines.append(f"| `{cmd}` | {info['count']} | {sample} |")
    lines.append("")
    return lines


def _collect_unknown_character_ids(report: dict[str, Any]) -> dict[str, dict]:
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
    return all_unknown_chars


def _build_unknown_characters_section(report: dict[str, Any]) -> list[str]:
    """未登録キャラクターIDセクションのMarkdown行を構築する (該当なしなら空)"""
    all_unknown_chars = _collect_unknown_character_ids(report)
    if not all_unknown_chars:
        return []
    lines = ["## ⚠️ 未登録キャラクターID", ""]
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
    return lines


def build_markdown_report(report: dict[str, Any]) -> str:
    """Markdown レポートを構築する。各セクションは _build_*_section へ切り出し、
    ここではセクションを順番に連結する組み立てのみを担う
    (挙動は分割前と同一、ruffのC901複雑度対策でのリファクタリング)。
    """
    generated_at = report.get("generatedAt", "")
    ts = generated_at[:19].replace("T", " ") if generated_at else ""

    lines: list[str] = [
        "# Script Compatibility Report",
        "",
        f"生成日時: {ts} UTC",
        "",
    ]
    lines.extend(_build_summary_section(report))
    lines.extend(_build_file_results_section(report))
    lines.extend(_build_new_speech_section(report))
    lines.extend(_build_unknown_commands_section(report))
    lines.extend(_build_unknown_characters_section(report))
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
        description=(
            "DKB Script Compatibility Checker - Raw Script の互換性をチェックします"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "\n"
            "例:\n"
            "  python scripts/check_script_compatibility.py data/raw/\n"
            "  python scripts/check_script_compatibility.py "
            "data/raw/main/example.dec\n"
            "  python scripts/check_script_compatibility.py data/raw/ "
            "--output data/reports/ "
            "--characters knowledge/dictionaries/characters.yaml\n"
        ),
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
        help=(
            "キャラクター辞書のパス (デフォルト: "
            f"{DEFAULT_CHARACTERS_PATH})。拡張子で形式を自動判別する: "
            ".yaml/.yml は knowledge/dictionaries/characters.yaml 形式、"
            ".json はレガシー characters_reference.json 形式"
            f" ({LEGACY_CHARACTERS_PATH})"
        ),
    )
    parser.add_argument(
        "--include-name-pattern",
        action="append",
        metavar="REGEX",
        help=(
            "対象ファイルをファイル名 (basename) の正規表現 (re.search) で絞り込む。"
            "複数指定可、いずれかにマッチするファイルのみ対象とする"
            "(OR条件)。未指定時は従来どおり全件走査する。"
            "本編系ファイル名の例: "
            r'"-episode\d+\.dec$", "-episode_EX\d+\.dec$", '
            r'"-main\d+(_tutorial\d*)?(\s*#\d+)?\.dec$", "-Surprise_\d+\.dec$"'
            " (正規表現が'-'で始まる場合は"
            "--include-name-pattern=<regex> の'='付き形式で指定すること)"
        ),
    )
    parser.add_argument(
        "--exclude-name-pattern",
        action="append",
        metavar="REGEX",
        help=(
            "ファイル名 (basename) の正規表現 (re.search) にマッチするファイルを"
            "対象から除外する。複数指定可 (OR条件)。"
            "--include-name-patternの絞り込み後に適用される。"
            " (正規表現が'-'で始まる場合は"
            "--exclude-name-pattern=<regex> の'='付き形式で指定すること)"
        ),
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


def _load_config_and_dictionaries(
    args: argparse.Namespace,
) -> tuple[set[str], dict[str, str], dict[str, str], set[str], list[str]]:
    """設定・キャラクター辞書を読み込み、check_fileへ渡す各種セットを組み立てる。"""
    config = load_command_config(Path(args.commands))
    char_map = load_characters(Path(args.characters))
    known_commands = build_known_command_set(config)
    case_variants_map = build_case_variants_map(config)
    speech_commands = get_speech_commands(config)
    speech_hints = get_new_speech_hints(config)
    return known_commands, char_map, case_variants_map, speech_commands, speech_hints


def _run_checks(
    files: list[Path],
    known_commands: set[str],
    speech_commands: set[str],
    case_variants_map: dict[str, str],
    speech_hints: list[str],
    char_map: dict[str, str],
    quiet: bool,
) -> list[FileCompatibilityResult]:
    """対象ファイルすべてに対してcheck_fileを実行する。"""
    results: list[FileCompatibilityResult] = []
    for file_path in files:
        if not quiet:
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
    return results


def _write_reports(
    json_report: dict[str, Any],
    md_report: str,
    output_dir: Path,
    write_md: bool,
) -> tuple[Path, Path | None]:
    """JSON/Markdownレポートをファイルへ書き出し、書き出し先パスを返す。"""
    json_path = output_dir / "script_compatibility_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_report, f, ensure_ascii=False, indent=2)

    md_path: Path | None = None
    if write_md:
        md_path = output_dir / "script_compatibility_report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_report)

    return json_path, md_path


def _print_summary(
    json_report: dict[str, Any], json_path: Path, md_path: Path | None
) -> str:
    """サマリーを表示し、parserCompatibilityステータスを返す。"""
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

    name_filter = summary.get("nameFilter")
    if name_filter:
        print(
            f"[DKB] ファイル名フィルタ: 走査対象数={name_filter['totalScanned']} "
            f"収集対象数={name_filter['collectedCount']} "
            f"除外数={name_filter['excludedCount']}"
        )

    print(f"[DKB] JSON レポート: {json_path}")
    if md_path is not None:
        print(f"[DKB] MD レポート:   {md_path}")

    return status


def main() -> int:
    args = parse_args()

    target = Path(args.target)
    if not target.exists():
        print(f"[エラー] 対象が見つかりません: {target}", file=sys.stderr)
        return 1

    try:
        include_patterns = compile_name_patterns(args.include_name_pattern)
        exclude_patterns = compile_name_patterns(args.exclude_name_pattern)
    except re.error as e:
        print(
            "[エラー] 不正な正規表現です "
            f"(--include-name-pattern/--exclude-name-pattern): {e}",
            file=sys.stderr,
        )
        return 2

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    known_commands, char_map, case_variants_map, speech_commands, speech_hints = (
        _load_config_and_dictionaries(args)
    )

    if not args.quiet:
        print("[DKB] Script Compatibility Checker")
        print(f"[DKB] 対象: {target}")
        print(f"[DKB] 既知コマンド数: {len(known_commands)}")
        print(f"[DKB] 登録キャラクター数: {len(char_map)}")

    files, name_filter_summary = collect_files(
        target, include_patterns=include_patterns, exclude_patterns=exclude_patterns
    )
    if not files:
        print(f"[警告] 対象ファイルが見つかりませんでした: {target}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"[DKB] 対象ファイル数: {len(files)}")

    results = _run_checks(
        files,
        known_commands,
        speech_commands,
        case_variants_map,
        speech_hints,
        char_map,
        args.quiet,
    )

    json_report = build_json_report(files, results, name_filter_summary)
    md_report = build_markdown_report(json_report)
    json_path, md_path = _write_reports(
        json_report, md_report, output_dir, not args.no_md
    )
    status = _print_summary(json_report, json_path, md_path)

    # 終了コード: blocked → 2, needs_update → 1, それ以外 → 0
    if status == "blocked":
        return 2
    if status == "needs_update":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
