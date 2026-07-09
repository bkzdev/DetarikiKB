#!/usr/bin/env python3
"""
Check Public Episode IDs
Public Evidence Index候補（`schemas/evidence_index.schema.json`準拠のYAML）から、
`publicEpisodeId`が未確定のepisodeを検出し、公開向けの割当候補
（suggestion）をworkspace配下にのみ出力するcheck-only scriptである
（`feature/evidence-index-public-episode-id-assignment`、
`docs/architecture/06_AI/Public_ID_Registry_Design.md`参照）。

背景（PR #95で判明）:
- `scripts/project_evidence_index_public_ids.py --projection-mode
  public-safe`は`publicEpisodeId`欠落をblocking errorとして扱う（安全策と
  して正しい）
- しかし実データでは、`story_manifest.yaml`側でepisode単位の
  `publicEpisodeId`が未確定のまま残っているケースがあり、そのepisodeの
  entry全件がPublic-safe projectionから弾かれてしまう
- 本scriptは、どのepisodeの`publicEpisodeId`が未確定かを検出し、
  `{publicStoryId}_E{episodeOrder:02d}`形式の割当候補を**提案するだけ**の
  ツールである。`story_manifest.yaml`・Evidence Index・Public ID Registry
  のいずれも自動で書き換えない

**重要な安全方針**:
- `--report`/`--suggestions-output`はいずれも`knowledge/evidence/`・
  `knowledge/public_ids/`配下を指定できない（安全確認で拒否、exit code 2）。
  すべてworkspace配下の一時出力を想定する
- `--input`ファイル自体は読み込みのみで変更しない
- **`--report`/`--suggestions-output`にはsourceKey由来の内部ID
  （`storyId`/`episodeId`/`evidenceId`）・raw title・raw pathを一切出力
  しない**。記録するのは`publicStoryId`/`publicEpisodeId`候補・
  `episodeOrder`（整数）のみ（`Public_ID_Registry_Design.md` §7）。
  `publicStoryId`が1件も無いstory groupは、内部IDの代わりに
  `unidentified-story-group-{N}`という匿名ラベルで報告する
- 割当候補（suggestion）は常に`reviewRequired: true`であり、人間レビュー
  なしに`story_manifest.yaml`やPublic ID Registryへ反映してはならない

publicEpisodeId採番方針（`Public_ID_Registry_Design.md` §3）:
    {publicStoryId}_E{episodeOrder:02d}

`--registry`（任意）:
- Public ID Registry（`schemas/public_id_registry.schema.json`準拠）を
  指定すると、既にRegistryへ記録済みの`(publicStoryId, episodeOrder)`が
  あればその値をそのまま提案として再利用する（一度公開したIDを
  推測で別の値に変えないため）。一致が無ければ従来通り
  `{publicStoryId}_E{episodeOrder:02d}`を提案する
- Registry自体のschema検証に失敗した場合はexit code 2

Non-goals（本scriptで行わないこと。詳細は
`docs/architecture/06_AI/Public_ID_Registry_Design.md` §9参照）:
- `story_manifest.yaml`の書き換え
- Public ID Registryへの実データ追加
- Evidence Indexの書き換え・`knowledge/evidence/stories/`への昇格
- `publicEpisodeId`の自動補完・本番反映

Usage:
    uv run python scripts/check_public_episode_ids.py \\
        --input workspace/evidence_index_dry_runs/<run>/default/stories \\
        --report workspace/public_episode_ids/report.md \\
        --suggestions-output workspace/public_episode_ids/suggestions.yaml

    # Public ID Registryを併用する場合
    uv run python scripts/check_public_episode_ids.py \\
        --input workspace/evidence_index_dry_runs/<run>/default/stories \\
        --registry workspace/public_id_registry/registry.yaml \\
        --report workspace/public_episode_ids/report.md \\
        --suggestions-output workspace/public_episode_ids/suggestions.yaml

Exit codes:
    0: 全episodeにpublicEpisodeIdが割り当て済み（blocking issueなし）
    1: publicEpisodeId欠落、publicStoryId欠落、duplicate publicEpisodeId、
       のいずれかを検出した（`--strict`指定時はepisode内でのconflictも
       blockingに含む）
    2: --input/--schema/--registry/--registry-schemaパスが見つからない、
       registryのschema検証に失敗した、または--report/--suggestions-output
       がknowledge/evidence/・knowledge/public_ids/配下を指しているなどの
       config error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft7Validator

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_evidence_index_promotion import (  # noqa: E402
    DEFAULT_SCHEMA_PATH,
    _collect_yaml_paths,
    _load_yaml_documents,
)

DEFAULT_REGISTRY_SCHEMA_PATH = (
    _PROJECT_ROOT / "schemas" / "public_id_registry.schema.json"
)

# workspace配下のみを出力先として許可する (§安全方針)。
_FORBIDDEN_OUTPUT_DIRS = (
    (_PROJECT_ROOT / "knowledge" / "evidence").resolve(),
    (_PROJECT_ROOT / "knowledge" / "public_ids").resolve(),
)


# ----------------------------------------------------------------
# Argument parser
# ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Public Evidence Index候補からpublicEpisodeId未確定のepisodeを"
            "検出し、割当候補をworkspace配下にのみ提案する (check-only、"
            "story_manifest.yaml/Evidence Index/Public ID Registryのいずれも"
            "自動で書き換えない)"
        ),
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Evidence Index YAMLファイル、またはdirectory (直下の*.yaml/*.ymlを収集)",
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help=f"evidence_index.schema.jsonのパス (デフォルト: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--registry",
        default=None,
        help=(
            "Public ID Registry YAMLのパス (任意)。既存の"
            "(publicStoryId, episodeOrder)割当があれば提案に再利用する"
        ),
    )
    parser.add_argument(
        "--registry-schema",
        default=str(DEFAULT_REGISTRY_SCHEMA_PATH),
        help=(
            "public_id_registry.schema.jsonのパス "
            f"(デフォルト: {DEFAULT_REGISTRY_SCHEMA_PATH})"
        ),
    )
    parser.add_argument(
        "--report",
        required=True,
        help="check結果をMarkdownで書き出すファイルパス (workspace配下のみ)",
    )
    parser.add_argument(
        "--suggestions-output",
        required=True,
        help=(
            "publicEpisodeId割当候補をYAMLで書き出すファイルパス "
            "(workspace配下のみ。publicStoryId/publicEpisodeId候補のみを含む)"
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "同一episodeに複数の異なるpublicEpisodeIdが混在するconflictを"
            "blocking errorにする (既定では警告のみでexit codeに影響しない)"
        ),
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


def _is_under_forbidden_dir(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    for forbidden in _FORBIDDEN_OUTPUT_DIRS:
        try:
            resolved.relative_to(forbidden)
            return True
        except ValueError:
            continue
    return False


# ----------------------------------------------------------------
# Registry loading
# ----------------------------------------------------------------


def _load_registry(
    path: Path, schema: dict[str, Any]
) -> tuple[dict[tuple[str, int], str] | None, list[str]]:
    """Public ID Registryを読み込み、(publicStoryId, episodeOrder) ->
    publicEpisodeId のlookupを組み立てる。

    戻り値: (lookup (schema検証失敗時はNone), エラーメッセージ一覧)。
    """
    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        return None, [f"{path}: 読み込み失敗: {e}"]

    errors = sorted(
        Draft7Validator(schema).iter_errors(raw), key=lambda e: list(e.path)
    )
    if errors:
        return None, [f"{path}: {list(e.path)}: {e.message}" for e in errors]

    lookup: dict[tuple[str, int], str] = {}
    for story in raw.get("stories", []) or []:
        public_story_id = story.get("publicStoryId")
        if not public_story_id:
            continue
        for episode in story.get("episodes", []) or []:
            order = episode.get("episodeOrder")
            public_episode_id = episode.get("publicEpisodeId")
            if order and public_episode_id:
                lookup[(public_story_id, order)] = public_episode_id
    return lookup, []


# ----------------------------------------------------------------
# Analysis: group entries by internal storyId (never exposed in output),
# detect missing/conflicting publicEpisodeId per internal episodeId
# ----------------------------------------------------------------


def _group_entries_by_internal_story(
    raw_documents: list[tuple[Path, dict[str, Any]]],
) -> tuple[list[str], dict[str, list[dict[str, Any]]]]:
    order: list[str] = []
    groups: dict[str, list[dict[str, Any]]] = {}
    for _, raw in raw_documents:
        for entry in raw.get("entries", []) or []:
            story_id = entry.get("storyId")
            if not story_id:
                continue
            if story_id not in groups:
                groups[story_id] = []
                order.append(story_id)
            groups[story_id].append(entry)
    return order, groups


def _analyze_story_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """1つの内部storyId分のentryから、publicStoryId候補・episode単位の
    割当状況を集計する。internal episodeIdの値自体は戻り値に含めない
    (呼び出し側でepisodeOrderのみを使う)。"""
    public_story_ids = {
        entry.get("publicStoryId") for entry in entries if entry.get("publicStoryId")
    }

    episode_order: dict[str, int] = {}
    episode_public_ids: dict[str, set[str]] = {}
    for entry in entries:
        episode_id = entry.get("episodeId")
        if not episode_id:
            continue
        if episode_id not in episode_order:
            episode_order[episode_id] = len(episode_order) + 1
        public_episode_id = entry.get("publicEpisodeId")
        if public_episode_id:
            episode_public_ids.setdefault(episode_id, set()).add(public_episode_id)

    assigned: dict[int, str] = {}
    missing_orders: list[int] = []
    conflict_orders: list[int] = []
    for episode_id, order in episode_order.items():
        values = episode_public_ids.get(episode_id, set())
        if len(values) == 1:
            assigned[order] = next(iter(values))
        elif len(values) > 1:
            conflict_orders.append(order)
        else:
            missing_orders.append(order)

    return {
        "publicStoryIdCandidates": public_story_ids,
        "episodeCount": len(episode_order),
        "assigned": assigned,
        "missingOrders": sorted(missing_orders),
        "conflictOrders": sorted(conflict_orders),
    }


def _build_story_records(
    raw_documents: list[tuple[Path, dict[str, Any]]],
) -> list[dict[str, Any]]:
    order, groups = _group_entries_by_internal_story(raw_documents)
    records: list[dict[str, Any]] = []
    unidentified_counter = 0

    for story_id in order:
        analysis = _analyze_story_entries(groups[story_id])
        candidates = analysis["publicStoryIdCandidates"]
        issues: list[str] = []
        warnings: list[str] = []

        if len(candidates) == 0:
            unidentified_counter += 1
            label = f"unidentified-story-group-{unidentified_counter}"
            public_story_id = None
            issues.append(
                f"{label}: publicStoryIdを持つentryがありません "
                "(publicEpisodeId候補を提案できません)"
            )
        elif len(candidates) > 1:
            unidentified_counter += 1
            label = f"unidentified-story-group-{unidentified_counter}"
            public_story_id = None
            issues.append(
                f"{label}: 複数の異なるpublicStoryIdが同一story内に混在して"
                "います (publicEpisodeId候補を提案できません、要review)"
            )
        else:
            public_story_id = next(iter(candidates))
            label = f"publicStoryId={public_story_id}"

        for order in analysis["missingOrders"]:
            issues.append(
                f"{label}: episodeOrder {order} のpublicEpisodeIdが欠落しています"
            )

        if analysis["conflictOrders"]:
            warnings.append(
                f"{label}: episodeOrder {analysis['conflictOrders']} に複数の"
                "異なるpublicEpisodeIdが混在しています (要review)"
            )

        records.append(
            {
                "label": label,
                "publicStoryId": public_story_id,
                "episodeCount": analysis["episodeCount"],
                "assigned": analysis["assigned"],
                "missingOrders": analysis["missingOrders"],
                "conflictOrders": analysis["conflictOrders"],
                "issues": issues,
                "warnings": warnings,
            }
        )
    return records


def _check_duplicate_public_episode_ids(
    records: list[dict[str, Any]],
) -> tuple[int, list[str]]:
    seen: dict[str, int] = {}
    for record in records:
        for value in record["assigned"].values():
            seen[value] = seen.get(value, 0) + 1
    duplicates = sorted(value for value, count in seen.items() if count > 1)
    issues = [f"publicEpisodeId '{value}' が重複しています" for value in duplicates]
    return len(duplicates), issues


def _build_suggestions(
    records: list[dict[str, Any]],
    registry_lookup: dict[tuple[str, int], str] | None,
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for record in records:
        public_story_id = record["publicStoryId"]
        if not public_story_id:
            continue
        for order in record["missingOrders"]:
            registry_value = (registry_lookup or {}).get((public_story_id, order))
            if registry_value:
                suggested = registry_value
                reason = (
                    "Matches existing Public ID Registry entry for this "
                    "publicStoryId/episodeOrder."
                )
            else:
                suggested = f"{public_story_id}_E{order:02d}"
                reason = "Next sequential episode order inferred from candidate order."
            suggestions.append(
                {
                    "publicStoryId": public_story_id,
                    "missingEpisodeOrder": order,
                    "suggestedPublicEpisodeId": suggested,
                    "reason": reason,
                    "reviewRequired": True,
                }
            )
    return suggestions


# ----------------------------------------------------------------
# Report building
# ----------------------------------------------------------------


def _story_summary_lines(records: list[dict[str, Any]]) -> list[str]:
    lines = ["## Stories", ""]
    if not records:
        lines.append("- (none)")
        lines.append("")
        return lines
    for record in records:
        line = (
            f"- {record['label']}: {record['episodeCount']} episodes, "
            f"{len(record['assigned'])} assigned, "
            f"{len(record['missingOrders'])} missing"
        )
        if record["conflictOrders"]:
            line += f", {len(record['conflictOrders'])} conflicts"
        lines.append(line)
    lines.append("")
    return lines


def _suggestions_lines(suggestions: list[dict[str, Any]]) -> list[str]:
    lines = ["## Suggestions", ""]
    if not suggestions:
        lines.append("- (none)")
        lines.append("")
        return lines
    for suggestion in suggestions:
        lines.append(
            f"- publicStoryId={suggestion['publicStoryId']}, "
            f"missingEpisodeOrder={suggestion['missingEpisodeOrder']}: "
            f"suggested {suggestion['suggestedPublicEpisodeId']} "
            f"({suggestion['reason']})"
        )
    lines.append("")
    return lines


def _issues_lines(heading: str, issues: list[str]) -> list[str]:
    lines = [heading, ""]
    if issues:
        for issue in issues:
            lines.append(f"- {issue}")
    else:
        lines.append("- (none)")
    lines.append("")
    return lines


def _build_report_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        "# Public Episode ID Assignment Check Report",
        "",
        f"- Input: {report['input']}",
        f"- Registry: {report['registry'] or '(none)'}",
        f"- File count: {report['fileCount']}",
        f"- Story count: {report['storyCount']}",
        f"- Missing publicStoryId count: {report['missingPublicStoryIdCount']}",
        f"- Total episode count: {report['totalEpisodeCount']}",
        f"- Assigned publicEpisodeId count: {report['assignedCount']}",
        f"- Missing publicEpisodeId count: {report['missingCount']}",
        f"- Conflict count: {report['conflictCount']}",
        f"- Duplicate publicEpisodeId count: {report['duplicateCount']}",
        "",
    ]
    lines.extend(_story_summary_lines(report["records"]))
    lines.extend(_suggestions_lines(report["suggestions"]))
    lines.extend(_issues_lines("## Issues", report["issues"]))
    lines.extend(_issues_lines("## Warnings", report["warnings"]))

    lines.append("## Final Decision")
    lines.append("")
    lines.append(f"- {'PASS' if report['passed'] else 'FAIL'}")
    lines.append("")

    lines.append("## Note")
    lines.append("")
    lines.append(
        "- Suggestions are candidates only. A human must review and confirm "
        "each publicEpisodeId before writing it into story_manifest.yaml or "
        "a Public ID Registry (docs/architecture/06_AI/Public_ID_Registry_Design.md)."
    )
    lines.append(
        "- This report and the suggestions output must never contain "
        "sourceKey-derived internal IDs (storyId/episodeId/evidenceId), raw "
        "titles, or raw paths; only publicStoryId/publicEpisodeId candidates "
        "and episodeOrder integers are recorded."
    )
    lines.append("- Once a publicEpisodeId has been published, it must not be changed.")
    lines.append("")
    return lines


def _print_summary(report: dict[str, Any], *, quiet: bool) -> None:
    if quiet:
        return
    print(
        f"[public-episode-id-check] {report['fileCount']} ファイル、"
        f"{report['storyCount']} stories、{report['totalEpisodeCount']} episodes"
    )
    print(
        f"[public-episode-id-check] assigned={report['assignedCount']} "
        f"missing={report['missingCount']} "
        f"suggestions={len(report['suggestions'])}"
    )
    if report["issues"]:
        print(f"[エラー] {len(report['issues'])}件のissueがあります:", file=sys.stderr)
        for issue in report["issues"]:
            print(f"  - {issue}", file=sys.stderr)
    for warning in report["warnings"]:
        print(f"[警告] {warning}")
    print(f"[public-episode-id-check] 結果: {'PASS' if report['passed'] else 'FAIL'}")


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------


def _resolve_registry_lookup(
    args: argparse.Namespace,
) -> tuple[dict[tuple[str, int], str] | None, int | None]:
    """`--registry`指定時にlookupを組み立てる。

    戻り値: (lookup, exit_code)。`--registry`未指定ならlookupはNone・
    exit_codeもNone。エラー時はlookupがNone・exit_codeが2 (エラーメッセージは
    このヘルパー内で出力済み)。
    """
    if not args.registry:
        return None, None

    registry_path = Path(args.registry)
    if not registry_path.exists():
        print(
            f"[エラー] --registryパスが見つかりません: {registry_path}", file=sys.stderr
        )
        return None, 2

    registry_schema_path = Path(args.registry_schema)
    if not registry_schema_path.exists():
        print(
            f"[エラー] --registry-schemaファイルが見つかりません: "
            f"{registry_schema_path}",
            file=sys.stderr,
        )
        return None, 2

    with open(registry_schema_path, encoding="utf-8") as f:
        registry_schema = json.load(f)
    registry_lookup, registry_errors = _load_registry(registry_path, registry_schema)
    if registry_errors:
        print("[エラー] Registryの読み込みに失敗しました:", file=sys.stderr)
        for issue in registry_errors:
            print(f"  - {issue}", file=sys.stderr)
        return None, 2

    return registry_lookup, None


def main() -> int:
    args = parse_args()

    schema_path = Path(args.schema)
    if not schema_path.exists():
        print(
            f"[エラー] schemaファイルが見つかりません: {schema_path}", file=sys.stderr
        )
        return 2
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    input_path = Path(args.input)
    yaml_paths = _collect_yaml_paths(input_path)
    if yaml_paths is None:
        print(f"[エラー] --inputパスが見つかりません: {input_path}", file=sys.stderr)
        return 2

    report_path = Path(args.report)
    suggestions_output_path = Path(args.suggestions_output)
    for label, path in (
        ("--report", report_path),
        ("--suggestions-output", suggestions_output_path),
    ):
        if _is_under_forbidden_dir(path):
            print(
                f"[エラー] {label}にknowledge/evidence・knowledge/public_ids配下の"
                f"pathは指定できません: {path}",
                file=sys.stderr,
            )
            return 2

    raw_documents, schema_errors = _load_yaml_documents(yaml_paths, schema)
    if schema_errors:
        print("[エラー] 入力のschema検証に失敗しました:", file=sys.stderr)
        for issue in schema_errors:
            print(f"  - {issue}", file=sys.stderr)
        return 2

    registry_lookup, registry_error_code = _resolve_registry_lookup(args)
    if registry_error_code is not None:
        return registry_error_code

    records = _build_story_records(raw_documents)
    duplicate_count, duplicate_issues = _check_duplicate_public_episode_ids(records)
    suggestions = _build_suggestions(records, registry_lookup)

    blocking_issues: list[str] = list(duplicate_issues)
    warnings: list[str] = []
    for record in records:
        blocking_issues.extend(record["issues"])
        if args.strict:
            blocking_issues.extend(record["warnings"])
        else:
            warnings.extend(record["warnings"])

    total_episode_count = sum(record["episodeCount"] for record in records)
    assigned_count = sum(len(record["assigned"]) for record in records)
    missing_count = sum(len(record["missingOrders"]) for record in records)
    conflict_count = sum(len(record["conflictOrders"]) for record in records)
    missing_public_story_id_count = sum(
        1 for record in records if record["publicStoryId"] is None
    )

    report = {
        "input": str(input_path),
        "registry": str(args.registry) if args.registry else None,
        "fileCount": len(raw_documents),
        "storyCount": len(records),
        "missingPublicStoryIdCount": missing_public_story_id_count,
        "totalEpisodeCount": total_episode_count,
        "assignedCount": assigned_count,
        "missingCount": missing_count,
        "conflictCount": conflict_count,
        "duplicateCount": duplicate_count,
        "records": records,
        "suggestions": suggestions,
        "issues": blocking_issues,
        "warnings": warnings,
        "passed": not blocking_issues,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(_build_report_lines(report)), encoding="utf-8")

    suggestions_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(suggestions_output_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"suggestions": suggestions}, f, allow_unicode=True, sort_keys=False
        )

    _print_summary(report, quiet=args.quiet)

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
