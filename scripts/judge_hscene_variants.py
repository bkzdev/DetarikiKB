#!/usr/bin/env python3
"""
Judge H_scene Variants
`character`カテゴリのH_sceneN本体ファイル(群)に対し、対応する変種ファイル
(`_n`/`_spine`/`#K`/`_n #K`/`_spine #K`)が本体の内容の部分集合かどうかを
動的判定する (`_VR`は判定対象外、常にスキップする)。

設計根拠:
    docs/architecture/01_Project/03_Scope.md §5.3・§5.5.1
    docs/architecture/05_Parser/Character_Story_ID_Manifest_Design.md §6・§9 (PR D)

判定ロジック本体は agents/parser/hscene_variant_judgment.py。

判定結果 (実ファイル名を含む) はworkspace限定のレポートとして出力し、
commitしない (`docs/runbooks/AI_PR_Playbook.md` §7)。

Usage:
    # 判定のみ (本体1ファイル指定)
    python scripts/judge_hscene_variants.py \\
        --input data/raw/character/.../CAB-...-H_scene1.dec \\
        --story-id CHAR_HS_EXAMPLE \\
        --report-output workspace/dry_runs/hscene_variant_judgment/report

    # 判定のみ (キャラクターexportディレクトリ全体、再帰的にH_sceneN本体を検出)
    python scripts/judge_hscene_variants.py \\
        --input data/raw/character/csl_script_charastory_character10_export \\
        --story-id CHAR_HS_EXAMPLE

    # data/raw/character/ 全量への判定 (storyId未指定でも判定自体は可能。
    # --normalizeにはstoryIdごとのディレクトリ単位実行を想定)
    python scripts/judge_hscene_variants.py --input data/raw/character/

    # 例外変種のnormalizeまで実行 (storyCategory CHAR_HS固定)
    python scripts/judge_hscene_variants.py \\
        --input data/raw/character/csl_script_charastory_character10_export \\
        --story-id CHAR_HS_EXAMPLE \\
        --normalize --output workspace/dry_runs/hscene_variant_judgment/normalized
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# プロジェクトルートを sys.path に追加
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.parser import (  # noqa: E402
    BodyJudgmentResult,
    CharacterDictionary,
    Exporter,
    Normalizer,
    StoryParser,
    VariantJudgmentResult,
    find_hscene_body_files,
    judge_body_variants,
)
from agents.parser.hscene_variant_judgment import hscene_number  # noqa: E402
from agents.parser.tokenizer import Tokenizer  # noqa: E402

DEFAULT_CHARACTERS_PATH = (
    _PROJECT_ROOT / "knowledge" / "dictionaries" / "characters.yaml"
)
DEFAULT_COMMANDS_CONFIG = _PROJECT_ROOT / "config" / "script_commands.yaml"
DEFAULT_NORMALIZE_OUTPUT = (
    _PROJECT_ROOT / "workspace" / "dry_runs" / "hscene_variant_judgment" / "normalized"
)

_VARIANT_PATTERNS: tuple[str, ...] = (
    "n",
    "spine",
    "hash",
    "n_hash",
    "spine_hash",
    "vr",
)


# ----------------------------------------------------------------
# Argument Parser
# ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="H_sceneN変種の動的部分集合判定を実行します",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="H_sceneN本体ファイル、またはキャラクターexportディレクトリ (再帰検出)",
    )
    parser.add_argument(
        "--story-id",
        default=None,
        help=(
            "base storyId (例: CHAR_HS_EXAMPLE)。指定するとbaseEpisodeId "
            "({story-id}_E{N:02d}) が導出され、exception変種のepisodeIdも"
            "§6.2のsuffix規則で導出される。--normalize指定時は必須"
        ),
    )
    parser.add_argument(
        "--normalize",
        action="store_true",
        help="exception判定された変種を別episode(storyCategory CHAR_HS)でnormalizeする",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_NORMALIZE_OUTPUT),
        help=f"--normalize出力先 (デフォルト: {DEFAULT_NORMALIZE_OUTPUT})",
    )
    parser.add_argument(
        "--report-output",
        default=None,
        help="判定レポートの出力先パス (拡張子なし。--report-formatで.json/.mdを付与)",
    )
    parser.add_argument(
        "--report-format",
        choices=["json", "markdown", "both"],
        default="json",
        help="判定レポートの出力形式 (デフォルト: json)",
    )
    parser.add_argument(
        "--characters",
        default=str(DEFAULT_CHARACTERS_PATH),
        help=f"キャラクター辞書 (デフォルト: {DEFAULT_CHARACTERS_PATH})",
    )
    parser.add_argument(
        "--commands",
        default=str(DEFAULT_COMMANDS_CONFIG),
        help=f"コマンド辞書 YAML (デフォルト: {DEFAULT_COMMANDS_CONFIG})",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する (サマリーは表示する)",
    )
    return parser.parse_args()


# ----------------------------------------------------------------
# Report building
# ----------------------------------------------------------------


def _variant_to_dict(v: VariantJudgmentResult) -> dict[str, Any]:
    return {
        "variantFile": str(v.variant.path),
        "pattern": v.variant.pattern,
        "dupIndex": v.variant.dup_index,
        "judgment": v.judgment,
        "bodyIdentifierCount": v.body_identifier_count,
        "variantIdentifierCount": v.variant_identifier_count,
        "extraInVariantCount": v.extra_in_variant_count,
        "derivedEpisodeId": v.derived_episode_id,
    }


def _body_to_dict(b: BodyJudgmentResult) -> dict[str, Any]:
    return {
        "bodyFile": str(b.body_path),
        "hSceneNumber": b.hscene_number,
        "baseEpisodeId": b.base_episode_id,
        "bodyIdentifierCount": b.body_identifier_count,
        "variants": [_variant_to_dict(v) for v in b.variants],
    }


def summarize_body_results(bodies: list[BodyJudgmentResult]) -> dict[str, Any]:
    """パターン別のsubset/exception/skipped_vr件数を集計する。"""
    by_pattern: dict[str, dict[str, int]] = {
        p: {"total": 0, "subset": 0, "exception": 0, "skipped_vr": 0}
        for p in _VARIANT_PATTERNS
    }
    total_subset = 0
    total_exception = 0
    total_skipped_vr = 0

    for body in bodies:
        for v in body.variants:
            bucket = by_pattern[v.variant.pattern]
            bucket["total"] += 1
            bucket[v.judgment] += 1
            if v.judgment == "subset":
                total_subset += 1
            elif v.judgment == "exception":
                total_exception += 1
            elif v.judgment == "skipped_vr":
                total_skipped_vr += 1

    return {
        "bodyCount": len(bodies),
        "byPattern": by_pattern,
        "totalSubset": total_subset,
        "totalException": total_exception,
        "totalSkippedVr": total_skipped_vr,
    }


def build_report(
    bodies: list[BodyJudgmentResult],
    input_path: str,
    story_id: str | None,
) -> dict[str, Any]:
    return {
        "generatedAt": datetime.now(tz=timezone.utc).isoformat(),
        "input": input_path,
        "storyId": story_id,
        "bodies": [_body_to_dict(b) for b in bodies],
        "summary": summarize_body_results(bodies),
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# H_scene Variant Judgment Report")
    lines.append("")
    lines.append(f"- generatedAt: {report['generatedAt']}")
    lines.append(f"- input: {report['input']}")
    lines.append(f"- storyId: {report['storyId']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- bodyCount: {report['summary']['bodyCount']}")
    lines.append(f"- totalSubset: {report['summary']['totalSubset']}")
    lines.append(f"- totalException: {report['summary']['totalException']}")
    lines.append(
        f"- totalSkippedVr (`_VR`, 判定対象外): {report['summary']['totalSkippedVr']}"
    )
    lines.append("")
    lines.append("| pattern | total | subset | exception | skipped_vr |")
    lines.append("|---|---|---|---|---|")
    for pattern, counts in report["summary"]["byPattern"].items():
        lines.append(
            f"| {pattern} | {counts['total']} | {counts['subset']} | "
            f"{counts['exception']} | {counts['skipped_vr']} |"
        )
    lines.append("")
    lines.append("## Bodies")
    lines.append("")
    for body in report["bodies"]:
        lines.append(f"### {body['bodyFile']} (H_scene{body['hSceneNumber']})")
        lines.append("")
        lines.append(f"- baseEpisodeId: {body['baseEpisodeId']}")
        lines.append(f"- bodyIdentifierCount: {body['bodyIdentifierCount']}")
        if body["variants"]:
            lines.append("")
            lines.append(
                "| variant | pattern | dupIndex | judgment | variantIdentifierCount | "
                "extraInVariantCount | derivedEpisodeId |"
            )
            lines.append("|---|---|---|---|---|---|---|")
            for v in body["variants"]:
                lines.append(
                    f"| {v['variantFile']} | {v['pattern']} | {v['dupIndex']} | "
                    f"{v['judgment']} | {v['variantIdentifierCount']} | "
                    f"{v['extraInVariantCount']} | {v['derivedEpisodeId']} |"
                )
        lines.append("")
    return "\n".join(lines)


def write_report(
    report: dict[str, Any], report_output: str, report_format: str, quiet: bool
) -> None:
    output_path = Path(report_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if report_format in ("json", "both"):
        json_path = output_path.with_suffix(".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        if not quiet:
            print(f"[DKB] レポート出力 (JSON): {json_path}")

    if report_format in ("markdown", "both"):
        md_path = output_path.with_suffix(".md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(render_markdown_report(report))
        if not quiet:
            print(f"[DKB] レポート出力 (Markdown): {md_path}")


# ----------------------------------------------------------------
# --normalize: 例外変種のnormalize実行
# ----------------------------------------------------------------


def _normalize_exception_variant(
    variant: VariantJudgmentResult,
    body: BodyJudgmentResult,
    story_id: str,
    char_dict: CharacterDictionary,
    output_dir: Path,
    commands_config_path: str,
    quiet: bool,
) -> Path:
    """1件のexception変種を、CHAR_HSカテゴリの別episodeとしてnormalizeし出力する。

    既存のnormalize経路 (StoryParser -> Normalizer -> Exporter) を再利用する
    (scripts/normalize_story.pyの本体改修はしない、Character_Story_ID_
    Manifest_Design.md §9のPR D方針どおり)。
    """
    episode_id = variant.derived_episode_id
    if episode_id is None:
        raise ValueError(
            "derivedEpisodeIdが未設定です (story_id未指定の可能性): "
            f"{variant.variant.path}"
        )

    input_path = variant.variant.path

    story_parser = StoryParser(
        char_dict=char_dict,
        preserve_stage_directions=True,
        preserve_unknown=True,
        source_file=input_path.stem,
    )
    parse_result = story_parser.parse_file(input_path)

    variant_trace = {
        "baseEpisodeId": body.base_episode_id,
        "variantPattern": variant.variant.pattern,
        "dupIndex": variant.variant.dup_index,
        "judgment": variant.judgment,
        "bodyIdentifierCount": variant.body_identifier_count,
        "variantIdentifierCount": variant.variant_identifier_count,
        "extraInVariantCount": variant.extra_in_variant_count,
    }

    normalizer = Normalizer(
        story_id=story_id,
        story_category="CHAR_HS",
        episode_id=episode_id,
        source_file=input_path.stem,
        source_path=str(input_path),
        preserve_stage_directions=True,
        commands_config_path=commands_config_path,
        variant_trace=variant_trace,
    )

    with open(input_path, encoding="utf-8", errors="ignore") as f:
        line_count = sum(1 for _ in f)

    story_json = normalizer.normalize(parse_result, line_count=line_count)

    exporter = Exporter(output_dir=output_dir, overwrite=True)
    output_path = exporter.export_with_category(story_json, f"{episode_id}.json")

    if not quiet:
        print(
            f"[DKB] normalize完了 (exception変種): {input_path.name} -> {output_path}"
        )

    return output_path


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------


def _judge_all_bodies(
    body_files: list[Path], story_id: str | None, quiet: bool
) -> list[BodyJudgmentResult]:
    """本体ファイル群それぞれについて動的部分集合判定を行う。"""
    if not quiet:
        print(f"[DKB] judge_hscene_variants: 本体 {len(body_files)} 件を判定します")

    tokenizer = Tokenizer()
    bodies: list[BodyJudgmentResult] = []
    for body_path in body_files:
        base_episode_id = None
        if story_id:
            num = hscene_number(body_path)
            if num is not None:
                base_episode_id = f"{story_id}_E{num:02d}"
        result = judge_body_variants(
            body_path, base_episode_id=base_episode_id, tokenizer=tokenizer
        )
        bodies.append(result)
    return bodies


def _run_normalize(
    bodies: list[BodyJudgmentResult],
    args: argparse.Namespace,
) -> int:
    """--normalize指定時、exception判定された変種をすべてnormalizeする。
    normalize済み件数を返す。
    """
    char_dict = CharacterDictionary()
    char_path = Path(args.characters)
    if char_path.exists():
        char_dict.load(char_path)
    else:
        print(f"[警告] キャラクター辞書が見つかりません: {char_path}", file=sys.stderr)

    output_dir = Path(args.output)
    normalized_count = 0
    for body in bodies:
        for variant in body.exception_variants:
            _normalize_exception_variant(
                variant,
                body,
                args.story_id,
                char_dict,
                output_dir,
                args.commands,
                args.quiet,
            )
            normalized_count += 1

    if not args.quiet:
        print(f"[DKB] normalize完了: exception変種 {normalized_count} 件")
    return normalized_count


def main() -> int:
    """CLIエントリポイント。各フェーズは_judge_all_bodies/_run_normalize等の
    ヘルパーへ切り出し、ここでは各フェーズを順に呼び出すだけの薄い
    オーケストレーションのみを担う (scripts/normalize_story.pyのmain()と
    同じ分割方針、ruffのC901複雑度対策)。
    """
    args = parse_args()

    if args.normalize and not args.story_id:
        print("[エラー] --normalizeには--story-idの指定が必須です", file=sys.stderr)
        return 1

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[エラー] 入力パスが見つかりません: {input_path}", file=sys.stderr)
        return 1

    body_files = find_hscene_body_files(input_path)
    if not body_files:
        print(
            f"[警告] H_sceneN本体ファイルが見つかりませんでした: {input_path}",
            file=sys.stderr,
        )
        return 0

    bodies = _judge_all_bodies(body_files, args.story_id, args.quiet)

    report = build_report(bodies, str(input_path), args.story_id)
    summary = report["summary"]

    if not args.quiet:
        print(
            "[DKB] 判定結果: "
            f"subset={summary['totalSubset']} exception={summary['totalException']} "
            f"skipped_vr={summary['totalSkippedVr']}"
        )

    if args.report_output:
        write_report(report, args.report_output, args.report_format, args.quiet)

    if args.normalize:
        _run_normalize(bodies, args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
