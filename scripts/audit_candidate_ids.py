#!/usr/bin/env python3
"""Stage A Candidate ID の運用契約を匿名集計で監査する。

Exit codes:
    0: 契約違反なし
    1: 契約違反あり
    2: 入出力エラー
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

from agents.extractor.candidate_id_audit import (  # noqa: E402
    CANDIDATE_ARRAY_SPECS,
    audit_candidate_ids,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extraction JSONのCandidate ID契約を検証し、識別情報を含まない"
            "集計結果だけを出力します"
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="監査対象Extraction JSONファイルまたはディレクトリ",
    )
    parser.add_argument(
        "--normalized-input",
        required=True,
        help="走査順照合用normalized JSONファイルまたはディレクトリ",
    )
    parser.add_argument(
        "--comparison-input",
        help="決定性比較用の2回目のExtraction JSONファイルまたはディレクトリ",
    )
    parser.add_argument(
        "--report-output",
        help="匿名aggregate JSONの出力先（repo内はworkspace/dry_runs配下のみ可）",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="標準出力を抑制する（エラー終了時の要約は表示）",
    )
    return parser.parse_args()


def _collect_json_files(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(path.rglob("*.json"))
    return [path]


def _validate_normalized_blocks(blocks: Any) -> None:
    if not isinstance(blocks, list):
        raise ValueError("Normalized Storyのblocksが配列ではありません")
    for block in blocks:
        if not isinstance(block, dict):
            raise ValueError("Normalized StoryのBlockがobjectではありません")
        options = block.get("options", []) or []
        if not isinstance(options, list):
            raise ValueError("Normalized Storyのoptionsが配列ではありません")
        for option in options:
            if not isinstance(option, dict):
                raise ValueError("Normalized Storyのoptionがobjectではありません")
            _validate_normalized_blocks(option.get("blocks", []) or [])


def _validate_normalized_document(document: dict[str, Any]) -> None:
    episodes = document.get("episodes")
    if not isinstance(episodes, list):
        raise ValueError("Normalized Storyのepisodesが配列ではありません")
    for episode in episodes:
        if not isinstance(episode, dict):
            raise ValueError("Normalized StoryのEpisodeがobjectではありません")
        scenes = episode.get("scenes")
        if not isinstance(scenes, list):
            raise ValueError("Normalized Storyのscenesが配列ではありません")
        for scene in scenes:
            if not isinstance(scene, dict):
                raise ValueError("Normalized StoryのSceneがobjectではありません")
            _validate_normalized_blocks(scene.get("blocks"))


def _validate_extraction_document(document: dict[str, Any]) -> None:
    if not isinstance(document.get("extractionRun"), dict):
        raise ValueError("ExtractionのextractionRunがobjectではありません")
    for array_key in CANDIDATE_ARRAY_SPECS:
        if array_key in document and not isinstance(document[array_key], list):
            raise ValueError("ExtractionのCandidate配列が配列ではありません")


def _load_documents(path: Path, *, document_kind: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError("入力が存在しません")
    files = _collect_json_files(path)
    if not files:
        raise ValueError("JSON入力がありません")

    documents: list[dict[str, Any]] = []
    for file_path in files:
        try:
            value = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError("JSON入力を読み込めません") from exc
        if not isinstance(value, dict):
            raise ValueError("JSON documentがobjectではありません")
        if document_kind == "normalized":
            _validate_normalized_document(value)
        else:
            _validate_extraction_document(value)
        documents.append(value)
    return documents


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_report_output(path: Path, protected_inputs: list[Path]) -> None:
    lexical = path.absolute()
    resolved = path.resolve()
    project_root = _PROJECT_ROOT.resolve()
    dry_run_root = (project_root / "workspace" / "dry_runs").resolve()

    target_is_in_repo = _is_relative_to(lexical, project_root) or _is_relative_to(
        resolved, project_root
    )
    target_is_in_dry_run = _is_relative_to(lexical, dry_run_root) and _is_relative_to(
        resolved, dry_run_root
    )
    if target_is_in_repo and not target_is_in_dry_run:
        raise ValueError(
            "repo内のreport-outputはworkspace/dry_runs配下に指定してください"
        )

    for input_path in protected_inputs:
        protected = input_path.resolve()
        if protected.is_dir() and _is_relative_to(resolved, protected):
            raise ValueError("report-outputを入力ディレクトリ内には指定できません")
        if protected.is_file() and resolved == protected:
            raise ValueError("report-outputを入力ファイルと同じ場所には指定できません")

    if path.exists():
        raise ValueError("report-outputは既に存在します")


def _write_report(
    path: Path, report: dict[str, Any], protected_inputs: list[Path]
) -> None:
    _validate_report_output(path, protected_inputs)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as report_file:
        json.dump(report, report_file, ensure_ascii=False, indent=2)
        report_file.write("\n")


def main() -> int:
    args = parse_args()
    input_paths = [
        Path(args.input),
        Path(args.normalized_input),
        *([Path(args.comparison_input)] if args.comparison_input else []),
    ]
    try:
        extraction_documents = _load_documents(
            input_paths[0], document_kind="extraction"
        )
        normalized_documents = _load_documents(
            input_paths[1], document_kind="normalized"
        )
        comparison_documents = (
            _load_documents(input_paths[2], document_kind="extraction")
            if args.comparison_input
            else None
        )
        report = audit_candidate_ids(
            extraction_documents,
            normalized_documents,
            comparison_documents,
        )
        if args.report_output:
            _write_report(Path(args.report_output), report, input_paths)
    except ValueError as exc:
        print(
            f"[エラー] Candidate ID監査の入出力に失敗しました: {exc}",
            file=sys.stderr,
        )
        return 2
    except OSError:
        print(
            "[エラー] Candidate ID監査の入出力に失敗しました",
            file=sys.stderr,
        )
        return 2

    summary = (
        f"[Candidate ID audit] status={report['status']} "
        f"documents={report['documentCount']} "
        f"candidates={report['candidateCount']} "
        f"errors={report['errorCount']}"
    )
    if not args.quiet or report["status"] != "pass":
        print(summary)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
