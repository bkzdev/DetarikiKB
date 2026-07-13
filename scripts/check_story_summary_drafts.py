#!/usr/bin/env python3
"""
Check Story Summary Drafts
AI生成したStory/Episode Summary draft（`schemas/story_summary.schema.json`
準拠、`scripts/generate_story_summaries.py`の出力形式）が
`knowledge/summaries/stories/`へ昇格可能かをcheckするgatekeeper script。

`docs/architecture/06_AI/Story_Summary_Generation_Plan.md` §8（品質ゲート）の
機械的検証を実装する。**実際のfile書き換え・copy・昇格は一切行わない**
(check-onlyのscript、`scripts/check_evidence_index_promotion.py`と同じ
gatekeeperパターン、`summary-generation-quality-gate`)。

機械的検証項目（Plan §8.1の表のうち、本scriptが対象とする4項目。
「public ID projection検証」は`scripts/project_story_summary_public_ids.py`
の責務であり本scriptの対象外）:

1. **schema検証**: `schemas/story_summary.schema.json`
   (`scripts/validate_story_summaries.py`と同じDraft7Validatorの使い方。
   構造化フィールドのparseは`agents.wiki_generator.story_summaries`の
   `parse_story_summary_document`をimport再利用する)
2. **evidenceRefs実在性**: `--normalized`（Normalized Story JSON file/
   directory）を指定した場合、storySummary/episodeSummariesの
   evidenceRefsが対応するstory/episodeのblockId集合
   (`agents.summarizer.extract_episode_blocks`で抽出、
   `dialogue`/`monologue`/`narration`/`choice`のみ) に実在するかを検証する。
   実在しないIDはblocking。`--normalized`で該当story/episodeが見つからない
   場合はwarning（検証不能、非blocking）。`--normalized`未指定時はこの
   検証全体をskipし、reportに明記する（warning扱い、非blocking）
3. **禁止文字列scan**: draft全text
   (`storySummary.text`/`episodeSummaries[].text`/`notes`/
   `review.notes`) に対する`FORBIDDEN_TEXT_PATTERNS`
   (`agents.wiki_generator.story_summaries`からimport) scan。検出はblocking
4. **長文verbatim引用検出**: `--normalized`指定時のみ、
   `episodeSummaries[].text`と対応episodeの参照元Block本文との連続一致を
   検出する (`agents.summarizer.check_verbatim_quotes`をimport再利用、
   既定閾値`--verbatim-threshold`30文字)。検出はblocking。
   **storySummary.text (story-level) は対象外**とする
   (`agents/summarizer/generator.py`の`synthesize_story_summary`が
   story合成では同じ理由でverbatim検出を行わない設計としているのと
   同じ判断: story合成の入力は既にsafeなepisode summary群であり、
   生のBlock本文そのものではないため)

**人間レビュー項目（Plan §8.2: 内容正確性・文体・`review.status`の判定）は
本scriptの対象外である。** 機械的検証をすべて通過したdraftのみが人間レビュー
対象になる、というPlan §8.3の分担方針をそのまま実装する。

Usage:
    # schema検証・禁止文字列scanのみ (--normalized未指定、evidenceRefs実在性・
    # verbatim検出はskip)
    uv run python scripts/check_story_summary_drafts.py \\
        --input workspace/summary_drafts/

    # Normalized Story JSONも指定し、evidenceRefs実在性・verbatim検出も行う
    uv run python scripts/check_story_summary_drafts.py \\
        --input workspace/summary_drafts/ \\
        --normalized workspace/dry_runs/summary_generation/normalized \\
        --report workspace/summary_drafts/quality_gate_report.md

    # 既存knowledge/summaries/stories/配下の再検証にも使える
    # (--inputはworkspace配下限定ではない)
    uv run python scripts/check_story_summary_drafts.py \\
        --input knowledge/summaries/stories

Exit codes:
    0: quality gate check通過（blocking issueなし。warningがあっても0）
    1: quality gate check失敗（blocking issueあり）
    2: 入力パスが見つからない、または`--report`がknowledge/配下を指している
       などのconfig error
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.summarizer import (  # noqa: E402
    DEFAULT_VERBATIM_THRESHOLD,
    ExtractedBlock,
    check_verbatim_quotes,
    extract_episode_blocks,
)
from agents.wiki_generator.story_summaries import (  # noqa: E402
    FORBIDDEN_TEXT_PATTERNS,
    EpisodeSummaryEntry,
    StorySummaryDocument,
    parse_story_summary_document,
)

DEFAULT_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "story_summary.schema.json"

# knowledge/配下は本scriptの --report 出力先として一切許可しない
# (workspace限定、docs/runbooks/AI_PR_Playbook.md §7方針。--inputは
# knowledge/summaries/stories/ 配下の既存fileの再検証にも使うため制限しない)。
_FORBIDDEN_OUTPUT_DIR = (_PROJECT_ROOT / "knowledge").resolve()


# ----------------------------------------------------------------
# Argument parser
# ----------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Story/Episode Summary draft (schemas/story_summary.schema.json準拠) が"
            "knowledge/summaries/stories/へ昇格可能かをcheckする"
            "(check-only、実際のfile書き換え・copy・昇格は行わない)"
        ),
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help=(
            "Story Summary draft YAMLファイル、またはdirectory "
            "(直下の*.yaml/*.ymlを収集。knowledge/summaries/stories/配下の"
            "既存fileの検証にも使えるようパス制限はしない)"
        ),
    )
    parser.add_argument(
        "--normalized",
        default=None,
        help=(
            "Normalized Story JSON (schemas/story.schema.json準拠) の"
            "ファイル、またはdirectory (任意)。指定した場合のみ、"
            "evidenceRefs実在性検証・長文verbatim引用検出を行う"
        ),
    )
    parser.add_argument(
        "--verbatim-threshold",
        type=int,
        default=DEFAULT_VERBATIM_THRESHOLD,
        help=(
            "長文verbatim引用検出の閾値文字数 "
            f"(デフォルト: {DEFAULT_VERBATIM_THRESHOLD}、"
            "agents/summarizer/generator.pyと同じ既定値)"
        ),
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help=f"story_summary.schema.jsonのパス (デフォルト: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--report",
        default=None,
        help=(
            "check結果をMarkdownで書き出すファイルパス (任意。workspace配下を"
            "指定すること、knowledge/配下は拒否、exit code 2)"
        ),
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args(argv)


def _is_under_forbidden_dir(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    try:
        resolved.relative_to(_FORBIDDEN_OUTPUT_DIR)
        return True
    except ValueError:
        return False


# ----------------------------------------------------------------
# Input collection (draft YAML)
# ----------------------------------------------------------------


def _collect_yaml_paths(input_path: Path) -> list[Path] | None:
    """--inputがファイルならそれ単体、directoryなら直下の*.yaml/*.ymlを返す
    (`scripts/validate_story_summaries.py`と同じ方針)。"""
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.glob("*.yaml")) + sorted(input_path.glob("*.yml"))
    return None


def _load_yaml_documents(
    yaml_paths: list[Path], schema: dict[str, Any]
) -> tuple[list[tuple[Path, dict[str, Any]]], list[str]]:
    """全ファイルをYAML読み込み+schema検証する
    (`scripts/check_evidence_index_promotion.py`の`_load_yaml_documents`と
    同じパターン)。

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
# Input collection (Normalized Story JSON, --normalized)
# ----------------------------------------------------------------


def _collect_json_paths(input_path: Path) -> list[Path] | None:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.glob("*.json"))
    return None


def _load_json_documents(
    json_paths: list[Path],
) -> tuple[list[dict[str, Any]], list[str]]:
    documents: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in json_paths:
        try:
            with open(path, encoding="utf-8") as f:
                documents.append(json.load(f))
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"{path}: 読み込み失敗: {e}")
    return documents, errors


@dataclass
class NormalizedIndex:
    """`--normalized`から構築した、evidenceRefs実在性検証・verbatim検出用の
    索引。

    `episode_blocks`はepisodeId単位 (episodeIdはproject全体で一意という
    既存のID命名規則、`Identifier_Specification.md`に依拠する)。
    `story_block_ids`はstoryId単位のblockId union (story-level
    evidenceRefsはepisode-level evidenceRefsのunionとして合成される設計
    `Story_Summary_Generation_Plan.md` §11のため、story-level検証に使う)。
    """

    episode_blocks: dict[str, list[ExtractedBlock]] = field(default_factory=dict)
    story_block_ids: dict[str, frozenset[str]] = field(default_factory=dict)


def _build_normalized_index(documents: list[dict[str, Any]]) -> NormalizedIndex:
    episode_blocks: dict[str, list[ExtractedBlock]] = {}
    story_block_ids_mut: dict[str, set[str]] = {}
    for document in documents:
        story_id = document.get("storyId")
        for episode in document.get("episodes", []) or []:
            episode_id = episode.get("episodeId")
            if not episode_id:
                continue
            blocks = extract_episode_blocks(episode)
            episode_blocks[episode_id] = blocks
            if story_id:
                story_block_ids_mut.setdefault(story_id, set()).update(
                    block.block_id for block in blocks
                )
    story_block_ids = {
        story_id: frozenset(ids) for story_id, ids in story_block_ids_mut.items()
    }
    return NormalizedIndex(
        episode_blocks=episode_blocks, story_block_ids=story_block_ids
    )


# ----------------------------------------------------------------
# 禁止文字列scan (項目3)
# ----------------------------------------------------------------


def _scan_text_for_forbidden_patterns(label: str, text: str | None) -> list[str]:
    if not text:
        return []
    return [
        f"{label}: 禁止文字列 '{pattern}' を検出しました"
        for pattern in FORBIDDEN_TEXT_PATTERNS
        if pattern in text
    ]


def _check_forbidden_text(document: StorySummaryDocument) -> list[str]:
    """draft全text (storySummary.text/episodeSummaries[].text/notes/
    review.notes) を対象にした禁止文字列scan (項目3)。"""
    issues: list[str] = []
    story_id = document.story_id
    if document.story_summary is not None:
        issues.extend(
            _scan_text_for_forbidden_patterns(
                f"storyId={story_id!r} storySummary.text", document.story_summary.text
            )
        )
    for entry in document.episode_summaries:
        issues.extend(
            _scan_text_for_forbidden_patterns(
                f"episodeId={entry.episode_id!r} text", entry.text
            )
        )
    issues.extend(
        _scan_text_for_forbidden_patterns(f"storyId={story_id!r} notes", document.notes)
    )
    issues.extend(
        _scan_text_for_forbidden_patterns(
            f"storyId={story_id!r} review.notes", document.review.notes
        )
    )
    return issues


# ----------------------------------------------------------------
# evidenceRefs実在性検証 (項目2、--normalized指定時のみ)
# ----------------------------------------------------------------


def _check_evidence_refs_exist(
    document: StorySummaryDocument, normalized_index: NormalizedIndex
) -> tuple[list[str], list[str]]:
    """戻り値: (blocking issues, warnings)。"""
    issues: list[str] = []
    warnings: list[str] = []
    story_id = document.story_id

    if document.story_summary is not None and document.story_summary.evidence_refs:
        story_block_ids = normalized_index.story_block_ids.get(story_id)
        if story_block_ids is None:
            warnings.append(
                f"storyId={story_id!r}: --normalizedに対応するstoryが見つからない"
                "ため storySummary.evidenceRefs を検証できません"
            )
        else:
            issues.extend(
                f"storyId={story_id!r} storySummary.evidenceRefs: "
                f"blockId '{ref}' はこのstoryのNormalized Story JSONに"
                "実在しません"
                for ref in document.story_summary.evidence_refs
                if ref not in story_block_ids
            )

    for entry in document.episode_summaries:
        if not entry.evidence_refs:
            continue
        blocks = normalized_index.episode_blocks.get(entry.episode_id)
        if blocks is None:
            warnings.append(
                f"episodeId={entry.episode_id!r}: --normalizedに対応するepisodeが"
                "見つからないためevidenceRefsを検証できません"
            )
            continue
        valid_ids = frozenset(block.block_id for block in blocks)
        issues.extend(
            f"episodeId={entry.episode_id!r} evidenceRefs: blockId '{ref}' は"
            "このepisodeのNormalized Story JSONに実在しません"
            for ref in entry.evidence_refs
            if ref not in valid_ids
        )

    return issues, warnings


# ----------------------------------------------------------------
# 長文verbatim引用検出 (項目4、--normalized指定時のみ、episode-levelのみ)
# ----------------------------------------------------------------


def _check_episode_verbatim_quotes(
    entry: EpisodeSummaryEntry, normalized_index: NormalizedIndex, *, threshold: int
) -> list[str]:
    blocks = normalized_index.episode_blocks.get(entry.episode_id)
    if not blocks:
        return []
    generation_issues = check_verbatim_quotes(entry.text, blocks, threshold=threshold)
    return [
        f"episodeId={entry.episode_id!r}: {issue.message}"
        for issue in generation_issues
    ]


def _check_verbatim_quotes_for_document(
    document: StorySummaryDocument, normalized_index: NormalizedIndex, *, threshold: int
) -> list[str]:
    """storySummary.text (story-level) は対象外。理由はモジュール
    docstring項目4参照 (`synthesize_story_summary`と同じ判断)。"""
    issues: list[str] = []
    for entry in document.episode_summaries:
        issues.extend(
            _check_episode_verbatim_quotes(entry, normalized_index, threshold=threshold)
        )
    return issues


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


def _build_report_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        "# Story Summary Draft Quality Gate Check Report",
        "",
        f"- Input: {report['input']}",
        f"- Normalized input: {report['normalizedInput'] or '(not specified)'}",
        f"- File count: {report['fileCount']}",
        f"- Story count (schema-valid): {report['storyCount']}",
        f"- Episode summary count: {report['episodeSummaryCount']}",
        "",
    ]

    _append_result_section(lines, "## Schema Validation", report["schemaIssues"])

    lines.append("## evidenceRefs Existence Check")
    lines.append("")
    if report["evidenceRefsCheck"]["status"] == "skipped":
        lines.append("- Status: skipped (--normalized not specified)")
        lines.append("- Result: PASS (skip、非blocking)")
    else:
        lines.append("- Status: checked")
        _append_result_section(lines, "", report["evidenceRefsCheck"]["issues"])
    lines.append("")

    _append_result_section(
        lines, "## Forbidden Text Pattern Scan", report["forbiddenTextIssues"]
    )

    lines.append("## Verbatim Quote Detection (episode-level only)")
    lines.append("")
    if report["verbatimCheck"]["status"] == "skipped":
        lines.append("- Status: skipped (--normalized not specified)")
        lines.append("- Result: PASS (skip、非blocking)")
        lines.append(
            "- Note: storySummary.text (story-level) はこの検証の対象外です"
            "（`agents/summarizer/generator.py`の`synthesize_story_summary`が"
            "story合成でverbatim検出を行わない設計と同じ理由）。"
        )
    else:
        lines.append("- Status: checked")
        _append_result_section(lines, "", report["verbatimCheck"]["issues"])
        lines.append(
            "- Note: storySummary.text (story-level) はこの検証の対象外です"
            "（`agents/summarizer/generator.py`の`synthesize_story_summary`が"
            "story合成でverbatim検出を行わない設計と同じ理由）。"
        )
    lines.append("")

    lines.append("## Warnings")
    lines.append("")
    if report["warnings"]:
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Out of Scope (人間レビュー、Plan §8.2)")
    lines.append("")
    lines.append(
        "- 内容の正確性（明示された事実のみか、AI考察が混入していないか）・"
        "文体・簡潔さ・`review.status`の判定（reviewed/approved/rejected/"
        "needs_revision）は本scriptの対象外です。機械的検証を通過した"
        "draftのみが人間レビュー対象になります (Plan §8.3)。"
    )
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
    normalized_input: str | None,
    normalized_index: NormalizedIndex | None,
    normalized_load_errors: list[str],
    verbatim_threshold: int,
    schema: dict[str, Any],
) -> dict[str, Any]:
    raw_documents, schema_issues = _load_yaml_documents(yaml_paths, schema)

    documents = [parse_story_summary_document(raw) for _, raw in raw_documents]

    forbidden_text_issues: list[str] = []
    for document in documents:
        forbidden_text_issues.extend(_check_forbidden_text(document))

    warnings: list[str] = list(normalized_load_errors)

    if normalized_index is None:
        evidence_refs_check: dict[str, Any] = {"status": "skipped", "issues": []}
        verbatim_check: dict[str, Any] = {"status": "skipped", "issues": []}
    else:
        evidence_refs_issues: list[str] = []
        for document in documents:
            issues, doc_warnings = _check_evidence_refs_exist(
                document, normalized_index
            )
            evidence_refs_issues.extend(issues)
            warnings.extend(doc_warnings)
        evidence_refs_check = {"status": "checked", "issues": evidence_refs_issues}

        verbatim_issues: list[str] = []
        for document in documents:
            verbatim_issues.extend(
                _check_verbatim_quotes_for_document(
                    document, normalized_index, threshold=verbatim_threshold
                )
            )
        verbatim_check = {"status": "checked", "issues": verbatim_issues}

    episode_summary_count = sum(
        len(document.episode_summaries) for document in documents
    )

    passed = not (
        schema_issues
        or forbidden_text_issues
        or evidence_refs_check["issues"]
        or verbatim_check["issues"]
    )

    return {
        "input": str(input_path),
        "normalizedInput": normalized_input,
        "fileCount": len(yaml_paths),
        "storyCount": len(documents),
        "episodeSummaryCount": episode_summary_count,
        "schemaIssues": schema_issues,
        "forbiddenTextIssues": forbidden_text_issues,
        "evidenceRefsCheck": evidence_refs_check,
        "verbatimCheck": verbatim_check,
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
        f"[quality-gate] {report['fileCount']} ファイル、"
        f"{report['storyCount']} story、"
        f"{report['episodeSummaryCount']} episode summaries"
    )
    _print_issue_block("schema検証に失敗しました", report["schemaIssues"])
    _print_issue_block("禁止文字列を検出しました", report["forbiddenTextIssues"])
    _print_issue_block(
        "evidenceRefs実在性検証に失敗しました", report["evidenceRefsCheck"]["issues"]
    )
    _print_issue_block(
        "長文verbatim引用を検出しました", report["verbatimCheck"]["issues"]
    )
    for warning in report["warnings"]:
        print(f"[警告] {warning}")
    print(f"[quality-gate] 結果: {'PASS' if report['passed'] else 'FAIL'}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

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

    if args.report is not None:
        report_path = Path(args.report)
        if _is_under_forbidden_dir(report_path):
            print(
                f"[エラー] --reportにknowledge/配下のpathは指定できません: "
                f"{report_path}",
                file=sys.stderr,
            )
            return 2
    else:
        report_path = None

    normalized_index: NormalizedIndex | None = None
    normalized_load_errors: list[str] = []
    if args.normalized is not None:
        normalized_path = Path(args.normalized)
        json_paths = _collect_json_paths(normalized_path)
        if json_paths is None:
            print(
                f"[エラー] --normalizedパスが見つかりません: {normalized_path}",
                file=sys.stderr,
            )
            return 2
        normalized_documents, normalized_load_errors = _load_json_documents(json_paths)
        if json_paths and not normalized_documents:
            print(
                "[エラー] --normalizedのNormalized Story JSON読み込みに"
                "すべて失敗しました:",
                file=sys.stderr,
            )
            for error in normalized_load_errors:
                print(f"  - {error}", file=sys.stderr)
            return 2
        normalized_index = _build_normalized_index(normalized_documents)

    report = _build_report(
        input_path=input_path,
        yaml_paths=yaml_paths,
        normalized_input=args.normalized,
        normalized_index=normalized_index,
        normalized_load_errors=normalized_load_errors,
        verbatim_threshold=args.verbatim_threshold,
        schema=schema,
    )

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(_build_report_lines(report)), encoding="utf-8")

    _print_report(report, quiet=args.quiet)

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
