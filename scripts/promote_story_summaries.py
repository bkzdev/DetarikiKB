#!/usr/bin/env python3
"""
Promote Story Summaries
Public-safe projection・review・品質ゲートを通過したStory Summary候補
（`schemas/story_summary.schema.json`準拠のYAML）を`knowledge/summaries/
stories/`へ安全にcopyするscript。

`scripts/promote_evidence_index.py`と同じ安全パターン
（既定dry-run・`--execute`必須・byte-for-byte copy・post-copy sanity
re-check・`--target`制限）を踏襲する（`feature/summary-promotion-copy-
script`）。**LLM呼び出しは一切含まない。**

**重要な安全方針**:
- **デフォルトはdry-run。`--execute`を指定しない限り一切ファイルを
  書き込まない**
- `--execute`時も、以下がすべて満たされない限りcopyしない（1ファイル単位、
  1つでも満たさなければそのファイルはcopyしない）:
  1. **Public-safe projection済みであること**: `storyId == publicStoryId`
     （非null）、全`episodeSummaries[].episodeId ==
     publicEpisodeId`（非null）、ファイル名が`{publicStoryId}.yaml`と一致
  2. schema検証PASS + `review.status`が`approved`または`reviewed`
     （`agents.wiki_generator.story_summaries.DISPLAYABLE_REVIEW_STATUSES`、
     `scripts/validate_story_summaries.py`の`--require-reviewed`と同じ
     判定基準） + `generationStatus`が`generated`
  3. 禁止文字列scan PASS（`FORBIDDEN_TEXT_PATTERNS`、
     `scripts/check_story_summary_drafts.py`と同じ4フィールド
     storySummary.text/episodeSummaries[].text/notes/review.notes対象、
     同scriptの`_check_forbidden_text`をそのままimport再利用する）
  4. `--registry`指定時: `publicStoryId`/全`publicEpisodeId`がPublic ID
     Registryに実在すること
  5. `--evidence-index`指定時（file/directory）: 非空の`evidenceRefs`が
     すべて該当Evidence Indexの`entries[].evidenceId`へ解決できること
     （空`evidenceRefs`は許容、§4.3.3どおり）
  6. copy先に既存ファイルがある場合は`--overwrite`が指定されている

**Evidence Indexとの設計差1（review note不要）**: `promote_evidence_index.py`
は`--review-note`（`docs/templates/evidence_index_promotion_review_
template.md`由来の別ファイル）を必須とするが、本scriptはそれを要求しない。
Story Summaryのschema自体が`review.status`/`review.reviewer`/
`review.reviewedAt`/`review.notes`という**in-fileの人間レビュー記録
セクション**を持つ設計であり（`schemas/story_summary.schema.json`
`Review`定義）、これが既にEvidence Indexの別ファイルreview noteと同じ役割
（人間レビューの記録・承認状態の表明）を果たしている。別ファイルのreview
noteを追加要求すると同じレビュー記録を二重管理することになるため、本
scriptではin-fileの`review.status`検証のみを承認条件とする。

**Evidence Indexとの設計差2（overwrite許可の理由）**: Evidence Indexは
一度昇格したentryを書き換える正当な理由が薄いため`promote_evidence_
index.py`も`--overwrite`を持つが実運用では稀にしか使わない想定である。
一方Story Summaryは、AI再生成・人間レビューでの本文修正・evidenceRefs
修正など**再生成・改訂が正当なユースケースとして頻繁に起こりうる**
（実際`knowledge/summaries/stories/`の初回昇格でもレビュー担当者が
本文を人手修正している）。そのため`--overwrite`は既定で禁止しつつも、
Evidence Indexよりも積極的に使われることを想定した設計とする。

- copyは入力ファイルのbyte-for-byte copy（`shutil.copy2`）で行い、内容の
  再生成・変換は一切行わない
- `--execute`成功後は、copy先に対してもschema+前提条件1〜5の再検証を
  再実行する（sanity re-check）
- `--target`は既定で`knowledge/summaries/stories`のみを許可する。tests等で
  一時ディレクトリを使う場合は`--allow-nonstandard-target`を明示指定する

Usage:
    # dry-run（既定、何もcopyしない）
    uv run python scripts/promote_story_summaries.py \\
        --input workspace/summary_drafts/projected \\
        --target knowledge/summaries/stories \\
        --report workspace/summary_drafts/promote_report.md

    # Public ID Registry・Evidence Indexも照合する場合
    uv run python scripts/promote_story_summaries.py \\
        --input workspace/summary_drafts/projected \\
        --target knowledge/summaries/stories \\
        --registry knowledge/public_ids/story_public_ids.yaml \\
        --evidence-index knowledge/evidence/stories \\
        --report workspace/summary_drafts/promote_report.md

    # 実copy（明示的に--executeが必要）
    uv run python scripts/promote_story_summaries.py \\
        --input workspace/summary_drafts/projected \\
        --target knowledge/summaries/stories \\
        --execute

Exit codes:
    0: dry-run成功、またはexecute成功（copy対象0件を含む）
    1: 前提条件違反（projection未済・review/generationStatus不適・
       禁止文字列検出・Registry不在・evidenceRefs未解決・overwrite
       conflict等）がある
    2: --input/--schema/--registry/--evidence-indexパスが見つからない、
       --targetが非標準かつ--allow-nonstandard-target未指定、または
       --reportがknowledge/配下を指しているなどのconfig error
"""

from __future__ import annotations

import argparse
import shutil
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
    DEFAULT_SCHEMA_PATH as DEFAULT_EVIDENCE_INDEX_SCHEMA_PATH,
)
from check_evidence_index_promotion import (  # noqa: E402
    _collect_yaml_paths as _collect_evidence_index_yaml_paths,
)
from check_evidence_index_promotion import (  # noqa: E402
    _load_yaml_documents as _load_evidence_index_yaml_documents,
)
from check_public_episode_ids import (  # noqa: E402
    DEFAULT_REGISTRY_SCHEMA_PATH,
)
from check_story_summary_drafts import _check_forbidden_text  # noqa: E402
from validate_story_summaries import (  # noqa: E402
    DEFAULT_SCHEMA_PATH as DEFAULT_STORY_SUMMARY_SCHEMA_PATH,
)
from validate_story_summaries import (  # noqa: E402
    _collect_yaml_paths,
    _validate_schema_for_file,
)

from agents.wiki_generator.evidence_index import (  # noqa: E402
    EvidenceIndexCollection,
    parse_evidence_index_document,
)
from agents.wiki_generator.story_summaries import (  # noqa: E402
    DISPLAYABLE_REVIEW_STATUSES,
    GENERATION_STATUS_GENERATED,
    StorySummaryDocument,
    parse_story_summary_document,
)

DEFAULT_TARGET_DIR = _PROJECT_ROOT / "knowledge" / "summaries" / "stories"

# --reportにknowledge/配下は一切許可しない
# (docs/runbooks/AI_PR_Playbook.md §7、scripts/check_story_summary_drafts.py
# と同じ方針)。--inputはknowledge/summaries/stories/配下の既存fileの
# 再検証・再promotion試行にも使えるようパス制限しない。
_FORBIDDEN_REPORT_DIR = (_PROJECT_ROOT / "knowledge").resolve()


# ----------------------------------------------------------------
# Argument parser
# ----------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Public-safe projection・review/品質ゲートを通過したStory "
            "Summary候補をknowledge/summaries/stories/へ安全にcopyする "
            "(既定はdry-run、実copyには--executeが必要)"
        ),
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Story Summary YAMLファイル、またはdirectory (直下の*.yaml/*.ymlを収集)",
    )
    parser.add_argument(
        "--target",
        required=True,
        help=(
            "copy先directory (既定ではknowledge/summaries/storiesのみ許可。"
            "他のpathを使う場合は--allow-nonstandard-targetを指定すること)"
        ),
    )
    parser.add_argument(
        "--report",
        default=None,
        help="check結果をMarkdownで書き出すファイルパス (任意。knowledge/配下は拒否)",
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_STORY_SUMMARY_SCHEMA_PATH),
        help=(
            "story_summary.schema.jsonのパス "
            f"(デフォルト: {DEFAULT_STORY_SUMMARY_SCHEMA_PATH})"
        ),
    )
    parser.add_argument(
        "--registry",
        default=None,
        help=(
            "Public ID Registry YAMLのパス (任意)。指定した場合、"
            "publicStoryId/全publicEpisodeIdがRegistryに実在するかを確認する"
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
        "--evidence-index",
        default=None,
        help=(
            "Evidence Index YAMLファイル、またはdirectory (任意)。指定した場合、"
            "非空のevidenceRefsが対応するentries[].evidenceIdへ解決できるかを"
            "確認する"
        ),
    )
    parser.add_argument(
        "--evidence-index-schema",
        default=str(DEFAULT_EVIDENCE_INDEX_SCHEMA_PATH),
        help=(
            "evidence_index.schema.jsonのパス "
            f"(デフォルト: {DEFAULT_EVIDENCE_INDEX_SCHEMA_PATH})"
        ),
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
        help="knowledge/summaries/stories以外のtargetを許可する (tests用)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args(argv)


def _is_standard_target(target_dir: Path) -> bool:
    try:
        return target_dir.resolve() == DEFAULT_TARGET_DIR.resolve()
    except OSError:
        return False


def _is_under_forbidden_report_dir(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    try:
        resolved.relative_to(_FORBIDDEN_REPORT_DIR)
        return True
    except ValueError:
        return False


# ----------------------------------------------------------------
# Precondition 1: public-safe projection
# ----------------------------------------------------------------


def _check_projection(path: Path, document: StorySummaryDocument) -> list[str]:
    """`storyId == publicStoryId`（非null）、全episodeSummaries[].episodeId
    == publicEpisodeId（非null）、ファイル名が`{publicStoryId}.yaml`と一致
    することを確認する (前提条件1)。"""
    issues: list[str] = []
    public_story_id = document.public_story_id
    if not public_story_id:
        issues.append(
            "publicStoryIdが設定されていません (public-safe projection未実施)"
        )
    elif document.story_id != public_story_id:
        issues.append(
            f"storyId '{document.story_id}' がpublicStoryId '{public_story_id}' と"
            "一致しません"
        )

    for entry in document.episode_summaries:
        if not entry.public_episode_id:
            issues.append(
                f"episodeId '{entry.episode_id}': publicEpisodeIdが設定されていません"
            )
        elif entry.episode_id != entry.public_episode_id:
            issues.append(
                f"episodeId '{entry.episode_id}' がpublicEpisodeId "
                f"'{entry.public_episode_id}' と一致しません"
            )

    if public_story_id and path.name != f"{public_story_id}.yaml":
        issues.append(
            f"ファイル名 '{path.name}' がpublicStoryId '{public_story_id}.yaml' と"
            "一致しません"
        )

    return issues


# ----------------------------------------------------------------
# Precondition 2: review.status / generationStatus
# ----------------------------------------------------------------


def _check_review_and_generation_status(
    document: StorySummaryDocument,
) -> list[str]:
    """review.statusがapproved/reviewedであり、generationStatusがgenerated
    であることを確認する (前提条件2)。

    review noteを別ファイルで要求しない理由はmodule docstring「Evidence
    Indexとの設計差1」参照 (in-fileのreview sectionが人間レビュー記録)。
    """
    issues: list[str] = []
    if document.review.status not in DISPLAYABLE_REVIEW_STATUSES:
        issues.append(
            f"review.statusが'{document.review.status}'です (approved/reviewedのみ許可)"
        )
    if document.generation_status != GENERATION_STATUS_GENERATED:
        issues.append(
            f"generationStatusが'{document.generation_status}'です (generatedのみ許可)"
        )
    return issues


# ----------------------------------------------------------------
# Precondition 4: Public ID Registry existence check (--registry指定時)
# ----------------------------------------------------------------


def _load_registry_ids(
    path: Path, schema: dict[str, Any]
) -> tuple[dict[str, set[str]] | None, list[str]]:
    """Public ID Registryを読み込み、publicStoryId -> publicEpisodeId集合の
    lookupを組み立てる。

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

    lookup: dict[str, set[str]] = {}
    for story in raw.get("stories", []) or []:
        public_story_id = story.get("publicStoryId")
        if not public_story_id:
            continue
        lookup[public_story_id] = {
            episode.get("publicEpisodeId")
            for episode in story.get("episodes", []) or []
            if episode.get("publicEpisodeId")
        }
    return lookup, []


def _check_registry(
    document: StorySummaryDocument, registry_lookup: dict[str, set[str]]
) -> list[str]:
    public_story_id = document.public_story_id
    if public_story_id not in registry_lookup:
        return [f"publicStoryId '{public_story_id}' がPublic ID Registryに存在しません"]

    episode_ids = registry_lookup[public_story_id]
    issues: list[str] = []
    for entry in document.episode_summaries:
        if entry.public_episode_id and entry.public_episode_id not in episode_ids:
            issues.append(
                f"publicEpisodeId '{entry.public_episode_id}' がPublic ID "
                f"Registryに存在しません (publicStoryId={public_story_id})"
            )
    return issues


# ----------------------------------------------------------------
# Precondition 5: Evidence Index evidenceRefs resolution (--evidence-index指定時)
# ----------------------------------------------------------------


def _load_evidence_ids(
    input_path: Path, schema: dict[str, Any]
) -> tuple[frozenset[str] | None, list[str]]:
    yaml_paths = _collect_evidence_index_yaml_paths(input_path)
    if yaml_paths is None:
        return None, [f"--evidence-indexパスが見つかりません: {input_path}"]

    raw_documents, schema_errors = _load_evidence_index_yaml_documents(
        yaml_paths, schema
    )
    if schema_errors:
        return None, schema_errors

    collection = EvidenceIndexCollection(
        documents=[parse_evidence_index_document(raw) for _, raw in raw_documents]
    )
    evidence_ids = frozenset(
        entry.evidence_id
        for document in collection.documents
        for entry in document.entries
        if entry.evidence_id
    )
    return evidence_ids, []


def _check_evidence_refs(
    document: StorySummaryDocument, evidence_ids: frozenset[str]
) -> list[str]:
    """非空のevidenceRefsが対応するEvidence Indexのentries[].evidenceIdへ
    解決できるかを確認する (前提条件5)。空のevidenceRefsは許容する。"""
    issues: list[str] = []
    if document.story_summary is not None:
        for ref in document.story_summary.evidence_refs:
            if ref not in evidence_ids:
                issues.append(
                    f"storySummary.evidenceRefs: evidenceId '{ref}' が"
                    "Evidence Indexに存在しません"
                )
    for entry in document.episode_summaries:
        for ref in entry.evidence_refs:
            if ref not in evidence_ids:
                issues.append(
                    f"episodeId={entry.episode_id!r} evidenceRefs: "
                    f"evidenceId '{ref}' がEvidence Indexに存在しません"
                )
    return issues


# ----------------------------------------------------------------
# Combined precondition check (1, 2, 3, 4, 5)
# ----------------------------------------------------------------


def _run_preconditions(
    path: Path,
    document: StorySummaryDocument,
    *,
    registry_lookup: dict[str, set[str]] | None,
    evidence_ids: frozenset[str] | None,
) -> list[str]:
    issues: list[str] = []
    issues.extend(_check_projection(path, document))
    issues.extend(_check_review_and_generation_status(document))
    issues.extend(_check_forbidden_text(document))
    if registry_lookup is not None and document.public_story_id:
        issues.extend(_check_registry(document, registry_lookup))
    if evidence_ids is not None:
        issues.extend(_check_evidence_refs(document, evidence_ids))
    return issues


# ----------------------------------------------------------------
# Copy planning (per-file precondition check + overwrite判定)
# ----------------------------------------------------------------


def _plan_copy_for_file(
    path: Path,
    document: StorySummaryDocument,
    *,
    target_dir: Path,
    overwrite: bool,
    registry_lookup: dict[str, set[str]] | None,
    evidence_ids: frozenset[str] | None,
) -> dict[str, Any]:
    issues = _run_preconditions(
        path, document, registry_lookup=registry_lookup, evidence_ids=evidence_ids
    )
    public_story_id = document.public_story_id
    if not public_story_id:
        return {
            "source": str(path),
            "status": "skipped",
            "issues": issues,
        }

    target_path = target_dir / f"{public_story_id}.yaml"
    if issues:
        return {
            "source": str(path),
            "target": str(target_path),
            "status": "skipped",
            "issues": issues,
        }
    if target_path.exists() and not overwrite:
        return {
            "source": str(path),
            "target": str(target_path),
            "status": "overwrite_conflict",
            "issues": ["target already exists (--overwriteが必要)"],
        }
    status = "overwrite" if target_path.exists() else "planned"
    return {
        "source": str(path),
        "target": str(target_path),
        "status": status,
        "issues": [],
    }


# ----------------------------------------------------------------
# Post-copy validation (sanity re-check)
# ----------------------------------------------------------------


def _validate_copied_files(
    target_paths: list[Path],
    *,
    schema: dict[str, Any],
    registry_lookup: dict[str, set[str]] | None,
    evidence_ids: frozenset[str] | None,
) -> list[str]:
    issues: list[str] = []
    for target_path in target_paths:
        raw, schema_errors = _validate_schema_for_file(target_path, schema)
        if schema_errors:
            issues.extend(schema_errors)
            continue
        document = parse_story_summary_document(raw)
        issues.extend(
            f"{target_path}: {message}"
            for message in _run_preconditions(
                target_path,
                document,
                registry_lookup=registry_lookup,
                evidence_ids=evidence_ids,
            )
        )
    return issues


# ----------------------------------------------------------------
# Report building
# ----------------------------------------------------------------


def _preconditions_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## Preconditions", ""]
    lines.append(
        "1. Public-safe projection (storyId==publicStoryId, "
        "episodeId==publicEpisodeId, filename == {publicStoryId}.yaml)"
    )
    lines.append(
        "2. schema validation + review.status (approved/reviewed) + "
        "generationStatus (generated)"
    )
    lines.append("3. Forbidden text pattern scan (FORBIDDEN_TEXT_PATTERNS)")
    lines.append(
        "4. Public ID Registry existence check: "
        + ("checked" if report["registry"] else "skipped (--registry not specified)")
    )
    lines.append(
        "5. Evidence Index evidenceRefs resolution: "
        + (
            "checked"
            if report["evidenceIndex"]
            else "skipped (--evidence-index not specified)"
        )
    )
    lines.append(
        "- Per-file results are listed under Planned copies / Skipped files / "
        "Overwrite conflicts below."
    )
    lines.append("")
    return lines


def _copy_plan_lines(heading: str, plans: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {heading}", ""]
    if not plans:
        lines.append("- (none)")
    for plan in plans:
        target = plan.get("target")
        issues = plan.get("issues") or []
        reason = f" ({'; '.join(issues)})" if issues else ""
        if target:
            lines.append(f"- {plan['source']} -> {target}{reason}")
        else:
            lines.append(f"- {plan['source']}{reason}")
    lines.append("")
    return lines


def _copied_and_postcopy_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## Copied files", ""]
    if report["mode"] != "execute":
        lines.append("- (skipped, dry-run mode)")
    elif report["copiedFiles"]:
        for path in report["copiedFiles"]:
            lines.append(f"- {path}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Post-copy validation")
    lines.append("")
    if report["mode"] != "execute":
        lines.append("- (skipped, dry-run mode)")
    elif report["postCopyValidationIssues"]:
        lines.append("- Result: FAIL")
        for issue in report["postCopyValidationIssues"]:
            lines.append(f"  - {issue}")
    else:
        lines.append("- Result: PASS")
    lines.append("")
    return lines


def _build_report_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        "# Story Summary Promotion Copy Report",
        "",
        f"- Mode: {report['mode']}",
        f"- Input: {report['input']}",
        f"- Target: {report['target']}",
        f"- Registry: {report['registry'] or '(not specified)'}",
        f"- Evidence Index: {report['evidenceIndex'] or '(not specified)'}",
        f"- Source file count: {report['sourceFileCount']}",
        "",
    ]
    lines.extend(_preconditions_lines(report))
    lines.extend(_copy_plan_lines("Planned copies", report["plannedCopies"]))
    lines.extend(_copy_plan_lines("Skipped files", report["skippedFiles"]))
    lines.extend(_copy_plan_lines("Overwrite conflicts", report["overwriteConflicts"]))
    lines.extend(_copied_and_postcopy_lines(report))

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
            print(f"  - {plan['source']}: {'; '.join(plan['issues'])}", file=sys.stderr)
    if report["overwriteConflicts"]:
        print(
            f"[エラー] overwrite conflicts: {len(report['overwriteConflicts'])}件 "
            "(--overwriteを指定してください)",
            file=sys.stderr,
        )
        for plan in report["overwriteConflicts"]:
            print(f"  - {plan['target']}", file=sys.stderr)
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


def _load_json_schema_or_exit(
    schema_arg: str,
) -> tuple[dict[str, Any] | None, int | None]:
    import json

    schema_path = Path(schema_arg)
    if not schema_path.exists():
        print(
            f"[エラー] schemaファイルが見つかりません: {schema_path}", file=sys.stderr
        )
        return None, 2
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f), None


def _resolve_registry_lookup(
    args: argparse.Namespace,
) -> tuple[dict[str, set[str]] | None, int | None]:
    """`--registry`指定時にlookupを組み立てる。

    戻り値: (lookup, exit_code)。`--registry`未指定ならlookupはNone・
    exit_codeもNone。エラー時はlookupがNone・exit_codeが2
    (エラーメッセージはこのヘルパー内で出力済み)。
    """
    if not args.registry:
        return None, None

    registry_path = Path(args.registry)
    if not registry_path.exists():
        print(
            f"[エラー] --registryパスが見つかりません: {registry_path}",
            file=sys.stderr,
        )
        return None, 2

    registry_schema, exit_code = _load_json_schema_or_exit(args.registry_schema)
    if exit_code is not None:
        return None, exit_code

    registry_lookup, registry_errors = _load_registry_ids(
        registry_path, registry_schema
    )
    if registry_errors:
        print("[エラー] Registryの読み込みに失敗しました:", file=sys.stderr)
        for issue in registry_errors:
            print(f"  - {issue}", file=sys.stderr)
        return None, 2

    return registry_lookup, None


def _resolve_evidence_ids(
    args: argparse.Namespace,
) -> tuple[frozenset[str] | None, int | None]:
    """`--evidence-index`指定時にevidenceIdの集合を組み立てる。

    戻り値: (evidence_ids, exit_code)。挙動は`_resolve_registry_lookup`と
    同じ方針 (未指定ならNone/None、エラー時はNone/2)。
    """
    if not args.evidence_index:
        return None, None

    evidence_index_schema, exit_code = _load_json_schema_or_exit(
        args.evidence_index_schema
    )
    if exit_code is not None:
        return None, exit_code

    evidence_ids, evidence_errors = _load_evidence_ids(
        Path(args.evidence_index), evidence_index_schema
    )
    if evidence_errors:
        print("[エラー] --evidence-indexの読み込みに失敗しました:", file=sys.stderr)
        for issue in evidence_errors:
            print(f"  - {issue}", file=sys.stderr)
        return None, 2

    return evidence_ids, None


def _build_plans(
    yaml_paths: list[Path],
    schema: dict[str, Any],
    *,
    target_dir: Path,
    overwrite: bool,
    registry_lookup: dict[str, set[str]] | None,
    evidence_ids: frozenset[str] | None,
) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for path in yaml_paths:
        raw, schema_errors = _validate_schema_for_file(path, schema)
        if schema_errors:
            plans.append(
                {"source": str(path), "status": "skipped", "issues": schema_errors}
            )
            continue
        document = parse_story_summary_document(raw)
        plans.append(
            _plan_copy_for_file(
                path,
                document,
                target_dir=target_dir,
                overwrite=overwrite,
                registry_lookup=registry_lookup,
                evidence_ids=evidence_ids,
            )
        )
    return plans


def _execute_copies(
    plans: list[dict[str, Any]],
    *,
    target_dir: Path,
    schema: dict[str, Any],
    registry_lookup: dict[str, set[str]] | None,
    evidence_ids: frozenset[str] | None,
) -> tuple[list[str], list[str]]:
    """planned/overwrite状態のplanをcopyし、post-copy validationを行う。

    戻り値: (copied_files, post_copy_validation_issues)。
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    planned = [p for p in plans if p["status"] in ("planned", "overwrite")]
    copied_files: list[str] = []
    for plan in planned:
        shutil.copy2(plan["source"], plan["target"])
        copied_files.append(plan["target"])
    post_copy_validation = _validate_copied_files(
        [Path(p["target"]) for p in planned],
        schema=schema,
        registry_lookup=registry_lookup,
        evidence_ids=evidence_ids,
    )
    return copied_files, post_copy_validation


def _build_report(
    *,
    args: argparse.Namespace,
    input_path: Path,
    target_dir: Path,
    yaml_paths: list[Path],
    plans: list[dict[str, Any]],
    copied_files: list[str],
    post_copy_validation: list[str] | None,
) -> dict[str, Any]:
    blocking = any(p["status"] in ("skipped", "overwrite_conflict") for p in plans)
    passed = not blocking
    if args.execute and post_copy_validation:
        passed = False

    return {
        "mode": "execute" if args.execute else "dry-run",
        "input": str(input_path),
        "target": str(target_dir),
        "registry": str(args.registry) if args.registry else None,
        "evidenceIndex": str(args.evidence_index) if args.evidence_index else None,
        "sourceFileCount": len(yaml_paths),
        "plannedCopies": [p for p in plans if p["status"] in ("planned", "overwrite")],
        "skippedFiles": [p for p in plans if p["status"] == "skipped"],
        "overwriteConflicts": [p for p in plans if p["status"] == "overwrite_conflict"],
        "copiedFiles": copied_files,
        "postCopyValidationIssues": post_copy_validation,
        "passed": passed,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    schema, exit_code = _load_json_schema_or_exit(args.schema)
    if exit_code is not None:
        return exit_code

    input_path = Path(args.input)
    yaml_paths = _collect_yaml_paths(input_path)
    if yaml_paths is None:
        print(f"[エラー] --inputパスが見つかりません: {input_path}", file=sys.stderr)
        return 2

    target_dir = Path(args.target)
    if not args.allow_nonstandard_target and not _is_standard_target(target_dir):
        print(
            f"[エラー] --targetは{DEFAULT_TARGET_DIR}を指定してください "
            "(tests等で一時ディレクトリを使う場合は--allow-nonstandard-targetを指定)",
            file=sys.stderr,
        )
        return 2

    if args.report is not None and _is_under_forbidden_report_dir(Path(args.report)):
        print(
            f"[エラー] --reportにknowledge/配下のpathは指定できません: {args.report}",
            file=sys.stderr,
        )
        return 2

    registry_lookup, exit_code = _resolve_registry_lookup(args)
    if exit_code is not None:
        return exit_code

    evidence_ids, exit_code = _resolve_evidence_ids(args)
    if exit_code is not None:
        return exit_code

    plans = _build_plans(
        yaml_paths,
        schema,
        target_dir=target_dir,
        overwrite=args.overwrite,
        registry_lookup=registry_lookup,
        evidence_ids=evidence_ids,
    )

    blocking = any(p["status"] in ("skipped", "overwrite_conflict") for p in plans)
    copied_files: list[str] = []
    post_copy_validation: list[str] | None = None
    if args.execute and not blocking:
        copied_files, post_copy_validation = _execute_copies(
            plans,
            target_dir=target_dir,
            schema=schema,
            registry_lookup=registry_lookup,
            evidence_ids=evidence_ids,
        )

    report = _build_report(
        args=args,
        input_path=input_path,
        target_dir=target_dir,
        yaml_paths=yaml_paths,
        plans=plans,
        copied_files=copied_files,
        post_copy_validation=post_copy_validation,
    )

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(_build_report_lines(report)), encoding="utf-8")

    _print_promote_report(report, quiet=args.quiet)

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
