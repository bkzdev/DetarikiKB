#!/usr/bin/env python3
"""Release scope M4 curation readinessを匿名集約する。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.extractor.release_curation_readiness import (  # noqa: E402
    build_release_curation_readiness_report,
)

_DRY_RUN_ROOT = (_PROJECT_ROOT / "workspace" / "dry_runs").resolve()
_SCHEMA_ROOT = _PROJECT_ROOT / "schemas"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "canonical ID/profile/story内・story間Timelineのreview準備状況を集約します"
        )
    )
    parser.add_argument("--normalization-report", required=True)
    parser.add_argument("--knowledge-report", required=True)
    parser.add_argument("--collection", required=True)
    parser.add_argument(
        "--character-dictionary", default="knowledge/dictionaries/characters.yaml"
    )
    parser.add_argument(
        "--character-profiles",
        default="knowledge/dictionaries/character_profiles.yaml",
    )
    parser.add_argument("--story-timeline-report", required=True)
    parser.add_argument("--canonical-timeline", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--quiet", "-q", action="store_true")
    return parser.parse_args()


def _output_path(raw: str) -> Path:
    path = Path(raw)
    resolved = path.resolve()
    try:
        resolved.relative_to(_DRY_RUN_ROOT)
    except ValueError as exc:
        raise ValueError("outputはworkspace/dry_runs配下に指定してください") from exc
    if path.exists():
        raise FileExistsError("outputは既に存在します")
    return path


def main() -> int:
    args = parse_args()
    try:
        output = _output_path(args.output)
        report = build_release_curation_readiness_report(
            normalization_report_path=Path(args.normalization_report),
            knowledge_report_path=Path(args.knowledge_report),
            collection_path=Path(args.collection),
            character_dictionary_path=Path(args.character_dictionary),
            character_profiles_path=Path(args.character_profiles),
            story_timeline_report_path=Path(args.story_timeline_report),
            canonical_timeline_path=Path(args.canonical_timeline),
            schema_root=_SCHEMA_ROOT,
        )
        schema = json.loads(
            (
                _SCHEMA_ROOT / "release_scope_curation_readiness_report.schema.json"
            ).read_text(encoding="utf-8")
        )
        errors = list(Draft7Validator(schema).iter_errors(report))
        if errors:
            raise ValueError(f"report schema validation failed: {errors[0].message}")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as destination:
            json.dump(report, destination, ensure_ascii=False, indent=2, sort_keys=True)
            destination.write("\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"[release-scope-curation-readiness] failed: {exc}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(
            "[release-scope-curation-readiness] "
            f"reviewable={str(report['reviewable']).lower()} output={output}"
        )
    return 0 if report["reviewable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
