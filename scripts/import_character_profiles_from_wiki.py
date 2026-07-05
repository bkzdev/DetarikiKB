#!/usr/bin/env python3
"""
Import Character Profiles from Wiki
デタリキZ攻略Wikiのメンバー一覧テーブルから、
knowledge/dictionaries/character_profiles.yaml へ投入可能な中間形式
(import candidate) をローカルへ書き出す補助スクリプト。

**重要**:
- このスクリプトは character_profiles.yaml を直接更新しない。出力は
  必ず candidate file (workspace/profile_import/ 配下等、.gitignore対象)
  であり、人間が確認してから次のconfirmed-batch/import batchで
  knowledge/dictionaries/character_profiles.yaml へ反映すること
  (docs/runbooks/Character_Profile_Wiki_Import.md 参照)。
- characterIdは自動生成しない。confirmed済みcharacterIdへのdisplayName
  完全一致のみを自動matchとし、それ以外はunmatchedとして人間確認に回す。
- 自己紹介文はメンバー一覧テーブルには存在しないため取得しない
  (常にselfIntroduction: null。個別キャラページからの取得は別タスク)。
- サイト負荷に配慮し、一覧テーブル1ページのみを取得する (個別ページ巡回は
  行わない)。robots.txtで許可されていない場合は取得しない。

Usage:
    # 合成HTML/ローカルHTMLファイルから (テスト・オフライン確認用)
    uv run python scripts/import_character_profiles_from_wiki.py \\
        --input-html \\
        tests/fixtures/character_profiles/synthetic_wiki_member_table.html \\
        --characters knowledge/dictionaries/characters.yaml \\
        --dry-run

    # 実WIKIから取得 (dry-run、summaryのみ表示)
    uv run python scripts/import_character_profiles_from_wiki.py \\
        --source-url "https://example.invalid/member-table" \\
        --characters knowledge/dictionaries/characters.yaml \\
        --output workspace/profile_import/character_profile_candidates_batch_001.yaml \\
        --dry-run

Exit codes:
    0: 成功 (dry-runでのsummary表示含む)
    1: 引数不正、または入力ファイルが見つからない
    2: メンバー一覧テーブルを検出できなかった
    3: robots.txtにより取得が許可されていない
"""

from __future__ import annotations

import argparse
import csv
import sys
import urllib.request
import urllib.robotparser
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.parser.character_dictionary import load_character_dictionary  # noqa: E402
from agents.parser.character_profile_wiki_import import (  # noqa: E402
    build_candidate_document,
    extract_tables,
    find_member_table,
    match_candidates,
    rows_to_dicts,
)

DEFAULT_CHARACTERS_PATH = (
    _PROJECT_ROOT / "knowledge" / "dictionaries" / "characters.yaml"
)
DEFAULT_USER_AGENT = (
    "DetarikiKB-CharacterProfileImportBot/0.1 "
    "(+https://github.com/; character profile member-table import, single page only)"
)

_CSV_FIELDS = (
    "matchStatus",
    "characterId",
    "sourceDisplayName",
    "displayName",
    "kana",
    "affiliation",
    "heightCm",
    "birthdayDisplay",
    "bloodType",
    "cv",
    "profileHighlightLabel",
    "profileHighlightValue",
    "reason",
)


def check_robots_allowed(url: str, user_agent: str) -> bool:
    """robots.txtで対象URLの取得が許可されているかを確認する。

    robots.txt自体が取得できない場合は、安全側に倒して許可されていない
    ものとして扱う。
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except OSError:
        return False
    return parser.can_fetch(user_agent, url)


def fetch_html(url: str, user_agent: str) -> str:
    """指定URLからHTMLを1回だけ取得する (個別ページ巡回はしない)。"""
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "デタリキZ攻略Wikiのメンバー一覧テーブルから、character_profiles.yaml"
            "へ投入可能な中間形式 (import candidate) をローカルへ書き出す"
        ),
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--source-url",
        help="メンバー一覧テーブルのURL (1ページのみ取得、個別ページ巡回はしない)",
    )
    source_group.add_argument(
        "--input-html",
        help="ローカルHTMLファイルのパス (テスト・オフライン確認用)",
    )
    parser.add_argument(
        "--characters",
        default=str(DEFAULT_CHARACTERS_PATH),
        help=f"characters.yamlのパス (デフォルト: {DEFAULT_CHARACTERS_PATH})",
    )
    parser.add_argument(
        "--output",
        help=(
            "candidate fileの出力先パス (--dry-run指定時は書き出さない)。"
            "commit対象外のローカルパス (例: workspace/profile_import/配下) "
            "を指定すること"
        ),
    )
    parser.add_argument(
        "--format",
        choices=("yaml", "csv", "both"),
        default="yaml",
        help="出力形式 (デフォルト: yaml)",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="HTTP取得時のUser-Agent",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="candidate fileへ書き出さず、標準出力にsummaryのみ表示する",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


def _load_html(args: argparse.Namespace) -> tuple[str, str | None, str] | None:
    """入力元 (URLまたはローカルファイル) からHTMLを読み込む。

    戻り値: (html, source_url, source_label)。取得に失敗した場合はNone
    (呼び出し側でexit codeを決める)。
    """
    if args.source_url:
        if not check_robots_allowed(args.source_url, args.user_agent):
            print(
                f"[エラー] robots.txtにより取得が許可されていません: {args.source_url}",
                file=sys.stderr,
            )
            return None
        html = fetch_html(args.source_url, args.user_agent)
        return html, args.source_url, f"Wiki member table ({args.source_url})"

    html_path = Path(args.input_html)
    if not html_path.exists():
        print(f"[エラー] 入力HTMLが見つかりません: {html_path}", file=sys.stderr)
        return None
    html = html_path.read_text(encoding="utf-8")
    return html, None, f"Local HTML file ({html_path})"


def _write_yaml(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(document, f, allow_unicode=True, sort_keys=False)


def _write_csv(path: Path, candidates: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for candidate in candidates:
            profile = candidate.get("profile") or {}
            reading = profile.get("reading") or {}
            birthday = profile.get("birthday") or {}
            highlight = profile.get("profileHighlight") or {}
            writer.writerow(
                {
                    "matchStatus": candidate.get("matchStatus", ""),
                    "characterId": candidate.get("characterId") or "",
                    "sourceDisplayName": candidate.get("sourceDisplayName", ""),
                    "displayName": profile.get("displayName", ""),
                    "kana": reading.get("kana") or "",
                    "affiliation": "|".join(profile.get("affiliation") or []),
                    "heightCm": profile.get("heightCm") or "",
                    "birthdayDisplay": birthday.get("display") or "",
                    "bloodType": profile.get("bloodType") or "",
                    "cv": profile.get("cv") or "",
                    "profileHighlightLabel": highlight.get("label") or "",
                    "profileHighlightValue": highlight.get("value") or "",
                    "reason": candidate.get("reason", ""),
                }
            )


def _write_candidate_outputs(
    output: str, format_: str, candidates: list[dict], source_url: str | None
) -> list[Path]:
    """--output指定時に、--formatに応じてYAML/CSVのcandidate fileを書き出す。"""
    document = build_candidate_document(
        candidates, source_url, datetime.now(UTC).isoformat()
    )
    output_path = Path(output)
    written: list[Path] = []
    if format_ in ("yaml", "both"):
        yaml_path = (
            output_path if format_ != "both" else output_path.with_suffix(".yaml")
        )
        _write_yaml(yaml_path, document)
        written.append(yaml_path)
    if format_ in ("csv", "both"):
        csv_path = output_path if format_ == "csv" else output_path.with_suffix(".csv")
        _write_csv(csv_path, candidates)
        written.append(csv_path)
    return written


def main() -> int:
    args = parse_args()

    loaded = _load_html(args)
    if loaded is None:
        return 1 if args.input_html else 3
    html, source_url, source_label = loaded

    tables = extract_tables(html)
    member_table = find_member_table(tables)
    if member_table is None:
        print("[エラー] メンバー一覧テーブルを検出できませんでした", file=sys.stderr)
        return 2

    rows = rows_to_dicts(member_table)
    character_dictionary = load_character_dictionary(args.characters)
    candidates = match_candidates(rows, character_dictionary, source_label)

    matched = sum(1 for c in candidates if c["matchStatus"] == "matched")
    unmatched = len(candidates) - matched

    if not args.quiet:
        print(f"[import] 検出した行数: {len(rows)}")
        print(f"[import]   matched:   {matched}")
        print(f"[import]   unmatched: {unmatched}")

    if args.dry_run:
        if not args.quiet:
            print("[import] --dry-run: candidate fileへの書き出しはスキップしました")
        return 0

    if args.output:
        written = _write_candidate_outputs(
            args.output, args.format, candidates, source_url
        )
        if not args.quiet:
            print(
                "[import] candidate fileを書き出しました (commit禁止・ローカル確認用):"
            )
            for path in written:
                print(f"  - {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
