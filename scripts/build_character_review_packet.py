#!/usr/bin/env python3
"""
Build Character Review Packet
merged knowledge collection (schemas/merged_knowledge_collection.schema.json)
とキャラクター辞書 (knowledge/dictionaries/characters.yaml) から、人間が
sourceCharacterId -> characterId mapping を確認・記入しやすい
review packet (YAML/CSV) をローカルへ書き出す補助スクリプト。

**このスクリプトが生成するpacket自体はcommitしない**
(docs/runbooks/Character_Dictionary_Review.md 参照)。出力先は必ず
.gitignore対象のローカル領域 (workspace/review_packets/ 等) を指定する
こと。

packetに含まれるのは sourceCharacterId・displayName・辞書の既存状態・
件数統計・空のレビュー用プレースホルダーのみで、元セリフ・raw payload・
merged collection全文は一切含まない (build_character_review_packet参照)。

Usage:
    uv run python scripts/build_character_review_packet.py \\
        --merged-collection \\
        workspace/dry_runs/<RUN_ID>/merged/merged_knowledge_collection.json \\
        --output workspace/review_packets/character_dictionary_review_batch_003.yaml

    # CSVでも欲しい場合
    uv run python scripts/build_character_review_packet.py \\
        --merged-collection <path> \\
        --output workspace/review_packets/character_dictionary_review_batch_003 \\
        --format both

Exit codes:
    0: 生成成功
    1: 入力ファイルが見つからない、またはJSONとして読み込めない
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.parser.character_dictionary import (  # noqa: E402
    build_character_review_packet,
    load_character_dictionary,
)

DEFAULT_DICTIONARY_PATH = (
    _PROJECT_ROOT / "knowledge" / "dictionaries" / "characters.yaml"
)

_CSV_FIELDS = (
    "sourceCharacterId",
    "displayName",
    "existingDictionaryStatus",
    "existingCharacterId",
    "aliases",
    "observedCount",
    "appearedEpisodeCount",
    "sourceDocumentCount",
    "humanReviewStatus",
    "humanConfirmedCharacterId",
    "notes",
)

_PACKET_HEADER = """\
# Character Dictionary Review Packet (auto-generated)
#
# scripts/build_character_review_packet.py が自動生成したローカル確認用
# ファイルです。
#
# 重要: このファイルはcommitしないでください
# (docs/runbooks/Character_Dictionary_Review.md 参照)。
# 人間が sourceCharacterId ごとに実データを直接確認し、
# humanConfirmedCharacterId / humanReviewStatus / notes を埋めたうえで、
# 確認済み (humanReviewStatus: confirmed) のエントリだけを
# workspace/local_inputs/character_confirmed_batch_XXX.yaml へ切り出し、
# 次のconfirmed-batch PRで knowledge/dictionaries/characters.yaml へ
# 反映すること。名前が一致するというだけの理由でconfirmedにしないこと。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "merged knowledge collectionとキャラクター辞書から、人間確認用の"
            "review packet (YAML/CSV) をローカルへ書き出す"
        ),
    )
    parser.add_argument(
        "--merged-collection",
        required=True,
        help="merged knowledge collection JSONのパス",
    )
    parser.add_argument(
        "--dictionary",
        default=str(DEFAULT_DICTIONARY_PATH),
        help=f"キャラクター辞書YAMLのパス (デフォルト: {DEFAULT_DICTIONARY_PATH})",
    )
    parser.add_argument(
        "--output",
        required=True,
        help=(
            "出力先パス (拡張子は--formatに応じて自動付与される)。"
            "commit対象外のローカルパス (例: workspace/review_packets/配下) "
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
        "--batch-id",
        default="character-dictionary-review-packet",
        help="packet内のreviewBatchId (デフォルト: character-dictionary-review-packet)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


def _output_path_for(output: Path, suffix: str, format_: str) -> Path:
    """--formatがbothの場合、拡張子をそれぞれ付け替えたパスを返す。"""
    if format_ == "both":
        return output.with_suffix(suffix)
    return output if output.suffix else output.with_suffix(suffix)


def write_yaml_packet(path: Path, batch_id: str, sources: dict, entries: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    packet = {
        "reviewBatchId": batch_id,
        "generatedFrom": sources,
        "entries": entries,
    }
    with open(path, "w", encoding="utf-8") as f:
        f.write(_PACKET_HEADER)
        yaml.safe_dump(packet, f, allow_unicode=True, sort_keys=False)


def write_csv_packet(path: Path, entries: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for entry in entries:
            row = dict(entry)
            row["aliases"] = "|".join(entry.get("aliases") or [])
            writer.writerow(row)


def main() -> int:
    args = parse_args()

    merged_collection_path = Path(args.merged_collection)
    if not merged_collection_path.exists():
        print(
            f"[エラー] merged collectionが見つかりません: {merged_collection_path}",
            file=sys.stderr,
        )
        return 1
    try:
        with open(merged_collection_path, encoding="utf-8") as f:
            collection = json.load(f)
    except json.JSONDecodeError:
        print(
            f"[エラー] JSONとして読み込めませんでした: {merged_collection_path}",
            file=sys.stderr,
        )
        return 1

    dictionary_path = Path(args.dictionary)
    dictionary_entries = load_character_dictionary(dictionary_path)
    entries = build_character_review_packet(collection, dictionary_entries)

    sources = {
        "dictionary": str(dictionary_path),
        "source": str(merged_collection_path),
    }
    output = Path(args.output)
    written: list[Path] = []

    if args.format in ("yaml", "both"):
        yaml_path = _output_path_for(output, ".yaml", args.format)
        write_yaml_packet(yaml_path, args.batch_id, sources, entries)
        written.append(yaml_path)
    if args.format in ("csv", "both"):
        csv_path = _output_path_for(output, ".csv", args.format)
        write_csv_packet(csv_path, entries)
        written.append(csv_path)

    if not args.quiet:
        print(
            f"[review-packet] {len(entries)} 件のレビュー候補を書き出しました "
            "(commit禁止・ローカル確認用):"
        )
        for path in written:
            print(f"  - {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
