#!/usr/bin/env python3
"""
Promote Evidence Index
promotion checkをPASSしたPublic Evidence Index候補を`knowledge/evidence/
stories/`へ安全にcopyするscript。

`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`のpromotion
criteriaと`docs/templates/evidence_index_promotion_review_template.md`の
human review記録を前提に、実際のfile copyを行う
（`feature/evidence-index-promotion-copy-script`）。

**重要な安全方針**（`docs/runbooks/Evidence_Index_Promotion_Copy.md`参照）:
- **デフォルトはdry-run。`--execute`を指定しない限り一切ファイルを書き込まない**
- `--execute`時も、以下がすべて満たされない限りcopyしない（blocking）:
  - `check_evidence_index_promotion.py`相当のpromotion checkがPASS
  - `--review-note`が存在し、Decision セクションで
    `- [x] Approved for promotion` がcheckされている
    （`Needs revision`/`Rejected`がcheckされている、または未決定の場合はblocking）
  - review note自体にraw/source text禁止文字列が含まれていない
  - 1ファイル1story方針が守られている（entries内のstoryIdが単一）
  - copy先に既存ファイルがある場合は`--overwrite`が指定されている
- copy自体は入力ファイルのbyte-for-byte copy（`shutil.copy2`）で行い、
  内容の再生成・変換は行わない
- `--execute`成功後は、copy先に対してもschema+整合性検証を再実行する
  （sanity re-check）
- `--target`は既定で`knowledge/evidence/stories`のみを許可する。
  tests等で一時ディレクトリを使う場合は`--allow-nonstandard-target`を
  明示指定すること

Usage:
    # dry-run (既定、何もcopyしない)
    uv run python scripts/promote_evidence_index.py \\
        --input workspace/evidence_index_dry_runs/<run>/default/stories \\
        --review-note workspace/evidence_index_dry_runs/<run>/review_note.md \\
        --target knowledge/evidence/stories \\
        --report workspace/evidence_index_dry_runs/<run>/promote_report.md

    # 実copy (明示的に--executeが必要)
    uv run python scripts/promote_evidence_index.py \\
        --input workspace/evidence_index_dry_runs/<run>/default/stories \\
        --review-note workspace/evidence_index_dry_runs/<run>/review_note.md \\
        --target knowledge/evidence/stories \\
        --report workspace/evidence_index_dry_runs/<run>/promote_report.md \\
        --execute

Exit codes:
    0: dry-run成功、またはexecute成功（copy対象0件を含む）
    1: promotion check失敗、review note未承認、1ファイル1story違反、
       overwrite conflict（--overwrite未指定）等のblocking issueがある
    2: --input/--review-note/--schemaパスが見つからない、または
       --targetが非標準かつ--allow-nonstandard-target未指定
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_evidence_index_promotion import (  # noqa: E402
    DEFAULT_SCHEMA_PATH,
    POLICIES,
    POLICY_PUBLIC_DEFAULT,
    _build_report,
    _collect_yaml_paths,
    _load_yaml_documents,
)

from agents.wiki_generator.evidence_index import (  # noqa: E402
    FORBIDDEN_TEXT_PATTERNS,
    EvidenceIndexCollection,
    parse_evidence_index_document,
    validate_evidence_index_collection,
)

# promotion checkの本体ロジックを再利用する (check_evidence_index_promotion.py
# のCLIとentry type policy/raw text scan/schema検証を重複実装しない)。
_run_promotion_check = _build_report

DEFAULT_TARGET_DIR = _PROJECT_ROOT / "knowledge" / "evidence" / "stories"

APPROVED_PATTERN = re.compile(r"-\s*\[[xX]\]\s*Approved for promotion")
NEEDS_REVISION_PATTERN = re.compile(r"-\s*\[[xX]\]\s*Needs revision")
REJECTED_PATTERN = re.compile(r"-\s*\[[xX]\]\s*Rejected")


# ----------------------------------------------------------------
# Argument parser
# ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "promotion checkをPASSしたEvidence Index候補をknowledge/evidence/"
            "stories/へ安全にcopyする (既定はdry-run、実copyには--executeが必要)"
        ),
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Evidence Index YAMLファイル、またはdirectory (直下の*.yaml/*.ymlを収集)",
    )
    parser.add_argument(
        "--review-note",
        required=True,
        help=(
            "docs/templates/evidence_index_promotion_review_template.md由来の"
            "human review記録ファイル (必須、Decisionで'Approved for promotion'が"
            "checkされている必要がある)"
        ),
    )
    parser.add_argument(
        "--target",
        required=True,
        help=(
            "copy先directory (既定ではknowledge/evidence/storiesのみ許可。"
            "他のpathを使う場合は--allow-nonstandard-targetを指定すること)"
        ),
    )
    parser.add_argument(
        "--report",
        default=None,
        help="check結果をMarkdownで書き出すファイルパス (任意。workspace配下を推奨)",
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help=f"evidence_index.schema.jsonのパス (デフォルト: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--story-summaries",
        default=None,
        help="promotion checkに渡すStory Summary YAMLファイル、またはdirectory (任意)",
    )
    parser.add_argument(
        "--policy",
        choices=sorted(POLICIES),
        default=POLICY_PUBLIC_DEFAULT,
        help="promotion checkに渡すpolicy (デフォルト: public-default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="実際にfileをcopyする (指定しない場合はdry-runのみ)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="copy先に既存ファイルがある場合、上書きを許可する (既定は禁止)",
    )
    parser.add_argument(
        "--allow-nonstandard-target",
        action="store_true",
        help="knowledge/evidence/stories以外のtargetを許可する (tests用)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


def _is_standard_target(target_dir: Path) -> bool:
    try:
        return target_dir.resolve() == DEFAULT_TARGET_DIR.resolve()
    except OSError:
        return False


# ----------------------------------------------------------------
# Review note check (承認状態 + source text exposure)
# ----------------------------------------------------------------


CHECKLIST_ITEM_PATTERN = re.compile(r"^\s*-\s*\[[ xX]\]")


def _scan_review_note_text_for_forbidden_patterns(text: str) -> list[str]:
    """review note本文をraw/source text禁止文字列scanする。

    `docs/templates/evidence_index_promotion_review_template.md`の
    「## Source Text Exposure」チェックリスト自体が`no `.dec`` `のように
    禁止文字列パターンをラベルとして含むため、チェックリスト行
    （`- [ ] ...`/`- [x] ...`）はscan対象から除外する（テンプレート由来の
    定型文言を誤検知しないため）。それ以外の自由記述行（Target/Notes等）は
    全てscanする。
    """
    issues: list[str] = []
    for line in text.splitlines():
        if CHECKLIST_ITEM_PATTERN.match(line):
            continue
        for pattern in FORBIDDEN_TEXT_PATTERNS:
            if pattern in line:
                issues.append(f"禁止文字列 '{pattern}' を検出しました: {line.strip()}")
    return issues


def _check_review_note(review_note_path: Path) -> dict[str, Any]:
    """review noteのDecisionセクションの承認状態と、review note自体への
    raw/source text禁止文字列scanを行う。

    rejected/needs_revisionがcheckされている場合は、approvedが同時に
    checkされていても安全側でapproved扱いにしない。
    """
    text = review_note_path.read_text(encoding="utf-8")
    if REJECTED_PATTERN.search(text):
        decision = "rejected"
    elif NEEDS_REVISION_PATTERN.search(text):
        decision = "needs_revision"
    elif APPROVED_PATTERN.search(text):
        decision = "approved"
    else:
        decision = "undecided"

    source_text_issues = _scan_review_note_text_for_forbidden_patterns(text)
    return {
        "path": str(review_note_path),
        "decision": decision,
        "approved": decision == "approved",
        "sourceTextIssues": source_text_issues,
    }


# ----------------------------------------------------------------
# Copy planning (1 file 1 story方針、overwrite判定)
# ----------------------------------------------------------------


def _extract_story_id(raw_document: dict[str, Any]) -> tuple[str | None, str | None]:
    """documentのentries[].storyIdから、このfileのstoryIdを1つに決定する。

    戻り値: (storyId, エラーメッセージ)。entriesが空、またはstoryIdが
    複数混在する場合はstoryIdがNoneになり、エラーメッセージが入る
    (1ファイル1story方針、Evidence_Index_Design.md §7.5)。
    """
    story_ids = {
        entry.get("storyId")
        for entry in raw_document.get("entries", []) or []
        if entry.get("storyId")
    }
    if not story_ids:
        return None, "entries内にstoryIdを持つentryがありません"
    if len(story_ids) > 1:
        return None, f"1ファイル内に複数のstoryIdが混在しています: {sorted(story_ids)}"
    return next(iter(story_ids)), None


def _plan_copy_for_file(
    path: Path, raw_document: dict[str, Any], target_dir: Path, *, overwrite: bool
) -> dict[str, Any]:
    story_id, error = _extract_story_id(raw_document)
    if error:
        return {"source": str(path), "status": "skipped", "reason": error}

    target_path = target_dir / f"{story_id}.yaml"
    if target_path.exists() and not overwrite:
        return {
            "source": str(path),
            "target": str(target_path),
            "storyId": story_id,
            "status": "overwrite_conflict",
            "reason": "target already exists (--overwriteが必要)",
        }
    status = "overwrite" if target_path.exists() else "planned"
    return {
        "source": str(path),
        "target": str(target_path),
        "storyId": story_id,
        "status": status,
    }


# ----------------------------------------------------------------
# Post-copy validation (sanity re-check)
# ----------------------------------------------------------------


def _validate_copied_files(
    target_paths: list[Path], schema: dict[str, Any]
) -> list[str]:
    raw_documents, schema_errors = _load_yaml_documents(target_paths, schema)
    collection = EvidenceIndexCollection(
        documents=[parse_evidence_index_document(raw) for _, raw in raw_documents]
    )
    structural_issues = validate_evidence_index_collection(collection)
    return schema_errors + structural_issues


# ----------------------------------------------------------------
# Report building
# ----------------------------------------------------------------


def _promotion_check_lines(promotion_check: dict[str, Any]) -> list[str]:
    lines = [
        "## Promotion Check",
        "",
        f"- Result: {'PASS' if promotion_check['passed'] else 'FAIL'}",
        f"- Entry count: {promotion_check['entryCount']}",
    ]
    if promotion_check["entriesByEvidenceType"]:
        lines.append("- Entries by type:")
        for evidence_type, count in sorted(
            promotion_check["entriesByEvidenceType"].items()
        ):
            lines.append(f"  - {evidence_type}: {count}")
    for label, key in (
        ("Type policy violations", "typePolicyViolations"),
        ("Schema/structural issues", "schemaAndStructuralIssues"),
        ("Source text issues", "sourceTextIssues"),
    ):
        issues = promotion_check[key]
        if issues:
            lines.append(f"- {label}:")
            for issue in issues:
                lines.append(f"  - {issue}")
    lines.append("")
    return lines


def _review_note_lines(review_note_check: dict[str, Any]) -> list[str]:
    lines = [
        "## Review Note",
        "",
        f"- Path: {review_note_check['path']}",
        f"- Decision: {review_note_check['decision']}",
        f"- Approved: {'yes' if review_note_check['approved'] else 'no'}",
    ]
    if review_note_check["sourceTextIssues"]:
        lines.append("- Source text issues:")
        for issue in review_note_check["sourceTextIssues"]:
            lines.append(f"  - {issue}")
    lines.append("")
    return lines


def _copy_plan_lines(heading: str, plans: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {heading}", ""]
    if not plans:
        lines.append("- (none)")
    for plan in plans:
        if "target" in plan:
            reason = f" ({plan['reason']})" if plan.get("reason") else ""
            lines.append(f"- {plan['source']} -> {plan['target']}{reason}")
        else:
            lines.append(f"- {plan['source']}: {plan.get('reason', '')}")
    lines.append("")
    return lines


def _execute_section_lines(report: dict[str, Any]) -> list[str]:
    if report["mode"] != "execute":
        return []
    lines = ["## Copied files", ""]
    if report["copiedFiles"]:
        for path in report["copiedFiles"]:
            lines.append(f"- {path}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Post-copy validation")
    lines.append("")
    if report["postCopyValidationIssues"]:
        lines.append("- Result: FAIL")
        for issue in report["postCopyValidationIssues"]:
            lines.append(f"  - {issue}")
    else:
        lines.append("- Result: PASS")
    lines.append("")
    return lines


def _build_promote_report_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        "# Evidence Index Promotion Copy Report",
        "",
        f"- Mode: {report['mode']}",
        f"- Input: {report['input']}",
        f"- Target: {report['target']}",
        f"- Review note: {report['reviewNote']}",
        f"- Source file count: {report['sourceFileCount']}",
        "",
    ]
    lines.extend(_promotion_check_lines(report["promotionCheck"]))
    lines.extend(_review_note_lines(report["reviewNoteCheck"]))
    lines.extend(_copy_plan_lines("Planned copies", report["plannedCopies"]))
    lines.extend(_copy_plan_lines("Skipped files", report["skippedFiles"]))
    lines.extend(_copy_plan_lines("Overwrite conflicts", report["overwriteConflicts"]))
    lines.extend(_execute_section_lines(report))

    lines.append("## Final Decision")
    lines.append("")
    if report["passed"]:
        decision_label = (
            "EXECUTE PASS" if report["mode"] == "execute" else "DRY RUN PASS"
        )
    else:
        decision_label = "FAILED"
    lines.append(f"- {decision_label}")
    lines.append("")
    return lines


def _build_promote_report(
    *,
    mode: str,
    input_path: Path,
    target_dir: Path,
    review_note_path: Path,
    source_file_count: int,
    promotion_check: dict[str, Any],
    review_note_check: dict[str, Any],
    plans: list[dict[str, Any]],
    copied_files: list[str],
    post_copy_validation: list[str] | None,
) -> dict[str, Any]:
    planned = [p for p in plans if p["status"] in ("planned", "overwrite")]
    skipped = [p for p in plans if p["status"] == "skipped"]
    conflicts = [p for p in plans if p["status"] == "overwrite_conflict"]

    blocking = (
        not promotion_check["passed"]
        or not review_note_check["approved"]
        or bool(review_note_check["sourceTextIssues"])
        or bool(skipped)
        or bool(conflicts)
    )
    passed = not blocking
    if mode == "execute" and post_copy_validation:
        passed = False

    return {
        "mode": mode,
        "input": str(input_path),
        "target": str(target_dir),
        "reviewNote": str(review_note_path),
        "sourceFileCount": source_file_count,
        "promotionCheck": promotion_check,
        "reviewNoteCheck": review_note_check,
        "plannedCopies": planned,
        "skippedFiles": skipped,
        "overwriteConflicts": conflicts,
        "copiedFiles": copied_files,
        "postCopyValidationIssues": post_copy_validation,
        "passed": passed,
    }


def _print_copy_result(report: dict[str, Any]) -> None:
    if report["mode"] == "dry-run":
        print("DRY RUN: no files were copied.")
        if report["plannedCopies"]:
            print("Would copy:")
            for plan in report["plannedCopies"]:
                print(f"- {plan['source']} -> {plan['target']}")
        else:
            print("Would copy: (none)")
        return
    if report["copiedFiles"]:
        print(f"Copied {len(report['copiedFiles'])} file(s):")
        for path in report["copiedFiles"]:
            print(f"- {path}")
    else:
        print("No files were copied (blocking issues found, or nothing to copy).")


def _print_blocking_issues(report: dict[str, Any]) -> None:
    if report["skippedFiles"]:
        print(f"[警告] skipped {len(report['skippedFiles'])}件:", file=sys.stderr)
        for plan in report["skippedFiles"]:
            print(f"  - {plan['source']}: {plan.get('reason')}", file=sys.stderr)
    if report["overwriteConflicts"]:
        print(
            f"[エラー] overwrite conflicts: {len(report['overwriteConflicts'])}件 "
            "(--overwriteを指定してください)",
            file=sys.stderr,
        )
        for plan in report["overwriteConflicts"]:
            print(f"  - {plan['target']}", file=sys.stderr)
    if not report["promotionCheck"]["passed"]:
        print("[エラー] promotion checkに失敗しました", file=sys.stderr)
    if not report["reviewNoteCheck"]["approved"]:
        print(
            "[エラー] review noteが承認されていません "
            f"(decision={report['reviewNoteCheck']['decision']})",
            file=sys.stderr,
        )
    if report["reviewNoteCheck"]["sourceTextIssues"]:
        print(
            "[エラー] review noteでsource text exposureを検出しました", file=sys.stderr
        )
    if report["mode"] == "execute" and report["postCopyValidationIssues"]:
        print("[エラー] copy後のvalidationに失敗しました", file=sys.stderr)


def _print_promote_report(report: dict[str, Any], *, quiet: bool) -> None:
    if quiet:
        return
    _print_copy_result(report)
    _print_blocking_issues(report)

    label = "PASS" if report["passed"] else "FAILED"
    print(f"[promote] 結果: {report['mode']} {label}")


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------


def _load_schema_or_exit(schema_arg: str) -> tuple[dict[str, Any] | None, int | None]:
    schema_path = Path(schema_arg)
    if not schema_path.exists():
        print(
            f"[エラー] schemaファイルが見つかりません: {schema_path}", file=sys.stderr
        )
        return None, 2
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f), None


def main() -> int:
    args = parse_args()

    schema, exit_code = _load_schema_or_exit(args.schema)
    if exit_code is not None:
        return exit_code

    input_path = Path(args.input)
    yaml_paths = _collect_yaml_paths(input_path)
    if yaml_paths is None:
        print(f"[エラー] --inputパスが見つかりません: {input_path}", file=sys.stderr)
        return 2

    review_note_path = Path(args.review_note)
    if not review_note_path.is_file():
        print(
            f"[エラー] --review-noteファイルが見つかりません: {review_note_path}",
            file=sys.stderr,
        )
        return 2

    target_dir = Path(args.target)
    if not args.allow_nonstandard_target and not _is_standard_target(target_dir):
        print(
            f"[エラー] --targetは{DEFAULT_TARGET_DIR}を指定してください "
            "(tests等で一時ディレクトリを使う場合は--allow-nonstandard-targetを指定)",
            file=sys.stderr,
        )
        return 2

    promotion_check = _run_promotion_check(
        input_path=input_path,
        yaml_paths=yaml_paths,
        policy=args.policy,
        story_summaries=args.story_summaries,
        schema=schema,
    )
    review_note_check = _check_review_note(review_note_path)

    raw_documents, _schema_errors = _load_yaml_documents(yaml_paths, schema)
    plans = [
        _plan_copy_for_file(path, raw, target_dir, overwrite=args.overwrite)
        for path, raw in raw_documents
    ]

    blocking = (
        not promotion_check["passed"]
        or not review_note_check["approved"]
        or bool(review_note_check["sourceTextIssues"])
        or any(p["status"] == "skipped" for p in plans)
        or any(p["status"] == "overwrite_conflict" for p in plans)
    )

    copied_files: list[str] = []
    post_copy_validation: list[str] | None = None
    if args.execute and not blocking:
        target_dir.mkdir(parents=True, exist_ok=True)
        planned = [p for p in plans if p["status"] in ("planned", "overwrite")]
        for plan in planned:
            shutil.copy2(plan["source"], plan["target"])
            copied_files.append(plan["target"])
        post_copy_validation = _validate_copied_files(
            [Path(p["target"]) for p in planned], schema
        )

    report = _build_promote_report(
        mode="execute" if args.execute else "dry-run",
        input_path=input_path,
        target_dir=target_dir,
        review_note_path=review_note_path,
        source_file_count=len(yaml_paths),
        promotion_check=promotion_check,
        review_note_check=review_note_check,
        plans=plans,
        copied_files=copied_files,
        post_copy_validation=post_copy_validation,
    )

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            "\n".join(_build_promote_report_lines(report)), encoding="utf-8"
        )

    _print_promote_report(report, quiet=args.quiet)

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
