#!/usr/bin/env python3
"""
Project Evidence Index Public IDs
Public Evidence Index候補に`publicEvidenceId`を生成・付与する
"Compatible projection"（案A）scriptである
（`feature/evidence-index-public-id-projection`、
`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md` §6/§12 Phase 2）。

**Compatible projectionのみを実装する**（既存の内部ID
`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`は一切削除しない、
`publicEvidenceId`を追加するだけ）。内部IDを完全に取り除く
"Public-safe projection"（案B、`evidence-index-public-id-public-safe-
projection`）は本scriptの対象外。

**重要な安全方針**:
- `--output`/`--mapping-output`/`--report`はいずれも`knowledge/evidence/`
  配下を指定できない（安全確認で拒否、exit code 2）。すべてworkspace
  配下の一時出力を想定する
- 本scriptの出力は**promotion対象ではない**（内部IDが残ったままの
  Compatible projectionのため）。`promote_evidence_index.py --execute`
  には使わないこと
- `promote_evidence_index.py`の実行、`knowledge/evidence/stories/`への
  実copyは本scriptの責務外であり、一切行わない
- `--input`ファイル自体は読み込みのみで変更しない（書き込み先は常に
  `--output`）

publicEvidenceId形式（`Evidence_Index_Public_ID_Policy.md` §6.4）:
    {publicEpisodeId}_{PREFIX}{sequence:04d}

採番方針（同 §6.6）:
- `--policy`で許可されたevidenceTypeのentryのみ、
  (publicEpisodeId, evidenceType) 単位で1始まりの連番を振る
  （`stage_direction`等policy対象外のtypeは採番対象に含めない）
- 連番は入力entriesの出現順（複数ファイルの場合はfile収集順→file内の
  entries順）に従う。そのため、同じ入力・同じprofileであれば再現可能だが、
  entryの並び順が変わればpublicEvidenceIdも変わりうる
- 既にpublicEvidenceIdを持つentryは、再生成した値と比較する。一致すれば
  そのまま採用、不一致ならblocking error（`--overwrite-public-ids`相当の
  上書きオプションは本PRでは実装しない）

Non-goals（本scriptで行わないこと。詳細は
`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md` §13参照）:
- 内部ID (`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`) の削除・
  改名（Public-safe projection、案B、将来PR）
- `knowledge/evidence/stories/`への実copy・commit
- `promote_evidence_index.py --execute`の実行
- rendererのEvidence page見出し・anchor・Summary evidenceRefsリンクの
  publicEvidenceId中心への切り替え

Usage:
    uv run python scripts/project_evidence_index_public_ids.py \\
        --input workspace/evidence_index_dry_runs/<run>/default/stories \\
        --output workspace/evidence_index_dry_runs/public_id_projection \\
        --mapping-output workspace/evidence_index_dry_runs/public_id_map.csv \\
        --report workspace/evidence_index_dry_runs/public_id_report.md \\
        --clean

Exit codes:
    0: projection成功（blocking issueなし）
    1: projection validation失敗（publicStoryId/publicEpisodeId欠落、
       既存publicEvidenceIdとの不一致、duplicate publicEvidenceId、
       projected出力のschema検証失敗、--strict指定時のpolicy対象外type等）
    2: --input/--schemaパスが見つからない、または--output/--mapping-output/
       --reportがknowledge/evidence/配下を指しているなどのconfig error
"""

from __future__ import annotations

import argparse
import csv
import json
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
    DEFAULT_SCHEMA_PATH,
    POLICIES,
    POLICY_PUBLIC_DEFAULT,
    _collect_yaml_paths,
    _load_yaml_documents,
)

# `Evidence_Index_Public_ID_Policy.md` §6.5 evidenceType prefix mapping。
EVIDENCE_TYPE_PREFIXES: dict[str, str] = {
    "dialogue": "DLG",
    "monologue": "MONO",
    "narration": "NAR",
    "choice": "CHO",
    "unknown": "UNK",
    "stage_direction": "STG",
    "speaker_label": "SPK",
    "scene": "SCN",
    "episode": "EP",
    "story": "STORY",
}

# knowledge/evidence配下は本scriptの出力先として一切許可しない
# (§安全方針。stories/以外のサブpathも念のため含めて拒否する)。
_KNOWLEDGE_EVIDENCE_DIR = (_PROJECT_ROOT / "knowledge" / "evidence").resolve()

MAPPING_FIELDNAMES = [
    "storyId",
    "publicStoryId",
    "episodeId",
    "publicEpisodeId",
    "evidenceId",
    "publicEvidenceId",
    "evidenceType",
    "sceneId",
    "blockId",
]


# ----------------------------------------------------------------
# Argument parser
# ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Public Evidence Index候補にpublicEvidenceIdを生成・付与する "
            "Compatible projection (内部IDは削除しない)。出力はworkspace "
            "配下のみを想定し、knowledge/evidence/配下への書き込みは拒否する"
        ),
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Evidence Index YAMLファイル、またはdirectory (直下の*.yaml/*.ymlを収集)",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help=(
            "projection結果を書き出すdirectory (workspace配下のみ。"
            "knowledge/evidence/配下は指定不可)"
        ),
    )
    parser.add_argument(
        "--mapping-output",
        required=True,
        help=(
            "内部ID<->公開IDのmapping CSVを書き出すファイルパス "
            "(workspace配下のみ。内部IDを含むためcommit禁止)"
        ),
    )
    parser.add_argument(
        "--report",
        required=True,
        help="projection結果をMarkdownで書き出すファイルパス (workspace配下のみ)",
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help=f"evidence_index.schema.jsonのパス (デフォルト: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--policy",
        choices=sorted(POLICIES),
        default=POLICY_PUBLIC_DEFAULT,
        help=(
            "publicEvidenceId採番対象のevidenceType policy "
            "(デフォルト: public-default。dialogue/monologue/narration/"
            "choice/unknownのみ採番、stage_direction等は採番対象外のまま"
            "entryとしては出力に残る)"
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "policy対象外のevidenceType (stage_direction等) を持つentryが"
            "入力に含まれている場合、blocking errorにする "
            "(既定では警告なしでpublicEvidenceIdを付与せず素通しする)"
        ),
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="--output出力先ディレクトリを書き込み前に削除する",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


def _is_under_knowledge_evidence(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    try:
        resolved.relative_to(_KNOWLEDGE_EVIDENCE_DIR)
        return True
    except ValueError:
        return False


# ----------------------------------------------------------------
# publicEvidenceId generation
# ----------------------------------------------------------------


def _build_public_evidence_id(
    public_episode_id: str, evidence_type: str, sequence: int
) -> str:
    prefix = EVIDENCE_TYPE_PREFIXES.get(evidence_type, "UNK")
    return f"{public_episode_id}_{prefix}{sequence:04d}"


def _check_missing_public_story_id(
    raw_documents: list[tuple[Path, dict[str, Any]]],
) -> tuple[list[str], list[str]]:
    """document (file) 単位でpublicStoryIdを持つentryが1件も無い場合を検出する。"""
    missing: list[str] = []
    issues: list[str] = []
    for path, raw in raw_documents:
        entries = raw.get("entries", []) or []
        has_public_story_id = any(entry.get("publicStoryId") for entry in entries)
        if not has_public_story_id:
            missing.append(str(path))
            issues.append(
                f"{path}: publicStoryIdを持つentryがありません (document全体で欠落)"
            )
    return missing, issues


def _flatten_entries(
    raw_documents: list[tuple[Path, dict[str, Any]]],
) -> list[tuple[Path, dict[str, Any]]]:
    flat: list[tuple[Path, dict[str, Any]]] = []
    for path, raw in raw_documents:
        for entry in raw.get("entries", []) or []:
            flat.append((path, entry))
    return flat


def _check_missing_public_episode_id(
    flat_entries: list[tuple[Path, dict[str, Any]]],
) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    issues: list[str] = []
    for path, entry in flat_entries:
        if not entry.get("publicEpisodeId"):
            label = f"{path}: evidenceId={entry.get('evidenceId')!r}"
            missing.append(label)
            issues.append(f"{label}: publicEpisodeIdが欠落しています")
    return missing, issues


def _assign_public_evidence_ids(
    flat_entries: list[tuple[Path, dict[str, Any]]],
    *,
    policy_types: frozenset[str],
    strict: bool,
) -> dict[str, Any]:
    """policy許可typeのentryにpublicEvidenceIdを採番・検証する。

    publicEpisodeIdが欠落しているentryは (別途blocking issueとして記録
    済みのため) 採番対象から除外する。
    """
    strict_issues: list[str] = []
    conflict_issues: list[str] = []
    counters: dict[tuple[str, str], int] = {}
    generated_count = 0
    existing_matched_count = 0
    out_of_policy_count = 0

    for path, entry in flat_entries:
        evidence_type = entry.get("evidenceType")
        public_episode_id = entry.get("publicEpisodeId")

        if evidence_type not in policy_types:
            out_of_policy_count += 1
            if strict:
                strict_issues.append(
                    f"{path}: evidenceId={entry.get('evidenceId')!r}: evidenceType "
                    f"'{evidence_type}' はpolicy '{'/'.join(sorted(policy_types))}' "
                    "の対象外です (--strict)"
                )
            continue

        if not public_episode_id:
            continue

        key = (public_episode_id, evidence_type)
        counters[key] = counters.get(key, 0) + 1
        expected = _build_public_evidence_id(
            public_episode_id, evidence_type, counters[key]
        )

        existing = entry.get("publicEvidenceId")
        if existing:
            if existing == expected:
                existing_matched_count += 1
            else:
                conflict_issues.append(
                    f"{path}: evidenceId={entry.get('evidenceId')!r}: "
                    f"既存publicEvidenceId '{existing}' が生成結果 "
                    f"'{expected}' と一致しません"
                )
        else:
            entry["publicEvidenceId"] = expected
            generated_count += 1

    return {
        "issues": conflict_issues + strict_issues,
        "conflictCount": len(conflict_issues),
        "generatedCount": generated_count,
        "existingMatchedCount": existing_matched_count,
        "outOfPolicyCount": out_of_policy_count,
    }


def _check_duplicate_public_evidence_ids(
    flat_entries: list[tuple[Path, dict[str, Any]]],
) -> tuple[int, list[str]]:
    seen: dict[str, int] = {}
    for _, entry in flat_entries:
        public_evidence_id = entry.get("publicEvidenceId")
        if public_evidence_id:
            seen[public_evidence_id] = seen.get(public_evidence_id, 0) + 1
    duplicates = sorted(pid for pid, count in seen.items() if count > 1)
    issues = [f"publicEvidenceId '{pid}' が重複しています" for pid in duplicates]
    return len(duplicates), issues


def _validate_projected_documents(
    raw_documents: list[tuple[Path, dict[str, Any]]], schema: dict[str, Any]
) -> list[str]:
    issues: list[str] = []
    for path, raw in raw_documents:
        errors = sorted(
            Draft7Validator(schema).iter_errors(raw), key=lambda e: list(e.path)
        )
        issues.extend(
            f"{path} (projected): {list(e.path)}: {e.message}" for e in errors
        )
    return issues


def _project_documents(
    raw_documents: list[tuple[Path, dict[str, Any]]],
    schema: dict[str, Any],
    *,
    policy_types: frozenset[str],
    strict: bool,
) -> dict[str, Any]:
    missing_public_story_id, story_id_issues = _check_missing_public_story_id(
        raw_documents
    )

    flat_entries = _flatten_entries(raw_documents)
    missing_public_episode_id, episode_id_issues = _check_missing_public_episode_id(
        flat_entries
    )

    entries_by_type: dict[str, int] = {}
    story_ids: set[str] = set()
    for _, entry in flat_entries:
        evidence_type = entry.get("evidenceType")
        entries_by_type[evidence_type] = entries_by_type.get(evidence_type, 0) + 1
        if entry.get("storyId"):
            story_ids.add(entry["storyId"])

    assignment = _assign_public_evidence_ids(
        flat_entries, policy_types=policy_types, strict=strict
    )

    duplicate_count, duplicate_issues = _check_duplicate_public_evidence_ids(
        flat_entries
    )

    schema_issues = _validate_projected_documents(raw_documents, schema)

    all_issues = (
        story_id_issues
        + episode_id_issues
        + assignment["issues"]
        + duplicate_issues
        + schema_issues
    )

    generated_count = assignment["generatedCount"]
    existing_matched_count = assignment["existingMatchedCount"]

    return {
        "fileCount": len(raw_documents),
        "storyCount": len(story_ids),
        "entryCount": len(flat_entries),
        "entriesByType": entries_by_type,
        "projectedEntryCount": generated_count + existing_matched_count,
        "generatedCount": generated_count,
        "existingMatchedCount": existing_matched_count,
        "missingPublicStoryIdCount": len(missing_public_story_id),
        "missingPublicStoryId": missing_public_story_id,
        "missingPublicEpisodeIdCount": len(missing_public_episode_id),
        "missingPublicEpisodeId": missing_public_episode_id,
        "conflictCount": assignment["conflictCount"],
        "outOfPolicyCount": assignment["outOfPolicyCount"],
        "duplicateCount": duplicate_count,
        "schemaIssueCount": len(schema_issues),
        "issues": all_issues,
        "passed": not all_issues,
    }


# ----------------------------------------------------------------
# Output writing (--output / --mapping-output)
# ----------------------------------------------------------------


def _write_projected_documents(
    output_dir: Path, raw_documents: list[tuple[Path, dict[str, Any]]], *, clean: bool
) -> list[str]:
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for path, raw in raw_documents:
        target = output_dir / path.name
        with open(target, "w", encoding="utf-8") as f:
            yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)
        written.append(str(target))
    return written


def _write_mapping_csv(
    mapping_output_path: Path, raw_documents: list[tuple[Path, dict[str, Any]]]
) -> None:
    mapping_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(mapping_output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MAPPING_FIELDNAMES)
        writer.writeheader()
        for _, raw in raw_documents:
            for entry in raw.get("entries", []) or []:
                writer.writerow(
                    {key: entry.get(key, "") or "" for key in MAPPING_FIELDNAMES}
                )


# ----------------------------------------------------------------
# Report building
# ----------------------------------------------------------------


def _report_summary_lines(report: dict[str, Any]) -> list[str]:
    return [
        "# Evidence Index Public ID Projection Report",
        "",
        f"- Input: {report['input']}",
        f"- Output: {report['output']}",
        f"- Mapping output: {report['mappingOutput']}",
        f"- Policy: {report['policy']}",
        f"- File count: {report['fileCount']}",
        f"- Story count: {report['storyCount']}",
        f"- Entry count: {report['entryCount']}",
        "",
    ]


def _report_entries_by_type_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## Entries by evidenceType", ""]
    if report["entriesByType"]:
        for evidence_type, count in sorted(report["entriesByType"].items()):
            lines.append(f"- {evidence_type}: {count}")
    else:
        lines.append("- (none)")
    lines.append("")
    return lines


def _report_projection_result_lines(report: dict[str, Any]) -> list[str]:
    return [
        "## Projection Result",
        "",
        f"- Projected entry count: {report['projectedEntryCount']}",
        "- Existing publicEvidenceId count (matched): "
        f"{report['existingMatchedCount']}",
        f"- Generated publicEvidenceId count: {report['generatedCount']}",
        f"- Missing publicStoryId count: {report['missingPublicStoryIdCount']}",
        f"- Missing publicEpisodeId count: {report['missingPublicEpisodeIdCount']}",
        f"- Conflicts count: {report['conflictCount']}",
        f"- Duplicate publicEvidenceId count: {report['duplicateCount']}",
        f"- Out-of-policy entry count: {report['outOfPolicyCount']}",
        "",
    ]


def _report_issues_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## Issues", ""]
    if report["issues"]:
        for issue in report["issues"]:
            lines.append(f"- {issue}")
    else:
        lines.append("- (none)")
    lines.append("")
    return lines


def _build_report_lines(report: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    lines.extend(_report_summary_lines(report))
    lines.extend(_report_entries_by_type_lines(report))
    lines.extend(_report_projection_result_lines(report))
    lines.extend(_report_issues_lines(report))
    lines.append("## Final Decision")
    lines.append("")
    lines.append(f"- {'PASS' if report['passed'] else 'FAIL'}")
    lines.append("")
    lines.append("## Note")
    lines.append("")
    lines.append(
        "- This is a compatible projection only (Option A, "
        "Evidence_Index_Public_ID_Policy.md §6.2). Internal IDs "
        "(evidenceId/storyId/episodeId/sceneId/blockId) remain unchanged "
        "in the output."
    )
    lines.append(
        "- The output is NOT promotion-ready: it must not be used with "
        "promote_evidence_index.py --execute, and must not be committed to "
        "knowledge/evidence/stories/."
    )
    lines.append(
        "- The mapping output contains internal IDs alongside public IDs and "
        "must never be committed (Internal Review Evidence Packet candidate, "
        "not yet implemented)."
    )
    lines.append("")
    return lines


def _print_summary(report: dict[str, Any], *, quiet: bool) -> None:
    if quiet:
        return
    print(
        f"[projection] {report['fileCount']} ファイル、{report['entryCount']} entries "
        f"(policy={report['policy']})"
    )
    print(
        f"[projection] projected={report['projectedEntryCount']} "
        f"(generated={report['generatedCount']}, "
        f"existing_matched={report['existingMatchedCount']})"
    )
    if report["issues"]:
        print(f"[エラー] {len(report['issues'])}件のissueがあります:", file=sys.stderr)
        for issue in report["issues"]:
            print(f"  - {issue}", file=sys.stderr)
    print(f"[projection] 結果: {'PASS' if report['passed'] else 'FAIL'}")


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------


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

    output_dir = Path(args.output)
    mapping_output_path = Path(args.mapping_output)
    report_path = Path(args.report)
    for label, path in (
        ("--output", output_dir),
        ("--mapping-output", mapping_output_path),
        ("--report", report_path),
    ):
        if _is_under_knowledge_evidence(path):
            print(
                f"[エラー] {label}にknowledge/evidence配下のpathは"
                f"指定できません: {path}",
                file=sys.stderr,
            )
            return 2

    raw_documents, schema_errors = _load_yaml_documents(yaml_paths, schema)
    if schema_errors:
        print("[エラー] 入力のschema検証に失敗しました:", file=sys.stderr)
        for issue in schema_errors:
            print(f"  - {issue}", file=sys.stderr)
        return 2

    policy_types = POLICIES[args.policy]
    result = _project_documents(
        raw_documents, schema, policy_types=policy_types, strict=args.strict
    )

    written_paths = _write_projected_documents(
        output_dir, raw_documents, clean=args.clean
    )
    _write_mapping_csv(mapping_output_path, raw_documents)

    report = {
        "input": str(input_path),
        "output": str(output_dir),
        "mappingOutput": str(mapping_output_path),
        "policy": args.policy,
        **result,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(_build_report_lines(report)), encoding="utf-8")

    if not args.quiet:
        for path in written_paths:
            print(f"[projection] wrote {path}")

    _print_summary(report, quiet=args.quiet)

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
