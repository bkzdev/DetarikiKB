#!/usr/bin/env python3
"""
Generate Story Summaries
Normalized Story JSON（`schemas/story.schema.json`）から、Episode Summary
draft（`schemas/story_summary.schema.json`準拠）をworkspace限定で生成する
CLI（`docs/architecture/06_AI/Story_Summary_Generation_Plan.md` §6・§9
`summary-generation-prompt-implementation`）。

ユーザーが2026-07-13にsummarizer系のLLM provider/prompt実装を明示的に
解禁したことを受けて実装する（`AI_CONTEXT.md` §4。`agents/extractor/`は
引き続き未解禁のまま）。

**重要**:
- 本scriptの実行には実Ollama（またはOllama互換API）が必要である。
  **本PR作業中は実行しない**（テストはすべて合成fixture + fake providerで
  検証する。実Ollama呼び出し・実データSummary生成・実データでのCLI実行は
  いずれもNon-goals）
- Story Summary合成（Episode Summary群 -> Story Summary）はまだ実装して
  いないため、出力draftの`storySummary`は常に`null`のままである
  （次PR`summary-generation-story-synthesis`のスコープ）
- `--output`/`--report`はworkspace配下のみを想定する。`knowledge/`配下は
  安全策として拒否する（exit code 2、`docs/runbooks/AI_PR_Playbook.md` §7
  「実データ・生成物をcommitしない」の運用を踏襲）
- 長文episodeのchunk分割2段階要約（Plan §6.4）は本PRでは未実装。
  `--max-input-characters`を超えるepisodeはissueを立てて生成をskipする
  安全弁のみ実装している

hallucination対策の後処理（`agents/summarizer/generator.py`が実装、Plan
§6.3）は検出結果を自動rejectしない。draftは常に`generationStatus: "draft"`
のまま出力され、issueがあるepisodeはこのreport（Markdown）と出力YAMLの
`notes`欄に記録される。

Usage:
    uv run python scripts/generate_story_summaries.py \\
        --input workspace/dry_runs/summary_generation/normalized \\
        --output workspace/summary_drafts/ \\
        --model llama3 \\
        --report workspace/summary_drafts/report.md \\
        --clean

Exit codes:
    0: 生成成功（hallucination対策issueの有無に関わらず、draftが
       schema検証を通過していればPASSとする）
    1: 生成したdraftのschema検証に失敗した（想定外のバグ）
    2: --input/--schemaパスが見つからない、入力の読み込みにすべて失敗した、
       または--output/--reportがknowledge/配下を指しているなどのconfig
       error
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

import yaml
from jsonschema import Draft7Validator

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.summarizer import (  # noqa: E402
    DEFAULT_MAX_INPUT_CHARACTERS,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_VERBATIM_THRESHOLD,
    OllamaProvider,
    StorySummaryGenerationResult,
    SummaryLLMProvider,
    generate_story_summary_draft,
)

DEFAULT_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "story_summary.schema.json"

# knowledge/配下は本scriptの出力先(--output/--report)として一切許可しない
# (workspace限定、docs/runbooks/AI_PR_Playbook.md §7方針)。
_FORBIDDEN_OUTPUT_DIR = (_PROJECT_ROOT / "knowledge").resolve()

ProviderFactory = Callable[[argparse.Namespace], SummaryLLMProvider]


# ----------------------------------------------------------------
# Argument parser
# ----------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalized Story JSONからEpisode Summary draftをworkspace限定で"
            "生成する (実Ollama呼び出しを伴う。knowledge/配下への出力は拒否)"
        ),
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Normalized Story JSONファイル、またはdirectory (直下の*.jsonを収集)",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help=(
            "draft YAML出力先directory (workspace配下のみ許可。"
            "knowledge/配下は拒否、exit code 2)"
        ),
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Ollamaのmodel名 (必須)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Ollama host (省略時はOLLAMA_HOST環境変数、無ければ既定値を使う)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"LLM呼び出しのtimeout秒数 (デフォルト: {DEFAULT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--verbatim-threshold",
        type=int,
        default=DEFAULT_VERBATIM_THRESHOLD,
        help=(
            "長文verbatim引用検出の閾値文字数 "
            f"(デフォルト: {DEFAULT_VERBATIM_THRESHOLD})"
        ),
    )
    parser.add_argument(
        "--max-input-characters",
        type=int,
        default=DEFAULT_MAX_INPUT_CHARACTERS,
        help=(
            "1 episodeの入力テキスト上限文字数 "
            f"(デフォルト: {DEFAULT_MAX_INPUT_CHARACTERS}。超過時はchunk分割"
            "せずissueを立てて生成をskipする、Plan §6.4の安全弁)"
        ),
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help=f"story_summary.schema.jsonのパス (デフォルト: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--report",
        required=True,
        help=(
            "生成結果をMarkdownで書き出すファイルパス (workspace配下のみ"
            "許可。knowledge/配下は拒否、exit code 2)"
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
    return parser.parse_args(argv)


def _default_provider_factory(args: argparse.Namespace) -> SummaryLLMProvider:
    return OllamaProvider(
        model=args.model, host=args.host, timeout_seconds=args.timeout
    )


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
# Input collection
# ----------------------------------------------------------------


def _collect_json_paths(input_path: Path) -> list[Path] | None:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.glob("*.json"))
    return None


def _load_json_documents(
    paths: list[Path],
) -> tuple[list[dict[str, Any]], list[str]]:
    documents: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                documents.append(json.load(f))
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"{path}: 読み込み失敗: {e}")
    return documents, errors


# ----------------------------------------------------------------
# Report building
# ----------------------------------------------------------------


def _build_story_report(result: StorySummaryGenerationResult) -> dict[str, Any]:
    episodes_generated = sum(1 for r in result.episode_results if not r.skipped)
    episodes_skipped = sum(1 for r in result.episode_results if r.skipped)

    issue_code_counts: dict[str, int] = {}
    episodes_with_issues: list[dict[str, Any]] = []
    for episode_result in result.episode_results:
        for issue in episode_result.issues:
            issue_code_counts[issue.code] = issue_code_counts.get(issue.code, 0) + 1
        if episode_result.issues:
            episodes_with_issues.append(
                {
                    "episodeId": episode_result.episode_id,
                    "skipped": episode_result.skipped,
                    "issues": [
                        {
                            "code": issue.code,
                            "message": issue.message,
                            "blocking": issue.blocking,
                        }
                        for issue in episode_result.issues
                    ],
                }
            )

    return {
        "storyId": result.story_id,
        "episodeCount": len(result.episode_results),
        "episodesGenerated": episodes_generated,
        "episodesSkipped": episodes_skipped,
        "issueCodeCounts": issue_code_counts,
        "episodesWithIssues": episodes_with_issues,
    }


def _build_report_markdown(
    story_reports: list[dict[str, Any]],
    *,
    input_count: int,
    written_count: int,
    schema_valid: bool,
    schema_issues: list[str],
) -> str:
    lines = [
        "# Story Summary Generation Report",
        "",
        f"- Input files: {input_count}",
        f"- Story count: {len(story_reports)}",
        f"- Draft files written: {written_count}",
        "",
    ]

    for report in story_reports:
        lines.append(f"## {report['storyId']}")
        lines.append("")
        lines.append(f"- Episode count: {report['episodeCount']}")
        lines.append(f"- Episodes generated: {report['episodesGenerated']}")
        lines.append(f"- Episodes skipped: {report['episodesSkipped']}")
        lines.append("")
        if report["issueCodeCounts"]:
            lines.append("### Issue code counts")
            lines.append("")
            for code, count in sorted(report["issueCodeCounts"].items()):
                lines.append(f"- {code}: {count}")
            lines.append("")
        if report["episodesWithIssues"]:
            lines.append("### Episodes with issues")
            lines.append("")
            for episode in report["episodesWithIssues"]:
                lines.append(
                    f"- {episode['episodeId']} (skipped={episode['skipped']}):"
                )
                for issue in episode["issues"]:
                    lines.append(
                        f"  - [{issue['code']}] {issue['message']} "
                        f"(blocking={issue['blocking']})"
                    )
            lines.append("")

    lines.append("## Validation")
    lines.append("")
    lines.append(f"schemaValid: {'true' if schema_valid else 'false'}")
    if schema_issues:
        for issue in schema_issues:
            lines.append(f"- {issue}")
    lines.append("")

    lines.append("## Note")
    lines.append("")
    lines.append(
        "- hallucination対策issue (unknown-evidence-ref/forbidden-text-"
        "pattern/verbatim-quote等) は自動rejectされていません。draftは"
        "generationStatus: draftのまま人間レビュー待ちです "
        "(Story_Summary_Generation_Plan.md §6.3)。"
    )
    lines.append(
        "- storySummary (Story全体の要約) はこのCLIでは生成していません "
        "(次PR summary-generation-story-synthesisのスコープ、常にnull)。"
    )
    lines.append("")
    return "\n".join(lines)


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------


def _prepare_inputs(
    args: argparse.Namespace,
) -> tuple[dict[str, Any] | None, int | None]:
    """schema読み込み・`--input`パス収集・出力先安全確認・Normalized Story
    JSONの読み込みをまとめて行う。戻り値: (context, exit_code)。"""
    schema_path = Path(args.schema)
    if not schema_path.exists():
        print(
            f"[エラー] schemaファイルが見つかりません: {schema_path}", file=sys.stderr
        )
        return None, 2
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    input_path = Path(args.input)
    json_paths = _collect_json_paths(input_path)
    if json_paths is None:
        print(f"[エラー] --inputパスが見つかりません: {input_path}", file=sys.stderr)
        return None, 2

    output_dir = Path(args.output)
    report_path = Path(args.report)
    for label, path in (("--output", output_dir), ("--report", report_path)):
        if _is_under_forbidden_dir(path):
            print(
                f"[エラー] {label}にknowledge/配下のpathは指定できません: {path}",
                file=sys.stderr,
            )
            return None, 2

    documents, load_errors = _load_json_documents(json_paths)
    if load_errors and not documents:
        print(
            "[エラー] Normalized Story JSONの読み込みにすべて失敗しました:",
            file=sys.stderr,
        )
        for error in load_errors:
            print(f"  - {error}", file=sys.stderr)
        return None, 2
    if load_errors and not args.quiet:
        for error in load_errors:
            print(f"[警告] {error}", file=sys.stderr)

    return {
        "schema": schema,
        "output_dir": output_dir,
        "report_path": report_path,
        "documents": documents,
    }, None


def _write_drafts(
    results: list[StorySummaryGenerationResult],
    *,
    schema: dict[str, Any],
    output_dir: Path,
    clean: bool,
) -> tuple[list[str], list[str]]:
    """各storyのdraft documentをschema検証しつつ`--output`配下へ書き出す。

    戻り値: (書き出したファイルpath一覧, schema検証エラー一覧)。
    schema検証に失敗したdocumentは書き出さない (report側にエラーを記録)。
    """
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    schema_issues: list[str] = []
    written_paths: list[str] = []
    for result in results:
        document_dict = result.to_document_dict()
        errors = sorted(
            Draft7Validator(schema).iter_errors(document_dict),
            key=lambda e: list(e.path),
        )
        if errors:
            schema_issues.extend(
                f"{result.story_id}: {list(e.path)}: {e.message}" for e in errors
            )
            continue
        out_path = output_dir / f"{result.story_id}.yaml"
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(document_dict, f, allow_unicode=True, sort_keys=False)
        written_paths.append(str(out_path))

    return written_paths, schema_issues


def main(
    argv: list[str] | None = None,
    *,
    provider_factory: ProviderFactory | None = None,
) -> int:
    args = parse_args(argv)

    context, error_code = _prepare_inputs(args)
    if error_code is not None:
        return error_code

    schema = context["schema"]
    output_dir = context["output_dir"]
    report_path = context["report_path"]
    documents = context["documents"]

    provider = (provider_factory or _default_provider_factory)(args)

    results = [
        generate_story_summary_draft(
            document,
            provider=provider,
            max_input_characters=args.max_input_characters,
            verbatim_threshold=args.verbatim_threshold,
        )
        for document in documents
    ]

    written_paths, schema_issues = _write_drafts(
        results, schema=schema, output_dir=output_dir, clean=args.clean
    )

    story_reports = [_build_story_report(result) for result in results]
    report_markdown = _build_report_markdown(
        story_reports,
        input_count=len(documents),
        written_count=len(written_paths),
        schema_valid=not schema_issues,
        schema_issues=schema_issues,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_markdown, encoding="utf-8")

    if not args.quiet:
        print(
            f"[generate] {len(documents)} story documentを処理し、"
            f"{len(written_paths)} draftを書き出しました"
        )
        print(f"[generate] 出力先: {output_dir}")
        print(f"[generate] report: {report_path}")
        if schema_issues:
            print(
                f"[エラー] {len(schema_issues)}件のschema検証エラーがあります",
                file=sys.stderr,
            )

    return 1 if schema_issues else 0


if __name__ == "__main__":
    sys.exit(main())
