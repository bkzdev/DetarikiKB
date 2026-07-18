#!/usr/bin/env python3
"""
Generate Story Summaries
Normalized Story JSON（`schemas/story.schema.json`）から、Episode Summary
draft、および（既定で）Episode Summary群から合成したStory Summaryを含む
draft（`schemas/story_summary.schema.json`準拠）をworkspace限定で生成する
CLI（`docs/architecture/06_AI/Story_Summary_Generation_Plan.md` §6・§9・§11
`summary-generation-prompt-implementation` / `summary-generation-story-
synthesis`）。

ユーザーが2026-07-13にsummarizer系のLLM provider/prompt実装を明示的に
解禁したことを受けて実装する（`AI_CONTEXT.md` §4。`agents/extractor/`は
引き続き未解禁のまま）。

**重要**:
- 本scriptの実行には実Ollama（またはOllama互換API）が必要である。
  **本PR作業中は実行しない**（テストはすべて合成fixture + fake providerで
  検証する。実Ollama呼び出し・実データSummary生成・実データでのCLI実行は
  いずれもNon-goals）
- Story Summary合成（Episode Summary群 -> Story Summary、Plan §11）は
  既定で有効。生成済みEpisode Summary群のtext（episodeNumber順）を再度
  LLMに要約させ、story-level evidenceRefsはepisode-level evidenceRefsの
  重複排除unionとして機械的に決める。`--no-story-synthesis`で無効化する
  と、出力draftの`storySummary`は常に`null`のままになる（従来動作）
- `--output`/`--report`はworkspace配下のみを想定する。`knowledge/`配下は
  安全策として拒否する（exit code 2、`docs/runbooks/AI_PR_Playbook.md` §7
  「実データ・生成物をcommitしない」の運用を踏襲）
- 長文episode/story合成のchunk分割2段階要約（Plan §6.4）は本PRでは未実装。
  `--max-input-characters`を超える場合はissueを立てて該当する生成
  （episode生成、またはstory合成）をskipする安全弁のみ実装している
- **storyId単位のグルーピング**: Phase 1 parserは1 episode 1ファイルの
  ため、複数episodeを持つstoryは必ず複数のNormalized Story JSONファイルに
  分かれる。`--input`で読み込んだdocumentはstoryId単位でグルーピングし、
  同一storyIdのdocument群の`episodes`配列をマージした上で1 story = 1
  draftとして`generate_story_summary_draft`へ渡す（`summary-generation-
  poc`のPoC実施中に発見されたバグの修正、`summary-generation-multi-
  episode-grouping`）。マージ後のepisode順序は各episodeの`episodeNumber`
  昇順、episodeNumberが無いepisodeはepisodeIdの辞書順にfallbackする
  （安定ソート）。同一storyIdのdocument間で`metadata.publicStoryId`が
  矛盾する場合はそのstoryをblocking errorとして扱い（該当storyのdraftは
  書き出さない、exit code 1）、reportに記録する。グルーピング後も万一
  同一出力ファイルパスへ2回書き込みが発生した場合も同様にblocking error
  とし、黙って上書きしない
- **story-summary-v2 / episode-summary-v3 / `--refine`
  (`summary-generation-quality-v2`、2026-07-18ユーザー承認済み)**: Story
  Summary合成の既定方式を、Episode Summary群の再要約(v1)から全episode本文の
  直接入力(v2)へ変更した。全episode本文の概算トークン数が
  `--story-synthesis-max-context-tokens` (既定
  `DEFAULT_MAX_CONTEXT_TOKENS`) を超える場合はv1方式へ自動フォールバック
  する(失敗にしない、reportに記録)。episode要約promptは
  `episode-summary-v3`(主語明確化・登場人物リスト注入・本文中evidence ID
  参照禁止)。`--refine`(既定OFF)で、生成済みの各summaryへ同モデルでの
  自己推敲パスを1周追加できる。詳細は`agents/summarizer/prompt.py`・
  `generator.py`のmodule docstring参照
- **episodeNumberのrenumber**: Phase 1 parserは1ファイル1 episodeで、
  各episodeの`episodeNumber`を常に`1`として出力する。そのため上記の
  storyId単位マージ後、複数episodeを持つstoryでは`episodeNumber`が
  全episode共通で`1`のまま重複してしまう（`summary-generation-poc`の
  PoC実施中に発見された2件目のバグの修正、`summary-generation-episode-
  renumbering`）。マージ・安定ソート後のepisodeNumber列が一意な昇順に
  なっていない場合（重複・None混在を含む）は、ソート済み順に1..nで
  renumberする。既に一意な昇順（manifest由来の飛び番を含む）の場合は
  renumberせずそのまま維持する。詳細は`_merge_story_documents`の
  docstring参照

hallucination対策の後処理（`agents/summarizer/generator.py`が実装、Plan
§6.3・§11）は検出結果を自動rejectしない。draftは常に`generationStatus:
"draft"`のまま出力され、issueがあるepisode・story合成issueはこのreport
（Markdown）と出力YAMLの`notes`欄に記録される。story合成では、入力が
既にsafeなepisode summaryであるためverbatim引用検出は行わない（Plan
§11）。

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
    1: 生成したdraftのschema検証に失敗した（想定外のバグ）、同一storyIdの
       document間でmetadata.publicStoryIdが矛盾した、または（想定外の
       バグとして）グルーピング後に同一出力ファイルパスへ2回書き込みが
       発生した
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
    DEFAULT_MAX_CONTEXT_TOKENS,
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
        "--no-story-synthesis",
        action="store_true",
        help=(
            "Story Summary合成 (Episode Summary群からのLLM再要約、Plan §11) "
            "を行わない (既定では合成を行い、storySummaryを埋める)"
        ),
    )
    parser.add_argument(
        "--story-synthesis-max-context-tokens",
        type=int,
        default=DEFAULT_MAX_CONTEXT_TOKENS,
        help=(
            "Story Summary合成v2 (全文直接入力方式) のcontextサイズガード。"
            "全episode本文の概算トークン数がこの値を超える場合、"
            "story-summary-v1方式 (Episode Summary群の再要約) へ"
            f"フォールバックする (デフォルト: {DEFAULT_MAX_CONTEXT_TOKENS}。"
            "`summary-generation-quality-v2`)"
        ),
    )
    parser.add_argument(
        "--refine",
        action="store_true",
        help=(
            "生成した各summary (episode/story両方) に対し、同モデルで"
            "自己推敲パスを1周実行する (既定OFF。`summary-generation-"
            "quality-v2`)"
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
# storyId単位のグルーピング
#
# Phase 1 parserは1 episode 1ファイルのため、複数episodeを持つstoryは
# 必ず複数のNormalized Story JSONファイルに分かれる。`generate_story_
# summary_draft`は「1 document = 1 story」を前提とするため、CLI層で
# 同一storyIdのdocumentをまとめ、episodes配列をマージしてから渡す
# (`summary-generation-multi-episode-grouping`で修正したPoC発見バグ)。
# ----------------------------------------------------------------


def _episode_sort_key(episode: dict[str, Any]) -> tuple[int, int, str]:
    """マージ後のepisode順序を決めるsort key。

    `episodeNumber`があればそれを昇順の主キーとする (tier 0)。
    `episodeNumber`が無い/不正な型のepisodeはtier 1へ回し、`episodeId`の
    辞書順で安定ソートする (fallback)。tierをまたいだ混在時はtier 0が
    常に先に来る。
    """
    number = episode.get("episodeNumber")
    if isinstance(number, int) and not isinstance(number, bool):
        return (0, number, "")
    return (1, 0, str(episode.get("episodeId") or ""))


def _check_metadata_conflict(
    story_id: str | None, docs_for_story: list[dict[str, Any]]
) -> str | None:
    """同一storyIdのdocument間で、draft組み立てに使うmetadata値
    (`metadata.publicStoryId`) が矛盾していないか確認する。

    矛盾が無ければNoneを返す。複数の異なる非nullの値が見つかった場合の
    みblockingな矛盾として扱う (一部のdocumentにpublicStoryIdが未設定な
    だけのケースは矛盾としない)。
    """
    values: set[str] = set()
    for doc in docs_for_story:
        public_story_id = (doc.get("metadata") or {}).get("publicStoryId")
        if public_story_id is not None:
            values.add(str(public_story_id))
    if len(values) > 1:
        joined = ", ".join(sorted(values))
        return (
            f"storyId={story_id}: 複数のNormalized Story JSONファイル間で"
            f"metadata.publicStoryIdが矛盾しています ({joined})"
        )
    return None


def _is_unique_ascending_episode_numbers(episodes: list[dict[str, Any]]) -> bool:
    """`episodes`(`_episode_sort_key`でソート済み前提) の`episodeNumber`列が、
    重複・None混在の無い一意な昇順になっているか判定する。

    `scripts/check_public_episode_ids.py`の「内部episodeIdの出現順を
    1始まりのepisodeOrderとする」episodeOrder導出ルールと同じ意味論を
    採用する: ここでは「renumberが必要かどうか」の判定のみを行い、既に
    一意な昇順であれば1始まりでなくとも (manifest由来の飛び番、例:
    2, 5, 9) そのまま維持する (正しいmetadataを上書きしないため)。
    """
    numbers: list[int] = []
    for episode in episodes:
        number = episode.get("episodeNumber")
        if not isinstance(number, int) or isinstance(number, bool):
            return False
        numbers.append(number)
    return all(a < b for a, b in zip(numbers, numbers[1:], strict=False))


def _renumber_episodes(episodes: list[dict[str, Any]]) -> None:
    """`episodes`(ソート済み) の`episodeNumber`を、ソート済み順に1..nで
    振り直す (in-place)。"""
    for index, episode in enumerate(episodes, start=1):
        episode["episodeNumber"] = index


def _merge_story_documents(
    docs_for_story: list[dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    """同一storyIdのdocument群を1 story documentへマージする。

    先頭documentを基準に、`episodes`配列のみを全document分連結して
    `_episode_sort_key`で安定ソートしたものへ置き換える (それ以外の
    document-levelフィールドは`generate_story_summary_draft`が
    `storyId`/`metadata.publicStoryId`/`episodes`のみを参照するため、
    先頭documentの値をそのまま使えばよい)。

    Phase 1 parserは1ファイル1 episodeで、各episodeの`episodeNumber`を
    常に`1`として出力する。そのため複数episodeを持つstoryをマージすると、
    マージ後のepisodes全体で`episodeNumber`が`1`のまま重複する
    (`summary-generation-poc`のPoC実施中に発見された2件目のバグ、
    `summary-generation-episode-renumbering`で修正)。

    マージ・安定ソート後、episodes全体の`episodeNumber`列が一意な昇順に
    なっていない場合 (重複・None混在を含む、
    `_is_unique_ascending_episode_numbers`参照) は、ソート済み順に1..nで
    renumberする。このrenumberルールは、`scripts/check_public_episode_ids.py`
    の「内部episodeIdの出現順を1始まりのepisodeOrderとする」episodeOrder
    導出ルールと同じ意味論である。episodeNumber列が既に一意な昇順
    (例: manifest由来で2, 5, 9等の飛び番) の場合はrenumberせずそのまま
    維持する (正しいmetadataを上書きしないため)。

    戻り値: (マージ済みdocument, renumberが発生したかどうか)。
    """
    merged = dict(docs_for_story[0])
    merged_episodes: list[dict[str, Any]] = []
    for doc in docs_for_story:
        merged_episodes.extend(doc.get("episodes", []) or [])
    merged_episodes.sort(key=_episode_sort_key)

    renumbered = False
    if not _is_unique_ascending_episode_numbers(merged_episodes):
        _renumber_episodes(merged_episodes)
        renumbered = True

    merged["episodes"] = merged_episodes
    return merged, renumbered


def _group_documents_by_story_id(
    documents: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str]]:
    """documentをstoryId単位でグルーピングし、episodes配列をマージする。

    戻り値: (マージ済みdocument一覧, metadata矛盾一覧, episodeNumberを
    renumberしたstoryId一覧)。マージ済みdocument一覧はグルーピング後も
    ユニークなstoryIdの数だけ含まれる (入力順に安定)。metadata矛盾が
    検出されたstoryはマージ済みdocument一覧に含めない (該当storyのdraft
    は生成しない)。
    """
    groups: dict[str | None, list[dict[str, Any]]] = {}
    order: list[str | None] = []
    for doc in documents:
        story_id = doc.get("storyId")
        if story_id not in groups:
            groups[story_id] = []
            order.append(story_id)
        groups[story_id].append(doc)

    merged_documents: list[dict[str, Any]] = []
    conflicts: list[dict[str, str]] = []
    renumbered_story_ids: list[str] = []
    for story_id in order:
        docs_for_story = groups[story_id]
        conflict_message = _check_metadata_conflict(story_id, docs_for_story)
        if conflict_message is not None:
            conflicts.append({"storyId": str(story_id), "message": conflict_message})
            continue
        merged_document, renumbered = _merge_story_documents(docs_for_story)
        if renumbered:
            renumbered_story_ids.append(str(story_id))
        merged_documents.append(merged_document)

    return merged_documents, conflicts, renumbered_story_ids


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

    story_synthesis_report: dict[str, Any] | None = None
    if result.story_synthesis is not None:
        story_synthesis_report = {
            "synthesized": not result.story_synthesis.skipped,
            "promptVersion": result.story_synthesis.prompt_version,
            "evidenceRefCount": len(result.story_synthesis.evidence_refs),
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "blocking": issue.blocking,
                }
                for issue in result.story_synthesis.issues
            ],
        }

    return {
        "storyId": result.story_id,
        "episodeCount": len(result.episode_results),
        "episodesGenerated": episodes_generated,
        "episodesSkipped": episodes_skipped,
        "issueCodeCounts": issue_code_counts,
        "episodesWithIssues": episodes_with_issues,
        "storySynthesis": story_synthesis_report,
    }


def _story_report_lines(
    report: dict[str, Any], *, renumbered: bool = False
) -> list[str]:
    """1 story分のreport Markdown節を組み立てる。"""
    lines = [
        f"## {report['storyId']}",
        "",
        f"- Episode count: {report['episodeCount']}",
        f"- Episodes generated: {report['episodesGenerated']}",
        f"- Episodes skipped: {report['episodesSkipped']}",
    ]
    if renumbered:
        lines.append(
            "- Episode numbers renumbered: merge後のepisodeNumber列が一意な"
            "昇順ではなかったため、ソート済み順に1..nへ振り直しました。"
        )
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
            lines.append(f"- {episode['episodeId']} (skipped={episode['skipped']}):")
            for issue in episode["issues"]:
                lines.append(
                    f"  - [{issue['code']}] {issue['message']} "
                    f"(blocking={issue['blocking']})"
                )
        lines.append("")

    lines.append("### Story synthesis")
    lines.append("")
    lines.extend(_story_synthesis_report_lines(report["storySynthesis"]))
    lines.append("")
    return lines


def _story_synthesis_report_lines(synthesis: dict[str, Any] | None) -> list[str]:
    """`_story_report_lines`の「Story synthesis」節本体を組み立てる
    (`summary-generation-quality-v2`でprompt version行を追加した際、
    C901複雑度対策として`_story_report_lines`から分離した)。"""
    if synthesis is None:
        return ["- Synthesized: skipped (--no-story-synthesis)"]

    lines = [f"- Synthesized: {synthesis['synthesized']}"]
    if synthesis["promptVersion"]:
        lines.append(f"- Prompt version: {synthesis['promptVersion']}")
    lines.append(f"- evidenceRefs (union): {synthesis['evidenceRefCount']}")
    if synthesis["issues"]:
        lines.append("- Issues:")
        for issue in synthesis["issues"]:
            lines.append(
                f"  - [{issue['code']}] {issue['message']} "
                f"(blocking={issue['blocking']})"
            )
    return lines


def _build_report_markdown(
    story_reports: list[dict[str, Any]],
    *,
    input_count: int,
    written_count: int,
    schema_valid: bool,
    schema_issues: list[str],
    metadata_conflicts: list[dict[str, str]] | None = None,
    renumbered_story_ids: list[str] | None = None,
) -> str:
    metadata_conflicts = metadata_conflicts or []
    renumbered_story_ids = renumbered_story_ids or []
    renumbered_set = set(renumbered_story_ids)
    # Story countはユニークstoryId単位 (グルーピング後に生成へ進んだstory +
    # metadata矛盾でblockされたstory)。
    lines = [
        "# Story Summary Generation Report",
        "",
        f"- Input files: {input_count}",
        f"- Story count: {len(story_reports) + len(metadata_conflicts)}",
        f"- Draft files written: {written_count}",
    ]
    if metadata_conflicts:
        lines.append(f"- Metadata conflicts (blocked): {len(metadata_conflicts)}")
    if renumbered_story_ids:
        lines.append(
            f"- Episode numbers renumbered (story count): {len(renumbered_story_ids)}"
        )
    lines.append("")

    for report in story_reports:
        lines.extend(
            _story_report_lines(report, renumbered=report["storyId"] in renumbered_set)
        )

    if metadata_conflicts:
        lines.append("## Metadata Conflicts")
        lines.append("")
        lines.append(
            "- 同一storyIdのdocument間でmetadata.publicStoryIdが矛盾した"
            "storyです。draftは生成していません。"
        )
        lines.append("")
        for conflict in metadata_conflicts:
            lines.append(f"- {conflict['storyId']}: {conflict['message']}")
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
        "- storySummary (Story全体の要約) は既定でEpisode Summary群から"
        "LLM再要約により合成しています (Plan §11)。`--no-story-synthesis`"
        "で無効化した場合は常にnullのままです。"
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
    seen_output_paths: set[Path] = set()
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
        if out_path in seen_output_paths:
            # storyId単位のグルーピング後は本来発生しないはずの防御策。
            # 万一発生した場合も黙って上書きせず、blocking errorとして
            # 報告する。
            schema_issues.append(
                f"{result.story_id}: 出力ファイル{out_path}へ2回目の"
                "書き込みが発生しました (storyIdグルーピング後の想定外の"
                "重複、書き込みをskipしました)"
            )
            continue
        seen_output_paths.add(out_path)
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

    # storyId単位でグルーピングし、同一storyIdのdocument群のepisodes配列を
    # マージした上で1 story = 1 draftとして処理する (Phase 1 parserは
    # 1 episode 1ファイルのため、複数episode storyは必ず複数ファイルに
    # 分かれる。`summary-generation-multi-episode-grouping`で修正した
    # PoC発見バグ)。metadata.publicStoryIdが矛盾するstoryはblocking error
    # としてgrouped_documentsに含めず、metadata_conflictsに記録する。
    grouped_documents, metadata_conflicts, renumbered_story_ids = (
        _group_documents_by_story_id(documents)
    )

    provider = (provider_factory or _default_provider_factory)(args)

    results = [
        generate_story_summary_draft(
            document,
            provider=provider,
            max_input_characters=args.max_input_characters,
            verbatim_threshold=args.verbatim_threshold,
            synthesize_story=not args.no_story_synthesis,
            max_context_tokens=args.story_synthesis_max_context_tokens,
            refine=args.refine,
        )
        for document in grouped_documents
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
        metadata_conflicts=metadata_conflicts,
        renumbered_story_ids=renumbered_story_ids,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_markdown, encoding="utf-8")

    if not args.quiet:
        print(
            f"[generate] {len(documents)} document ({len(grouped_documents)} "
            f"unique story) を処理し、{len(written_paths)} draftを"
            "書き出しました"
        )
        print(f"[generate] 出力先: {output_dir}")
        print(f"[generate] report: {report_path}")
        if schema_issues:
            print(
                f"[エラー] {len(schema_issues)}件のschema検証エラーがあります",
                file=sys.stderr,
            )
        if metadata_conflicts:
            print(
                f"[エラー] {len(metadata_conflicts)}件のmetadata矛盾により"
                "storyのdraft生成をblockしました",
                file=sys.stderr,
            )

    return 1 if (schema_issues or metadata_conflicts) else 0


if __name__ == "__main__":
    sys.exit(main())
