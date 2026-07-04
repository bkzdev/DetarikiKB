#!/usr/bin/env python3
"""
Check Character Dictionary Coverage
実データ (.dec) を対象に、knowledge/dictionaries/characters.yaml 相当の
人手管理キャラクター辞書がどれだけ sourceCharacterId をカバーできて
いるかを確認する補助スクリプト。

実データそのものを解析するが、出力するのは件数・カバレッジ率・
未登録IDの一覧 (ID番号のみ) にとどめ、実データ本文・セリフは一切
出力しない。このレポート自体もローカル確認用であり、commit対象では
ない (docs/runbooks/Real_Data_Dry_Run.md 参照)。

Usage:
    # data/raw/dry_run/ 配下の .dec 全件を対象にカバレッジを確認
    python scripts/check_character_dictionary_coverage.py data/raw/dry_run/

    # 辞書ファイルを明示指定
    python scripts/check_character_dictionary_coverage.py data/raw/dry_run/ \
        --dictionary knowledge/dictionaries/characters.yaml

Exit codes:
    0: 実行成功 (カバレッジ率に関わらず)
    1: 対象ファイルが1件も見つからなかった
    2: 辞書ファイルの読み込み・検証に失敗した
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.parser import StoryParser  # noqa: E402
from agents.parser.character_dictionary import (  # noqa: E402
    STATUS_CONFIRMED,
    STATUS_NAME_ONLY,
    build_character_dictionary_coverage_report,
    build_review_candidates,
    load_character_dictionary,
    validate_character_dictionary,
)
from agents.parser.resolver import CharacterDictionary  # noqa: E402

DEFAULT_DICTIONARY_PATH = (
    _PROJECT_ROOT / "knowledge" / "dictionaries" / "characters.yaml"
)


def collect_files(target: Path) -> list[Path]:
    """ディレクトリまたは単一ファイルから対象の .dec/.txt を収集する。"""
    if target.is_file():
        return [target]
    files: list[Path] = []
    for ext in (".dec", ".txt"):
        files.extend(target.rglob(f"*{ext}"))
    return sorted(files)


def collect_observed_source_ids(files: list[Path]) -> dict[str, int]:
    """対象ファイル群をパースし、observed sourceCharacterIdの出現回数を集計する。

    辞書は敢えて空のCharacterDictionaryを渡す (解決済みかどうかに関わらず、
    speakerAssignmentsに現れた全sourceCharacterIdを観測対象にするため)。
    """
    parser = StoryParser(char_dict=CharacterDictionary())
    counter: Counter[str] = Counter()

    for path in files:
        try:
            result = parser.parse_file(path)
        except Exception as e:  # noqa: BLE001 - 1ファイルの失敗で全体を止めない
            print(f"[警告] 解析に失敗しました: {path} ({e})", file=sys.stderr)
            continue
        for episode in result.episodes:
            for assignment in episode.speaker_assignments:
                if assignment.source_character_id:
                    counter[assignment.source_character_id] += 1

    return dict(counter)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "実データ (.dec) に対するキャラクター辞書 "
            "(knowledge/dictionaries/characters.yaml) のカバレッジを確認する"
        ),
    )
    parser.add_argument(
        "target",
        help="対象ディレクトリまたは単一ファイル (.dec/.txt)",
    )
    parser.add_argument(
        "--dictionary",
        default=str(DEFAULT_DICTIONARY_PATH),
        help=f"キャラクター辞書YAMLのパス (デフォルト: {DEFAULT_DICTIONARY_PATH})",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    parser.add_argument(
        "--review-template-output",
        metavar="PATH",
        help=(
            "未登録sourceCharacterIdの人間確認用テンプレートをYAMLで書き出す"
            "(ローカル確認用。commit対象外のパス、例: workspace/dry_runs/配下"
            "を指定すること。docs/runbooks/Character_Dictionary_Review.md参照)"
        ),
    )
    return parser.parse_args()


_REVIEW_TEMPLATE_HEADER = """\
# Character Dictionary Review Candidates (auto-generated)
#
# scripts/check_character_dictionary_coverage.py --review-template-output
# が自動生成したローカル確認用ファイルです。
#
# 重要: このファイルはcommitしないでください
# (docs/runbooks/Character_Dictionary_Review.md 参照)。
# 人間が sourceCharacterId ごとに実データを確認し、confirmedCharacterId /
# suggestedDisplayName / reviewerNotes を埋めたうえで、確認済みの
# エントリだけを knowledge/dictionaries/characters.yaml へ手動で反映すること。
# 名前が一致するというだけの理由で status を confirmed にしないこと。
"""


def write_review_template(path: Path, candidates: list[dict]) -> None:
    """未登録sourceCharacterIdの確認用テンプレートをYAMLへ書き出す。

    candidatesはsourceCharacterId・出現回数と空のプレースホルダーのみで
    構成され、実データの本文・displayNameは含まない
    (build_review_candidates参照)。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(_REVIEW_TEMPLATE_HEADER)
        yaml.safe_dump(
            {"reviewCandidates": candidates},
            f,
            allow_unicode=True,
            sort_keys=False,
        )


def main() -> int:
    args = parse_args()

    dictionary_path = Path(args.dictionary)
    entries = load_character_dictionary(dictionary_path)
    if not entries:
        print(f"[エラー] 辞書が空か読み込めませんでした: {dictionary_path}")
        return 2

    issues = validate_character_dictionary(entries)
    if issues:
        print("[エラー] 辞書の検証に失敗しました:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 2

    target = Path(args.target)
    files = collect_files(target)
    if not files:
        print(f"[エラー] 対象ファイルが見つかりません: {target}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"[dry-run] 辞書: {dictionary_path} ({len(entries)} 件)")
        print(
            f"[dry-run]   status内訳: confirmed="
            f"{sum(1 for e in entries if e.status == STATUS_CONFIRMED)} 件 / "
            f"name_only={sum(1 for e in entries if e.status == STATUS_NAME_ONLY)} 件"
        )
        print(f"[dry-run] 対象ファイル数: {len(files)}")

    observed = collect_observed_source_ids(files)
    report = build_character_dictionary_coverage_report(entries, observed)

    print(f"[dry-run] observedCount: {report['observedCount']}")
    print(f"[dry-run] knownCount:    {report['knownCount']}")
    print(f"[dry-run] unknownCount:  {report['unknownCount']}")
    print(f"[dry-run] coverage:      {report['coveragePercentage']}%")
    print(
        f"[dry-run]   confirmed coverage: "
        f"{report['confirmedObservedCount']} 件 "
        f"({report['confirmedCoveragePercentage']}%)"
    )
    print(
        f"[dry-run]   name_only coverage: "
        f"{report['nameOnlyObservedCount']} 件 "
        f"({report['nameOnlyCoveragePercentage']}%)"
    )
    if report["topUnknownIds"]:
        print("[dry-run] top unknown sourceCharacterIds (id: count):")
        for item in report["topUnknownIds"]:
            print(f"  - {item['sourceCharacterId']}: {item['count']}")

    if args.review_template_output:
        known_ids = {entry.source_character_id for entry in entries}
        candidates = build_review_candidates(observed, known_ids)
        output_path = Path(args.review_template_output)
        write_review_template(output_path, candidates)
        if not args.quiet:
            print(
                f"[dry-run] review template書き出し: {output_path} "
                f"({len(candidates)} 件、commit禁止・ローカル確認用)"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
