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

# $numX = ID（parserと同じくRHSの先頭トークンを値とし、数字の右境界を必須化）
NUM_VAR_PATTERN = re.compile(r"^\$num(\d+)\s*=\s*(\d+)(?=\s|$)")
# $valueX = ID（parserと同じくRHSの先頭トークンを値とし、数字の右境界を必須化）
VALUE_VAR_PATTERN = re.compile(r"^\$value(\d+)\s*=\s*(\d+)(?=\s|$)")
# 数値ID以外も含む$numX/$valueX代入行。ID候補の抽出には使わず、
# 正規の変数代入をunknown command扱いしないためだけに使う。
NUM_VALUE_ASSIGNMENT_PATTERN = re.compile(r"^\$(?:num|value)\d+\s*=\s*\S+")
# @ScenarioCos slot id (数値直接指定) または @ScenarioCos slot $var (変数経由)
SCENARIO_COS_PATTERN = re.compile(r"^@ScenarioCos\s+(\d+)\s+(\d+|\$[\w\d]+)")
# @ScenarioCosLoad slot var
SCENARIO_COS_LOAD_PATTERN = re.compile(r"^@ScenarioCosLoad\s+(\d+)\s+(\$[\w\d]+)")
# ch N (表示スロットN指定の裸コマンド、feature/costume-slot-binding-fix)。
# 第1引数を捕捉し、数字かどうかの判定は呼び出し側 (_apply_ch_command) で行う
# (agents/parser/parser.pyのtoken.args[0].isdigit()判定と対称)。
CH_PATTERN = re.compile(r"^ch\s+(\S+)")
# costume <衣装ID> <キャラID> [ON] (第1引数=衣装ID、第2引数=キャラID)
COSTUME_PATTERN = re.compile(r"^costume\s+(\S+)\s+(\S+)")

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
        # 未登録キャラクターID (話者スロットとして実際に@ChTalk系コマンドに
        # 消費されたもののみ。判定は消費文脈シミュレーション
        # (_simulate_id_consumption) による。03_Scope.md §5.2参照)
        self.unknown_character_ids: dict[
            str, dict
        ] = {}  # char_id -> {count, sample_lines}
        # 未登録の数値代入のうち、話者スロットとして消費されなかったもの
        # (costume/mo/fa等の非話者引数としてのみ消費される・完全未消費のいずれも
        # このバケットに分類する。「不明情報を破棄しない」不変則
        # (AI_CONTEXT.md §3.2) のため削除はせず、判定への影響を持たない
        # 別フィールドとして情報保持する)
        self.non_speaker_numeric_assignments: dict[str, dict] = {}
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


def _is_supported_assignment_line(line: str) -> bool:
    """$numX / $valueX / @ScenarioCos / @ScenarioCosLoad 行かどうかを判定する。

    キャラクターIDの記録自体は、ファイル単位の消費文脈シミュレーション
    (`_simulate_id_consumption` / `_classify_and_record_character_ids`、
    `check_file`から一度だけ呼ばれる) へ移管したため、ここでは
    「通常のコマンド行処理 (`_check_command_line`) をスキップすべきか」の
    判定のみを行う (挙動は分割前と同一: これらの行はunknown commandとして
    扱われない)。

    `$numX`/`$valueX`は非リテラル値もparserが変数代入として受理するため、
    数値ID専用のNUM_VAR_PATTERN/VALUE_VAR_PATTERNではなく汎用パターンで
    判定する。非リテラル式をcharacter ID候補としては記録しない。
    """
    return bool(
        NUM_VALUE_ASSIGNMENT_PATTERN.match(line)
        or SCENARIO_COS_PATTERN.match(line)
        or SCENARIO_COS_LOAD_PATTERN.match(line)
    )


class _SlotSimState:
    """`_simulate_id_consumption`の時系列1パスシミュレーション状態。

    `resolver.py`(`SpeakerResolver`)・`agents/parser/parser.py`と同じ意味論
    (スロットへの再代入は上書き) で`slot_map`/`variable_map`を保持する。
    """

    def __init__(self) -> None:
        self.max_num_index = -1
        self.variable_map: dict[str, str] = {}
        self.slot_map: dict[str, str] = {}
        self.id_signals: dict[str, dict[str, Any]] = {}
        # ch N (表示スロットN指定の裸コマンド) で直近に指定されたスロット番号。
        # 直後 (間に別の ch が現れるまでの範囲) に出現する costume コマンドの
        # スロット再束縛先として参照する (feature/costume-slot-binding-fix、
        # agents/parser/parser.pyのpending_ch_slotと対称)。
        self.pending_ch_slot: str | None = None

    def get_signal(self, id_value: str) -> dict[str, Any]:
        return self.id_signals.setdefault(
            id_value, {"speaker": False, "occurrences": []}
        )


def _apply_num_var_assignment(
    match: re.Match[str], line_number: int, line: str, state: _SlotSimState
) -> None:
    idx = int(match.group(1))
    value = match.group(2)
    if idx > state.max_num_index:
        state.max_num_index = idx
    state.variable_map[f"$num{idx}"] = value
    state.slot_map[str(idx)] = value
    state.get_signal(value)["occurrences"].append((line_number, line))


def _apply_value_var_assignment(
    match: re.Match[str], line_number: int, line: str, state: _SlotSimState
) -> None:
    idx = int(match.group(1))
    value = match.group(2)
    slot = str(state.max_num_index + 1 + idx)
    state.variable_map[f"$value{idx}"] = value
    state.slot_map[slot] = value
    state.get_signal(value)["occurrences"].append((line_number, line))


def _apply_scenario_cos(
    match: re.Match[str], line_number: int, line: str, state: _SlotSimState
) -> None:
    slot, second_arg = match.group(1), match.group(2)
    if second_arg.startswith("$"):
        # 変数経由 (@ScenarioCosLoadと同じ意味論): variable_mapから
        # IDを引いてスロットへ束縛し、その定義元IDへ話者シグナルを立てる。
        # char_id直接取得不可のためoccurrencesには追加しない
        # (従来のchar_id直接取得不可判定と同じ)。
        resolved = state.variable_map.get(second_arg)
        if resolved is not None:
            state.slot_map[slot] = resolved
            state.get_signal(resolved)["speaker"] = True
        return
    state.slot_map[slot] = second_arg
    sig = state.get_signal(second_arg)
    sig["occurrences"].append((line_number, line))
    sig["speaker"] = True


def _apply_scenario_cos_load(match: re.Match[str], state: _SlotSimState) -> None:
    slot, var = match.group(1), match.group(2)
    resolved = state.variable_map.get(var)
    if resolved is not None:
        state.slot_map[slot] = resolved
        state.get_signal(resolved)["speaker"] = True


def _apply_ch_command(match: re.Match[str], state: _SlotSimState) -> None:
    """`ch N`によるpending_ch_slotの更新
    (agents/parser/parser.pyの`kw == "ch"`分岐と対称)。数字以外の引数
    (カメラ演出目的の別用法) はウィンドウを無効化する。"""
    arg = match.group(1)
    state.pending_ch_slot = arg if arg.isdigit() else None


def _apply_costume_command(
    match: re.Match[str], line_number: int, line: str, state: _SlotSimState
) -> None:
    """`costume <衣装ID> <キャラID> [ON]`によるpending_ch_slotの再束縛
    (agents/parser/parser.pyの`resolver.assign_costume_character`と対称)。
    第2引数 (キャラID) が`$`始まりの変数ならvariable_mapから解決
    (occurrences追加なし、assign_from_variableと同じ意味論)、数字のみの
    リテラルならそのまま (occurrences追加あり、assign_characterと同じ
    意味論) スロットを再束縛する。直前にchが無い場合・第2引数が未定義変数/
    非数値の場合は一切束縛しない (既存slot_mapを破壊しない)。"""
    if state.pending_ch_slot is None:
        return
    second_arg = match.group(2)
    if second_arg.startswith("$"):
        resolved = state.variable_map.get(second_arg)
        if resolved is None:
            return
        state.slot_map[state.pending_ch_slot] = resolved
        state.get_signal(resolved)["speaker"] = True
    elif second_arg.isdigit():
        state.slot_map[state.pending_ch_slot] = second_arg
        sig = state.get_signal(second_arg)
        sig["occurrences"].append((line_number, line))
        sig["speaker"] = True


def _apply_speech_command_consumption(
    parts: list[str],
    state: _SlotSimState,
    speech_commands: set[str],
    case_variants_map: dict[str, str],
) -> None:
    first_token = parts[0]
    normalized = case_variants_map.get(first_token, first_token)
    if normalized not in speech_commands:
        return
    slot_arg = parts[1] if len(parts) > 1 else None
    if slot_arg is None:
        return
    resolved = state.slot_map.get(slot_arg)
    if resolved is not None:
        state.get_signal(resolved)["speaker"] = True


def _simulate_id_consumption(
    lines: list[str],
    speech_commands: set[str],
    case_variants_map: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """ファイル全体を時系列1パスでシミュレートし、`$numX`/`$valueX`代入・
    `@ScenarioCos`(直接数値指定)・`ch N`+`costume`(feature/costume-slot-
    binding-fix)で検出されたcharacter_id候補ごとに、実際に話者スロットとして
    `@ChTalk`系コマンドに消費されたかどうかを判定する。

    行ごとの分岐は独立したヘルパー (`_apply_num_var_assignment`等) へ
    切り出し、ここでは行分類の制御フローのみを担う (ruffのC901複雑度対策)。
    調査用スキャナv3 (`docs/architecture/01_Project/03_Scope.md` §5.2) と
    同じアルゴリズムをchecker本体へ統合したもの。

    戻り値: `id_value -> {"speaker": bool, "occurrences": [(line_number, raw), ...]}`。
    `occurrences`が空のIDは「代入行として検出されなかった」ことを意味し
    (`@ScenarioCosLoad`や変数形式`@ScenarioCos`経由でのみ話者判定された値等)、
    従来どおり未登録ID候補の集計対象にしない。
    """
    state = _SlotSimState()

    for line_number, line in enumerate(lines, start=1):
        if not line or line.startswith("//"):
            continue

        num_match = NUM_VAR_PATTERN.match(line)
        if num_match:
            _apply_num_var_assignment(num_match, line_number, line, state)
            continue

        val_match = VALUE_VAR_PATTERN.match(line)
        if val_match:
            _apply_value_var_assignment(val_match, line_number, line, state)
            continue

        sc_match = SCENARIO_COS_PATTERN.match(line)
        if sc_match:
            _apply_scenario_cos(sc_match, line_number, line, state)
            continue

        scl_match = SCENARIO_COS_LOAD_PATTERN.match(line)
        if scl_match:
            _apply_scenario_cos_load(scl_match, state)
            continue

        ch_match = CH_PATTERN.match(line)
        if ch_match:
            _apply_ch_command(ch_match, state)
            continue

        costume_match = COSTUME_PATTERN.match(line)
        if costume_match:
            _apply_costume_command(costume_match, line_number, line, state)
            continue

        parts = line.split()
        if not parts:
            continue
        _apply_speech_command_consumption(
            parts, state, speech_commands, case_variants_map
        )

    return state.id_signals


def _classify_and_record_character_ids(
    id_signals: dict[str, dict[str, Any]],
    char_map: dict[str, str],
    result: FileCompatibilityResult,
) -> None:
    """`_simulate_id_consumption`の結果を分類し、未登録IDを
    (a) 話者消費あり → `result.unknown_character_ids` (従来フィールド、
        `parserCompatibility`判定に反映される)、
    (b) 話者消費なし → `result.non_speaker_numeric_assignments` (新設フィールド、
        判定には影響しない情報保持用)
    へ振り分けて記録する。
    """
    for id_value, sig in id_signals.items():
        occurrences = sig["occurrences"]
        if not occurrences:
            continue
        if id_value in char_map:
            continue

        target = (
            result.unknown_character_ids
            if sig["speaker"]
            else result.non_speaker_numeric_assignments
        )
        entry = target.setdefault(
            id_value,
            {"sourceCharacterId": id_value, "count": 0, "sampleLines": []},
        )
        for line_number, raw in occurrences:
            entry["count"] += 1
            if len(entry["sampleLines"]) < 3:
                entry["sampleLines"].append({"lineNumber": line_number, "raw": raw})


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
    line: str,
    branch_stack: list[int],
    known_commands: set[str],
    case_variants_map: dict[str, str],
    speech_hints: list[str],
    result: FileCompatibilityResult,
) -> None:
    """制御文字除去済みの1行を解析し、検出結果をresultへ記録する。
    各行分類は独立したヘルパーへ切り出し、ここでは「空行・コメントスキップ」
    →「その他の分類を順番に試す」という制御フローのみを担う (挙動は分割前と
    同一、ruffのC901複雑度対策でのリファクタリング)。

    キャラクターID代入行 (`$numX`/`$valueX`/`@ScenarioCos`/`@ScenarioCosLoad`)
    の記録自体は`check_file`側の消費文脈シミュレーションで一括処理済みのため、
    ここでは`_is_supported_assignment_line`でそれらの行をunknown command
    判定から除外するだけに留める (制御文字除去は`check_file`側で一度だけ行う
    ため、ここでは受け取らない)。
    """
    if not line or line.startswith("//"):
        return

    if HYPHEN_LINE_PATTERN.match(line):
        result.hyphen_option_lines += 1
        return

    parts = line.split()
    first_token = parts[0] if parts else ""

    if _is_supported_assignment_line(line):
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

    # 制御文字除去 (行単位、除去件数はresultへ集計)。以降の消費文脈
    # シミュレーション・通常のコマンド行処理はいずれもこのstripped_linesを使う
    # (二重stripを避けるため一度だけ行う)。
    stripped_lines = [_strip_control_chars(rl, result) for rl in raw_lines]

    # キャラクターID消費文脈シミュレーション (ファイル単位、時系列1パス)。
    # unknown_character_ids (話者消費あり) / non_speaker_numeric_assignments
    # (話者消費なし) への分類はここで完結させる (03_Scope.md §5.2参照)。
    id_signals = _simulate_id_consumption(
        stripped_lines, speech_commands, case_variants_map
    )
    _classify_and_record_character_ids(id_signals, char_map, result)

    # 分岐スタック
    branch_stack: list[int] = []

    for line_number, line in enumerate(stripped_lines, start=1):
        _process_line(
            line_number,
            line,
            branch_stack,
            known_commands,
            case_variants_map,
            speech_hints,
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
    total_non_speaker_numeric_assignments = sum(
        len(r.non_speaker_numeric_assignments) for r in results
    )
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
            "nonSpeakerNumericAssignments": list(
                r.non_speaker_numeric_assignments.values()
            ),
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
            "nonSpeakerNumericAssignmentCount": total_non_speaker_numeric_assignments,
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
    unknown_char_count = summary["unknownCharacterIdCount"]
    lines.append(f"| 未登録キャラクターID (話者消費あり) | {unknown_char_count} |")
    lines.append(
        f"| 話者非消費の数値代入 (参考情報、判定に非反映) | "
        f"{summary['nonSpeakerNumericAssignmentCount']} |"
    )
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
        "| ファイル | 互換性 | 行数 | 未知Cmd | 新規会話 | 未登録ID(話者) | "
        "話者非消費代入 | 制御文字 |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for f in report["files"]:
        st = f["parserCompatibility"]
        em = _status_emoji(st)
        lines.append(
            f"| {f['file']} | {em} {st} | {f['lineCount']} | "
            f"{len(f['unknownCommands'])} | {len(f['newSpeechCommands'])} | "
            f"{len(f['unknownCharacterIds'])} | "
            f"{len(f.get('nonSpeakerNumericAssignments', []))} | "
            f"{f['controlCharsRemoved']} |"
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
    """未登録キャラクターID (話者消費あり) セクションのMarkdown行を構築する
    (該当なしなら空)。ここに載るIDのみが`parserCompatibility`判定に反映される
    (03_Scope.md §5.2の消費文脈ベース判定)。"""
    all_unknown_chars = _collect_unknown_character_ids(report)
    if not all_unknown_chars:
        return []
    lines = ["## ⚠️ 未登録キャラクターID (話者消費あり)", ""]
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


def _collect_non_speaker_numeric_assignments(report: dict[str, Any]) -> dict[str, dict]:
    all_non_speaker: dict[str, dict] = {}
    for f in report["files"]:
        for char_info in f.get("nonSpeakerNumericAssignments", []):
            cid = char_info["sourceCharacterId"]
            if cid not in all_non_speaker:
                all_non_speaker[cid] = {
                    "sourceCharacterId": cid,
                    "count": 0,
                    "files": set(),
                    "sampleLines": [],
                }
            all_non_speaker[cid]["count"] += char_info["count"]
            all_non_speaker[cid]["files"].add(f["file"])
            if len(all_non_speaker[cid]["sampleLines"]) < 2:
                all_non_speaker[cid]["sampleLines"].extend(
                    char_info.get("sampleLines", [])
                )
    return all_non_speaker


def _build_non_speaker_numeric_assignments_section(report: dict[str, Any]) -> list[str]:
    """話者非消費の数値代入セクションのMarkdown行を構築する (該当なしなら空)。

    ここに載るIDは`$numX`/`$valueX`等で代入されたが、話者スロットとして
    `@ChTalk`系コマンドに一度も消費されなかったもの (costume/mo/fa等の
    非話者引数としてのみ消費される・完全未消費のいずれも含む)。
    `parserCompatibility`判定・exit codeには一切影響しない参考情報
    (03_Scope.md §5.2、「不明情報を破棄しない」不変則により削除ではなく
    分類変更として保持する)。
    """
    all_non_speaker = _collect_non_speaker_numeric_assignments(report)
    if not all_non_speaker:
        return []
    lines = ["## ℹ️ 話者非消費の数値代入 (参考情報、判定に非反映)", ""]
    lines.append(
        "`$numX`/`$valueX`等で代入されたが、話者スロットとして`@ChTalk`系"
        "コマンドには一度も消費されなかった値です。costume/mo/fa等の非話者"
        "引数としてのみ消費される場合や、完全に未消費の場合が含まれます。"
        "`parserCompatibility`判定には影響しません。"
    )
    lines.append("")
    lines.append("| ID | 出現回数 | サンプル行 |")
    lines.append("|---|---:|---|")
    for cid, info in sorted(
        all_non_speaker.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0
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
    lines.extend(_build_non_speaker_numeric_assignments_section(report))
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
    print(
        "[DKB] 未登録キャラクターID (話者消費あり): "
        f"{summary['unknownCharacterIdCount']}"
    )
    print(
        "[DKB] 話者非消費の数値代入 (参考情報、判定に非反映): "
        f"{summary['nonSpeakerNumericAssignmentCount']}"
    )
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
