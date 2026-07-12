#!/usr/bin/env python3
"""
Project Story Summary Public IDs
Story Summary（`schemas/story_summary.schema.json`準拠のYAML）に
`publicStoryId`/`publicEpisodeId`中心のCompatible/Public-safe projectionを
適用するscriptである（`feature/summary-generation-public-safe-projection`、
`docs/architecture/06_AI/Summary_Public_ID_Projection_Design.md` §4〜§9）。

`--projection-mode`で2つのmodeを切り替える:

- `compatible`（既定）: 既存の内部ID`storyId`/`episodeId`は一切削除しない。
  `--registry`指定時のみ、欠落している`episodeSummaries[].publicEpisodeId`を
  Registry値で補完する。migration/debugging用であり、
  **Public promotion対象ではない**
- `public-safe`: `storyId`/`episodeId`の値をそれぞれ`publicStoryId`/
  `publicEpisodeId`の値へ置換する（field自体はrequiredのまま維持）。
  `source.inputRefs`は除去する。`evidenceRefs`は`--evidence-mapping`で
  `publicEvidenceId`へ変換し、解決不可なら空配列にする。出力ファイル名も
  `{publicStoryId}.yaml`にする

**重要な安全方針**（両modeで共通）:
- `--output`/`--mapping-output`/`--report`はいずれも`knowledge/summaries/`・
  `knowledge/public_ids/`配下を指定できない（安全確認で拒否、exit code 2）
- `--input`ファイル自体は読み込みのみで変更しない（書き込み先は常に
  `--output`）
- `--mapping-output`は内部ID⇔公開IDのmappingを常に含む
  （public-safe modeでも同様）。Internal Review Evidence Packet候補データ
  であり、**commit禁止**

Registry共有設計（`Summary_Public_ID_Projection_Design.md` §7）:
`scripts/check_public_episode_ids.py`から`_resolve_registry_lookup`/
`_group_entries_by_internal_story`/`DEFAULT_REGISTRY_SCHEMA_PATH`をそのまま
importして再利用する。Evidence Indexの「flatなentries配列」とStory
Summaryの「1 file 1 story、episodeSummaries入れ子配列」という構造差は、
Story Summary document側でEvidence Index entry形状を模したsynthetic
entriesアダプタ（`_build_synthetic_entries`）を組み立てることで吸収する。

evidenceRefs変換（同 §6）:
`scripts/project_evidence_index_public_ids.py --projection-mode public-safe
--mapping-output <path>`が生成するmapping CSVを`--evidence-mapping`として
受け取り、`evidenceId`列→`publicEvidenceId`列の2列のみを使って変換する。
1件でも未解決参照があれば、そのSummary単位（story-level/episode-level）の
`evidenceRefs`全体を空配列にする（部分変換は残さない）。

実装時に確定した、設計docの記述との差分（§設計 vs 実装の整合、いずれも
設計の趣旨を保った上での確定であり、PR報告にも明記する）:

1. `Summary_Public_ID_Projection_Design.md` §5の field rewrite tableは
   `publicStoryId`（compatible mode）を「Registry補完があれば書き込む」と
   記載しているが、同文書 §7.3は「Registry構造上`publicStoryId`自体を
   キーにstoryを逆引きする仕組みは提供されない」と明記している。本実装は
   より詳細な §7.3 を正とし、`publicStoryId`のRegistry補完は行わない
   （欠落時は常にblocking、§4.3項目1）
2. 出力ファイル名の compatible mode 表記は `{output_dir}/{storyId}.yaml`
   だが、同じ行の括弧書きは「入力ファイル名を維持」としている。本実装は
   後者（`project_evidence_index_public_ids.py`のcompatible modeと同じ、
   入力ファイル名 `path.name` をそのまま使う）を採用した。Story Summaryの
   命名規約上、通常はこの2つは同じ値になる
3. `--mapping-output`のCSV行仕様（§4.5.1）「1 episode 1行
   （story-level summaryのみのdocumentは1 story 1行を追加）」は、文字通り
   「`episodeSummaries`が空でStory Summaryのみ存在するdocument」の場合に
   限定してstory行を1行追加する仕様として実装した（`episodeSummaries`が
   非空のdocumentでは、Story Summary自体のevidenceRefs変換統計はmapping
   CSVの行としては出力されない。ただしreportの
   `## Evidence Refs Conversion`sectionには常に集計される）

Non-goals（本scriptで行わないこと。詳細は
`docs/architecture/06_AI/Summary_Public_ID_Projection_Design.md` §11参照）:
- `knowledge/summaries/stories/`への実copy・commit
- Summary promotion copy script（`promote_evidence_index.py`相当）の実行
- LLM呼び出し・provider・prompt実装
- `review.status`/`generationStatus`のenforcement（`validate_story_summaries.py
  --require-reviewed`の責務のまま）

Usage:
    uv run python scripts/project_story_summary_public_ids.py \\
        --input knowledge/summaries/stories/ \\
        --output workspace/summary_drafts/public_id_projection/ \\
        --mapping-output workspace/summary_drafts/public_id_map.csv \\
        --report workspace/summary_drafts/public_id_report.md \\
        --projection-mode compatible \\
        --clean

    uv run python scripts/project_story_summary_public_ids.py \\
        --input knowledge/summaries/stories/ \\
        --output workspace/summary_drafts/public_safe/stories/ \\
        --mapping-output workspace/summary_drafts/public_safe/mapping.csv \\
        --report workspace/summary_drafts/public_safe/report.md \\
        --projection-mode public-safe \\
        --evidence-mapping workspace/evidence_index_dry_runs/public_safe/mapping.csv \\
        --registry knowledge/public_ids/story_public_ids.yaml \\
        --clean

Exit codes:
    0: projection成功（blocking issueなし）
    1: projection validation失敗（publicStoryId/publicEpisodeId欠落、
       既存publicStoryId/publicEpisodeIdとRegistry値の不一致、public-safe
       mode時の出力ファイル名衝突、projected出力のschema検証失敗、
       public-safe mode時のsourceKey由来ID exposure検出等）
    2: --input/--schema/--registry/--registry-schema/--evidence-mapping
       パスが見つからない、または--output/--mapping-output/--reportが
       knowledge/summaries/・knowledge/public_ids/配下を指しているなどの
       config error
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

from check_public_episode_ids import (  # noqa: E402
    DEFAULT_REGISTRY_SCHEMA_PATH,
    _group_entries_by_internal_story,
    _resolve_registry_lookup,
)

DEFAULT_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "story_summary.schema.json"

# knowledge/summaries・knowledge/public_ids配下は本scriptの出力先として
# 一切許可しない (§安全方針)。
_FORBIDDEN_OUTPUT_DIRS = (
    (_PROJECT_ROOT / "knowledge" / "summaries").resolve(),
    (_PROJECT_ROOT / "knowledge" / "public_ids").resolve(),
)

PROJECTION_MODE_COMPATIBLE = "compatible"
PROJECTION_MODE_PUBLIC_SAFE = "public-safe"
PROJECTION_MODES = (PROJECTION_MODE_COMPATIBLE, PROJECTION_MODE_PUBLIC_SAFE)

# public-safe modeのsourceKey由来ID exposure scanで対象にする内部IDの
# 最小長 (`Evidence_Index_Public_ID_Policy.md` §6.7.1、
# `Summary_Public_ID_Projection_Design.md` §9で同じ値を再利用)。
MIN_FORBIDDEN_INTERNAL_ID_LENGTH = 4

MAPPING_FIELDNAMES = [
    "storyId",
    "publicStoryId",
    "episodeId",
    "publicEpisodeId",
    "publicEpisodeIdSource",
    "registryMatched",
    "registryConflict",
    "registryPublicEpisodeId",
    "episodeOrder",
    "evidenceRefsInputCount",
    "evidenceRefsConvertedCount",
    "evidenceRefsClearedCount",
]


# ----------------------------------------------------------------
# Argument parser
# ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Story SummaryにpublicStoryId/publicEpisodeId中心のprojectionを"
            "適用するscript。--projection-mode compatible (既定、内部IDは"
            "削除しない) と public-safe (内部IDを公開IDへ置換・除去する) を"
            "切り替えられる。出力はworkspace配下のみを想定し、"
            "knowledge/summaries/・knowledge/public_ids/配下への書き込みは"
            "拒否する"
        ),
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Story Summary YAMLファイル、またはdirectory (直下の*.yaml/*.ymlを収集)",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help=(
            "projection結果を書き出すdirectory (workspace配下のみ。"
            "knowledge/summaries/・knowledge/public_ids/配下は指定不可)"
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
        help=f"story_summary.schema.jsonのパス (デフォルト: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--registry",
        default=None,
        help=(
            "Public ID Registry YAMLのパス (任意、"
            "scripts/check_public_episode_ids.pyと同じschema/lookup方針)。"
            "指定すると、publicStoryId+episodeOrderで引けるentryについて、"
            "欠落しているepisodeSummaries[].publicEpisodeIdをRegistryの値で"
            "補完する。publicStoryId自体の補完はRegistry構造上できない"
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
        "--evidence-mapping",
        default=None,
        help=(
            "project_evidence_index_public_ids.py --projection-mode "
            "public-safe --mapping-output が生成したmapping CSV (fileまたは"
            "directory)。evidenceId/publicEvidenceId列のみを使い、"
            "evidenceRefs内の内部blockId参照をpublicEvidenceId参照へ変換する"
        ),
    )
    parser.add_argument(
        "--projection-mode",
        choices=PROJECTION_MODES,
        default=PROJECTION_MODE_COMPATIBLE,
        help=(
            "projection mode (デフォルト: compatible。compatibleは既存の"
            "内部IDを維持したままRegistry補完のみ行いpromotion対象ではない。"
            "public-safeは内部IDを公開IDへ置換・除去し、出力ファイル名も"
            "publicStoryIdベースにする)"
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
# Input collection / schema validation
# (`scripts/check_evidence_index_promotion.py`の`_collect_yaml_paths`/
# `_load_yaml_documents`と同じ方針だが、本scriptがimportするのは
# `check_public_episode_ids.py`の2関数のみという設計上の制約
# (`Summary_Public_ID_Projection_Design.md` §7.1) のため、ここでは
# 同等のロジックを独立して実装する。)
# ----------------------------------------------------------------


def _collect_yaml_paths(input_path: Path) -> list[Path] | None:
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
# --evidence-mapping loading (evidenceId -> publicEvidenceId lookup)
# ----------------------------------------------------------------


def _load_evidence_mapping(
    path: Path | None,
) -> tuple[dict[str, str] | None, int | None]:
    """`--evidence-mapping`のCSV (fileまたはdirectory) を読み込み、
    evidenceId -> publicEvidenceId のlookup dictを組み立てる
    (`Summary_Public_ID_Projection_Design.md` §6.1)。`evidenceId`/
    `publicEvidenceId`列以外は無視する。

    戻り値: (lookup, exit_code)。`--evidence-mapping`未指定ならlookupは
    None・exit_codeもNone。エラー時はlookupがNone・exit_codeが2。
    """
    if path is None:
        return None, None
    if not path.exists():
        print(
            f"[エラー] --evidence-mappingパスが見つかりません: {path}", file=sys.stderr
        )
        return None, 2

    if path.is_file():
        csv_paths = [path]
    elif path.is_dir():
        csv_paths = sorted(path.glob("*.csv"))
    else:
        print(
            f"[エラー] --evidence-mappingパスが見つかりません: {path}", file=sys.stderr
        )
        return None, 2

    lookup: dict[str, str] = {}
    for csv_path in csv_paths:
        try:
            with open(csv_path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    evidence_id = row.get("evidenceId")
                    public_evidence_id = row.get("publicEvidenceId")
                    if evidence_id and public_evidence_id:
                        # 複数file合流時は後勝ち (§6.1)。
                        lookup[evidence_id] = public_evidence_id
        except OSError as e:
            print(
                f"[エラー] --evidence-mappingの読み込みに失敗しました: {e}",
                file=sys.stderr,
            )
            return None, 2

    return lookup, None


# ----------------------------------------------------------------
# Registry integration: synthetic entries adapter
# (`Summary_Public_ID_Projection_Design.md` §7.2)
# ----------------------------------------------------------------


def _build_synthetic_entries(
    raw_documents: list[tuple[Path, dict[str, Any]]],
) -> tuple[list[tuple[Path, dict[str, Any]]], dict[int, dict[str, Any]]]:
    """Story Summary documentから、Evidence Index entry形状を模した
    synthetic entriesを組み立てる (§7.2 adapter)。`_group_entries_by_
    internal_story`へそのまま渡せる `{"entries": [...]}` 形へ包む。

    戻り値: (adapter raw_documents, id(synthetic entry) -> 対応する実際の
    episode dict)。
    """
    adapter_documents: list[tuple[Path, dict[str, Any]]] = []
    backref: dict[int, dict[str, Any]] = {}
    for path, doc in raw_documents:
        story_id = doc.get("storyId")
        public_story_id = doc.get("publicStoryId")
        synthetic_entries: list[dict[str, Any]] = []
        for episode in doc.get("episodeSummaries", []) or []:
            synthetic = {
                "storyId": story_id,
                "episodeId": episode.get("episodeId"),
                "publicStoryId": public_story_id,
                "publicEpisodeId": episode.get("publicEpisodeId"),
            }
            synthetic_entries.append(synthetic)
            backref[id(synthetic)] = episode
        adapter_documents.append((path, {"entries": synthetic_entries}))
    return adapter_documents, backref


def _apply_registry_and_build_metadata(
    raw_documents: list[tuple[Path, dict[str, Any]]],
    registry_lookup: dict[tuple[str, int], str] | None,
) -> dict[str, Any]:
    """`_group_entries_by_internal_story`（`check_public_episode_ids.py`
    からimport）を使って内部storyId単位でepisodeOrderを計算し
    (内部episodeIdの出現順を1始まりとする、Evidence Index側と同じ
    ロジック)、`registry_lookup`が与えられていれば欠落
    `episodeSummaries[].publicEpisodeId`をentryへ補完する (in-place)。

    Registry補完ルール（`Public_ID_Registry_Design.md` §6.4、
    `Summary_Public_ID_Projection_Design.md` §7.3）:
    - 既存publicEpisodeIdがある場合: Registry値と一致すればそのまま、
      不一致ならblocking issue、Registryに該当が無ければwarning
    - 既存publicEpisodeIdが無い場合: Registryに該当があれば補完、
      無ければ何もしない（欠落のまま、別途blockingとして報告される）
    - publicStoryId自体はRegistryから補完しない (§7.3、Registry構造上
      逆引きができないため)

    戻り値: {"issues": [...], "warnings": [...], "completedCount": int,
    "metaByEpisodeId": {id(実際のepisode dict): {"source": ...,
    "episodeOrder": ..., "registryPublicEpisodeId": ...,
    "registryConflict": ...}}}。
    """
    adapter_documents, backref = _build_synthetic_entries(raw_documents)
    order, groups = _group_entries_by_internal_story(adapter_documents)

    issues: list[str] = []
    warnings: list[str] = []
    completed_count = 0
    meta: dict[int, dict[str, Any]] = {}

    for story_id in order:
        entries = groups[story_id]
        public_story_ids = {
            entry.get("publicStoryId")
            for entry in entries
            if entry.get("publicStoryId")
        }
        resolved_public_story_id = (
            next(iter(public_story_ids)) if len(public_story_ids) == 1 else None
        )
        label = (
            f"publicStoryId={resolved_public_story_id}"
            if resolved_public_story_id
            else "publicStoryId未確定のstory"
        )

        episode_order: dict[str, int] = {}
        for entry in entries:
            episode_id = entry.get("episodeId")
            if episode_id and episode_id not in episode_order:
                episode_order[episode_id] = len(episode_order) + 1

        for entry in entries:
            episode_id = entry.get("episodeId")
            order_number = episode_order.get(episode_id)
            if order_number is None:
                continue
            real_episode = backref[id(entry)]
            existing_value = entry.get("publicEpisodeId")
            registry_value = (
                registry_lookup.get((resolved_public_story_id, order_number))
                if registry_lookup is not None and resolved_public_story_id
                else None
            )

            if existing_value:
                conflict = bool(registry_value) and registry_value != existing_value
                if conflict:
                    issues.append(
                        f"{label}: episodeOrder {order_number} の既存"
                        f"publicEpisodeId '{existing_value}' がRegistry値 "
                        f"'{registry_value}' と一致しません"
                    )
                elif registry_lookup is not None and not registry_value:
                    warnings.append(
                        f"{label}: episodeOrder {order_number} は既存"
                        f"publicEpisodeId '{existing_value}' を使用して"
                        "いますが、Registryには対応するentryがありません"
                    )
                meta[id(real_episode)] = {
                    "source": "input",
                    "episodeOrder": order_number,
                    "registryPublicEpisodeId": registry_value,
                    "registryConflict": conflict,
                }
            elif registry_value:
                real_episode["publicEpisodeId"] = registry_value
                completed_count += 1
                meta[id(real_episode)] = {
                    "source": "registry",
                    "episodeOrder": order_number,
                    "registryPublicEpisodeId": registry_value,
                    "registryConflict": False,
                }
            else:
                meta[id(real_episode)] = {
                    "source": "missing",
                    "episodeOrder": order_number,
                    "registryPublicEpisodeId": None,
                    "registryConflict": False,
                }

    return {
        "issues": issues,
        "warnings": warnings,
        "completedCount": completed_count,
        "metaByEpisodeId": meta,
    }


# ----------------------------------------------------------------
# Blocking checks: missing publicStoryId / publicEpisodeId
# (`Summary_Public_ID_Projection_Design.md` §4.3 items 1-2)
# ----------------------------------------------------------------


def _check_missing_public_story_id(
    raw_documents: list[tuple[Path, dict[str, Any]]],
) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    issues: list[str] = []
    for path, doc in raw_documents:
        if not doc.get("publicStoryId"):
            missing.append(str(path))
            issues.append(
                f"{path}: publicStoryIdが欠落しています "
                "(Public ID Registryはepisode単位のpublicEpisodeIdしか補完"
                "できないため、Registry指定時も自動補完されません)"
            )
    return missing, issues


def _check_missing_public_episode_id(
    raw_documents: list[tuple[Path, dict[str, Any]]],
) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    issues: list[str] = []
    for path, doc in raw_documents:
        for episode in doc.get("episodeSummaries", []) or []:
            if not episode.get("publicEpisodeId"):
                label = f"{path}: episodeId={episode.get('episodeId')!r}"
                missing.append(label)
                issues.append(f"{label}: publicEpisodeIdが欠落しています")
    return missing, issues


# ----------------------------------------------------------------
# evidenceRefs conversion (`Summary_Public_ID_Projection_Design.md` §6)
# ----------------------------------------------------------------


def _process_evidence_refs(
    refs: list[str] | None,
    lookup: dict[str, str] | None,
    *,
    convert: bool,
) -> tuple[list[str], dict[str, int]]:
    """evidenceRefsを変換する (§6.2)。`convert=False` (compatible mode) の
    場合は無変換のまま返す。`convert=True` (public-safe mode) の場合:

    1. `ref`がlookupに`evidenceId`として存在すれば`publicEvidenceId`へ置換
    2. `ref`が既に`publicEvidenceId`形式 (lookupの値側と一致) ならそのまま
       保持
    3. どちらにも見つからない参照が1件でもあれば、refs全体を空配列にする

    `lookup`がNone (`--evidence-mapping`未指定) の場合、refsが非空なら
    常に空配列にする (§6.3)。

    戻り値: (変換後refs, {"inputCount": ..., "convertedCount": ...,
    "clearedCount": ...})。
    """
    refs = list(refs or [])
    input_count = len(refs)

    if not convert:
        return refs, {
            "inputCount": input_count,
            "convertedCount": 0,
            "clearedCount": 0,
        }

    if not refs:
        return [], {"inputCount": 0, "convertedCount": 0, "clearedCount": 0}

    if lookup is None:
        return [], {
            "inputCount": input_count,
            "convertedCount": 0,
            "clearedCount": input_count,
        }

    lookup_values = set(lookup.values())
    converted: list[str] = []
    for ref in refs:
        if ref in lookup:
            converted.append(lookup[ref])
        elif ref in lookup_values:
            converted.append(ref)
        else:
            return [], {
                "inputCount": input_count,
                "convertedCount": 0,
                "clearedCount": input_count,
            }

    return converted, {
        "inputCount": input_count,
        "convertedCount": len(converted),
        "clearedCount": 0,
    }


# ----------------------------------------------------------------
# Field rewrite / document build (compatible / public-safe)
# (`Summary_Public_ID_Projection_Design.md` §5)
# ----------------------------------------------------------------


def _rewrite_documents(
    raw_documents: list[tuple[Path, dict[str, Any]]],
    *,
    mode: str,
    evidence_lookup: dict[str, str] | None,
) -> dict[str, Any]:
    """compatible/public-safeそれぞれのfield rewriteを行う。

    戻り値: {
      "outputDocuments": {filename: projected raw dict},
      "filenameSources": {filename: [由来source path, ...]},
      "episodeEvidenceStats": {id(元のepisode dict): {"inputCount":,
        "convertedCount":, "clearedCount":}},
      "storyEvidenceStats": {id(元のdoc dict): stats または None
        (storySummary無しの場合)},
      "evidenceWarnings": [...],
      "storiesPromotedWithoutEvidenceRefsCount": int,
    }
    """
    convert = mode == PROJECTION_MODE_PUBLIC_SAFE

    episode_stats: dict[int, dict[str, Any]] = {}
    story_stats: dict[int, dict[str, Any] | None] = {}
    warnings: list[str] = []
    stories_promoted_without_evidence_refs: set[str] = set()

    output_documents: dict[str, dict[str, Any]] = {}
    filename_sources: dict[str, list[Path]] = {}

    for path, doc in raw_documents:
        story_id = doc.get("storyId")
        public_story_id = doc.get("publicStoryId")

        story_summary = doc.get("storySummary")
        new_story_summary: dict[str, Any] | None = None
        if story_summary is not None:
            refs, stats = _process_evidence_refs(
                story_summary.get("evidenceRefs"), evidence_lookup, convert=convert
            )
            story_stats[id(doc)] = stats
            if convert and stats["clearedCount"] > 0:
                stories_promoted_without_evidence_refs.add(str(story_id))
                warnings.append(
                    f"{path}: storyId={story_id!r}のStory Summary "
                    "evidenceRefsは--evidence-mappingで解決できなかったため"
                    "空配列にしました"
                )
            new_story_summary = {
                "text": story_summary.get("text"),
                "confidence": story_summary.get("confidence"),
                "evidenceRefs": refs,
            }
        else:
            story_stats[id(doc)] = None

        new_episodes: list[dict[str, Any]] = []
        for episode in doc.get("episodeSummaries", []) or []:
            refs, stats = _process_evidence_refs(
                episode.get("evidenceRefs"), evidence_lookup, convert=convert
            )
            episode_stats[id(episode)] = stats
            if convert and stats["clearedCount"] > 0:
                stories_promoted_without_evidence_refs.add(str(story_id))
                warnings.append(
                    f"{path}: episodeId={episode.get('episodeId')!r}のEpisode "
                    "Summary evidenceRefsは--evidence-mappingで解決できな"
                    "かったため空配列にしました"
                )

            episode_id_value = episode.get("episodeId")
            public_episode_id_value = episode.get("publicEpisodeId")
            new_episodes.append(
                {
                    "episodeId": (
                        public_episode_id_value if convert else episode_id_value
                    ),
                    "publicEpisodeId": public_episode_id_value,
                    "episodeNumber": episode.get("episodeNumber"),
                    "text": episode.get("text"),
                    "confidence": episode.get("confidence"),
                    "evidenceRefs": refs,
                }
            )

        if convert:
            new_doc = {
                "schemaVersion": doc.get("schemaVersion"),
                "documentType": doc.get("documentType"),
                "storyId": public_story_id,
                "publicStoryId": public_story_id,
                "language": doc.get("language"),
                "generationStatus": doc.get("generationStatus"),
                "storySummary": new_story_summary,
                "episodeSummaries": new_episodes,
                "source": {
                    key: value
                    for key, value in (doc.get("source") or {}).items()
                    if key != "inputRefs"
                },
                "review": doc.get("review"),
                "notes": doc.get("notes"),
            }
            filename = f"{public_story_id}.yaml" if public_story_id else None
        else:
            new_doc = {
                "schemaVersion": doc.get("schemaVersion"),
                "documentType": doc.get("documentType"),
                "storyId": story_id,
                "publicStoryId": public_story_id,
                "language": doc.get("language"),
                "generationStatus": doc.get("generationStatus"),
                "storySummary": new_story_summary,
                "episodeSummaries": new_episodes,
                "source": doc.get("source"),
                "review": doc.get("review"),
                "notes": doc.get("notes"),
            }
            filename = path.name

        if filename:
            filename_sources.setdefault(filename, []).append(path)
            output_documents[filename] = new_doc

    return {
        "outputDocuments": output_documents,
        "filenameSources": filename_sources,
        "episodeEvidenceStats": episode_stats,
        "storyEvidenceStats": story_stats,
        "evidenceWarnings": warnings,
        "storiesPromotedWithoutEvidenceRefsCount": len(
            stories_promoted_without_evidence_refs
        ),
    }


def _run_public_safe_checks(
    raw_documents: list[tuple[Path, dict[str, Any]]],
    rewrite_result: dict[str, Any],
) -> dict[str, Any]:
    """public-safe mode専用の追加チェック（duplicate filename・internal ID
    exposure scan）とfield rewrite集計をまとめて行う。

    戻り値: {"issues": [...], "internalIdExposureCount": int,
    "internalIdExposureDetails": [...], "rewrittenIdFieldsCount": int,
    "removedInternalFieldsCount": int}。
    """
    duplicate_filename_issues = _check_duplicate_filenames(
        rewrite_result["filenameSources"]
    )
    forbidden_ids = _collect_forbidden_internal_ids(raw_documents)
    exposure_counts, exposure_issues = _scan_documents_for_exposure(
        rewrite_result["outputDocuments"], forbidden_ids
    )

    rewritten_id_fields_count = 0
    removed_internal_fields_count = 0
    for _, doc in raw_documents:
        if doc.get("publicStoryId"):
            rewritten_id_fields_count += 1
        source = doc.get("source") or {}
        if source.get("inputRefs"):
            removed_internal_fields_count += 1
        for episode in doc.get("episodeSummaries", []) or []:
            if episode.get("publicEpisodeId"):
                rewritten_id_fields_count += 1

    return {
        "issues": duplicate_filename_issues + exposure_issues,
        "internalIdExposureCount": sum(exposure_counts.values()),
        "internalIdExposureDetails": [
            f"'{internal_id}': {count}回"
            for internal_id, count in sorted(exposure_counts.items())
        ],
        "rewrittenIdFieldsCount": rewritten_id_fields_count,
        "removedInternalFieldsCount": removed_internal_fields_count,
    }


def _sum_evidence_ref_counts(rewrite_result: dict[str, Any]) -> tuple[int, int]:
    """episode/story双方のevidenceRefs変換統計を合算する。戻り値:
    (convertedCount合計, clearedCount合計)。"""
    episode_stats = rewrite_result["episodeEvidenceStats"].values()
    story_stats = [
        stats
        for stats in rewrite_result["storyEvidenceStats"].values()
        if stats is not None
    ]
    converted = sum(s["convertedCount"] for s in episode_stats) + sum(
        s["convertedCount"] for s in story_stats
    )
    cleared = sum(s["clearedCount"] for s in episode_stats) + sum(
        s["clearedCount"] for s in story_stats
    )
    return converted, cleared


def _check_duplicate_filenames(filename_sources: dict[str, list[Path]]) -> list[str]:
    """複数の入力ファイルが同じpublicStoryId (= 同じ出力ファイル名) へ解決
    される場合、出力の衝突としてblocking errorにする (§4.3項目4)。"""
    issues: list[str] = []
    for filename, paths in sorted(filename_sources.items()):
        if len(paths) > 1:
            source_list = sorted(str(p) for p in paths)
            issues.append(
                f"出力ファイル名 '{filename}' が複数の入力ファイル "
                f"{source_list!r} に混在しています "
                "(public-safe projectionの出力ファイル名が衝突します)"
            )
    return issues


# ----------------------------------------------------------------
# Internal ID exposure scan (`Summary_Public_ID_Projection_Design.md` §9)
# ----------------------------------------------------------------


def _collect_forbidden_internal_ids(
    raw_documents: list[tuple[Path, dict[str, Any]]],
) -> frozenset[str]:
    """public-safe modeのsourceKey由来ID exposure scan用に、除去すべき
    内部ID値 (storyId/episodeSummaries[].episodeId) を収集する。

    対応する公開ID (publicStoryId/publicEpisodeId) と一致する値は除外し
    (偶然一致は安全)、`MIN_FORBIDDEN_INTERNAL_ID_LENGTH`未満の短い値も
    誤検出防止のため対象から除く。
    """
    internal_ids: set[str] = set()
    public_ids: set[str] = set()
    for _, doc in raw_documents:
        story_id = doc.get("storyId")
        if isinstance(story_id, str) and story_id:
            internal_ids.add(story_id)
        public_story_id = doc.get("publicStoryId")
        if isinstance(public_story_id, str) and public_story_id:
            public_ids.add(public_story_id)
        for episode in doc.get("episodeSummaries", []) or []:
            episode_id = episode.get("episodeId")
            if isinstance(episode_id, str) and episode_id:
                internal_ids.add(episode_id)
            public_episode_id = episode.get("publicEpisodeId")
            if isinstance(public_episode_id, str) and public_episode_id:
                public_ids.add(public_episode_id)
    return frozenset(
        value
        for value in internal_ids
        if value not in public_ids and len(value) >= MIN_FORBIDDEN_INTERNAL_ID_LENGTH
    )


def _scan_text_for_forbidden_internal_ids(
    text: str, forbidden_ids: frozenset[str]
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for internal_id in forbidden_ids:
        occurrences = text.count(internal_id)
        if occurrences:
            counts[internal_id] = occurrences
    return counts


def _scan_documents_for_exposure(
    output_documents: dict[str, dict[str, Any]], forbidden_ids: frozenset[str]
) -> tuple[dict[str, int], list[str]]:
    exposure_counts: dict[str, int] = {}
    issues: list[str] = []
    for filename, raw in sorted(output_documents.items()):
        text = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
        for internal_id, count in _scan_text_for_forbidden_internal_ids(
            text, forbidden_ids
        ).items():
            exposure_counts[internal_id] = exposure_counts.get(internal_id, 0) + count
            issues.append(
                f"{filename}: 内部ID '{internal_id}' がpublic-safe出力に "
                f"{count}回残っています (internal ID exposure)"
            )
    return exposure_counts, issues


# ----------------------------------------------------------------
# Schema validation / output writing
# ----------------------------------------------------------------


def _validate_documents_against_schema(
    documents: dict[str, dict[str, Any]], schema: dict[str, Any]
) -> list[str]:
    issues: list[str] = []
    for filename, raw in sorted(documents.items()):
        errors = sorted(
            Draft7Validator(schema).iter_errors(raw), key=lambda e: list(e.path)
        )
        issues.extend(
            f"{filename} (projected): {list(e.path)}: {e.message}" for e in errors
        )
    return issues


def _write_documents(
    output_dir: Path, documents: dict[str, dict[str, Any]], *, clean: bool
) -> list[str]:
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for filename, raw in sorted(documents.items()):
        target = output_dir / filename
        with open(target, "w", encoding="utf-8") as f:
            yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)
        written.append(str(target))
    return written


# ----------------------------------------------------------------
# Mapping CSV (`Summary_Public_ID_Projection_Design.md` §4.5.1)
# ----------------------------------------------------------------


def _mapping_rows_for_document(
    path: Path,
    doc: dict[str, Any],
    *,
    meta_by_episode_id: dict[int, dict[str, Any]],
    episode_evidence_stats: dict[int, dict[str, Any]],
    story_evidence_stats: dict[int, dict[str, Any] | None],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    story_id = doc.get("storyId")
    public_story_id = doc.get("publicStoryId") or ""
    episodes = doc.get("episodeSummaries", []) or []

    if not episodes and doc.get("storySummary") is not None:
        stats = story_evidence_stats.get(id(doc)) or {
            "inputCount": 0,
            "convertedCount": 0,
            "clearedCount": 0,
        }
        rows.append(
            {
                "storyId": story_id,
                "publicStoryId": public_story_id,
                "episodeId": "",
                "publicEpisodeId": "",
                "publicEpisodeIdSource": "",
                "registryMatched": "",
                "registryConflict": "",
                "registryPublicEpisodeId": "",
                "episodeOrder": "",
                "evidenceRefsInputCount": stats["inputCount"],
                "evidenceRefsConvertedCount": stats["convertedCount"],
                "evidenceRefsClearedCount": stats["clearedCount"],
            }
        )

    for episode in episodes:
        meta = meta_by_episode_id.get(id(episode), {})
        stats = episode_evidence_stats.get(id(episode)) or {
            "inputCount": 0,
            "convertedCount": 0,
            "clearedCount": 0,
        }
        rows.append(
            {
                "storyId": story_id,
                "publicStoryId": public_story_id,
                "episodeId": episode.get("episodeId"),
                "publicEpisodeId": episode.get("publicEpisodeId") or "",
                "publicEpisodeIdSource": meta.get("source", ""),
                "registryMatched": meta.get("source") == "registry",
                "registryConflict": bool(meta.get("registryConflict", False)),
                "registryPublicEpisodeId": meta.get("registryPublicEpisodeId") or "",
                "episodeOrder": (
                    meta.get("episodeOrder")
                    if meta.get("episodeOrder") is not None
                    else ""
                ),
                "evidenceRefsInputCount": stats["inputCount"],
                "evidenceRefsConvertedCount": stats["convertedCount"],
                "evidenceRefsClearedCount": stats["clearedCount"],
            }
        )
    return rows


def _write_mapping_csv(
    mapping_output_path: Path,
    raw_documents: list[tuple[Path, dict[str, Any]]],
    *,
    meta_by_episode_id: dict[int, dict[str, Any]],
    episode_evidence_stats: dict[int, dict[str, Any]],
    story_evidence_stats: dict[int, dict[str, Any] | None],
) -> None:
    mapping_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(mapping_output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MAPPING_FIELDNAMES)
        writer.writeheader()
        for path, doc in raw_documents:
            for row in _mapping_rows_for_document(
                path,
                doc,
                meta_by_episode_id=meta_by_episode_id,
                episode_evidence_stats=episode_evidence_stats,
                story_evidence_stats=story_evidence_stats,
            ):
                writer.writerow(row)


# ----------------------------------------------------------------
# Report building (`Summary_Public_ID_Projection_Design.md` §4.5.2)
# ----------------------------------------------------------------


def _report_summary_lines(report: dict[str, Any]) -> list[str]:
    return [
        "# Story Summary Public ID Projection Report",
        "",
        f"- Input: {report['input']}",
        f"- Output: {report['output']}",
        f"- Mapping output: {report['mappingOutput']}",
        f"- Evidence mapping: {report['evidenceMapping'] or '(none)'}",
        f"- Projection mode: {report['projectionMode']}",
        f"- File count: {report['fileCount']}",
        f"- Story count: {report['storyCount']}",
        f"- Episode count: {report['episodeCount']}",
        "",
    ]


def _report_projection_result_lines(report: dict[str, Any]) -> list[str]:
    return [
        "## Projection Result",
        "",
        f"- Missing publicStoryId count: {report['missingPublicStoryIdCount']}",
        f"- Missing publicEpisodeId count: {report['missingPublicEpisodeIdCount']}",
        f"- Conflicts count: {report['registryConflictCount']}",
        "",
    ]


def _report_registry_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## Registry", ""]
    lines.append(f"- Registry path: {report['registryPath'] or '(none)'}")
    lines.append(f"- Registry stories count: {report['registryStoriesCount']}")
    lines.append(f"- Registry episodes count: {report['registryEpisodesCount']}")
    lines.append(
        f"- Entries with publicEpisodeId from input: {report['entriesFromInputCount']}"
    )
    lines.append(
        "- Entries with publicEpisodeId from registry: "
        f"{report['entriesFromRegistryCount']}"
    )
    lines.append(
        "- Missing publicEpisodeId after registry lookup: "
        f"{report['entriesMissingAfterRegistryCount']}"
    )
    lines.append(f"- Registry conflicts: {report['registryConflictCount']}")
    lines.append("")
    return lines


def _report_evidence_refs_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## Evidence Refs Conversion", ""]
    lines.append(f"- Evidence mapping path: {report['evidenceMapping'] or '(none)'}")
    lines.append(f"- Converted count: {report['evidenceRefsConvertedCount']}")
    lines.append(
        "- Cleared count (no evidence mapping match): "
        f"{report['evidenceRefsClearedCount']}"
    )
    lines.append(
        "- Stories promoted without evidenceRefs: "
        f"{report['storiesPromotedWithoutEvidenceRefsCount']}"
    )
    lines.append("")
    return lines


def _report_public_safe_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## Public-safe Projection", ""]
    lines.append("- Output filename policy: publicStoryId-based ({publicStoryId}.yaml)")
    lines.append(f"- Rewritten ID fields count: {report['rewrittenIdFieldsCount']}")
    lines.append(
        f"- Removed internal fields count: {report['removedInternalFieldsCount']} "
        "(source.inputRefs)"
    )
    lines.append(
        f"- Internal ID exposure scan: {report['internalIdExposureCount']} "
        "occurrence(s) across "
        f"{len(report['internalIdExposureDetails'])} distinct internal ID(s)"
    )
    if report["internalIdExposureDetails"]:
        for detail in report["internalIdExposureDetails"]:
            lines.append(f"  - {detail}")
    lines.append(f"- Promotion readiness: {report['promotionReadiness']}")
    lines.append("")
    return lines


def _report_issues_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## Issues", ""]
    if report["issues"]:
        for issue in report["issues"]:
            lines.append(f"- {issue}")
    else:
        lines.append("- (none)")
    lines.append("")
    return lines


def _report_warnings_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## Warnings", ""]
    if report["warnings"]:
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- (none)")
    lines.append("")
    return lines


def _build_report_lines(report: dict[str, Any]) -> list[str]:
    is_public_safe = report["projectionMode"] == PROJECTION_MODE_PUBLIC_SAFE

    lines: list[str] = []
    lines.extend(_report_summary_lines(report))
    lines.extend(_report_projection_result_lines(report))
    lines.extend(_report_registry_lines(report))
    lines.extend(_report_evidence_refs_lines(report))
    if is_public_safe:
        lines.extend(_report_public_safe_lines(report))
    lines.extend(_report_issues_lines(report))
    lines.extend(_report_warnings_lines(report))

    lines.append("## Final Decision")
    lines.append("")
    lines.append(f"- {'PASS' if report['passed'] else 'FAIL'}")
    lines.append("")

    lines.append("## Note")
    lines.append("")
    if is_public_safe:
        lines.append(
            "- This is a public-safe projection (Option B, "
            "Summary_Public_ID_Projection_Design.md §5). Internal IDs "
            "(storyId/episodeId) are rewritten to public IDs; "
            "source.inputRefs is removed; the output filename is "
            "publicStoryId-based."
        )
        lines.append(
            f"- Promotion readiness: {report['promotionReadiness']}. Even when "
            "this projection passes validation and the internal ID exposure "
            "scan, a promotion copy step (not yet implemented) and "
            "review.status enforcement (validate_story_summaries.py "
            "--require-reviewed) are still required before committing to "
            "knowledge/summaries/stories/."
        )
    else:
        lines.append(
            "- This is a compatible projection only (Option A, "
            "Summary_Public_ID_Projection_Design.md §5). Internal IDs "
            "(storyId/episodeId) remain unchanged in the output."
        )
        lines.append(
            "- The output is NOT promotion-ready: it must not be committed to "
            "knowledge/summaries/stories/."
        )
    lines.append(
        "- The mapping output contains internal IDs alongside public IDs and "
        "must never be committed (Internal Review Evidence Packet candidate, "
        "not yet implemented)."
    )
    if report["registryPath"]:
        lines.append(
            "- Registry completion only reuses publicEpisodeId values that a "
            "human has already reviewed and recorded in the Public ID Registry "
            "(docs/architecture/06_AI/Public_ID_Registry_Design.md); this "
            "script never invents new publicEpisodeId values, and never "
            "completes publicStoryId from the registry (structurally not "
            "possible, Summary_Public_ID_Projection_Design.md §7.3)."
        )
    lines.append("")
    return lines


def _print_summary(report: dict[str, Any], *, quiet: bool) -> None:
    if quiet:
        return
    print(
        f"[projection] mode={report['projectionMode']} "
        f"{report['fileCount']} ファイル、{report['storyCount']} stories、"
        f"{report['episodeCount']} episodes"
    )
    print(
        f"[projection] missing_public_story_id={report['missingPublicStoryIdCount']} "
        f"missing_public_episode_id={report['missingPublicEpisodeIdCount']} "
        f"registry_conflicts={report['registryConflictCount']}"
    )
    if report["projectionMode"] == PROJECTION_MODE_PUBLIC_SAFE:
        print(
            f"[projection] public-safe: internal_id_exposure="
            f"{report['internalIdExposureCount']} "
            f"promotion_readiness={report['promotionReadiness']}"
        )
    if report["issues"]:
        print(f"[エラー] {len(report['issues'])}件のissueがあります:", file=sys.stderr)
        for issue in report["issues"]:
            print(f"  - {issue}", file=sys.stderr)
    for warning in report["warnings"]:
        print(f"[警告] {warning}")
    print(f"[projection] 結果: {'PASS' if report['passed'] else 'FAIL'}")


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------


def _prepare_main_inputs(
    args: argparse.Namespace,
) -> tuple[dict[str, Any] | None, int | None]:
    """schema読み込み・`--input`パス収集・出力先安全確認・`--input`の
    schema検証をまとめて行う。戻り値: (context, exit_code)。"""
    schema_path = Path(args.schema)
    if not schema_path.exists():
        print(
            f"[エラー] schemaファイルが見つかりません: {schema_path}", file=sys.stderr
        )
        return None, 2
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    input_path = Path(args.input)
    yaml_paths = _collect_yaml_paths(input_path)
    if yaml_paths is None:
        print(f"[エラー] --inputパスが見つかりません: {input_path}", file=sys.stderr)
        return None, 2

    output_dir = Path(args.output)
    mapping_output_path = Path(args.mapping_output)
    report_path = Path(args.report)
    for label, path in (
        ("--output", output_dir),
        ("--mapping-output", mapping_output_path),
        ("--report", report_path),
    ):
        if _is_under_forbidden_dir(path):
            print(
                f"[エラー] {label}にknowledge/summaries・knowledge/public_ids"
                f"配下のpathは指定できません: {path}",
                file=sys.stderr,
            )
            return None, 2

    raw_documents, schema_errors = _load_yaml_documents(yaml_paths, schema)
    if schema_errors:
        print("[エラー] 入力のschema検証に失敗しました:", file=sys.stderr)
        for issue in schema_errors:
            print(f"  - {issue}", file=sys.stderr)
        return None, 2

    return {
        "schema": schema,
        "input_path": input_path,
        "output_dir": output_dir,
        "mapping_output_path": mapping_output_path,
        "report_path": report_path,
        "raw_documents": raw_documents,
    }, None


def main() -> int:
    args = parse_args()

    context, error_code = _prepare_main_inputs(args)
    if error_code is not None:
        return error_code

    schema = context["schema"]
    input_path = context["input_path"]
    output_dir = context["output_dir"]
    mapping_output_path = context["mapping_output_path"]
    report_path = context["report_path"]
    raw_documents = context["raw_documents"]

    evidence_mapping_path = (
        Path(args.evidence_mapping) if args.evidence_mapping else None
    )
    evidence_lookup, evidence_mapping_error_code = _load_evidence_mapping(
        evidence_mapping_path
    )
    if evidence_mapping_error_code is not None:
        return evidence_mapping_error_code

    registry_lookup, registry_error_code = _resolve_registry_lookup(args)
    if registry_error_code is not None:
        return registry_error_code

    registry_step = _apply_registry_and_build_metadata(raw_documents, registry_lookup)

    missing_public_story_id, story_id_issues = _check_missing_public_story_id(
        raw_documents
    )
    missing_public_episode_id, episode_id_issues = _check_missing_public_episode_id(
        raw_documents
    )

    rewrite_result = _rewrite_documents(
        raw_documents, mode=args.projection_mode, evidence_lookup=evidence_lookup
    )

    schema_issues = _validate_documents_against_schema(
        rewrite_result["outputDocuments"], schema
    )

    issues: list[str] = (
        story_id_issues + episode_id_issues + registry_step["issues"] + schema_issues
    )
    warnings: list[str] = registry_step["warnings"] + rewrite_result["evidenceWarnings"]

    story_count = len({doc.get("storyId") for _, doc in raw_documents})
    episode_count = sum(
        len(doc.get("episodeSummaries", []) or []) for _, doc in raw_documents
    )

    meta_values = list(registry_step["metaByEpisodeId"].values())

    is_public_safe = args.projection_mode == PROJECTION_MODE_PUBLIC_SAFE

    public_safe_extras = {
        "issues": [],
        "internalIdExposureCount": 0,
        "internalIdExposureDetails": [],
        "rewrittenIdFieldsCount": 0,
        "removedInternalFieldsCount": 0,
    }
    if is_public_safe:
        public_safe_extras = _run_public_safe_checks(raw_documents, rewrite_result)
        issues = issues + public_safe_extras["issues"]

    passed = not issues
    promotion_readiness = (
        "promotion-candidate" if (is_public_safe and passed) else "not-promotion-ready"
    )

    written_paths = _write_documents(
        output_dir, rewrite_result["outputDocuments"], clean=args.clean
    )

    _write_mapping_csv(
        mapping_output_path,
        raw_documents,
        meta_by_episode_id=registry_step["metaByEpisodeId"],
        episode_evidence_stats=rewrite_result["episodeEvidenceStats"],
        story_evidence_stats=rewrite_result["storyEvidenceStats"],
    )

    evidence_refs_converted_count, evidence_refs_cleared_count = (
        _sum_evidence_ref_counts(rewrite_result)
    )

    report = {
        "input": str(input_path),
        "output": str(output_dir),
        "mappingOutput": str(mapping_output_path),
        "evidenceMapping": str(evidence_mapping_path)
        if evidence_mapping_path
        else None,
        "projectionMode": args.projection_mode,
        "fileCount": len(raw_documents),
        "storyCount": story_count,
        "episodeCount": episode_count,
        "missingPublicStoryIdCount": len(missing_public_story_id),
        "missingPublicEpisodeIdCount": len(missing_public_episode_id),
        "registryPath": str(args.registry) if args.registry else None,
        "registryStoriesCount": len({key[0] for key in (registry_lookup or {})}),
        "registryEpisodesCount": len(registry_lookup or {}),
        "entriesFromInputCount": sum(1 for m in meta_values if m["source"] == "input"),
        "entriesFromRegistryCount": sum(
            1 for m in meta_values if m["source"] == "registry"
        ),
        "entriesMissingAfterRegistryCount": sum(
            1 for m in meta_values if m["source"] == "missing"
        ),
        "registryConflictCount": sum(1 for m in meta_values if m["registryConflict"]),
        "evidenceRefsConvertedCount": evidence_refs_converted_count,
        "evidenceRefsClearedCount": evidence_refs_cleared_count,
        "storiesPromotedWithoutEvidenceRefsCount": rewrite_result[
            "storiesPromotedWithoutEvidenceRefsCount"
        ],
        "rewrittenIdFieldsCount": public_safe_extras["rewrittenIdFieldsCount"],
        "removedInternalFieldsCount": public_safe_extras["removedInternalFieldsCount"],
        "internalIdExposureCount": public_safe_extras["internalIdExposureCount"],
        "internalIdExposureDetails": public_safe_extras["internalIdExposureDetails"],
        "promotionReadiness": promotion_readiness,
        "issues": issues,
        "warnings": warnings,
        "passed": passed,
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
