#!/usr/bin/env python3
"""Classify Evidence Index stories for batch promotion.

The command consumes the additive per-story counts in the report produced by
``build_evidence_index_candidates.py --public-profile default`` and the
corresponding Normalized Story JSON documents. It only writes workspace report
artifacts; it never promotes data or changes the Public ID Registry.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.wiki_generator.promotion_candidates import (  # noqa: E402
    PROMOTION_CANDIDATE,
    VALID_PARSER_COMPATIBILITIES,
    classify_promotion_candidate,
)

DEFAULT_PUBLIC_EVIDENCE_TYPES = frozenset(
    {"dialogue", "monologue", "narration", "choice", "unknown"}
)
PARSER_COMPATIBILITY_ORDER = {
    "compatible": 0,
    "warning": 1,
    "needs_update": 2,
    "blocked": 3,
}


class ClassificationInputError(ValueError):
    """Raised when an input cannot be classified without discarding data."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evidence Index generation reportとNormalized Story JSONから"
            "batch promotion候補をstory単位で分類する"
        )
    )
    parser.add_argument(
        "--report",
        required=True,
        help="build_evidence_index_candidates.pyが出力したreport.json",
    )
    parser.add_argument(
        "--normalized-input",
        required=True,
        help="Normalized Story JSONファイル、または再帰的に*.jsonを収集するdirectory",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="classification_report.json/.mdの出力directory (workspace配下を想定)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ClassificationInputError(
            f"{path}: 読み込みに失敗しました: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ClassificationInputError(
            f"{path}: JSONの解析に失敗しました: {exc}"
        ) from exc


def _collect_json_paths(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() != ".json":
            raise ClassificationInputError(
                f"--normalized-inputはJSONファイルを指定してください: {path}"
            )
        return [path]
    if not path.is_dir():
        raise ClassificationInputError(
            f"--normalized-inputパスが見つかりません: {path}"
        )
    paths = sorted(
        candidate for candidate in path.rglob("*.json") if candidate.is_file()
    )
    if not paths:
        raise ClassificationInputError(
            f"--normalized-input配下にJSONファイルがありません: {path}"
        )
    return paths


def _validate_count(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ClassificationInputError(f"{label}は0以上の整数である必要があります")
    return value


def _parse_count_mapping(value: Any, *, label: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ClassificationInputError(f"{label}はobjectである必要があります")
    counts: dict[str, int] = {}
    for evidence_type, raw_count in value.items():
        if not isinstance(evidence_type, str) or not evidence_type:
            raise ClassificationInputError(
                f"{label}のevidenceTypeは空でない文字列である必要があります"
            )
        counts[evidence_type] = _validate_count(
            raw_count, label=f"{label}.{evidence_type}"
        )
    return counts


def _load_story_reports(report_path: Path) -> list[dict[str, Any]]:  # noqa: C901
    raw = _load_json(report_path)
    if not isinstance(raw, dict):
        raise ClassificationInputError("report.jsonのrootはobjectである必要があります")
    if raw.get("publicProfile") != "default":
        raise ClassificationInputError(
            "report.jsonは--public-profile defaultで生成されている必要があります"
        )

    included_types = raw.get("includedTypes")
    if (
        not isinstance(included_types, list)
        or any(not isinstance(item, str) for item in included_types)
        or frozenset(included_types) != DEFAULT_PUBLIC_EVIDENCE_TYPES
    ):
        raise ClassificationInputError(
            "report.jsonのincludedTypesがpublic-profile defaultの集合と一致しません"
        )

    raw_story_reports = raw.get("storyReports")
    if not isinstance(raw_story_reports, list):
        raise ClassificationInputError(
            "report.jsonにstoryReports配列がありません。"
            "最新のbuild_evidence_index_candidates.pyで再生成してください"
        )

    story_reports: list[dict[str, Any]] = []
    seen_story_ids: set[str] = set()
    aggregate_counts: dict[str, int] = {}
    for index, item in enumerate(raw_story_reports):
        label = f"storyReports[{index}]"
        if not isinstance(item, dict):
            raise ClassificationInputError(f"{label}はobjectである必要があります")
        story_id = item.get("storyId")
        if not isinstance(story_id, str) or not story_id.strip():
            raise ClassificationInputError(
                f"{label}.storyIdは空でない文字列である必要があります"
            )
        story_id = story_id.strip()
        if story_id in seen_story_ids:
            raise ClassificationInputError(
                f"report.jsonのstoryIdが重複しています: {story_id}"
            )
        seen_story_ids.add(story_id)

        counts = _parse_count_mapping(
            item.get("entriesByEvidenceType"),
            label=f"{label}.entriesByEvidenceType",
        )
        entry_count = _validate_count(
            item.get("entryCount"), label=f"{label}.entryCount"
        )
        if entry_count != sum(counts.values()):
            raise ClassificationInputError(
                f"{label}.entryCountとentriesByEvidenceTypeの合計が一致しません"
            )
        for evidence_type, count in counts.items():
            aggregate_counts[evidence_type] = (
                aggregate_counts.get(evidence_type, 0) + count
            )
        story_reports.append(
            {
                "storyId": story_id,
                "entryCount": entry_count,
                "entriesByEvidenceType": counts,
            }
        )

    story_count = raw.get("storyCount")
    if story_count is not None and (
        _validate_count(story_count, label="storyCount") != len(story_reports)
    ):
        raise ClassificationInputError(
            "report.jsonのstoryCountとstoryReports件数が一致しません"
        )
    global_counts = _parse_count_mapping(
        raw.get("entriesByEvidenceType"), label="entriesByEvidenceType"
    )
    if aggregate_counts != global_counts:
        raise ClassificationInputError(
            "report.jsonの全体entriesByEvidenceTypeとstoryReports集計が一致しません"
        )
    return sorted(story_reports, key=lambda item: item["storyId"])


def _load_parser_compatibilities(
    normalized_input: Path,
    required_story_ids: set[str],
) -> dict[str, str]:
    statuses_by_story: dict[str, list[str]] = {
        story_id: [] for story_id in required_story_ids
    }
    for path in _collect_json_paths(normalized_input):
        raw = _load_json(path)
        if not isinstance(raw, dict):
            raise ClassificationInputError(f"{path}: rootはobjectである必要があります")
        story_id = raw.get("storyId")
        if not isinstance(story_id, str) or not story_id.strip():
            raise ClassificationInputError(
                f"{path}: storyIdは空でない文字列である必要があります"
            )
        story_id = story_id.strip()
        if story_id not in required_story_ids:
            continue
        compatibility_report = raw.get("compatibilityReport")
        if not isinstance(compatibility_report, dict):
            raise ClassificationInputError(f"{path}: compatibilityReportがありません")
        status = compatibility_report.get("parserCompatibility")
        if status not in VALID_PARSER_COMPATIBILITIES:
            raise ClassificationInputError(
                f"{path}: parserCompatibilityが不正です: {status!r}"
            )
        statuses_by_story[story_id].append(status)

    missing = sorted(
        story_id for story_id, statuses in statuses_by_story.items() if not statuses
    )
    if missing:
        raise ClassificationInputError(
            "Normalized Story JSONが見つからないstoryId: " + ", ".join(missing)
        )

    return {
        story_id: max(
            statuses,
            key=lambda status: PARSER_COMPATIBILITY_ORDER[status],
        )
        for story_id, statuses in sorted(statuses_by_story.items())
    }


def classify_report(
    report_path: Path,
    normalized_input: Path,
) -> dict[str, Any]:
    story_reports = _load_story_reports(report_path)
    story_ids = {item["storyId"] for item in story_reports}
    compatibility_by_story = _load_parser_compatibilities(normalized_input, story_ids)

    stories: list[dict[str, Any]] = []
    for item in story_reports:
        story_id = item["storyId"]
        result = classify_promotion_candidate(
            item["entriesByEvidenceType"], compatibility_by_story[story_id]
        )
        stories.append(
            {
                "storyId": story_id,
                "entriesByEvidenceType": item["entriesByEvidenceType"],
                **result.to_dict(),
            }
        )

    return {
        "publicProfile": "default",
        "storyCount": len(stories),
        "stories": stories,
        "promotionCandidateStoryIds": [
            item["storyId"]
            for item in stories
            if item["classification"] == PROMOTION_CANDIDATE
        ],
    }


def _format_percent(value: float) -> str:
    return f"{value:.2%}"


def _build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Evidence Index Promotion Candidate Classification",
        "",
        f"- Public profile: {report['publicProfile']}",
        f"- Story count: {report['storyCount']}",
        "- Promotion candidate story IDs: "
        + (", ".join(report["promotionCandidateStoryIds"]) or "(none)"),
        "",
        "| Story | total | unknown比率 | 意味あるentry比率 | "
        "parserCompat | entry数判定 | 分類 |",
        "|---|---:|---:|---:|---|---|---|",
    ]
    for story in report["stories"]:
        entry_count_status = (
            "保留（600超）"
            if story["entryCountReviewRequired"]
            else "候補可（600以下）"
        )
        classification = (
            "human-review-required"
            if story["humanReviewRequired"]
            else story["classification"]
        )
        lines.append(
            f"| `{story['storyId']}` | {story['totalEntryCount']} | "
            f"{_format_percent(story['unknownRatio'])} | "
            f"{_format_percent(story['meaningfulRatio'])} | "
            f"{story['parserCompatibility']} | {entry_count_status} | "
            f"{classification} |"
        )
    lines.append("")
    return "\n".join(lines)


def _write_reports(output_dir: Path, report: dict[str, Any]) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "classification_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "classification_report.md").write_text(
            _build_markdown(report), encoding="utf-8"
        )
    except OSError as exc:
        raise ClassificationInputError(
            f"分類reportの書き込みに失敗しました: {exc}"
        ) from exc


def main() -> int:
    args = parse_args()
    try:
        report = classify_report(Path(args.report), Path(args.normalized_input))
        _write_reports(Path(args.output), report)
    except ClassificationInputError as exc:
        print(f"[エラー] {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"[エラー] 判定入力が不正です: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(
            f"[classify] {report['storyCount']} storyを分類し、"
            f"{len(report['promotionCandidateStoryIds'])} storyを"
            "promotion-candidateと判定しました"
        )
        print(f"[classify] 出力先: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
