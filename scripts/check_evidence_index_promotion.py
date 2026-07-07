#!/usr/bin/env python3
"""
Check Evidence Index Promotion
`workspace/evidence_index_dry_runs/.../stories`（Public Evidence Index候補）が
`knowledge/evidence/stories/`へ昇格可能かをcheckするgatekeeper script。

`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`のpromotion
criteria/exclusion criteriaを機械的にcheckする。**実際のcopy・commitは
行わない**（check-onlyのscript、`feature/evidence-index-promotion-policy-
implementation`）。

チェック内容:
- schema検証（`schemas/evidence_index.schema.json`）
- `agents.wiki_generator.evidence_index.validate_evidence_index_collection`
  （duplicate evidenceId・enum・`visibility.rawTextIncluded`/`public`・
  構造化フィールド中のraw text禁止文字列）
- Evidence Index YAMLファイル全文に対するraw/source text禁止文字列scan
  （`FORBIDDEN_TEXT_PATTERNS`を再利用、構造化フィールドだけでなく
  ファイル全体をscanする点がvalidate_evidence_index_collectionとの違い）
- entry type policy（`--policy public-default`、既定値かつ現状唯一の
  policy。`dialogue`/`monologue`/`narration`/`choice`/`unknown`のみ許可、
  `stage_direction`/`scene`/`episode`/`story`/`speaker_label`は
  promotion対象外としてblocking error）
- `--story-summaries`指定時のみ、reviewed/approvedかつgeneratedな
  Story/Episode Summaryの`evidenceRefs`が対象Evidence Indexに存在するかを
  確認する（missingはwarning、blockingにはしない。理由は
  Evidence_Index_Promotion_Policy.md §10参照）

Usage:
    uv run python scripts/check_evidence_index_promotion.py \\
        --input workspace/evidence_index_dry_runs/<run>/default/stories

    uv run python scripts/check_evidence_index_promotion.py \\
        --input workspace/evidence_index_dry_runs/<run>/default/stories \\
        --story-summaries knowledge/summaries/stories \\
        --report workspace/evidence_index_dry_runs/<run>/promotion_check_report.md

Exit codes:
    0: promotion check passed（blocking issueなし。warningがあっても0）
    1: promotion check failed（blocking issueあり）
    2: 入力パスが見つからない、またはIOエラー
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.wiki_generator.evidence_index import (  # noqa: E402
    FORBIDDEN_TEXT_PATTERNS,
    EvidenceIndexCollection,
    EvidenceIndexEntry,
    parse_evidence_index_document,
    validate_evidence_index_collection,
)
from agents.wiki_generator.story_summaries import (  # noqa: E402
    StorySummaryCollection,
    is_document_displayable,
    load_story_summaries,
)

DEFAULT_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "evidence_index.schema.json"

# Evidence_Index_Promotion_Policy.md §4.1の初期公開対象entry type。
POLICY_PUBLIC_DEFAULT = "public-default"

PUBLIC_DEFAULT_ALLOWED_TYPES: frozenset[str] = frozenset(
    {"dialogue", "monologue", "narration", "choice", "unknown"}
)

# Evidence_Index_Promotion_Policy.md §4.2の除外・保留entry type。
# stage_directionは§3の通り単独で明示的に言及する。
PROMOTION_EXCLUDED_TYPES: frozenset[str] = frozenset(
    {"stage_direction", "scene", "episode", "story", "speaker_label"}
)

POLICIES: dict[str, frozenset[str]] = {
    POLICY_PUBLIC_DEFAULT: PUBLIC_DEFAULT_ALLOWED_TYPES,
}


# ----------------------------------------------------------------
# Argument parser
# ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evidence Index候補 (workspace/evidence_index_dry_runs/配下等) が"
            "knowledge/evidence/stories/へ昇格可能かをcheckする"
            "(check-only、実際のcopy/commitは行わない)"
        ),
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Evidence Index YAMLファイル、またはdirectory (直下の*.yaml/*.ymlを収集)",
    )
    parser.add_argument(
        "--story-summaries",
        default=None,
        help=(
            "Story Summary YAMLファイル、またはdirectory (任意)。指定した場合、"
            "reviewed/approvedかつgeneratedなsummaryのevidenceRefsが"
            "Evidence Indexに存在するかを確認する (missingはwarning)"
        ),
    )
    parser.add_argument(
        "--policy",
        choices=sorted(POLICIES),
        default=POLICY_PUBLIC_DEFAULT,
        help=(
            "promotion policy (デフォルト: public-default。"
            "dialogue/monologue/narration/choice/unknownのみ許可)"
        ),
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help=f"evidence_index.schema.jsonのパス (デフォルト: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--report",
        default=None,
        help=(
            "check結果をMarkdownで書き出すファイルパス (任意。workspace配下を"
            "指定すること、commit対象にしない)"
        ),
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


# ----------------------------------------------------------------
# Input collection / schema validation
# ----------------------------------------------------------------


def _collect_yaml_paths(input_path: Path) -> list[Path] | None:
    """--inputがファイルならそれ単体、directoryなら直下の*.yaml/*.ymlを返す
    (`scripts/validate_evidence_index.py`と同じ方針)。"""
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.glob("*.yaml")) + sorted(input_path.glob("*.yml"))
    return None


def _load_yaml_documents(
    yaml_paths: list[Path], schema: dict[str, Any]
) -> tuple[list[tuple[Path, dict[str, Any]]], list[str]]:
    """全ファイルをYAML読み込み+schema検証する。

    戻り値: (成功した(path, raw_dict)一覧, エラーメッセージ一覧)。
    """
    import yaml

    schema_errors: list[str] = []
    raw_documents: list[tuple[Path, dict[str, Any]]] = []
    for path in yaml_paths:
        try:
            with open(path, encoding="utf-8") as f:
                raw_data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            schema_errors.append(f"{path}: 読み込み失敗: {e}")
            continue
        errors = sorted(
            Draft7Validator(schema).iter_errors(raw_data), key=lambda e: list(e.path)
        )
        if errors:
            schema_errors.extend(f"{path}: {list(e.path)}: {e.message}" for e in errors)
        else:
            raw_documents.append((path, raw_data))
    return raw_documents, schema_errors


# ----------------------------------------------------------------
# Source text exposure check (ファイル全文scan)
# ----------------------------------------------------------------


def _scan_file_for_forbidden_text(path: Path) -> list[str]:
    """Evidence Index YAMLファイル全文に対して、raw/source text禁止文字列
    (`.dec`/raw command/`$num`/local path等) をscanする。

    構造化フィールド単位のチェック (`validate_evidence_index_collection`) は
    `notes`/`speaker.displayName`等の限られたフィールドのみを対象とするため、
    ここではファイル全文を対象にすることで取りこぼしを防ぐ
    (`docs/runbooks/Evidence_Index_Generation_Dry_Run.md` §8の
    source text exposure checkと同じ検索対象文字列を再利用する)。
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{path}: 読み込み失敗: {e}"]
    issues: list[str] = []
    for pattern in FORBIDDEN_TEXT_PATTERNS:
        if pattern in text:
            issues.append(f"{path}: 禁止文字列 '{pattern}' を検出しました")
    return issues


# ----------------------------------------------------------------
# Entry type policy check
# ----------------------------------------------------------------


def _check_entry_type_policy(
    entries: list[EvidenceIndexEntry], allowed_types: frozenset[str]
) -> tuple[dict[str, int], list[str]]:
    """entryのevidenceTypeがpolicyの許可typeに収まっているかを確認する。

    戻り値: (evidenceType別entry数, policy違反の説明一覧)。
    """
    counts_by_type: dict[str, int] = {}
    violations: list[str] = []
    for entry in entries:
        counts_by_type[entry.evidence_type] = (
            counts_by_type.get(entry.evidence_type, 0) + 1
        )
        if entry.evidence_type in allowed_types:
            continue
        if entry.evidence_type == "stage_direction":
            violations.append(
                f"evidenceId={entry.evidence_id!r}: stage_directionはPublic "
                "promotion対象外です (Evidence_Index_Promotion_Policy.md §3)"
            )
        else:
            violations.append(
                f"evidenceId={entry.evidence_id!r}: evidenceType "
                f"'{entry.evidence_type}' はpromotion対象外です "
                "(Evidence_Index_Promotion_Policy.md §4.2)"
            )
    return counts_by_type, violations


# ----------------------------------------------------------------
# Summary evidenceRefs consistency check (--story-summaries指定時のみ)
# ----------------------------------------------------------------


def _collect_summary_evidence_refs(
    collection: StorySummaryCollection,
) -> list[tuple[str, str]]:
    """reviewed/approvedかつgeneratedなsummaryのevidenceRefsを集める。

    戻り値: [(storyId, evidenceRef), ...]（unreviewed/rejected/deprecated
    等は対象外、Evidence_Index_Promotion_Policy.md §10）。
    """
    refs: list[tuple[str, str]] = []
    for document in collection.documents:
        if not is_document_displayable(document):
            continue
        if document.story_summary is not None:
            refs.extend(
                (document.story_id, ref) for ref in document.story_summary.evidence_refs
            )
        for episode_summary in document.episode_summaries:
            refs.extend(
                (document.story_id, ref) for ref in episode_summary.evidence_refs
            )
    return refs


def _check_summary_evidence_refs(
    story_summaries_path: str, evidence_ids: frozenset[str]
) -> dict[str, Any]:
    collection = load_story_summaries(story_summaries_path)
    all_refs = _collect_summary_evidence_refs(collection)
    missing = [
        {"storyId": story_id, "evidenceId": ref}
        for story_id, ref in all_refs
        if ref not in evidence_ids
    ]
    return {
        "checkedDocumentCount": len(collection.documents),
        "checkedRefCount": len(all_refs),
        "missingRefCount": len(missing),
        "missingRefs": missing,
    }


# ----------------------------------------------------------------
# Report building
# ----------------------------------------------------------------


def _append_result_section(
    lines: list[str], heading: str, issues: list[str], *, issues_label: str = "Issues"
) -> None:
    if heading:
        lines.append(heading)
        lines.append("")
    lines.append(f"- Result: {'PASS' if not issues else 'FAIL'}")
    if issues:
        lines.append(f"- {issues_label}:")
        for issue in issues:
            lines.append(f"  - {issue}")
    lines.append("")


def _append_summary_evidence_refs_section(
    lines: list[str], summary_check: dict[str, Any] | None
) -> None:
    if summary_check is None:
        return
    lines.append("## Summary evidenceRefs Consistency")
    lines.append("")
    lines.append(f"- Checked documents: {summary_check['checkedDocumentCount']}")
    lines.append(f"- Checked evidenceRefs: {summary_check['checkedRefCount']}")
    lines.append(f"- Missing evidenceRefs: {summary_check['missingRefCount']}")
    if summary_check["missingRefs"]:
        lines.append("- Details (review recommended, may be stage_direction etc.):")
        for missing in summary_check["missingRefs"]:
            lines.append(
                f"  - storyId={missing['storyId']!r} "
                f"evidenceId={missing['evidenceId']!r}"
            )
    lines.append("")


def _build_report_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        "# Evidence Index Promotion Check Report",
        "",
        f"- Input: {report['input']}",
        f"- Policy: {report['policy']}",
        f"- File count: {report['fileCount']}",
        f"- Story count: {report['storyCount']}",
        f"- Episode count: {report['episodeCount']}",
        f"- Entry count: {report['entryCount']}",
        "",
        "## Entries by evidenceType",
        "",
    ]
    if report["entriesByEvidenceType"]:
        for evidence_type, count in sorted(report["entriesByEvidenceType"].items()):
            lines.append(f"- {evidence_type}: {count}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Public Type Policy")
    lines.append("")
    lines.append(f"- Allowed types: {', '.join(sorted(POLICIES[report['policy']]))}")
    _append_result_section(
        lines, "", report["typePolicyViolations"], issues_label="Violations"
    )
    _append_result_section(
        lines, "## Schema / Structural Validation", report["schemaAndStructuralIssues"]
    )
    _append_result_section(
        lines, "## Source Text Exposure Check", report["sourceTextIssues"]
    )
    _append_summary_evidence_refs_section(lines, report["summaryEvidenceRefs"])

    lines.append("## Warnings")
    lines.append("")
    if report["warnings"]:
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Final Decision")
    lines.append("")
    lines.append(f"- {'PASS' if report['passed'] else 'FAIL'}")
    lines.append("")
    return lines


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------


def _build_report(
    *,
    input_path: Path,
    yaml_paths: list[Path],
    policy: str,
    story_summaries: str | None,
    schema: dict[str, Any],
) -> dict[str, Any]:
    raw_documents, schema_errors = _load_yaml_documents(yaml_paths, schema)

    source_text_issues: list[str] = []
    for path in yaml_paths:
        source_text_issues.extend(_scan_file_for_forbidden_text(path))

    collection = EvidenceIndexCollection(
        documents=[parse_evidence_index_document(raw) for _, raw in raw_documents]
    )
    structural_issues = validate_evidence_index_collection(collection)
    schema_and_structural_issues = schema_errors + structural_issues

    all_entries = [
        entry for document in collection.documents for entry in document.entries
    ]
    entries_by_type, type_policy_violations = _check_entry_type_policy(
        all_entries, POLICIES[policy]
    )

    story_ids = {entry.story_id for entry in all_entries if entry.story_id}
    episode_ids = {entry.episode_id for entry in all_entries if entry.episode_id}

    warnings: list[str] = []
    summary_check: dict[str, Any] | None = None
    if story_summaries:
        evidence_ids = frozenset(
            entry.evidence_id for entry in all_entries if entry.evidence_id
        )
        summary_check = _check_summary_evidence_refs(story_summaries, evidence_ids)
        if summary_check["missingRefCount"]:
            warnings.append(
                f"{summary_check['missingRefCount']}件のSummary evidenceRefsが"
                "このEvidence Indexに存在しません "
                "(stage_direction等の除外typeを参照している可能性、"
                "またはSummaryが先行している可能性があります。要review)"
            )

    passed = not (
        schema_and_structural_issues or source_text_issues or type_policy_violations
    )

    return {
        "input": str(input_path),
        "policy": policy,
        "fileCount": len(yaml_paths),
        "storyCount": len(story_ids),
        "episodeCount": len(episode_ids),
        "entryCount": len(all_entries),
        "entriesByEvidenceType": entries_by_type,
        "typePolicyViolations": type_policy_violations,
        "schemaAndStructuralIssues": schema_and_structural_issues,
        "sourceTextIssues": source_text_issues,
        "summaryEvidenceRefs": summary_check,
        "warnings": warnings,
        "passed": passed,
    }


def _print_issue_block(label: str, issues: list[str]) -> None:
    if not issues:
        return
    print(f"[エラー] {label}: {len(issues)}件", file=sys.stderr)
    for issue in issues:
        print(f"  - {issue}", file=sys.stderr)


def _print_report(report: dict[str, Any], *, quiet: bool) -> None:
    if quiet:
        return
    print(
        f"[promotion-check] {report['fileCount']} ファイル、"
        f"{report['entryCount']} entries "
        f"(policy={report['policy']})"
    )
    _print_issue_block("entry type policy違反", report["typePolicyViolations"])
    _print_issue_block(
        "schema/整合性検証に失敗しました", report["schemaAndStructuralIssues"]
    )
    _print_issue_block("source text exposure check失敗", report["sourceTextIssues"])
    for warning in report["warnings"]:
        print(f"[警告] {warning}")
    print(f"[promotion-check] 結果: {'PASS' if report['passed'] else 'FAIL'}")


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

    report = _build_report(
        input_path=input_path,
        yaml_paths=yaml_paths,
        policy=args.policy,
        story_summaries=args.story_summaries,
        schema=schema,
    )

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(_build_report_lines(report)), encoding="utf-8")

    _print_report(report, quiet=args.quiet)

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
