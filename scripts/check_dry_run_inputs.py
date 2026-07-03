#!/usr/bin/env python3
"""
Check Dry Run Inputs
実データを使ったローカルdry-run (docs/runbooks/Real_Data_Dry_Run.md) の
前後で、ディレクトリ状態と「commitしてはいけないものがcommit対象に
入っていないか」を確認する補助スクリプト。

本格的なpipeline実行 (normalize_story.py/extract_story.py/
merge_extractions.py) の代わりにはならない。あくまで状態確認・
チェックリストの機械的な裏付けのための軽量ツール。

Usage:
    # 既定のディレクトリ (data/raw, data/normalized, data/extracted,
    # data/reports, workspace) の存在確認 + git tracked禁止パターン確認
    python scripts/check_dry_run_inputs.py

    # data/extracted配下のJSON件数・episode_extraction候補を確認
    python scripts/check_dry_run_inputs.py --count-json data/extracted

    # schema validationコマンド例を表示
    python scripts/check_dry_run_inputs.py --show-commands

Exit codes:
    0: 問題なし (git tracked禁止パターンが見つからなかった)
    1: git管理してはいけないパス (実データ/生成物) がtrackedになっている
    2: git ls-files自体の実行に失敗した (gitリポジトリでない等)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent

# dry-run方針上、ローカルにだけ置くディレクトリ (docs/runbooks/Real_Data_Dry_Run.md
# §推奨ローカルディレクトリ構成 参照)。存在しなくてもエラーにはしない
# (dry-run未実施の初期状態ではまだ作られていないため)。
DRY_RUN_DIRECTORIES = (
    "data/raw",
    "data/normalized",
    "data/extracted",
    "data/reports",
    "workspace",
)

# git tracked状態であってはならないパスパターン (正規表現、git ls-files の
# 出力行に対して適用する)。tests/fixtures/ 配下の自作fixtureは対象外
# (小さい自作データはcommitしてよい既存ルールのため、ここでは判定しない)。
# .gitkeepは対象拡張子 (.dec/.txt/.json/.md) のいずれにも一致しないため、
# 除外用の否定先読みは不要 (拡張子マッチの時点で自然に除外される)。
_FORBIDDEN_TRACKED_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"^data/raw/.*\.dec$", "実.decスクリプト"),
    (r"^data/raw/.*\.txt$", "実スクリプトのtxt書き出し"),
    (r"^data/normalized/.*\.json$", "Normalized Story JSON生成物"),
    (r"^data/extracted/.*\.json$", "episode_extraction生成物"),
    (r"^data/reports/.*\.(json|md)$", "レポート生成物"),
    (r"^workspace/dry_runs/", "dry-run出力 (workspace/dry_runs/)"),
    (r"^(?:\.env|\.env\.[^.]+)$", "環境変数ファイル (.envの本体)"),
    (r".*\.log$", "ログファイル"),
)

# .envのテンプレート (.env.example) 等、上記パターンに一致してもよい例外。
_ALLOWED_EXCEPTIONS = {".env.example"}


def _run_git_ls_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git ls-files failed: {result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line]


def check_directories(root: Path) -> dict[str, bool]:
    """dry-run方針で使うディレクトリの存在確認。"""
    return {rel: (root / rel).is_dir() for rel in DRY_RUN_DIRECTORIES}


def classify_forbidden_paths(tracked_files: list[str]) -> list[tuple[str, str]]:
    """tracked扱いのパス一覧に対して、commitしてはいけないパターンとの
    一致を判定する純粋関数 (git呼び出しを含まないためテストしやすい)。

    戻り値: (該当パス, 該当理由) のリスト。空リストなら問題なし。
    """
    findings: list[tuple[str, str]] = []

    for path in tracked_files:
        if path in _ALLOWED_EXCEPTIONS:
            continue
        for pattern, reason in _FORBIDDEN_TRACKED_PATTERNS:
            if re.match(pattern, path):
                findings.append((path, reason))
                break

    return findings


def find_tracked_forbidden_paths(root: Path) -> list[tuple[str, str]]:
    """git tracked ファイルの中に、commitしてはいけないパターンが無いか確認する。

    戻り値: (該当パス, 該当理由) のリスト。空リストなら問題なし。
    """
    tracked_files = _run_git_ls_files(root)
    return classify_forbidden_paths(tracked_files)


def count_json_files(directory: Path) -> int:
    """指定ディレクトリ配下の *.json 件数を再帰的に数える。"""
    if not directory.is_dir():
        return 0
    return sum(1 for _ in directory.rglob("*.json"))


def find_extraction_candidates(directory: Path) -> list[Path]:
    """`documentType: "episode_extraction"` を持つJSONファイルを検出する
    (merge_extractions.py --input のmerge対象候補)。

    壊れたJSON・documentTypeが無いファイルは静かにスキップする
    (merge_extractions.py自体のvalidationゲートに委ねるため、ここでは
    候補の一覧化のみ行う)。
    """
    if not directory.is_dir():
        return []

    candidates: list[Path] = []
    for path in directory.rglob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("documentType") == "episode_extraction":
            candidates.append(path)

    return candidates


_EXAMPLE_COMMANDS = """
# 1. .dec -> Normalized Story JSON
uv run python scripts/normalize_story.py \\
    --input data/raw/main/example.dec \\
    --story-id MAIN_S01_C02 --episode-id MAIN_S01_C02_E01 --category MAIN \\
    --output data/normalized/main/ \\
    --validate --check-compat

# 2. Normalized Story JSON -> episode_extraction (Stage A)
uv run python scripts/extract_story.py \\
    --input data/normalized/main/MAIN_S01_C02_E01.json \\
    --output data/extracted/_raw/ \\
    --validate

# 3. episode_extraction のschema + semantic validation
uv run python scripts/validate_extraction_json.py \\
    --input data/extracted/_raw/ --semantic

# 4. Stage B merge (manual overrideなし)
uv run python scripts/merge_extractions.py \\
    --input data/extracted/_raw/ \\
    --output workspace/dry_runs/20260703_000000/

# 5. Stage B merge (manual overrideあり)
uv run python scripts/merge_extractions.py \\
    --input data/extracted/_raw/ \\
    --overrides knowledge/overrides/base.json \\
    --output workspace/dry_runs/20260703_000000/
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "実データdry-run (docs/runbooks/Real_Data_Dry_Run.md) の前後で、"
            "ディレクトリ状態とcommit対象の安全性を確認する"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--count-json",
        metavar="DIR",
        help="指定ディレクトリ配下のJSON件数とepisode_extraction候補を表示する",
    )
    parser.add_argument(
        "--show-commands",
        action="store_true",
        help="dry-run実行コマンド例を表示して終了する",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="ディレクトリ存在確認の詳細出力を抑制する",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.show_commands:
        print(_EXAMPLE_COMMANDS)
        return 0

    if args.count_json:
        directory = Path(args.count_json)
        total = count_json_files(directory)
        candidates = find_extraction_candidates(directory)
        print(f"[dry-run] {directory}: JSON {total} 件")
        print(f"[dry-run] うちepisode_extraction候補: {len(candidates)} 件")
        for path in candidates:
            print(f"  - {path}")
        return 0

    if not args.quiet:
        print("[dry-run] ディレクトリ存在確認:")
        for rel, exists in check_directories(_PROJECT_ROOT).items():
            mark = "OK" if exists else "  (未作成)"
            print(f"  - {rel}: {mark}")

    try:
        findings = find_tracked_forbidden_paths(_PROJECT_ROOT)
    except RuntimeError as e:
        print(f"[エラー] {e}", file=sys.stderr)
        return 2

    if findings:
        print(
            "[エラー] git管理下に含めてはいけないファイルがtrackedになっています:",
            file=sys.stderr,
        )
        for path, reason in findings:
            print(f"  - {path} ({reason})", file=sys.stderr)
        return 1

    if not args.quiet:
        print("[dry-run] git tracked禁止パターン: 検出なし")

    return 0


if __name__ == "__main__":
    sys.exit(main())
