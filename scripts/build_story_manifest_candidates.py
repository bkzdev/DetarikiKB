#!/usr/bin/env python3
"""
Build Story Manifest Candidates
ローカルのraw DECファイル配置（`EVENT`・`CHARACTER`・`CHARACTER_DATE`カテゴリ）
から、`story_manifest.yaml`候補（`schemas/story_manifest.schema.json`準拠）を
機械的に生成するCLI。

コアロジックは`agents/parser/story_manifest_candidates.py`にある
(このCLIはそのCLIエントリポイント)。

docs/architecture/05_Parser/Story_Manifest_Design.md、
docs/architecture/05_Parser/Character_Story_ID_Manifest_Design.md 参照。

**重要**: このscriptはDEC本文を一切読まない（ファイル名・ディレクトリ名の
文字列処理のみ）。title/subtitle/displayTitleは常にnull、metadataStatusは
常にpendingとして出力する（DEC本文からタイトル・サブタイトルを推測する処理は
一切行わない）。実DECファイル・生成したmanifest候補はcommitしないこと
（`.gitignore`のworkspace/story_manifest/・story_manifest_candidates_*
パターンを参照）。

対応するraw配置（EVENT・CHARACTER・CHARACTER_DATEカテゴリ、MAIN/RAID/OTHERは
未対応、Story_Manifest_Design.md §18 OD-002）:

    EVENT/csl_script_event_{sourceKey}_export/
        CAB-csl_script_event_{sourceKey}-episode{N}.dec

    CHARACTER/csl_script_charastory_character{N}_export/
        CAB-csl_script_charastory_character{N}-episode{M}.dec
        CAB-csl_script_charastory_character{N}-episode_EX{M}.dec
        CAB-csl_script_charastory_character{N}-H_scene{M}.dec
        CAB-csl_script_charastory_character{N}-H_scene_s.dec
        (その他の変種・演出コマンド専用ファイルはauxiliaryFilesとして記録)

    CHARACTER_DATE/csl_script_surprise_character{N}_export/
        CAB-csl_script_surprise_character{N}-Surprise_{M}.dec

CHARACTER/CHARACTER_DATEの`{N}`（sourceCharacterId）は、
`knowledge/dictionaries/characters.yaml`（`--character-dictionary`で指定、
既定値`knowledge/dictionaries/characters.yaml`）でstatus: confirmedとして
登録されているキャラクターのみcandidateを生成する。未confirmedのキャラクター・
`{N}`が一致しないファイル・紐づけ先の無いauxiliaryFilesは、黙って除外せず
標準出力へpending報告として表示する（`--quiet`指定時は抑制）。

Usage:
    uv run python scripts/build_story_manifest_candidates.py \\
        --raw-root /path/to/local/raw/root

    uv run python scripts/build_story_manifest_candidates.py \\
        --raw-root /path/to/local/raw/root \\
        --output workspace/story_manifest/candidates.yaml

    uv run python scripts/build_story_manifest_candidates.py \\
        --raw-root /path/to/local/raw/root \\
        --character-dictionary knowledge/dictionaries/characters.yaml

Exit codes:
    0: 成功（該当するストーリーが0件でも成功）
    1: --raw-rootが存在しない、またはディレクトリでない
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.parser.character_dictionary import load_character_dictionary  # noqa: E402
from agents.parser.story_manifest_candidates import (  # noqa: E402
    build_candidate_document,
    build_character_story_manifest_candidates,
    build_story_manifest_candidates,
)

_DEFAULT_CHARACTER_DICTIONARY = (
    _PROJECT_ROOT / "knowledge" / "dictionaries" / "characters.yaml"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "ローカルのraw DECファイル配置 (EVENT/CHARACTER/CHARACTER_DATE"
            "カテゴリ) から story_manifest.yaml候補を機械的に生成する"
        ),
    )
    parser.add_argument(
        "--raw-root",
        required=True,
        help=(
            "raw DECファイル群のルートディレクトリ "
            "(EVENT/CHARACTER/CHARACTER_DATE等を直下に含む)"
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        help="生成したmanifest候補 (YAML) の書き出し先。省略時は件数サマリーのみ表示",
    )
    parser.add_argument(
        "--character-dictionary",
        default=str(_DEFAULT_CHARACTER_DICTIONARY),
        help=(
            "CHARACTER/CHARACTER_DATEの{N}->characterId解決に使うcharacters.yaml "
            "のパス (既定値: knowledge/dictionaries/characters.yaml)。confirmed "
            "でないキャラクターはcandidate生成対象外とし、pending報告に含める"
        ),
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

    raw_root = Path(args.raw_root)
    if not raw_root.is_dir():
        print(
            f"[エラー] --raw-rootがディレクトリとして見つかりません: {raw_root}",
            file=sys.stderr,
        )
        return 1

    event_candidates = build_story_manifest_candidates(raw_root)

    dictionary_entries = load_character_dictionary(args.character_dictionary)
    character_candidates, character_report = build_character_story_manifest_candidates(
        raw_root, dictionary_entries
    )

    candidates = event_candidates + character_candidates
    candidates.sort(key=lambda story: story["storyId"])
    document = build_candidate_document(candidates)
    episode_count = sum(len(story["episodes"]) for story in candidates)

    if not args.quiet:
        print(
            f"[story-manifest] 検出したストーリー数: {len(candidates)} "
            f"(episode合計: {episode_count})"
        )
        for story in candidates:
            print(f"  - {story['storyId']} ({len(story['episodes'])} episodes)")

        if character_report:
            print(
                f"[story-manifest] 未解決の報告: {len(character_report)} 件 "
                "(黙って除外していません。人間確認が必要です)"
            )
            for issue in character_report:
                detail = issue.get("detail", "")
                path = issue.get("path")
                if path:
                    print(
                        f"  - [{issue['issueType']}] "
                        f"sourceCharacterId={issue.get('sourceCharacterId')} "
                        f"path={path}: {detail}"
                    )
                else:
                    print(
                        f"  - [{issue['issueType']}] "
                        f"sourceCharacterId={issue.get('sourceCharacterId')}: {detail}"
                    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(document, f, allow_unicode=True, sort_keys=False)
        if not args.quiet:
            print(f"[story-manifest] 候補を書き出しました: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
