#!/usr/bin/env python3
"""Normalized release scope全件からStage A抽出とStage B統合を一括実行する。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.extractor.release_scope import build_release_scope_knowledge  # noqa: E402

DEFAULT_STORY_SCHEMA = _PROJECT_ROOT / "schemas" / "story.schema.json"
DEFAULT_EXTRACTION_SCHEMA = _PROJECT_ROOT / "schemas" / "extraction.schema.json"
DEFAULT_COLLECTION_SCHEMA = (
    _PROJECT_ROOT / "schemas" / "merged_knowledge_collection.schema.json"
)
DEFAULT_REPORT_SCHEMA = (
    _PROJECT_ROOT / "schemas" / "release_scope_knowledge_report.schema.json"
)
DEFAULT_NORMALIZATION_REPORT_SCHEMA = (
    _PROJECT_ROOT / "schemas" / "release_scope_normalization_report.schema.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalized release scopeをfail-closedで抽出・統合します"
    )
    parser.add_argument("--normalized-root", required=True)
    parser.add_argument(
        "--normalization-report",
        help="M2匿名report。省略時はnormalized rootの親directoryから読みます",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--story-schema", default=str(DEFAULT_STORY_SCHEMA))
    parser.add_argument("--extraction-schema", default=str(DEFAULT_EXTRACTION_SCHEMA))
    parser.add_argument("--collection-schema", default=str(DEFAULT_COLLECTION_SCHEMA))
    parser.add_argument("--report-schema", default=str(DEFAULT_REPORT_SCHEMA))
    parser.add_argument(
        "--normalization-report-schema",
        default=str(DEFAULT_NORMALIZATION_REPORT_SCHEMA),
    )
    parser.add_argument("--quiet", "-q", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    normalized_root = Path(args.normalized_root)
    normalization_report = (
        Path(args.normalization_report)
        if args.normalization_report
        else normalized_root.parent / "release_scope_normalization_report.json"
    )
    try:
        report = build_release_scope_knowledge(
            normalized_root=normalized_root,
            output_root=Path(args.output),
            story_schema_path=Path(args.story_schema),
            extraction_schema_path=Path(args.extraction_schema),
            collection_schema_path=Path(args.collection_schema),
            report_schema_path=Path(args.report_schema),
            normalization_report_path=normalization_report,
            normalization_report_schema_path=Path(args.normalization_report_schema),
        )
    except Exception as exc:
        print(f"[release-scope-knowledge] failed: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
